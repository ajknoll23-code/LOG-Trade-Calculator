/* LOG FA27R1 -- Owner-local IDP Role Evidence: five private 2026 Week-10 CSVs.
   NO input data posted to a server, bundled in public code, or merged into FV/MV.
   Season-to-date aggregates (which include W10) and W10 single-week stats remain distinct.
   The page is a static public site; IndexedDB data are private to this browser origin,
   not server-side access-controlled. Import only on a device/browser you trust.
 */
(() => {
 'use strict';
 const ROOT='https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/main/';
 const IDB='LOG_Private_IDP_Role_2026_v1', STORE='evidence', KEY='2026-W10-five-source';
 const CLASS='PRIVATE_OWNER_IDP_ROLE_EVIDENCE_2026_W10_DO_NOT_PUBLISH';
 const GROUPS=['DL','LB','DB'];
 const FIELDS={
  lb:['Green Dot','Player','Team','Games','Defensive Snaps','Snap %','Off-Ball %','Tackle Rate','Role Security','Role Security Tier'],
  seasonSnap:['Player','Team','Pos','Snaps','Team Defensive Snaps','Snap Rate (%)','Nickel Rate (%)','Dime Rate (%)','LOS Rate'],
  w10Snap:['Player','Team','Pos','Snaps','Team Defensive Snaps','Snap Rate (%)','Nickel Rate (%)','Dime Rate (%)','LOS Rate'],
  seasonDB:['Player','Team','Position','Snaps','Team Defensive Snaps','Team Games','Snap Rate (%)','Box Rate (%)','Edge Rate (%)','Outside CB Rate (%)','Slot CB Rate (%)','Safety Rate (%)'],
  w10DB:['Player','Team','Pos','Snaps','Team Defensive Snaps','Snap Rate (%)','Box Rate (%)','Edge Rate (%)','Outside CB Rate (%)','Slot CB Rate (%)','Safety Rate (%)']
 };
 const NAME_TO_TEAM={
  'Arizona Cardinals':'ARI','Atlanta Falcons':'ATL','Baltimore Ravens':'BAL','Buffalo Bills':'BUF',
  'Carolina Panthers':'CAR','Chicago Bears':'CHI','Cincinnati Bengals':'CIN','Cleveland Browns':'CLE',
  'Dallas Cowboys':'DAL','Denver Broncos':'DEN','Detroit Lions':'DET','Green Bay Packers':'GB',
  'Houston Texans':'HOU','Indianapolis Colts':'IND','Jacksonville Jaguars':'JAX','Kansas City Chiefs':'KC',
  'Las Vegas Raiders':'LV','Los Angeles Chargers':'LAC','Los Angeles Rams':'LAR','Miami Dolphins':'MIA',
  'Minnesota Vikings':'MIN','New England Patriots':'NE','New Orleans Saints':'NO','New York Giants':'NYG',
  'New York Jets':'NYJ','Philadelphia Eagles':'PHI','Pittsburgh Steelers':'PIT','San Francisco 49ers':'SF',
  'Seattle Seahawks':'SEA','Tampa Bay Buccaneers':'TB','Tennessee Titans':'TEN','Washington Commanders':'WAS'
 };
 const ALIAS={GBP:'GB',LVR:'LV',NEP:'NE',NOS:'NO',JAC:'JAX',LA:'LAR',OAK:'LV',WSH:'WAS'};
 const $=id=>document.getElementById(id);
 const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
 const norm=s=>String(s??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\b(jr|sr|ii|iii|iv)\b\.?/g,'').replace(/[^a-z0-9]/g,'');
 const team=s=>{const t=String(s??'').trim();if(NAME_TO_TEAM[t])return NAME_TO_TEAM[t];let x=t.toUpperCase();return ALIAS[x]||x;};
 const finite=n=>typeof n==='number'&&Number.isFinite(n);
 const fmt=(v,d=1)=>finite(v)?v.toFixed(d):'—';
 const n=(v,low=-100,high=999999)=>{const s=String(v??'').trim();if(!s)return null;const z=Number(s.replace(/,/g,''));return Number.isFinite(z)&&z>=low&&z<=high?z:null;};
 const key=(name,tm)=>norm(name)+'|'+team(tm);
 const group=(x)=>x==='LB'?'LB':['S','CB','DS','DC','DB'].includes(x)?'DB':['DT','DE','DI','ED','EDGE','DL','OB','IB'].includes(x)?'DL':null;
 const RENDER_EVENT='log-idp-role-updated';
 let current=null,matching=null,availability=null,sourceDate=null,pending=false,selection='available';
 function dbOpen(){return new Promise((resolve,reject)=>{
  if(!window.indexedDB){reject(Error('Private browser storage unavailable'));return;}
  const r=indexedDB.open(IDB,1);r.onupgradeneeded=()=>{if(!r.result.objectStoreNames.contains(STORE))r.result.createObjectStore(STORE);};
  r.onerror=()=>reject(r.error||Error('Cannot open private storage'));r.onsuccess=()=>resolve(r.result);
 });}
 async function dbGet(){const db=await dbOpen();return new Promise((resolve,reject)=>{
  const tx=db.transaction(STORE,'readonly'),r=tx.objectStore(STORE).get(KEY);
  r.onsuccess=()=>resolve(r.result||null);r.onerror=()=>reject(r.error);
  tx.oncomplete=()=>db.close();tx.onerror=()=>{db.close();reject(tx.error);};
 });}
 async function dbPut(value){const db=await dbOpen();return new Promise((resolve,reject)=>{
  const tx=db.transaction(STORE,'readwrite');tx.objectStore(STORE).put(value,KEY);
  tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>{db.close();reject(tx.error);};
 });}
 async function dbDel(){const db=await dbOpen();return new Promise((resolve,reject)=>{
  const tx=db.transaction(STORE,'readwrite');tx.objectStore(STORE).delete(KEY);
  tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>{db.close();reject(tx.error);};
 });}
 function parseCSV(str){
  const lines=[];let row=[],field='',quoted=false;
  str=String(str).replace(/^\uFEFF/,'');
  for(let i=0;i<str.length;i++){
   const c=str[i];if(c==='"'){if(quoted&&str[i+1]==='"'){field+='"';i++;}else quoted=!quoted;}
   else if(c===','&&!quoted){row.push(field);field='';}
   else if((c==='\r'||c==='\n')&&!quoted){if(c==='\r'&&str[i+1]==='\n')i++;row.push(field);if(row.some(v=>String(v).trim()))lines.push(row);row=[];field='';}
   else field+=c;
  }
  if(quoted)throw Error('Unterminated CSV quote');row.push(field);if(row.some(v=>String(v).trim()))lines.push(row);
  if(lines.length<2||lines.length>1200)throw Error('CSV has unexpected row count');
  const header=lines.shift().map(s=>s.trim());
  return {header,records:lines.map(r=>Object.fromEntries(header.map((h,i)=>[h,String(r[i]??'').trim()] )))};
 }
 function identify(fileName,header){
  const h=new Set(header);
  const has=a=>a.every(k=>h.has(k));
  const low=fileName.toLowerCase();
  let kind=null;
  if(has(FIELDS.lb))kind='lb';
  else if(has(FIELDS.seasonDB))kind='seasonDB';
  else if(has(FIELDS.w10DB))kind='w10DB';
  else if(has(FIELDS.seasonSnap))kind=/(full\s*season|full[ -]?season)/.test(low)?'seasonSnap':/week[ -]?10/.test(low)?'w10Snap':null;
  if(!kind||!has(FIELDS[kind]))throw Error('Unrecognized CSV headers/file: '+fileName);
  // Full-season DB may also contain the W10 headers; explicit `Team Games` distinguishes it.
  if(kind==='w10DB'&&h.has('Team Games'))throw Error('Wrong DB alignment source scope');
  return kind;
 }
 function normalizeRecords(kind,records){
  const cap=kind==='lb'?150:kind==='w10DB'?500:kind==='seasonDB'?600:1200;
  if(!records.length||records.length>cap)throw Error(kind+': implausible source population');
  const parsed=[];
  const stats=['Snaps','Team Defensive Snaps','Snap Rate (%)','Nickel Rate (%)','Dime Rate (%)','LOS Rate',
   'Box Rate (%)','Edge Rate (%)','Outside CB Rate (%)','Slot CB Rate (%)','Safety Rate (%)','Other / Not Charted (%)',
   'Games','Defensive Snaps','Snap %','Off-Ball Snaps','Off-Ball %','Tackle Rate','Missed Tackle %',
   'Role Security','Off-Ball Tackle Rate','Run Defense Snaps','Stop Rate (%)','PFF Coverage Grade','PFF Tackle Grade'];
  for(const rec of records){
   if(!rec.Player||!rec.Team)throw Error(kind+': blank player/team');
   const code=team(rec.Team);if(!/^[A-Z]{2,3}$/.test(code))throw Error(kind+': unknown NFL team '+rec.Team);
   const one={name:rec.Player,team:code,position:rec.Pos||rec.Position||(kind==='lb'?'LB':''),values:{}};
   for(const name of stats)if(Object.hasOwn(rec,name)&&rec[name]!=='' ){
    const max=/(Snaps|Games)/.test(name)&&!name.includes('Rate')&&!name.includes('%')?2500:100;
    const z=n(rec[name],0,max);if(z===null)throw Error(kind+': invalid '+name+' for '+rec.Player);one.values[name]=z;
   }
   if(kind==='lb'){
    if(!['','🟢','🟢 (Wk 10)'].includes(rec['Green Dot']))throw Error('Unknown green-dot status');
    one.values.green_dot_status=rec['Green Dot']==='🟢'?'GREEN_DOT':rec['Green Dot']==='🟢 (Wk 10)'?'W10_GREEN_DOT':'NOT_MARKED';
    one.values.role_security_tier=String(rec['Role Security Tier']||'').slice(0,40);
    one.values.role_security_score=n(rec['Role Security'],0,100);
   }
   parsed.push(one);
  }
  return parsed;
 }
 function validatePack(doc){
  if(!doc||doc.schema_version!==1||doc.classification!==CLASS||doc.season!==2026||doc.completed_through_week!==10||!doc.datasets)throw Error('Invalid private LOG 2026 W10 role evidence pack');
  const required=Object.keys(FIELDS);if(required.some(k=>!Array.isArray(doc.datasets[k])))throw Error('Pack must contain all five sources');
  const datasets={};for(const kind of required)datasets[kind]=normalizeRecords(kind,doc.datasets[kind]);
  return datasets;
 }
 async function buildData(files){
  if(files.length===1&&files[0].name.toLowerCase().endsWith('.json')){
   const file=files[0];if(file.size<200||file.size>2000000)throw Error('Pack size invalid');
   const pack=JSON.parse(await file.text());return validatePack(pack);
  }
  if(files.length!==5)throw Error('Select the five supplied CSVs together, or one private combined JSON pack');
  const res={};for(const file of files){
   if(!file.name.toLowerCase().endsWith('.csv')||file.size<100||file.size>2000000)throw Error('CSV type/size invalid');
   const {header,records}=parseCSV(await file.text()),kind=identify(file.name,header);
   if(res[kind])throw Error('Duplicate CSV type: '+kind);
   res[kind]=normalizeRecords(kind,records);
  }
  for(const k of Object.keys(FIELDS))if(!res[k])throw Error('Missing source: '+k);
  return res;
 }
 function indexByIdentity(datasets){
  const map=new Map(),ambiguous=[];let imported=0;
  for(const [kind,rows] of Object.entries(datasets)){
   const seen=new Set(),dups=new Set();
   for(const r of rows){const k=key(r.name,r.team);if(seen.has(k))dups.add(k);seen.add(k);}
   for(const r of rows){
    imported++;const k=key(r.name,r.team);
    if(dups.has(k)){if(!ambiguous.some(a=>a.kind===kind&&a.identity===k))ambiguous.push({kind,identity:k});continue;}
    const m=map.get(k)||{name:r.name,team:r.team,datasets:{}};
    m.datasets[kind]=r;map.set(k,m);
   }
  }
  return {map,ambiguous,imported};
 }
 async function fetchRoster(){
  const resp=await Promise.all(['data/free_agents.json','data/league_rosters.json','config.json'].map(path=>fetch(ROOT+path+'?role='+Date.now(),{cache:'no-store'})));
  if(resp.some(r=>!r.ok))throw Error('Public LOG Sleeper roster unavailable');
  const [free,rosters,config]=await Promise.all(resp.map(r=>r.json()));
  if(!free.league_id||free.league_id!==rosters.league_id||free.league_id!==config.league_id||free.count!==free.free_agents?.length||rosters.rosters?.length!==12)throw Error('League snapshot inconsistent');
  const catalog=[...free.free_agents.map(p=>({...p,owner:'free-agent'}))];
  for(const r of rosters.rosters)for(const k of ['starters','bench','taxi','reserve_ir'])for(const p of r[k]||[])catalog.push({...p,owner:'rostered',roster_id:r.roster_id});
  const byKey=new Map(),byId=new Map();for(const p of catalog){
   const id=String(p.player_id),t=team(p.team),k=key(p.name,t);if(!/^\d+$/.test(id)||!t)continue;
   const arr=byKey.get(k)||[];arr.push(p);byKey.set(k,arr);byId.set(id,p);
  }
  return {free,byKey,byId};
 }
 function matchData(datasets,catalog){
  const {map,ambiguous,imported}=indexByIdentity(datasets);
  const rows=new Map(),unmatched=[];
  for(const [keystr,r] of map){
   const options=catalog.byKey.get(keystr)||[];
   const unique=new Map(options.map(o=>[String(o.player_id),o]));
   if(unique.size!==1){unmatched.push({name:r.name,team:r.team,reason:unique.size?'ambiguous identity':'not in LOG roster/free-agent pool'});continue;}
   const p=[...unique.values()][0],pid=String(p.player_id),g=p.pos||p.position;
   const groupValue=GROUPS.includes(g)?g:(p.fantasy_positions||[]).some(v=>v==='LB')?'LB':(p.fantasy_positions||[]).some(v=>v==='DL')?'DL':(p.fantasy_positions||[]).some(v=>v==='DB')?'DB':null;
   if(!groupValue){unmatched.push({name:r.name,team:r.team,reason:'not IDP eligible'});continue;}
   const old=rows.get(pid);
   // Multiple name aliases resolving to one ID must not silently overwrite.
   if(old){rows.delete(pid);unmatched.push({name:r.name,team:r.team,reason:'duplicate matched Sleeper ID'});continue;}
   rows.set(pid,{id:pid,name:p.name,team:team(p.team),group:groupValue,raw_position:p.raw_position||p.position||null,
    owner:p.owner,roster_id:p.roster_id??null,age:Number.isInteger(p.age)?p.age:null,datasets:r.datasets});
  }
  const report={source_rows:imported,unique_identities:map.size,ambiguous_source_rows:ambiguous.length,
   matched_players:rows.size,unmatched_identities:unmatched.length,unmatched_preview:unmatched.slice(0,18),
   free_agents:[...rows.values()].filter(r=>r.owner==='free-agent').length,
   rostered:[...rows.values()].filter(r=>r.owner==='rostered').length,
   source_coverage:Object.fromEntries(Object.entries(datasets).map(([k,v])=>[k,v.length]))};
  return {rows,report};
 }
 const val=(r,k,field)=>r?.datasets?.[k]?.values?.[field]??null;
 function evidence(row,analysisWeek){
  if(!row||!Number.isInteger(analysisWeek)||analysisWeek<11||analysisWeek>18)return null;
  const season=val(row,'seasonSnap','Snap Rate (%)'),w10=val(row,'w10Snap','Snap Rate (%)');
  const snaps=val(row,'w10Snap','Snaps'),denom=val(row,'w10Snap','Team Defensive Snaps');
  const delta=finite(w10)&&finite(season)?Number((w10-season).toFixed(1)):null;
  const surge=finite(delta)&&delta>=20&&finite(snaps)&&snaps>=35&&finite(w10)&&w10>=65;
  const lb=val(row,'lb','green_dot_status');
  const box=val(row,'w10DB','Box Rate (%)'),slot=val(row,'w10DB','Slot CB Rate (%)');
  const seasonBox=val(row,'seasonDB','Box Rate (%)');
  const boxDelta=finite(box)&&finite(seasonBox)?Number((box-seasonBox).toFixed(1)):null;
  return {id:row.id,group:row.group,age:row.age,owner:row.owner,team:row.team,
   season_snap_pct:season,w10_snap_pct:w10,w10_snaps:snaps,w10_team_snaps:denom,
   delta_pct_points:delta,role_surge:surge,
   green_dot_status:lb||null,
   lb_role_security_tier:val(row,'lb','role_security_tier'),lb_role_security_score:val(row,'lb','role_security_score'),
   lb_tackle_rate:val(row,'lb','Tackle Rate'),lb_missed_tackle_rate:val(row,'lb','Missed Tackle %'),
   w10_box_pct:box,w10_slot_pct:slot,season_box_pct:seasonBox,box_delta_pct_points:boxDelta,
   w10_los_rate:val(row,'w10Snap','LOS Rate'),season_los_rate:val(row,'seasonSnap','LOS Rate'),
   lb_offball_pct:val(row,'lb','Off-Ball %'),
   w10_outside_pct:val(row,'w10DB','Outside CB Rate (%)'),
   position_disagreement:!!row.datasets.w10DB && !!row.raw_position &&
    ['CB','S','SS','FS'].includes(row.raw_position.toUpperCase())&&
    ['CB','S'].includes(row.datasets.w10DB.position)&&
    ({SS:'S',FS:'S'}[row.raw_position.toUpperCase()]||row.raw_position.toUpperCase())!==row.datasets.w10DB.position,
   source_count:Object.keys(row.datasets).length,
   scope:'Week 10 observed vs 2026 season-to-date (season figure includes W10); role source available for Week 11+ only',
   week:10};
 }
 function status(msg,error=false){const p=$('fa27Status');if(p){p.textContent=msg;p.classList.toggle('fa27-error',error);}}
 function notify(){window.dispatchEvent(new CustomEvent(RENDER_EVENT,{detail:{loaded:!!current,counts:current?.report||null}}));render();}
 function label(row){const e=evidence(row,11);if(!e)return [];
  const a=[];if(e.role_surge)a.push('W10 ROLE SURGE');
  if(e.green_dot_status==='GREEN_DOT')a.push('GREEN DOT');
  if(e.green_dot_status==='W10_GREEN_DOT')a.push('W10 GREEN DOT');
  if(finite(e.w10_snap_pct)&&e.w10_snap_pct>=90)a.push('90%+ W10 SNAPS');
  if(finite(e.w10_box_pct)&&e.w10_box_pct>=25&&finite(e.w10_snaps)&&e.w10_snaps>=25)a.push('BOX USAGE');
  if(finite(e.box_delta_pct_points)&&e.box_delta_pct_points>=10&&finite(e.w10_snaps)&&e.w10_snaps>=35)a.push('BOX ROLE UP');
  return a;
 }
 function evidenceText(row){const e=evidence(row,11);if(!e)return [];
  const z=[];
  if(finite(e.w10_snap_pct))z.push(`W10 ${fmt(e.w10_snap_pct)}% of team defensive snaps (${e.w10_snaps??'unknown'} / ${e.w10_team_snaps??'unknown'})`);
  if(finite(e.season_snap_pct))z.push(`2026 season-to-date snap rate ${fmt(e.season_snap_pct)}% (includes W10)`);
  if(finite(e.delta_pct_points))z.push(`W10 vs season-to-date: ${e.delta_pct_points>=0?'+':''}${fmt(e.delta_pct_points)} percentage points (NOT a week-over-week trend)`);
  if(e.green_dot_status==='GREEN_DOT')z.push('Green-dot designation in owner LB CSV; season-level source label');
  if(e.green_dot_status==='W10_GREEN_DOT')z.push('Green-dot designation labeled Wk 10 only');
  if(e.lb_role_security_tier)z.push(`LB source role security: ${e.lb_role_security_tier} (${fmt(e.lb_role_security_score)} source score; not a LOG grade)`);
  if(finite(e.lb_tackle_rate))z.push(`LB source tackle rate: ${fmt(e.lb_tackle_rate)}%${finite(e.lb_offball_pct)?'; off-ball alignment '+fmt(e.lb_offball_pct)+'%':''}`);
  if(finite(e.w10_los_rate))z.push(`W10 source LOS rate ${fmt(e.w10_los_rate)}% (source-defined; not snap share)`);
  if(finite(e.w10_box_pct))z.push(`W10 DB alignment: ${fmt(e.w10_box_pct)}% box; ${fmt(e.w10_slot_pct)}% slot${finite(e.box_delta_pct_points)?'; box vs inclusive season '+(e.box_delta_pct_points>=0?'+':'')+fmt(e.box_delta_pct_points)+' pts':''} (source categories may overlap)`);
  if(e.position_disagreement)z.push('Source alignment position differs from Sleeper raw position; manually check eligibility');
  return z;
 }
 function updateCards(){
  const week=Number($('fa24Week')?.value);
  const cards=document.querySelectorAll('#fa24List .fa25-card[data-player-id]');
  for(const c of cards){const id=c.getAttribute('data-player-id');const r=matching?.rows?.get(id)||null;
   const old=c.querySelector('.fa27-card-proof');if(old)old.remove();
   if(!r||week<11||week>18)continue;
   const list=evidenceText(r);if(!list.length)continue;
   const b=document.createElement('section');b.className='fa27-card-proof';
   b.innerHTML=`<strong>Observed Week 10 role evidence</strong><small>${label(r).map(esc).join(' · ')||'Source evidence, not a graded recommendation'}</small><ul>${list.map(t=>`<li>${esc(t)}</li>`).join('')}</ul>`;
   const d=c.querySelector('.fa25-details');if(d)d.insertAdjacentElement('beforebegin',b);else c.appendChild(b);
  }
 }
 function tableRows(rows,max){
  return rows.slice(0,max).map(r=>{
   const e=evidence(r,11),l=label(r);return `<tr><td><strong>${esc(r.name)}</strong><small>${esc(r.team)} · ${esc(r.group)} · ${esc(r.owner)}</small></td>
   <td>${fmt(e?.season_snap_pct)}%</td><td>${fmt(e?.w10_snap_pct)}%</td><td>${finite(e?.delta_pct_points)?(e.delta_pct_points>=0?'+':'')+fmt(e.delta_pct_points)+' pts':'—'}</td><td>${l.map(x=>`<span>${esc(x)}</span>`).join(' ')||'—'}</td></tr>`;
  }).join('');
 }
 function shortlist(rows,scope){
  const r=rows.filter(r=>scope==='all'||r.owner==='free-agent').filter(r=>evidence(r,11));
  const surges=r.filter(x=>evidence(x,11).role_surge),dots=r.filter(x=>/GREEN_DOT/.test(evidence(x,11).green_dot_status||''));
  const primary=surges.sort((a,b)=>evidence(b,11).delta_pct_points-evidence(a,11).delta_pct_points);
  const dotRows=dots.filter(x=>!surges.includes(x)).sort((a,b)=>(evidence(b,11).w10_snap_pct??0)-(evidence(a,11).w10_snap_pct??0));
  return primary.concat(dotRows,r.filter(x=>!primary.includes(x)&&!dotRows.includes(x)).filter(x=>finite(evidence(x,11).w10_snap_pct))
   .sort((a,b)=>(evidence(b,11).w10_snap_pct??0)-(evidence(a,11).w10_snap_pct??0)));
 }
 function render(){
  updateCards();if(!current||!matching)return;
  const rows=[...matching.rows.values()],scope=$('fa27Scope')?.value||'available',list=shortlist(rows,scope);
  const body=$('fa27Candidates');if(body)body.innerHTML=tableRows(list,30)||'<tr><td colspan="5">No matching evidence in this scope</td></tr>';
  const note=$('fa27Report');if(note){const r=matching.report;note.textContent=`Matched ${r.matched_players} unique Sleeper IDPs (${r.free_agents} free agents / ${r.rostered} rostered); ${r.ambiguous_source_rows} ambiguous source player/team keys omitted; ${r.unmatched_identities} unmatched identities. Inputs are private to this browser.`;}
  const start=$('fa27StartSit');if(start){
   const high=shortlist(rows.filter(r=>r.owner==='rostered'), 'all').slice(0,15);
   start.innerHTML=`<strong>W10 role context for rostered IDPs</strong><p>For Week 11+ only. This is independent of Macri/Woellert weekly rankings and is not a lineup recommendation.</p><div class="fa27-mini">${high.map(p=>{const e=evidence(p,11);return `<div><b>${esc(p.name)}</b> · ${esc(p.team)} · W10 ${fmt(e.w10_snap_pct)}% (${finite(e.delta_pct_points)?(e.delta_pct_points>=0?'+':'')+fmt(e.delta_pct_points)+' pts':'no season baseline'})</div>`;}).join('')||'No matched rostered IDP evidence'}</div>`;
  }
  const watch=$('fa27Watch');if(watch){
   watch.innerHTML=`<strong>Imported 2026 Week 10 role research</strong><p>All matched IDPs, including rostered players. Not the separate private scouting watchlist.</p><div class="fa27-mini">${shortlist(rows,'all').slice(0,25).map(p=>{const e=evidence(p,11);return `<div><b>${esc(p.name)}</b> · ${esc(p.team)} · ${esc(p.owner)} · W10 ${fmt(e.w10_snap_pct)}%</div>`;}).join('')}</div>`;
  }
 }
 async function setCurrent(doc,catalog,save){
  matching=matchData(doc.datasets,catalog);availability=catalog;current=doc;
  if(save)await dbPut(doc);
  sourceDate=new Date(doc.created_at).toLocaleString();
  const stale=Date.now()/1000-catalog.free.synced_at>72*3600;
  status(`Five-source W10 role evidence loaded (${matching.report.matched_players} matched). Saved locally on this device; for Week 11+ only.${stale?' ROSTER SNAPSHOT IS STALE: verify waiver availability.':''}`);
  notify();
 }
 function createUI(){
  const target=$('fa-ws-idp-panel');if(!target||$('fa27Lab'))return false;
  const host=document.createElement('section');host.id='fa27Lab';host.className='fa27';
  host.innerHTML=`<header><div><small>FA27 · OWNER-LOCAL ROLE INTELLIGENCE</small><h3>Snap share, green dots & DB alignment</h3><p>W10 vs season-to-date role changes from five private CSVs. Complements expert rankings; never modifies FV/MV.</p></div><span>PRIVATE · BROWSER-ONLY</span></header>
  <div class="fa27-upload"><label>Import five private 2026 CSV files (or one LOG private pack)<input id="fa27Files" type="file" accept=".csv,.json,text/csv,application/json" multiple></label><button type="button" id="fa27Import">Correlate role data</button><button type="button" id="fa27Clear">Forget saved research</button></div>
  <p id="fa27Status" role="status" aria-live="polite">Checking for previously saved research on this device…</p>
  <p class="fa27-warning">These are observations collected after W10. Use for Week 11+ decisions only, never as pregame W10 evidence. Season figures include Week 10. The five source categories remain independent; Week 10 DB alignment percentages can overlap and are not meant to sum to 100%.</p>
  <div class="fa27-controls"><label>Availability<select id="fa27Scope"><option value="available">Available only</option><option value="all">All players (including rostered)</option></select></label></div>
  <p id="fa27Report"></p><div class="fa27-scroll"><table><thead><tr><th>Player</th><th>Season snap rate</th><th>W10 snap rate</th><th>Change</th><th>Evidence</th></tr></thead><tbody id="fa27Candidates"><tr><td colspan="5">Import role evidence to begin</td></tr></tbody></table></div>
  <details><summary>Data-quality and scoring safeguards</summary><p>Unique Sleeper identity requires matching normalized name and NFL team. A duplicate in any single CSV source is excluded for that source. Source-specific role-security grades are not LOG scores. Changes compare one week with an inclusive season average, not two independent periods.</p></details>`;
  const intro=target.querySelector('.fa-ws-intro');if(intro)intro.insertAdjacentElement('afterend',host);else target.prepend(host);
  for(const [place,id] of [['fa-ws-startsit-panel','fa27StartSit'],['fa-ws-watch-panel','fa27Watch']]){
   const t=$(place);if(t){const div=document.createElement('div');div.id=id;div.className='fa27-secondary';t.appendChild(div);}
  }
  $('fa27Import').addEventListener('click',importFiles);
  $('fa27Clear').addEventListener('click',async()=>{if(pending)return;pending=true;try{await dbDel();current=null;matching=null;availability=null;status('Private role evidence forgotten on this device.');const b=$('fa27Candidates');if(b)b.innerHTML='<tr><td colspan="5">No role data loaded</td></tr>';for(const id of ['fa27StartSit','fa27Watch'])if($(id))$(id).replaceChildren();notify();}catch(e){status('Could not clear private research: '+e.message,true);}finally{pending=false;}});
  $('fa27Scope').addEventListener('change',render);
  // FA25 rerenders cards; decorate on demand without touching its own rankings or state.
  const fa25List=$('fa24List');if(fa25List){const observer=new MutationObserver(()=>{
   // Only additions of FA25 cards trigger this; injecting our role notes must not recurse.
   if(!current)return;const cards=[...fa25List.querySelectorAll('.fa25-card[data-player-id]')];
   if(cards.some(c=>!c.querySelector('.fa27-card-proof')))updateCards();
  });observer.observe(fa25List,{childList:true,subtree:false});}
  return true;
 }
 async function importFiles(){
  if(pending)return;pending=true;
  $('fa27Import').disabled=true;
  try{const files=[...$('fa27Files').files];if(!files.length)throw Error('Select the five CSVs or the private combined JSON pack');
   status('Validating five source schemas and matching the current Sleeper pool…');
   const datasets=await buildData(files),catalog=await fetchRoster(),doc={schema_version:1,classification:CLASS,
    season:2026,completed_through_week:10,created_at:new Date().toISOString(),datasets};
   await setCurrent(doc,catalog,true);$('fa27Files').value='';
  }catch(e){status('Import rejected: '+String(e.message||e),true);}
  finally{pending=false;$('fa27Import').disabled=false;}
 }
 // Read-only research seam for FA25 or other same-origin LOG modules. Input is a Sleeper ID.
 window.LOG_IDP_ROLE27_READ=(sleeperId,analysisWeek)=>evidence(matching?.rows?.get(String(sleeperId)),Number(analysisWeek));
 async function init(){if(!createUI())return;
  try{const doc=await dbGet();if(doc){
    if(doc.classification!==CLASS||doc.season!==2026||doc.completed_through_week!==10)throw Error('Stored private research schema mismatch');
    for(const k of Object.keys(FIELDS))if(!Array.isArray(doc.datasets?.[k]))throw Error('Private research incomplete');
    await setCurrent(doc,await fetchRoster(),false);
   }else status('Select the five CSVs or the combined private research pack. Nothing is sent to GitHub.');
  }catch(e){status('Saved research not available: '+String(e.message||e),true);}
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
