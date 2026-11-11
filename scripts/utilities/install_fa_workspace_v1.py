#!/usr/bin/env python3
"""LOG A-FA09R1: append-only workspace nav code, plus truthful privacy copy.

No edits inside the canonical valuation script, any source-data JSON, or existing
IDP module. The companion JS relocates the original DOM nodes at runtime.
"""
from pathlib import Path

HTML = Path('free-agent-board.html')
CSS = Path('assets/fa_workspace_v1.css')
JS = Path('assets/fa_workspace_v1.js')
STYLE_MARKER = '<!-- FA_WORKSPACE_V1_STYLE -->'
SCRIPT_MARKER = '<!-- FA_WORKSPACE_V1_SCRIPT -->'
STYLE = STYLE_MARKER+'<link rel="stylesheet" href="assets/fa_workspace_v1.css?v=1">\n'
SCRIPT = SCRIPT_MARKER+'<script src="assets/fa_workspace_v1.js?v=1" defer></script>\n'
OLD_PRIVACY = 'Private tool — kept local, never hosted or shared. Nothing here is visible to anyone else in the league.'
NEW_PRIVACY = 'Private research imports stay in this browser tab. This GitHub Pages site is public, and its password screen is not secure authentication. Never upload subscriber files here.'
REQUIRED = [
    '<div class="wrap">',
    'class="privacy-note"',
    '<section class="filter-panel" aria-label="Free agent data filters">',
    '<div id="boardWrap"></div>',
    '<!-- IDP_EARLY_V1_PANEL_START -->',
    '<!-- IDP_EARLY_V1_PANEL_END -->',
    '<!-- IDP_OPPORTUNITY_V1_PANEL_START -->',
    '<!-- IDP_OPPORTUNITY_V1_PANEL_END -->',
    '<!-- IDP_INTEL_V1_PANEL_START -->',
    '<!-- IDP_INTEL_V1_PANEL_END -->',
    '<!-- IDP_WEEKLY_PUBLIC_V1_PANEL_START -->',
    '<!-- IDP_WEEKLY_PUBLIC_V1_PANEL_END -->',
    '<script id="free-agent-password-gate-runtime">',
    '<script>\n/* CANONICAL VALUATION SYNC',
    '<script src="assets/idp_intel_v1.js" defer></script>',
    'id="fa13ResearchPanel"',
]


def require_exact(src, token, n=1):
    got=src.count(token)
    if got != n:
        raise RuntimeError(f'Unsafe HTML layout: expected {n} occurrence(s) of {token[:75]!r}, saw {got}')


def install():
    if not all(p.is_file() and p.stat().st_size>100 for p in (HTML,CSS,JS)):
        raise RuntimeError('Missing board or workspace modules')
    before=HTML.read_text(encoding='utf-8')
    for marker in REQUIRED:require_exact(before,marker)
    if before.count(STYLE_MARKER) or before.count(SCRIPT_MARKER):
        require_exact(before,STYLE_MARKER)
        require_exact(before,SCRIPT_MARKER)
        require_exact(before,STYLE)
        require_exact(before,SCRIPT)
        require_exact(before,NEW_PRIVACY)
        print('PASS A-FA09R1 already installed; idempotent no-op')
        return
    require_exact(before,OLD_PRIVACY)
    require_exact(before,'</head>')
    require_exact(before,'</body>')
    after=before.replace(OLD_PRIVACY,NEW_PRIVACY,1)
    after=after.replace('</head>',STYLE+'</head>',1)
    after=after.replace('</body>',SCRIPT+'</body>',1)
    # Absolute invariant: exact reverse transform equals source, byte for byte.
    back=after.replace(STYLE,'',1).replace(SCRIPT,'',1).replace(NEW_PRIVACY,OLD_PRIVACY,1)
    if back != before:raise RuntimeError('Page changed outside allowed insertions')
    for marker in REQUIRED:require_exact(after,marker)
    require_exact(after,STYLE_MARKER)
    require_exact(after,SCRIPT_MARKER)
    HTML.write_text(after,encoding='utf-8')
    print('PASS A-FA09R1 additive workspace references installed, canonical HTML retained')


if __name__=='__main__':
    install()
