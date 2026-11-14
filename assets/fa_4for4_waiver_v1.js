/* LOG A-FA23R1: two-horizon waiver research, extending owner-only FA22 importer.
 * Subscription CSVs are read from a local File input and held in RAM only.
 * Public reads: LOG free agent pool and frozen Macri ROS reference.
 * This module never writes FV/MV, canonical rankings, localStorage, IndexedDB or network uploads.
 */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const nameKey = value => String(value ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
    .replace(/\b(jr|sr|ii|iii|iv)\b\.?/g, '').replace(/[^a-z0-9]/g, '');
  const teamKey = value => {
    const s = String(value ?? '').toUpperCase().trim();
    return ({JAC:'JAX',LA:'LAR',STL:'LAR',SD:'LAC',OAK:'LV',WSH:'WAS'}[s] || s);
  };
  const groupKey = value => {
    const v = String(value ?? '').toUpperCase().replace(/[^A-Z]/g,'');
    if (['DL','DE','DT','ED','DI','EDGE','NT','IDL','OLB','DEFENSIVELINE','DEFENSIVEEND'].includes(v)) return 'DL';
    if (['LB','ILB','MLB','WLB','SLB','LINEBACKER'].includes(v)) return 'LB';
    if (['DB','S','SS','FS','CB','SAFETY','CORNERBACK'].includes(v)) return 'DB';
    return '';
  };
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
  const normalizeCol = value => String(value ?? '').toLowerCase().replace(/[^a-z0-9]/g,'');
  const num = value => {
    const s = String(value ?? '').trim().replace(/,/g,'').replace(/%$/, '');
    if (!s) return null;
    const x = Number(s);
    return Number.isFinite(x) ? x : null;
  };
  const col = (headers, names) => {
    const ix = headers.findIndex(x => names.includes(normalizeCol(x)));
    return ix;
  };
  function parseCsv(text) {
    const output = []; let row = [], field = '', quoted = false;
    text = String(text).replace(/^\uFEFF/,'');
    for (let i=0;i<text.length;i++) {
      const c=text[i];
      if (c==='"') {
        if (quoted && text[i+1]==='"') {field+='"';i++;}
        else quoted=!quoted;
      } else if (c===',' && !quoted) {row.push(field);field='';}
      else if ((c==='\n'||c==='\r') && !quoted) {
        if (c==='\r' && text[i+1]==='\n') i++;
        row.push(field);field='';
        if (row.some(v=>String(v).trim())) output.push(row);
        row=[];
      } else field+=c;
    }
    if (quoted) throw new Error('CSV has an unmatched quote');
    row.push(field);
    if (row.some(v=>String(v).trim())) output.push(row);
    return output;
  }
  const parseRank = (value, allowed) => {
    const m = /^\s*([A-Z]+)\s*-\s*(\d+)\s*$/i.exec(String(value ?? ''));
    if (!m) return null;
    const group=m[1].toUpperCase(), rank=Number(m[2]);
    return allowed.includes(group) && Number.isInteger(rank) && rank>0 && rank<2000
      ? {group,rank} : null;
  };
  function parseProjectionCsv(content, filename) {
    const table=parseCsv(content);
    if (table.length<2) throw new Error(`${filename}: No projection rows`);
    const headers=table[0];
    const fields={
      name:col(headers,['player','playername','name']),
      team:col(headers,['team','tm']),
      pos:col(headers,['position','pos']),
      groupRank:col(headers,['grouprank']),
      positionRank:col(headers,['positionrank']),
      opp:col(headers,['opp','opponent','matchup']),
      pts:col(headers,['ffpts','fpts','fantasypoints','projectedpoints','projection','projpts']),
      vor:col(headers,['vor','valueoverreplacement']),
      snap:col(headers,['snap','snaps','snappct','snappercent','snappercentage']),
      tackles:col(headers,['tackles','solo','solotackles']),
      assists:col(headers,['assists','ast','assistedtackles']),
      sacks:col(headers,['sacks','sack']),
      tfl:col(headers,['tfl','tacklesforloss']),
      pd:col(headers,['pd','passdeflections','passesdefended']),
    };
    if ([fields.name,fields.team,fields.pts,fields.opp].some(x=>x<0) ||
      (fields.pos<0 && fields.groupRank<0))
      throw new Error(`${filename}: Expected Player, Team, Opp, FF Pts and either Position or Group-Rank. Weekly 4for4 exports with Group-Rank / Position-Rank are supported.`);
    if (col(headers,['bye','byeweek'])>=0)
      throw new Error(`${filename}: Looks like a season-long projection (Bye column). Export a specific NFL week.`);
    const rows=[];
    for (let i=1;i<table.length;i++) {
      const cells=table[i], get=key=>fields[key]>=0?(cells[fields[key]]??''):'';
      const gr=fields.groupRank>=0?parseRank(get('groupRank'),['DL','LB','DB']):null;
      const pr=fields.positionRank>=0?parseRank(get('positionRank'),['DE','DT','LB','CB','S']):null;
      const group=gr?.group || groupKey(get('pos'));
      if (!group) continue;
      if (fields.groupRank>=0 && !gr) throw new Error(`${filename}: Invalid Group-Rank on CSV row ${i+1}`);
      if (fields.positionRank>=0 && (!pr || groupKey(pr.group)!==group))
        throw new Error(`${filename}: Invalid or conflicting Position-Rank on CSV row ${i+1}`);
      const pts=num(get('pts')), player=String(get('name')).trim(), team=teamKey(get('team'));
      if (!player || !team || pts===null || pts<0 || pts>100) continue;
      rows.push({name:player,team,group,rawPos:pr?.group||get('pos')||group,
        groupRank:gr?.rank??null,positionRank:pr?.rank??null,vor:num(get('vor')),
        opp:get('opp'),pts,
        snap:num(get('snap')),tackles:num(get('tackles')),assists:num(get('assists')),
        sacks:num(get('sacks')),tfl:num(get('tfl')),pd:num(get('pd')),line:i+1});
    }
    if (!rows.length) throw new Error(`${filename}: No valid DL/LB/DB projection rows. Check the CSV layout.`);
    return rows;
  }
  function init() {
    const target=$('fa-ws-idp-panel');
    if (!target || $('fa22WaiverLab')) return;
    const host=document.createElement('section');
    host.id='fa22WaiverLab';
    host.className='fa22';
    host.setAttribute('aria-label','Private weekly 4for4 IDP waiver finder');
    host.innerHTML=`
      <header class="fa22-heading"><div><span class="fa22-eyebrow">Weekly decision research</span>
        <h3>Waiver Decision Center</h3>
        <p>Explore <strong>Win This Week</strong> and <strong>Dynasty Upside</strong> using separate 4for4, Macri ROS, age, and public role-evidence lenses. No blended score or FV adjustment.</p></div>
        <span class="fa22-private">PRIVATE · THIS TAB ONLY</span></header>
      <div class="fa22-controls">
        <label>2026 NFL week <input id="fa22Week" type="number" min="1" max="18" step="1" placeholder="e.g. 11" inputmode="numeric"></label>
        <label>Scoring on export <select id="fa22Scoring"><option value="">Choose scoring</option><option value="log">My LOG league scoring</option><option value="other">Other 4for4 scoring</option></select></label>
        <label class="fa22-file">4for4 weekly CSV files (DL / LB / DB or combined) <input id="fa22Files" type="file" accept=".csv,text/csv" multiple></label>
      </div>
      <p class="fa22-caption">Export the <strong>weekly</strong> IDP projections as CSV from 4for4. The standard export uses Player, Team, Opp, Group-Rank, Position-Rank, FF Pts and VOR; optional detailed-stat columns are accepted too. Select your actual scoring setup. Files stay in browser memory, aren't uploaded, and disappear on refresh. Week and scoring are selected by you, not inferred from file names.</p>
      <div class="fa22-actions"><button type="button" id="fa22Import" class="fa22-primary">Analyze my weekly CSVs</button><button type="button" id="fa22Clear">Clear private projections</button></div>
      <p id="fa22Status" class="fa22-status" role="status" aria-live="polite">No 4for4 projections loaded. Your existing IDP research below is unchanged.</p>
      <div id="fa22Results" hidden>
        <div class="fa23-horizons" role="tablist" aria-label="Waiver planning horizon">
          <button type="button" id="fa23Week" role="tab" aria-selected="true" aria-controls="fa22List">Win This Week</button>
          <button type="button" id="fa23Dynasty" role="tab" aria-selected="false" aria-controls="fa22List">Dynasty Upside</button>
        </div>
        <p id="fa23Guide" class="fa23-guide">Ranks by 4for4 projected points within each DL/LB/DB group. Macri ROS is independent context, not a comparable number.</p>
        <p id="fa23EvidenceStatus" class="fa23-evidence" aria-live="polite">Public usage context loads after importing your private CSV.</p>
        <div class="fa22-filterbar"><label>Position <select id="fa22Group"><option value="ALL">All IDP</option><option value="DL">DL</option><option value="LB">LB</option><option value="DB">DB</option></select></label>
        <label>Focus <select id="fa22Focus"><option value="week">Best projected this week</option><option value="young">Age 25 or younger</option><option value="ros">Also ranked in Macri ROS</option></select></label></div>
        <div id="fa22List" class="fa22-list" aria-live="polite"></div>
        <details class="fa22-unmatched"><summary id="fa22UnmatchedTitle">Not matched to available LOG players</summary><div id="fa22UnmatchedList"></div></details>
      </div>`;
    const anchor=target.querySelector('.fa-mobile-focus-row') || target.querySelector('.fa-ws-intro');
    if (anchor) anchor.insertAdjacentElement('afterend',host);
    else target.prepend(host);
    const status=$('fa22Status'), results=$('fa22Results'), output=$('fa22List');
    let privateRows=[], unmatched=[], week='', scoring='', publicFa=[], rosById=new Map();
    let requestGeneration=0, evidenceNotes=[], horizon='week';
    const pNum=x=>Number.isFinite(x)?x.toFixed(1):'—';
    const lookupKey=x=>`${nameKey(x.name)}|${teamKey(x.team)}|${groupKey(x.pos||x.group)}`;
    function say(message,error=false){status.textContent=message;status.classList.toggle('fa22-error',error);}
    function clear(){requestGeneration++;privateRows=[];unmatched=[];week='';scoring='';results.hidden=true;output.replaceChildren();
      $('fa22Files').value='';$('fa23EvidenceStatus').textContent='No usage evidence loaded.';
      say('Private projections cleared from this browser tab.');}
    $('fa22Clear').addEventListener('click',clear);
    for(const id of ['fa22Week','fa22Scoring','fa22Files']) {
      $(id).addEventListener('change',()=>{requestGeneration++;if(privateRows.length){privateRows=[];unmatched=[];results.hidden=true;output.replaceChildren();
        $('fa23EvidenceStatus').textContent='Inputs changed; prior public evidence and projections are no longer active.';
        say('Inputs changed. Analyze the selected weekly CSV again before using any results.');}});
    }
    const horizonOptions={
      week:[['week','Best projected this week'],['young','Age 25 or younger'],['ros','Also ranked in Macri ROS']],
      dynasty:[['all','All young free agents (25 or younger)'],['snap','Positive raw snap change'],['ros','Present in Macri ROS'],['both','Snap change + Macri ROS']]
    };
    function changeHorizon(next){
      horizon=next;
      $('fa23Week').setAttribute('aria-selected',String(next==='week'));
      $('fa23Dynasty').setAttribute('aria-selected',String(next==='dynasty'));
      $('fa22Focus').innerHTML=horizonOptions[next].map(([key,label])=>`<option value="${key}">${label}</option>`).join('');
      $('fa23Guide').textContent=next==='week'
        ? 'Ranks by 4for4 projected points within each DL/LB/DB group. Macri ROS is independent context, not a comparable number.'
        : 'A young-player research shortlist, NOT a dynasty ranking. Groups are organized by evidence coverage, then age and weekly points only as display tie-breakers. No breakout probabilities or blended score.';
      render();
    }
    $('fa23Week').addEventListener('click',()=>changeHorizon('week'));
    $('fa23Dynasty').addEventListener('click',()=>changeHorizon('dynasty'));
    function showUsage(row){
      const e=row.usage;
      if(!e)return '';
      const p=[];
      if(Number.isFinite(e.snaps_per_game))p.push(`${pNum(e.snaps_per_game)} defensive snaps/game`);
      if(Number.isFinite(e.tackle_rate_pct))p.push(`${pNum(e.tackle_rate_pct)}% tackle rate`);
      return p.length?`Season usage (Nov 9 research snapshot; time range not specified): ${p.join(' · ')}`:'';
    }
    function showWeekly(row){
      const e=row.weekly;
      if(!e)return '';
      const g=e.delta===null?'no consecutive 3-week comparison':`raw snap change ${e.delta>=0?'+':''}${pNum(e.delta)} vs prior 2-week average`;
      return `Public weekly snaps through W${e.week} (before selected W${week}): ${e.snaps} most recent; ${g}`;
    }
    function hasRise(row){return row.weekly?.delta!==null && Number.isFinite(row.weekly?.delta) && row.weekly.delta>0 && row.weekly.week===Number(week)-1;}
    function cohort(row){const rise=hasRise(row),ros=!!row.ros;return rise&&ros?0:rise?1:ros?2:3;}
    function render() {
      if (!privateRows.length && !unmatched.length) {results.hidden=true;return;}
      results.hidden=false;
      const group=$('fa22Group').value,focus=$('fa22Focus').value;
      let rows=privateRows.filter(x=>group==='ALL'||group===x.group);
      if(horizon==='week'){
        rows=rows.filter(x=>(focus!=='young'||(Number.isFinite(x.age)&&x.age<=25))&&
          (focus!=='ros'||!!x.ros));
      } else {
        rows=rows.filter(x=>Number.isFinite(x.age)&&x.age<=25 &&
          (focus!=='snap'||hasRise(x)) &&
          (focus!=='ros'||!!x.ros) &&
          (focus!=='both'||(hasRise(x)&&!!x.ros)));
      }
      const order={DL:0,LB:1,DB:2};
      if(horizon==='week')rows.sort((a,b)=>order[a.group]-order[b.group]||b.pts-a.pts||a.name.localeCompare(b.name));
      else rows.sort((a,b)=>order[a.group]-order[b.group]||cohort(a)-cohort(b)||a.age-b.age||b.pts-a.pts||a.name.localeCompare(b.name));
      const shown=group==='ALL'
        ? ['DL','LB','DB'].flatMap(g=>rows.filter(x=>x.group===g).slice(0,15))
        : rows.slice(0,50);
      const parts=[];let last='';
      for(const x of shown){
        if(x.group!==last){last=x.group;parts.push(`<h4 class="fa22-group-title">${escape(last)} · ${horizon==='week'?'Week '+escape(week)+' projections':'Young-player evidence (NOT a dynasty rank)'}</h4>`);}
        const ros=x.ros ? `${escape(x.ros.group)} #${x.ros.rank} (Nov 7 ROS)` : 'No matching Macri ROS rank (not a negative grade)';
        const ranks=[x.groupRank!==null?`${x.group} #${x.groupRank}`:null,
          x.positionRank!==null?`${x.rawPos} #${x.positionRank}`:null].filter(Boolean).join(' · ');
        const vor=x.vor===null?'Not provided':`${x.vor>0?'+':''}${pNum(x.vor)}`;
        const weekly=showWeekly(x),usage=showUsage(x),rise=hasRise(x);
        const signals=horizon==='week'
          ? [`4for4 W${week}: ${pNum(x.pts)} projected points (weekly only)`,x.ros?'Also appears in frozen Macri ROS list':'Projection-only; ROS rank not matched']
          : [`Age ${x.age} · research candidate, not a validated dynasty breakout`,rise?'Positive pre-week raw snap change':x.weekly?'No confirmed positive recent snap change':'No confirmed weekly snap evidence',x.ros?'Macri ROS listed':'No matching Macri ROS rank'];
        parts.push(`<article class="fa22-player"><div class="fa22-player-main"><strong>${escape(x.name)}</strong>
          <div class="fa22-meta">${escape(x.team)} · ${escape(x.rawPos)} · Age ${x.age ?? '—'} · vs ${escape(x.opp||'—')}</div>
          <div class="fa22-meta">4for4 ${escape(ranks||'ranks not supplied')} · VOR ${escape(vor)}</div>
          <div class="fa22-ros">Macri: ${ros}</div>
          <p class="fa23-reason">${signals.map(escape).join(' · ')}</p>
          ${weekly?`<div class="fa23-role">${escape(weekly)}</div>`:'<div class="fa23-role">Weekly role trend unavailable; do not infer zero snaps or a breakout.</div>'}
          ${usage?`<div class="fa23-role">${escape(usage)}</div>`:''}
          </div><div class="fa22-score"><strong>${pNum(x.pts)}</strong><span>4for4 W${escape(week)} pts${horizon==='dynasty'?' · context only':''}</span></div></article>`);
      }
      output.innerHTML=parts.join('') || '<p class="fa22-empty">No available players meet this focus. Lack of evidence is not proof of low potential.</p>';
      $('fa22UnmatchedTitle').textContent=`Not matched to available LOG players (${unmatched.length})`;
      $('fa22UnmatchedList').textContent=unmatched.length ? unmatched.slice(0,50).map(x=>`${x.name} · ${x.team} · ${x.group}`).join(' | ') : 'All valid projection rows matched LOG free agents.';
    }
    $('fa22Group').addEventListener('change',render);
    $('fa22Focus').addEventListener('change',render);
    function usageSourceValid(doc){return doc?.schema_version===1 && doc.policy==='READ_ONLY_RESEARCH_NOT_FV_OR_PROJECTION' &&
      doc.source_week_range==='not_stated_in_csv' && Array.isArray(doc.players) && doc.players.length>20;}
    function weeklySourceValid(doc){return doc?.schema_version===1 && doc.classification==='PUBLIC_SLEEPER_WEEKLY_IDP_EVIDENCE_NOT_PROJECTION_OR_BREAKOUT' &&
      doc.season===2026 && Number.isInteger(doc.last_completed_week) && doc.last_completed_week>=5 && Array.isArray(doc.players);}
    function usageEvidence(doc){
      const byId=new Map();
      for(const p of doc.players){
        if(!p.sleeper_id || !['exact_name_team','suffix_normalized_name_team'].includes(p.identity_status))continue;
        const id=String(p.sleeper_id);
        if(byId.has(id)){byId.set(id,null);continue;}
        byId.set(id,p);
      }
      return byId;
    }
    function weeklyEvidence(doc,selectedWeek){
      const byId=new Map();
      for(const p of doc.players){
        if(!p.sleeper_id || !Array.isArray(p.observations))continue;
        const eligible=p.observations.filter(o=>Number.isInteger(o.week)&&o.week<selectedWeek &&
          Number.isFinite(o.defensive_snaps)&&o.defensive_snaps>=0 && o.defensive_snaps<=150)
          .sort((a,b)=>a.week-b.week);
        if(!eligible.length)continue;
        const last=eligible[eligible.length-1];
        let delta=null;
        if(eligible.length>=3){const prev=eligible.slice(-3);
          if(prev[2].week===prev[1].week+1 && prev[1].week===prev[0].week+1){
            delta=prev[2].defensive_snaps-(prev[0].defensive_snaps+prev[1].defensive_snaps)/2;
          }}
        const id=String(p.sleeper_id);
        if(byId.has(id)){byId.set(id,null);continue;}
        byId.set(id,{team:teamKey(p.team),group:groupKey(p.position),week:last.week,snaps:last.defensive_snaps,delta});
      }
      return byId;
    }
    async function loadRoleEvidence(token){
      const root='https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/main/';
      async function publicRead(path){
        const response=await fetch(root+path+'?t='+Date.now(),{cache:'no-store'});
        if(!response.ok)throw new Error('Public research unavailable');
        return response.json();
      }
      const docs=await Promise.allSettled([
        publicRead('data/idp_usage_2026_season.json'),
        publicRead('data/idp_weekly_2026_public.json')
      ]);
      if(token!==requestGeneration || !privateRows.length)return;
      let usage=new Map(),weekly=new Map();
      const messages=[];
      if(docs[0].status==='fulfilled'&&usageSourceValid(docs[0].value)){
        usage=usageEvidence(docs[0].value);
        messages.push('Season usage: Nov 9 snapshot (week coverage unspecified)');
      }else messages.push('Season usage: unavailable; no assumptions');
      if(docs[1].status==='fulfilled'&&weeklySourceValid(docs[1].value)){
        weekly=weeklyEvidence(docs[1].value,Number(week));
        messages.push('Weekly snaps: only observations before W'+week+' (no lookahead)');
      }else messages.push('Weekly snap trends: unavailable; no assumptions');
      privateRows=privateRows.map(p=>{
        const u=usage.get(p.sleeper_id),w=weekly.get(p.sleeper_id);
        // Stable identity + team + position guard; never infer matches by name alone.
        const uOk=u && teamKey(u.team_at_source)===teamKey(p.team) && groupKey(u.position)===p.group;
        const wOk=w && w.team===teamKey(p.team) && w.group===p.group;
        return {...p,usage:uOk?u:null,weekly:wOk?w:null};
      });
      $('fa23EvidenceStatus').textContent=messages.join(' · ')+'. Role observations are descriptive, not projections or dynasty breakout probabilities.';
      render();
    }
    async function importFiles(){
      const token=++requestGeneration;
      privateRows=[];unmatched=[];results.hidden=true;output.replaceChildren();
      $('fa23EvidenceStatus').textContent='Checking public role evidence after private CSV import…';
      const w=Number($('fa22Week').value), s=$('fa22Scoring').value, files=[...$('fa22Files').files];
      if(!Number.isInteger(w)||w<1||w>18){say('Choose the exact NFL week (1–18) for this export.',true);return;}
      if(!s){say('Choose the scoring setting used by 4for4 before importing.',true);return;}
      if(!files.length||files.length>4){say('Choose one to four weekly CSV files.',true);return;}
      if(files.some(f=>!f.name.toLowerCase().endsWith('.csv')||f.size>1500000||f.size<30)){
        say('Select only CSV files, each between 30 bytes and 1.5 MB.',true);return;
      }
      $('fa22Import').disabled=true;
      try{
        const parsed=[];
        for(const file of files){parsed.push(...parseProjectionCsv(await file.text(),file.name));}
        const seen=new Set();
        for(const row of parsed){const k=lookupKey({name:row.name,team:row.team,pos:row.group});
          if(seen.has(k))throw new Error(`Duplicate player across CSV files: ${row.name} (${row.team})`);seen.add(k);}
        say('Matching projections against the current LOG free-agent pool…');
        // Public data only; never transmit anything read from File.text().
        const root='https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/main/';
        const [faResponse,rosResponse]=await Promise.all([
          fetch(root+'data/free_agents.json?t='+Date.now(),{cache:'no-store'}),
          fetch(root+'data/idp_ros_2026_w09.json?t='+Date.now(),{cache:'no-store'})]);
        if(!faResponse.ok||!rosResponse.ok)throw new Error('LOG public evidence is unavailable; no recommendations shown.');
        const [faDoc,rosDoc]=await Promise.all([faResponse.json(),rosResponse.json()]);
        if(!Array.isArray(faDoc.free_agents)||!Array.isArray(rosDoc.records)||
          rosDoc.rank_policy!=='FROZEN_SCREENSHOT_DISPLAY_ONLY')throw new Error('LOG public evidence format mismatch.');
        publicFa=faDoc.free_agents;rosById=new Map();
        for(const row of rosDoc.records){if(row.sleeper_id && Number.isInteger(row.rank)){
          const key=String(row.sleeper_id);
          if(!rosById.has(key))rosById.set(key,[]);
          rosById.get(key).push(row);
        }}
        const index=new Map();
        for(const p of publicFa){const group=groupKey(p.pos);if(!group)continue;
          const k=lookupKey({name:p.name,team:p.team,pos:group});
          if(!index.has(k))index.set(k,[]);index.get(k).push(p);
        }
        // Commit RAM state only after all strict data checks have succeeded.
        const matched=[],missed=[];
        for(const p of parsed){const matches=index.get(lookupKey({name:p.name,team:p.team,pos:p.group}))||[];
          if(matches.length!==1){missed.push(p);continue;}
          const found=matches[0];const ros=(rosById.get(String(found.player_id))||[])
            .find(r=>groupKey(r.group)===p.group&&teamKey(r.team)===p.team)||null;
          matched.push({...p,sleeper_id:String(found.player_id),age:found.age,ros});
        }
        if(token!==requestGeneration)return; // Ignore superseded private CSV imports.
        privateRows=matched;unmatched=missed;week=String(w);scoring=s;
        const synced=Number(faDoc.synced_at),ageHours=Number.isFinite(synced)?(Date.now()/1000-synced)/3600:null;
        const stale=ageHours!==null && (ageHours>48 || ageHours< -2);
        say(`2026 Week ${week} · ${scoring==='log'?'LOG scoring selected (not externally verified)':'Other scoring selected'} · ${matched.length} matched available IDPs / ${parsed.length} projected · ${missed.length} unmatched. ${stale?'CAUTION: Sleeper free-agent snapshot is more than 48h old or incorrectly dated; refresh availability before acting. ':'Sleeper availability is a snapshot, not a waiver guarantee. '}Macri ROS is a Nov 7 ordinal snapshot, NOT a weekly forecast.`);
        render();
        // Supplemental public usage fetches never receive CSV text or player projections.
        void loadRoleEvidence(token);
      } catch(e){if(token===requestGeneration){$('fa23EvidenceStatus').textContent='No validated projections or role evidence active.';
        say(`Import not completed: ${e.message||'Invalid projections'}`,true);}}
      finally{$('fa22Import').disabled=false;}
    }
    $('fa22Import').addEventListener('click',importFiles);
    host.dataset.ready='true';
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
