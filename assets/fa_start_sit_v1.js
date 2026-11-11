/* LOG A-FA11R1 — owner-local Week 10 two-expert IDP Start/Sit comparison.
 * Public module contains NO subscriber rank data and NO private scouting data.
 * User-selects a local JSON; ranks/projections stay only in this browser tab.
 * Does not modify player valuations, roster transactions, or existing IDP panels.
 */
(() => {
  'use strict';
  function initializeStartSit() {
  const root = document.getElementById('fa-ws-startsit-panel');
  if (!root || root.querySelector('#faSsApp')) return;
  const escape = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const norm = x => String(x ?? '').toLowerCase().replace(/\b(jr|sr|ii|iii|iv)\b/g,'').replace(/[^a-z0-9]/g,'');
  const aliases = new Map([
    ['jtt uimoloau'.replace(' ','') ,'jaylahntuimoloau'],
    ['jttuimoloau','jaylahntuimoloau'],
    ['patjones','patrickjones'],
    ['gregrousseau','gregoryrousseau'],
    ['trevonmoehrig','trevonmoehrig'],
    ['kev inwinston'.replace(' ',''),'kevinwinston'],
  ]);
  const key = name => aliases.get(norm(name)) || norm(name);
  const groupNames = {LB:'Linebacker',EDGE:'EDGE',DT:'Interior DL',S:'Safety',CB:'Cornerback'};
  const groups = Object.keys(groupNames);
  const maxPick=12;
  const trustedClassification='PRIVATE_OWNER_SUPPLIED_WEEKLY_IDP_START_SIT_NOT_FOR_PUBLIC_REPO';
  let catalog=new Map(), userRoster=new Set(), selected=[], ranks=new Map(),rankNames=new Map(), loaded=false, capturedWeek=null, sourceMeta=null;
  let rosterSync=null, catalogReady=false, noRosterError=null;
  root.insertAdjacentHTML('beforeend', `
    <section id="faSsApp" class="fa-ss" aria-labelledby="faSsTitle">
      <div class="fa-ss-steps"><span>1 · Import privately</span><span>2 · Choose 2–12 players</span><span>3 · Compare</span></div>
      <div class="fa-ss-import">
        <label for="faSsFile"><strong>Private weekly expert consensus JSON</strong><small>Choose the provided private file from your phone. Nothing is uploaded, saved, or sent.</small></label>
        <input id="faSsFile" type="file" accept=".json,application/json">
        <div id="faSsStatus" class="fa-ss-status" role="status">Loading the LOG player pool. Import your private Week 10 ranking snapshot to start.</div>
      </div>
      <div class="fa-ss-searchtools">
        <label>Find a player<input id="faSsSearch" type="search" placeholder="Search your roster or free agents" autocomplete="off" aria-label="Search IDP player"></label>
        <label>Where to search<select id="faSsScope"><option value="mine">My roster</option><option value="available">Free agents</option><option value="all">Everyone</option></select></label>
        <label>Position<select id="faSsGroup"><option value="ALL">All IDP</option><option value="LB">LB</option><option value="EDGE">EDGE</option><option value="DT">DT</option><option value="S">S</option><option value="CB">CB</option></select></label>
      </div>
      <div id="faSsSuggestions" class="fa-ss-suggestions" aria-live="polite"></div>
      <div class="fa-ss-selected-heading"><h3>Players to compare <span id="faSsCount">0 / 12</span></h3><button type="button" id="faSsClear">Clear selection</button></div>
      <div id="faSsSelected" class="fa-ss-selected"><p class="fa-ss-empty">Choose any 2–12 players. Your roster and free agents are both supported.</p></div>
      <button type="button" id="faSsCompare" class="fa-ss-compare" disabled>Compare selected players</button>
      <div id="faSsResults" class="fa-ss-results" aria-live="polite"></div>
      <p class="fa-ss-fine">Weekly start/sit guidance, not dynasty value. The IDP Show and Woellert each contribute one rank when present; missing screenshot ranks are not zero. Cross-position rankings are not comparable. Projections are an optional separate Woellert signal and do not count as a third expert.</p>
    </section>`);
  const $=id=>root.querySelector('#'+id);
  const ui={file:$('faSsFile'),status:$('faSsStatus'),search:$('faSsSearch'),scope:$('faSsScope'),group:$('faSsGroup'),suggestions:$('faSsSuggestions'),selected:$('faSsSelected'),count:$('faSsCount'),compare:$('faSsCompare'),clear:$('faSsClear'),results:$('faSsResults')};
  const fail=(condition,message)=>{if(!condition)throw Error(message);};
  const val=(x,d=1)=>typeof x==='number'&&Number.isFinite(x)?x.toFixed(d):'—';
  const strId=x=>String(x?.player_id??'');
  const isIdp=p=>['LB','DL','DB'].includes(p?.pos||p?.position);
  const rosterMembers=t=>['starters','bench','taxi','reserve_ir'].flatMap(k=>Array.isArray(t[k])?t[k]:[]);
  function inferGroup(player){
    const raw=String(player.raw_position||player.position||'').toUpperCase();
    return groups.includes(raw)?raw:(raw==='DE'||raw==='OLB'?'EDGE':raw==='NT'?'DT':null);
  }
  function playerGroup(player){
    const possible=rankNames.get(key(player.name))||[];
    if(possible.length===1)return possible[0].group;
    return inferGroup(player);
  }
  function poolStatus(player){return userRoster.has(player.player_id)?'My roster':player.source==='available'?'Free agent':'Other roster';}
  function validSnap(doc){
    fail(doc&&doc.schema_version===1&&doc.classification===trustedClassification,'Not a LOG private weekly Start/Sit consensus file');
    fail(doc.season===2026&&Number.isInteger(doc.week)&&doc.week>=1&&doc.week<=18,'Season/week mismatch');
    fail(doc.source_scope==='WEEKLY_ONLY_NOT_ROS','This import is not a weekly ranking snapshot');
    fail(Array.isArray(doc.records)&&doc.records.length>=2&&doc.records.length<=500,'Invalid ranking population');
    const next=new Map();
    for(const r of doc.records){
      fail(r&&typeof r.name==='string'&&r.name.length>0&&r.name.length<=100&&groups.includes(r.group),'Invalid rank identity/group');
      const a=r.rankings?.idp_show,b=r.rankings?.woellert;
      for(const n of [a,b])fail(n===null||(Number.isInteger(n)&&n>=1&&n<=200),'Rank must be a positive integer or null');
      fail(a!==null||b!==null,'No source ranks');
      const sig=r.group+'|'+key(r.name);
      fail(!next.has(sig),'Duplicate player/position in imported ranking file');
      fail(r.projection===null||r.projection===undefined||(
        typeof r.projection==='object' &&
        Number.isFinite(r.projection.log_linear_base_points) && r.projection.log_linear_base_points>=0 && r.projection.log_linear_base_points<=150 &&
        Number.isFinite(r.projection.projected_defensive_snaps) && r.projection.projected_defensive_snaps>=0 && r.projection.projected_defensive_snaps<=150),
      'Invalid optional LOG linear projection');
      next.set(sig,r);
    }
    return next;
  }
  function getRank(p){
    const matches=rankNames.get(key(p.name))||[];
    const grp=inferGroup(p);
    const exact=matches.find(r=>r.group===grp);
    if(exact)return exact;
    return matches.length===1?matches[0]:null;
  }
  function present(p){return getRank(p);}
  function synced(){return rosterSync?new Date(rosterSync*1000).toLocaleDateString(): 'unknown date';}
  function chip(p){const r=present(p);return r&&r.rankings.idp_show!==null&&r.rankings.woellert!==null?'2 expert ranks':r?'1 expert rank':'No captured rank';}
  function showMatches(){
    if(!catalogReady)return;
    const query=key(ui.search.value);
    const scope=ui.scope.value,filter=ui.group.value;
    let list=[...catalog.values()].filter(p=>{
      if(scope==='mine'&&!userRoster.has(p.player_id))return false;
      if(scope==='available'&&p.source!=='available')return false;
      if(filter!=='ALL'&&playerGroup(p)!==filter)return false;
      if(query&&!key(p.name).includes(query))return false;
      return !selected.includes(p.player_id);
    });
    if(!query && loaded){list.sort((a,b)=>{
      const ra=present(a),rb=present(b);
      return ((ra&&ra.rankings.idp_show!==null&&ra.rankings.woellert!==null)?0:1)-((rb&&rb.rankings.idp_show!==null&&rb.rankings.woellert!==null)?0:1)
        ||((ra?.consensus_rank??999)-(rb?.consensus_rank??999))||a.name.localeCompare(b.name);
    });}
    else list.sort((a,b)=>a.name.localeCompare(b.name));
    list=list.slice(0,14);
    ui.suggestions.innerHTML=list.length?list.map(p=>`<button type="button" data-add-id="${escape(p.player_id)}" class="fa-ss-candidate">
      <span><strong>${escape(p.name)}</strong><small>${escape(playerGroup(p)||p.position||p.pos)} · ${escape(p.team||'—')} · ${escape(poolStatus(p))}</small></span>
      <span class="fa-ss-candidate-right"><small>${escape(chip(p))}</small><strong aria-hidden="true">+</strong></span>
    </button>`).join(''):'<p class="fa-ss-empty">No matching player found in the current LOG pool. Try another position or player name.</p>';
    ui.suggestions.querySelectorAll('[data-add-id]').forEach(b=>b.addEventListener('click',()=>add(b.dataset.addId)));
  }
  function add(id){
    if(selected.length>=maxPick){ui.status.textContent='Selection limit reached. Remove a player to add another (maximum 12).';return;}
    if(!catalog.has(id)||selected.includes(id))return;
    selected.push(id);refresh();
  }
  function remove(id){selected=selected.filter(x=>x!==id);refresh();}
  function refresh(){
    ui.count.textContent=`${selected.length} / ${maxPick}`;
    ui.selected.innerHTML=selected.length?selected.map(id=>{
      const p=catalog.get(id),r=present(p);
      const label=r?`${r.group} · ${r.rankings.idp_show===null?'IDP Show —':'IDP Show #'+r.rankings.idp_show} · ${r.rankings.woellert===null?'Woellert —':'Woellert #'+r.rankings.woellert}`:'No Week 10 rank in supplied screenshots';
      return `<div class="fa-ss-chip"><span><strong>${escape(p.name)}</strong><small>${escape(poolStatus(p))} · ${escape(label)}</small></span><button type="button" data-remove-id="${escape(id)}" aria-label="Remove ${escape(p.name)}">Remove</button></div>`;
    }).join(''):'<p class="fa-ss-empty">Choose any 2–12 players. Your roster and free agents are both supported.</p>';
    ui.selected.querySelectorAll('[data-remove-id]').forEach(b=>b.addEventListener('click',()=>remove(b.dataset.removeId)));
    ui.compare.disabled=!loaded||selected.length<2;
    ui.results.textContent='';showMatches();
  }
  function dataOf(p){
    const r=getRank(p),a=r?.rankings.idp_show??null,b=r?.rankings.woellert??null;
    return {p,r,a,b,n:(a===null?0:1)+(b===null?0:1),avg:a===null||b===null?null:(a+b)/2,gap:a===null||b===null?null:Math.abs(a-b),group:r?.group||playerGroup(p)||'UNKNOWN'};
  }
  function fmtNum(n){return Number.isInteger(n)?String(n):val(n,1);}
  function explain(groupData){
    if(groupData.length===1)return '<p class="fa-ss-caveat">Only one selected player is in this position group. There is no within-position matchup to compare.</p>';
    const both=groupData.filter(x=>x.n===2);
    if(both.length<2)return '<p class="fa-ss-caveat">Fewer than two players have both experts’ captured position ranks. No defensible two-expert start lean for this group.</p>';
    both.sort((a,b)=>a.avg-b.avg);
    const first=both[0],second=both[1];
    if(first.avg===second.avg)return '<p class="fa-ss-caveat">The two leading players are tied on average expert rank; treat the decision as unresolved.</p>';
    const idpPref=first.a<second.a,wooPref=first.b<second.b;
    if(idpPref!==wooPref){
      const showFavorite=first.a<second.a?first:second;
      const wooFavorite=first.b<second.b?first:second;
      return `<p class="fa-ss-caveat"><strong>Split decision — no two-expert start consensus.</strong> IDP Show prefers ${escape(showFavorite.p.name)} (#${showFavorite.a} vs #${showFavorite===first?second.a:first.a}), while Woellert prefers ${escape(wooFavorite.p.name)} (#${wooFavorite.b} vs #${wooFavorite===first?second.b:first.b}). Check playing-time expectations and the separate LOG base-point estimates before choosing. Do not treat the slight average-rank edge as a certain start recommendation.</p>`;
    }
    const conflict=(first.gap>=Math.max(10,first.avg*.4));
    return `<p class="fa-ss-lean"><strong>Start lean: ${escape(first.p.name)}</strong> over ${escape(second.p.name)} among the two-source candidates in this ${escape(first.group)} group. Both experts place that player ahead. Average ranks ${fmtNum(first.avg)} vs ${fmtNum(second.avg)}.${conflict?' Experts disagree on the magnitude of his ranking; verify the role before locking a starter.':''} This is an ordinal comparison, not a probability or projected scoring margin.</p>`;
  }
  function compare(){
    if(!loaded||selected.length<2)return;
    const rows=selected.map(id=>dataOf(catalog.get(id)));
    const by=new Map();for(const x of rows){if(!by.has(x.group))by.set(x.group,[]);by.get(x.group).push(x);}
    const multi=by.size>1;
    let out=`<div class="fa-ss-result-head"><h3>Week ${capturedWeek} start/sit comparison</h3><p>${selected.length} players · equal-weight expert rankings · ${[...by.keys()].map(x=>groupNames[x]||x).join(' / ')}</p></div>`;
    if(multi)out+='<p class="fa-ss-caveat">You selected multiple positions. LB, EDGE, DT, safety and corner ranks use different pools: we will NOT declare one overall winner across positions. Compare players within each position group or inspect the optional LOG base-point projections separately.</p>';
    for(const [group,arr] of by){
      arr.sort((a,b)=>(a.n===2?0:a.n===1?1:2)-(b.n===2?0:b.n===1?1:2)||(a.avg??a.a??a.b??999)-(b.avg??b.a??b.b??999)||a.p.name.localeCompare(b.p.name));
      out+=`<section class="fa-ss-result-group"><h4>${escape(groupNames[group]||group)}</h4>`;
      out+=explain(arr);
      out+=arr.map(x=>{
        const r=x.r,proj=r?.projection;
        const difference=x.gap===null?'Not enough for a rank spread':x.gap>=Math.max(10,x.avg*.4)?'Experts disagree materially':x.gap<=5?'Strong agreement':'Some disagreement';
        const meta=x.n===2?'Two-source consensus':x.n===1?'One source visible':'No captured rank';
        const positionOf=r?.group||'—';
        return `<article class="fa-ss-result-card"><div class="fa-ss-result-top"><div><strong>${escape(x.p.name)}</strong><small>${escape(x.p.team||'—')} · ${escape(poolStatus(x.p))} · ${escape(positionOf)}</small></div><span class="fa-ss-quality">${escape(meta)}</span></div>
          <div class="fa-ss-ranks"><div><small>IDP Show W${capturedWeek}</small><strong>${x.a===null?'—':'#'+x.a}</strong></div><div><small>Woellert W${capturedWeek}</small><strong>${x.b===null?'—':'#'+x.b}</strong></div><div><small>Average rank</small><strong>${x.avg===null?'—':'#'+fmtNum(x.avg)}</strong></div></div>
          <p class="fa-ss-result-comment">${escape(difference)}${r?.idp_show_tier?' · IDP Show tier '+escape(r.idp_show_tier):''}.</p>
          ${proj?`<div class="fa-ss-proj">Woellert stat projection → <strong>${val(proj.log_linear_base_points)} LOG linear-base pts</strong> · ${val(proj.projected_defensive_snaps)} defensive snaps <small>(one expert’s separate projection; scoring bonuses excluded)</small></div>`:'<p class="fa-ss-proj fa-ss-subtle">No matched LOG linear-base projection in the selected private snapshot.</p>'}
          </article>`;
      }).join('');out+='</section>';
    }
    out+='<p class="fa-ss-fine">Consensus averages published position ranks exactly as captured; two-source coverage varies because some Woellert DL/DB screenshots were cropped. Missing does not mean unranked. Verify current injuries, active status, matchup, and league eligibility before setting your lineup.</p>';
    ui.results.innerHTML=out;
    ui.results.scrollIntoView({block:'start',behavior:window.matchMedia?.('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
  }
  async function loadCatalog(){
    try{
      const base='https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/main/';
      const files=['data/free_agents.json','data/league_rosters.json','data/my_roster.json','config.json'];
      const resp=await Promise.all(files.map(f=>fetch(base+f+'?t='+Date.now(),{cache:'no-store'})));
      fail(resp.every(r=>r.ok),'LOG source unavailable');
      const [fa,rs,mine,cfg]=await Promise.all(resp.map(r=>r.json()));
      fail(fa.league_id===rs.league_id&&fa.league_id===cfg.league_id,'League ID mismatch');
      fail(Array.isArray(fa.free_agents)&&fa.count===fa.free_agents.length,'Invalid free agent pool');
      fail(Array.isArray(rs.rosters)&&rs.rosters.length===12,'Invalid league roster pool');
      fail(mine.roster_id&&mine.roster_id<=rs.rosters.length,'Cannot identify my roster');
      const team=rs.rosters.find(x=>x.roster_id===mine.roster_id);
      fail(team&&team.owner_id===mine.owner_id,'My roster mismatch');
      const myIds=new Set(rosterMembers(mine).filter(isIdp).map(strId));
      for(const roster of rs.rosters){for(const p of rosterMembers(roster)){
        if(!isIdp(p))continue;const sid=strId(p);if(!/^\d+$/.test(sid))continue;
        const old=catalog.get(sid);if(old){fail(old.name===p.name,'Conflicting roster identity');continue;}
        catalog.set(sid,{player_id:sid,name:p.name,team:p.team||'',position:p.position||p.pos,raw_position:p.raw_position||'',source:'rostered',roster_id:roster.roster_id});
      }}
      for(const p of fa.free_agents){if(!isIdp(p))continue;const sid=strId(p);if(!/^\d+$/.test(sid))continue;
        fail(!catalog.has(sid),'Rostered/free-agent overlap '+sid);
        catalog.set(sid,{player_id:sid,name:p.name,team:p.team||'',position:p.pos||p.position,raw_position:p.raw_position||'',source:'available'});
      }
      userRoster=myIds;rosterSync=fa.synced_at;catalogReady=true;
      fail(catalog.size>=250,'Unexpectedly few IDPs in current league');
      noRosterError=null;
      ui.status.textContent=`${catalog.size} LOG IDPs matched. My roster and free agents available · synced ${synced()}. Choose your private Week 10 rankings file.`;
      showMatches();
    }catch(e){noRosterError=String(e.message||e);ui.status.textContent='Cannot reliably identify LOG players: '+noRosterError;ui.status.classList.add('fa-ss-error');ui.file.disabled=true;}
  }
  ui.file.addEventListener('change',async()=>{
    const file=ui.file.files?.[0];
    try{
      fail(catalogReady,'Roster/player source not ready');
      fail(file&&file.size>0&&file.size<=900000,'Private JSON file missing or too large');
      const doc=JSON.parse(await file.text()),candidate=validSnap(doc);
      const coverage=[...candidate.values()].filter(r=>r.rankings.idp_show!==null&&r.rankings.woellert!==null).length;
      ranks=candidate;rankNames=new Map();
      for(const row of ranks.values()){const k=key(row.name);if(!rankNames.has(k))rankNames.set(k,[]);rankNames.get(k).push(row);}
      capturedWeek=doc.week;sourceMeta=doc.source_coverage;loaded=true;
      ui.status.classList.remove('fa-ss-error');
      ui.status.textContent=`Private Week ${capturedWeek} consensus loaded: ${candidate.size} ranked names (${coverage} with both experts). Data remains in this browser tab; no upload.`;
      refresh();
    }catch(e){ui.status.textContent='Private ranking import rejected: '+String(e.message||e);ui.status.classList.add('fa-ss-error');}
    ui.file.value='';
  });
  ui.search.addEventListener('input',showMatches);
  ui.scope.addEventListener('change',showMatches);
  ui.group.addEventListener('change',showMatches);
  ui.clear.addEventListener('click',()=>{selected=[];refresh()});
  ui.compare.addEventListener('click',compare);
  loadCatalog();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',initializeStartSit,{once:true});
  else initializeStartSit();
})();
