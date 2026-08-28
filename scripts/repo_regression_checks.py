#!/usr/bin/env python3
"""High-value repository regression checks for Trade Desk.

These checks focus on the drift/correctness problems fixed in the 2026-08-28
repo audit. They require no network access.

Run from anywhere:
    python3 scripts/repo_regression_checks.py
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
INDEX = REPO_ROOT / "index.html"
DATA = REPO_ROOT / "data"

sys.path.insert(0, str(SCRIPT_DIR))

import snapshot_values
import sync_sleeper
import dual_eligibility_pipeline
import team_field_refresh_pipeline
import idp_v1_projection
from generate_player_positions import parse_player_positions, build_player_position_lookup


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
    print(f"PASS position/free-agent invariants: {len(seen)} free agents, 0 roster overlap")


def check_dual_eligibility_audit():
    rows = json.load(open(SCRIPT_DIR / "dual_eligibility_results.json"))
    assert all("recommended_bucket" not in r for r in rows), "retired economic recommended_bucket still present"
    mismatches = [r for r in rows if r.get("current_position_is_eligible") is False]
    # Current cache has two unique-name current-position mismatches. Surface;
    # don't auto-correct because special cases such as two-way players exist.
    names = {r["player"] for r in mismatches}
    assert "james pearce" in names, "known stale-position audit case no longer surfaced"
    assert "travis hunter" in names, "known two-way/manual-review case no longer surfaced"
    print(f"PASS eligibility audit: {len(rows)} review rows, {len(mismatches)} current-position mismatches surfaced")


def check_team_identity():
    refresh = json.load(open(SCRIPT_DIR / "player_team_refresh.json"))
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
    stored = json.load(open(SCRIPT_DIR / "player_positions.json"))
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
    baseline_path = SCRIPT_DIR / "prod_mult_pre_v1_baseline.json"
    assert baseline_path.exists(), "missing immutable pre-V1 PROD_MULT baseline snapshot"
    baseline = json.load(open(baseline_path))
    assert baseline.get("snapshot_type") == "baked_prod_mult_data"
    assert baseline.get("entry_count") == len(baseline.get("values", {}))
    assert baseline.get("entry_count") > 0
    print(
        f"PASS IDP V1 projection/baseline invariants: "
        f"{baseline['entry_count']} immutable pre-V1 PROD_MULT entries"
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
        check_index_js_syntax,
    ]
    for check in checks:
        check()
    print(f"\nALL REPO REGRESSION CHECKS PASSED ({len(checks)} groups).")


if __name__ == "__main__":
    main()
