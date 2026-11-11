/* LOG A-FA17R1 — Compact multi-evidence weekly lineup decision (public code only).
 * Sources: existing owner-local expert ranks/projections, owner-local SAME-WEEK matchup
 * tables, and public Sleeper observed defensive snaps. NO subscriber statistics bundled.
 * Pairwise votes are a transparent, UNCALIBRATED decision heuristic, NOT fantasy points.
 * This module does not edit the canonical Start/Sit source, player values or snapshots.
 */
(() => {
  'use strict';
  const DB_RANKS = 'LOG_Private_StartSit_Weekly_2026_v1';
  const DB_MATCH = 'LOG_Private_Woellert_Matchups_v1';
  const TEAM_CODES = new Set('ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LAR LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split(' '));
  const expectedMatchClass = 'PRIVATE_USER_PROVIDED_MATCHUP_REFERENCE_NOT_FOR_PUBLIC_GITHUB';
  const clamp = (v,min,max) => Math.max(min,Math.min(max,v));
  const norm = s => String(s||'').toLowerCase().replace(/\b(jr|sr|ii|iii|iv)\b/g,'').replace(/[^a-z0-9]/g,'');
  const esc = v => String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num = s => {const match = /^\s*#?\s*(\d+(?:\.\d+)?)/.exec(String(s??'')); return match?Number(match[1]):null;};
  const validNumber = v => typeof v==='number' && Number.isFinite(v);
  const roleSlot = r => r==='S'||r==='CB'?'DB':r==='DT'||r==='EDGE'?'DL':r;

  // Never create an owner-private database during a read. If absent, return [].
  async function readPrivate(dbName,storeName) {
    if(!window.indexedDB || !indexedDB.databases) return [];
    const names=await indexedDB.databases();
    if(!names.some(d=>d.name===dbName)) return [];
    const db=await new Promise((resolve,reject)=>{
      const req=indexedDB.open(dbName);
      req.onsuccess=()=>resolve(req.result);
      req.onerror=()=>reject(req.error||Error('Private storage unavailable'));
    });
    if(!db.objectStoreNames.contains(storeName)){db.close();return [];}
    try{
      return await new Promise((resolve,reject)=>{
        const tx=db.transaction(storeName,'readonly');
        const req=tx.objectStore(storeName).getAll();
        req.onsuccess=()=>resolve(req.result||[]);
        req.onerror=()=>reject(req.error||Error('Private evidence read failed'));
        tx.oncomplete=()=>db.close();
        tx.onerror=()=>{db.close();reject(tx.error||Error('Private evidence read failed'));};
      });
    } catch(e){db.close();throw e;}
  }

  function parseCards(results) {
    const list=[];
    for(const group of results.querySelectorAll('.fa-ss-result-group')) {
      const heading=(group.querySelector('h4')?.textContent||'').toLowerCase();
      const slot=heading.includes('lineback')?'LB':heading.includes('defensive back')?'DB':heading.includes('defensive line')?'DL':'UNKNOWN';
      for(const card of group.querySelectorAll('.fa-ss-result-card')) {
        const name=card.querySelector('.fa-ss-result-top strong')?.textContent?.trim();
        const meta=card.querySelector('.fa-ss-result-top small')?.textContent||'';
        const team=meta.split(' · ')[0]?.trim()?.toUpperCase();
        const role=meta.match(/\b(LB|EDGE|DT|CB|S)\s*→/)?.[1]||null;
        const ranks=[...card.querySelectorAll('.fa-ss-ranks > div strong')];
        const projNode=card.querySelector('.fa-ss-proj strong');
        if(!name || !TEAM_CODES.has(team) || !role || roleSlot(role)!==slot)continue;
        list.push({name,team,role,slot,a:num(ranks[0]?.textContent),b:num(ranks[1]?.textContent),
          pts:projNode?num(projNode.textContent):null, card});
      }
    }
    return list;
  }
  function buildRankSchedule(rankDoc) {
    const teamOpp=new Map(), nameOpp=new Map();
    for(const r of rankDoc?.records||[]) {
      const projection=r.projection;
      if(!projection||!TEAM_CODES.has(projection.team)||!TEAM_CODES.has(projection.opponent)||projection.team===projection.opponent)continue;
      const key=`${norm(r.name)}|${r.group}|${projection.team}`;
      nameOpp.set(key,projection.opponent);
      if(!teamOpp.has(projection.team))teamOpp.set(projection.team,new Set());
      teamOpp.get(projection.team).add(projection.opponent);
    }
    return {teamOpp,nameOpp};
  }
  function getOpponent(p,schedule) {
    // Manual opponent selected in the existing private matchup panel takes precedence.
    const header=p.card.querySelector('.fa-mu-evidence-head strong')?.textContent||'';
    const explicit=/\bmatchup:\s*[A-Z]{2,3}\s+vs\s+([A-Z]{2,3})\b/.exec(header);
    if(explicit && TEAM_CODES.has(explicit[1]))return explicit[1];
    const direct=schedule.nameOpp.get(`${norm(p.name)}|${p.role}|${p.team}`);
    if(direct)return direct;
    const fallback=schedule.teamOpp.get(p.team);
    return fallback?.size===1?[...fallback][0]:null;
  }
  function matchupSignal(p,match,schedule) {
    if(!match || match.season!==2026 || !match.teams || !match.league_averages)return null;
    const opp=getOpponent(p,schedule);
    if(!opp || !match.teams[opp])return null;
    const team=match.teams[opp],avg=match.league_averages;
    const role=p.role;
    const volume=(key)=>{
      const v=team.tackles_allowed_per_game?.[key],base=avg.tackles_allowed_per_game?.[key];
      return validNumber(v)&&validNumber(base)&&base>0?clamp(v/base-1,-0.5,0.5):null;
    };
    let relative=null,category=role,quality='observed opponent trend';
    if(role==='CB'){
      const out=volume('OUTSIDE_CB'),slot=volume('SLOT_CB');
      // No verified individual alignment: only allow a directional signal when
      // BOTH outside and slot conditions agree. Never assume outside snaps.
      if(out!==null && slot!==null && (out>0.03&&slot>0.03 || out< -0.03&&slot< -0.03)){
        relative=Math.sign(out)*Math.min(Math.abs(out),Math.abs(slot));
        quality='CB alignment unverified; conservative shared direction';
      } else {relative=0;quality='CB alignment unverified; matchup neutral';}
      category='outside/slot CB';
    }else if(role==='EDGE'||role==='DT'){
      const pressure=team.overall_pressure_rate_allowed_pct,base=avg.overall_pressure_rate_allowed_pct;
      const pressureDelta=validNumber(pressure)&&validNumber(base)&&base>0?clamp(pressure/base-1,-0.5,0.5):null;
      const tackleDelta=volume(role);
      // EDGE/DT: pressure opportunity is the primary, while tackle volume is
      // a corroborating check, not a multiplicative or points adjustment.
      relative=pressureDelta;
      if(pressureDelta!==null && tackleDelta!==null && Math.sign(pressureDelta)!==Math.sign(tackleDelta)){
        relative=pressureDelta*0.5;quality='pressure/tackle context disagree';
      }
      category=role+' pressure';
    }else relative=volume(role);
    if(relative===null)return null;
    return {relative,opp,category,quality,display:Math.round(relative*100),
      volumeRate:role==='CB'?null:volume(role)};
  }
  function usageSignal(p,weekly,rankingWeek) {
    if(!weekly||weekly.season!==2026||!Array.isArray(weekly.players))return null;
    const matches=weekly.players.filter(x=>norm(x.name)===norm(p.name)&&x.team===p.team);
    if(matches.length!==1)return null;
    const obs=matches[0].observations.filter(x=>Number.isInteger(x.week)&&x.week<rankingWeek&&
      rankingWeek-x.week<=4&&validNumber(x.defensive_snaps)&&x.games_played>0)
      .sort((a,b)=>a.week-b.week);
    if(!obs.length)return null;
    const last=obs[obs.length-1];
    if(rankingWeek-last.week>2)return null;
    const thresholds={LB:[50,25],S:[55,25],CB:[55,25],EDGE:[45,20],DT:[40,18]};
    const [strong,low]=thresholds[p.role];
    let signal=last.defensive_snaps>=strong ? 0.45 : last.defensive_snaps<low ? -0.55 : 0;
    const prev=obs.slice(0,-1).slice(-2);
    if(prev.length && obs.at(-2).week===last.week-1){
      const mean=prev.reduce((a,b)=>a+b.defensive_snaps,0)/prev.length;
      if(mean>=15){
        if(last.defensive_snaps>=mean*1.20)signal+=.3;
        else if(last.defensive_snaps<=mean*.8)signal-=.3;
      }
    }
    return {score:clamp(signal,-1,1),week:last.week,snaps:last.defensive_snaps,sample:obs.length};
  }
  function comparison(a,b) {
    let av=0,bv=0;const channels=[];
    if(validNumber(a.pts)&&validNumber(b.pts)){
      const diff=a.pts-b.pts;
      if(Math.abs(diff)>.05){const weight=Math.abs(diff)>=3?3:1;
        if(diff>0)av+=weight;else bv+=weight;
        channels.push('projection');}
    }
    if(a.role===b.role){
      for(const k of ['a','b']){
        if(validNumber(a[k])&&validNumber(b[k])&&a[k]!==b[k]){
          if(a[k]<b[k])av++;else bv++;
          channels.push('expert');
        }
      }
    }
    if(a.match && b.match && Math.abs(a.match.relative-b.match.relative)>=.12){
      if(a.match.relative>b.match.relative)av+=2;else bv+=2;
      channels.push('matchup');
    }
    if(a.usage && b.usage && Math.abs(a.usage.score-b.usage.score)>=.5){
      if(a.usage.score>b.usage.score)av++;else bv++;
      channels.push('usage');
    }
    if(av===bv)return {winner:null,margin:0,channels};
    return {winner:av>bv?a:b,margin:Math.abs(av-bv),channels};
  }
  function rankCandidates(rows) {
    if(rows.some(p=>p.slot!==rows[0].slot || p.slot==='UNKNOWN'))return {error:'Choose players for the same LOG slot (LB, DL, or DB).'};
    const tally=new Map(rows.map(p=>[p,{wins:0,margin:0,links:0}]));
    for(let i=0;i<rows.length;i++)for(let j=i+1;j<rows.length;j++){
      const p=rows[i],q=rows[j],v=comparison(p,q);
      const t=tally.get(p),u=tally.get(q);
      if(!v.channels.length)continue;
      t.links++;u.links++;
      if(v.winner===p){t.wins++;t.margin+=v.margin;u.margin-=v.margin;}
      if(v.winner===q){u.wins++;u.margin+=v.margin;t.margin-=v.margin;}
    }
    const order=[...rows].sort((a,b)=>tally.get(b).wins-tally.get(a).wins ||
      tally.get(b).margin-tally.get(a).margin ||
      (validNumber(b.pts)?b.pts:-1)-(validNumber(a.pts)?a.pts:-1) ||
      a.name.localeCompare(b.name));
    const unsupported=rows.filter(p=>!validNumber(p.pts)&&!validNumber(p.a)&&!validNumber(p.b)).length;
    return {order,tally,unsupported};
  }
  function boot() {
    const app=document.getElementById('faSsApp');
    const results=document.getElementById('faSsResults');
    const selected=document.getElementById('faSsSelected');
    const compare=document.getElementById('faSsCompare');
    if(!app||!results||!selected||!compare||document.getElementById('faDecisionV2'))return;
    const control=document.createElement('section');
    control.id='faDecisionV2';control.className='fa-decision-v2';
    control.innerHTML=`<div class="fa-dc-select"><label for="faDcCount">How many to start?</label><select id="faDcCount" aria-label="Choose number of players to start"></select><span id="faDcReady">Choose players</span></div><div id="faDcOutput" aria-live="polite"></div>`;
    compare.before(control);
    const output=control.querySelector('#faDcOutput');
    const nSelect=control.querySelector('#faDcCount');
    const ready=control.querySelector('#faDcReady');
    for(let n=1;n<=12;n++)nSelect.add(new Option(String(n),String(n),false,n===2));
    compare.textContent='Rank my START / SIT picks';
    const detail=document.createElement('details');detail.className='fa-dc-evidence';detail.id='faDcEvidence';
    const summary=document.createElement('summary');summary.textContent='Why these picks?';detail.append(summary);
    results.before(detail);detail.append(results);
    const allSteps=app.querySelector('.fa-ss-steps');if(allSteps)allSteps.hidden=true;
    const staticTitle=document.querySelector('#fa-ws-startsit-panel .fa-ws-intro h2');
    if(staticTitle)staticTitle.textContent='Start / Sit';
    // Collapse weekly imports and long status instructions until the owner needs them.
    // Move the REAL form nodes, not copies: saved browser data and event listeners survive.
    const importBox=app.querySelector('.fa-ss-import');
    if(importBox){
      const sources=document.createElement('details');sources.id='faDcSources';sources.className='fa-dc-sources';
      const sourceHeading=document.createElement('summary');sourceHeading.textContent='Weekly data / imports';
      sources.append(sourceHeading);importBox.before(sources);sources.append(importBox);
      const matchupApp=document.getElementById('faMatchupV1');if(matchupApp)sources.append(matchupApp);
    }
    let cachedResult=null,liveWeek=null,loading=false,rerenderTimer=null,publicPromise=null;
    async function loadUsage(){
      if(!publicPromise)publicPromise=fetch('data/idp_weekly_2026_public.json',{cache:'no-store'})
        .then(r=>r.ok?r.json():null).then(doc=>doc?.schema_version?doc:null).catch(()=>null);
      return publicPromise;
    }
    // Current NFL week is contextual. Failure leaves the source week visible, not "fresh".
    fetch('https://api.sleeper.app/v1/state/nfl',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(x=>{
      const w=Number(x?.week);if(Number.isInteger(w)&&w>=1&&w<=18){liveWeek=w;if(cachedResult)paint(cachedResult);}
    }).catch(()=>{});
    function selectionCount(){return selected.querySelectorAll('.fa-ss-chip').length;}
    function refreshCount(){
      const n=selectionCount(),current=Number(nSelect.value);
      for(const o of nSelect.options)o.disabled=n>0 && Number(o.value)>n;
      if(n>0&&current>n)nSelect.value=String(n);
      ready.textContent=n?`${n} selected`:'Choose 2–12 players';
    }
    function pill(p) {
      const match=p.match?(p.role==='CB' && p.match.quality.includes('unverified') && p.match.display===0
        ? `${p.match.opp} CB: alignment unknown`
        : `${p.match.opp} ${p.role}: ${p.match.display>0?'+':''}${p.match.display}% matchup`):'Matchup unavailable';
      const usage=p.usage?`W${p.usage.week} ${p.usage.snaps} snaps`:'Usage unavailable';
      return [match,usage];
    }
    function paint(result) {
      if(!result)return;
      const n=Math.min(Number(nSelect.value)||2,result.rows.length);
      const week=result.week;
      const stale=liveWeek!==null && week!==liveWeek;
      const weekLabel=liveWeek===null?`W${week} · current week unverified`:stale?`W${week} · STALE (NFL W${liveWeek})`:`W${week} rankings`;
      if(result.ranked.error){output.innerHTML=`<div class="fa-dc-head"><strong>Choose one lineup slot</strong><span class="fa-dc-week">${esc(weekLabel)}</span></div><p class="fa-dc-short-warning">${esc(result.ranked.error)}</p>`;return;}
      const {order,unsupported,tally}=result.ranked;
      function renderRows(rows,start){return rows.map((p,i)=>{
        const [match,usage]=pill(p);
        const coverage=[validNumber(p.pts),validNumber(p.a)||validNumber(p.b),!!p.match,!!p.usage].filter(Boolean).length;
        const shortNote=coverage<2?'Limited evidence':`Experts ${p.a!==null&&p.b!==null?'2/2':'partial'} · ${usage}`;
        return `<div class="fa-dc-player ${start?'fa-dc-start':'fa-dc-sit'}"><span class="fa-dc-index">${start?'#'+(i+1):'#'+(n+i+1)}</span><div class="fa-dc-name"><strong>${esc(p.name)}</strong><small>${esc(p.role)} · ${esc(match)}</small><small>${esc(shortNote)}</small></div><div class="fa-dc-pts">${p.pts!==null?`${p.pts.toFixed(1)}<small>base pts</small>`:'<small>No pts</small>'}</div></div>`;
      }).join('');}
      const withContext=order.filter(p=>!!p.match).length,withUsage=order.filter(p=>!!p.usage).length;
      const missing=[];
      if(withContext<order.length)missing.push('matchups');
      if(withUsage<order.length)missing.push('usage');
      if(unsupported)missing.push('player projections/ranks');
      output.innerHTML=`<div class="fa-dc-head"><strong>START ${n} OF ${order.length}</strong><span class="fa-dc-week ${stale?'fa-dc-stale':''}">${esc(weekLabel)}</span></div>
        <div class="fa-dc-list">${renderRows(order.slice(0,n),true)}</div>
        ${order.length>n?`<div class="fa-dc-sit-title">SIT</div><div class="fa-dc-list">${renderRows(order.slice(n),false)}</div>`:''}
        <div class="fa-dc-bottom">4 signals: experts · LOG points · matchup · snaps${missing.length?` <span class="fa-dc-missing">· Missing: ${esc(missing.join(', '))}</span>`:''}</div>`;
      const why=detail.querySelector('summary');
      why.textContent='Why these picks?';
      if(result.ranked.unsupported && result.ranked.unsupported===order.length){
        const note=document.createElement('p');note.className='fa-dc-short-warning';note.textContent='No comparable ranking/projection evidence for these players.';output.append(note);
      }
      // Historical matchup and observed-snap inputs are selection heuristics, not a
      // revised fantasy-point projection or calibrated win probability.
      output.dataset.logic='PAIRWISE_FOUR_SIGNAL_HEURISTIC_NOT_PROJECTED_POINTS';
    }
    async function recompute(){
      if(loading)return;
      const body=results.querySelector('.fa-ss-result-head h3')?.textContent||'';
      const m=/\bWeek\s+(\d{1,2})\b/i.exec(body);
      if(!m){cachedResult=null;output.textContent='';return;}
      const week=Number(m[1]);
      const rows=parseCards(results);
      if(rows.length<2){cachedResult=null;output.textContent='';return;}
      loading=true;
      try{
        const [weekly,rankDocs,matchDocs]=await Promise.all([
          loadUsage(),
          readPrivate(DB_RANKS,'snapshots').catch(()=>[]),
          readPrivate(DB_MATCH,'weekly').catch(()=>[])
        ]);
        const rankDoc=rankDocs.find(d=>d?.season===2026&&d.week===week&&Array.isArray(d.records));
        const match=matchDocs.find(d=>d?.schema_version===1&&d.classification===expectedMatchClass&&d.season===2026&&d.analysis_week===week&&d.private===true&&d.do_not_publish_to_github===true);
        const schedule=buildRankSchedule(rankDoc);
        for(const p of rows){
          p.match=matchupSignal(p,match,schedule);
          p.usage=usageSignal(p,weekly,week);
        }
        cachedResult={week,rows,ranked:rankCandidates(rows)};
        paint(cachedResult);
      }catch(e){output.textContent='Unable to compare complete evidence. Review the original rankings below.';console.warn('LOG four-signal ranking unavailable',e);
      }finally{loading=false;}
    }
    function scheduleCalc(){
      if(rerenderTimer!==null)clearTimeout(rerenderTimer);
      rerenderTimer=setTimeout(()=>{rerenderTimer=null;recompute();},120);
    }
    new MutationObserver(()=>{
      refreshCount();
      if(!results.querySelector('.fa-ss-result-head')){cachedResult=null;output.textContent='';}
    }).observe(selected,{childList:true});
    new MutationObserver(()=>scheduleCalc()).observe(results,{childList:true,subtree:true});
    nSelect.addEventListener('change',()=>{if(cachedResult)paint(cachedResult);});
    // Re-rank when matchup import or a manually selected opponent changes.
    const mu=document.getElementById('faMatchupV1');
    if(mu){mu.addEventListener('change',()=>setTimeout(scheduleCalc,180));
      new MutationObserver(()=>scheduleCalc()).observe(mu,{childList:true,subtree:true});}
    compare.addEventListener('click',()=>scheduleCalc());
    refreshCount();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
