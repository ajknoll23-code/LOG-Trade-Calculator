#!/usr/bin/env python3
"""Validate deployed Free Agent Utility V1 board integration."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
BOARD = ROOT / "free-agent-board.html"
FREE_AGENTS = ROOT / "data" / "free_agents.json"
UTILITY = ROOT / "data" / "free_agent_utility_v1.json"
BASE_VALIDATOR = ROOT / "scripts" / "validation" / "validate_free_agent_valuation_parity.py"
BUILDER = ROOT / "scripts" / "projections" / "build_free_agent_utility_v1.py"

POSITIONS = ("ALL", "QB", "RB", "WR", "TE", "DL", "LB", "DB")


def load_module(path: Path, name: str):
    directory = str(path.parent)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to import {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def run_node(js: str):
    p = subprocess.run(["node", "-e", js], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"node failed: {p.stderr[:3000]}")
    return json.loads(p.stdout)


def board_runtime(board_text: str, free_doc: dict, utility_doc: dict):
    m = re.search(r"<script>(.*?)</script>", board_text, re.S | re.I)
    if not m:
        raise RuntimeError("free-agent-board.html has no inline script")
    script = m.group(1)
    call = "loadFreeAgents();"
    idx = script.rfind(call)
    if idx < 0:
        raise RuntimeError("board no longer calls loadFreeAgents()")
    script = script[:idx] + script[idx + len(call):]

    js = f"""
(async()=>{{
const __free = {json.dumps(free_doc)};
const __util = {json.dumps(utility_doc)};
const __els = new Map();
globalThis.document = {{
  getElementById(id) {{
    if (!__els.has(id)) __els.set(id, {{className:'', textContent:'', innerHTML:''}});
    return __els.get(id);
  }}
}};
globalThis.fetch = async (url) => {{
  const u = String(url || '');
  const data = u.includes('free_agent_utility_v1.json') ? __util : __free;
  return {{ok:true, status:200, json:async()=>data}};
}};
{script}
await loadFreeAgents();
process.stdout.write(JSON.stringify({{
  utilityActive: FREE_AGENT_UTILITY_ACTIVE,
  rows: FREE_AGENTS.map(r => ({{
    playerId:r.playerId,
    name:r.name,
    pos:r.pos,
    val:r.val,
    hasRealData:r.hasRealData,
    utilityRank:r.utilityRank
  }})),
  html: document.getElementById('boardWrap').innerHTML
}}));
}})().catch(e=>{{console.error(e.stack||e);process.exit(1);}});
"""
    return run_node(js)


def section_ids(html: str) -> dict[str, list[str]]:
    out = {}
    parts = html.split("<details")
    for part in parts[1:]:
        m = re.search(r"<summary>(ALL|QB|RB|WR|TE|DL|LB|DB)\s", part)
        if not m:
            continue
        pos = m.group(1)
        ids = re.findall(r'data-player-id="([^"]+)"', part)
        out[pos] = ids
    return out


def validate():
    builder = load_module(BUILDER, "fa_utility_v1_builder_validator")
    base = load_module(BASE_VALIDATOR, "fa_utility_v1_base_validator")

    board = BOARD.read_text(encoding="utf-8")
    free_doc = json.loads(FREE_AGENTS.read_text(encoding="utf-8"))
    utility = json.loads(UTILITY.read_text(encoding="utf-8"))

    builder.validate_artifact(utility, free_doc)
    if builder.BOARD_MARKER not in board:
        raise RuntimeError("board integration marker missing")

    base.validate()

    active = board_runtime(board, free_doc, utility)
    if active["utilityActive"] is not True:
        raise RuntimeError("fresh production utility artifact did not activate")

    artifact_by_id = {str(r["player_id"]): r for r in utility["players"]}
    data_rows = [r for r in active["rows"] if r["hasRealData"]]
    if len(data_rows) != len(utility["players"]):
        raise RuntimeError(
            f"board data-backed count != utility rows: {len(data_rows)} != {len(utility['players'])}"
        )

    for r in active["rows"]:
        sid = str(r["playerId"])
        if r["hasRealData"]:
            a = artifact_by_id.get(sid)
            if a is None:
                raise RuntimeError(f"data-backed board row missing utility entry: {sid}")
            if r["pos"] != a["pos"] or r["utilityRank"] != a["priority_rank"]:
                raise RuntimeError(f"board utility rank mismatch for {sid}")
        elif r["utilityRank"] is not None:
            raise RuntimeError(f"speculative player unexpectedly received utility rank: {sid}")

    sections = section_ids(active["html"])
    if set(sections) != set(POSITIONS):
        raise RuntimeError(f"rendered sections changed: {sorted(sections)}")

    expected_all = [
        str(r["playerId"])
        for r in sorted(data_rows, key=lambda r: -int(r["val"]))
    ]
    if sections["ALL"] != expected_all:
        raise RuntimeError("ALL section no longer preserves existing LOG value order")

    for pos in POSITIONS[1:]:
        expected = [
            str(r["player_id"])
            for r in sorted(
                [x for x in utility["players"] if x["pos"] == pos],
                key=lambda x: x["priority_rank"],
            )
        ]
        if sections[pos] != expected:
            raise RuntimeError(f"{pos} section does not follow derived priority rank")

    stale = json.loads(json.dumps(utility))
    stale["source"]["free_agents_synced_at"] = -1
    inactive = board_runtime(board, free_doc, stale)
    if inactive["utilityActive"] is not False:
        raise RuntimeError("stale utility artifact did not fail closed")

    stale_rows = [r for r in inactive["rows"] if r["hasRealData"]]
    stale_sections = section_ids(inactive["html"])
    for pos in POSITIONS[1:]:
        expected = [
            str(r["playerId"])
            for r in sorted(
                [x for x in stale_rows if x["pos"] == pos],
                key=lambda x: -int(x["val"]),
            )
        ]
        if stale_sections[pos] != expected:
            raise RuntimeError(f"{pos}: stale utility fallback is not exact LOG order")

    return {
        "status": "PASS_FREE_AGENT_UTILITY_V1_PRODUCTION",
        "utility_rows": len(utility["players"]),
        "board_data_backed_rows": len(data_rows),
        "fresh_artifact_active": True,
        "stale_artifact_falls_back_to_log": True,
        "all_section_log_order_preserved": True,
        "position_sections_utility_order_verified": True,
        "base_free_agent_parity_passed": True,
    }


def run_selftest():
    html = (
        '<details open><summary>ALL <span>(2)</span></summary>'
        '<div data-player-id="2"></div><div data-player-id="1"></div></details>'
        '<details><summary>WR <span>(1)</span></summary>'
        '<div data-player-id="1"></div></details>'
    )
    got = section_ids(html)
    assert got["ALL"] == ["2", "1"]
    assert got["WR"] == ["1"]
    print("validate_free_agent_utility_v1 self-test passed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        run_selftest()
        return 0
    print(json.dumps(validate(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
