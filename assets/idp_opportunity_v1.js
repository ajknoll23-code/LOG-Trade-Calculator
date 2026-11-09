/* LOG IDP Opportunity V1 — standalone, read-only, season-snapshot research.
   Never accesses or changes player FV, canonical valuations, or sort order. */
(() => {
  'use strict';
  const root = document.getElementById('idpoPanel');
  if (!root) return;
  const $ = id => document.getElementById(id);
  const el = {
    note:$('idpoNote'), status:$('idpoStatus'), count:$('idpoCount'), list:$('idpoItems'),
    pos:$('idpoPosition'), scope:$('idpoScope'), lens:$('idpoLens'),
    search:$('idpoSearch'), young:$('idpoYoung'), strong:$('idpoStrong'), more:$('idpoMore')
  };
  const base='https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/main/';
  const url=p=>base+p+'?t='+Date.now();
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=(v,d=1)=>Number.isFinite(v)?v.toFixed(d):'—';
  const text=v=>String(v??'').trim().toLowerCase();
  const id=v=>String(v??'');
  const POS={LB:'Linebacker',S:'Safety',CB:'Cornerback',ED:'EDGE',DI:'Interior DL'};
  const ROS={LB:'LB',S:'S',CB:'CB',ED:'EDGE',DI:'DT'};
  const RATE_CUT={LB:[16,15,14,13],S:[12,11,10,9],CB:[10,9,8,7]};
  const LABELS=['Elite','Outstanding','Strong','Positive'];
  let season=null,free=null,rosters=null,rank=null,me=null,entries=[],visibleLimit=12;
  const idsFree=new Map(), idsRoster=new Map(), idsRank=new Map();
  function allRosterPlayers(team){return ['starters','bench','taxi','reserve_ir'].flatMap(k=>team[k]||[]);}
  function statusFor(p){
    if(!p.sleeper_id) return 'Identity unresolved';
    if(idsRoster.has(id(p.sleeper_id)))return 'Rostered';
    if(idsFree.has(id(p.sleeper_id)))return 'Available';
    return 'Availability unresolved';
  }
  function rateGrade(p){
    if(p.tackle_rate_pct===null)return {label:'Missing rate',tier:-1};
    const cut=RATE_CUT[p.position];
    if(!cut)return {label:'No tackle grade for DL',tier:-1};
    for(let i=0;i<cut.length;i++)if(p.tackle_rate_pct>=cut[i])return {label:LABELS[i],tier:4-i};
    return {label:'Below screening threshold',tier:0};
  }
  function usage(p){return p.position==='CB'?['Slot alignment',p.slot_rate_pct]:
    p.position==='S'?['Box alignment',p.box_rate_pct]:
    p.position==='LB'?['Box alignment',p.box_rate_pct]:
    ['DL alignment',p.dl_rate_pct];}
  function rankOf(p){const r=idsRank.get(id(p.sleeper_id));return r&&r.group===ROS[p.position]?r:null;}
  function decorated(p){
    const person=idsFree.get(id(p.sleeper_id))||idsRoster.get(id(p.sleeper_id))||{};
    return {...p, age:Number.isInteger(person.age)?person.age:null, injury:person.injury_status||null,
      available:statusFor(p)==='Available', ownership:statusFor(p), grade:rateGrade(p), rank:rankOf(p)};
  }
  function explain(p){
    const amount=p.grade.tier>=1?`${p.grade.label.toLowerCase()} tackle-rate tier for ${POS[p.position]}`:
      'Tackle efficiency alone does not establish a dependable fantasy role';
    if(p.position==='ED'||p.position==='DI')return `Season alignment and workload only; pressure and pass-rush win rates are absent from this CSV. ${p.games_played} games, ${p.defensive_snaps} snaps.`;
    const caution=p.defensive_snaps<300?' Small sample near the 200-snap source minimum.':'';
    return `${amount}. ${fmt(p.snaps_per_game)} defensive snaps per recorded game.${caution} Weekly trend not yet established.`;
  }
  function card(p){
    const [usageLabel,usagePct]=usage(p), r=p.rank;
    const badge=p.grade.tier>=3?' idpo-good':'';
    return `<article class="idpo-card" data-player-id="${esc(p.sleeper_id||'')}" aria-label="${esc(p.name)}">
      <div class="idpo-card-top"><div class="idpo-main"><strong>${esc(p.name)}</strong><span>${esc(p.team_at_source)} · ${esc(POS[p.position])} · ${p.age===null?'Age unknown':'Age '+p.age} · ${esc(p.ownership)}</span></div>
      <div class="idpo-grade${badge}">${esc(p.grade.label)}</div></div>
      <div class="idpo-facts">
        <div><span>Tackle rate</span><b>${p.tackle_rate_pct===null?'Missing':fmt(p.tackle_rate_pct)+'%'}</b></div>
        <div><span>${esc(usageLabel)}</span><b>${fmt(usagePct)}%</b></div>
        <div><span>Def. snaps</span><b>${p.defensive_snaps}</b></div>
        <div><span>Snaps/game</span><b>${fmt(p.snaps_per_game)}</b></div>
      </div>
      <div class="idpo-tags"><span>${r?esc(r.group)+' #'+r.rank:'No supplied ROS rank'}</span><span>${p.games_played} games</span>${p.injury?'<span class="idpo-alert">'+esc(p.injury)+'</span>':''}</div>
      <details class="idpo-details"><summary>Why monitor this player?</summary><div class="idpo-explanation">${esc(explain(p))}<br>Source: owner-supplied 2026 season snapshot; ROS: frozen Nov 7 IDP Show rankings. No multiweek breakout claim and no valuation change.</div></details>
    </article>`;
  }
  function order(a,b){
    const lens=el.lens.value;
    // Explicit decision aids, not fitted projections or blended cross-position rankings.
    if(lens==='dynasty'){
      const ay=a.age!==null&&a.age<=25, by=b.age!==null&&b.age<=25;
      if(ay!==by)return ay?-1:1;
      if(a.age!==b.age)return (a.age??99)-(b.age??99);
      return b.grade.tier-a.grade.tier||b.snaps_per_game-a.snaps_per_game;
    }
    return b.grade.tier-a.grade.tier||b.snaps_per_game-a.snaps_per_game||b.defensive_snaps-a.defensive_snaps;
  }
  function render(){
    if(!season)return;
    const position=el.pos.value, scope=el.scope.value, query=text(el.search.value);
    const ownIds=new Set(allRosterPlayers(me).map(p=>id(p.player_id)));
    let items=entries.filter(p=>(position==='ALL'||p.position===position)&&
      (!query||text(p.name).includes(query))&&
      (scope==='all'||(scope==='available'&&p.available)||(scope==='mine'&&ownIds.has(id(p.sleeper_id))))&&
      (!el.young.checked||(p.age!==null&&p.age<=25))&&
      (!el.strong.checked||p.grade.tier>=2));
    // Never imply that LB / S / CB tackle rates share a common scale.
    items.sort((a,b)=>(position==='ALL'?(['LB','S','CB','ED','DI'].indexOf(a.position)-['LB','S','CB','ED','DI'].indexOf(b.position)):0)||order(a,b)||a.name.localeCompare(b.name));
    el.count.textContent=items.length+' matching players';
    el.list.innerHTML=items.slice(0,visibleLimit).map(card).join('')||'<div class="idpo-empty">No players match these filters. Try widening your position or availability filter.</div>';
    el.more.hidden=items.length<=visibleLimit;
    el.more.textContent='Show more ('+(items.length-visibleLimit)+' remaining)';
    const group=position==='ALL'?'separate position groups':POS[position];
    el.note.textContent=`Viewing ${group}. Sort: ${el.lens.value==='dynasty'?'age ≤25 first, then age, then grade':'position-specific tackle grade, then snaps/game'}. These are scouting filters, not predictions. The season CSV has no weekly trend or pressure-rate history.`;
  }
  function strictValidate(s,fa,ranks,rs,config){
    if(s?.schema_version!==1||s.policy!=='READ_ONLY_RESEARCH_NOT_FV_OR_PROJECTION'||s.counts?.players!==436||!Array.isArray(s.players)||s.players.length!==436)throw Error('Invalid season usage snapshot');
    const observed={LB:0,S:0,CB:0,ED:0,DI:0};
    const matched=new Set();
    for(const p of s.players){
      if(!POS[p.position]||!Number.isInteger(p.defensive_snaps)||p.defensive_snaps<200||!Number.isInteger(p.games_played)||p.games_played<1||!p.name)throw Error('Malformed season usage record');
      observed[p.position]++;
      for(const key of ['tackle_rate_pct','box_rate_pct','slot_rate_pct','deep_rate_pct','dl_rate_pct','wide_cb_rate_pct']){
        if(p[key]!==null&&(!Number.isFinite(p[key])||p[key]<0||p[key]>100))throw Error('Malformed percentage metric '+key);
      }
      if(p.sleeper_id){if(!/^\d+$/.test(id(p.sleeper_id))||matched.has(id(p.sleeper_id)))throw Error('Duplicate or invalid season Sleeper ID');matched.add(id(p.sleeper_id));}
    }
    if(Object.entries({LB:75,S:85,CB:92,ED:91,DI:93}).some(([k,v])=>observed[k]!==v))throw Error('Season source population changed');
    if(!Array.isArray(fa?.free_agents)||fa.count!==fa.free_agents.length||fa.league_id!==rs.league_id||!Array.isArray(rs.rosters)||rs.rosters.length!==12)throw Error('Incomplete LOG league snapshots');
    if(!Array.isArray(ranks?.records)||ranks.records.length!==300||ranks.rank_policy!=='FROZEN_SCREENSHOT_DISPLAY_ONLY')throw Error('Invalid expert ROS snapshot');
    const owner=rs.rosters.find(x=>x.team_name===config.my_team_name||x.owner_username===config.my_username);
    if(!owner)throw Error('Owner roster unresolved');
    return owner;
  }
  async function init(){
    try{
      const paths=['data/idp_usage_2026_season.json','data/free_agents.json','data/idp_ros_2026_w09.json','data/league_rosters.json','config.json'];
      const responses=await Promise.all(paths.map(p=>fetch(url(p),{cache:'no-store'})));
      if(responses.some(r=>!r.ok))throw Error('One or more source files unavailable');
      const [s,fa,ranks,rs,config]=await Promise.all(responses.map(x=>x.json()));
      me=strictValidate(s,fa,ranks,rs,config);
      season=s;free=fa;rank=ranks;rosters=rs;
      fa.free_agents.forEach(p=>idsFree.set(id(p.player_id),p));
      rs.rosters.flatMap(allRosterPlayers).forEach(p=>idsRoster.set(id(p.player_id),p));
      if([...idsFree.keys()].some(k=>idsRoster.has(k)))throw Error('Available/rostered ID overlap; cannot confirm availability');
      ranks.records.filter(r=>r.sleeper_id).forEach(r=>idsRank.set(id(r.sleeper_id),r));
      entries=s.players.map(decorated);
      const matched=entries.filter(p=>p.sleeper_id).length;
      const hrs=(Date.now()-Number(fa.synced_at)*1000)/3600000;
      const when=Number.isFinite(fa.synced_at)?new Date(fa.synced_at*1000).toLocaleString():'unknown';
      const warn=hrs>48?' · WARNING: Sleeper data over 48 hours old; verify availability before claiming.':'';
      el.status.textContent=`2026 season snapshot: ${s.players.length} players (${matched} matched IDs). Sleeper availability synced ${when}.${warn}`;
      render();
    }catch(err){
      el.status.textContent='IDP Opportunity unavailable: '+String(err?.message||err)+'; existing free-agent board and IDP rankings are unaffected.';
      el.status.classList.add('idpo-error');
      el.list.textContent='';
      el.count.textContent='Data unavailable';
    }
  }
  for(const control of [el.pos,el.scope,el.lens,el.young,el.strong])control.addEventListener('change',()=>{visibleLimit=12;render();});
  el.search.addEventListener('input',()=>{visibleLimit=12;render();});
  el.more.addEventListener('click',()=>{visibleLimit+=12;render();});
  init();
})();
