/* LOG A-FA13R1 — LOG lineup-slot-aware IDP Start/Sit (presentation/scoring evidence only).
 * Public module contains NO subscriber rank data and NO private scouting data.
 * Private rankings are installed with a one-time local activation and restored from this device; no subscriber data is hosted.
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
  const groupNames = {LB:'Linebacker',EDGE:'EDGE',DT:'Interior DL',S:'Safety',CB:'Cornerback',DL:'Defensive line (DL)',DB:'Defensive back (DB)'};
  const groups = ['LB','EDGE','DT','S','CB'];
  // LOG permits S and CB in any DB slot; EDGE and DT in any DL slot.
  // Expert source ranks remain tied to their ORIGINAL subposition groups.
  const lineupSlot = group => group==='S'||group==='CB'?'DB':group==='EDGE'||group==='DT'?'DL':group;

  const maxPick=12;
  const trustedClassification='PRIVATE_OWNER_SUPPLIED_WEEKLY_IDP_START_SIT_NOT_FOR_PUBLIC_REPO';
  let catalog=new Map(), userRoster=new Set(), selected=[], ranks=new Map(),rankNames=new Map(), loaded=false, capturedWeek=null, sourceMeta=null;
  let rosterSync=null, catalogReady=false, noRosterError=null, privateRestoreDone=false;
  root.insertAdjacentHTML('beforeend', `
    <section id="faSsApp" class="fa-ss" aria-label="Week 10 start sit comparison">
      <div class="fa-ss-steps"><span>1 · Rankings load privately</span><span>2 · Choose 2–12 players</span><span>3 · Compare</span></div>
      <div class="fa-ss-import">
        <div class="fa-ss-import-info"><strong>Private expert consensus</strong><small>Activates once on this browser, then automatically loads on future visits. Rankings are stored locally on this device—not posted to GitHub.</small></div>
        <div id="faSsStatus" class="fa-ss-status" role="status">Loading LOG players and checking for your privately saved Week 10 rankings…</div>
        <details class="fa-ss-backup"><summary>Import / replace private ranking file</summary><label for="faSsFile">Optional JSON file fallback</label><input id="faSsFile" type="file" accept=".json,application/json"></details>
        <button type="button" id="faSsForget" class="fa-ss-forget" hidden>Forget rankings saved on this device</button>
      </div>
      <div class="fa-ss-searchtools">
        <label>Find a player<input id="faSsSearch" type="search" placeholder="Search your roster or free agents" autocomplete="off" aria-label="Search IDP player"></label>
        <label>Where to search<select id="faSsScope"><option value="mine">My roster</option><option value="available">Free agents</option><option value="all">Everyone</option></select></label>
        <label>Playable LOG slot<select id="faSsGroup"><option value="ALL">All IDP</option><option value="DB">DB — safety + corner</option><option value="DL">DL — EDGE + interior</option><option value="LB">LB</option><option value="S">S only</option><option value="CB">CB only</option><option value="EDGE">EDGE only</option><option value="DT">DT only</option></select></label>
      </div>
      <div id="faSsSuggestions" class="fa-ss-suggestions" aria-live="polite"></div>
      <div class="fa-ss-selected-heading"><h3>Players to compare <span id="faSsCount">0 / 12</span></h3><button type="button" id="faSsClear">Clear selection</button></div>
      <div id="faSsSelected" class="fa-ss-selected"><p class="fa-ss-empty">Choose any 2–12 players. Your roster and free agents are both supported.</p></div>
      <button type="button" id="faSsCompare" class="fa-ss-compare" disabled>Compare selected players</button>
      <div id="faSsResults" class="fa-ss-results" aria-live="polite"></div>
      <p class="fa-ss-fine">LOG lineup eligibility: S + CB can fill DB; EDGE + DT can fill DL. Expert ranks remain within each source's original subposition, so cross-subposition ordinal averages are not used. For cross-subposition decisions, Woellert's LOG linear-base point projections are a separate one-source estimate; threshold/event bonuses and current injury news require manual review. No dynasty value changes.</p>
    </section>`);
  const $=id=>root.querySelector('#'+id);
  const ui={file:$('faSsFile'),status:$('faSsStatus'),search:$('faSsSearch'),scope:$('faSsScope'),group:$('faSsGroup'),suggestions:$('faSsSuggestions'),selected:$('faSsSelected'),count:$('faSsCount'),compare:$('faSsCompare'),clear:$('faSsClear'),results:$('faSsResults'),forget:$('faSsForget')};
  const fail=(condition,message)=>{if(!condition)throw Error(message);};
  const val=(x,d=1)=>typeof x==='number'&&Number.isFinite(x)?x.toFixed(d):'—';
  const strId=x=>String(x?.player_id??'');
  const isIdp=p=>['LB','DL','DB'].includes(p?.pos||p?.position);
  const rosterMembers=t=>['starters','bench','taxi','reserve_ir'].flatMap(k=>Array.isArray(t[k])?t[k]:[]);
  function inferGroup(player){
    const raw=String(player.raw_position||player.position||'').toUpperCase();
    return groups.includes(raw)?raw:(raw==='DE'||raw==='OLB'?'EDGE':raw==='NT'?'DT':raw==='DB'?'DB':raw==='DL'?'DL':null);
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
  /* The public website has no paid rankings; only this user's browser holds them.
     The one-time launcher transfers the ranking payload in a URL FRAGMENT (never
     an HTTP request body or query), which is cleared from the URL immediately.
     The private cache uses IndexedDB on this browser/device; another device needs
     its own activation. All import methods use the exact same strict validator. */
  const DB_NAME='LOG_Private_StartSit_Weekly_2026_v1';
  const STORE='snapshots';
  const KEY='2026-W10-two-expert';
  function openDB(){return new Promise((resolve,reject)=>{
    if(!window.indexedDB){reject(Error('Browser private storage unavailable'));return;}
    const req=indexedDB.open(DB_NAME,1);
    req.onupgradeneeded=()=>{if(!req.result.objectStoreNames.contains(STORE))req.result.createObjectStore(STORE);};
    req.onerror=()=>reject(req.error||Error('Could not open private store'));
    req.onsuccess=()=>resolve(req.result);
  });}
  async function privateGet(){const db=await openDB();return new Promise((resolve,reject)=>{
    const t=db.transaction(STORE,'readonly'),req=t.objectStore(STORE).get(KEY);
    req.onsuccess=()=>resolve(req.result??null);
    req.onerror=()=>reject(req.error||Error('Cannot read private store'));
    t.oncomplete=()=>db.close();
  });}
  async function privatePut(data){const db=await openDB();return new Promise((resolve,reject)=>{
    const t=db.transaction(STORE,'readwrite'); t.objectStore(STORE).put(data,KEY);
    t.oncomplete=()=>{db.close();resolve();};
    t.onerror=()=>{db.close();reject(t.error||Error('Cannot save private ranks'));};
  });}
  async function privateDelete(){const db=await openDB();return new Promise((resolve,reject)=>{
    const t=db.transaction(STORE,'readwrite');t.objectStore(STORE).delete(KEY);
    t.oncomplete=()=>{db.close();resolve();};
    t.onerror=()=>{db.close();reject(t.error||Error('Cannot erase private ranks'));};
  });}
  function acceptRanks(doc,from){
    const candidate=validSnap(doc),coverage=[...candidate.values()].filter(r=>r.rankings.idp_show!==null&&r.rankings.woellert!==null).length;
    ranks=candidate;rankNames=new Map();
    for(const row of ranks.values()){const k=key(row.name);if(!rankNames.has(k))rankNames.set(k,[]);rankNames.get(k).push(row);}
    capturedWeek=doc.week;sourceMeta=doc.source_coverage;loaded=true;
    ui.status.classList.remove('fa-ss-error');
    ui.status.textContent=`Week ${capturedWeek} private consensus ${from}: ${candidate.size} ranked players (${coverage} with both experts). Compare 2–12 players below. Data is not hosted in GitHub.`;
    ui.forget.hidden=false;
    refresh();
  }
  async function decodeActivation(encoded){
    fail(/^[A-Za-z0-9_-]{100,40000}$/.test(encoded),'Invalid private activation payload');
    fail(typeof DecompressionStream==='function','Your browser cannot decode private activation. Use file import fallback.');
    const padded=encoded.replace(/-/g,'+').replace(/_/g,'/');
    const binary=atob(padded+'='.repeat((4-padded.length%4)%4));
    const bytes=Uint8Array.from(binary,c=>c.charCodeAt(0));
    const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate'));
    const data=await new Response(stream).text();
    fail(data.length>100&&data.length<900000,'Invalid decoded ranking data size');
    return JSON.parse(data);
  }
  async function restorePrivate(){
    const marker='#fa-ss-install=';
    if(location.hash.startsWith(marker)){
      const encoded=location.hash.slice(marker.length);
      try{
        const doc=await decodeActivation(encoded);
        validSnap(doc);
        acceptRanks(doc,'activated');
        try{await privatePut(doc);ui.status.textContent+=' Saved on this device for automatic reuse.';}
        catch(err){ui.status.textContent+=' Browser denied local storage: activation is valid for this tab only. You may need to allow site storage.';}
      }catch(err){ui.status.classList.add('fa-ss-error');ui.status.textContent='Private activation failed: '+String(err.message||err);}
      try{history.replaceState(null,'',location.pathname+location.search+'#fa-ws-startsit');}catch(_){location.hash='#fa-ws-startsit';}
      window.dispatchEvent(new Event('hashchange'));
      privateRestoreDone=true;
      return;
    }
    try{
      const saved=await privateGet();
      if(saved){acceptRanks(saved,'restored automatically');privateRestoreDone=true;return;}
    }catch(err){console.info('LOG Start/Sit: private browser storage is unavailable; file fallback remains available.');}
    privateRestoreDone=true;
    ui.status.textContent=`Activate your private Week 10 consensus once using the personal activation page; it will load automatically on subsequent visits on this device. You can also use the optional JSON fallback.`;
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
      const playerSubposition=playerGroup(p);
      if(filter!=='ALL'&&playerSubposition!==filter&&lineupSlot(playerSubposition)!==filter)return false;
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
      const label=r?`${lineupSlot(r.group)} slot · ${r.group} ranks · ${r.rankings.idp_show===null?'IDP Show —':'IDP Show #'+r.rankings.idp_show} · ${r.rankings.woellert===null?'Woellert —':'Woellert #'+r.rankings.woellert}`:'No Week 10 rank in supplied screenshots';
      return `<div class="fa-ss-chip"><span><strong>${escape(p.name)}</strong><small>${escape(poolStatus(p))} · ${escape(label)}</small></span><button type="button" data-remove-id="${escape(id)}" aria-label="Remove ${escape(p.name)}">Remove</button></div>`;
    }).join(''):'<p class="fa-ss-empty">Choose any 2–12 players. Your roster and free agents are both supported.</p>';
    ui.selected.querySelectorAll('[data-remove-id]').forEach(b=>b.addEventListener('click',()=>remove(b.dataset.removeId)));
    ui.compare.disabled=!loaded||selected.length<2;
    ui.results.textContent='';showMatches();
  }
  function dataOf(p){
    const r=getRank(p),a=r?.rankings.idp_show??null,b=r?.rankings.woellert??null;
    const group=r?.group||playerGroup(p)||'UNKNOWN';
    return {p,r,a,b,n:(a===null?0:1)+(b===null?0:1),avg:a===null||b===null?null:(a+b)/2,gap:a===null||b===null?null:Math.abs(a-b),group,slot:lineupSlot(group)};
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
  function slotForecastSummary(arr,slot) {
    const subgroups=[...new Set(arr.map(x=>x.group))];
    if(subgroups.length===1)return explain([...arr]);
    const projected=arr.filter(x=>Number.isFinite(x.r?.projection?.log_linear_base_points))
      .sort((a,b)=>b.r.projection.log_linear_base_points-a.r.projection.log_linear_base_points);
    let message=`<p class="fa-ss-caveat"><strong>All these players are eligible for the same LOG ${escape(slot)} slot.</strong> `+
      `However, the saved expert ranks are ${slot==='DB'?'S vs CB':'EDGE vs DT'} positional lists. ${slot==='DB'?'A rank #3 safety is NOT automatically better than a rank #5 corner.':'A rank #3 EDGE is NOT automatically better than a rank #5 defensive tackle.'} `+
      `We do not average incompatible ranks to manufacture a two-expert cross-position consensus.</p>`;
    if(projected.length>=2){
      const best=projected[0],next=projected[1];
      const spread=best.r.projection.log_linear_base_points-next.r.projection.log_linear_base_points;
      message+=`<p class="fa-ss-caveat"><strong>Projected LOG base points (${escape(slot)}-eligible):</strong> `+
        projected.map(x=>escape(x.p.name)+' '+val(x.r.projection.log_linear_base_points)+' pts').join(' · ')+`.</p>`;
      message+=`<p class="fa-ss-caveat"><strong>Projection-only lean: ${escape(best.p.name)}</strong> `+
        `(${val(best.r.projection.log_linear_base_points)} vs ${val(next.r.projection.log_linear_base_points)}; +${val(spread)} pts). `+
        `This is based ONLY on Woellert's projected statistics converted to LOG linear scoring. It excludes bonus/rare events and is NOT a two-expert consensus or a guaranteed starter.</p>`;
    }else if(projected.length===1){
      message+='<p class="fa-ss-caveat">Only one selected player has a comparable LOG linear-base forecast. No cross-subposition projected start lean.</p>';
    }else{
      message+='<p class="fa-ss-caveat">No cross-subposition LOG base-point forecasts for these selections. Cannot recommend a slot starter from these incomplete rankings.</p>';
    }
    for(const sub of subgroups){
      const subset=arr.filter(x=>x.group===sub);
      if(subset.length>=2){
        message+=`<div class="fa-ss-subposition-context"><p class="fa-ss-fine"><strong>Within ${escape(groupNames[sub]||sub)} rankings:</strong></p>${explain([...subset])}</div>`;
        const complete=subset.filter(x=>x.n===2).sort((a,b)=>a.avg-b.avg);
        const expertLeader=complete[0];
        const projectedFromSub=projected.filter(x=>x.group===sub);
        if(expertLeader&&projectedFromSub.length>=2&&projectedFromSub[0]!==expertLeader){
          const other=projectedFromSub[0];
          if(expertLeader.a<other.a&&expertLeader.b<other.b){
            message+=`<p class="fa-ss-caveat"><strong>Conflicting start signals:</strong> Both weekly ${escape(groupNames[sub]||sub)} rankings prefer ${escape(expertLeader.p.name)} over ${escape(other.p.name)}, but the separate LOG-scored projection prefers ${escape(other.p.name)}. This is not a clean consensus pick.</p>`;
          }
        }
      }
    }
    return message;
  }
  function compare(){
    if(!loaded||selected.length<2)return;
    const rows=selected.map(id=>dataOf(catalog.get(id)));
    // Group by legal LOG lineup slot, not expert source subgroup.
    const by=new Map();for(const x of rows){if(!by.has(x.slot))by.set(x.slot,[]);by.get(x.slot).push(x);}
    const multi=by.size>1;
    let out=`<div class="fa-ss-result-head"><h3>Week ${capturedWeek} start/sit comparison</h3><p>${selected.length} players · LOG lineup slots · ${[...by.keys()].map(x=>groupNames[x]||x).join(' / ')}</p></div>`;
    if(multi)out+='<p class="fa-ss-caveat">You selected different LOG lineup slots. We compare DB with DB, DL with DL, and LB with LB. We do not declare an overall winner across separate slots.</p>';
    for(const [slot,arr] of by){
      const mixedSubposition=new Set(arr.map(x=>x.group)).size>1;
      arr.sort((a,b)=>mixedSubposition?
        (Number.isFinite(b.r?.projection?.log_linear_base_points)?b.r.projection.log_linear_base_points:-1)-
        (Number.isFinite(a.r?.projection?.log_linear_base_points)?a.r.projection.log_linear_base_points:-1)||a.p.name.localeCompare(b.p.name):
        (a.n===2?0:a.n===1?1:2)-(b.n===2?0:b.n===1?1:2)||
        (a.avg??a.a??a.b??999)-(b.avg??b.a??b.b??999)||a.p.name.localeCompare(b.p.name));
      out+=`<section class="fa-ss-result-group"><h4>${escape(groupNames[slot]||slot)}</h4>`;
      out+=slotForecastSummary(arr,slot);
      out+=arr.map(x=>{
        const r=x.r,proj=r?.projection;
        const difference=x.gap===null?'Not enough for a rank spread':x.gap>=Math.max(10,x.avg*.4)?'Experts disagree materially':x.gap<=5?'Strong agreement':'Some disagreement';
        const meta=x.n===2?'Two-source '+x.group+' ranking':x.n===1?'One '+x.group+' rank':'No captured rank';
        const positionOf=r?.group||'—';
        return `<article class="fa-ss-result-card"><div class="fa-ss-result-top"><div><strong>${escape(x.p.name)}</strong><small>${escape(x.p.team||'—')} · ${escape(poolStatus(x.p))} · ${escape(positionOf)} → ${escape(slot)} eligible</small></div><span class="fa-ss-quality">${escape(meta)}</span></div>
          <div class="fa-ss-ranks"><div><small>IDP Show ${escape(positionOf)} W${capturedWeek}</small><strong>${x.a===null?'—':'#'+x.a}</strong></div><div><small>Woellert ${escape(positionOf)} W${capturedWeek}</small><strong>${x.b===null?'—':'#'+x.b}</strong></div><div><small>${escape(positionOf)} avg rank</small><strong>${x.avg===null?'—':'#'+fmtNum(x.avg)}</strong></div></div>
          <p class="fa-ss-result-comment">${escape(difference)}${r?.idp_show_tier?' · IDP Show tier '+escape(r.idp_show_tier):''}. These numbers rank ${escape(positionOf)} players, not all ${escape(slot)}-eligible players.</p>
          ${proj?`<div class="fa-ss-proj">Woellert stat projection → <strong>${val(proj.log_linear_base_points)} LOG linear-base pts</strong> · ${val(proj.projected_defensive_snaps)} defensive snaps <small>(one expert’s separate projection; scoring bonuses excluded)</small></div>`:'<p class="fa-ss-proj fa-ss-subtle">No matched LOG linear-base projection in the selected private snapshot.</p>'}
          </article>`;
      }).join('');out+='</section>';
    }
    out+='<p class="fa-ss-fine">LOG slots: S+CB = DB; EDGE+DT = DL; LB = LB. Expert S and CB ranks (or EDGE and DT ranks) retain their source-specific meaning. Two-source ordinal consensus is only valid WITHIN the same original expert subgroup. If different subgroups compete for one slot, the cross-group base-point comparison is one expert’s incomplete projection—not a validated consensus. Verify current role, injuries, active status and lineup rules before starting.</p>';
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
      if(!loaded && !privateRestoreDone)ui.status.textContent=`${catalog.size} LOG IDPs matched. My roster and free agents available · synced ${synced()}. Checking saved private rankings…`;
      showMatches();
    }catch(e){noRosterError=String(e.message||e);ui.status.textContent='Cannot reliably identify LOG players: '+noRosterError;ui.status.classList.add('fa-ss-error');ui.file.disabled=true;}
  }
  ui.file.addEventListener('change',async()=>{
    const file=ui.file.files?.[0];
    try{
      fail(catalogReady,'Roster/player source not ready');
      fail(file&&file.size>0&&file.size<=900000,'Private JSON file missing or too large');
      const doc=JSON.parse(await file.text());
      acceptRanks(doc,'imported locally');
      try{await privatePut(doc);ui.status.textContent+=' Saved on this device for automatic reuse.';}
      catch(err){ui.status.textContent+=' Browser denied local storage: rankings remain available until this tab is closed.';}
    }catch(e){ui.status.textContent='Private ranking import rejected: '+String(e.message||e);ui.status.classList.add('fa-ss-error');}
    ui.file.value='';
  });
  ui.search.addEventListener('input',showMatches);
  ui.scope.addEventListener('change',showMatches);
  ui.group.addEventListener('change',showMatches);
  ui.clear.addEventListener('click',()=>{selected=[];refresh()});
  ui.compare.addEventListener('click',compare);
  ui.forget.addEventListener('click',async()=>{
    if(!window.confirm('Remove privately cached Week 10 rankings from this browser?'))return;
    try{await privateDelete();ranks.clear();rankNames.clear();capturedWeek=null;sourceMeta=null;loaded=false;
      ui.forget.hidden=true;ui.status.classList.remove('fa-ss-error');
      ui.status.textContent='Private rankings erased from this browser. Use your private activation page to reinstall.';
      refresh();}
    catch(err){ui.status.textContent='Could not erase saved private rankings: '+String(err.message||err);ui.status.classList.add('fa-ss-error');}
  });
  loadCatalog();
  restorePrivate();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',initializeStartSit,{once:true});
  else initializeStartSit();
})();
