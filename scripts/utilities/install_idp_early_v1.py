#!/usr/bin/env python3
"""Install additive LOG IDP Early Opportunity V1, without editing valuation code.

The installer is idempotent and fail-closed on partial or duplicate markers.
It never reads, writes, copies or publishes subscription-derived data.
"""
from pathlib import Path
import argparse
import difflib
import sys

BOARD = Path('free-agent-board.html')
JS = Path('assets/idp_early_v1.js')
CSS = Path('assets/idp_early_v1.css')
PANEL_START='<!-- IDP_EARLY_V1_PANEL_START -->'
PANEL_END='<!-- IDP_EARLY_V1_PANEL_END -->'
STYLE='<!-- IDP_EARLY_V1_STYLE --><link rel="stylesheet" href="assets/idp_early_v1.css">\n'
SCRIPT='<!-- IDP_EARLY_V1_SCRIPT --><script src="assets/idp_early_v1.js" defer></script>\n'
ANCHOR_PANEL='<!-- IDP_OPPORTUNITY_V1_PANEL_START -->'
ANCHOR_STYLE='<!-- IDP_OPPORTUNITY_V1_STYLE -->'
ANCHOR_SCRIPT='<!-- IDP_OPPORTUNITY_V1_SCRIPT -->'
PANEL='''<!-- IDP_EARLY_V1_PANEL_START -->
<section id="idpePanel" aria-label="IDP early opportunity watch" data-feature="browser-local-research-only">
  <details>
    <summary>Early Opportunity Watch <span id="idpeCount">(private research not loaded)</span></summary>
    <div class="idpe-inner">
      <p class="idpe-intro">Small-sample scouting for young or newly promoted IDPs. Choose local private research files to view them alongside live LOG availability. Your selected files stay in this browser tab and are never uploaded to GitHub or a server. No confirmed breakout or FV claim.</p>
      <div class="idpe-files">
        <label for="idpeFile">Private weekly watch JSON
          <input id="idpeFile" type="file" accept=".json,application/json" multiple>
        </label>
        <label for="idpeProjectionFile">Optional private Week 10 projections JSON
          <input id="idpeProjectionFile" type="file" accept=".json,application/json">
        </label>
      </div>
      <div class="idpe-filter">
        <label for="idpePosition">Position<select id="idpePosition">
          <option value="ALL">All IDP</option><option value="LB">Linebacker</option><option value="S">Safety</option><option value="CB">Corner</option><option value="EDGE">EDGE</option><option value="DT">Interior DL</option>
        </select></label>
        <label for="idpeScope">LOG status<select id="idpeScope"><option value="available">Available only</option><option value="all">All watched</option></select></label>
        <label for="idpeSort">Sort<select id="idpeSort"><option value="event">Opportunity signals</option><option value="age">Youngest</option><option value="snaps">Latest weekly snaps</option></select></label>
      </div>
      <label class="idpe-filter-search" for="idpeSearch"><input id="idpeSearch" type="search" placeholder="Search watched players" aria-label="Search watched players"></label>
      <div class="idpe-bottom"><label><input id="idpeYoung" type="checkbox"> Age 25 or younger</label><button id="idpeClear" type="button">Clear imported files</button></div>
      <div class="idpe-status" id="idpeStatus" role="status">Checking LOG availability…</div>
      <div class="idpe-note" id="idpeNote"></div>
      <div class="idpe-list" id="idpeItems" aria-live="polite"></div>
    </div>
  </details>
</section>
<!-- IDP_EARLY_V1_PANEL_END -->
'''
MARKERS=(PANEL_START,PANEL_END,'<!-- IDP_EARLY_V1_STYLE -->','<!-- IDP_EARLY_V1_SCRIPT -->')


def insert_exact(text,anchor,addition):
    if text.count(anchor)!=1:
        raise RuntimeError(f'Missing or duplicated expected dashboard anchor: {anchor}')
    return text.replace(anchor,addition+anchor,1)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true',help='Do not write board; assert installation is valid')
    args=parser.parse_args()
    if not (BOARD.is_file() and JS.is_file() and CSS.is_file()):
        raise RuntimeError('Missing canonical free-agent board or staged independent early-opportunity assets')
    text=BOARD.read_text(encoding='utf-8')
    if any(text.count(a)!=1 for a in (ANCHOR_PANEL,ANCHOR_STYLE,ANCHOR_SCRIPT)):
        raise RuntimeError('Expected existing IDP season panel is missing or duplicated')
    existing=[m for m in MARKERS if m in text]
    if existing:
        if len(existing)!=4 or any(text.count(m)!=1 for m in MARKERS) or text.count('id="idpePanel"')!=1:
            raise RuntimeError('Partial or duplicate FA06 installation; refusing modifications')
        for needle in (STYLE,SCRIPT,PANEL):
            if text.count(needle)!=1:raise RuntimeError('FA06 present but its embedded markup differs; audit manually')
        print('PASS: A-FA06R1 already installed; no duplicate insertion')
        return
    if args.check:
        raise RuntimeError('FA06 feature is not installed; --check cannot proceed')
    board=text
    board=insert_exact(board,ANCHOR_PANEL,PANEL)
    board=insert_exact(board,ANCHOR_STYLE,STYLE)
    board=insert_exact(board,ANCHOR_SCRIPT,SCRIPT)
    if any(board.count(m)!=1 for m in MARKERS) or board.count('id="idpePanel"')!=1:
        raise RuntimeError('New feature markers or panel IDs are not unique')
    if board.replace(PANEL,'',1).replace(STYLE,'',1).replace(SCRIPT,'',1)!=text:
        raise RuntimeError('Existing page changed outside additive UI insertions')
    BOARD.write_text(board,encoding='utf-8',newline='\n')
    print('PASS: installed additive, read-only Early Opportunity Watch before season IDP panel')


if __name__=='__main__':
    try:main()
    except Exception as e:
        print('FAIL: '+str(e),file=sys.stderr)
        sys.exit(1)
