/* LOG A-FA15R1 — Private weekly Woellert matchup context for Start/Sit.
 * No subscriber tables in public assets. Strict week join, read-only context.
 * Does not change rankings, projections, lineup selection, or player valuation.
 */
(() => {
  'use strict';
  function init() {
    const app = document.getElementById('faSsApp');
    if (!app || document.getElementById('faMatchupV1')) return;
    const $ = id => document.getElementById(id);
    const rankStatus = $('faSsStatus');
    const results = $('faSsResults');
    const importBox = app.querySelector('.fa-ss-import');
    if (!rankStatus || !results || !importBox) return;
    const escape = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const tidy = x => String(x||'').trim().toUpperCase();
    const codes = ['ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE','DAL','DEN','DET','GB','HOU','IND','JAX','KC','LAC','LAR','LV','MIA','MIN','NE','NO','NYG','NYJ','PHI','PIT','SEA','SF','TB','TEN','WAS'];
    const codeSet = new Set(codes);
    const roles = ['LB','EDGE','DT','OUTSIDE_CB','SLOT_CB','S'];
    const positionNames = {LB:'Linebacker',EDGE:'EDGE',DT:'Defensive tackle',S:'Safety',OUTSIDE_CB:'Outside corner',SLOT_CB:'Slot corner'};
    const storeName='LOG_Private_Woellert_Matchups_v1';
    const sourceClass='PRIVATE_USER_PROVIDED_MATCHUP_REFERENCE_NOT_FOR_PUBLIC_GITHUB';
    let source=null, savedSnapshots=new Map(), schedule=new Map(), manualOpponents=new Map();
    let rankingWeek=null, rankingSeason=2026, saving=false;

    const box = document.createElement('section');
    box.id='faMatchupV1';box.className='fa-mu';
    box.innerHTML=`<div class="fa-mu-header"><div><strong>Weekly matchup evidence</strong><span id="faMuBadge" class="fa-mu-badge">Checking private data…</span></div><p id="faMuStatus" role="status">Matchup tables stay in this browser and are never uploaded to GitHub.</p></div>
      <details id="faMuImportDetails" class="fa-mu-import"><summary>Load / replace Woellert matchup tables for the week</summary>
      <p>Choose the private structured JSON created from your weekly matchup screenshots. Import just once per week; it is restored on this device. This is independent of the expert rankings and does not alter any projection.</p>
      <label for="faMuFile">Private weekly matchup JSON</label><input id="faMuFile" type="file" accept=".json,application/json">
      <button id="faMuForget" type="button" hidden>Forget saved matchup tables for this week</button></details>`;
    importBox.insertAdjacentElement('afterend',box);
    const badge=$('faMuBadge'), status=$('faMuStatus'), file=$('faMuFile'), forget=$('faMuForget'), detail=$('faMuImportDetails');
    function check(c,msg){if(!c)throw Error(msg);}
    const finite = x => typeof x==='number' && Number.isFinite(x);
    function validate(doc) {
      check(doc&&doc.schema_version===1&&doc.classification===sourceClass,'Not a private LOG matchup research file');
      check(Number.isInteger(doc.season)&&doc.season>=2026&&doc.season<=2100,'Invalid season');
      check(Number.isInteger(doc.analysis_week)&&doc.analysis_week>=1&&doc.analysis_week<=18,'Invalid week');
      check(doc.private===true&&doc.do_not_publish_to_github===true&&doc.derived_numeric_adjustment_authorized===false,'Research privacy/policy mismatch');
      check(doc.teams&&typeof doc.teams==='object'&&Object.keys(doc.teams).length===32,'Expected exactly 32 NFL opponent tables');
      check(codes.every(c=>Object.hasOwn(doc.teams,c)),'Team names must use standard NFL codes');
      check(doc.league_averages&&typeof doc.league_averages==='object','Missing league averages');
      for(const item of ['tackles_allowed_per_game','tackle_rate_allowed_pct']) {
        const avg=doc.league_averages[item];
        check(avg&&roles.every(k=>finite(avg[k])&&avg[k]>0&&avg[k]<100),'Invalid league average for '+item);
        for(const c of codes){const values=doc.teams[c][item];
          check(values&&roles.every(k=>finite(values[k])&&values[k]>=0&&values[k]<=100),'Invalid '+c+' '+item);
        }
      }
      check(finite(doc.league_averages.overall_pressure_rate_allowed_pct)&&doc.league_averages.overall_pressure_rate_allowed_pct>0,'Invalid pressure average');
      for(const c of codes){
        const row=doc.teams[c];
        check(finite(row.overall_pressure_rate_allowed_pct)&&row.overall_pressure_rate_allowed_pct>=0&&row.overall_pressure_rate_allowed_pct<=100,'Invalid pressure data for '+c);
        check(row.offense&&finite(row.offense.run_pct)&&row.offense.run_pct>=0&&row.offense.run_pct<=100&&finite(row.offense.plays_per_minute)&&row.offense.plays_per_minute>0&&row.offense.plays_per_minute<4,'Invalid offensive context for '+c);
      }
      return doc;
    }
    function dbOpen(){return new Promise((resolve,reject)=>{
      if(!window.indexedDB){reject(Error('Browser does not support private storage'));return;}
      const request=indexedDB.open(storeName,1);
      request.onupgradeneeded=()=>{if(!request.result.objectStoreNames.contains('weekly'))request.result.createObjectStore('weekly')};
      request.onerror=()=>reject(request.error||Error('Private database unavailable'));
      request.onsuccess=()=>resolve(request.result);
    });}
    async function dbAll(){const db=await dbOpen();return new Promise((resolve,reject)=>{
      const tx=db.transaction('weekly','readonly'),req=tx.objectStore('weekly').getAll();
      req.onsuccess=()=>resolve(req.result||[]);req.onerror=()=>reject(req.error);
      tx.oncomplete=()=>db.close();tx.onerror=()=>{db.close();reject(tx.error)};
    });}
    async function dbPut(doc){const db=await dbOpen();return new Promise((resolve,reject)=>{
      const tx=db.transaction('weekly','readwrite');tx.objectStore('weekly').put(doc,`${doc.season}-W${doc.analysis_week}`);
      tx.oncomplete=()=>{db.close();resolve()};tx.onerror=()=>{db.close();reject(tx.error)};
    });}
    async function dbRemove(doc){const db=await dbOpen();return new Promise((resolve,reject)=>{
      const tx=db.transaction('weekly','readwrite');tx.objectStore('weekly').delete(`${doc.season}-W${doc.analysis_week}`);
      tx.oncomplete=()=>{db.close();resolve()};tx.onerror=()=>{db.close();reject(tx.error)};
    });}
    function detectRankWeek(){
      const text=rankStatus.textContent||'';
      // Do not misinterpret a generic "activate Week 10" prompt as loaded rankings.
      const loaded=/\bprivate consensus\s+(?:activated|restored|imported)/i.test(text);
      const match=text.match(/\bWeek\s+(\d{1,2})\b/i);
      if(!loaded||!match){
        // The comparison tool may temporarily display a selection-limit message;
        // never lose the loaded week because a status label changed.
        if(rankingWeek!==null && $('faSsForget')?.hidden===false) return rankingWeek;
        return null;
      }
      const n=Number(match[1]);return n>=1&&n<=18?n:null;
    }
    async function getRankSchedule(){
      // Only read owner-local IndexedDB; never request rankings from GitHub or a server.
      try{
        const request=indexedDB.open('LOG_Private_StartSit_Weekly_2026_v1',1);
        const docs=await new Promise((resolve,reject)=>{
          request.onupgradeneeded=()=>{if(!request.result.objectStoreNames.contains('snapshots'))request.result.createObjectStore('snapshots')};
          request.onerror=()=>reject(request.error);
          request.onsuccess=()=>{
            const db=request.result;
            if(!db.objectStoreNames.contains('snapshots')){db.close();resolve([]);return;}
            const tx=db.transaction('snapshots','readonly'),get=tx.objectStore('snapshots').getAll();
            get.onsuccess=()=>resolve(get.result||[]);get.onerror=()=>reject(get.error);
            tx.oncomplete=()=>db.close();
          };
        });
        const doc=docs.find(d=>d&&d.season===rankingSeason&&d.week===rankingWeek&&Array.isArray(d.records));
        const candidates=new Map();
        for(const row of doc?.records||[]){const p=row.projection;
          if(!p||!codeSet.has(tidy(p.team))||!codeSet.has(tidy(p.opponent)))continue;
          const team=tidy(p.team),opp=tidy(p.opponent);
          if(!candidates.has(team))candidates.set(team,new Set());
          candidates.get(team).add(opp);
        }
        schedule=new Map();
        for(const [team,opponents] of candidates){if(opponents.size===1){const opp=[...opponents][0];if(team!==opp)schedule.set(team,opp)}}
      } catch (_) {schedule=new Map();}
      render();
    }
    function sync(){
      rankingWeek=detectRankWeek();
      source=rankingWeek===null?null:savedSnapshots.get(`${rankingSeason}-W${rankingWeek}`)||null;
      if(rankingWeek===null){badge.textContent='Rankings not loaded';badge.dataset.state='unverified';status.textContent='Activate your private weekly expert consensus before using matchup data. Saved matchup data is retained.';}
      else if(!source){badge.textContent=`Week ${rankingWeek} matchup missing`;badge.dataset.state='missing';status.textContent=`Week ${rankingWeek} expert rankings detected. Load Week ${rankingWeek} matchup tables once to see opponent context; other weeks cannot be substituted.`;}
      else {badge.textContent=`Week ${rankingWeek} · matchup loaded`;badge.dataset.state='ready';status.textContent=`2026 Week ${rankingWeek} matchup evidence saved privately. Same-week expert rankings and matchup tables. Statistics are opponent season-to-date tendencies, not projected points.`;}
      forget.hidden=!source;
      render();
    }
    function fmt(n,d=1){return finite(n)?n.toFixed(d):'—';}
    function pctDiff(n,baseline){return baseline>0?(n/baseline-1)*100:null;}
    function labelVolume(n){return n>=10?'Higher':n<=-10?'Lower':'Near-average';}
    function matchupFor(opponent,role){
      const r=source.teams[opponent],avg=source.league_averages;
      const taps=r.tackles_allowed_per_game[role],base=avg.tackles_allowed_per_game[role];
      const rate=r.tackle_rate_allowed_pct[role],leagueRate=avg.tackle_rate_allowed_pct[role];
      const delta=pctDiff(taps,base);
      return {taps,base,rate,leagueRate,delta,label:labelVolume(delta)};
    }
    function roleRow(opponent,role){const x=matchupFor(opponent,role),delta=fmt(x.delta,0);
      const sign=x.delta>0?'+':'';
      return `<div class="fa-mu-role"><span>${escape(positionNames[role])}</span><strong>${fmt(x.taps)} tackles/game allowed <small>to the full position group; league avg ${fmt(x.base)} (${sign}${delta}%)</small></strong><span>${fmt(x.rate)}% tackle rate <small>vs ${fmt(x.leagueRate)}% league avg</small></span></div>`;
    }
    const roleOf = card => {
      const t=card.querySelector('.fa-ss-result-top small')?.textContent||'';
      const p=t.match(/\b(LB|EDGE|DT|CB|S)\s*→/);
      return p?.[1]||null;
    };
    function opponentFor(team){return manualOpponents.get(team)||schedule.get(team)||null;}
    function matchCard(card){
      const parent=card.querySelector('.fa-ss-result-top');
      if(!parent)return;
      const team=tidy(parent.querySelector('small')?.textContent.split(' · ')[0]);
      const name=parent.querySelector('strong')?.textContent||'Player';
      const role=roleOf(card);
      if(!codeSet.has(team))return;
      const out=document.createElement('section');out.className='fa-mu-evidence';out.setAttribute('aria-label','Private matchup evidence for '+name);
      const opp=opponentFor(team);
      if(!opp){
        out.innerHTML=`<div class="fa-mu-evidence-head"><strong>Week ${rankingWeek} opponent: not verified</strong></div><p>There is no validated opponent in the saved Week ${rankingWeek} ranking projections for ${escape(team)}. Choose the opponent manually; we will not guess.</p><label>Opponent (manual selection)<select data-fa-mu-team="${escape(team)}"><option value="">Select opponent</option>${codes.filter(c=>c!==team).map(c=>`<option value="${c}">${c}</option>`).join('')}</select></label>`;
      } else {
        const manual=manualOpponents.has(team);
        out.innerHTML=`<div class="fa-mu-evidence-head"><strong>Week ${rankingWeek} matchup: ${escape(team)} vs ${escape(opp)}</strong><small>${manual?'Manually selected':'Inferred from your private Woellert projection schedule'}</small></div>`;
        const roles=role==='CB'?['OUTSIDE_CB','SLOT_CB']:role&&['S','LB','EDGE','DT'].includes(role)?[role]:[];
        if(!roles.length)out.insertAdjacentHTML('beforeend','<p>Defensive alignment is unresolved; no specific tackle rate assigned.</p>');
        else {
          out.insertAdjacentHTML('beforeend','<div class="fa-mu-roles">'+roles.map(r=>roleRow(opp,r)).join('')+'</div>');
          const row=source.teams[opp],league=source.league_averages;
          if(role==='EDGE'||role==='DT'){
            out.insertAdjacentHTML('beforeend',`<p><strong>Team pressure context:</strong> ${fmt(row.overall_pressure_rate_allowed_pct)}% pressure rate allowed (league ${fmt(league.overall_pressure_rate_allowed_pct)}%). This is team-wide, not a player sack projection.</p>`);
          } else if(role==='S'||role==='LB'||role==='CB'){
            out.insertAdjacentHTML('beforeend',`<p><strong>Offensive context:</strong> ${fmt(row.offense.run_pct)}% run rate, ${fmt(row.offense.plays_per_minute,2)} plays/minute. ${role==='CB'?'Outside and slot corners are shown separately because the player’s actual coverage alignment is not provided.':'These are matchup tendencies, not a guaranteed tackle volume.'}</p>`);
          }
        }
        out.insertAdjacentHTML('beforeend','<p class="fa-mu-noadjust">Research context only · No multiplier or adjustment to existing LOG point projections or start recommendations.</p>');
      }
      card.appendChild(out);
    }
    let active=false;
    function render(){
      if(active)return;
      active=true;
      try{
        results.querySelectorAll('.fa-mu-evidence').forEach(e=>e.remove());
        if(!source||!rankingWeek)return;
        const heading=results.querySelector('.fa-ss-result-head h3')?.textContent||'';
        if(!new RegExp(`\\bWeek\\s+${rankingWeek}\\b`,'i').test(heading))return;
        results.querySelectorAll('.fa-ss-result-card').forEach(matchCard);
      }finally{active=false;}
    }
    // Core Start/Sit replaces the results' top-level children on each comparison.
    // Watching only direct children avoids an observer loop when adding context cards.
    new MutationObserver(()=>render()).observe(results,{childList:true});
    new MutationObserver(()=>{
      const before=rankingWeek;sync();if(before!==rankingWeek)getRankSchedule();
    }).observe(rankStatus,{childList:true,characterData:true,subtree:true});
    results.addEventListener('change',e=>{
      const select=e.target.closest?.('[data-fa-mu-team]');
      if(!select)return;
      const team=tidy(select.dataset.faMuTeam),opp=tidy(select.value);
      if(codeSet.has(team)&&codeSet.has(opp)&&team!==opp){manualOpponents.set(team,opp);render();}
    });
    file.addEventListener('change',async()=>{
      const f=file.files?.[0];
      try{
        check(f&&f.size>50&&f.size<200000,'Select a private weekly matchup JSON under 200 KB');
        const doc=validate(JSON.parse(await f.text()));
        if(rankingWeek!==null)check(doc.analysis_week===rankingWeek&&doc.season===rankingSeason,`Rankings are Week ${rankingWeek}, but this is Week ${doc.analysis_week}. Import matching weekly tables.`);
        let persisted=true;
        try{await dbPut(doc)}catch(_){persisted=false;}
        savedSnapshots.set(`${doc.season}-W${doc.analysis_week}`,doc);
        detail.open=false;sync();
        if(!persisted)status.textContent+=' Browser storage was blocked; this import lasts for this tab only.';
      }catch(e){badge.textContent='Matchup import rejected';badge.dataset.state='error';status.textContent=String(e.message||e);}
      file.value='';
    });
    forget.addEventListener('click',async()=>{
      if(!source||!confirm(`Remove private 2026 Week ${rankingWeek} matchup data from this browser?`))return;
      try{await dbRemove(source);savedSnapshots.delete(`${source.season}-W${source.analysis_week}`);sync();}
      catch(e){status.textContent='Unable to erase private data: '+String(e.message||e);}
    });
    (async()=>{
      try{for(const doc of await dbAll()){
        try{validate(doc);savedSnapshots.set(`${doc.season}-W${doc.analysis_week}`,doc)}catch(_){/* Ignore corrupted prior entries. */}
      }}catch(e){status.textContent='Private browser storage unavailable. You can still import the matchup JSON for this tab.';}
      sync();await getRankSchedule();
    })();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
