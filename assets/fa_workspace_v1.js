/* LOG A-FA09R1: additive workspace navigation for the Free Agent Board.
 * Existing IDs, modules, live data, and private browser-local imports remain unchanged.
 * DOM nodes are MOVED, never cloned, so existing event handlers and data remain intact.
 * If a prerequisite is missing, the original stacked page remains usable.
 */
(() => {
  'use strict';
  const panels = [
    {key:'board', label:'All Free Agents', kicker:'Browse', detail:'All positions and original LOG values'},
    {key:'idp', label:'IDP Targets', kicker:'Evaluate', detail:'Waiver rankings and season opportunity'},
    {key:'trends', label:'Weekly Trends', kicker:'Discover', detail:'Rising snaps and weekly defensive stats'},
    {key:'watch', label:'My Watchlist', kicker:'Research', detail:'Private imports and frozen research'},
  ];
  const slug = key => 'fa-ws-' + key;
  const get = selector => document.querySelector(selector);
  const safeHash = () => {
    const found = /^#fa-ws-(board|idp|trends|watch)$/.exec(location.hash);
    return found ? found[1] : 'board';
  };
  function init() {
    const wrap = get('body > .wrap');
    if (!wrap || get('#faWorkspaceNav')) return;
    const privacy = wrap.querySelector('.privacy-note');
    const nodes = {
      controls: wrap.querySelector('section.filter-panel[aria-label="Free agent data filters"]'),
      board: get('#boardWrap'),
      intel: get('#idpiPanel'),
      season: get('#idpoPanel'),
      radar: get('#idptPanel'),
      early: get('#idpePanel'),
      legacy: get('#fa13ResearchPanel')?.closest('section'),
    };
    if (!privacy || Object.values(nodes).some(x => !x) || !nodes.early.contains(nodes.radar)) {
      console.warn('LOG workspace navigation: prerequisite missing; original page retained.');
      return;
    }
    const nav = document.createElement('section');
    nav.id = 'faWorkspaceNav';
    nav.className = 'fa-ws';
    nav.setAttribute('aria-label', 'Free Agent Board workspaces');
    nav.innerHTML = `
      <header class="fa-ws-header">
        <div>
          <div class="fa-ws-eyebrow">Explore the free agent board</div>
          <h2>Choose what you want to do</h2>
        </div>
        <p>One workspace at a time. Your filters and imported files stay in place when switching.</p>
      </header>
      <div class="fa-ws-tabs" role="tablist" aria-label="Board workspace">
        ${panels.map(p => `<button type="button" class="fa-ws-tab" id="${slug(p.key)}-tab" role="tab" aria-controls="${slug(p.key)}-panel" aria-selected="false" tabindex="-1" data-fa-workspace="${p.key}"><span class="fa-ws-tab-kicker">${p.kicker}</span><span class="fa-ws-tab-label">${p.label}</span><span class="fa-ws-tab-detail">${p.detail}</span></button>`).join('')}
      </div>
      <div class="fa-ws-panel" id="fa-ws-board-panel" role="tabpanel" aria-labelledby="fa-ws-board-tab" hidden>
        <div class="fa-ws-intro"><h2>All available players</h2><p>Browse LOG's existing free agent valuations. These are the original calculator values, not the independent IDP scouting scores.</p></div>
        <nav class="fa-ws-positions" aria-label="Jump to free agent position">
          ${['ALL','QB','RB','WR','TE','DL','LB','DB'].map(p => `<button type="button" data-fa-position="${p}" aria-label="Show ${p === 'ALL'?'all positions':p}">${p === 'ALL'?'All':p}</button>`).join('')}
        </nav>
        <p class="fa-ws-jump-hint" id="faWsJumpHint" aria-live="polite">Choose a position to open its player list.</p>
      </div>
      <div class="fa-ws-panel" id="fa-ws-idp-panel" role="tabpanel" aria-labelledby="fa-ws-idp-tab" hidden>
        <div class="fa-ws-intro"><h2>IDP waiver targets</h2><p>Start with the expert ROS waiver comparison; open season opportunity for defensive usage and efficiency. Two independent lenses—not fantasy trade values.</p></div>
      </div>
      <div class="fa-ws-panel" id="fa-ws-trends-panel" role="tabpanel" aria-labelledby="fa-ws-trends-tab" hidden>
        <div class="fa-ws-intro"><h2>Weekly snap trends</h2><p>Public Sleeper data identifies changing playing time. A rising snap signal is not a verified breakout or a projection.</p></div>
      </div>
      <div class="fa-ws-panel" id="fa-ws-watch-panel" role="tabpanel" aria-labelledby="fa-ws-watch-tab" hidden>
        <div class="fa-ws-intro"><h2>My private watchlist</h2><p>Load your private scouting notes and weekly projections locally in this browser. Historical frozen research is below the active watchlist.</p></div>
      </div>`;
    privacy.insertAdjacentElement('afterend', nav);
    const target = key => nav.querySelector('#'+slug(key)+'-panel');
    // Relocate existing LIVE nodes; this preserves identity, events and async renders.
    target('board').append(nodes.controls, nodes.board);
    target('idp').append(nodes.intel, nodes.season);
    target('trends').append(nodes.radar);
    target('watch').append(nodes.early, nodes.legacy);
    const visited = new Set();
    function activate(key, updateUrl = false) {
      if (!panels.some(p => p.key === key)) key = 'board';
      for (const p of panels) {
        const selected = p.key === key;
        const tab = nav.querySelector('#'+slug(p.key)+'-tab');
        const panel = target(p.key);
        tab.setAttribute('aria-selected', String(selected));
        tab.tabIndex = selected ? 0 : -1;
        panel.hidden = !selected;
      }
      if (!visited.has(key)) {
        visited.add(key);
        if (key === 'idp') {
          nodes.intel.querySelector('details').open = true;
          nodes.season.querySelector('details').open = false;
        }
        if (key === 'trends') nodes.radar.open = true;
        if (key === 'watch') nodes.early.querySelector('details').open = true;
      }
      if (updateUrl && history.replaceState) {
        try { history.replaceState(null, '', '#'+slug(key)); } catch (_) { /* Navigation remains usable. */ }
      }
    }
    const tabs = Array.from(nav.querySelectorAll('[role="tab"]'));
    tabs.forEach((tab, i) => {
      tab.addEventListener('click', () => activate(panels[i].key, true));
      tab.addEventListener('keydown', event => {
        if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
        event.preventDefault();
        let next = i;
        if (event.key === 'ArrowRight') next = (i+1)%tabs.length;
        if (event.key === 'ArrowLeft') next = (i+tabs.length-1)%tabs.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = tabs.length-1;
        activate(panels[next].key, true);
        tabs[next].focus();
      });
    });
    nav.querySelectorAll('[data-fa-position]').forEach(button => {
      button.addEventListener('click', () => {
        const targetPos = button.getAttribute('data-fa-position');
        const details = Array.from(nodes.board.querySelectorAll(':scope > details'));
        const chosen = details.find(x => x.querySelector(':scope > summary')?.textContent.trim().split(/\s/)[0] === targetPos);
        const hint = get('#faWsJumpHint');
        if (!chosen) {
          if (hint) hint.textContent = 'Player list still loading. Try again when the data status is ready.';
          return;
        }
        details.forEach(x => { x.open = x === chosen; });
        if (hint) hint.textContent = (targetPos === 'ALL'?'All positions':targetPos)+' selected. Open another position at any time.';
        chosen.scrollIntoView({behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',block:'start'});
      });
    });
    window.addEventListener('hashchange', () => activate(safeHash()));
    activate(safeHash());
    nav.dataset.ready = 'true';
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
})();
