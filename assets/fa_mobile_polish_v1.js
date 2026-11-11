/* LOG A-FA10R1: mobile usability enhancement. No network/storage/projection behavior.
 * Complements rather than replaces the existing workspace and IDP modules. */
(() => {
  'use strict';
  function init() {
    const nav=document.getElementById('faWorkspaceNav');
    const board=document.getElementById('boardWrap');
    if(!nav || !board || document.getElementById('faMobilePolishReady')) return;
    const marker=document.createElement('span');
    marker.id='faMobilePolishReady';
    marker.hidden=true;
    nav.append(marker);

    // Keep position shortcuts in sync even when the canonical board re-renders
    // asynchronously after Sleeper data refreshes. Never change sorting/values.
    const shortcuts=[...nav.querySelectorAll('button[data-fa-position]')];
    const hint=document.getElementById('faWsJumpHint');
    let chosenPosition='ALL';
    const selectedButton=()=>shortcuts.find(b=>b.dataset.faPosition===chosenPosition);
    function label(p){return p==='ALL'?'All positions':p;}
    function applyShortcut({restoreDetails=false}={}) {
      shortcuts.forEach(button=>button.setAttribute('aria-pressed',String(button===selectedButton())));
      if(!restoreDetails)return;
      const details=[...board.children].filter(child=>child.tagName==='DETAILS');
      if(!details.length)return;
      const choice=details.find(d=>{
        const summary=d.querySelector(':scope > summary');
        return summary?.textContent.trim().split(/\s+/)[0]===chosenPosition;
      });
      if(!choice)return;
      for(const item of details)item.open=(item===choice);
      if(hint)hint.textContent=label(chosenPosition)+' selected. Tap another position to switch lists.';
    }
    // Capture before existing shortcut handler; that handler can still scroll.
    for(const button of shortcuts){
      button.addEventListener('click',()=>{
        chosenPosition=button.dataset.faPosition;
        applyShortcut();
      },{capture:true});
    }
    if(shortcuts.length===8){
      applyShortcut();
      const observer=new MutationObserver(records=>{
        if(records.some(record=>record.type==='childList'&&record.target===board))applyShortcut({restoreDetails:true});
      });
      observer.observe(board,{childList:true});
    }

    // Expose the two existing IDP research lenses directly, without adding
    // duplicate content or deleting the users' original expandable panels.
    const idpPanel=document.getElementById('fa-ws-idp-panel');
    const intel=document.getElementById('idpiPanel')?.querySelector(':scope > details');
    const season=document.getElementById('idpoPanel')?.querySelector(':scope > details');
    if(idpPanel && intel && season && !idpPanel.querySelector('.fa-mobile-focus-row')){
      const menu=document.createElement('div');
      menu.className='fa-mobile-focus-row';
      menu.setAttribute('aria-label','Choose IDP research lens');
      menu.innerHTML='<button type="button" data-idp-lens="ranks">Expert waiver rankings</button><button type="button" data-idp-lens="season">Season usage & efficiency</button>';
      idpPanel.querySelector('.fa-ws-intro')?.insertAdjacentElement('afterend',menu);
      const buttons=[...menu.querySelectorAll('button')];
      function mark(){
        const active=intel.open && !season.open?'ranks':season.open && !intel.open?'season':null;
        for(const btn of buttons)btn.setAttribute('aria-pressed',String(btn.dataset.idpLens===active));
      }
      for(const b of buttons){b.addEventListener('click',()=>{
        intel.open=b.dataset.idpLens==='ranks';
        season.open=b.dataset.idpLens==='season';
        mark();
      });}
      intel.addEventListener('toggle',mark);
      season.addEventListener('toggle',mark);
      mark();
    }

    // Private imports are designed to be ephemeral. Explain the empty state
    // clearly, without persisting subscriber files in GitHub or local storage.
    const watchPanel=document.getElementById('fa-ws-watch-panel');
    const watchCount=document.getElementById('idpeCount');
    if(watchPanel && watchCount && !document.getElementById('faMobileWatchNotice')){
      const notice=document.createElement('p');
      notice.id='faMobileWatchNotice';
      notice.className='fa-mobile-watch-notice';
      notice.setAttribute('role','note');
      notice.textContent='Private watchlists are not saved after a page refresh or new browser tab. Re-select your watch JSON to restore the players; your subscriber projections are never uploaded.';
      watchPanel.querySelector('.fa-ws-intro')?.insertAdjacentElement('afterend',notice);
      function syncWatch(){
        const s=watchCount.textContent||'';
        const loaded=/\b([1-9]\d*)\s+of\s+\d+\b/.test(s);
        notice.hidden=loaded;
      }
      new MutationObserver(syncWatch).observe(watchCount,{childList:true,subtree:true,characterData:true});
      syncWatch();
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
