/* LOG FA08R1: public Sleeper weekly IDP trends. Read-only, no subscriber data. */
(() => {
  'use strict';
  const root = document.getElementById('idptPanel');
  if (!root) return;
  const $ = id => document.getElementById(id);
  const ui = {status:$('idptStatus'),count:$('idptCount'),list:$('idptList'),more:$('idptMore'),note:$('idptNote'),
    group:$('idptGroup'),view:$('idptView'),availability:$('idptAvailability'),sort:$('idptSort'),search:$('idptSearch')};
  const safe = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const n = v => (typeof v==='number'&&Number.isFinite(v)) ? v : null;
  const val = (v,d=1) => n(v)===null ? '—' : v.toFixed(d);
  const id = v => String(v ?? '');
  const latest = p => p.observations[p.observations.length-1] || null;
  let weekly=null,free=new Map(),owned=new Map(),limit=12,when='';
  const rising = p => p.research_trend?.status === 'RISING_RAW_DEFENSIVE_SNAPS';
  const availability = p => owned.has(id(p.sleeper_id)) ? 'rostered' : free.has(id(p.sleeper_id)) ? 'available' : 'unresolved';
  const age = p => Number.isInteger(p.age)&&p.age>=18&&p.age<=45 ? p.age : null;
  function rosterPlayers(t){return ['starters','bench','taxi','reserve_ir'].flatMap(k=>t[k]||[]);}
  function assert(c,m){if(!c)throw Error(m);}
  function check(doc,fa,rs,config){
    assert(doc && doc.schema_version===1 && doc.classification==='PUBLIC_SLEEPER_WEEKLY_IDP_EVIDENCE_NOT_PROJECTION_OR_BREAKOUT','Wrong public evidence type');
    assert(doc.season===2026 && Number.isInteger(doc.last_completed_week) && doc.last_completed_week>=5 && doc.last_completed_week<=18,'Unexpected season/week');
    assert(Array.isArray(doc.source_manifest) && doc.source_manifest.length===doc.last_completed_week-4 && doc.source_manifest.every((m,i)=>m.week===i+5&&typeof m.response_sha256==='string'&&/^[a-f0-9]{64}$/.test(m.response_sha256)),'Source-week manifest incomplete');
    assert(Array.isArray(doc.players) && doc.players.length>=100 && doc.players.length<=5000,'Unexpected public player count');
    assert(doc.counts?.total_player_records===doc.players.length,'Player count mismatch');
    const seen=new Set();
    for(const p of doc.players){
      assert(p&&/^\d+$/.test(id(p.sleeper_id))&&!seen.has(id(p.sleeper_id))&&typeof p.name==='string'&&p.name.length<120&&['LB','DL','DB'].includes(p.position),'Invalid/duplicate IDP identity');
      seen.add(id(p.sleeper_id));
      assert(Array.isArray(p.observations)&&p.observations.length>0&&p.observations.length<=14,'Invalid weekly observations');
      let prev=4;
      for(const o of p.observations){
        assert(Number.isInteger(o.week)&&o.week>=5&&o.week<=doc.last_completed_week&&o.week>prev,'Bad week sequence');
        prev=o.week;
        assert(o.defensive_snaps===null || (Number.isFinite(o.defensive_snaps)&&o.defensive_snaps>=0&&o.defensive_snaps<=150),'Bad defensive snap count');
        assert(o.snap_share_pct===null,'Unexpected unsourced snap-share data');
        assert(n(o.tackles)!==null&&o.tackles>=0,'Invalid sourced tackles');
      }
      assert(p.research_trend && ['RISING_RAW_DEFENSIVE_SNAPS','NO_STRONG_RAW_SNAP_INCREASE','NONCONSECUTIVE_WEEKS_NO_TREND_CLAIM','INSUFFICIENT_CONSECUTIVE_WEEKLY_SNAPS'].includes(p.research_trend.status),'Bad research-trend classification');
    }
    assert(fa?.league_id && fa.league_id===rs?.league_id && fa.league_id===config?.league_id && fa.count===fa.free_agents?.length && Array.isArray(rs.rosters)&&rs.rosters.length===12,'LOG league/availability snapshot mismatch');
  }
  function score(p){
    const l=latest(p),s=n(l?.defensive_snaps)??0,rt=n(l?.tackle_rate_pct)??0;
    const gain=n(p.research_trend?.snap_gain_vs_previous_two)??-999;
    // UI-only descriptive sorting. Never interpreted as an FV score or probability.
    return (rising(p)?100000:0)+(l?.week===weekly.last_completed_week?10000:0)+Math.max(-100,gain)*10+s+Math.min(50,rt)*0.01;
  }
  function card(p){
    const stat=availability(p),obs=new Map(p.observations.map(o=>[o.week,o])),l=latest(p),t=p.research_trend;
    const subtitle=[p.position,p.team||'Team unknown',age(p)===null?'Age unknown':'Age '+age(p),stat==='available'?'LOG free agent':stat==='rostered'?'Rostered':'Status unresolved'].map(safe).join(' · ');
    const label=rising(p)?'Rising raw snaps':t.status==='NONCONSECUTIVE_WEEKS_NO_TREND_CLAIM'?'Nonconsecutive weeks':t.status==='INSUFFICIENT_CONSECUTIVE_WEEKLY_SNAPS'?'Limited snap history':'No strong snap rise';
    const weekCells=[];
    for(let w=5;w<=weekly.last_completed_week;w++){
      const o=obs.get(w),snaps=o?n(o.defensive_snaps):null;
      weekCells.push(`<div class="idpt-week"><small>W${w}</small><strong>${snaps===null?'—':snaps}</strong></div>`);
    }
    const gain=n(t.snap_gain_vs_previous_two);
    const supported=!!l && n(l.defensive_snaps)!==null;
    const lastWeek=weekly.last_completed_week;
    return `<article class="idpt-card">
      <div class="idpt-head"><div><strong>${safe(p.name)}</strong><small>${subtitle}</small></div><span class="idpt-tag ${rising(p)?'idpt-rise':''}">${label}</span></div>
      <div class="idpt-metrics"><div><small>Most recent observed</small><strong>${l?'W'+l.week:'—'}${l?.week===lastWeek?' (current)':' (older)'}</strong></div>
      <div><small>Defensive snaps</small><strong>${supported?val(l.defensive_snaps,0):'Not reported'}</strong></div>
      <div><small>Solo + assists</small><strong>${l?val(l.tackles,1):'—'}</strong></div>
      <div><small>Tackle rate</small><strong>${supported?val(l.tackle_rate_pct,1)+'%':'—'}</strong></div></div>
      <div class="idpt-weeks" aria-label="Weeks 5 through ${lastWeek} defensive snaps">${weekCells.join('')}</div>
      <p class="idpt-reason">${gain===null?'No validated three-consecutive-week snap comparison.':`Latest three consecutive weeks: ${gain>=0?'+':''}${val(gain)} defensive snaps vs. prior-two average.`} ${stat==='available'?'Available in most recent LOG snapshot.':''}</p>
      <details class="idpt-evidence"><summary>Weekly evidence & limitations</summary>
      <p>Raw defensive snaps only, not snap share. Tackle rate uses solo + assisted tackles and available defensive snaps. An em dash means missing or no confirmed participation; it does not mean zero. Ranking is descriptive, not a validated breakout prediction.</p>
      <div class="idpt-detail">${p.observations.map(o=>`<span>W${o.week}: ${n(o.defensive_snaps)===null?'snaps unknown':o.defensive_snaps+' snaps'}, ${val(o.tackles)} tackles${n(o.tackle_rate_pct)===null?'':', '+val(o.tackle_rate_pct)+'% rate'}</span>`).join('')}</div>
      </details></article>`;
  }
  function render(){
    if(!weekly)return;
    const q=ui.search.value.trim().toLowerCase();
    let all=weekly.players.filter(p=>
      (ui.group.value==='ALL'||p.position===ui.group.value)&&
      (ui.availability.value==='all'||availability(p)===ui.availability.value)&&
      (ui.view.value==='all'||(ui.view.value==='rising'&&rising(p))||(ui.view.value==='young'&&age(p)!==null&&age(p)<=25))&&
      (!q||p.name.toLowerCase().includes(q)));
    const sort=ui.sort.value;
    all.sort((a,b)=>{
      if(sort==='latest')return (n(latest(b)?.defensive_snaps)??-1)-(n(latest(a)?.defensive_snaps)??-1)||a.name.localeCompare(b.name);
      if(sort==='youngest')return (age(a)??100)-(age(b)??100)||a.name.localeCompare(b.name);
      if(sort==='tackle')return (n(latest(b)?.tackle_rate_pct)??-1)-(n(latest(a)?.tackle_rate_pct)??-1)||a.name.localeCompare(b.name);
      return score(b)-score(a)||a.name.localeCompare(b.name);
    });
    ui.count.textContent=`(${all.length} matching)`;
    ui.list.innerHTML=all.length?all.slice(0,limit).map(card).join(''):'<p class="idpt-empty">No players match these filters. Select “All observed” to explore the full public evidence history.</p>';
    ui.more.hidden=all.length<=limit;
    ui.more.textContent=`Show more (${Math.min(all.length-limit,12)} of ${all.length-limit} remaining)`;
    const availableRising=weekly.players.filter(p=>rising(p)&&availability(p)==='available').length;
    ui.note.textContent=`2026 W5–${weekly.last_completed_week} public Sleeper data · ${weekly.players.length} observed IDPs · ${weekly.counts.rising_raw_snap_signals} raw-snap signals · ${availableRising} currently in LOG free-agent snapshot. Roster sync: ${when}. This is not snap share, expert ranking, a transaction alert, or a projection.`;
  }
  async function init(){
    try{
      const base='https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/main/';
      const paths=['data/idp_weekly_2026_public.json','data/free_agents.json','data/league_rosters.json','config.json'];
      const requests=await Promise.all(paths.map(p=>fetch(base+p,{cache:'no-store'})));
      assert(requests.every(r=>r.ok),'One or more public source files are unavailable');
      const [w,fa,rs,config]=await Promise.all(requests.map(r=>r.json()));
      check(w,fa,rs,config);
      weekly=w;
      fa.free_agents.forEach(p=>free.set(id(p.player_id),p));
      rs.rosters.flatMap(rosterPlayers).forEach(p=>owned.set(id(p.player_id),p));
      assert(![...free.keys()].some(k=>owned.has(k)),'LOG roster/free-agent overlap');
      const sync=Number(fa.synced_at);
      when=Number.isFinite(sync)?new Date(sync*1000).toLocaleString():'unavailable';
      const old=Number.isFinite(sync)&&Date.now()-sync*1000>48*3600*1000;
      ui.status.textContent=`Public weekly stats loaded for ${w.players.length} IDPs. ${old?'WARNING: LOG roster snapshot is over 48 hours old; verify availability before adding.':'Availability checked against LOG sync.'}`;
      render();
    }catch(e){
      ui.status.textContent='Public trend radar unavailable: '+String(e?.message||e)+'; private watchlist and original dashboard are unaffected.';
      ui.status.classList.add('idpt-error');ui.list.textContent='';ui.count.textContent='(unavailable)';
    }
  }
  for(const elem of [ui.group,ui.view,ui.availability,ui.sort])elem.addEventListener('change',()=>{limit=12;render()});
  ui.search.addEventListener('input',()=>{limit=12;render()});
  ui.more.addEventListener('click',()=>{limit+=12;render()});
  init();
})();
