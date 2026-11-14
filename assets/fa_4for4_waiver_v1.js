/* LOG A-FA22R2: owner-only 4for4 weekly IDP waiver discovery.
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
        <h3>4for4 waiver finder</h3>
        <p>Find available DL, LB and DB candidates using <strong>this week's</strong> 4for4 projections, then check their separate Macri rest-of-season rank. No combined score or FV adjustment.</p></div>
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
    const pNum=x=>Number.isFinite(x)?x.toFixed(1):'—';
    const lookupKey=x=>`${nameKey(x.name)}|${teamKey(x.team)}|${groupKey(x.pos||x.group)}`;
    function say(message,error=false){status.textContent=message;status.classList.toggle('fa22-error',error);}
    function clear(){privateRows=[];unmatched=[];week='';scoring='';results.hidden=true;output.replaceChildren();
      $('fa22Files').value='';say('Private projections cleared from this browser tab.');}
    $('fa22Clear').addEventListener('click',clear);
    for(const id of ['fa22Week','fa22Scoring','fa22Files']) {
      $(id).addEventListener('change',()=>{if(privateRows.length){privateRows=[];unmatched=[];results.hidden=true;output.replaceChildren();say('Inputs changed. Analyze the selected weekly CSV again before using any results.');}});
    }
    function render() {
      if (!privateRows.length && !unmatched.length) {results.hidden=true;return;}
      results.hidden=false;
      const group=$('fa22Group').value,focus=$('fa22Focus').value;
      let rows=privateRows.filter(x=>(group==='ALL'||group===x.group) &&
        (focus!=='young'||(Number.isFinite(x.age) && x.age<=25)) &&
        (focus!=='ros'||!!x.ros));
      const order={DL:0,LB:1,DB:2};
      rows.sort((a,b)=>order[a.group]-order[b.group]||b.pts-a.pts||a.name.localeCompare(b.name));
      // Every group must be represented in the All IDP view, not only the long DL pool.
      const shown=group==='ALL'
        ? ['DL','LB','DB'].flatMap(g=>rows.filter(x=>x.group===g).slice(0,15))
        : rows.slice(0,50);
      const parts=[];let last='';
      for(const x of shown){
        if(x.group!==last){last=x.group;parts.push(`<h4 class="fa22-group-title">${escape(last)} · Weekly projections</h4>`);}
        const ros=x.ros ? `${escape(x.ros.group)} #${x.ros.rank} (Nov 7 ROS)` : 'No matching Macri ROS rank';
        const stat=[x.snap!==null?`Projected snaps ${pNum(x.snap)}%`:null,
          x.tackles!==null?`Tackles ${pNum(x.tackles)}`:null,
          x.assists!==null?`Assists ${pNum(x.assists)}`:null,
          x.sacks!==null?`Sacks ${pNum(x.sacks)}`:null].filter(Boolean).join(' · ');
        const ranks=[x.groupRank!==null?`${x.group} #${x.groupRank}`:null,
          x.positionRank!==null?`${x.rawPos} #${x.positionRank}`:null].filter(Boolean).join(' · ');
        const vor=x.vor===null?'Not provided':`${x.vor>0?'+':''}${pNum(x.vor)}`;
        parts.push(`<article class="fa22-player"><div class="fa22-player-main"><strong>${escape(x.name)}</strong><div class="fa22-meta">${escape(x.team)} · ${escape(x.rawPos)} · Age ${x.age ?? '—'} · vs ${escape(x.opp||'—')}</div><div class="fa22-meta">${escape(ranks||'4for4 positional ranks not supplied')} · VOR ${escape(vor)}</div><div class="fa22-meta">${escape(stat||'Detailed snap/tackle projections not included in this export')}</div><div class="fa22-ros">Macri: ${ros}</div></div><div class="fa22-score"><strong>${pNum(x.pts)}</strong><span>4for4 FF pts</span></div></article>`);
      }
      output.innerHTML=parts.join('') || '<p class="fa22-empty">No available players match this selection.</p>';
      $('fa22UnmatchedTitle').textContent=`Not matched to available LOG players (${unmatched.length})`;
      $('fa22UnmatchedList').textContent=unmatched.length ? unmatched.slice(0,50).map(x=>`${x.name} · ${x.team} · ${x.group}`).join(' | ') : 'All valid projection rows matched LOG free agents.';
    }
    $('fa22Group').addEventListener('change',render);
    $('fa22Focus').addEventListener('change',render);
    async function importFiles(){
      privateRows=[];unmatched=[];results.hidden=true;output.replaceChildren();
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
        privateRows=matched;unmatched=missed;week=String(w);scoring=s;
        say(`2026 Week ${week} · ${scoring==='log'?'LOG scoring selected at import':'Other scoring selected'} · ${matched.length} matched available IDPs / ${parsed.length} projected · ${missed.length} not matched to available pool. 4for4 VOR and ordinal ranks are source-specific; Macri ROS is a separate Nov 7 snapshot, NOT a weekly forecast.`);
        render();
      } catch(e){say(`Import not completed: ${e.message||'Invalid projections'}`,true);}
      finally{$('fa22Import').disabled=false;}
    }
    $('fa22Import').addEventListener('click',importFiles);
    host.dataset.ready='true';
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
