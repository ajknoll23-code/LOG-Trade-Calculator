/* LOG FA26R1 — browser-local prospective IDP waiver validation.
 * Captures *all* FA25 free-agent candidates and evidence in a private IndexedDB store.
 * No uploads; reads only public Sleeper weekly observations to evaluate raw snaps.
 * Fantasy-point outcomes require an owner-supplied same-week LOG-scoring CSV.
 * No change to canonical FV/MV, league player values, projections, or recommenders.
 * Source capture is an owner-clock, one-time local snapshot, not an externally
 * attested timestamp; previously started games cannot be judged prospectively.
 */
(() => {
 'use strict';
 const $ = id => document.getElementById(id);
 const DB='LOG_Private_FA26_ProspectiveValidation_v1', STORE='snapshots';
 const GROUPS=['DL','LB','DB'];
 const safe=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
 const fmt=(v,d=1)=>typeof v==='number'&&Number.isFinite(v)?v.toFixed(d):'—';
 const validInt=(n,min,max)=>Number.isInteger(n)&&n>=min&&n<=max;
 const isNum=x=>typeof x==='number'&&Number.isFinite(x);
 const dbOpen=()=>new Promise((resolve,reject)=>{
   if(!window.indexedDB){reject(Error('Private browser storage unavailable'));return;}
   const req=indexedDB.open(DB,1);
   req.onupgradeneeded=()=>{const db=req.result;if(!db.objectStoreNames.contains(STORE))db.createObjectStore(STORE,{keyPath:'key'});};
   req.onsuccess=()=>resolve(req.result);
   req.onerror=()=>reject(req.error||Error('Cannot open private snapshot store'));
 });
 async function dbRead(key){const db=await dbOpen();return new Promise((resolve,reject)=>{
   const tx=db.transaction(STORE,'readonly'),req=tx.objectStore(STORE).get(key);
   req.onsuccess=()=>resolve(req.result||null);req.onerror=()=>reject(req.error);
   tx.oncomplete=()=>db.close();tx.onerror=()=>{db.close();reject(tx.error||Error('Snapshot read failed'));};
 });}
 async function dbAdd(doc){const db=await dbOpen();return new Promise((resolve,reject)=>{
   const tx=db.transaction(STORE,'readwrite'),req=tx.objectStore(STORE).add(doc);
   req.onerror=()=>reject(req.error||Error('Snapshot already exists'));
   tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>{db.close();reject(tx.error||Error('Cannot freeze snapshot'));};
 });}
 const snapshotKey=week=>`2026-W${week}`;
 const sha256=async value=>{
   if(!crypto?.subtle)throw Error('Secure SHA-256 unavailable in this browser');
   const data=new TextEncoder().encode(JSON.stringify(value));
   const bytes=new Uint8Array(await crypto.subtle.digest('SHA-256',data));
   return [...bytes].map(x=>x.toString(16).padStart(2,'0')).join('');
 };
 function csvParse(text){
   const rows=[];let row=[],value='',quoted=false;
   for(let i=0;i<text.length;i++){
     const c=text[i];
     if(c==='"'){if(quoted&&text[i+1]==='"'){value+='"';i++;}else quoted=!quoted;}
     else if(c===','&&!quoted){row.push(value);value='';}
     else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(value);value='';if(row.some(x=>x.trim()))rows.push(row);row=[];}
     else value+=c;
   }
   if(quoted)throw Error('Unterminated quoted field in actual-points CSV');
   row.push(value);if(row.some(x=>x.trim()))rows.push(row);
   return rows;
 }
 function parseActualPoints(text,week){
   const table=csvParse(text.replace(/^\uFEFF/,''));
   if(table.length<2||table.length>5000)throw Error('Actual-points CSV must contain 1–4999 player rows');
   const headers=table.shift().map(x=>String(x).toLowerCase().replace(/[^a-z0-9]/g,''));
   const col=(...names)=>headers.findIndex(x=>names.includes(x));
   const ix={pid:col('playerid','sleeperid'),week:col('week'),season:col('season'),pts:col('actualpoints','actualfantasypoints')};
   if(Object.values(ix).some(x=>x<0))throw Error('CSV needs player_id, season, week, actual_points; no guessed scoring');
   const result=new Map();
   for(const line of table){
     const sid=String(line[ix.pid]||'').trim(),y=Number(line[ix.season]),w=Number(line[ix.week]);
     const raw=String(line[ix.pts]||'').trim(),p=raw===''?null:Number(raw);
     if(!/^\d+$/.test(sid)||y!==2026||w!==week||p===null||!isNum(p)||p< -50||p>250)
       throw Error('Invalid player ID, missing score, season/week mismatch, or nonnumeric points');
     if(result.has(sid))throw Error('Duplicate player_id in actual-points CSV');
     result.set(sid,p);
   }
   return result;
 }
 function validFrozen(snap){
   const p=snap?.payload;
   return snap?.key===snapshotKey(p?.week)&&p?.schema_version===1&&p?.season===2026&&
    validInt(p.week,10,18)&&typeof snap.sha256==='string'&&/^[0-9a-f]{64}$/.test(snap.sha256)&&
    Array.isArray(p.candidates)&&p.candidates.length>=1&&p.candidates.length<=6000&&
    p.candidates.every(c=>/^[0-9]+$/.test(String(c.id))&&GROUPS.includes(c.group)&&typeof c.name==='string');
 }
 function rowsFor(snap,group){
   return snap.payload.candidates.filter(r=>r.group===group &&
     !['hold','thin'].includes(r.weekly_category) &&
     !/^(IR|OUT|PUP|SUSPENDED)\b/i.test(String(r.injury||'')) && r.team!=='FA');
 }
 function fa25Ordering(a,b){
   return a.weekly_order-b.weekly_order || b.weekly_top-a.weekly_top ||
     (b.four_points??-1)-(a.four_points??-1) ||
     (a.utility_rank??999999)-(b.utility_rank??999999) || a.name.localeCompare(b.name);
 }
 function getCohorts(snap,group){
   const candidates=rowsFor(snap,group);
   const original=candidates.slice().sort(fa25Ordering);
   const baseline=snap.payload.scoring==='log'?candidates.filter(x=>isNum(x.four_points)&&validInt(x.four_group_rank,1,2000))
    .sort((a,b)=>a.four_group_rank-b.four_group_rank||b.four_points-a.four_points||a.name.localeCompare(b.name)):[];
   const size=Math.min(10,original.length,baseline.length);
   return {fa25:original.slice(0,size),baseline:baseline.slice(0,size),size};
 }
 function summary(group,snap,points,observed){
   const samples=getCohorts(snap,group);const analyze=players=>{
     const scoreList=players.map(p=>points.get(p.id)).filter(isNum);
     const snaps=players.map(p=>observed.get(p.id)).filter(isNum);
     const changes=players.map(p=>{
       const actual=observed.get(p.id);
       return isNum(actual)&&p.prev_week===snap.payload.week-1&&isNum(p.prev_snaps)?actual-p.prev_snaps:null;
     }).filter(isNum);
     const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:null;
     return {n:players.length,pointsN:scoreList.length,pointsAvg:avg(scoreList),snapsN:snaps.length,snapsAvg:avg(snaps),
       snaps40:snaps.length?snaps.filter(v=>v>=40).length/snaps.length:null,
       changeN:changes.length,changeAvg:avg(changes)};
   };
   const a=analyze(samples.fa25),b=analyze(samples.baseline);
   const completePoints=samples.size>=5&&a.pointsN>=Math.ceil(samples.size*.8)&&b.pointsN>=Math.ceil(samples.size*.8);
   const completeSnaps=samples.size>=5&&a.snapsN>=Math.ceil(samples.size*.8)&&b.snapsN>=Math.ceil(samples.size*.8);
   return {group,n:samples.size,fa25:a,baseline:b,comparePoints:completePoints,compareSnaps:completeSnaps};
 }
 function createPanel(){
   const target=$('fa-ws-idp-panel');if(!target||$('fa26Lab'))return null;
   const host=document.createElement('section');host.id='fa26Lab';host.className='fa26';
   host.setAttribute('aria-label','FA26 private prospective validation');
   host.innerHTML=`<header class="fa26-head"><div><div class="fa26-kicker">FA26 · PROSPECTIVE RESEARCH VALIDATION</div><h3>Did our waiver targets work?</h3>
     <p>Freeze the FA25 candidate universe before games, then compare the identical players with actual defensive snaps and optional league-scored fantasy points. Never use hindsight to rebuild the old candidate list.</p></div><span class="fa26-private">LOCAL DEVICE ONLY</span></header>
     <div class="fa26-note">A local snapshot is <strong>one-time per week</strong> and SHA-256 checksummed, but your device clock is <strong>not independently attested</strong>. If any games already started, this is a partial/exploratory capture, not a clean full-week prospective test. No historical backtest exists without earlier frozen snapshots.</div>
     <div class="fa26-actions"><label class="fa26-confirm"><input id="fa26Confirm" type="checkbox"> I understand this snapshot must be taken before each included player's kickoff to count as prospective.</label>
     <button type="button" id="fa26Capture" class="fa26-primary">Freeze current FA25 week</button><button type="button" id="fa26Load">Load frozen week</button><button type="button" id="fa26Export">Export private snapshot</button></div>
     <p id="fa26Status" role="status" aria-live="polite">Select an analysis week in FA25, refresh its evidence, then freeze a prospective snapshot.</p>
     <div class="fa26-data"><div class="fa26-data-head"><strong>Postgame evaluation</strong><small>Exact-week public Sleeper defensive snaps; never infer 0 from missing stats</small></div>
       <div class="fa26-actions"><button type="button" id="fa26Evaluate" class="fa26-primary">Check public snap outcomes</button></div>
       <label>Optional LOG league-scored actual points CSV <input type="file" id="fa26Points" accept=".csv,text/csv"></label>
       <p class="fa26-hint">Required columns: <code>player_id,season,week,actual_points</code>. Include an explicit zero for verified zero-point results; missing rows remain unknown. Keep this CSV in your browser.</p>
       <label class="fa26-confirm"><input type="checkbox" id="fa26ScoringConfirm"> I confirm these actual scores use the same LOG scoring as the frozen 4for4 file.</label>
     </div><p id="fa26OutStatus" role="status" aria-live="polite">No postgame observations loaded.</p>
     <div id="fa26Report" class="fa26-report"></div>
     <p class="fa26-foot">Comparisons use up to ten IDPs per position and the same frozen, injury-eligible player pool for both approaches. Comparisons are withheld below 80% observed coverage or fewer than five candidates. Dynasty results require several future weeks, not one matchup. No changes to FV, MV, FA25 categories, or lineup decisions.</p>`;
   const anchor=$('fa24Lab');if(anchor)anchor.insertAdjacentElement('afterend',host);else target.prepend(host);
   return host;
 }
 function init(){
   if(!createPanel())return;
   const status=$('fa26Status'),outStatus=$('fa26OutStatus'),report=$('fa26Report');
   let frozen=null,points=new Map(),snapOut=new Map(),weekOut=null;
   const selectedWeek=()=>Number($('fa24Week')?.value);
   const say=(msg,isError=false)=>{status.textContent=msg;status.classList.toggle('fa26-error',isError);};
   function resetEval(){points=new Map();snapOut=new Map();weekOut=null;report.replaceChildren();outStatus.textContent='No postgame observations loaded.';$('fa26Points').value='';$('fa26ScoringConfirm').checked=false;}
   async function load(){
     const w=selectedWeek();if(!validInt(w,10,18)){say('Choose a supported 2026 week, 10–18, in FA25.',true);return;}
     frozen=null;resetEval();
     try{const data=await dbRead(snapshotKey(w));if(!data){say(`No frozen Week ${w} snapshot on this device. Refresh FA25 and freeze before kickoff.`);return;}
       if(!validFrozen(data)||await sha256(data.payload)!==data.sha256)throw Error('Frozen snapshot failed integrity validation');
       frozen=data;say(`Frozen W${w} · ${data.payload.candidates.length} IDPs · captured ${data.captured_at} (device clock) · SHA ${data.sha256.slice(0,16)}… · source scoring ${data.payload.scoring||'not loaded'}.`);
     }catch(e){say('Cannot load snapshot: '+String(e.message||e),true);}
   }
   async function freeze(){
     if(!$('fa26Confirm').checked){say('Confirm that captures must precede each included player kickoff.',true);return;}
     const read=window.LOG_FA26_READ;
     if(typeof read!=='function'){say('FA25 read-only evidence bridge missing; refresh this page.',true);return;}
     const payload=read();if(!payload){say('FA25 evidence is stale or not loaded. Refresh FA25 sources first.',true);return;}
     const w=selectedWeek();
     if(payload.season!==2026||payload.week!==w||!validInt(w,10,18)||
       !Array.isArray(payload.candidates)||payload.candidates.length<1){say('Invalid FA25 week or no candidate universe.',true);return;}
     if(!isNum(payload.free_agent_sync_unix)||(Date.now()/1000-payload.free_agent_sync_unix)>72*3600){say('Sleeper free-agent snapshot is over 72 hours old; refresh league data before freeze.',true);return;}
     if(!validInt(payload.observed_last_completed_week,5,18)||payload.observed_last_completed_week>=w){say('Public weekly outcome data are missing or already include this week; cannot label a pregame freeze.',true);return;}
     try{
       if(await dbRead(snapshotKey(w))){say(`Week ${w} is already frozen on this device. Overwriting is not allowed; load and export the existing snapshot.`,true);return;}
       const record={key:snapshotKey(w),captured_at:new Date().toISOString(),payload,sha256:await sha256(payload)};
       await dbAdd(record);frozen=record;resetEval();
       say(`Week ${w} locally frozen once · ${payload.candidates.length} IDPs · SHA ${record.sha256.slice(0,16)}… . Export a private copy for backup. Confirm kickoff timing independently.`);
     }catch(e){say('Freeze unavailable: '+String(e.message||e),true);}
   }
   function showReport(){
     if(!frozen)return;
     const w=frozen.payload.week,scope=$('fa26ScoringConfirm').checked;
     const actual=weekOut===w?snapOut:new Map();
     const scores=scope?points:new Map();
     const groups=GROUPS.map(g=>summary(g,frozen,scores,actual));
     const lines=groups.map(item=>{
       const pair=(a,b,n,ok,suffix='')=>!ok?`<span class="fa26-missing">Not comparable (coverage below 80%, n&lt;5, or baseline unavailable)</span>`:
         `${fmt(a,1)} vs ${fmt(b,1)}${suffix}`;
       const n=item.n,fa=item.fa25,base=item.baseline;
       const score=pair(fa.pointsAvg,base.pointsAvg,n,item.comparePoints,' points');
       const snap=pair(fa.snapsAvg,base.snapsAvg,n,item.compareSnaps,' snaps');
       const scoreN=`${fa.pointsN}/${n} vs ${base.pointsN}/${n}`;
       const snapN=`${fa.snapsN}/${n} vs ${base.snapsN}/${n}`;
       return `<tr><th scope="row">${item.group}</th><td>${n}</td><td>${score}<small>${scoreN} reported</small></td><td>${snap}<small>${snapN} reported</small></td></tr>`;
     }).join('');
     const snapshot=frozen.payload.candidates;
     const catNames=[['starter','Weekly starter'],['streamer','Streamer'],['rise','Rising opportunity'],['single','One signal'],['risk','Projection/role risk']];
     const sampleRows=catNames.map(([code,label])=>{
       const list=snapshot.filter(x=>x.weekly_category===code),observed=list.map(x=>actual.get(x.id)).filter(isNum);
       const pts=list.map(x=>scores.get(x.id)).filter(isNum);
       const n=observed.length;return `<tr><th scope="row">${safe(label)}</th><td>${list.length}</td><td>${n}/${list.length} observed</td><td>${n?fmt(observed.filter(x=>x>=40).length/n*100,0)+'%':'—'}</td><td>${pts.length?fmt(pts.reduce((s,x)=>s+x,0)/pts.length)+' ('+pts.length+' scored)':'—'}</td></tr>`;
     }).join('');
     report.innerHTML=`<div class="fa26-report-head"><strong>Frozen Week ${w} evaluation</strong><span>FA25 vs 4for4 · <em>equal-size groups</em></span></div>
       <div class="fa26-scroll"><table><thead><tr><th>Position</th><th>N / method</th><th>Mean actual points<br><small>FA25 vs 4for4</small></th><th>Mean actual snaps<br><small>FA25 vs 4for4</small></th></tr></thead><tbody>${lines}</tbody></table></div>
       <h4>FA25 category diagnostics (not validation of dynasty breakouts)</h4><div class="fa26-scroll"><table><thead><tr><th>Pregame category</th><th>Captured</th><th>Snap coverage</th><th>40+ snaps</th><th>Mean actual points</th></tr></thead><tbody>${sampleRows}</tbody></table></div>
       <p class="fa26-report-note">Points comparisons require an owner-supplied, matching-week LOG-scored CSV and matching scoring confirmation. No reported actual score is ever interpreted as zero. Defensive snaps are exact-week observed raw snaps, not snap share. This is a small-sample descriptive audit; no significance or score calibration claims.</p>`;
   }
   async function evaluate(){
     if(!frozen){say('Load or freeze a valid snapshot first.',true);return;}
     outStatus.textContent='Fetching public Sleeper IDP weekly observations…';
     const w=frozen.payload.week;
     try{
       const url='https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/main/data/idp_weekly_2026_public.json?t='+Date.now();
       const resp=await fetch(url,{cache:'no-store'});
       if(!resp.ok)throw Error('Weekly public outcome dataset unavailable');
       const doc=await resp.json();
       if(doc?.schema_version!==1||doc.season!==2026||doc.classification!=='PUBLIC_SLEEPER_WEEKLY_IDP_EVIDENCE_NOT_PROJECTION_OR_BREAKOUT'||
          !validInt(doc.last_completed_week,w,18)||!Array.isArray(doc.players)||
          !doc.source_manifest?.some(m=>m.week===w&&/^[0-9a-f]{64}$/.test(m.response_sha256)))
          throw Error(`Week ${w} complete outcome evidence unavailable; no postgame claim`);
       const m=new Map();
       for(const p of doc.players){
         const pid=String(p.sleeper_id),obs=Array.isArray(p.observations)?p.observations.filter(o=>o.week===w):[];
         if(obs.length>1){m.set(pid,null);continue;}
         const o=obs[0];if(o&&isNum(o.defensive_snaps)&&o.defensive_snaps>=0&&o.defensive_snaps<=150 && !m.has(pid))m.set(pid,o.defensive_snaps);
       }
       snapOut=m;weekOut=w;
       outStatus.textContent=`W${w} public defensive snaps loaded for ${[...m.values()].filter(isNum).length} observed players (all NFL). Missing observations remain unknown, not zero.`;
       showReport();
     }catch(e){snapOut=new Map();weekOut=null;outStatus.textContent='Not ready: '+String(e.message||e);showReport();}
   }
   async function pointsChanged(){
     points=new Map();if(!frozen){say('Load a frozen week before actual points.',true);return;}
     const file=$('fa26Points').files[0];if(!file){showReport();return;}
     if(!file.name.toLowerCase().endsWith('.csv')||file.size<30||file.size>2000000){outStatus.textContent='Actual-points file rejected (CSV, 30 bytes–2 MB required).';return;}
     try{points=parseActualPoints(await file.text(),frozen.payload.week);outStatus.textContent=`Read ${points.size} actual LOG points from local CSV. Confirm matching scoring before points comparisons.`;}
     catch(e){outStatus.textContent='Points CSV rejected: '+String(e.message||e);}
     showReport();
   }
   async function exportPrivate(){
     if(!frozen){say('Load or freeze a snapshot first.',true);return;}
     const blob=new Blob([JSON.stringify(frozen,null,2)+'\n'],{type:'application/json'});
     const link=document.createElement('a'),url=URL.createObjectURL(blob);link.href=url;link.download=`LOG-FA26-PRIVATE-2026-W${frozen.payload.week}-${frozen.sha256.slice(0,10)}.json`;
     document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
     say(`Private snapshot exported locally. It contains owner-sourced rankings/projections; do not publish it to GitHub.`);
   }
   $('fa26Capture').addEventListener('click',freeze);
   $('fa26Load').addEventListener('click',load);
   $('fa26Export').addEventListener('click',exportPrivate);
   $('fa26Evaluate').addEventListener('click',evaluate);
   $('fa26Points').addEventListener('change',pointsChanged);
   $('fa26ScoringConfirm').addEventListener('change',showReport);
   $('fa24Week')?.addEventListener('change',()=>{frozen=null;resetEval();say('Week changed: load that week’s frozen snapshot or refresh FA25 and make a new pregame capture.');});
   load();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
