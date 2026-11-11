#!/usr/bin/env python3
"""Add isolated public Sleeper weekly IDP radar inside existing Early Opportunity Watch.

Read-only research. Do not alter original dashboard modules or private file imports.
"""
import json
from pathlib import Path

BOARD = Path('free-agent-board.html')
JS = Path('assets/idp_weekly_radar_v1.js')
CSS = Path('assets/idp_weekly_radar_v1.css')
DATA = Path('data/idp_weekly_2026_public.json')
PANEL = '''<!-- IDP_WEEKLY_PUBLIC_V1_PANEL_START -->
      <details id="idptPanel" aria-label="Public IDP weekly snap trends">
        <summary>Weekly Snap Trends <span id="idptCount">(loading public evidence)</span></summary>
        <div class="idpt-inner">
          <p class="idpt-intro">Public Sleeper observations by NFL week. Discover rising defensive snap counts among LOG free agents without a 200-snap requirement. This is NOT snap share, a breakout probability, or an expert projection. Your private watchlist and subscriber forecasts remain browser-local.</p>
          <div class="idpt-controls">
            <label for="idptGroup">Position<select id="idptGroup"><option value="ALL">All IDP</option><option value="LB">LB</option><option value="DL">DL</option><option value="DB">DB</option></select></label>
            <label for="idptView">Evidence filter<select id="idptView"><option value="rising">Rising raw snaps</option><option value="young">Age 25 or younger</option><option value="all">All observed</option></select></label>
            <label for="idptAvailability">LOG status<select id="idptAvailability"><option value="available">Available only</option><option value="rostered">Rostered</option><option value="all">Everyone</option></select></label>
            <label for="idptSort">Sort<select id="idptSort"><option value="signal">Strongest usage signal</option><option value="latest">Most recent snaps</option><option value="youngest">Youngest</option><option value="tackle">Latest tackle rate</option></select></label>
          </div>
          <label for="idptSearch">Find player<input id="idptSearch" type="search" placeholder="Search all tracked IDPs" autocomplete="off"></label>
          <p class="idpt-status" id="idptStatus" role="status">Loading public week-by-week defensive statistics…</p>
          <p class="idpt-note" id="idptNote"></p>
          <div class="idpt-list" id="idptList" aria-live="polite"></div>
          <button type="button" class="idpt-more" id="idptMore" hidden>Show more</button>
        </div>
      </details>
<!-- IDP_WEEKLY_PUBLIC_V1_PANEL_END -->
'''
STYLE = '<!-- IDP_WEEKLY_PUBLIC_V1_STYLE --><link rel="stylesheet" href="assets/idp_weekly_radar_v1.css">\n'
SCRIPT = '<!-- IDP_WEEKLY_PUBLIC_V1_SCRIPT --><script src="assets/idp_weekly_radar_v1.js" defer></script>\n'


def insert_once(source, anchor, snippet):
    if source.count(anchor) != 1:
        raise RuntimeError('Missing or nonunique HTML anchor: '+anchor)
    return source.replace(anchor, snippet + anchor, 1)


def validate_data():
    assert BOARD.is_file() and JS.is_file() and CSS.is_file() and DATA.is_file(), 'Required public files absent'
    d = json.loads(DATA.read_text('utf-8'))
    assert d.get('schema_version') == 1
    assert d.get('classification') == 'PUBLIC_SLEEPER_WEEKLY_IDP_EVIDENCE_NOT_PROJECTION_OR_BREAKOUT'
    assert d.get('season') == 2026 and 9 <= d.get('last_completed_week', 0) <= 18
    players=d.get('players')
    assert isinstance(players, list) and len(players) >= 100
    assert d.get('counts', {}).get('total_player_records') == len(players)
    assert d.get('policy') == 'PUBLIC_SOURCE_ONLY_READ_ONLY_RESEARCH_NO_FV_MV_TU_OR_PRIVATE_SUBSCRIBER_DATA'
    manifest=d.get('source_manifest')
    assert isinstance(manifest, list) and len(manifest) == d['last_completed_week'] - 4
    assert [w['week'] for w in manifest] == list(range(5, d['last_completed_week'] + 1))
    assert all(len(w['response_sha256']) == 64 for w in manifest)
    ids=set()
    for p in players:
        sid=str(p['sleeper_id'])
        assert sid.isdigit() and sid not in ids
        ids.add(sid)
        assert p.get('position') in ('LB','DL','DB')
        assert p.get('observations') and isinstance(p['observations'], list)
    print(f'PASS public weekly evidence: {len(players)} players through W{d["last_completed_week"]}; {d["counts"].get("rising_raw_snap_signals")} rising raw-snap signals')


def main():
    validate_data()
    orig=BOARD.read_text('utf-8')
    assert orig.count('id="idpePanel"') == 1 and orig.count('id="idpoPanel"') == 1 and orig.count('id="idpiPanel"') == 1
    for marker in ('IDP_EARLY_V1_PANEL_START','IDP_EARLY_V1_PANEL_END','IDP_EARLY_V1_STYLE','IDP_EARLY_V1_SCRIPT'):
        assert orig.count(marker) == 1, 'Existing IDP dashboard anchor changed: '+marker
    markers=('IDP_WEEKLY_PUBLIC_V1_PANEL_START','IDP_WEEKLY_PUBLIC_V1_PANEL_END','IDP_WEEKLY_PUBLIC_V1_STYLE','IDP_WEEKLY_PUBLIC_V1_SCRIPT')
    found=[orig.count(m) for m in markers]
    if any(found):
        assert found==[1,1,1,1], 'Partial / duplicated weekly radar installation; refusing edit'
        assert orig.count('id="idptPanel"') == 1 and orig.count('idp_weekly_radar_v1.js') == 1 and orig.count('idp_weekly_radar_v1.css') == 1
        print('PASS existing IDP weekly radar already installed: no-op')
        return
    # Insert inside the existing browser-local panel without touching that panel's JS or private inputs.
    candidate=insert_once(orig,'      <div class="idpe-files">',PANEL)
    candidate=insert_once(candidate,'<!-- IDP_EARLY_V1_STYLE -->',STYLE)
    candidate=insert_once(candidate,'<!-- IDP_EARLY_V1_SCRIPT -->',SCRIPT)
    assert all(candidate.count(m)==1 for m in markers)
    assert candidate.count('id="idptPanel"')==1
    assert candidate.count('id="idpeFile"')==1 and candidate.count('id="idpeProjectionFile"')==1
    # Reversing all three additions gives byte-identical original board.
    assert candidate.replace(PANEL,'',1).replace(STYLE,'',1).replace(SCRIPT,'',1)==orig
    BOARD.write_text(candidate,encoding='utf-8')
    print('PASS isolated IDP weekly radar installed; no existing dashboard or valuation changes')


if __name__=='__main__':
    main()
