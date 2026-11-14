/* LOG A-FA24R1: source-aware IDP waiver target research.
 * The candidate universe is the CURRENT LOG Sleeper free-agent pool, not a 4for4 export.
 * Private 4for4 inputs remain in browser RAM; private weekly Macri/Woellert ranks
 * and matchup context are read-only from the existing same-origin private stores.
 * No paid data is sent to any endpoint, stored by this module, or published.
 * Descriptive evidence tiers are NOT a calibrated score, FV, or roster decision.
 */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const ROOT = 'https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/main/';
  const GROUPS = ['DL','LB','DB'];
  const SUB = ['EDGE','DT','LB','S','CB'];
  const TOP = {EDGE:24,DT:12,LB:24,S:24,CB:12}; // Explicit screening bands, not source probabilities
  const FF_TOP = {DL:36,LB:24,DB:36}; // Positional screening bands in 4for4 original order
  const TEAM_ALIAS = {JAC:'JAX',LA:'LAR',STL:'LAR',SD:'LAC',OAK:'LV',WSH:'WAS'};
  const norm = v => String(v ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/g,'')
    .toLowerCase().replace(/\b(jr|sr|ii|iii|iv)\b\.?/g,'').replace(/[^a-z0-9]/g,'');
  const team = v => TEAM_ALIAS[String(v ?? '').trim().toUpperCase()] || String(v ?? '').trim().toUpperCase();
  const safe = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
  const finite = x => typeof x==='number' && Number.isFinite(x);
  const number = (x,d=1) => finite(x) ? x.toFixed(d) : '—';
  const nval = x => {const v=Number(String(x??'').replace(/,/g,''));return String(x??'').trim()!==''&&Number.isFinite(v)?v:null;};
  const id = v => String(v??'');
  const pos = p => ['DL','LB','DB'].includes(p?.pos)?p.pos:null;
  function subpos(p) {
    const raw=String(p?.raw_position||'').toUpperCase();
    if(p.pos==='LB') return 'LB';
    if(p.pos==='DL') return ['DE','ED','EDGE','OLB'].includes(raw)?'EDGE':['DT','DI','NT'].includes(raw)?'DT':null;
    if(p.pos==='DB') return ['S','SS','FS'].includes(raw)?'S':raw==='CB'?'CB':null;
    return null;
  }
  const key=(name,g)=>norm(name)+'|'+g;
  const matchKey=(name,t,g)=>key(name,g)+'|'+team(t);
  const query=(file)=>ROOT+file+'?t='+Date.now();
  async function publicDoc(path) {
    const r=await fetch(query(path),{cache:'no-store'});
    if(!r.ok)throw Error('HTTP '+r.status+' · '+path);
    return r.json();
  }
  async function readExistingDb(dbName,storeName) {
    if(!window.indexedDB)return [];
    // A missing database is NOT created: abort the upgrade before any write.
    return await new Promise((resolve,reject)=>{
      const req=indexedDB.open(dbName);
      req.onupgradeneeded=()=>{req.transaction.abort();};
      req.onerror=()=>{
        if(req.error?.name==='AbortError') resolve([]); else reject(req.error||Error('Private DB unavailable'));
      };
      req.onsuccess=()=>{
        const db=req.result;
        if(!db.objectStoreNames.contains(storeName)){db.close();resolve([]);return;}
        const tx=db.transaction(storeName,'readonly');
        const get=tx.objectStore(storeName).getAll();
        get.onsuccess=()=>resolve(get.result||[]);
        get.onerror=()=>reject(get.error||Error('Private DB read failed'));
        tx.oncomplete=()=>db.close();
        tx.onerror=()=>{db.close();reject(tx.error||Error('Private DB transaction failed'));};
      };
    });
  }
  function csvRows(text) {
    const rows=[];let row=[],value='',quoted=false;
    for(let i=0;i<text.length;i++) {
      const ch=text[i];
      if(ch==='"'){if(quoted&&text[i+1]==='"'){value+='"';i++;}else quoted=!quoted;}
      else if(ch===','&&!quoted){row.push(value);value='';}
      else if((ch==='\n'||ch==='\r')&&!quoted){if(ch==='\r'&&text[i+1]==='\n')i++;row.push(value);value='';if(row.some(v=>v.trim()))rows.push(row);row=[];}
      else value+=ch;
    }
    if(quoted)throw Error('Unmatched CSV quote');row.push(value);
    if(row.some(v=>v.trim()))rows.push(row);
    return rows;
  }
  function load4for4(text) {
    const rows=csvRows(text.replace(/^\uFEFF/,''));
    if(!rows.length)throw Error('Empty CSV');
    const h=rows.shift().map(x=>x.toLowerCase().replace(/[^a-z0-9]/g,''));
    const col=(...names)=>h.findIndex(x=>names.includes(x));
    const nm=col('player','playername','name'),tm=col('team','tm'),gr=col('grouprank'),pr=col('positionrank'),pts=col('ffpts','fpts','projectedpoints','fantasypoints'),opp=col('opp','opponent'),vor=col('vor','valueoverreplacement');
    if([nm,tm,gr,pts].some(x=>x<0))throw Error('Expected Player, Team, Group-Rank, FF Pts');
    if(col('bye','byeweek')>=0)throw Error('Season-long export rejected; weekly only');
    const result=[];for(const r of rows){
      const gm=/^(DL|LB|DB)-(\d+)$/i.exec(String(r[gr]||''));const points=nval(r[pts]);
      if(!gm||!r[nm]||!r[tm]||points===null||points<0||points>100)continue;
      const group=gm[1].toUpperCase(),groupRank=Number(gm[2]);
      const posm=pr>=0?/^(DE|DT|LB|CB|S)-(\d+)$/i.exec(String(r[pr]||'')):null;
      const sub=posm?({DE:'EDGE',DT:'DT',LB:'LB',S:'S',CB:'CB'})[posm[1].toUpperCase()]:null;
      const opponent=opp>=0?String(r[opp]||'').replace(/^@/,'').trim().toUpperCase():'';
      result.push({name:r[nm].trim(),team:team(r[tm]),group,groupRank,points,vor:vor>=0?nval(r[vor]):null,sub,
        opponent:/^[A-Z]{2,3}$/.test(opponent)?team(opponent):null});
    }
    return result;
  }
  function getPrivateWeek(docs,week) {
    const valid=docs.filter(d=>d&&d.schema_version===1 &&
      d.classification==='PRIVATE_OWNER_SUPPLIED_WEEKLY_IDP_START_SIT_NOT_FOR_PUBLIC_REPO' &&
      d.source_scope==='WEEKLY_ONLY_NOT_ROS'&&d.season===2026&&d.week===week&&
      Array.isArray(d.records)&&d.records.length>=2&&d.records.length<=500);
    if(valid.length!==1)return null; // Fail closed if ambiguous or stale
    const doc=valid[0],seen=new Set();
    for(const r of doc.records){
      if(!r||!SUB.includes(r.group)||typeof r.name!=='string'||!r.name.trim()||
        !r.rankings||![r.rankings.idp_show,r.rankings.woellert].every(v=>v===null||(Number.isInteger(v)&&v>=1&&v<=200))||
        (r.rankings.idp_show===null&&r.rankings.woellert===null))return null;
      const k=key(r.name,r.group);if(seen.has(k))return null;seen.add(k);
    }
    return doc;
  }
  function getPrivateMatchups(docs,week) {
    const valid=docs.filter(d=>d&&d.schema_version===1&&d.season===2026&&d.analysis_week===week&&
      d.classification==='PRIVATE_USER_PROVIDED_MATCHUP_REFERENCE_NOT_FOR_PUBLIC_GITHUB'&&
      d.private===true&&d.do_not_publish_to_github===true&&
      d.derived_numeric_adjustment_authorized===false&&
      d.teams&&Object.keys(d.teams).length===32&&d.league_averages);
    return valid.length===1?valid[0]:null;
  }
  function trendMap(doc,week) {
    const ret=new Map();
    if(doc?.schema_version!==1||doc.classification!=='PUBLIC_SLEEPER_WEEKLY_IDP_EVIDENCE_NOT_PROJECTION_OR_BREAKOUT'||
       doc.season!==2026||!Array.isArray(doc.players)||!Number.isInteger(doc.last_completed_week))return ret;
    const seen=new Set();
    for(const p of doc.players){
      const sid=id(p.sleeper_id);
      if(!/^\d+$/.test(sid)||seen.has(sid)||!GROUPS.includes(p.position)||!Array.isArray(p.observations))continue;
      seen.add(sid);
      const obs=p.observations.filter(o=>Number.isInteger(o.week)&&o.week<week&&o.week>=5&&o.week<=18&&
        (o.defensive_snaps===null||(finite(o.defensive_snaps)&&o.defensive_snaps>=0&&o.defensive_snaps<=150)))
        .sort((a,b)=>a.week-b.week);
      const last=obs.at(-1);if(!last)continue;
      // We only claim a change from three consecutive PRE-WEEK observations.
      const prev=obs.slice(-3);const contiguous=prev.length===3&&prev[0].week===prev[1].week-1&&prev[1].week===prev[2].week-1&&prev.every(o=>finite(o.defensive_snaps));
      const delta=contiguous?prev[2].defensive_snaps-(prev[0].defensive_snaps+prev[1].defensive_snaps)/2:null;
      ret.set(sid,{team:team(p.team),group:p.position,week:last.week,snaps:last.defensive_snaps,delta});
    }
    return ret;
  }
  function usageMap(doc) {
    const ret=new Map();
    if(doc?.schema_version!==1||doc.policy!=='READ_ONLY_RESEARCH_NOT_FV_OR_PROJECTION'||
       !Array.isArray(doc.players))return ret;
    for(const p of doc.players){
      const sid=id(p.sleeper_id);if(!/^\d+$/.test(sid))continue;
      if(ret.has(sid)){ret.set(sid,null);continue;}
      ret.set(sid,p);
    }
    return ret;
  }
  function buildWeeklyIndex(doc,candidates) {
    const ret=new Map();if(!doc)return ret;
    const byName=new Map();for(const p of candidates){const sub=subpos(p);if(!sub)continue;
      const k=key(p.name,sub);const array=byName.get(k)||[];array.push(p);byName.set(k,array);
    }
    for(const r of doc.records){
      const options=byName.get(key(r.name,r.group))||[];
      // Private rank files may have only name+subposition. Do not guess duplicates.
      const hintedTeam=r.projection?.team?team(r.projection.team):null;
      const eligible=hintedTeam?options.filter(x=>team(x.team)===hintedTeam):options;
      const p=eligible.length===1?eligible[0]:null;
      if(!p||ret.has(id(p.player_id)))continue;
      ret.set(id(p.player_id),r);
    }
    return ret;
  }
  function match4for4(rows,candidates) {
    const byKey=new Map();for(const p of candidates){const k=matchKey(p.name,p.team,p.pos);const xs=byKey.get(k)||[];xs.push(p);byKey.set(k,xs);}
    const res=new Map(),used=new Set();let unmatched=0,duplicates=0;
    for(const r of rows){const k=matchKey(r.name,r.team,r.group);const options=byKey.get(k)||[];
      if(options.length!==1){unmatched++;continue;}
      const p=options[0],pid=id(p.player_id);
      if(r.sub && subpos(p) && r.sub!==subpos(p)){unmatched++;continue;}
      if(used.has(pid)){duplicates++;res.delete(pid);continue;}
      used.add(pid);res.set(pid,r);
    }
    return {data:res,unmatched,duplicates};
  }
  function utilityMap(doc,faDoc) {
    const m=new Map();
    if(doc?.schema_version!==1||doc.policy_id!=='phase3-selected-15pct-cap040'||
      doc.source?.league_id!==faDoc.league_id||doc.source?.free_agents_synced_at!==faDoc.synced_at||
      doc.source?.free_agents_count!==faDoc.count||!Array.isArray(doc.players))return m;
    for(const p of doc.players){if(!/^\d+$/.test(id(p.player_id))||!GROUPS.includes(p.pos)||!Number.isInteger(p.priority_rank))continue;
      m.set(id(p.player_id)+'|'+p.pos,p.priority_rank);
    }
    return m;
  }
  function rosMap(doc) {
    const m=new Map();if(doc?.rank_policy!=='FROZEN_SCREENSHOT_DISPLAY_ONLY'||!Array.isArray(doc.records))return m;
    for(const r of doc.records){if(r.sleeper_id&&SUB.includes(r.group)&&Number.isInteger(r.rank)){
      const k=id(r.sleeper_id);if(m.has(k))m.set(k,null);else m.set(k,r);
    }}return m;
  }
  function roleOf(p){return subpos(p)||'unknown subposition';}
  const isTop=(r,s)=>Number.isInteger(r)&&!!s&&r<=TOP[s];
  const isFFTop=r=>!!r&&Number.isInteger(r.groupRank)&&r.groupRank<=FF_TOP[r.group];
  function context(row){
    const weekly=row.expert,sub=roleOf(row),a=weekly?.rankings?.idp_show,b=weekly?.rankings?.woellert;
    const expertTop=(isTop(a,sub)?1:0)+(isTop(b,sub)?1:0);
    const fourTop=isFFTop(row.four)?1:0;
    const snapRise=finite(row.weekly?.delta)&&row.weekly.delta>=12&&row.weekly.week===activeWeek-1&&finite(row.weekly.snaps)&&row.weekly.snaps>=35;
    return {top:expertTop+fourTop,expertTop,fourTop,snapRise};
  }
  let activeWeek=10;
  function tier(row,horizon) {
    const sig=context(row);
    if(horizon==='week'){
      if(/^(IR|OUT|PUP|SUSPENDED)\b/i.test(String(row.injury||'')))return ['Injury/status hold',6];
      if(sig.top>=2)return ['Independent weekly agreement',0];
      if(sig.top>=1&&(finite(row.weekly?.snaps)&&row.weekly.snaps>=35))return ['Weekly option + snaps',1];
      if(sig.snapRise)return ['Rising weekly opportunity',2];
      if(sig.top>=1)return ['Weekly expert/projection signal',3];
      if(row.four||row.expert||row.weekly||row.usage||row.ros||row.utility!==null)return ['Monitor / limited evidence',4];
      return ['No confirmed signal',5];
    }
    if(sig.snapRise&&row.age<=25)return ['Young role expanding',0];
    if(row.ros&&row.age<=25)return ['Young, ROS-ranked',1];
    if(row.age<=25&&finite(row.usage?.snaps_per_game)&&row.usage.snaps_per_game>=40)return ['Young, season usage',2];
    if(row.age<=25&&(row.four||row.expert||row.weekly))return ['Young, weekly evidence',3];
    return ['Speculative research',4];
  }
  function joinCandidates(faDoc,documents,privateDocs,fourRows,week) {
    const candidates=faDoc.free_agents.filter(p=>pos(p)&&/^\d+$/.test(id(p.player_id)));
    const ros=rosMap(documents.ros),utility=utilityMap(documents.utility,faDoc);
    const usage=usageMap(documents.usage),weekly=trendMap(documents.weekly,week);
    const expertDoc=getPrivateWeek(privateDocs.ranks,week),matchup=getPrivateMatchups(privateDocs.matchups,week);
    const experts=buildWeeklyIndex(expertDoc,candidates),four=match4for4(fourRows,candidates);
    const now=Date.now()/1000;
    const fresh=finite(faDoc.synced_at)?Math.max(0,(now-faDoc.synced_at)/3600):null;
    const schedule=new Map();
    if(expertDoc){for(const r of expertDoc.records){const t=team(r.projection?.team),o=team(r.projection?.opponent);
      if(t&&o&&t!==o){const v=schedule.get(t);schedule.set(t,v===undefined?o:v===o?o:null);}
    }}
    const rows=candidates.map(p=>{
      const sid=id(p.player_id),r=ros.get(sid),u=usage.get(sid),w=weekly.get(sid),f=four.data.get(sid)||null,e=experts.get(sid)||null;
      const sub=subpos(p);const hasMatchingRos=r && r.team===team(p.team)&&r.group===sub;
      const hasMatchingUsage=u && team(u.team_at_source)===team(p.team) &&
        ((u.position==='ED'&&sub==='EDGE')||(u.position==='DI'&&sub==='DT')||u.position===sub);
      const hasMatchingWeek=w&&team(w.team)===team(p.team)&&w.group===p.pos;
      const o=team(f?.opponent||e?.projection?.opponent||schedule.get(team(p.team))||'');
      const validMatchup=matchup&&o&&o!==team(p.team)&&matchup.teams?.[o];
      return {id:sid,name:p.name,team:team(p.team),group:p.pos,raw_position:p.raw_position,age:Number.isInteger(p.age)?p.age:null,
        injury:p.injury_status||null,ros:hasMatchingRos?r:null,utility:utility.get(sid+'|'+p.pos)??null,
        usage:hasMatchingUsage?u:null,weekly:hasMatchingWeek?w:null,
        expert:e,four:f,opponent:o||null,matchup:validMatchup?matchup:null};
    });
    return {rows,expertDoc,matchupDoc:matchup,four,...{fresh},unmatched:four.unmatched,duplicates:four.duplicates,
      sourceStatus:{ros:ros.size,utility:utility.size,usage:usage.size,weekly:weekly.size,expert:experts.size,four:four.data.size,matchup:!!matchup}};
  }
  function viewDescription(row,horizon) {
    const a=row.expert?.rankings?.idp_show,b=row.expert?.rankings?.woellert,sub=roleOf(row),rank=row.ros;
    const proof=[];
    if(row.four) proof.push(`4for4 W${activeWeek}: ${number(row.four.points)} pts${finite(row.four.vor)?' · VOR '+number(row.four.vor):''} · ${row.group} #${row.four.groupRank}${isFFTop(row.four)?' (weekly screening band)':''}`);
    else proof.push('4for4: no matching private weekly projection');
    if(row.expert){
      proof.push(`Macri weekly: ${Number.isInteger(a)?sub+' #'+a:'not ranked'} · Woellert weekly: ${Number.isInteger(b)?sub+' #'+b:'not ranked'}`);
      const proj=row.expert.projection;
      if(finite(proj?.log_linear_base_points))proof.push(`Woellert/LOG weekly base: ${number(proj.log_linear_base_points)} pts · projected defensive snaps: ${number(proj.projected_defensive_snaps,0)} (independent projection, not averaged with 4for4)`);
    }
    else proof.push('Weekly expert consensus: not loaded or not matched for W'+activeWeek);
    if(Number.isInteger(a)&&Number.isInteger(b)&&Math.abs(a-b)>=15)proof.push(`Weekly expert disagreement: Macri #${a} versus Woellert #${b} (same original subposition; no averaging)`);
    if(row.four&&isFFTop(row.four)&&row.expert&&!isTop(a,sub)&&!isTop(b,sub))proof.push('4for4 weekly signal is stronger than the available expert rank bands; investigate role and matchup');
    if(!row.four&&(isTop(a,sub)||isTop(b,sub)))proof.push('Weekly expert signal without a matching 4for4 row: deliberately retained');
    if(row.weekly)proof.push(`Sleeper W${row.weekly.week}: ${finite(row.weekly.snaps)?row.weekly.snaps:'unknown'} snaps`+
      (finite(row.weekly.delta)?` · ${row.weekly.delta>=0?'+':''}${number(row.weekly.delta)} vs previous two`:' · 3-week trend unavailable'));
    if(row.usage)proof.push(`Season research: ${number(row.usage.snaps_per_game)} snaps/game · ${number(row.usage.tackle_rate_pct)}% tackle rate (week coverage unspecified)`);
    if(rank)proof.push(`Macri ROS ${rank.group} #${rank.rank} · frozen Nov 7`);
    if(row.utility!==null)proof.push(`LOG Utility position priority #${row.utility} (not fantasy points)`);
    if(row.injury)proof.push(`Sleeper injury/status: ${row.injury}`);
    if(horizon==='dynasty'&&row.age!==null)proof.push(`Age ${row.age}; age is a scouting filter, not proof of breakout`);
    if(row.matchup){
      const subpos=roleOf(row),role=subpos==='CB'?'OUTSIDE_CB':subpos;
      const opponent=row.matchup.teams[row.opponent],r=opponent?.tackle_rate_allowed_pct?.[role],avg=row.matchup.league_averages?.tackle_rate_allowed_pct?.[role];
      if(finite(r)&&finite(avg)&&avg>0){const diff=(r/avg-1)*100;
        proof.push(`Woellert W${activeWeek} vs ${row.opponent}: ${number(diff,0)}% relative tackle-rate allowance vs league average (${role}; context only)`);
      }
    }
    return proof;
  }
  function prepare() {
    const target=$('fa-ws-idp-panel');if(!target||$('fa24Lab'))return null;
    const host=document.createElement('section');host.className='fa24';host.id='fa24Lab';
    host.setAttribute('aria-label','Integrated IDP waiver-target research');
    host.innerHTML=`<header class="fa24-head"><div><div class="fa24-kicker">FA24 · MULTI-SOURCE RESEARCH</div><h3>Waiver target intelligence</h3><p>Start with every confirmed LOG free agent, then compare independent weekly projections, expert ranks, snaps, ROS and utility. No blended score.</p></div><span class="fa24-private">PRIVATE SOURCES STAY LOCAL</span></header>
    <div class="fa24-toolbar"><label>Analysis week<input type="number" min="10" max="18" id="fa24Week" value="10"></label>
    <label>Position<select id="fa24Group"><option value="ALL">All IDP</option><option value="DL">DL</option><option value="LB">LB</option><option value="DB">DB</option></select></label>
    <label>Search<input id="fa24Search" type="search" placeholder="Player or NFL team"></label>
    <button type="button" id="fa24Refresh">Refresh all sources</button></div>
    <div class="fa24-horizons" role="tablist" aria-label="Integrated waiver research horizon"><button type="button" id="fa24Win" role="tab" aria-selected="true">Win This Week</button><button type="button" id="fa24Dynasty" role="tab" aria-selected="false">Dynasty Upside</button></div>
    <div id="fa24Pulse" class="fa24-pulse" role="status" aria-live="polite">Checking available evidence…</div>
    <details class="fa24-provenance"><summary>Source coverage & privacy details</summary>
    <div id="fa24Sources" class="fa24-sources">Loading public data and checking private sources…</div>
    <p class="fa24-privacy">Private weekly Macri/Woellert ranks and matchup tables are read from your existing Start/Sit browser cache for the exact selected week. The optional 4for4 file is read from the importer below, in memory only. Missing sources are labeled—not scored as zero.</p></details>
    <div class="fa24-options"><label><input type="checkbox" id="fa24AllAges"> Include ages 26+ in dynasty mode</label><label><input type="checkbox" id="fa24ShowAll"> Show low-evidence players</label></div>
    <p id="fa24Count" class="fa24-summary"></p><div id="fa24List" class="fa24-list"></div>
    <p class="fa24-disclaimer">Screening bands: Macri/Woellert top 24 EDGE, LB, S or top 12 DT, CB; 4for4 top 36 DL/DB or 24 LB. These are <strong>uncalibrated screening rules</strong>, not consensus probabilities or validated pickup rankings. Original subposition ranks are never averaged.</p>`;
    const first=target.querySelector('.fa-ws-intro');if(first)first.insertAdjacentElement('afterend',host);else target.prepend(host);
    return host;
  }
  function setup() {
    if(!prepare())return;
    let cached=null,sourceDocs=null,privateDocs=null,results=null,horizon='week',epoch=0,viewCount=15;
    const status=$('fa24Sources'),count=$('fa24Count'),out=$('fa24List');
    const selectedWeek=()=>Number($('fa24Week').value);
    function select(next){horizon=next;$('fa24Win').setAttribute('aria-selected',String(next==='week'));$('fa24Dynasty').setAttribute('aria-selected',String(next==='dynasty'));viewCount=15;render();}
    $('fa24Win').addEventListener('click',()=>select('week'));
    $('fa24Dynasty').addEventListener('click',()=>select('dynasty'));
    function render(){
      if(!results)return;
      const group=$('fa24Group').value,q=$('fa24Search').value.trim().toLowerCase(),
        showAll=$('fa24ShowAll').checked,allAges=$('fa24AllAges').checked;
      let rows=results.rows.filter(p=>(group==='ALL'||p.group===group)&&(!q||(p.name+' '+p.team).toLowerCase().includes(q))&&
        (horizon==='week'||allAges||(p.age!==null&&p.age<=25)));
      rows=rows.map(p=>({...p,tier:tier(p,horizon)}));
      const meaningful=p=>p.tier[1]<(horizon==='week'?5:4);
      if(!showAll && !q)rows=rows.filter(meaningful);
      rows.sort((a,b)=>{
        const tierOrder=a.tier[1]-b.tier[1];if(tierOrder)return tierOrder;
        if(a.group!==b.group)return GROUPS.indexOf(a.group)-GROUPS.indexOf(b.group);
        if(horizon==='week')return (b.four?.points??-1)-(a.four?.points??-1)||
          (a.utility??99999)-(b.utility??99999)||a.name.localeCompare(b.name);
        return (finite(b.weekly?.delta)?b.weekly.delta:-10000)-(finite(a.weekly?.delta)?a.weekly.delta:-10000)||
          (a.ros?.rank??999)-(b.ros?.rank??999)||a.name.localeCompare(b.name);
      });
      if(group==='ALL'){
        // Rotate DL/LB/DB within each evidence tier so one position does not crowd out the others.
        const balanced=[];
        for(const level of [0,1,2,3,4,5,6]){const byGroup=Object.fromEntries(GROUPS.map(g=>[g,rows.filter(r=>r.group===g&&r.tier[1]===level)]));
          while(GROUPS.some(g=>byGroup[g].length)){for(const g of GROUPS){if(byGroup[g].length)balanced.push(byGroup[g].shift());}}
        }
        rows=balanced;
      }
      const visible=rows.slice(0,viewCount);
      count.textContent=`${rows.length} matching research candidates · ${results.rows.length} confirmed IDP free agents in the LOG snapshot. ${rows.length>viewCount?'Showing first '+viewCount+'.':''}`;
      const items=visible.map(p=>{
        const injury=p.injury?` · ${safe(p.injury)}`:'';
        const bullets=viewDescription(p,horizon).map(s=>`<li>${safe(s)}</li>`).join('');
        return `<article class="fa24-card"><div class="fa24-cardtop"><div><strong>${safe(p.name)}</strong><small>${safe(p.team)} · ${safe(p.group)}${p.raw_position?' / '+safe(p.raw_position):''} · Age ${p.age??'unknown'}${injury}</small></div><span class="fa24-tier fa24-tier-${p.tier[1]}">${safe(p.tier[0])}</span></div><ul>${bullets}</ul><p class="fa24-limits">Evidence screening, not a transaction recommendation. Validate current depth-chart role, injury news, and your league's scoring before adding.</p></article>`;
      }).join('');
      out.innerHTML=items||'<p class="fa24-empty">No candidates match these settings. Try another position, the broader view, or Show low-evidence players.</p>';
      if(rows.length>visible.length){const b=document.createElement('button');b.type='button';b.className='fa24-more';b.textContent=`Show more (${rows.length-visible.length} remaining)`;b.addEventListener('click',()=>{viewCount+=20;render();});out.appendChild(b);}
    }
    async function getPrivateDocs(){const [r,m]=await Promise.allSettled([
      readExistingDb('LOG_Private_StartSit_Weekly_2026_v1','snapshots'),
      readExistingDb('LOG_Private_Woellert_Matchups_v1','weekly')]);
      return {ranks:r.status==='fulfilled'?r.value:[],matchups:m.status==='fulfilled'?m.value:[]};}
    async function getPublicDocs(){const names={fa:'data/free_agents.json',utility:'data/free_agent_utility_v1.json',ros:'data/idp_ros_2026_w09.json',usage:'data/idp_usage_2026_season.json',weekly:'data/idp_weekly_2026_public.json'};
      const entries=await Promise.all(Object.entries(names).map(async([key,path])=>{try{return [key,await publicDoc(path),null];}catch(e){return [key,null,String(e.message||e)];}}));
      const docs=Object.fromEntries(entries.map(([k,v])=>[k,v]));
      if(!docs.fa||!Array.isArray(docs.fa.free_agents)||docs.fa.count!==docs.fa.free_agents.length||!docs.fa.league_id){throw Error('No verified LOG free-agent pool. Recommendations disabled.');}
      return docs;}
    async function read4for4(){
      const input=$('fa22Files'),scoring=$('fa22Scoring');
      if(!input?.files?.length)return {rows:[],status:'Not loaded'};
      if(!scoring?.value)return {rows:[],status:'Select 4for4 scoring setting'};
      const files=[...input.files];if(files.length>4||files.some(f=>f.size<30||f.size>1500000||!f.name.toLowerCase().endsWith('.csv')))return {rows:[],status:'Rejected invalid CSV selection'};
      try{const rows=[];for(const f of files){
        const w=/\bweek[-_ ]?(\d{1,2})\b/i.exec(f.name);
        if(w&&Number(w[1])!==activeWeek)throw Error('CSV filename shows Week '+w[1]+' but selected Week '+activeWeek);
        rows.push(...load4for4(await f.text()));
      }return {rows,status:`${rows.length} weekly rows loaded locally (${scoring.value==='log'?'LOG selected':'other scoring'})`};}
      catch(e){return {rows:[],status:'4for4 CSV invalid: '+String(e.message||e)};}
    }
    async function refresh(){
      const run=++epoch;results=null;out.replaceChildren();
      activeWeek=selectedWeek();if(!Number.isInteger(activeWeek)||activeWeek<10||activeWeek>18){status.textContent='FA24 has no pre-Week-10 frozen availability/role baseline. Choose 2026 Week 10–18; historical backtesting needs separately frozen snapshots.';return;}
      status.textContent='Reading public LOG evidence, existing private sources, and optional 4for4 CSV…';$('fa24Pulse').textContent='Checking source coverage…';
      try{
        const [pvt,pub,four]=await Promise.all([getPrivateDocs(),getPublicDocs(),read4for4()]);if(run!==epoch)return;
        privateDocs=pvt;sourceDocs=pub;
        results=joinCandidates(pub.fa,pub,pvt,four.rows,activeWeek);
        const x=results.sourceStatus,age=results.fresh;
        const sourceText=[`Sleeper ${results.rows.length} IDPs (${age===null?'age unknown':number(age,1)+'h old'}${age!==null&&age>72?', STALE':''})`,
          `4for4 ${x.four} matches (${safe(four.status)})`,
          `Macri + Woellert weekly ${x.expert} matches (${results.expertDoc?'same W'+activeWeek:'unavailable or other week'})`,
          `Macri ROS ${x.ros} IDs`, `LOG Utility ${x.utility} IDs`,
          `Season usage ${x.usage} IDs`, `Weekly snap data ${x.weekly} IDs`,
          `Woellert matchups ${x.matchup?'same-week available':'unavailable or other week'}`];
        status.innerHTML=sourceText.map(t=>`<span>${safe(t)}</span>`).join('');
        $('fa24Pulse').textContent=`Sleeper ${results.rows.length} available IDPs · 4for4 ${x.four} · Weekly experts ${x.expert} · Snap evidence ${x.weekly}`+(age!==null&&age>72?' · STALE ROSTER':'');
        count.textContent=`Note: ${results.unmatched} CSV records not confirmed available; ${results.duplicates} ambiguous duplicates. Missing sources never receive zero scores.`;
        viewCount=15;render();
      }catch(e){status.textContent='FA24 paused: '+String(e.message||e);$('fa24Pulse').textContent='Research unavailable';count.textContent='No candidate recommendations shown.';}
    }
    $('fa24Refresh').addEventListener('click',refresh);
    for(const name of ['fa24Group','fa24Search','fa24AllAges','fa24ShowAll'])$(name).addEventListener(name==='fa24Search'?'input':'change',()=>{viewCount=15;render();});
    $('fa24Week').addEventListener('change',()=>{results=null;status.textContent='Week changed. Refresh sources to enforce same-week imports.';count.textContent='';out.replaceChildren();});
    const button=$('fa22Import');if(button)button.addEventListener('click',()=>{window.setTimeout(refresh,25);});
    for(const fid of ['fa22Scoring','fa22Files'])$(fid)?.addEventListener('change',()=>{results=null;status.textContent='Private CSV selection changed. Refresh to avoid stale rankings.';count.textContent='';out.replaceChildren();});
    $('fa22Week')?.addEventListener('change',()=>{const n=Number($('fa22Week').value);
      if(Number.isInteger(n)&&n>=10&&n<=18)$('fa24Week').value=String(n);
      results=null;out.replaceChildren();status.textContent='4for4 week changed. Refresh the integrated evidence for this week.';count.textContent='';});
    // Internal test seam carries only current in-memory computed facts, not subscriber data.
    refresh();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup,{once:true});else setup();
})();
