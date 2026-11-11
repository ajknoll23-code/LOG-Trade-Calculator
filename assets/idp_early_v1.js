/* LOG IDP Early Opportunity V1 — browser-local, research-only.
   Subscriber data is selected from local files and NEVER sent, persisted,
   posted, or committed by this module. This code does not access valuation APIs. */
(() => {
  'use strict';
  const root=document.getElementById('idpePanel');
  if(!root)return;
  const $=id=>document.getElementById(id);
  const ui={status:$('idpeStatus'),list:$('idpeItems'),count:$('idpeCount'),
    file:$('idpeFile'),proj:$('idpeProjectionFile'),position:$('idpePosition'),
    scope:$('idpeScope'),sort:$('idpeSort'),search:$('idpeSearch'),
    young:$('idpeYoung'),clear:$('idpeClear'),note:$('idpeNote')};
  const POS={LB:'LB',S:'Safety',CB:'Corner',EDGE:'EDGE',DT:'Interior DL'};
  const lower=s=>String(s??'').toLowerCase().trim();
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const norm=s=>lower(s).replace(/\b(jr|sr|ii|iii|iv)\b/g,'').replace(/[^a-z0-9]/g,'');
  const n=v=>Number.isFinite(v)?v:null;
  const fmt=(v,dec=1)=>n(v)===null?'—':v.toFixed(dec);
  const age=p=>Number.isInteger(p.age)&&p.age>=18&&p.age<=45?p.age:null;
  const ids=new Map(),owners=new Map(),projections=new Map();
  let watch=new Map(),hasProjection=false,rosterTime=null,importCount=0;
  function rosterPlayers(r){return ['starters','bench','taxi','reserve_ir'].flatMap(k=>r[k]||[]);}
  function ensure(cond,msg){if(!cond)throw Error(msg);}
  function safeRate(t,s){return n(t)!==null&&n(s)!==null&&s>0?100*t/s:null;}
  function validateObservation(o){
    ensure(o&&Number.isInteger(o.week)&&o.week>=1&&o.week<=22,'Invalid observed week');
    ensure(Number.isInteger(o.defensive_snaps)&&o.defensive_snaps>=0&&o.defensive_snaps<=150,'Invalid defensive snaps');
    ensure(o.tackles===null||(Number.isFinite(o.tackles)&&o.tackles>=0&&o.tackles<=100),'Invalid tackle count');
    ensure(o.snap_share_pct===null||(Number.isFinite(o.snap_share_pct)&&o.snap_share_pct>=0&&o.snap_share_pct<=100),'Invalid snap share');
    ensure(typeof o.source_label==='string'&&o.source_label.length<=180,'Missing observation source label');
  }
  function validateWatch(d){
    ensure(d?.schema_version===1&&d.classification==='PRIVATE_LOCAL_IDP_EARLY_WATCH_NOT_FOR_REPO','Expected LOG private early-watch JSON; nothing imported');
    ensure(d.season===2026&&Array.isArray(d.players)&&d.players.length>0&&d.players.length<=300,'Invalid private watch file season or population');
    const seen=new Set();
    d.players.forEach(p=>{
      ensure(/^\d+$/.test(String(p.sleeper_id))&&!seen.has(String(p.sleeper_id)),'Invalid or duplicate Sleeper ID');
      seen.add(String(p.sleeper_id));
      ensure(typeof p.name==='string'&&p.name.length>0&&p.name.length<=100,'Invalid player name');
      ensure(POS[p.position]&&typeof p.team==='string'&&p.team.length<=5,'Invalid watch position/team');
      ensure(p.age===null||(Number.isInteger(p.age)&&p.age>=18&&p.age<=45),'Invalid age');
      ensure(Array.isArray(p.observations)&&p.observations.length<=22,'Invalid observations array');
      const weeks=new Set();
      p.observations.forEach(o=>{validateObservation(o);ensure(!weeks.has(o.week),'Duplicate weekly observation');weeks.add(o.week);});
      ensure(Array.isArray(p.events)&&p.events.length<=15,'Invalid opportunity events');
      p.events.forEach(e=>{
        ensure(e&&typeof e.date==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(e.date)&&e.description?.length<=400,'Invalid event date or description');
        ensure(['USER_REPORTED_UNVERIFIED','SOURCE_VERIFIED','OBSERVED_USAGE'].includes(e.verification),'Invalid event verification');
      });
      ensure(typeof p.note==='string'&&p.note.length<=500,'Invalid note');
    });
    return d;
  }
  function validateProjections(d){
    ensure(d?.schema_version===1&&d.classification==='PRIVATE_SUBSCRIBER_DERIVED_NOT_FOR_PUBLIC_REPO','Expected private Woellert projection snapshot');
    ensure(d.season===2026&&d.week===10&&d.record_count===308&&Array.isArray(d.players)&&d.players.length===308,'Wrong or incomplete frozen Week 10 projection');
    const m=new Map();
    d.players.forEach(p=>{
      ensure(p&&typeof p.player==='string'&&typeof p.team==='string','Malformed projection identity');
      ensure(Number.isFinite(p.log_linear_base_points)&&Number.isFinite(p.projected_defensive_snaps),'Malformed projection statistics');
      const key=norm(p.player)+'|'+p.team.toUpperCase();
      ensure(!m.has(key),'Ambiguous same-name/team projection');m.set(key,p);
    });
    return m;
  }
  async function readFile(file,maxBytes){
    ensure(file&&file.size>0&&file.size<=maxBytes,'File is missing or too large');
    return JSON.parse(await file.text());
  }
  function status(p){
    const k=String(p.sleeper_id);
    if(owners.has(k))return 'Rostered';
    if(ids.has(k))return 'LOG free agent';
    return 'Availability unresolved';
  }
  function metadata(p){return ids.get(String(p.sleeper_id))||owners.get(String(p.sleeper_id))||{};}
  function obsOf(p){return [...p.observations].sort((a,b)=>a.week-b.week);}
  function roleTrend(p){
    const x=obsOf(p);
    if(x.length<3)return {label:'Role trend unconfirmed',delta:null};
    const last=x.slice(-3);
    if(last.some(o=>n(o.snap_share_pct)===null))return {label:'Role trend unconfirmed',delta:null};
    const baseline=(last[0].snap_share_pct+last[1].snap_share_pct)/2;
    const delta=last[2].snap_share_pct-baseline;
    return {label:delta>=15?'Rising role — 3 observations':'Role change not established',delta};
  }
  function signals(p){
    const x=obsOf(p), last=x.at(-1), rt=roleTrend(p);
    if(!last)return {label:'Opportunity watch',rate:null,notes:'No weekly statistics imported.'};
    const rate=safeRate(last.tackles,last.defensive_snaps);
    if(rt.delta!==null&&rt.delta>=15)return {label:'Rising usage signal',rate,notes:'Snap-share change observed; future fantasy contribution remains unproven.'};
    const high=p.position==='LB'?16:(p.position==='S'?12:(p.position==='CB'?10:null));
    const strong=high!==null&&rate!==null&&rate>=high&&last.defensive_snaps>=10;
    if(strong)return {label:'Small-sample efficiency',rate,notes:'High one-game tackle rate; not a validated breakout.'};
    return {label:'Opportunity watch',rate,notes:'Monitor additional defensive snaps and weekly efficiency.'};
  }
  function projectionFor(p){
    // Source team is matched explicitly; moving a player to a different team
    // cannot silently attach a stale source projection.
    const key=norm(p.name)+'|'+String(p.team).toUpperCase();
    return projections.get(key)||null;
  }
  function card(p){
    const person=metadata(p),validAge=age(person)??age(p),observations=obsOf(p);
    const latest=observations.at(-1),sig=signals(p),trend=roleTrend(p),pr=projectionFor(p);
    const state=status(p), events=[...p.events].sort((a,b)=>b.date.localeCompare(a.date));
    const flags=[];
    if(validAge!==null&&validAge<=25)flags.push('Age ≤25');
    if(latest&&latest.defensive_snaps<200)flags.push('Small sample');
    if(events.some(e=>e.verification==='USER_REPORTED_UNVERIFIED'))flags.push('Event needs verification');
    const facts=latest?`<div class="idpe-facts"><div><small>Last observed</small><strong>W${latest.week}</strong></div>
      <div><small>Def. snaps</small><strong>${latest.defensive_snaps}</strong></div>
      <div><small>Tackles</small><strong>${latest.tackles===null?'Not supplied':fmt(latest.tackles,0)}</strong></div>
      <div><small>Tackle rate</small><strong>${sig.rate===null?'Unavailable':fmt(sig.rate)+'%'}</strong></div></div>`:'';
    const eventsHTML=events.length?events.map(e=>`<li><strong>${esc(e.date)}</strong> · ${esc(e.description)} <em>${e.verification==='SOURCE_VERIFIED'?'Verified at source':e.verification==='OBSERVED_USAGE'?'Observed usage':'User-reported; verify'}</em></li>`).join(''):'<li>No transaction/injury event recorded.</li>';
    const projHTML=!hasProjection?'No private projection file loaded.':pr?
      `Week 10 source forecast: ${fmt(pr.projected_defensive_snaps)} defensive snaps; ${fmt(pr.log_linear_base_points)} LOG linear-base points (excludes bonuses and unprojected events).`:
      'NOT PROJECTED in frozen Week 10 workbook — never interpret absence as zero.';
    return `<article class="idpe-card">
      <div class="idpe-head"><div><strong>${esc(p.name)}</strong><span>${esc(POS[p.position])} · ${esc(p.team)} · ${validAge===null?'Age unverified':'Age '+validAge} · ${esc(state)}</span></div><div class="idpe-chip">${esc(sig.label)}</div></div>
      ${facts}
      <p class="idpe-fine">${esc(sig.notes)} ${trend.delta!==null?`Latest snap share vs previous two observed: ${trend.delta>=0?'+':''}${fmt(trend.delta)} pp.`:'No multiweek snap-share evidence yet.'}</p>
      <div class="idpe-tags">${flags.map(t=>`<span>${esc(t)}</span>`).join('')}</div>
      <details class="idpe-detail"><summary>Evidence and private forecast</summary>
        <div class="idpe-body"><strong>Opportunity events</strong><ul>${eventsHTML}</ul>
        <strong>Private weekly projection</strong><p>${esc(projHTML)}</p>
        <strong>Observer notes</strong><p>${esc(p.note||'No notes')}</p>
        ${latest?`<small>Observed W${latest.week} source: ${esc(latest.source_label)}. Tackle rates here are calculated only from supplied game totals and snaps.</small>`:''}
        </div></details></article>`;
  }
  function render(){
    const q=lower(ui.search.value);const ps=ui.position.value,scope=ui.scope.value;
    let entries=[...watch.values()].filter(p=>(ps==='ALL'||p.position===ps)&&
      (scope==='all'||(scope==='available'&&status(p)==='LOG free agent'))&&
      (!ui.young.checked||((age(metadata(p))??age(p))??100)<=25)&&
      (!q||lower(p.name).includes(q)));
    const sorter=ui.sort.value;
    entries.sort((a,b)=>{
      if(sorter==='age')return ((age(metadata(a))??age(a))??99)-((age(metadata(b))??age(b))??99)||a.name.localeCompare(b.name);
      if(sorter==='snaps')return (obsOf(b).at(-1)?.defensive_snaps??-1)-(obsOf(a).at(-1)?.defensive_snaps??-1)||a.name.localeCompare(b.name);
      return (b.events.length>0)-(a.events.length>0)||b.observations.length-a.observations.length||a.name.localeCompare(b.name);
    });
    ui.count.textContent=`(${entries.length} of ${watch.size} local watch players)`;
    ui.list.innerHTML=entries.length?entries.map(card).join(''):
      `<div class="idpe-empty">${watch.size?'No watch players match these filters.':'No private early-opportunity file loaded. Choose the private Watch JSON on your device to begin.'}</div>`;
    ui.note.textContent=`Local-only: ${watch.size} watch players; ${hasProjection?'frozen W10 forecast loaded privately':'no weekly projection loaded'}. This module does not submit or store your imports. Source: 2026; availability refreshed ${rosterTime||'not loaded'}.`;
  }
  async function init(){
    try{
      const base='https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/main/';
      const paths=['data/free_agents.json','data/league_rosters.json','config.json'];
      const responses=await Promise.all(paths.map(p=>fetch(base+p+'?idpe='+Date.now(),{cache:'no-store'})));
      ensure(responses.every(r=>r.ok),'Current LOG free-agent sources unavailable');
      const [f,r,c]=await Promise.all(responses.map(x=>x.json()));
      ensure(Array.isArray(f.free_agents)&&f.count===f.free_agents.length&&f.league_id===r.league_id&&r.rosters?.length===12,'League snapshot is incomplete');
      ensure(c.league_id===f.league_id,'Wrong league configuration');
      f.free_agents.forEach(p=>ids.set(String(p.player_id),p));
      r.rosters.flatMap(rosterPlayers).forEach(p=>owners.set(String(p.player_id),p));
      ensure(![...ids.keys()].some(k=>owners.has(k)),'Roster/free-agent overlap');
      const stamp=Number(f.synced_at);
      rosterTime=Number.isFinite(stamp)?new Date(stamp*1000).toLocaleString():'unknown';
      const stale=Number.isFinite(stamp)&&Date.now()-stamp*1000>48*3600000;
      ui.status.textContent=`LOG roster matched (${ids.size} free agents). ${stale?'WARNING: Roster data older than 48 hours. Verify before claims.':'Upload your private watch JSON to view candidates.'}`;
      render();
    }catch(error){
      ui.status.textContent='IDP Early Opportunity unavailable: '+String(error.message||error)+'; existing board unaffected.';
      ui.status.classList.add('idpe-error');ui.list.textContent='';
      // Fail closed rather than pretending to know current availability.
      ui.file.disabled=true;ui.proj.disabled=true;
    }
  }
  ui.file.addEventListener('change',async()=>{
    try{
      const docs=[...ui.file.files];ensure(docs.length>0&&docs.length<=12,'Choose up to 12 local watch files');
      const next=new Map(watch);
      for(const file of docs){const d=validateWatch(await readFile(file,1_500_000));
        for(const p of d.players){
          const key=String(p.sleeper_id),prior=next.get(key);
          if(!prior){next.set(key,p);continue;}
          ensure(prior.name===p.name&&prior.position===p.position,'Conflicting identity for '+p.name);
          const ob=new Map(prior.observations.map(x=>[x.week,x]));
          p.observations.forEach(x=>{if(ob.has(x.week))ensure(JSON.stringify(ob.get(x.week))===JSON.stringify(x),'Conflicting snapshot week for '+p.name);else ob.set(x.week,x);});
          const ev=[...prior.events];p.events.forEach(x=>{if(!ev.some(e=>JSON.stringify(e)===JSON.stringify(x)))ev.push(x);});
          next.set(key,{...p,observations:[...ob.values()],events:ev});
        }
      }
      watch=next;importCount+=docs.length;
      ui.status.textContent=`Private watch import validated: ${watch.size} unique players from ${importCount} file(s). Data stays in this browser tab.`;
      ui.file.value='';render();
    }catch(error){ui.status.textContent='Private watch import rejected: '+String(error.message||error);ui.status.classList.add('idpe-error');ui.file.value='';}
  });
  ui.proj.addEventListener('change',async()=>{
    try{const d=await readFile(ui.proj.files?.[0],3_000_000);const next=validateProjections(d);
      projections.clear();next.forEach((v,k)=>projections.set(k,v));hasProjection=true;
      ui.status.classList.remove('idpe-error');ui.status.textContent='Frozen 2026 Week 10 projection loaded in memory only. No data uploaded.';
      ui.proj.value='';render();
    }catch(error){ui.status.textContent='Private projection rejected: '+String(error.message||error);ui.status.classList.add('idpe-error');ui.proj.value='';}
  });
  ui.clear.addEventListener('click',()=>{watch.clear();projections.clear();hasProjection=false;importCount=0;ui.status.classList.remove('idpe-error');ui.status.textContent='Private imports cleared from this browser tab.';render();});
  for(const control of [ui.position,ui.scope,ui.sort,ui.young])control.addEventListener('change',render);
  ui.search.addEventListener('input',render);
  init();
})();
