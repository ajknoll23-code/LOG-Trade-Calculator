#!/usr/bin/env python3
"""Add LOG IDP season-usage opportunity panel without altering existing model code."""
import json
from pathlib import Path

BOARD = Path('free-agent-board.html')
JS = Path('assets/idp_opportunity_v1.js')
CSS = Path('assets/idp_opportunity_v1.css')
DATA = Path('data/idp_usage_2026_season.json')

PANEL = '''<!-- IDP_OPPORTUNITY_V1_PANEL_START -->
<section id="idpoPanel" aria-label="IDP opportunity dashboard" data-feature="research-only">
  <details open>
    <summary>IDP Opportunity Center <span id="idpoCount">(loading season data)</span></summary>
    <div class="idpo-wrap">
      <p class="idpo-subtitle">Find available IDP players through defensive usage and tackle efficiency. Season snapshot and the IDP Show's frozen ROS rankings are separate evidence. No valuation or projection changes.</p>
      <div class="idpo-toolbar">
        <label class="idpo-control" for="idpoPosition">Position
          <select id="idpoPosition"><option value="LB">Linebacker</option><option value="S">Safety</option><option value="CB">Cornerback</option><option value="ED">EDGE</option><option value="DI">Interior DL</option><option value="ALL">All (separate groups)</option></select>
        </label>
        <label class="idpo-control" for="idpoScope">Show
          <select id="idpoScope"><option value="available">LOG free agents</option><option value="mine">My roster</option><option value="all">All studied</option></select>
        </label>
        <label class="idpo-control" for="idpoLens">Sorting lens
          <select id="idpoLens"><option value="contender">Win now</option><option value="dynasty">Dynasty</option></select>
        </label>
      </div>
      <label class="idpo-control" for="idpoSearch">Search player
        <input id="idpoSearch" type="search" placeholder="Filter by name" autocomplete="off">
      </label>
      <div class="idpo-checks">
        <label><input type="checkbox" id="idpoYoung"> Age 25 or younger</label>
        <label><input type="checkbox" id="idpoStrong"> Strong tackle grade or higher</label>
      </div>
      <p class="idpo-status" id="idpoStatus" role="status">Loading verified season usage and league availability…</p>
      <p class="idpo-note" id="idpoNote"></p>
      <div class="idpo-grid" id="idpoItems" aria-live="polite"></div>
      <button type="button" class="idpo-more" id="idpoMore" hidden>Show more</button>
    </div>
  </details>
</section>
<!-- IDP_OPPORTUNITY_V1_PANEL_END -->
'''
STYLE='<!-- IDP_OPPORTUNITY_V1_STYLE --><link rel="stylesheet" href="assets/idp_opportunity_v1.css">\n'
SCRIPT='<!-- IDP_OPPORTUNITY_V1_SCRIPT --><script src="assets/idp_opportunity_v1.js" defer></script>\n'


def insert_once(text,anchor,insertion):
    if text.count(anchor)!=1:
        raise RuntimeError('Anchor missing or duplicated: '+anchor)
    return text.replace(anchor,insertion+anchor,1)


def main():
    if not BOARD.exists() or not JS.exists() or not CSS.exists():
        raise RuntimeError('Required board and assets must exist')
    sample=json.loads(DATA.read_text(encoding='utf-8'))
    if sample.get('schema_version')!=1 or sample.get('counts',{}).get('players')!=436 or sample.get('policy')!='READ_ONLY_RESEARCH_NOT_FV_OR_PROJECTION':
        raise RuntimeError('A-FA04R1 data import has not been applied; refusing dashboard install')
    board=BOARD.read_text(encoding='utf-8')
    markers=['IDP_OPPORTUNITY_V1_PANEL_START','IDP_OPPORTUNITY_V1_PANEL_END',
             'IDP_OPPORTUNITY_V1_STYLE','IDP_OPPORTUNITY_V1_SCRIPT']
    existing=[x for x in markers if x in board]
    if existing:
        if len(existing)==len(markers) and all(board.count(x)==1 for x in markers):
            print('Dashboard markers already present. No HTML re-injection performed.')
            return
        raise RuntimeError('Partial/duplicate opportunity feature found; refusing unsafe modification')
    before=board
    board=insert_once(board,'<!-- IDP_INTEL_V1_PANEL_START -->',PANEL)
    board=insert_once(board,'<!-- IDP_INTEL_V1_STYLE -->',STYLE)
    board=insert_once(board,'<!-- IDP_INTEL_V1_SCRIPT -->',SCRIPT)
    for marker in markers:
        if board.count(marker)!=1:raise RuntimeError('Insertion marker not unique: '+marker)
    if board.count('id="idpoPanel"')!=1 or board.count('id="idpiPanel"')!=1:
        raise RuntimeError('New and legacy IDP panels must both exist exactly once')
    # Strict no-canonical-edit check: removing only new UI insertions gives original byte-identical board.
    check=board.replace(PANEL,'').replace(STYLE,'').replace(SCRIPT,'')
    if check!=before:
        raise RuntimeError('Non-additive board changes detected; refusing write')
    BOARD.write_text(board,encoding='utf-8')
    print('Installed isolated dashboard: free-agent-board.html and two assets. Existing model markup unchanged.')

if __name__=='__main__':
    main()
