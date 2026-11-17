/* LOG FA28R1 — Mobile-first Free Agent Player Finder.
 * Browser-only private weekly CSV imports. Public read-only LOG Sleeper data.
 * Never uploads paid evidence, alters FV/MV, or rewrites FA25/FA26 frozen results.
 * Week-over-week requires actual consecutive per-week observations; missing != zero.
 */
(() => {
 'use strict';
 const ROOT='https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/main/';
 const DB='LOG_Private_FA28_WeeklySnaps_2026_v1',STORE='weeks',KEY='owner-snap-weeks';
 const SOURCE_CLASS='PUBLIC_SLEEPER_WEEKLY_IDP_EVIDENCE_NOT_PROJECTION_OR_BREAKOUT';
 const TYPES=['LB','DL','DB'];
 const TEAM_NAMES={'Arizona Cardinals':'ARI','Atlanta Falcons':'ATL','Baltimore Ravens':'BAL','Buffalo Bills':'BUF','Carolina Panthers':'CAR','Chicago Bears':'CHI','Cincinnati Bengals':'CIN','Cleveland Browns':'CLE','Dallas Cowboys':'DAL','Denver Broncos':'DEN','Detroit Lions':'DET','Green Bay Packers':'GB','Houston Texans':'HOU','Indianapolis Colts':'IND','Jacksonville Jaguars':'JAX','Kansas City Chiefs':'KC','Las Vegas Raiders':'LV','Los Angeles Chargers':'LAC','Los Angeles Rams':'LAR','Miami Dolphins':'MIA','Minnesota Vikings':'MIN','New England Patriots':'NE','New Orleans Saints':'NO','New York Giants':'NYG','New York Jets':'NYJ','Philadelphia Eagles':'PHI','Pittsburgh Steelers':'PIT','San Francisco 49ers':'SF','Seattle Seahawks':'SEA','Tampa Bay Buccaneers':'TB','Tennessee Titans':'TEN','Washington Commanders':'WAS'};
 const TEAM_ALIAS={GBP:'GB',LVR:'LV',NEP:'NE',NOS:'NO',JAC:'JAX',LA:'LAR',WSH:'WAS'};
 const $=s=>document.querySelector(s);
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
 const numeric=x=>typeof x==='number'&&Number.isFinite(x);
 const fmt=(x,d=1)=>numeric(x)?x.toFixed(d):'—';
 const normalize=s=>String(s??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\b(jr|sr|ii|iii|iv)\b\.?/g,'').replace(/[^a-z0-9]/g,'');
 const team=t=>TEAM_NAMES[String(t).trim()]||TEAM_ALIAS[String(t).toUpperCase()]||String(t??'').toUpperCase();
 const key=(name,tm)=>normalize(name)+'|'+team(tm);
 const int=(v,lo,hi)=>Number.isInteger(Number(v))&&Number(v)>=lo&&Number(v)<=hi?Number(v):null;
 const clamp=(v,lo,hi)=>Number.isFinite(Number(v))?Math.max(lo,Math.min(hi,Number(v))):lo;
 const percent=(x)=>numeric(x)?`${fmt(x)}%`:'—';
 let free=[],publicWeekly=new Map(),publicUsage=new Map(),extraWeeks=new Map(),ready=false,sourceInfo={};
 let visibleRows=[],limit=30,storageEnabled=true;
 const defaults={mode:'tackles',position:'ALL',scope:'free',minSnaps:40,minRate:10,minSampleSnaps:100,minGames:2,minGain:8,rateSource:'best',maxLag:1,sort:'rate',search:'',includeInjured:false};
 let filters={...defaults};
 const qs=id=>document.getElementById(id);
 function dbOpen(){return new Promise((resolve,reject)=>{
  if(!window.indexedDB)return reject(Error('Private local browser storage is unavailable'));
  const r=indexedDB.open(DB,1);r.onupgradeneeded=()=>{if(!r.result.objectStoreNames.contains(STORE))r.result.createObjectStore(STORE);};
  r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error||Error('Private storage unavailable'));
 });}
 function dbRead(){return dbOpen().then(db=>new Promise((resolve,reject)=>{
  const tx=db.transaction(STORE,'readonly'),r=tx.objectStore(STORE).get(KEY);
  r.onsuccess=()=>resolve(r.result||null);r.onerror=()=>reject(r.error);
  tx.oncomplete=()=>db.close();tx.onerror=()=>{db.close();reject(tx.error);};
 }));}
 function dbSave(value){return dbOpen().then(db=>new Promise((resolve,reject)=>{
  const tx=db.transaction(STORE,'readwrite');tx.objectStore(STORE).put(value,KEY);
  tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>{db.close();reject(tx.error);};
 }));}
 function parseCSV(content){
  const rows=[];let row=[],field='',quote=false;content=String(content).replace(/^\uFEFF/,'');
  for(let i=0;i<content.length;i++){
   const c=content[i];if(c==='"'){if(quote&&content[i+1]==='"'){field+='"';i++;}else quote=!quote;}
   else if(c===','&&!quote){row.push(field);field='';}
   else if((c==='\r'||c==='\n')&&!quote){if(c==='\r'&&content[i+1]==='\n')i++;row.push(field);field='';if(row.some(s=>s.trim()))rows.push(row);row=[];}
   else field+=c;
  }
  if(quote)throw Error('Unclosed CSV quotation');row.push(field);if(row.some(s=>s.trim()))rows.push(row);
  if(rows.length<2||rows.length>1300)throw Error('CSV needs a header and 1–1299 records');
  const header=rows.shift().map(x=>x.trim());
  if(!['Player','Team','Snaps','Team Defensive Snaps','Snap Rate (%)'].every(x=>header.includes(x)))throw Error('Expected defensive snap-rate CSV (Player, Team, Snaps, Team Defensive Snaps, Snap Rate (%))');
  return rows.map(r=>Object.fromEntries(header.map((x,i)=>[x,String(r[i]??'').trim()])));
 }
 function importWeekly(files){
  if(!files.length||files.length>12)throw Error('Choose 1–12 weekly snap-rate CSV files');
  return Promise.all(files.map(async file=>{
   if(!file.name.toLowerCase().endsWith('.csv')||file.size<100||file.size>2000000)throw Error('Only weekly snap-rate CSV files up to 2 MB are supported');
   const match=file.name.match(/(?:week|wk)[\s._-]*(\d{1,2})\b/i);
   const w=match?int(match[1],1,18):files.length===1?int(qs('fa28ImportWeek').value,1,18):null;
   if(w===null)throw Error('A multi-file import needs Week NN in each filename');
   const rows=parseCSV(await file.text()),found=new Map(),dups=new Set();
   for(const row of rows){
    const k=key(row.Player,row.Team),sn=Number(row.Snaps),total=Number(row['Team Defensive Snaps']),pct=Number(row['Snap Rate (%)']);
    if(!k.split('|')[0]||!/^\d+(\.\d+)?$/.test(row.Snaps)||!Number.isInteger(sn)||sn<0||sn>150||!Number.isInteger(total)||total<0||total>150||sn>total||!Number.isFinite(pct)||pct<0||pct>100)
     throw Error(`Invalid snap count or rate for ${row.Player}`);
    if(total>0&&Math.abs(pct-100*sn/total)>1.5)throw Error(`Snap rate disagrees with snaps/team snaps for ${row.Player}`);
    if(found.has(k))dups.add(k);
    found.set(k,{name:row.Player,team:team(row.Team),snaps:sn,share:pct});
   }
   for(const k of dups)found.delete(k); // Duplicate source identities remain unresolved; never silently select one.
   return {week:w,items:[...found.entries()].map(([k,v])=>({identity:k,...v})),duplicate_keys:dups.size,filename:file.name};
  }));
 }
 async function fetchJson(path){const r=await fetch(ROOT+path+'?fa28='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error(`${path}: HTTP ${r.status}`);return r.json();}
 async function sources(){
  const [pool,weekly,usage,rosters,config]=await Promise.all([
   fetchJson('data/free_agents.json'),fetchJson('data/idp_weekly_2026_public.json'),fetchJson('data/idp_usage_2026_season.json'),
   fetchJson('data/league_rosters.json'),fetchJson('config.json')]);
  if(!Array.isArray(pool.free_agents)||pool.count!==pool.free_agents.length||!pool.league_id||pool.league_id!==rosters.league_id||pool.league_id!==config.league_id||!Array.isArray(rosters.rosters)||rosters.rosters.length!==12)throw Error('Free-agent/roster pool mismatch');
  if(weekly.classification!==SOURCE_CLASS||weekly.season!==2026||!Array.isArray(weekly.players)||!Number.isInteger(weekly.last_completed_week))throw Error('Unexpected public weekly research schema');
  if(usage.schema_version!==1||!Array.isArray(usage.players))throw Error('Unexpected historical tackle usage schema');
  const rostered=rosters.rosters.flatMap(r=>['starters','bench','taxi','reserve_ir'].flatMap(k=>r[k]||[]).map(p=>({...p,owner:'rostered'})));
  const all=[...pool.free_agents.map(p=>({...p,owner:'free'})),...rostered];
  const byId=new Map();for(const p of all){if(!/^\d+$/.test(String(p.player_id)))continue;const prev=byId.get(String(p.player_id));if(prev){byId.delete(String(p.player_id));continue;}byId.set(String(p.player_id),p);}
  free=[...byId.values()].filter(p=>TYPES.includes(p.pos)||p.fantasy_positions?.some(x=>TYPES.includes(x)));
  publicWeekly=new Map(weekly.players.map(p=>[String(p.sleeper_id),p]));
  publicUsage=new Map(usage.players.filter(p=>p.identity_status==='exact_name_team').map(p=>[String(p.sleeper_id),p]));
  sourceInfo={asOf:new Date(pool.synced_at*1000).toLocaleString(),currentPublicWeek:weekly.last_completed_week,all:free.length,
   free:free.filter(p=>p.owner==='free').length,stale:Date.now()/1000-pool.synced_at>72*3600,
   historical:'Historical tackle-rate source has no stated week range'};
 }
 function toMap(docs){
  const idIndex=new Map(),conflict=new Set();for(const p of free){const k=key(p.name,p.team);const v=idIndex.get(k)||[];v.push(String(p.player_id));idIndex.set(k,v);}
  const out=new Map();let unmatched=0,ambiguous=0;
  for(const doc of docs){
   if(!Number.isInteger(doc.week)||!Array.isArray(doc.items))throw Error('Invalid saved weekly source schema');
   for(const row of doc.items){const ids=idIndex.get(row.identity)||[];
    if(ids.length!==1){unmatched++;continue;}
    const pk=ids[0]+'|'+doc.week;
    if(out.has(pk)){conflict.add(pk);continue;}
    out.set(pk,{snaps:row.snaps,share:row.share,source:'Owner CSV W'+doc.week});
   }
   ambiguous+=doc.duplicate_keys||0;
  }
  for(const k of conflict)out.delete(k);
  return {map:out,unmatched,ambiguous:ambiguous+conflict.size};
 }
 function weeksFor(p,custom){
  const w=new Map(),weekly=publicWeekly.get(String(p.player_id));
  for(const v of weekly?.observations||[]){if(int(v.week,1,18)===null||!numeric(v.defensive_snaps)||v.defensive_snaps<0||v.defensive_snaps>150)continue;
   w.set(v.week,{week:v.week,snaps:v.defensive_snaps,share:null,tackles:numeric(v.tackles)?v.tackles:null,source:'Sleeper public'});
  }
  // Week 10 from imported FA27 role data is not retrospectively used as W10 pregame research.
  const fromRole=typeof window.LOG_IDP_ROLE27_READ==='function'?window.LOG_IDP_ROLE27_READ(String(p.player_id),11):null;
  if(fromRole&&numeric(fromRole.w10_snaps)&&fromRole.week===10){
   const old=w.get(10);w.set(10,{week:10,snaps:fromRole.w10_snaps,share:fromRole.w10_snap_pct,
    tackles:old?.tackles??null,source:'Private FA27 W10'});
  }
  for(let n=1;n<=18;n++){const o=custom.map.get(String(p.player_id)+'|'+n);if(o){const old=w.get(n);
    w.set(n,{week:n,snaps:o.snaps,share:o.share,tackles:old?.tackles??null,source:o.source});
  }}
  return [...w.values()].sort((a,b)=>a.week-b.week);
 }
 function recentTackles(weekRows){
  // Only weekly observations where BOTH defensive snaps and tackles are directly reported.
  const valid=weekRows.filter(o=>numeric(o.tackles)&&numeric(o.snaps)&&o.snaps>0);
  const totalSnaps=valid.reduce((x,o)=>x+o.snaps,0),totalTackles=valid.reduce((x,o)=>x+o.tackles,0);
  return {rate:totalSnaps>0?100*totalTackles/totalSnaps:null,games:valid.length,snaps:totalSnaps,
   tackles:totalTackles,weeks:valid.map(x=>x.week)};
 }
 function getRate(p,history,role){
  const recent=recentTackles(history);const historical=publicUsage.get(String(p.player_id));
  const u=numeric(historical?.tackle_rate_pct)?{rate:historical.tackle_rate_pct,source:'Historical usage (date range unspecified)',
    sampleSnaps:historical.defensive_snaps,games:historical.games_played,scope:'historical'}:null;
  const lb=role&&numeric(role.lb_tackle_rate)?{rate:role.lb_tackle_rate,source:'Owner LB tackle-rate CSV (scope not week-specific)',
    sampleSnaps:role.lb_sample_snaps??null,games:null,scope:'ownerLB'}:null;
  const rw=recent.rate!==null?{rate:recent.rate,source:`Sleeper actuals W${recent.weeks.join(',')}`,
    sampleSnaps:recent.snaps,games:recent.games,scope:'weekly'}:null;
  let chosen=null;
  if(filters.rateSource==='recent')chosen=rw;
  else if(filters.rateSource==='ownerLB')chosen=lb;
  else if(filters.rateSource==='historical')chosen=u;
  else chosen=(lb&&numeric(lb.sampleSnaps)&&lb.sampleSnaps>=filters.minSampleSnaps?lb:null)||
    (rw&&rw.sampleSnaps>=filters.minSampleSnaps&&rw.games>=filters.minGames?rw:null)||
    (u&&numeric(u.sampleSnaps)&&u.sampleSnaps>=filters.minSampleSnaps?u:null); 
  return {chosen,recent:rw,lb,historical:u};
 }
 function trendInfo(weeks){
  if(!weeks.length)return {strict3:false,up2:false,gain3:null,gain2:null,last:[]};
  const end=weeks.at(-1),last3=[end.week-2,end.week-1,end.week].map(w=>weeks.find(x=>x.week===w));
  const last2=last3.slice(1);
  const strict3=last3.every(Boolean)&&last3[0].snaps<last3[1].snaps&&last3[1].snaps<last3[2].snaps;
  const up2=last2.every(Boolean)&&last2[1].snaps>last2[0].snaps;
  return {strict3,up2,gain3:last3.every(Boolean)?last3[2].snaps-last3[0].snaps:null,
   gain2:last2.every(Boolean)?last2[1].snaps-last2[0].snaps:null,last:last3.filter(Boolean)};
 }
 function record(p,custom,globalWeek){
  const history=weeksFor(p,custom),latest=history.at(-1)||null;
  const role=typeof window.LOG_IDP_ROLE27_READ==='function'?window.LOG_IDP_ROLE27_READ(String(p.player_id),11):null;
  const rates=getRate(p,history,role),trend=trendInfo(history);
  const group=TYPES.includes(p.pos)?p.pos:(p.fantasy_positions||[]).find(x=>TYPES.includes(x))||'OTHER';
  return {id:String(p.player_id),name:p.name,team:p.team,age:p.age,group,owner:p.owner,rawPosition:p.raw_position||group,
   injury:p.injury_status||null,status:p.status||null,latest,history,role,rates,trend,
   lag:latest?globalWeek-latest.week:999};
 }
 function eligible(r){
  if(filters.scope==='free'&&r.owner!=='free')return false;
  if(filters.position!=='ALL'&&r.group!==filters.position)return false;
  if(!filters.includeInjured&&(/^(IR|OUT|PUP|SUSPENDED)/i.test(String(r.injury||''))||r.status==='Inactive'))return false;
  if(filters.search&&!normalize(r.name+' '+r.team+' '+r.group).includes(normalize(filters.search)))return false;
  if(!r.latest||r.latest.snaps<filters.minSnaps||r.lag>filters.maxLag)return false;
  const rate=r.rates.chosen;
  if(filters.mode==='tackles'){
   if(!rate||rate.rate<filters.minRate)return false;
   if(rate.scope==='weekly'&&(rate.sampleSnaps<filters.minSampleSnaps||rate.games<filters.minGames))return false;
   if(rate.scope==='historical'&&(rate.sampleSnaps??0)<filters.minSampleSnaps)return false;
   if(rate.scope==='ownerLB'&&(!r.role||!numeric(r.role.lb_tackle_rate)||(rate.sampleSnaps??0)<filters.minSampleSnaps))return false;
  }
  if(filters.mode==='rising'&&!(r.trend.strict3&&r.trend.gain3>=filters.minGain))return false;
  if(filters.mode==='jump'&&!(r.role?.role_surge&&r.role?.delta_pct_points>=filters.minGain&&r.latest.week===10))return false;
  return true;
 }
 function sortRows(rows){
  const byRate=r=>r.rates.chosen?.rate??-1,bySnap=r=>r.latest?.snaps??-1;
  const sort=filters.mode==='rising'&&filters.sort==='rate'?'gain':filters.sort;
  rows.sort((a,b)=>sort==='snaps'?bySnap(b)-bySnap(a):sort==='gain'?(b.trend.gain3??-999)-(a.trend.gain3??-999):
   sort==='young'?(a.age??99)-(b.age??99):sort==='week'? (b.latest?.week??0)-(a.latest?.week??0):
   byRate(b)-byRate(a)||bySnap(b)-bySnap(a));
  return rows;
 }
 function chart(history){
  if(!history.length)return '<div class="fa28-no-data">No verified per-week snaps</div>';
  const last=history.at(-1).week,start=Math.max(1,last-5),recent=Array.from({length:last-start+1},(_,i)=>history.find(x=>x.week===start+i)||{week:start+i,snaps:null});
  const peak=Math.max(70,...recent.filter(o=>numeric(o.snaps)).map(o=>o.snaps));
  return `<div class="fa28-week-bars" role="list" aria-label="Exact calendar-week defensive snaps, missing weeks shown as dashes">${recent.map(o=>`<div class="fa28-bar-item" role="listitem" aria-label="Week ${o.week}, ${numeric(o.snaps)?o.snaps+' defensive snaps':'no observation'}"><div class="fa28-bar-value">${numeric(o.snaps)?o.snaps:'—'}</div><div class="fa28-bar-track">${numeric(o.snaps)?`<div class="fa28-bar" style="height:${Math.max(3,Math.round(o.snaps/peak*100))}%"></div>`:''}</div><div class="fa28-bar-week">W${o.week}</div></div>`).join('')}</div>`;
 }
 function drawCard(r){
  const rate=r.rates.chosen,tackle=rate?`${fmt(rate.rate)}%`:'Not measured';
  const rising=r.trend.strict3&&r.trend.gain3>=filters.minGain;
  const tags=[];if(r.role?.green_dot_status==='GREEN_DOT'||r.role?.green_dot_status==='W10_GREEN_DOT')tags.push('Green dot');
  if(r.role?.role_surge)tags.push('W10 role surge');
  if(rising)tags.push('3-week rising');
  if(r.injury)tags.push('Injury: '+r.injury);
  return `<article class="fa28-result"><div class="fa28-result-top"><div><strong>${esc(r.name)}</strong> <span>${esc(r.team)} · ${esc(r.rawPosition)} · Age ${r.age??'—'}</span></div><span class="fa28-owner ${r.owner==='free'?'fa28-available':''}">${r.owner==='free'?'FREE AGENT':'ROSTERED'}</span></div>
   <div class="fa28-metrics"><div><small>Latest observed snaps</small><b>${r.latest?.snaps??'—'} <em>W${r.latest?.week??'—'}</em></b></div><div><small>Tackle rate</small><b>${tackle}</b></div><div><small>3-week snap gain</small><b>${r.trend.gain3===null?'—':(r.trend.gain3>=0?'+':'')+r.trend.gain3}</b></div></div>
   ${chart(r.history)}
   <div class="fa28-card-foot"><small>${esc(rate?.source||'Tackle data unavailable')}${rate?.sampleSnaps!=null?` · ${rate.sampleSnaps} sample snaps`:''}${rate?.games!=null?` · ${rate.games} games`:''}</small><small>Latest: ${esc(r.latest?.source||'unknown')} · ${esc(r.lag+' week(s) behind newest data')}</small></div>
   ${tags.length?`<div class="fa28-tags">${tags.map(x=>`<span>${esc(x)}</span>`).join('')}</div>`:''}
   <details><summary>Exact weekly evidence & safeguards</summary><div class="fa28-detail">
   ${r.history.length?r.history.map(o=>`<div>W${o.week}: <b>${o.snaps} snaps</b>${numeric(o.tackles)?`, ${o.tackles} tackles`:''} · ${esc(o.source)}</div>`).join(''):'No weekly evidence'}
   ${r.role?.season_snap_pct!=null?`<p>Season-to-date snap rate ${fmt(r.role.season_snap_pct)}%; W10 ${fmt(r.role.w10_snap_pct)}%. Their difference is <b>not</b> a week-to-week trend.</p>`:''}
   ${rate?.scope==='ownerLB'?'<p>LB tackle rate comes from the separate owner CSV, not necessarily the displayed week.</p>':''}
   ${rate?.scope==='historical'?'<p>Historical tackle-rate dataset does not identify its date range.</p>':''}
   ${r.lag>0?'<p>This player lacks data for the latest observed week; do not assume a zero snap count.</p>':''}
   </div></details></article>`;
 }
 function refresh(){
  if(!ready)return;
  const custom=toMap([...extraWeeks.values()]);
  const rows=free.map(p=>record(p,custom,0));
  const globalWeek=Math.max(sourceInfo.currentPublicWeek,...[...extraWeeks.keys()].map(Number),...rows.map(r=>r.latest?.week??0));
  for(const r of rows)r.lag=r.latest?globalWeek-r.latest.week:999;
  visibleRows=sortRows(rows.filter(eligible));
  const d=qs('fa28Results');d.innerHTML=visibleRows.slice(0,limit).map(drawCard).join('')||'<div class="fa28-empty">No players meet all these filters. Lower the threshold or switch the tackle-rate source. Missing stats are never treated as zero.</div>';
  qs('fa28Summary').textContent=`${visibleRows.length} matches · ${sourceInfo.free} free agents · current public snaps through W${sourceInfo.currentPublicWeek}${globalWeek>sourceInfo.currentPublicWeek?` + private weekly observations through W${globalWeek}`:''}${sourceInfo.stale?' · ROSTER SNAPSHOT STALE':''}.`;
  qs('fa28LoadMore').hidden=visibleRows.length<=limit;
  qs('fa28ImportStatus').textContent=`${extraWeeks.size} owner weekly file(s) ${storageEnabled?'saved privately on this device':'in this tab only (storage disabled)'} · ${custom.unmatched} unmatched rows · ${custom.ambiguous} ambiguous identities omitted.`;
  qs('fa28SourceNote').textContent=`Tackle sources are labeled individually. Public Sleeper weeks: ${sourceInfo.currentPublicWeek>=5?'5–'+sourceInfo.currentPublicWeek:'through '+sourceInfo.currentPublicWeek}; owner FA27 Week 10 is snap-only; recent tackle rate never assumes Week 10 tackles. ${sourceInfo.historical}.`;
 }
 function updateUI(){
  const m=filters.mode;
  document.querySelectorAll('[data-fa28-mode]').forEach(x=>{x.classList.toggle('active',x.dataset.fa28Mode===m);x.setAttribute('aria-pressed',String(x.dataset.fa28Mode===m));});
  qs('fa28TackleControls').hidden=m==='rising'||m==='jump';
  qs('fa28GainBox').hidden=!(m==='rising'||m==='jump');
  qs('fa28ModeNote').textContent=m==='rising'?'Requires 3 consecutive calendar weeks with snaps increasing on BOTH transitions; no missing-week interpolation.':
   m==='jump'?'Compares W10 snap share against season-to-date, which includes W10. NOT a week-over-week trend.':
   m==='tackles'?'Shows players meeting your minimum latest snaps AND tackle rate; choose the rate source below.':'Browse snap workloads across the full available player population.';
 }
 function openFinder(){qs('fa28Backdrop').hidden=false;document.body.classList.add('fa28-open');qs('fa28Dialog').focus();if(ready){limit=30;refresh();}}
 function closeFinder(){qs('fa28Backdrop').hidden=true;document.body.classList.remove('fa28-open');qs('fa28Launcher').focus();}
 function createUI(){
  if(qs('fa28Backdrop'))return;
  const launcher=document.createElement('button');launcher.type='button';launcher.id='fa28Launcher';launcher.textContent='⌕ Find IDP free agents';launcher.setAttribute('aria-haspopup','dialog');
  document.body.appendChild(launcher);
  const host=document.createElement('div');host.id='fa28Backdrop';host.hidden=true;
  host.innerHTML=`<div id="fa28Dialog" role="dialog" aria-modal="true" aria-label="IDP Player Finder" tabindex="-1"><header class="fa28-header"><div><small>LOG · FA28 PLAYER FINDER</small><h2>Find available IDPs</h2><p>One search screen for tackle volume, playing time and consecutive-week trends.</p></div><button type="button" id="fa28Close" aria-label="Close player finder">×</button></header>
   <div class="fa28-content"><div class="fa28-preset" role="group" aria-label="Search mode"><button type="button" data-fa28-mode="tackles">High tackles + snaps</button><button type="button" data-fa28-mode="rising">Rising snaps</button><button type="button" data-fa28-mode="jump">Role jumps</button><button type="button" data-fa28-mode="all">All snaps</button></div>
   <p id="fa28ModeNote" class="fa28-mode-note"></p>
   <div class="fa28-controls"><label>Search player <input id="fa28Search" type="search" placeholder="Name or NFL team"></label><label>Position <select id="fa28Position"><option value="ALL">All IDP</option><option>LB</option><option>DB</option><option>DL</option></select></label><label>Availability <select id="fa28Scope"><option value="free">Free agents only</option><option value="all">All players</option></select></label><label>Min latest snaps <input id="fa28MinSnaps" type="number" value="40" min="0" max="120" step="5"></label>
   <div id="fa28TackleControls" class="fa28-subcontrols"><label>Min tackle rate (%) <input id="fa28MinRate" type="number" value="10" min="0" max="50" step="0.5"></label><label>Tackle-rate source <select id="fa28RateSource"><option value="best">Best available (LB CSV → actuals → history)</option><option value="recent">Observed weekly tackles / snaps</option><option value="ownerLB">Owner LB tackle-rate CSV only</option><option value="historical">Historical usage tackle-rate CSV</option></select></label><label>Min tackle-rate sample snaps <input id="fa28MinSampleSnaps" type="number" value="100" min="0" max="1500" step="10"></label><label>Min observed weeks <input id="fa28MinGames" type="number" value="2" min="1" max="12" step="1"></label></div>
   <div id="fa28GainBox" class="fa28-gain"><label>Min increase (snaps or percentage points) <input id="fa28MinGain" type="number" value="8" min="1" max="100" step="1"></label></div>
   <label>Recency <select id="fa28MaxLag"><option value="0">Latest data week only</option><option value="1" selected>Within 1 week</option><option value="2">Within 2 weeks</option><option value="18">Any week (include stale)</option></select></label><label>Sort <select id="fa28Sort"><option value="rate">Highest tackle rate</option><option value="snaps">Most latest snaps</option><option value="gain">Largest 3-week gain</option><option value="young">Youngest</option><option value="week">Most recent</option></select></label><label class="fa28-check"><input id="fa28IncludeInjured" type="checkbox"> Include IR / Out / Inactive</label></div>
   <section class="fa28-import"><details><summary>Import more weekly snap-rate CSVs</summary><p>Optional: import future weekly Defensive Players Week NN Snap Rates CSVs. Each week is retained privately on this device. Only observed defensive snaps are used; missing weeks are never filled with zero.</p><div class="fa28-import-controls"><label>Weekly CSVs <input id="fa28Files" type="file" accept=".csv,text/csv" multiple></label><label>Week if filename has no number <input id="fa28ImportWeek" type="number" min="1" max="18" value="10"></label><button type="button" id="fa28Import">Import selected week(s)</button></div><p id="fa28ImportStatus"></p></details></section>
   <p id="fa28Summary" role="status">Loading free-agent and weekly evidence…</p><p id="fa28SourceNote" class="fa28-source"></p><div id="fa28Results" class="fa28-results"></div><button id="fa28LoadMore" type="button" hidden>Show 30 more players</button><div class="fa28-footer"><button type="button" id="fa28Export">Export filtered CSV to my device</button><span>Evidence and filters do not modify FV, MV, lineup rankings or FA26 frozen snapshots.</span></div></div></div>`;
  document.body.appendChild(host);
  launcher.addEventListener('click',openFinder);qs('fa28Close').addEventListener('click',closeFinder);
  host.addEventListener('click',e=>{if(e.target===host)closeFinder();});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!host.hidden)closeFinder();});
  document.querySelectorAll('[data-fa28-mode]').forEach(b=>b.addEventListener('click',()=>{
   filters.mode=b.dataset.fa28Mode;filters.sort=filters.mode==='rising'?'gain':filters.mode==='jump'?'snaps':'rate';qs('fa28Sort').value=filters.sort;
   updateUI();limit=30;refresh();
  }));
  const defs={fa28Search:['search','string'],fa28Position:['position','string'],fa28Scope:['scope','string'],fa28MinSnaps:['minSnaps',0,120],
   fa28MinRate:['minRate',0,50],fa28RateSource:['rateSource','string'],fa28MinSampleSnaps:['minSampleSnaps',0,1500],
   fa28MinGames:['minGames',1,12],fa28MinGain:['minGain',1,100],fa28MaxLag:['maxLag',0,18],fa28Sort:['sort','string'],fa28IncludeInjured:['includeInjured','boolean']};
  for(const [id,[prop,a,b]] of Object.entries(defs))qs(id).addEventListener(id==='fa28Search'?'input':'change',()=>{
   filters[prop]=a==='boolean'?qs(id).checked:a==='string'?qs(id).value:clamp(qs(id).value,a,b);limit=30;refresh();
  });
  qs('fa28LoadMore').addEventListener('click',()=>{limit+=30;refresh();});
  qs('fa28Import').addEventListener('click',async()=>{
   const btn=qs('fa28Import');btn.disabled=true;
   try{const files=[...qs('fa28Files').files],docs=await importWeekly(files);const next=new Map(extraWeeks);
    for(const doc of docs)next.set(doc.week,doc);const obj={schema_version:1,classification:'PRIVATE_OWNER_WEEKLY_IDP_SNAP_CSV_LOCAL_ONLY',season:2026,
     docs:[...next.values()]};
    if(storageEnabled){try{await dbSave(obj);}catch(e){storageEnabled=false;}}
    extraWeeks=next;qs('fa28Files').value='';limit=30;refresh();
   }catch(e){qs('fa28ImportStatus').textContent='Import rejected: '+e.message;}finally{btn.disabled=false;}
  });
  qs('fa28Export').addEventListener('click',()=>{
   const h=['sleeper_id','player','team','position','availability','latest_week','latest_snaps','tackle_rate_pct','tackle_rate_source','measured_sample_snaps','three_week_gain','weekly_snaps'];
   const safe=x=>'"'+String(x??'').replace(/"/g,'""')+'"';
   const lines=[h.join(','),...visibleRows.map(r=>[r.id,r.name,r.team,r.group,r.owner,r.latest?.week,r.latest?.snaps,
    r.rates.chosen?.rate?.toFixed(2),r.rates.chosen?.source,r.rates.chosen?.sampleSnaps,r.trend.gain3,
    r.history.map(x=>`W${x.week}:${x.snaps}`).join(' ')].map(safe).join(','))];
   const blob=new Blob([lines.join('\r\n')+'\r\n'],{type:'text/csv'}),url=URL.createObjectURL(blob),a=document.createElement('a');
   a.href=url;a.download=`LOG-FA28-private-idp-finder-${filters.mode}-2026.csv`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
  });
  updateUI();
 }
 async function init(){createUI();
  try{await sources();let saved=null;
   try{saved=await dbRead();}catch(e){storageEnabled=false;}
   if(saved){
    if(saved.schema_version!==1||saved.classification!=='PRIVATE_OWNER_WEEKLY_IDP_SNAP_CSV_LOCAL_ONLY'||saved.season!==2026||!Array.isArray(saved.docs)||saved.docs.length>18)throw Error('Unsupported private week cache');
    extraWeeks=new Map(saved.docs.map(x=>[x.week,x]));
   }
   ready=true;refresh();
  }catch(e){qs('fa28Summary').textContent='Player Finder data unavailable: '+e.message;qs('fa28Results').textContent='Check the most recent LOG data refresh. No partial or guessed availability results shown.';}
 }
 window.addEventListener('log-idp-role-updated',()=>{if(ready)refresh();});
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
