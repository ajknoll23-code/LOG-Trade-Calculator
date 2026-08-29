#!/usr/bin/env python3
"""Validate free-agent-board valuation parity against the canonical Trade Desk.

This is intentionally deeper than a syntax check. It verifies:

1. generated source regions in free-agent-board.html exactly match index.html;
2. the board's JavaScript valuation outputs match snapshot_values.py for every
   canonical PLAYER_DB row;
3. critical synthetic boundary cases match the canonical Python port;
4. the full free-agent board executes in Node against the committed
   data/free_agents.json with finite/valid values and expected exclusions;
5. same-name collision guards still protect Justin Jefferson (LB) and Devonta
   Smith (DB) from inheriting the unrelated star WR records;
6. rostered Sleeper IDs do not appear in the free-agent source data.

No network access and no file writes are required.
"""

from __future__ import annotations

from collections import Counter
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
INDEX = REPO_ROOT / "index.html"
BOARD = REPO_ROOT / "free-agent-board.html"
FREE_AGENTS = REPO_ROOT / "data" / "free_agents.json"
LEAGUE_ROSTERS = REPO_ROOT / "data" / "league_rosters.json"

sys.path.insert(0, str(SCRIPT_DIR))
import snapshot_values
import sync_free_agent_valuation

VALID_POSITIONS = {"QB", "RB", "WR", "TE", "DL", "LB", "DB", "K"}
VALID_ROLES = {"Elite", "Every-Down", "Starter", "Rotational", "Understudy", "Depth", "Speculative"}
EXCLUDED_FREE_AGENTS = {("byron young", "DL"), ("devonta smith", "DB")}


def normalize_name(value: str) -> str:
    """Python port of the canonical JS normalizeName() for audit-only matching."""
    s = str(value or "").strip().lower()
    s = re.sub(r"[.'\u2019-]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _run_node(js: str):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        path = f.name
    try:
        proc = subprocess.run(["node", path], capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(f"Node harness failed:\n{proc.stderr}")
        return json.loads(proc.stdout)
    finally:
        os.unlink(path)


def _board_canonical_values(board_text: str):
    core = sync_free_agent_valuation._extract_core(board_text)[2]
    player_db = sync_free_agent_valuation._extract_const_object(board_text, "PLAYER_DB")[2]
    normalize = sync_free_agent_valuation._extract_function(board_text, "normalizeName")[2]
    js = "\n\n".join(
        [
            core,
            player_db,
            normalize,
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
    )
    return _run_node(js)


def _synthetic_js_values(board_text: str):
    core = sync_free_agent_valuation._extract_core(board_text)[2]
    player_db = sync_free_agent_valuation._extract_const_object(board_text, "PLAYER_DB")[2]
    normalize = sync_free_agent_valuation._extract_function(board_text, "normalizeName")[2]
    cases = [
        ("floor_with_history", "WR", 23, "Depth", 0.15, False),
        ("floor_no_history", "WR", 23, "Depth", 0.15, True),
        ("elite_floor", "LB", 30, "Elite", 0.20, False),
        ("lb_age_31", "LB", 31, "Starter", 0.80, False),
        ("young_wr_continuous", "WR", 22, "Starter", 0.769, False),
        ("young_rb_elite", "RB", 21, "Elite", 1.10, False),
        ("old_qb", "QB", 38, "Starter", 0.80, False),
        ("no_real_data", "TE", 23, "Speculative", None, False),
    ]
    js_cases = json.dumps(cases)
    js = "\n\n".join(
        [
            core,
            player_db,
            normalize,
            f"const __cases = {js_cases};",
            r"""
const __out = {};
for (const [label, pos, age, role, prod, noHistory] of __cases) {
  const key = '__parity_' + label;
  delete PROD_MULT[key];
  delete NO_REAL_PRODUCTION_HISTORY[key];
  if (prod !== null) PROD_MULT[key] = prod;
  if (noHistory) NO_REAL_PRODUCTION_HISTORY[key] = 1;
  const rm = productionMultiplier(key, role);
  const rawRm = Object.prototype.hasOwnProperty.call(PROD_MULT, key) ? PROD_MULT[key] : null;
  const am = ageMultiplier(pos, age, role, rm, rawRm);
  __out[label] = {value: playerValue(pos, age, role, key), prod_mult: rm, age_mult: am};
  delete PROD_MULT[key];
  delete NO_REAL_PRODUCTION_HISTORY[key];
}
process.stdout.write(JSON.stringify(__out));
""",
        ]
    )
    return cases, _run_node(js)


def _board_runtime_rows(board_text: str, free_agent_doc: dict):
    m = re.search(r"<script>(.*?)</script>", board_text, re.S | re.I)
    if not m:
        raise AssertionError("free-agent-board.html has no inline script")
    script = m.group(1)
    call = "loadFreeAgents();"
    idx = script.rfind(call)
    if idx < 0:
        raise AssertionError("free-agent board no longer calls loadFreeAgents()")
    script = script[:idx] + script[idx + len(call) :]

    js = f"""
(async()=>{{
const __data = {json.dumps(free_agent_doc)};
const __els = new Map();
globalThis.document = {{
  getElementById(id) {{
    if (!__els.has(id)) __els.set(id, {{className:'', textContent:'', innerHTML:''}});
    return __els.get(id);
  }}
}};
globalThis.fetch = async () => ({{ok:true, status:200, json:async()=>__data}});
{script}
await loadFreeAgents();
const __sourceCounts = {{
  speculative_estimate: 0,
  fa_specific_prod: 0,
  canonical_prod: 0,
  canonical_role_only: 0
}};
const __sourceById = {{}};
for (const fa of (__data.free_agents || [])) {{
  const rawKey = normalizeName(fa.name);
  if ([['byron young','DL'],['devonta smith','DB']].some(([n,p]) => n === rawKey && p === fa.pos)) continue;
  const key = ALIASES[rawKey] || ALIASES_REVERSE[rawKey] || rawKey;
  const candidateCurated = PLAYER_DB[key];
  const curated = (candidateCurated && candidateCurated.pos === fa.pos) ? candidateCurated : null;
  const faProdRaw = FA_PROD_MULT_DATA[key];
  const faProdEntry = Array.isArray(faProdRaw)
    ? faProdRaw.find(e => e.pos === fa.pos) || null
    : faProdRaw;
  const faProdMatch = (faProdEntry && faProdEntry.pos === fa.pos) ? faProdEntry : null;
  let source;
  if (curated && Object.prototype.hasOwnProperty.call(PROD_MULT, key)) source = 'canonical_prod';
  else if (faProdMatch) source = 'fa_specific_prod';
  else if (curated) source = 'canonical_role_only';
  else source = 'speculative_estimate';
  __sourceCounts[source] += 1;
  __sourceById[String(fa.player_id)] = source;
}}
if (Object.values(__sourceCounts).reduce((a,b)=>a+b,0) !== FREE_AGENTS.length) {{
  throw new Error('production-source classification count does not match rendered free-agent count');
}}
process.stdout.write(JSON.stringify({{
  rows: FREE_AGENTS,
  status: document.getElementById('syncStatus').textContent,
  fa_prod_entry_count: Object.values(FA_PROD_MULT_DATA).reduce((n,v)=>n+(Array.isArray(v)?v.length:1),0),
  canonical_prod_count: Object.keys(PROD_MULT_DATA).length,
  canonical_player_db_count: Object.keys(PLAYER_DB).length,
  production_source_counts: __sourceCounts,
  production_source_by_id: __sourceById
}}));
}})().catch(e=>{{console.error(e.stack||e); process.exit(1);}});
"""
    return _run_node(js)


def _fa_source_precedence_synthetic(board_text: str) -> dict:
    """Exercise curated-metadata + FA-production precedence on a fake player."""
    m = re.search(r"<script>(.*?)</script>", board_text, re.S | re.I)
    if not m:
        raise AssertionError("free-agent-board.html has no inline script")
    script = m.group(1)
    call = "loadFreeAgents();"
    idx = script.rfind(call)
    if idx < 0:
        raise AssertionError("free-agent board no longer calls loadFreeAgents()")
    script = script[:idx] + script[idx + len(call) :]
    doc = {
        "synced_at": 1,
        "free_agents": [{
            "player_id": "999999",
            "name": "Parity FA Prod",
            "pos": "WR",
            "team": "TST",
            "age": 23,
            "injury_status": None,
        }],
    }
    js = f"""
(async()=>{{
const __data = {json.dumps(doc)};
const __els = new Map();
globalThis.document = {{
  getElementById(id) {{
    if (!__els.has(id)) __els.set(id, {{className:'', textContent:'', innerHTML:''}});
    return __els.get(id);
  }}
}};
globalThis.fetch = async () => ({{ok:true, status:200, json:async()=>__data}});
{script}
const __key = normalizeName('Parity FA Prod');
PLAYER_DB[__key] = {{pos:'WR', age:23, role:'Depth'}};
delete PROD_MULT[__key];
FA_PROD_MULT_DATA[__key] = {{pos:'WR', prod:0.30, role:'Depth'}};
await loadFreeAgents();
process.stdout.write(JSON.stringify(FREE_AGENTS[0]));
}})().catch(e=>{{console.error(e.stack||e); process.exit(1);}});
"""
    return _run_node(js)


def _python_synthetic_expected(cfg, cases):
    out = {}
    for label, pos, age, role, prod, no_history in cases:
        key = "__parity_" + label
        prod_map = dict(cfg["prod_mult"])
        nh = set(cfg["no_real_history"])
        if prod is not None:
            prod_map[key] = float(prod)
        if no_history:
            nh.add(key)
        rm, raw = snapshot_values.production_multiplier(key, role, prod_map, nh, cfg["role_mult"])
        am = snapshot_values.age_multiplier(pos, age, role, rm, raw, cfg)
        pw = cfg["position_weight"].get(pos, 1.0)
        value = math.floor(100 * pw * am * rm * 55 + 0.5)
        out[label] = {"value": value, "prod_mult": rm, "age_mult": am}
    return out


def validate() -> dict:
    index_text = INDEX.read_text(encoding="utf-8")
    board_text = BOARD.read_text(encoding="utf-8")

    # 1) Exact generated-source parity and idempotent would-be sync.
    parity = sync_free_agent_valuation.parity_regions(index_text, board_text)
    assert all(parity.values()), f"canonical source regions differ: {parity}"
    assert sync_free_agent_valuation.render_synced(index_text, board_text) == board_text, (
        "free-agent-board.html would change if canonical sync ran; run "
        "python3 scripts/sync_free_agent_valuation.py --write"
    )

    # 2) Every canonical PLAYER_DB valuation must match the canonical Python port.
    cfg = snapshot_values.load_from_html(INDEX)
    expected = snapshot_values.compute_all_values(cfg)
    board_values = _board_canonical_values(board_text)
    assert set(board_values) == set(expected), "canonical board/index PLAYER_DB key sets differ"
    diffs = []
    for key, exp in expected.items():
        got = board_values[key]
        if got["value"] != exp["value"]:
            diffs.append((key, "value", exp["value"], got["value"]))
        if abs(float(got["prod_mult"]) - float(exp["prod_mult"])) > 1e-6:
            diffs.append((key, "prod_mult", exp["prod_mult"], got["prod_mult"]))
        if abs(float(got["age_mult"]) - float(exp["age_mult"])) > 1e-6:
            diffs.append((key, "age_mult", exp["age_mult"], got["age_mult"]))
    assert not diffs, f"free-agent canonical runtime valuation drift: {diffs[:10]}"

    # 3) Explicit boundary/mechanism tests so a future shared bug cannot hide
    # behind a population that happens not to exercise one branch.
    cases, js_synth = _synthetic_js_values(board_text)
    py_synth = _python_synthetic_expected(cfg, cases)
    synth_diffs = []
    for label in py_synth:
        for field in ("value", "prod_mult", "age_mult"):
            a, b = py_synth[label][field], js_synth[label][field]
            tol = 0 if field == "value" else 1e-9
            if abs(float(a) - float(b)) > tol:
                synth_diffs.append((label, field, a, b))
    assert not synth_diffs, f"synthetic valuation parity failures: {synth_diffs}"

    # A separate board-specific synthetic covers source precedence that the
    # canonical playerValue() cases cannot: curated metadata must not suppress
    # verified FA_PROD_MULT_DATA when canonical PROD_MULT is absent.
    fa_precedence = _fa_source_precedence_synthetic(board_text)
    precedence_case = [("fa_precedence", "WR", 23, "Depth", 0.30, False)]
    precedence_expected = _python_synthetic_expected(cfg, precedence_case)["fa_precedence"]
    assert fa_precedence["hasRealData"] is True
    assert fa_precedence["role"] == "Depth"
    assert fa_precedence["val"] == precedence_expected["value"], (
        "curated metadata suppressed FA-specific production in synthetic precedence case",
        fa_precedence, precedence_expected,
    )

    # 4) Execute the complete board against committed free-agent data.
    free_doc = json.load(open(FREE_AGENTS, encoding="utf-8"))
    runtime = _board_runtime_rows(board_text, free_doc)
    rows = runtime["rows"]

    expected_raw = [
        r for r in free_doc.get("free_agents", [])
        if (normalize_name(r.get("name")), r.get("pos")) not in EXCLUDED_FREE_AGENTS
    ]
    # Avoid relying on unique names: the real source contains duplicate-name
    # test/collision rows. Counter preserves multiplicity.
    expected_counter = Counter((r.get("name"), r.get("pos"), r.get("team")) for r in expected_raw if r.get("pos"))
    actual_counter = Counter((r.get("name"), r.get("pos"), r.get("team")) for r in rows)
    assert actual_counter == expected_counter, (
        f"board population differs from free_agents.json after explicit exclusions: "
        f"expected {sum(expected_counter.values())}, got {sum(actual_counter.values())}"
    )

    for row in rows:
        assert row["pos"] in VALID_POSITIONS, f"invalid free-agent position: {row}"
        assert row["role"] in VALID_ROLES, f"invalid free-agent role: {row}"
        assert isinstance(row["age"], (int, float)) and 18 <= row["age"] <= 45, f"invalid free-agent age: {row}"
        assert isinstance(row["val"], int) and 0 < row["val"] < 20000, f"invalid free-agent value: {row}"
        assert isinstance(row["hasRealData"], bool), f"invalid hasRealData flag: {row}"

    # Real-data badges must describe the production source that actually feeds
    # playerValue(). This specifically guards against a subtle old bug where a
    # PLAYER_DB metadata match could suppress FA_PROD_MULT_DATA even while the
    # row was labeled as having real production.
    source_by_id = runtime["production_source_by_id"]
    runtime_by_source_tuple = {}
    for row in rows:
        runtime_by_source_tuple.setdefault((row["name"], row["pos"], row["team"]), []).append(row)
    real_source_count = 0
    for src in expected_raw:
        pid = str(src["player_id"])
        source = source_by_id[pid]
        candidates = runtime_by_source_tuple[(src["name"], src["pos"], src["team"])]
        row = candidates.pop(0)
        should_have_real_data = source in {"canonical_prod", "fa_specific_prod"}
        assert row["hasRealData"] == should_have_real_data, (
            f"free-agent real-data badge/source mismatch for {pid} {src['name']}: "
            f"source={source}, hasRealData={row['hasRealData']}"
        )
        real_source_count += int(should_have_real_data)
    assert real_source_count == sum(1 for r in rows if r["hasRealData"]), (
        "rendered real-data count does not match actual production-source count"
    )

    # 5) Known same-name collisions / exclusions that previously caused real bugs.
    raw_justin = next((r for r in free_doc["free_agents"] if r["name"].lower() == "justin jefferson" and r.get("pos") == "LB"), None)
    if raw_justin:
        jj = next((r for r in rows if r["name"].lower() == "justin jefferson" and r.get("pos") == "LB"), None)
        assert jj is not None
        assert jj["age"] == (raw_justin.get("age") or 24), "LB Justin Jefferson inherited WR age"
        assert jj["role"] == "Speculative", "LB Justin Jefferson inherited WR role"
    assert not any(r["name"].lower() == "devonta smith" and r.get("pos") == "DB" for r in rows), (
        "explicitly excluded DB Devonta Smith returned to board"
    )
    assert not any(r["name"].lower() == "byron young" and r.get("pos") == "DL" for r in rows), (
        "explicitly excluded DL Byron Young returned to board"
    )

    # 6) Source-level roster/free-agent disjointness, repeated here because the
    # board must never rank a player who is already on a league roster.
    roster_doc = json.load(open(LEAGUE_ROSTERS, encoding="utf-8"))
    rostered = set()
    for roster in roster_doc.get("rosters", []):
        for slot in ("starters", "bench", "taxi", "reserve_ir"):
            for player in roster.get(slot) or []:
                rostered.add(str(player["player_id"]))
    free_ids = [str(r["player_id"]) for r in free_doc.get("free_agents", [])]
    overlap = sorted(set(free_ids) & rostered)
    assert not overlap, f"rostered Sleeper IDs leaked into free-agent source: {overlap[:10]}"
    assert len(free_ids) == len(set(free_ids)), "duplicate Sleeper IDs in free_agents.json"

    result = {
        "status": "PASS",
        "canonical_player_values_checked": len(expected),
        "synthetic_cases_checked": len(cases),
        "fa_source_precedence_cases_checked": 1,
        "free_agents_rendered": len(rows),
        "free_agents_with_real_data": sum(1 for r in rows if r["hasRealData"]),
        "fa_prod_entry_count": runtime["fa_prod_entry_count"],
        "canonical_prod_mult_count": runtime["canonical_prod_count"],
        "canonical_player_db_count": runtime["canonical_player_db_count"],
        "production_source_counts": runtime["production_source_counts"],
        "roster_overlap": len(overlap),
        "source_region_parity": parity,
    }
    return result


def main() -> None:
    result = validate()
    print(
        "PASS free-agent valuation parity: "
        f"{result['canonical_player_values_checked']} canonical player values, "
        f"{result['synthetic_cases_checked']} synthetic branch cases, "
        f"{result['free_agents_rendered']} free agents rendered, "
        f"{result['roster_overlap']} roster overlap"
    )
    print(
        "Free-agent production coverage: "
        f"{result['free_agents_with_real_data']} current rows with real data; "
        f"{result['fa_prod_entry_count']} FA-specific production entries"
    )


if __name__ == "__main__":
    main()
