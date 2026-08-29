#!/usr/bin/env python3
"""High-value repository regression checks for Trade Desk.

These checks focus on the drift/correctness problems fixed in the 2026-08-28
repo audit. They require no network access.

Run from anywhere:
    python3 scripts/repo_regression_checks.py
"""

import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
INDEX = REPO_ROOT / "index.html"
DATA = REPO_ROOT / "data"

sys.path.insert(0, str(SCRIPT_DIR.parent))

import snapshot_values
import sync_sleeper
import dual_eligibility_pipeline
import team_field_refresh_pipeline
import idp_v1_projection
import production_history_component
import validate_idp_v1_final_deployment
import validate_free_agent_valuation_parity
from generate_player_positions import parse_player_positions, build_player_position_lookup

IDP_V1_RELEASE_MANIFEST = SCRIPT_DIR.parent / "idp_v1_release_manifest.json"


def _sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _validate_idp_v1_release_manifest():
    """Protect frozen deployed-release artifacts from silent regeneration.

    The 2026-08-28 IDP V1 bake is a deployed release, not a live view of
    whatever the latest historical/projection source files happen to contain.
    General repo maintenance may refresh those source files later. That must
    not retroactively rewrite the approved candidate/patch/baseline lineage.
    """
    assert IDP_V1_RELEASE_MANIFEST.exists(), "missing frozen IDP V1 release manifest"
    manifest = json.load(open(IDP_V1_RELEASE_MANIFEST, encoding="utf-8"))
    assert manifest.get("status") == "deployed_validated_frozen"
    immutable = manifest.get("immutable_release_artifacts") or {}
    assert immutable, "IDP V1 release manifest has no immutable artifacts"
    mismatches = []
    for rel, expected in immutable.items():
        path = REPO_ROOT / rel
        if not path.exists():
            mismatches.append((rel, "missing", expected))
            continue
        actual = _sha256_file(path)
        if actual != expected:
            mismatches.append((rel, actual, expected))
    assert not mismatches, f"frozen IDP V1 release artifacts changed: {mismatches[:10]}"
    return manifest


def _release_lineage_drift(manifest):
    """Return release source/code files whose current bytes differ from release."""
    changed = []
    for section in ("release_source_snapshot_sha256", "release_lineage_code_snapshot_sha256"):
        for rel, expected in (manifest.get(section) or {}).items():
            path = REPO_ROOT / rel
            actual = _sha256_file(path) if path.exists() else "missing"
            if actual != expected:
                changed.append(rel)
    return sorted(set(changed))


def _extract_balanced_statement(text, marker, open_char="{", close_char="}"):
    start = text.find(marker)
    if start < 0:
        raise AssertionError(f"Missing JS marker: {marker}")
    open_idx = text.find(open_char, start)
    if open_idx < 0:
        raise AssertionError(f"Missing opening {open_char} after {marker}")

    depth = 0
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    i = open_idx
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
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                # Include trailing semicolon if present.
                end = i + 1
                while end < len(text) and text[end].isspace():
                    end += 1
                if end < len(text) and text[end] == ";":
                    end += 1
                return text[start:end]
        i += 1
    raise AssertionError(f"Unbalanced JS statement: {marker}")


def _extract_function(text, name):
    return _extract_balanced_statement(text, f"function {name}(")


def _extract_const_object(text, name):
    return _extract_balanced_statement(text, f"const {name} =")


def _extract_scalar_const(text, name):
    m = re.search(rf"const\s+{re.escape(name)}\s*=\s*[^;]+;", text)
    if not m:
        raise AssertionError(f"Missing scalar const {name}")
    return m.group(0)


def live_js_values():
    """Run the actual live valuation JS functions from index.html in Node."""
    text = INDEX.read_text(encoding="utf-8")
    parts = [
        _extract_const_object(text, "POSITION_WEIGHT"),
        _extract_const_object(text, "AGE_CURVE"),
        _extract_scalar_const(text, "QB_POST_PEAK_FLOOR"),
        _extract_scalar_const(text, "LB_POST_PEAK_DECAY_POWER"),
        _extract_const_object(text, "ROLE_MULT"),
        _extract_const_object(text, "PROD_MULT_DATA"),
        "const PROD_MULT = PROD_MULT_DATA;",
        _extract_const_object(text, "NO_REAL_PRODUCTION_HISTORY"),
        _extract_const_object(text, "PLAYER_DB"),
        re.search(r"function normalizeName\(s\)\{.*?\n\}", text, re.S).group(0),
        _extract_function(text, "productionMultiplier"),
        _extract_function(text, "ageMultiplier"),
        _extract_function(text, "playerValue"),
        r"""
const __rows = {};
for (const [key, info] of Object.entries(PLAYER_DB)) {
  const rm = productionMultiplier(key, info.role);
  const rawRm = Object.prototype.hasOwnProperty.call(PROD_MULT, key) ? PROD_MULT[key] : null;
  const am = ageMultiplier(info.pos, info.age, info.role, rm, rawRm);
  __rows[key] = {
    value: playerValue(info.pos, info.age, info.role, key),
    prod_mult: rm,
    age_mult: am,
  };
}
process.stdout.write(JSON.stringify(__rows));
""",
    ]
    js = "\n\n".join(parts)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        path = f.name
    try:
        proc = subprocess.run(["node", path], capture_output=True, text=True, check=True)
        return json.loads(proc.stdout)
    finally:
        os.unlink(path)


def check_snapshot_parity():
    cfg = snapshot_values.load_from_html(INDEX)
    py_rows = snapshot_values.compute_all_values(cfg)
    js_rows = live_js_values()
    assert set(py_rows) == set(js_rows), "snapshot/live PLAYER_DB key sets differ"

    diffs = []
    for key in py_rows:
        p = py_rows[key]
        j = js_rows[key]
        if p["value"] != j["value"]:
            diffs.append((key, "value", p["value"], j["value"]))
        if abs(p["prod_mult"] - j["prod_mult"]) > 1e-6:
            diffs.append((key, "prod_mult", p["prod_mult"], j["prod_mult"]))
        if abs(p["age_mult"] - j["age_mult"]) > 1e-6:
            diffs.append((key, "age_mult", p["age_mult"], j["age_mult"]))
    assert not diffs, f"snapshot/live valuation drift: first differences {diffs[:10]}"
    print(f"PASS snapshot/live valuation parity: {len(py_rows)} players, 0 differences")


def check_position_rules_and_free_agents():
    assert sync_sleeper.pick_best_position(["DE", "LB"], "DE") == "DL"
    assert sync_sleeper.pick_best_position(["LB", "DE"], "DE") == "LB"
    assert sync_sleeper.pick_best_position(["S", "LB"], "S") == "DB"

    fa = json.load(open(DATA / "free_agents.json"))
    rostered = set()
    rosters = json.load(open(DATA / "league_rosters.json"))["rosters"]
    for roster in rosters:
        for slot in ("starters", "bench", "taxi", "reserve_ir"):
            for player in roster.get(slot) or []:
                rostered.add(str(player["player_id"]))

    seen = set()
    for row in fa["free_agents"]:
        pid = str(row["player_id"])
        assert pid not in rostered, f"rostered player appears in free_agents: {pid} {row['name']}"
        assert pid not in seen, f"duplicate free-agent Sleeper ID: {pid}"
        seen.add(pid)
        assert "fantasy_positions" in row, f"missing fantasy_positions: {row['name']}"
        expected = sync_sleeper.pick_best_position(row.get("fantasy_positions"), row.get("raw_position"))
        assert row.get("pos") == expected, f"free-agent primary-position drift: {row['name']} {row.get('pos')} != {expected}"

    # Clean-checkout reproducibility: committed free_agents.json must be exactly
    # derivable from the committed Sleeper cache + committed league rosters.
    # This catches a surprisingly common failure mode where one generated file
    # refreshes without its dependent waiver-wire snapshot. Compare by stable
    # Sleeper ID so source iteration order is not a false failure.
    cache_doc = json.load(open(DATA / "players_cache.json"))
    regenerated = sync_sleeper.compute_free_agents(cache_doc["players"], rostered)
    stored_by_id = {str(r["player_id"]): r for r in fa["free_agents"]}
    regenerated_by_id = {str(r["player_id"]): r for r in regenerated}
    assert fa.get("count") == len(stored_by_id), "free_agents.json count metadata is stale"
    assert stored_by_id == regenerated_by_id, (
        "free_agents.json is stale relative to committed players_cache.json / "
        "league_rosters.json; run the Sleeper sync or regenerate from the cache"
    )
    print(
        f"PASS position/free-agent invariants: {len(seen)} free agents, 0 roster overlap, "
        "committed cache regeneration exact"
    )


def check_dual_eligibility_audit():
    rows = json.load(open(SCRIPT_DIR.parent / "dual_eligibility_results.json"))
    assert all("recommended_bucket" not in r for r in rows), "retired economic recommended_bucket still present"
    mismatches = [r for r in rows if r.get("current_position_is_eligible") is False]
    # Current cache has two unique-name current-position mismatches. Surface;
    # don't auto-correct because special cases such as two-way players exist.
    names = {r["player"] for r in mismatches}
    assert "james pearce" in names, "known stale-position audit case no longer surfaced"
    assert "travis hunter" in names, "known two-way/manual-review case no longer surfaced"
    print(f"PASS eligibility audit: {len(rows)} review rows, {len(mismatches)} current-position mismatches surfaced")


def check_team_identity():
    refresh = json.load(open(SCRIPT_DIR.parent / "player_team_refresh.json"))
    by_id = refresh["teams_by_sleeper_id"]
    by_name = refresh["teams"]
    collisions = refresh["name_collisions"]
    assert len(by_id) == refresh["n_players"]
    for name in collisions:
        assert name not in by_name, f"ambiguous name leaked into fallback team map: {name}"

    # Exercise the actual live JS team-precedence helper with a deliberately
    # wrong name fallback to prove stable-ID-resolved p.team wins.
    text = INDEX.read_text(encoding="utf-8")
    helper = _extract_function(text, "resolveSyncedTeam")
    js = (
        "const PLAYER_TEAM = {collision:'WRONG'};\n" + helper + "\n" +
        "const out = [" +
        "resolveSyncedTeam({team:'LIVE'}, 'collision', {team:'CURATED'})," +
        "resolveSyncedTeam({}, 'collision', {team:'CURATED'})," +
        "resolveSyncedTeam({}, 'collision', null)" +
        "]; process.stdout.write(JSON.stringify(out));"
    )
    proc = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    assert json.loads(proc.stdout) == ["LIVE", "CURATED", "WRONG"]
    print(f"PASS team identity: {len(by_id)} ID mappings, {len(collisions)} ambiguous names safely excluded")


def check_aliases_and_ktc_positions():
    subprocess.run([sys.executable, str(SCRIPT_DIR / "check_no_duplicate_prod_mult_keys.py")], cwd=REPO_ROOT, check=True)
    canonical = parse_player_positions(INDEX)
    expected = build_player_position_lookup(INDEX)
    stored = json.load(open(SCRIPT_DIR.parent / "player_positions.json"))
    assert stored == expected, "player_positions.json is stale relative to canonical PLAYER_DB/alias data"
    for key, pos in canonical.items():
        assert stored.get(key) == pos, f"canonical KTC position missing/wrong: {key}"

    # Historical vote labels that previously displaced canonical rows must now
    # coexist as compatibility aliases rather than replacing the real key.
    expected_aliases = {
        "c schwesinger": "LB",
        "d ezeiruaku": "DL",
        "m fitzpatrick": "DB",
        "t stevenson": "DB",
        "michael penix": "QB",
        "harold perkins": "LB",
        "zonovan knight": "RB",
    }
    for alias, pos in expected_aliases.items():
        assert stored.get(alias) == pos, f"KTC legacy alias missing: {alias}"

    ratings_path = SCRIPT_DIR / "ktc_ratings.json"
    unresolved = set()
    if ratings_path.exists():
        ratings = json.load(open(ratings_path))
        for section in ("league_only", "all_voters_combined"):
            for player in ratings.get(section, {}).get("player_ratings", {}):
                if player not in stored:
                    unresolved.add(player)
        # Any unresolved names must not be one of the known aliases we know how
        # to resolve; they are historical/out-of-PLAYER_DB players and should
        # be surfaced explicitly by ktc_pipeline rather than silently guessed.
        assert not (unresolved & set(expected_aliases)), unresolved
    print(
        f"PASS alias/KTC position integrity: {len(canonical)} canonical + "
        f"{len(stored)-len(canonical)} compatibility aliases; "
        f"{len(unresolved)} historical/out-of-DB rated names remain explicit"
    )



def check_idp_v1_projection_invariants():
    idp_v1_projection.run_selftest()
    baseline_path = SCRIPT_DIR.parent / "prod_mult_pre_v1_baseline.json"
    assert baseline_path.exists(), "missing immutable pre-V1 PROD_MULT baseline snapshot"
    baseline = json.load(open(baseline_path))
    assert baseline.get("snapshot_type") == "baked_prod_mult_data"
    assert baseline.get("entry_count") == len(baseline.get("values", {}))
    assert baseline.get("entry_count") > 0
    print(
        f"PASS IDP V1 projection/baseline invariants: "
        f"{baseline['entry_count']} immutable pre-V1 PROD_MULT entries"
    )



def check_canonical_history_and_v1_bridge():
    production_history_component.run_selftest()
    manifest = _validate_idp_v1_release_manifest()

    # The deployed V1 release artifacts are intentionally frozen. Historical
    # source files (especially ppg_results.json) can be refreshed later by
    # separate workflows. A source refresh is not permission to silently
    # rewrite a production release.
    frozen_history = json.load(open(SCRIPT_DIR.parent / "production_history_components.json"))
    assert frozen_history.get("method") == "canonical_history_component_v1_preserve_legacy_math"
    assert len(frozen_history.get("players", {})) == 858

    all_players = json.load(open(SCRIPT_DIR.parent / "all_players.json"))
    ppg_rows = json.load(open(SCRIPT_DIR.parent / "ppg_results.json"))
    durability = json.load(open(SCRIPT_DIR / "durability_results.json"))
    regenerated_now = production_history_component.build_history_output(all_players, ppg_rows, durability)
    lineage_drift = _release_lineage_drift(manifest)

    if lineage_drift:
        # Expected post-release behavior: current source/code snapshots may
        # move. Keep the deployed release frozen and surface the drift clearly.
        print(
            "INFO IDP V1 release lineage snapshot differs from current repo inputs; "
            "frozen deployed artifacts intentionally preserved. Changed: "
            + ", ".join(lineage_drift)
        )
    else:
        # If every release input/code file is still byte-identical, then the
        # canonical generator must reproduce the frozen artifact exactly.
        assert regenerated_now == frozen_history, (
            "IDP V1 history generator no longer reproduces the frozen release "
            "despite identical release source/code snapshots"
        )

    # Validate the *approved frozen release candidate*, not a newly regenerated
    # candidate built from mutable current league/source data.
    bridge = json.load(open(SCRIPT_DIR / "idp_v1_model_delta_transport_candidate.json"))
    players = bridge["players"]
    assert len(players) == 404, f"unexpected frozen IDP bridge population: {len(players)}"
    assert bridge["comparable_player_count"] == 330, bridge["comparable_player_count"]
    assert sum(bridge["source_cohort_counts"].values()) == len(players)

    position_mismatches = [
        key for key, r in players.items()
        if r.get("legacy_model_position") != r.get("current_valuation_position")
    ]
    assert len(position_mismatches) == 46, (
        "frozen release legacy/current position mismatch cohort changed",
        len(position_mismatches),
    )

    for key, r in players.items():
        assert math.isfinite(r["candidate_prod_mult"]), key
        assert 0.15 <= r["candidate_prod_mult"] <= 1.55, key
        if r["update_status"] == "exact_hold_no_comparable_old_projection":
            assert r["candidate_prod_mult"] == r["old_live_prod_mult"], key

    assert players["bradley chubb"]["candidate_prod_mult"] > players["bradley chubb"]["old_live_prod_mult"]
    assert players["myles garrett"]["candidate_prod_mult"] > players["myles garrett"]["old_live_prod_mult"]
    assert abs(players["fred warner"]["pct_change"]) < 3.0
    assert players["isaiah mcduffie"]["candidate_prod_mult"] < players["isaiah mcduffie"]["old_live_prod_mult"]

    for pos in ("LB", "DL", "DB"):
        old_b = bridge["old_model_baseline_by_position"][pos]
        new_b = bridge["new_model_baseline_by_position"][pos]
        shift = abs(new_b / old_b - 1)
        assert shift < 0.10, f"{pos} V1 model baseline shift unexpectedly large: {shift:.1%}"

    print(
        "PASS frozen IDP V1 release/history bridge invariants: "
        f"{len(frozen_history['players'])} frozen history rows; {len(players)} release IDPs; "
        f"{bridge['comparable_player_count']} comparable model-delta rows; "
        f"{len(position_mismatches)} position mismatches isolated; "
        f"{len(lineage_drift)} current lineage files drifted since release"
    )



def check_preferred_bake_preview_invariants():
    patch_path = SCRIPT_DIR / "idp_v1_prod_mult_patch.json"
    candidate_path = SCRIPT_DIR / "idp_v1_model_delta_transport_candidate.json"
    baseline_path = SCRIPT_DIR / "prod_mult_pre_v1_baseline.json"
    assert patch_path.exists() and candidate_path.exists(), "preferred V1 preview artifacts missing"

    patch = json.load(open(patch_path))
    candidate = json.load(open(candidate_path))
    baseline = json.load(open(baseline_path))["values"]
    entries = patch.get("entries", [])
    assert patch.get("changed_entry_count") == len(entries)
    assert patch.get("candidate_player_count") == len(candidate["players"])

    seen = set()
    for e in entries:
        key = e["key"]
        assert key not in seen, f"duplicate preferred-bake patch key: {key}"
        seen.add(key)
        assert key in baseline, key
        assert key in candidate["players"], key
        assert abs(float(e["old"]) - float(baseline[key])) < 1e-12, key
        assert abs(float(e["new"]) - float(candidate["players"][key]["candidate_prod_mult"])) < 1e-12, key
        assert e["pos"] in {"LB", "DL", "DB"}, key

    floor_guarded = {
        key for key, r in candidate["players"].items()
        if r.get("update_status") == "exact_hold_floor_rescue_discontinuity_guard"
    }
    assert floor_guarded == {"jaishawn barham", "jake golday", "kaleb elarmsorr", "kyle louis"}, floor_guarded

    for key, r in candidate["players"].items():
        if r["candidate_prod_mult"] == r["old_live_prod_mult"]:
            assert key not in seen, f"exact hold unexpectedly present in bake patch: {key}"

    assert len(entries) == 320, f"unexpected preferred-bake change count: {len(entries)}"
    print(
        f"PASS preferred V1 bake-preview invariants: {len(entries)} changed PROD_MULT entries, "
        f"{len(candidate['players'])-len(entries)} exact holds (including {len(floor_guarded)} floor-rescue guards)"
    )


def check_deployed_idp_v1_invariants():
    result = validate_idp_v1_final_deployment.validate_deployment()
    assert result["status"] == "PASS"
    assert result["actual_changed_entry_count"] == 320, result["actual_changed_entry_count"]
    assert result["approved_changed_entry_count"] == 320
    assert result["non_idp_final_value_changes"] == 0
    assert result["update_status_counts"].get("exact_hold_floor_rescue_discontinuity_guard") == 4
    assert result["position_lineage_mismatch_count"] == 46
    print(
        "PASS deployed IDP V1 invariants: "
        f"{result['actual_changed_entry_count']} approved PROD_MULT changes; "
        f"{result['exact_hold_candidate_count']} exact holds; "
        f"{result['non_idp_final_value_changes']} offense value changes"
    )

def check_free_agent_board_parity():
    result = validate_free_agent_valuation_parity.validate()
    assert result["status"] == "PASS"
    assert result["canonical_player_values_checked"] == 565
    assert result["synthetic_cases_checked"] >= 8
    assert result["fa_source_precedence_cases_checked"] == 1
    assert result["roster_overlap"] == 0
    print(
        "PASS free-agent board valuation parity: "
        f"{result['canonical_player_values_checked']} canonical values; "
        f"{result['synthetic_cases_checked']} canonical synthetic branches + "
        f"{result['fa_source_precedence_cases_checked']} FA source-precedence branch; "
        f"{result['free_agents_rendered']} rendered free agents"
    )


def check_index_js_syntax():
    text = INDEX.read_text(encoding="utf-8")
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", text, re.S | re.I)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write("\n".join(scripts))
        path = f.name
    try:
        subprocess.run(["node", "--check", path], check=True, capture_output=True, text=True)
    finally:
        os.unlink(path)
    print("PASS index.html inline JavaScript syntax")


def main():
    checks = [
        check_snapshot_parity,
        check_position_rules_and_free_agents,
        check_dual_eligibility_audit,
        check_team_identity,
        check_aliases_and_ktc_positions,
        check_idp_v1_projection_invariants,
        check_canonical_history_and_v1_bridge,
        check_preferred_bake_preview_invariants,
        check_deployed_idp_v1_invariants,
        check_free_agent_board_parity,
        check_index_js_syntax,
    ]
    for check in checks:
        check()
    print(f"\nALL REPO REGRESSION CHECKS PASSED ({len(checks)} groups).")


if __name__ == "__main__":
    main()
