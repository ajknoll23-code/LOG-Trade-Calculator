#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "research" / "package-adjustment-v7"
INDEX = ROOT / "index.html"
KTC = ROOT / "scripts/market/ktc_pipeline.py"
PHASE1A = D / "phase1a_power_and_catalog_manifest_v1.json"
POWER = D / "phase1a_power_analysis_v1.json"
CATALOG = D / "package_vote_challenges_v7_development_v1.json"
OUT_MAN = D / "development_voting_activation_manifest_v1.json"
OUT_MD = D / "development_voting_activation_v1.md"

PREFIX = "__pkgv7dev__|"
META_PREFIX = "__pkgv7dev_meta__|"
SCHEMA_MARKER = "__pkgv7dev_schema__|1"
CATALOG_SHA256 = "ddf1ad55a7f6b46a198e0855c7f2d1ae5346d5a1e8b88bb6e1a859076c2ac8dd"

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def replace_function(text: str, name: str, replacement: str) -> str:
    marker = f"function {name}("
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"missing JS function: {name}")
    brace = text.find("{", start)
    depth = 0
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    i = brace
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if line_comment:
            if ch == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            if ch == "*" and nxt == "/":
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            i += 1
            continue
        if ch == "/" and nxt == "/":
            line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            block_comment = True
            i += 2
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[:start] + replacement.strip() + text[i + 1:]
        i += 1
    raise RuntimeError(f"unbalanced JS function: {name}")

def validate_frozen_inputs():
    p = read_json(PHASE1A)
    power = read_json(POWER)
    cat = read_json(CATALOG)

    assert p["status"] == "FROZEN_PRE_VOTE_POWER_AND_CATALOG"
    assert p["decision"] == "FREEZE_V7_PHASE1A_AT_40_VOTER_FIRST_CHECKPOINT"
    assert p["v7_votes_read"] is False
    assert p["voting_activated"] is False
    assert p["selected_first_checkpoint_distinct_voters"] == 40
    assert p["hard_cap_distinct_voters"] == 50

    assert power["status"] == "FROZEN_PRE_VOTE_POWER"
    assert power["selected_first_checkpoint_distinct_voters"] == 40
    assert power["hard_cap_distinct_voters"] == 50
    assert power["coverage_gate_at_or_after_first_checkpoint"]["minimum_distinct_voters_per_challenge"] == 32
    assert power["v7_votes_read"] is False

    assert cat["status"] == "FROZEN_PRE_VOTE_DEVELOPMENT_CATALOG"
    assert cat["frozen"] is True
    assert cat["released"] is False
    assert cat["voting_activated"] is False
    assert cat["v7_votes_read"] is False
    assert cat["candidate_fit_performed"] is False
    assert cat["candidate_predictions_used_for_catalog_selection"] is False
    assert cat["challenge_count"] == 40
    assert len(cat["challenges"]) == 40
    assert sha256(CATALOG) == CATALOG_SHA256

    ids = [str(c["id"]) for c in cat["challenges"]]
    assert len(ids) == len(set(ids)) == 40
    assert all(c["fv_visible_to_voter"] is False for c in cat["challenges"])
    assert all(c["candidate_prediction_used_for_selection"] is False for c in cat["challenges"])

def constants_block(base_sha: str, activated: str) -> str:
    return f'''/* Package Adjustment V7 Development Voting.
Research only. Frozen 40-trade player-only multi-v-multi catalog.
No candidate has been fit and production Package Adjustment remains V1.7. */
const PACKAGE_VOTE_CHALLENGES_URL = 'https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/{base_sha}/research/package-adjustment-v7/package_vote_challenges_v7_development_v1.json';
const PACKAGE_VOTE_CATALOG_SHA256 = '{CATALOG_SHA256}';
const PACKAGE_VOTE_DAILY_LIMIT = 40;
const PACKAGE_VOTE_TOTAL_CHALLENGES = 40;
const PACKAGE_VOTE_VALID_AFTER_UTC = '{activated}';
let PACKAGE_VOTE_CHALLENGES = null;
let PACKAGE_VOTE_STATUS = 'idle';
let packageVoteCurrent = null;'''

def functions():
    return {
"packageVoteTodayKey": r'''
function packageVoteHash(value){
let h = 2166136261 >>> 0;
for(let i = 0; i < String(value).length; i++){
h ^= String(value).charCodeAt(i);
h = Math.imul(h, 16777619) >>> 0;
}
return h >>> 0;
}

function packageVoteCompletedKey(){
const voter = ktcCurrentVoterId() || 'unconfirmed';
return `package_votes_v7dev_completed_${voter}`;
}

function packageVoteCompleted(){
try {
const rows = JSON.parse(localStorage.getItem(packageVoteCompletedKey()) || '[]');
return Array.isArray(rows)
  ? Array.from(new Set(rows.map(String))).slice(0, PACKAGE_VOTE_TOTAL_CHALLENGES)
  : [];
} catch(e){
return [];
}
}

function packageVoteTodayKey(){
const voter = ktcCurrentVoterId() || 'unconfirmed';
return `package_votes_v7dev_${voter}_` + new Date().toISOString().slice(0,10);
}''',

"packageVotesToday": r'''
function packageVotesToday(){
return parseInt(localStorage.getItem(packageVoteTodayKey()) || '0', 10);
}''',

"packageVoteRecent": r'''
function packageVoteRecent(){
return packageVoteCompleted();
}''',

"packageVoteRemember": r'''
function packageVoteRemember(id){
const completed = packageVoteCompleted();
if(!completed.includes(String(id))) completed.push(String(id));
localStorage.setItem(
packageVoteCompletedKey(),
JSON.stringify(completed.slice(0, PACKAGE_VOTE_TOTAL_CHALLENGES))
);
}''',

"packageVoteSelectChallenge": r'''
function packageVoteSelectChallenge(){
if(!PACKAGE_VOTE_CHALLENGES || PACKAGE_VOTE_CHALLENGES.length !== PACKAGE_VOTE_TOTAL_CHALLENGES) return null;
const voter = ktcCurrentVoterId();
if(!voter) return null;

const completed = new Set(packageVoteCompleted());
const ordered = PACKAGE_VOTE_CHALLENGES.slice().sort((a,b) => {
const ha = packageVoteHash(`${voter}|order|${a.id}`);
const hb = packageVoteHash(`${voter}|order|${b.id}`);
if(ha !== hb) return ha - hb;
return String(a.id).localeCompare(String(b.id));
});
const challenge = ordered.find(c => !completed.has(String(c.id)));
if(!challenge) return null;

const left = (packageVoteHash(`${voter}|side|${challenge.id}`) & 1) === 0 ? 'A' : 'B';
return { challenge, left };
}''',

"packageVoteEnsureLoaded": r'''
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
doc.study_id !== 'package-adjustment-v7-multi-v-multi' ||
doc.stage !== 'phase1a_development_catalog' ||
doc.status !== 'FROZEN_PRE_VOTE_DEVELOPMENT_CATALOG' ||
doc.frozen !== true ||
doc.released !== false ||
doc.voting_activated !== false ||
doc.v7_votes_read !== false ||
doc.candidate_fit_performed !== false ||
doc.candidate_predictions_used_for_catalog_selection !== false ||
doc.fv_visible_to_voter !== false ||
Number(doc.challenge_count) !== 40 ||
!Array.isArray(doc.challenges) ||
doc.challenges.length !== 40 ||
!doc.challenges.every(c =>
  c &&
  c.schema_version === 1 &&
  c.experiment === 'package_adjustment_v7_multi_vs_multi_development' &&
  ['2v2','2v3','2v4','3v3','3v4','4v4'].includes(c.topology) &&
  c.fv_visible_to_voter === false &&
  c.candidate_prediction_used_for_selection === false &&
  c.side_A && Array.isArray(c.side_A.assets) &&
  c.side_B && Array.isArray(c.side_B.assets) &&
  c.side_A.assets.length >= 2 && c.side_A.assets.length <= 4 &&
  c.side_B.assets.length >= 2 && c.side_B.assets.length <= 4
)
){
throw new Error('unexpected frozen V7 development challenge catalog');
}
const ids = new Set(doc.challenges.map(c => String(c.id)));
if(ids.size !== 40) throw new Error('v7_development_duplicate_challenge_ids');

PACKAGE_VOTE_CHALLENGES = doc.challenges;
PACKAGE_VOTE_STATUS = 'ready';
packageVoteCurrent = null;
renderPackageVote();
})
.catch(err => {
console.warn('Package Adjustment V7 development catalog load failed:', err);
PACKAGE_VOTE_CHALLENGES = null;
PACKAGE_VOTE_STATUS = 'failed';
renderPackageVote();
});
}''',

"packageVoteAssetCard": r'''
function packageVoteAssetCard(p){
const age = (typeof p.age === 'number') ? ` &middot; ${p.age} y.o.` : '';
const team = p.team ? ` &middot; ${ktcTeamLabel(p.team)}` : '';
return `<div class="need-cell" style="text-align:left;padding:10px;">
<div style="font-weight:600;font-size:14px;">${escapeHtml(p.name)}</div>
<div style="color:var(--text-dim);font-size:11px;">${escapeHtml(p.pos)}${team}${age}</div>
</div>`;
}''',

"packageVoteSubmit": r'''
function packageVoteSubmit(displaySide){
if(Date.now() < Date.parse(PACKAGE_VOTE_VALID_AFTER_UTC)) return;
if(!packageVoteCurrent || packageVotesToday() >= PACKAGE_VOTE_DAILY_LIMIT) return;

const left = packageVoteCurrent.left;
const choice = displaySide === 'L' ? left : (left === 'A' ? 'B' : 'A');
const id = String(packageVoteCurrent.challenge.id);
const voter = ktcCurrentVoterId();
if(!voter) return;
if(packageVoteCompleted().includes(id)) return;

fetch(KTC_SUBMIT_URL, {
method: 'POST',
headers: { 'Content-Type': 'text/plain;charset=utf-8' },
body: JSON.stringify({
voterRosterId: voter,
keep: `__pkgv7dev__|${id}|${choice}`,
trade: `__pkgv7dev_meta__|${left}`,
cut: '__pkgv7dev_schema__|1',
}),
}).catch(() => {});

localStorage.setItem(packageVoteTodayKey(), String(packageVotesToday() + 1));
packageVoteRemember(id);
packageVoteCurrent = packageVoteSelectChallenge();
renderPackageVote();
}''',

"renderPackageVote": r'''
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
</div>`;
return;
}

if(Date.now() < Date.parse(PACKAGE_VOTE_VALID_AFTER_UTC)){
el.innerHTML = `<div style="color:var(--text-dim);font-size:13px;padding:8px 0;">
V7 multi-package development voting opens at ${new Date(PACKAGE_VOTE_VALID_AFTER_UTC).toLocaleString()}.
</div>`;
return;
}

const completedCount = packageVoteCompleted().length;
if(completedCount >= PACKAGE_VOTE_TOTAL_CHALLENGES){
el.innerHTML = `<div style="color:var(--green);font-size:13px;padding:8px 0;">
You've completed all ${PACKAGE_VOTE_TOTAL_CHALLENGES} V7 package comparisons. Thank you.
</div>`;
return;
}

if(PACKAGE_VOTE_STATUS === 'idle'){
packageVoteEnsureLoaded();
el.innerHTML = `<div style="color:var(--text-dim);font-size:13px;padding:8px 0;">Loading the frozen V7 multi-package comparisons...</div>`;
return;
}
if(PACKAGE_VOTE_STATUS === 'loading'){
el.innerHTML = `<div style="color:var(--text-dim);font-size:13px;padding:8px 0;">Loading the frozen V7 multi-package comparisons...</div>`;
return;
}
if(PACKAGE_VOTE_STATUS === 'failed'){
el.innerHTML = `<div style="color:var(--text-dim);font-size:13px;padding:8px 0;">V7 package research is temporarily unavailable. Normal KTC voting is unaffected.</div>`;
return;
}

if(!packageVoteCurrent) packageVoteCurrent = packageVoteSelectChallenge();
if(!packageVoteCurrent){
el.innerHTML = `<div style="color:var(--text-dim);font-size:13px;padding:8px 0;">No remaining V7 package comparison is available for this voter.</div>`;
return;
}

const c = packageVoteCurrent.challenge;
const canonicalA = c.side_A.assets.map(packageVoteAssetCard).join('');
const canonicalB = c.side_B.assets.map(packageVoteAssetCard).join('');
const leftIsA = packageVoteCurrent.left === 'A';
const leftHTML = leftIsA ? canonicalA : canonicalB;
const rightHTML = leftIsA ? canonicalB : canonicalA;

el.innerHTML = `
<div style="border:1px solid var(--line);border-radius:8px;padding:10px;margin-bottom:10px;font-size:12px;color:var(--text-dim);">
<b style="color:var(--text);">Multi-package research:</b> Which side would you rather receive in this dynasty trade?
Values are intentionally hidden. Choose based on the assets themselves.
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
${completedCount} / ${PACKAGE_VOTE_TOTAL_CHALLENGES} V7 comparisons completed &middot; order and display sides randomized per voter
</div>`;
}'''
    }

def patch_index(text: str, base_sha: str, activated: str) -> str:
    start = text.find("/* Package Adjustment V6P1 Prospective Confirmation:")
    if start < 0:
        raise RuntimeError("missing V6P1 package constants marker")
    end_marker = "let packageVoteCurrent = null;"
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError("missing package vote constants end")
    end += len(end_marker)
    text = text[:start] + constants_block(base_sha, activated) + text[end:]

    fn = functions()
    for name in (
        "packageVoteTodayKey","packageVotesToday","packageVoteRecent",
        "packageVoteRemember","packageVoteSelectChallenge","packageVoteEnsureLoaded",
        "packageVoteAssetCard","packageVoteSubmit","renderPackageVote",
    ):
        text = replace_function(text, name, fn[name])

    old_help = (
        '<div class="vote-help-text"><strong>Choose the trade side you would rather receive.</strong> '
        "These votes help measure how much extra value a multi-player package needs to match a more concentrated asset. "
        "This is research-only and does not change the live trade result yet.</div>"
    )
    new_help = (
        '<div class="vote-help-text"><strong>Choose the trade side you would rather receive.</strong> '
        "These V7 research votes test how asset concentration changes preference when both sides contain multiple players. "
        "Player values are hidden, and these votes do not change the live trade result.</div>"
    )
    if old_help not in text:
        raise RuntimeError("package vote help copy marker drift")
    return text.replace(old_help, new_help, 1)

def patch_ktc(text: str) -> str:
    if PREFIX in text:
        raise RuntimeError("V7 development prefix already present before activation")
    m = re.search(r'PACKAGE_VOTE_PREFIXES\s*=\s*\((.*?)\)\n', text, flags=re.S)
    if not m:
        raise RuntimeError("missing PACKAGE_VOTE_PREFIXES tuple")
    body = m.group(1).rstrip()
    if not body.endswith(","):
        body += ","
    body += ' "__pkgv7dev__|",'
    return text[:m.start(1)] + body + text[m.end(1):]

def write_manifest(base_sha: str, activated: str):
    cat = read_json(CATALOG)
    power = read_json(POWER)
    manifest = {
        "schema_version": 1,
        "study_id": "package-adjustment-v7-multi-v-multi",
        "stage": "development_voting_activation",
        "status": "V7_DEVELOPMENT_VOTING_ACTIVATED",
        "activated_at_utc": activated,
        "valid_ballot_start_utc": activated,
        "research_only": True,
        "production_change_authorized": False,
        "candidate_fit_performed": False,
        "candidate_scores_read": False,
        "v7_vote_outcomes_read_at_activation": False,
        "source_catalog_commit": base_sha,
        "catalog": {
            "path": "research/package-adjustment-v7/package_vote_challenges_v7_development_v1.json",
            "sha256": sha256(CATALOG),
            "challenge_count": cat["challenge_count"],
            "topology_counts": cat["diagnostics"]["topology_counts"],
            "candidate_predictions_used_for_selection": False,
            "fv_visible_to_voter": False,
        },
        "maturity_contract": {
            "first_checkpoint_distinct_voters": power["selected_first_checkpoint_distinct_voters"],
            "minimum_distinct_voters_per_challenge": power["coverage_gate_at_or_after_first_checkpoint"]["minimum_distinct_voters_per_challenge"],
            "hard_cap_distinct_voters": power["hard_cap_distinct_voters"],
            "stopping_may_use_vote_direction": False,
            "stopping_may_use_candidate_performance": False,
        },
        "transport": {
            "vote_prefix": PREFIX,
            "meta_prefix": META_PREFIX,
            "schema_marker": SCHEMA_MARKER,
            "canonical_choices": ["A","B"],
            "canonical_left_sides": ["A","B"],
            "one_vote_per_voter_per_challenge_analysis_rule": "first valid post-activation row only",
            "browser_daily_limit": 40,
            "all_40_one_session_supported": True,
        },
        "browser_sampling": {
            "challenge_order": "deterministic pseudorandom permutation keyed by voter id; each of 40 shown once",
            "display_side": "deterministic pseudorandom A/B swap keyed by voter id and challenge id",
            "reload_stability": True,
            "local_progress_saved": True,
            "candidate_predictions_used": False,
        },
        "isolation": {
            "ktc_pipeline_reserves_v7_prefix": True,
            "normal_ktc_ratings_do_not_consume_v7_rows": True,
            "v6_vote_namespaces_unchanged": True,
            "rows_at_or_before_valid_ballot_start_utc_invalid": True,
            "draft_picks_included": False,
        },
        "next_action": "Collect V7 development ballots and use only an outcome-blind maturity monitor until the frozen coverage gate is reached.",
    }
    OUT_MAN.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(
        "# Package Adjustment V7 — Development Voting Activation\n\n"
        f"Activated: `{activated}`\n\n"
        "- Research only; production remains V1.7.\n"
        "- Frozen catalog: 40 player-only multi-v-multi challenges.\n"
        "- First checkpoint: 40 distinct voters.\n"
        "- Coverage gate: 32 distinct voters on every challenge.\n"
        "- Hard cap: 50 distinct voters.\n"
        "- FV and candidate scores remain hidden.\n",
        encoding="utf-8",
    )

def write(base_sha: str):
    validate_frozen_inputs()
    if OUT_MAN.exists() or OUT_MD.exists():
        raise RuntimeError("activation output already exists")
    activated = datetime.now(timezone.utc).isoformat()
    INDEX.write_text(
        patch_index(INDEX.read_text(encoding="utf-8"), base_sha, activated),
        encoding="utf-8",
    )
    KTC.write_text(patch_ktc(KTC.read_text(encoding="utf-8")), encoding="utf-8")
    write_manifest(base_sha, activated)

def check():
    validate_frozen_inputs()
    man = read_json(OUT_MAN)
    assert man["status"] == "V7_DEVELOPMENT_VOTING_ACTIVATED"
    assert man["candidate_fit_performed"] is False
    assert man["candidate_scores_read"] is False
    assert man["v7_vote_outcomes_read_at_activation"] is False
    assert man["production_change_authorized"] is False
    assert man["maturity_contract"]["first_checkpoint_distinct_voters"] == 40
    assert man["maturity_contract"]["minimum_distinct_voters_per_challenge"] == 32
    assert man["maturity_contract"]["hard_cap_distinct_voters"] == 50

    index = INDEX.read_text(encoding="utf-8")
    ktc = KTC.read_text(encoding="utf-8")
    assert f"const PACKAGE_VOTE_CATALOG_SHA256 = '{CATALOG_SHA256}';" in index
    assert "const PACKAGE_VOTE_TOTAL_CHALLENGES = 40;" in index
    assert man["source_catalog_commit"] in index
    assert "__pkgv7dev__|" in index
    assert "__pkgv7dev_meta__|" in index
    assert "__pkgv7dev_schema__|1" in index
    assert "package_votes_v7dev_completed_" in index
    assert "packageVoteHash(`${voter}|order|${a.id}`)" in index
    assert "packageVoteHash(`${voter}|side|${challenge.id}`)" in index
    assert ktc.count('"__pkgv7dev__|"') == 1
    print("PASS: V7 voting activation revalidated.")

def selftest():
    index = '''<div class="vote-help-text"><strong>Choose the trade side you would rather receive.</strong> These votes help measure how much extra value a multi-player package needs to match a more concentrated asset. This is research-only and does not change the live trade result yet.</div>
/* Package Adjustment V6P1 Prospective Confirmation: x
Research only. Production Package Adjustment remains V1.6. */
const PACKAGE_VOTE_CHALLENGES_URL = 'old';
const PACKAGE_VOTE_CATALOG_SHA256 = 'old';
const PACKAGE_VOTE_DAILY_LIMIT = 40;
const PACKAGE_VOTE_RECENT_MEMORY = 24;
const PACKAGE_VOTE_VALID_AFTER_UTC = 'old';
let PACKAGE_VOTE_CHALLENGES = null;
let PACKAGE_VOTE_STATUS = 'idle';
let packageVoteCurrent = null;
function packageVoteTodayKey(){return 'old';}
function packageVotesToday(){return 0;}
function packageVoteRecent(){return [];}
function packageVoteRemember(id){}
function packageVoteSelectChallenge(){return null;}
function packageVoteEnsureLoaded(){}
function packageVoteAssetCard(p){return '';}
function packageVoteSubmit(s){}
function renderPackageVote(){}
'''
    patched = patch_index(index, "abc123", "2026-09-25T00:00:00+00:00")
    assert "__pkgv7dev__|" in patched
    assert "package_votes_v7dev_completed_" in patched
    assert patched.count("function packageVoteHash(") == 1
    assert patched.count("function renderPackageVote(") == 1

    ktc = 'PACKAGE_VOTE_PREFIXES = ("__pkgv6__|", "__pkgv6p1__|",)\n'
    assert patch_ktc(ktc).count('"__pkgv7dev__|"') == 1
    print("PASS: activation patcher self-test.")

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    ap.add_argument("--base-sha")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    elif a.write:
        if not a.base_sha:
            raise SystemExit("--base-sha required")
        write(a.base_sha)
    else:
        check()

if __name__ == "__main__":
    main()
