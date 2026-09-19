#!/usr/bin/env python3
"""Package Adjustment V3 Phase 3C — fresh voting activation.

This changes only:
- the browser research-vote consumer,
- KTC transport isolation,
- the regression contract for that consumer,
- a separate Phase 3C release record.

It does NOT change:
- the frozen Phase 3A preregistration,
- the frozen Phase 3B catalog,
- production Package Adjustment V1.6,
- Fundamental Value / Market Value / Team Utility.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "research" / "package-adjustment-v3-ktc-style"

INDEX = ROOT / "index.html"
KTC_PIPE = ROOT / "scripts" / "market" / "ktc_pipeline.py"
REGRESSION = ROOT / "scripts" / "validation" / "repo_regression_checks.py"

PREREG = D / "phase3_confirmation_preregistration.json"
PREREG_MANIFEST = D / "phase3_confirmation_preregistration_manifest.json"
CATALOG = D / "phase3_confirmation_catalog.json"
CATALOG_MD = D / "phase3_confirmation_catalog.md"
CATALOG_MANIFEST = D / "phase3_confirmation_catalog_manifest.json"
RELEASE = D / "phase3_voting_release.json"

EXPECTED = {
    "prereg_blob": "19966121899d41bdbc754a6a260758cf175b12e2",
    "prereg_manifest_blob": "df63773385e982ff7bfdfc0d042159e2ed957679",
    "catalog_blob": "3d4615e590697341ee8c27785d8b22e16b82ac44",
    "catalog_md_blob": "47313bf7ec8dd61471bd970e97352baedb30dc60",
    "catalog_manifest_blob": "6ecd25f01b758a5ea5bd69f513f775c55fc84d4c",
    "catalog_sha256": "a26a619fb0efce1dba701c9f31a99ba8a4ba91fc2a51eb9afef99e307591786e",
    "catalog_fingerprint": "aa389ed35d011d9fd0a7d674014fd8b535e78145ddd0cedd39995df7d378ebc6",
}


def git_blob(path: Path) -> str:
    return subprocess.check_output(
        ["git", "hash-object", str(path.relative_to(ROOT))],
        cwd=ROOT,
        text=True,
    ).strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_frozen_inputs() -> None:
    assert git_blob(PREREG) == EXPECTED["prereg_blob"]
    assert git_blob(PREREG_MANIFEST) == EXPECTED["prereg_manifest_blob"]
    assert git_blob(CATALOG) == EXPECTED["catalog_blob"]
    assert git_blob(CATALOG_MD) == EXPECTED["catalog_md_blob"]
    assert git_blob(CATALOG_MANIFEST) == EXPECTED["catalog_manifest_blob"]

    cfg = json.loads(PREREG.read_text(encoding="utf-8"))
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    man = json.loads(CATALOG_MANIFEST.read_text(encoding="utf-8"))

    assert cfg["status"] == "FROZEN_FRESH_CONFIRMATION_PREREGISTRATION"
    assert cfg["frozen"] is True
    assert cfg["catalog_design"]["new_vote_namespace"] == "__pkgv3c1__"
    assert cfg["catalog_design"]["research_cell_count"] == 24
    assert cfg["catalog_design"]["challenge_count"] == 240
    assert cfg["catalog_design"]["challenges_per_cell"] == 10
    assert cfg["collection_and_maturity"]["exact_effective_vote_checkpoints"] == [600, 700, 800]

    assert cat["status"] == "frozen_unreleased_fresh_confirmation_catalog"
    assert cat["frozen"] is True
    assert cat["released"] is False
    assert cat["voting_activated"] is False
    assert cat["research_only"] is True
    assert cat["consumer_changed"] is False
    assert cat["production_formula_enabled"] is False
    assert cat["production_revision_retained"] == "v1.6-v5-size2-composition-overlay"
    assert cat["vote_namespace_reserved"] == "__pkgv3c1__"
    assert cat["old_900_vote_dataset_read"] is False
    assert cat["human_vote_outcomes_read"] is False
    assert len(cat["challenges"]) == 240

    cells = {}
    for challenge in cat["challenges"]:
        cells[challenge["research_cell"]] = cells.get(challenge["research_cell"], 0) + 1
    assert len(cells) == 24
    assert set(cells.values()) == {10}

    assert man["catalog_sha256"] == EXPECTED["catalog_sha256"]
    assert man["catalog_sha256"] == sha256(CATALOG)
    assert man["catalog_fingerprint_sha256"] == EXPECTED["catalog_fingerprint"]
    assert man["catalog_generated"] is True
    assert man["voting_activated"] is False
    assert man["production_change_authorized"] is False


def browser_function_block() -> str:
    return r"""function packageVoteTodayKey(){
return 'package_votes_v3c1_' + new Date().toISOString().slice(0,10);
}

function packageVotesToday(){
return parseInt(localStorage.getItem(packageVoteTodayKey()) || '0', 10);
}

function packageVoteRecent(){
try { return JSON.parse(localStorage.getItem('package_vote_recent_v3c1') || '[]'); }
catch(e){ return []; }
}

function packageVoteRemember(id){
const recent = packageVoteRecent().concat([id]).slice(-PACKAGE_VOTE_RECENT_MEMORY);
localStorage.setItem('package_vote_recent_v3c1', JSON.stringify(recent));
}

/* PACKAGE_VOTE_V3C1_EXACT_CELL_SAMPLING_V1
   Frozen fresh-confirmation schedule:
   1) select one of the 24 preregistered research cells uniformly;
   2) select one of exactly 10 challenges uniformly inside that cell,
      preferring one outside recent-memory when available;
   3) randomize whether canonical Side A or Side B is displayed left.
   Recent-memory is applied only AFTER the cell is selected. Vote outcomes,
   candidate identities, and candidate predictions never affect sampling. */
function packageVoteSelectChallenge(){
if(!PACKAGE_VOTE_CHALLENGES || !PACKAGE_VOTE_CHALLENGES.length) return null;

const byCell = new Map();
for(const c of PACKAGE_VOTE_CHALLENGES){
if(!c || typeof c.research_cell !== 'string') continue;
if(!byCell.has(c.research_cell)) byCell.set(c.research_cell, []);
byCell.get(c.research_cell).push(c);
}

const cells = Array.from(byCell.keys()).sort();
if(cells.length !== 24) return null;

const selectedCell = cells[Math.floor(Math.random() * cells.length)];
const cellPool = byCell.get(selectedCell);
if(!cellPool || cellPool.length !== 10) return null;

const recent = new Set(packageVoteRecent());
let challengePool = cellPool.filter(c => !recent.has(c.id));
if(!challengePool.length) challengePool = cellPool;

const challenge = challengePool[Math.floor(Math.random() * challengePool.length)];
return { challenge, left: Math.random() < 0.5 ? 'A' : 'B' };
}

function packageVoteEnsureLoaded(){
if(PACKAGE_VOTE_STATUS === 'loading' || PACKAGE_VOTE_STATUS === 'ready') return;
PACKAGE_VOTE_STATUS = 'loading';

fetch(PACKAGE_VOTE_CHALLENGES_URL, {cache:'no-store'})
.then(r => {
if(!r.ok) throw new Error('HTTP ' + r.status);
return r.json();
})
.then(doc => {
if(
doc.schema_version !== 1 ||
doc.status !== 'frozen_unreleased_fresh_confirmation_catalog' ||
doc.frozen !== true ||
doc.released !== false ||
doc.voting_activated !== false ||
doc.research_only !== true ||
doc.consumer_changed !== false ||
doc.production_formula_enabled !== false ||
doc.production_revision_retained !== 'v1.6-v5-size2-composition-overlay' ||
doc.vote_namespace_reserved !== '__pkgv3c1__' ||
doc.old_900_vote_dataset_read !== false ||
doc.human_vote_outcomes_read !== false ||
!doc.catalog_diagnostics ||
Number(doc.catalog_diagnostics.challenge_count) !== 240 ||
Number(doc.catalog_diagnostics.research_cell_count) !== 24 ||
Number(doc.catalog_diagnostics.known_ktc_examples_in_selected_catalog) !== 0 ||
Number(doc.catalog_diagnostics.historical_trade_matches_in_selected_catalog) !== 0 ||
!Array.isArray(doc.challenges) ||
doc.challenges.length !== 240 ||
!doc.challenges.every(c =>
  c &&
  c.schema_version === 1 &&
  c.experiment === 'package_adjustment_v3_fresh_confirmation' &&
  typeof c.research_cell === 'string' &&
  ['1v2','1v3','2v2','2v3','3v3','3v4'].includes(c.topology) &&
  ['players_only','includes_picks'].includes(c.asset_mix) &&
  ['g201_vs_g215','g215_vs_g230'].includes(c.disagreement_band) &&
  Array.isArray(c.side_a) &&
  Array.isArray(c.side_b) &&
  c.side_a.length === Number(c.side_a_count) &&
  c.side_b.length === Number(c.side_b_count) &&
  c.side_a.length > 0 &&
  c.side_b.length > 0 &&
  [...c.side_a, ...c.side_b].every(a =>
    a &&
    ['player','pick'].includes(a.kind) &&
    typeof a.name === 'string' &&
    a.name.length > 0 &&
    Number(a.fv) > 0
  ) &&
  Number(c.raw_side_total_ratio) >= 0.80 &&
  Number(c.raw_side_total_ratio) <= 1.25
)
){
throw new Error('unexpected frozen V3 confirmation challenge catalog');
}

const cells = new Map();
for(const c of doc.challenges){
cells.set(c.research_cell, Number(cells.get(c.research_cell) || 0) + 1);
}
if(cells.size !== 24) throw new Error('v3c1_catalog_cell_count');
if(Array.from(cells.values()).some(n => n !== 10)){
throw new Error('v3c1_catalog_cell_balance');
}

const topologyCounts = new Map();
const mixCounts = new Map();
const bandCounts = new Map();
for(const c of doc.challenges){
topologyCounts.set(c.topology, Number(topologyCounts.get(c.topology) || 0) + 1);
mixCounts.set(c.asset_mix, Number(mixCounts.get(c.asset_mix) || 0) + 1);
bandCounts.set(c.disagreement_band, Number(bandCounts.get(c.disagreement_band) || 0) + 1);
}
if(Array.from(topologyCounts.values()).some(n => n !== 40) || topologyCounts.size !== 6){
throw new Error('v3c1_catalog_topology_balance');
}
if(mixCounts.get('players_only') !== 120 || mixCounts.get('includes_picks') !== 120){
throw new Error('v3c1_catalog_asset_mix_balance');
}
if(bandCounts.get('g201_vs_g215') !== 120 || bandCounts.get('g215_vs_g230') !== 120){
throw new Error('v3c1_catalog_disagreement_balance');
}

PACKAGE_VOTE_CHALLENGES = doc.challenges;
PACKAGE_VOTE_STATUS = 'ready';
packageVoteCurrent = null;
renderPackageVote();
})
.catch(err => {
console.warn('Package Adjustment V3 confirmation catalog load failed:', err);
PACKAGE_VOTE_CHALLENGES = null;
PACKAGE_VOTE_STATUS = 'failed';
renderPackageVote();
});
}

function packageVoteAssetCard(asset){
const age = (typeof asset.age === 'number') ? ` &middot; ${asset.age} y.o.` : '';
const team = asset.team ? ` &middot; ${ktcTeamLabel(asset.team)}` : '';
const meta = asset.kind === 'pick'
  ? 'Draft Pick'
  : `${escapeHtml(asset.pos)}${team}${age}`;
return `<div class="need-cell" style="text-align:left;padding:10px;">
<div style="font-weight:600;font-size:14px;">${escapeHtml(asset.name)}</div>
<div style="color:var(--text-dim);font-size:11px;">${meta}</div>
</div>`;
}

function packageVoteSubmit(displaySide){
if(Date.now() < Date.parse(PACKAGE_VOTE_VALID_AFTER_UTC)) return;
if(!packageVoteCurrent || packageVotesToday() >= PACKAGE_VOTE_DAILY_LIMIT) return;

const left = packageVoteCurrent.left;
const choice = displaySide === 'L' ? left : (left === 'A' ? 'B' : 'A');
const id = packageVoteCurrent.challenge.id;
const voter = ktcCurrentVoterId();
if(!voter) return;

fetch(KTC_SUBMIT_URL, {
method: 'POST',
headers: { 'Content-Type': 'text/plain;charset=utf-8' },
body: JSON.stringify({
voterRosterId: voter,
keep: `__pkgv3c1__|${id}|${choice}`,
trade: `__pkgv3c1_meta__|${left}`,
cut: '__pkgv3c1_schema__|1',
}),
}).catch(() => {});

localStorage.setItem(packageVoteTodayKey(), String(packageVotesToday() + 1));
packageVoteRemember(id);
packageVoteCurrent = packageVoteSelectChallenge();
renderPackageVote();
}

function renderPackageVote(){
const el = document.getElementById('packageVoteWrap');
if(!el) return;

if(!(state.teamConfirmed && MY_ROSTER_ID) && !ktcIsGuestMode()){
el.innerHTML = `
<div class="vote-access-card">
<div class="vote-access-copy">
<div class="vote-access-title">Ready to compare trades?</div>
<div class="vote-access-sub">League members: choose your team above to use your league voter identity. Everyone else can vote as a guest.</div>
</div>
<button type="button" class="vote-guest-btn" onclick="ktcStartGuestMode()">Vote as a guest</button>
</div>
`;
return;
}

if(Date.now() < Date.parse(PACKAGE_VOTE_VALID_AFTER_UTC)){
el.innerHTML = `<div style="color:var(--text-dim);font-size:13px;padding:8px 0;">
Fresh package confirmation voting opens at ${new Date(PACKAGE_VOTE_VALID_AFTER_UTC).toLocaleString()}.
</div>`;
return;
}

if(packageVotesToday() >= PACKAGE_VOTE_DAILY_LIMIT){
el.innerHTML = `<div style="color:var(--text-dim);font-size:13px;padding:8px 0;">
You've completed today's ${PACKAGE_VOTE_DAILY_LIMIT} package research votes. Thank you.
</div>`;
return;
}

if(PACKAGE_VOTE_STATUS === 'idle'){
packageVoteEnsureLoaded();
el.innerHTML = `<div style="color:var(--text-dim);font-size:13px;padding:8px 0;">Loading fresh package comparisons...</div>`;
return;
}
if(PACKAGE_VOTE_STATUS === 'loading'){
el.innerHTML = `<div style="color:var(--text-dim);font-size:13px;padding:8px 0;">Loading fresh package comparisons...</div>`;
return;
}
if(PACKAGE_VOTE_STATUS === 'failed'){
el.innerHTML = `<div style="color:var(--text-dim);font-size:13px;padding:8px 0;">Package research is temporarily unavailable. Normal KTC voting is unaffected.</div>`;
return;
}

if(!packageVoteCurrent) packageVoteCurrent = packageVoteSelectChallenge();
if(!packageVoteCurrent){
el.innerHTML = `<div style="color:var(--text-dim);font-size:13px;padding:8px 0;">No fresh package comparison is available right now.</div>`;
return;
}

const c = packageVoteCurrent.challenge;
const canonicalAHTML = c.side_a.map(packageVoteAssetCard).join('');
const canonicalBHTML = c.side_b.map(packageVoteAssetCard).join('');
const leftIsA = packageVoteCurrent.left === 'A';
const leftHTML = leftIsA ? canonicalAHTML : canonicalBHTML;
const rightHTML = leftIsA ? canonicalBHTML : canonicalAHTML;

el.innerHTML = `
<div style="border:1px solid var(--line);border-radius:8px;padding:10px;margin-bottom:10px;font-size:12px;color:var(--text-dim);">
<b style="color:var(--text);">Research question:</b> Which side would you rather receive in a dynasty trade?
Values and model predictions are intentionally hidden.
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;align-items:stretch;">
<div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--gold);margin-bottom:5px;text-align:center;">SIDE A</div>
<div style="display:flex;flex-direction:column;gap:6px;">${leftHTML}</div>
<button class="tab-btn" style="width:100%;margin-top:8px;" onclick="packageVoteSubmit('L')">Choose Side A</button>
</div>
<div>
<div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--violet);margin-bottom:5px;text-align:center;">SIDE B</div>
<div style="display:flex;flex-direction:column;gap:6px;">${rightHTML}</div>
<button class="tab-btn" style="width:100%;margin-top:8px;" onclick="packageVoteSubmit('R')">Choose Side B</button>
</div>
</div>
<div style="color:var(--text-dim);font-size:10px;margin-top:8px;text-align:center;">
${packageVotesToday()} / ${PACKAGE_VOTE_DAILY_LIMIT} package votes today &middot; display sides randomized
</div>
`;
}
"""


def regression_check_block() -> str:
    return """def check_package_sampling_contract():
    text = INDEX.read_text(encoding="utf-8")
    start = text.index("function packageVoteTodayKey(){")
    end = text.index("\\nfunction render(){", start)
    block = text[start:end]

    assert "PACKAGE_VOTE_V3C1_EXACT_CELL_SAMPLING_V1" in block
    assert "function packageVoteOwnPlayers()" not in block
    assert "function packageVoteEligibleChallenges()" not in block
    assert "own.has(" not in block
    assert "const byCell = new Map();" in block
    assert "if(!byCell.has(c.research_cell)) byCell.set(c.research_cell, []);" in block
    assert "const cells = Array.from(byCell.keys()).sort();" in block
    assert "if(cells.length !== 24) return null;" in block
    assert "if(!cellPool || cellPool.length !== 10) return null;" in block
    assert "const selectedCell = cells[Math.floor(Math.random() * cells.length)];" in block
    assert "let challengePool = cellPool.filter(c => !recent.has(c.id));" in block
    assert "if(!challengePool.length) challengePool = cellPool;" in block
    assert "left: Math.random() < 0.5 ? 'A' : 'B'" in block
    assert "Date.now() < Date.parse(PACKAGE_VOTE_VALID_AFTER_UTC)" in block

    cell_idx = block.index("const selectedCell =")
    recent_idx = block.index("const recent = new Set(packageVoteRecent());")
    assert cell_idx < recent_idx

    assert "Package Adjustment V3 Fresh Confirmation: frozen all-asset disagreement catalog." in text
    assert "const PACKAGE_VOTE_DAILY_LIMIT = 20;" in text
    assert "__pkgv3c1__|" in text
    assert "__pkgv3c1_meta__|" in text
    assert "__pkgv3c1_schema__|1" in text
    assert "doc.challenges.length !== 240" in block
    assert "cells.size !== 24" in block
    assert "n !== 10" in block
    assert "topologyCounts.size !== 6" in block
    assert "mixCounts.get('players_only') !== 120" in block
    assert "bandCounts.get('g201_vs_g215') !== 120" in block

    print(
        "PASS V3C1 exact 24-cell fresh-confirmation sampling contract: "
        "10 challenges/cell; recent-memory post-cell only; display randomized"
    )

"""


def patch_index(source_commit: str, valid_after_utc: str) -> None:
    catalog_manifest = json.loads(CATALOG_MANIFEST.read_text(encoding="utf-8"))
    text = INDEX.read_text(encoding="utf-8")

    constants_pattern = re.compile(
        r"/\* Package Adjustment V6 Development: frozen 1-vs-3 composition catalog\.\n"
        r"Research-only development evidence\. Production Package Adjustment remains V1\.6\. \*/\n"
        r"const PACKAGE_VOTE_CHALLENGES_URL = .*?\n"
        r"const PACKAGE_VOTE_CATALOG_SHA256 = .*?\n"
        r"const PACKAGE_VOTE_DAILY_LIMIT = .*?\n"
        r"const PACKAGE_VOTE_RECENT_MEMORY = .*?\n"
        r"const PACKAGE_VOTE_VALID_AFTER_UTC = .*?\n"
        r"let PACKAGE_VOTE_CHALLENGES = null;",
        re.S,
    )

    raw_url = (
        "https://raw.githubusercontent.com/ajknoll23-code/"
        f"LOG-Trade-Calculator/{source_commit}/"
        "research/package-adjustment-v3-ktc-style/"
        "phase3_confirmation_catalog.json"
    )

    replacement_constants = (
        "/* Package Adjustment V3 Fresh Confirmation: frozen all-asset disagreement catalog.\n"
        "Research-only confirmation evidence. Production Package Adjustment remains V1.6. */\n"
        f"const PACKAGE_VOTE_CHALLENGES_URL = '{raw_url}';\n"
        f"const PACKAGE_VOTE_CATALOG_SHA256 = '{catalog_manifest['catalog_sha256']}';\n"
        "const PACKAGE_VOTE_DAILY_LIMIT = 20;\n"
        "const PACKAGE_VOTE_RECENT_MEMORY = 24;\n"
        f"const PACKAGE_VOTE_VALID_AFTER_UTC = '{valid_after_utc}';\n"
        "let PACKAGE_VOTE_CHALLENGES = null;"
    )

    text2, n = constants_pattern.subn(replacement_constants, text, count=1)
    if n != 1:
        raise RuntimeError(
            f"Expected exactly one current V6 constants block; replaced {n}"
        )

    functions_pattern = re.compile(
        r"function packageVoteTodayKey\(\)\{.*?\n\}\nfunction render\(\)\{",
        re.S,
    )
    text3, n = functions_pattern.subn(
        browser_function_block() + "\nfunction render(){",
        text2,
        count=1,
    )
    if n != 1:
        raise RuntimeError(
            f"Expected exactly one package-vote function block; replaced {n}"
        )

    INDEX.write_text(text3, encoding="utf-8")


def patch_transport_isolation() -> None:
    pipe = KTC_PIPE.read_text(encoding="utf-8")

    old_tuple = (
        'PACKAGE_VOTE_PREFIXES = ("__pkgv1__|", "__pkgv2__|", "__pkgv3__|", '
        '"__pkgv4__|", "__pkgv5__|", "__pkgnv2__|", "__pkgnv2p1__|", "__pkgv6__|")'
    )
    new_tuple = (
        'PACKAGE_VOTE_PREFIXES = ("__pkgv1__|", "__pkgv2__|", "__pkgv3__|", '
        '"__pkgv4__|", "__pkgv5__|", "__pkgnv2__|", "__pkgnv2p1__|", '
        '"__pkgv6__|", "__pkgv3c1__|")'
    )
    if pipe.count(old_tuple) != 1:
        raise RuntimeError("Could not uniquely locate KTC package-vote prefix tuple")
    pipe = pipe.replace(old_tuple, new_tuple, 1)

    old_comment = (
        "# Package Preference Voting V1-V6 plus NextGen V2 first-wave and prospective V1\n"
        "# share transport only. Remove all reserved row families before normal KTC\n"
    )
    new_comment = (
        "# Package Preference Voting V1-V6, NextGen V2, and V3 fresh confirmation\n"
        "# share transport only. Remove all reserved row families before normal KTC\n"
    )
    if old_comment not in pipe:
        raise RuntimeError("Expected KTC transport-isolation comment not found")
    pipe = pipe.replace(old_comment, new_comment, 1)

    KTC_PIPE.write_text(pipe, encoding="utf-8")


def patch_regression_contract() -> None:
    regression = REGRESSION.read_text(encoding="utf-8")

    old_expected = (
        '        "__pkgv1__|",\n'
        '        "__pkgv2__|",\n'
        '        "__pkgv3__|",\n'
        '        "__pkgv4__|",\n'
        '        "__pkgv5__|",\n'
        '        "__pkgnv2__|",\n'
        '        "__pkgnv2p1__|",\n'
        '        "__pkgv6__|",\n'
        '    )\n'
    )
    new_expected = (
        '        "__pkgv1__|",\n'
        '        "__pkgv2__|",\n'
        '        "__pkgv3__|",\n'
        '        "__pkgv4__|",\n'
        '        "__pkgv5__|",\n'
        '        "__pkgnv2__|",\n'
        '        "__pkgnv2p1__|",\n'
        '        "__pkgv6__|",\n'
        '        "__pkgv3c1__|",\n'
        '    )\n'
    )
    if regression.count(old_expected) != 1:
        raise RuntimeError(
            "Could not uniquely locate regression expected prefix tuple"
        )
    regression = regression.replace(old_expected, new_expected, 1)

    start = regression.index("def check_package_sampling_contract():")
    end = regression.index("\ndef check_index_js_syntax():", start)
    regression = (
        regression[:start]
        + regression_check_block()
        + regression[end:]
    )
    REGRESSION.write_text(regression, encoding="utf-8")


def write_release(source_commit: str, valid_after_utc: str) -> None:
    manifest = json.loads(CATALOG_MANIFEST.read_text(encoding="utf-8"))
    release = {
        "schema_version": 1,
        "study_id": "package-adjustment-v3-ktc-style",
        "phase": "3C",
        "status": "FRESH_CONFIRMATION_VOTING_ACTIVE",
        "source_commit_before_activation": source_commit,
        "valid_after_utc": valid_after_utc,
        "vote_namespace": "__pkgv3c1__",
        "vote_meta_namespace": "__pkgv3c1_meta__",
        "vote_schema_marker": "__pkgv3c1_schema__|1",
        "catalog_git_blob": git_blob(CATALOG),
        "catalog_sha256": sha256(CATALOG),
        "catalog_fingerprint_sha256":
            manifest["catalog_fingerprint_sha256"],
        "catalog_challenge_count": 240,
        "research_cell_count": 24,
        "challenges_per_cell": 10,
        "daily_client_vote_limit": 20,
        "display_side_randomization": True,
        "values_hidden_from_voter_ui": True,
        "candidate_identity_hidden_from_voter_ui": True,
        "candidate_predictions_hidden_from_voter_ui": True,
        "old_namespace_rows_count_for_this_study": False,
        "old_900_vote_dataset_read": False,
        "production_change_authorized": False,
        "production_revision_retained":
            "v1.6-v5-size2-composition-overlay",
        "frozen_catalog_mutated": False,
        "normal_ktc_transport_isolation_extended": True,
    }
    RELEASE.write_text(
        json.dumps(release, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_after() -> None:
    text = INDEX.read_text(encoding="utf-8")
    assert "PACKAGE_VOTE_V3C1_EXACT_CELL_SAMPLING_V1" in text
    assert "__pkgv3c1__|" in text
    assert "__pkgv3c1_meta__|" in text
    assert "__pkgv3c1_schema__|1" in text
    assert "c.side_a.map(packageVoteAssetCard)" in text
    assert "c.side_b.map(packageVoteAssetCard)" in text
    assert "doc.challenges.length !== 240" in text

    tree = ast.parse(KTC_PIPE.read_text(encoding="utf-8"))
    prefixes = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "PACKAGE_VOTE_PREFIXES"
                ):
                    prefixes = ast.literal_eval(node.value)
                    break
        if prefixes is not None:
            break

    assert prefixes == (
        "__pkgv1__|",
        "__pkgv2__|",
        "__pkgv3__|",
        "__pkgv4__|",
        "__pkgv5__|",
        "__pkgnv2__|",
        "__pkgnv2p1__|",
        "__pkgv6__|",
        "__pkgv3c1__|",
    )

    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    assert release["status"] == "FRESH_CONFIRMATION_VOTING_ACTIVE"
    assert release["vote_namespace"] == "__pkgv3c1__"
    assert release["production_change_authorized"] is False

    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    assert cat["released"] is False
    assert cat["voting_activated"] is False


def selftest() -> None:
    block = browser_function_block()
    assert "PACKAGE_VOTE_V3C1_EXACT_CELL_SAMPLING_V1" in block
    assert "cellPool.length !== 10" in block
    assert "__pkgv3c1__|" in block
    assert "__pkgv3c1_meta__|" in block
    assert "__pkgv3c1_schema__|1" in block
    assert "side_a.map(packageVoteAssetCard)" in block
    assert "side_b.map(packageVoteAssetCard)" in block

    check = regression_check_block()
    compile(check, "<regression-check>", "exec")

    print("Package Adjustment V3 Phase 3C activation self-test PASS")


def activate() -> None:
    verify_frozen_inputs()

    if RELEASE.exists():
        raise RuntimeError(
            "Phase 3C release already exists; refusing to overwrite"
        )

    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
    ).strip()
    valid_after_utc = datetime.now(timezone.utc).isoformat()

    patch_index(source_commit, valid_after_utc)
    patch_transport_isolation()
    patch_regression_contract()
    write_release(source_commit, valid_after_utc)
    verify_after()

    print("PASS: Package Adjustment V3 fresh confirmation voting activated")
    print("VALID_AFTER_UTC=" + valid_after_utc)


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--selftest", action="store_true")
    group.add_argument("--activate", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        selftest()
    else:
        activate()


if __name__ == "__main__":
    main()
