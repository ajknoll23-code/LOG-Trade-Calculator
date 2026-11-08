/* A-FA03R1 IDP Waiver Intelligence -- display-only and fail-closed.
   Source ranks are frozen user-provided IDP Show ROS screenshots, not live projections.
   No access to, or mutation of, PLAYER_DB, FV, role multipliers or board sorting. */
(() => {
  'use strict';
  const root = document.getElementById('idpiPanel');
  if (!root) return;
  const $ = id => document.getElementById(id);
  const el = {
    status:$('idpiStatus'), panel:$('idpiItems'),
    group:$('idpiGroup'), lens:$('idpiLens'), view:$('idpiView'), search:$('idpiSearch'),
    sub:$('idpiSubline'), count:$('idpiCount')
  };
  const sourceRoot = 'https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/main/';
  const ext = s => sourceRoot + s + '?t=' + Date.now();
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeInt = x => Number.isInteger(x) && x > 0 ? x : 0;
  const key = x => String(x ?? '');
  const txt = x => String(x ?? '').trim().toLowerCase();
  const minor = str => `<span class="idpi-muted">${esc(str)}</span>`;
  const label = r => r ? r.label : 'Not in supplied top list';
  const groupOf = g => (g === 'EDGE' || g === 'DT' ? 'DL' : (g === 'S' || g === 'CB' ? 'DB' : 'LB'));
  const ranksMin = { EDGE:70, DT:30, S:65, CB:35, LB:100 };
  const EDITORIAL = {
    contender: ['8323','12619','12604','7811','10873','8355','4999','5864','5297','11328','7677','8680','5580','13555'],
    dynasty: ['12619','12604','12673','10873','8355','11328','8323','7811','13555','5864','4999','5297','8680','5580']
  };
  const REASONS = {
    '8323':'Consistent tackle-oriented safety candidate; verify latest usage.',
    '12619':'Age-23 safety with dynasty runway; compare weekly tackle volume.',
    '12604':'Young safety worth tracking for snaps and tackle role.',
    '7811':'Highest-ranked available S in the supplied list; check injury status.',
    '10873':'Highest-ranked available EDGE in the supplied list; sack-dependent profile.',
    '8355':'Age-25 EDGE candidate; compare recent snaps and pressure opportunities.',
    '4999':'Veteran EDGE depth for a title run; check current pass-rush production.',
    '5864':'CB004 in the supplied list; verify tackle-friendly usage before starting.',
    '5297':'DT013 in the supplied list; DL depth, not directly comparable to EDGE ranks.',
    '11328':'DT018 at age 27; longer-term DL watch candidate.',
    '12673':'Age-23 safety: potential dynasty bench/taxi watch.',
    '7677':'LB043, but check questionable injury tag and real playing time.',
    '8680':'LB055; high earlier-week snaps, verify latest before adding.',
    '5580':'LB040; name reputation alone is not enough for a claim.',
    '13555':'Age-22 speculative LB; stash profile over a proven weekly starter.'
  };
  const COMPARES = [
    ['8323','8334'],['12619','8334'],['12604','8334'],['7811','8334'],
    ['10873','7018'],['8355','7018'],['4999','7018'],['5297','7018'],
    ['13555','8334']
  ];
  let src=null, liveFa=null, liveRosters=null, me=null;
  let byRankId=new Map(), byFa=new Map(), byRoster=new Map();
  let view='waiver', group='ALL', lens='contender', query='';

  function activePlayers(roster){
    return ['starters','bench'].flatMap(slot => (roster?.[slot] || []).map(p => ({...p, slot})));
  }
  function allPlayers(roster){
    return ['starters','bench','taxi','reserve_ir'].flatMap(slot => (roster?.[slot] || []).map(p => ({...p, slot})));
  }
  function pos(p){
    const positions = (p.fantasy_positions || []).map(x => String(x).toUpperCase());
    for (const [short, variants] of [
      ['DL',['DL','DE','DT']],['LB',['LB','ILB','OLB']],['DB',['DB','S','SS','FS','CB']],
      ['QB',['QB']],['RB',['RB']],['WR',['WR']],['TE',['TE']],['K',['K']]
    ]) if (positions.some(x => variants.includes(x))) return short;
    const raw=String(p.position||p.pos||'').toUpperCase();
    if(['DE','DT','DL','NT'].includes(raw)) return 'DL';
    if(['S','FS','SS','CB','DB'].includes(raw)) return 'DB';
    return raw;
  }
  function legal17(players){
    let remaining = players.map(p => ({...p,elig:pos(p)}));
    let count=0;
    const pick = (allowed,n) => {
      for(let i=0;i<n;i++){
        const ix=remaining.findIndex(p=>allowed.includes(p.elig));
        if(ix===-1)return;
        remaining.splice(ix,1); count++;
      }
    };
    [['QB',1],['RB',2],['WR',2],['TE',1],['DL',2],['LB',2],['DB',2],['K',1]]
      .forEach(([p,n]) => pick([p],n));
    pick(['RB','WR','TE'],1);
    pick(['QB','RB','WR','TE'],1);
    pick(['DL','LB','DB'],2);
    return count===17;
  }
  function scopeRank(row){return groupOf(row.group);}
  function statusText(row){
    const fa=byFa.get(key(row.sleeper_id));
    const own=byRoster.get(key(row.sleeper_id));
    return own ? 'Rostered' : fa ? 'Available' : 'Not matched in league';
  }
  function ageText(p){return Number.isInteger(p.age) ? `Age ${p.age}` : 'Age unknown';}
  function recordItem(row){
    const fa=byFa.get(key(row.sleeper_id));
    const own=byRoster.get(key(row.sleeper_id));
    return {row,fa,own,id:key(row.sleeper_id),label:label(row)};
  }
  function sourceTime(epoch){
    const v=Number(epoch);
    return Number.isFinite(v) && v>0 ? new Date(v*1000).toLocaleString() : 'unknown';
  }
  function freshnessWarning(){
    if(!liveFa?.synced_at)return 'Availability unavailable';
    const hrs=(Date.now()-Number(liveFa.synced_at)*1000)/3600000;
    return hrs>48 ? `Availability is ${Math.floor(hrs)} hours old; refresh Sleeper.` : '';
  }
  function isAllowed(row){return group==='ALL'||scopeRank(row)===group;}
  function withinSearch(name){return !query||txt(name).includes(query);}
  function rowHeader(){
    return `<div class="idpi-meta">The IDP Show · user-provided frozen 2026 ROS ranks (Nov 7) · availability refreshed ${esc(sourceTime(liveFa.synced_at))} · ${esc(src?.records?.length)} total ranked players</div>`;
  }
  function chip(value,variant){return `<span class="idpi-chip ${variant||''}">${esc(value)}</span>`;}
  function rankTag(row){return `<strong class="idpi-rank">${esc(row.label)}</strong>`;}
  function waiverCard(o,number){
    const {row,fa}=o, injury=fa?.injury_status, status=fa?.status;
    const injuryTag=injury ? chip(injury,'idpi-risk') : (status==='Inactive'?chip('Inactive','idpi-risk'):'');
    const reason=REASONS[o.id]||`Expert ${row.group} rank ${row.rank}; verify production, snaps, and role before claiming.`;
    return `<article class="idpi-card">
      <div class="idpi-card-head"><span class="idpi-ordinal">${number}</span><div class="idpi-player-title">${esc(fa?.name||row.name)}</div>${rankTag(row)}</div>
      <div class="idpi-info">${chip(row.group)}${chip(row.team)} ${ageText(fa||{})} ${injuryTag}</div>
      <p class="idpi-note">${esc(reason)}</p>
    </article>`;
  }
  function renderWaiver(){
    const ranked=src.records.filter(r=>r.sleeper_id && isAllowed(r) && withinSearch(r.name) && byFa.has(key(r.sleeper_id)));
    const priority=EDITORIAL[lens];
    ranked.sort((a,b)=>{
      const ai=priority.indexOf(key(a.sleeper_id)),bi=priority.indexOf(key(b.sleeper_id));
      if(ai>=0 && bi<0)return -1;
      if(bi>=0 && ai<0)return 1;
      if(ai>=0 && bi>=0)return ai-bi;
      // No false cross-position equivalence: group then rank.
      return ({S:0,EDGE:1,LB:2,DT:3,CB:4}[a.group]-{S:0,EDGE:1,LB:2,DT:3,CB:4}[b.group]) || a.rank-b.rank;
    });
    const list=ranked.slice(0,10).map((r,i)=>waiverCard(recordItem(r),i+1)).join('');
    const totals={DL:0,LB:0,DB:0};
    src.records.filter(r=>r.sleeper_id&&byFa.has(key(r.sleeper_id))).forEach(r=>totals[scopeRank(r)]++);
    return `<div class="idpi-brief">${chip('Research shortlist','idpi-highlight')}
      ${minor(`Available from supplied ranks: ${totals.DL} DL · ${totals.LB} LB · ${totals.DB} DB. Sorting is editorial, not an FV or algorithmic claim.`)}</div>
      ${list||'<p class="idpi-empty">No ranked free agents match this filter.</p>'}`;
  }
  function renderRoster(){
    let rows=allPlayers(me).filter(p=>['DL','LB','DB'].includes(pos(p)) && (group==='ALL'||pos(p)===group) && withinSearch(p.name));
    rows=rows.map(p=>({p,rank:byRankId.get(key(p.player_id))}));
    const sectionOrder={DL:0,LB:1,DB:2};
    rows.sort((a,b)=>{
      const ga=pos(a.p),gb=pos(b.p);
      if(ga!==gb) return sectionOrder[ga]-sectionOrder[gb];
      if(a.rank && b.rank && a.rank.group===b.rank.group)return a.rank.rank-b.rank.rank;
      if(a.rank&&!b.rank)return -1;
      if(b.rank&&!a.rank)return 1;
      return a.p.name.localeCompare(b.p.name);
    });
    const counts={DL:0,LB:0,DB:0};
    allPlayers(me).filter(p=>['DL','LB','DB'].includes(pos(p))).forEach(p=>counts[pos(p)]++);
    const lines=rows.map(({p,rank})=>`<div class="idpi-roster-row">
      <div><strong>${esc(p.name)}</strong><div class="idpi-secondary">${esc(pos(p))} · ${esc(p.slot.replace('_',' '))} · ${ageText(p)}${p.injury_status?' · '+esc(p.injury_status):''}</div></div>
      <div class="idpi-right">${rank?rankTag(rank):minor('No supplied ROS rank')}${rank?`<div class="idpi-secondary">${esc(rank.group)}</div>`:''}</div>
    </div>`).join('');
    return `<div class="idpi-brief">${chip('Your IDP roster','idpi-highlight')}${minor(`${counts.DL} DL · ${counts.LB} LB · ${counts.DB} DB (includes taxi and IR). ROS rank is separate from dynasty FV.`)}</div>${lines||'<p class="idpi-empty">No players match this filter.</p>'}`;
  }
  function renderAllAvailable(){
    const order={EDGE:0,DT:1,LB:2,S:3,CB:4};
    const listed=src.records.filter(r=>r.sleeper_id && isAllowed(r) && withinSearch(r.name) && byFa.has(key(r.sleeper_id)))
      .sort((a,b)=>order[a.group]-order[b.group] || a.rank-b.rank);
    const rows=listed.map(r=>{
      const p=byFa.get(key(r.sleeper_id));
      return `<div class="idpi-roster-row"><div><strong>${esc(p.name)}</strong><div class="idpi-secondary">${esc(r.group)} · ${esc(r.team)} · ${ageText(p)}${p.injury_status?' · '+esc(p.injury_status):''}</div></div><div class="idpi-right">${rankTag(r)}</div></div>`;
    }).join('');
    return `<div class="idpi-brief">${chip('All ranked available IDPs','idpi-highlight')}${minor(`${listed.length} rank matches; ordered within EDGE, DT, LB, S, then CB (not one blended rank).`)}</div>${rows || '<p class="idpi-empty">No ranked free agents match this filter.</p>'}`;
  }
  function renderCompare(){
    const own=allPlayers(me);
    const pairs=COMPARES.map(([faId,dropId])=>{
      const add=byFa.get(faId),drop=own.find(p=>key(p.player_id)===dropId);
      if(!add||!drop)return null;
      const addRank=byRankId.get(faId),dropRank=byRankId.get(dropId);
      if(!addRank||!isAllowed(addRank)||!withinSearch(add.name))return null;
      const legal=legal17(activePlayers(me).filter(p=>key(p.player_id)!==dropId).concat([{...add,position:add.pos}]));
      return `<article class="idpi-compare">
        <div><div class="idpi-compare-caption">Investigate adding</div><strong>${esc(add.name)}</strong><div>${rankTag(addRank)} ${chip(addRank.group)}</div></div>
        <div class="idpi-swap">⇄</div>
        <div><div class="idpi-compare-caption">Possible roster spot</div><strong>${esc(drop.name)}</strong><div>${dropRank?rankTag(dropRank):minor('Unranked in supplied set')} ${chip(pos(drop))}</div></div>
        <div class="idpi-compare-foot">${chip(legal?'17-slot coverage maintained':'Lineup constraint needs review',legal?'idpi-pass':'idpi-risk')}<span>Not a trade-value or salary-cap decision</span></div>
      </article>`;
    }).filter(Boolean);
    return `<div class="idpi-brief">${chip('Roster churn ideas','idpi-highlight')}${minor('Only available players paired with someone on your current active roster. This tests positional lineup coverage, NOT cap, contracts, waiver priority, or projected points.')}</div>${pairs.join('')||'<p class="idpi-empty">No proposed comparisons currently match.</p>'}`;
  }
  function render(){
    if(!src || !liveFa || !me)return;
    el.status.textContent='';
    const warning=freshnessWarning();
    el.sub.innerHTML=(warning?`<div class="idpi-stale">${esc(warning)}</div>`:'')+rowHeader()+
      `<div class="idpi-disclaimer">EDGE, DT, S, CB and LB use separate ranks. Not live fantasy-points rankings. Snapshot ranks never alter FV, FV+, draft picks, optimizer or waiver-priority calculations.</div>`;
    if(el.lens){el.lens.disabled=view!=='waiver';}
    if(view==='roster')el.panel.innerHTML=renderRoster();
    else if(view==='all')el.panel.innerHTML=renderAllAvailable();
    else if(view==='compare')el.panel.innerHTML=renderCompare();
    else el.panel.innerHTML=renderWaiver();
  }
  function validated(source,fa,roster,config){
    if(source?.schema_version!==1 || source.rank_policy!=='FROZEN_SCREENSHOT_DISPLAY_ONLY' || !Array.isArray(source.records) || source.records.length!==300)throw Error('ROS snapshot not verified (expected 300 rows)');
    const counts={EDGE:0,DT:0,S:0,CB:0,LB:0},seen=new Set();
    for(const row of source.records){
      if(!ranksMin[row.group] || row.rank<1 || row.rank>ranksMin[row.group] || !row.label)throw Error('Malformed expert-rank row');
      counts[row.group]++;
      const k=row.group+'|'+row.rank;
      if(seen.has(k))throw Error('Duplicate rank '+k);
      seen.add(k);
      if(row.sleeper_id && !/^\d+$/.test(String(row.sleeper_id)))throw Error('Invalid Sleeper ID');
    }
    for(const [g,n] of Object.entries(ranksMin))if(counts[g]!==n)throw Error('Rank count mismatch '+g);
    if(!Array.isArray(fa?.free_agents) || !Array.isArray(roster?.rosters) || fa.league_id!==roster.league_id || roster.rosters.length!==12)throw Error('Incomplete league data');
    const own=roster.rosters.find(r=>r.team_name===config.my_team_name || r.owner_username===config.my_username);
    if(!own)throw Error('Configured owner roster not found');
    const freeIds=new Set(fa.free_agents.map(p=>key(p.player_id)));
    const rosterIds=new Set(roster.rosters.flatMap(r=>allPlayers(r)).map(p=>key(p.player_id)));
    if([...freeIds].some(id=>rosterIds.has(id)))throw Error('Rosters/free-agent pool overlap');
    return own;
  }
  async function init(){
    try{
      const [rs,fs,rr,cr]=await Promise.all([
        fetch(ext('data/idp_ros_2026_w09.json'),{cache:'no-store'}),
        fetch(ext('data/free_agents.json'),{cache:'no-store'}),
        fetch(ext('data/league_rosters.json'),{cache:'no-store'}),
        fetch(ext('config.json'),{cache:'no-store'})
      ]);
      if([rs,fs,rr,cr].some(r=>!r.ok))throw Error('One or more data files unavailable');
      const [s,f,r,c]=await Promise.all([rs.json(),fs.json(),rr.json(),cr.json()]);
      me=validated(s,f,r,c);
      src=s;liveFa=f;liveRosters=r;
      byRankId=new Map(s.records.filter(x=>x.sleeper_id).map(x=>[key(x.sleeper_id),x]));
      byFa=new Map(f.free_agents.map(x=>[key(x.player_id),x]));
      byRoster=new Map(r.rosters.flatMap(team=>allPlayers(team)).map(p=>[key(p.player_id),p]));
      el.count.textContent=`(${s.records.length} expert ranks)`;
      render();
    }catch(error){
      el.status.textContent='IDP Intelligence unavailable: '+String(error?.message||error)+' — your existing free-agent board is unaffected.';
      el.status.classList.add('idpi-error');
      el.panel.innerHTML='';
    }
  }
  el.view.addEventListener('change',e=>{view=e.target.value;render();});
  el.group.addEventListener('change',e=>{group=e.target.value;render();});
  el.lens.addEventListener('change',e=>{lens=e.target.value;render();});
  el.search.addEventListener('input',e=>{query=txt(e.target.value);render();});
  init();
})();
