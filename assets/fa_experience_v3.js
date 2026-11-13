/* A-FA19R1 + A-FA20R1: LOG Free Agent Board experience refresh.
 * UI-only. Existing valuation logic, research models, rankings, private imports,
 * IDs, and event handlers are not replaced. Source modules keep their own state.
 */
(() => {
  'use strict';
  const choices = {
    board: {label:'Players', heading:'Free agents'},
    idp: {label:'Targets', heading:'IDP targets'},
    trends: {label:'Trends', heading:'Weekly trends'},
    startsit: {label:'Start / Sit', heading:'Choose your starters'},
    watch: {label:'Watch', heading:'My watchlist'}
  };
  function init() {
    const nav = document.getElementById('faWorkspaceNav');
    const wrap = nav?.closest('.wrap');
    if (!wrap || !nav || nav.dataset.fa19Ready === 'true') return;
    const mustHave = ['fa-ws-board-panel','fa-ws-idp-panel','fa-ws-trends-panel',
                      'fa-ws-startsit-panel','fa-ws-watch-panel','boardWrap'];
    if (mustHave.some(id => !document.getElementById(id))) return;
    nav.dataset.fa19Ready = 'true';
    wrap.classList.add('fa19-experience');
    nav.setAttribute('aria-label','Free Agent Board');

    // Existing tab listeners stay wired to their original keys and DOM order.
    const tabs = nav.querySelector('.fa-ws-tabs');
    for (const [key, config] of Object.entries(choices)) {
      const tab = nav.querySelector(`[data-fa-workspace="${key}"]`);
      const title = document.querySelector(`#fa-ws-${key}-panel .fa-ws-intro h2`);
      if (tab) {
        tab.querySelector('.fa-ws-tab-label').textContent = config.label;
        tab.title = config.heading;
        tab.setAttribute('aria-label', config.heading);
        // Iconography uses characters only, no external font or image payload.
        const icon = document.createElement('span');
        icon.className = 'fa19-tab-icon';
        icon.setAttribute('aria-hidden','true');
        icon.textContent = ({board:'▦',idp:'◎',trends:'↗',startsit:'✓',watch:'☆'})[key];
        tab.prepend(icon);
      }
      if (title) title.textContent = config.heading;
    }
    if (tabs) {
      const ensureVisible = tab => {
        const left = tab.offsetLeft - tabs.offsetLeft - (tabs.clientWidth - tab.clientWidth)/2;
        if (Math.abs(left - tabs.scrollLeft) > 30) {
          tabs.scrollTo({left:Math.max(0,left),behavior:window.matchMedia?.('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
        }
      };
      tabs.addEventListener('click', e => {
        const button = e.target.closest('[data-fa-workspace]');
        if (button) ensureVisible(button);
      });
      window.addEventListener('hashchange',() => {
        const current=tabs.querySelector('[aria-selected="true"]');
        if(current) ensureVisible(current);
      });
    }

    // Keep the security caveat readable but not a huge mandatory paragraph.
    // Existing privacy text is MOVED (not deleted), and remains discoverable.
    const originalPrivacy=wrap.querySelector('.privacy-note');
    if (originalPrivacy && !document.getElementById('fa19Privacy')) {
      const details=document.createElement('details');
      details.id='fa19Privacy';
      details.className='fa19-privacy';
      const summary=document.createElement('summary');
      summary.textContent='Public site · keep subscriber research private';
      details.append(summary);
      originalPrivacy.replaceWith(details);
      details.append(originalPrivacy);
    }

    // The main site header remains sticky; this second row sticks beneath it.
    const shell=document.querySelector('.log-app-shell');
    const updateTop=()=>{
      const height=shell?.getBoundingClientRect().height||0;
      nav.style.setProperty('--fa19-stick-top',Math.ceil(Math.max(0,height))+'px');
    };
    updateTop();
    if (shell && typeof ResizeObserver!=='undefined') new ResizeObserver(updateTop).observe(shell);
    else window.addEventListener('resize',updateTop,{passive:true});

    // Real name/team search across currently loaded free agents. No API calls,
    // no changes to values or sorting; it only hides DOM rows while searching.
    const panel=document.getElementById('fa-ws-board-panel');
    const board=document.getElementById('boardWrap');
    const positionNav=panel.querySelector('.fa-ws-positions');
    const search=document.createElement('div');
    search.className='fa19-player-search';
    search.innerHTML='<label for="fa19PlayerQuery">Find a player</label><div class="fa19-search-field"><input id="fa19PlayerQuery" type="search" placeholder="Search name or NFL team" autocomplete="off" spellcheck="false" enterkeyhint="search"><button type="button" id="fa19SearchClear" aria-label="Clear player search">Clear</button></div><span id="fa19PlayerFeedback" aria-live="polite"></span>';
    positionNav?.insertAdjacentElement('beforebegin',search);
    const field=search.querySelector('#fa19PlayerQuery');
    const feedback=search.querySelector('#fa19PlayerFeedback');
    const clear=search.querySelector('#fa19SearchClear');
    let selectedPosition='ALL';
    const details=()=>Array.from(board.children).filter(x=>x.tagName==='DETAILS');
    const normal=x=>String(x||'').trim().toLocaleLowerCase();
    function applySearch(){
      const query=normal(field.value);
      const sections=details();
      const selected=sections.find(x=>normal(x.querySelector(':scope > summary')?.textContent).split(/\s+/)[0]===normal(selectedPosition));
      if (!sections.length || !selected) {feedback.textContent='Loading players…';return;}
      const rows=Array.from(board.querySelectorAll('.row'));
      if (!query) {
        rows.forEach(row=>row.hidden=false);
        feedback.textContent='';
        return;
      }
      sections.forEach(x=>x.open=(x===selected));
      let found=0,shown=0;
      for(const row of rows){
        const matched=selected.contains(row) && normal((row.querySelector('.row-title')?.textContent||'')+' '+(row.querySelector('.row-meta')?.textContent||'')).includes(query);
        if(matched)found++;
        const show=matched&&shown<50;
        if(show)shown++;
        row.hidden=!show;
      }
      feedback.textContent=found===0?`No ${selectedPosition==='ALL'?'player':selectedPosition} matches`:`${found} match${found===1?'':'es'}${found>50?' · first 50 shown':''}`;
    }
    field.addEventListener('input',applySearch);
    clear.addEventListener('click',()=>{field.value='';applySearch();field.focus();});
    field.addEventListener('keydown', e => {
      if(e.key==='Escape'){field.value='';applySearch();field.blur();}
      if(e.key==='Enter'){e.preventDefault();document.getElementById('boardWrap')?.scrollIntoView({block:'start',behavior:'smooth'});field.blur();}
    });
    positionNav?.addEventListener('click',e=>{
      const button=e.target.closest('[data-fa-position]');
      if(!button)return;
      selectedPosition=button.dataset.faPosition;
      if(field.value) applySearch();
    },{capture:true});
    // renderBoard() reconstructs board nodes after coverage setting/data sync.
    new MutationObserver(records=>{
      if(records.some(x=>x.type==='childList'&&x.target===board))applySearch();
    }).observe(board,{childList:true});
    applySearch();

    // Shorten the explanatory text without removing legal/private controls.
    const watchNotice=document.getElementById('faMobileWatchNotice');
    if (watchNotice) watchNotice.textContent='Private watchlists require re-import after refreshing this page.';
    const startSearch=document.querySelector('#fa-ws-startsit-panel .fa-ss-selected-heading h3');
    if(startSearch && startSearch.firstChild?.nodeType===Node.TEXT_NODE)startSearch.firstChild.textContent='Selected players ';

    // Make current section easy to locate even when returning via deep link.
    const active=tabs?.querySelector('[aria-selected="true"]');
    if(active && active.offsetLeft>tabs.clientWidth)tabs.scrollLeft=active.offsetLeft;
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
