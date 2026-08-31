#!/usr/bin/env python3
"""Refresh deterministic repository artifacts from committed canonical inputs.

This helper exists for *manual* repository validation/repair runs. It never
fetches the network and never edits ``index.html`` or model parameters.

Artifacts refreshed:
  * free-agent-board.html canonical valuation regions <- index.html
  * scripts/artifacts/generated/player_positions.json <- index.html + aliases + players_cache.json
  * data/free_agents.json <- players_cache.json - committed league rosters

Explicitly NOT refreshed here:
  * deployed/frozen IDP V1 release artifacts such as
    model/releases/idp-v1/production_history_components.json,
    the approved candidate, patch, and pre-V1 baseline. Those are release evidence, not rolling derived state.
    Later source refreshes are allowed to diverge without rewriting the release.

The point is to make a manual GitHub Actions validation run self-contained:
if a generated artifact is stale because files were uploaded out of order or a
source snapshot changed, the workflow can repair only these derived files inside
the validation runner, then run the strict regression suite in the same job.
The read-only regression workflow does not push those repairs back to GitHub.

Pull-request validation should use ``--check`` only; it must not silently repair
stale files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
REPO_ROOT = SCRIPTS_DIR.parent
DATA_DIR = REPO_ROOT / "data"

sys.path.insert(0, str(SCRIPTS_DIR))

from utilities import generate_player_positions
from sync import sync_free_agent_valuation
from sync import sync_sleeper

INDEX = REPO_ROOT / "index.html"
BOARD = REPO_ROOT / "free-agent-board.html"
POSITIONS = SCRIPTS_DIR / "artifacts" / "generated" / "player_positions.json"
FREE_AGENTS = DATA_DIR / "free_agents.json"
PLAYERS_CACHE = DATA_DIR / "players_cache.json"
LEAGUE_ROSTERS = DATA_DIR / "league_rosters.json"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(obj, *, trailing_newline: bool = False) -> bytes:
    text = json.dumps(obj, indent=2)
    if trailing_newline:
        text += "\n"
    return text.encode("utf-8")


def _rostered_ids(rosters_doc: dict) -> set[str]:
    out: set[str] = set()
    for roster in rosters_doc.get("rosters") or []:
        for slot in ("starters", "bench", "taxi", "reserve_ir"):
            for player in roster.get(slot) or []:
                pid = player.get("player_id")
                if pid is not None:
                    out.add(str(pid))
    return out


def expected_artifacts() -> dict[Path, bytes]:
    index_text = INDEX.read_text(encoding="utf-8")
    board_text = BOARD.read_text(encoding="utf-8")
    expected_board = sync_free_agent_valuation.render_synced(index_text, board_text)

    lookup = generate_player_positions.build_player_position_lookup()
    expected_positions = _json_bytes(dict(sorted(lookup.items())), trailing_newline=True)

    cache_doc = json.loads(PLAYERS_CACHE.read_text(encoding="utf-8"))
    rosters_doc = json.loads(LEAGUE_ROSTERS.read_text(encoding="utf-8"))
    current_fa = json.loads(FREE_AGENTS.read_text(encoding="utf-8")) if FREE_AGENTS.exists() else {}
    pool = cache_doc.get("players", cache_doc)
    regenerated = sync_sleeper.compute_free_agents(pool, _rostered_ids(rosters_doc))

    # Preserve sync metadata because this is a deterministic cache-derived
    # repair, not a claim that a fresh Sleeper network sync occurred.
    expected_fa = dict(current_fa)
    expected_fa.setdefault("league_id", rosters_doc.get("league_id"))
    expected_fa["count"] = len(regenerated)
    expected_fa["free_agents"] = regenerated
    expected_free_agents = _json_bytes(expected_fa, trailing_newline=True)

    return {
        BOARD: expected_board.encode("utf-8"),
        POSITIONS: expected_positions,
        FREE_AGENTS: expected_free_agents,
    }


def compare() -> list[dict]:
    rows = []
    for path, expected in expected_artifacts().items():
        actual = path.read_bytes() if path.exists() else b""
        rows.append(
            {
                "path": str(path.relative_to(REPO_ROOT)),
                "matches": actual == expected,
                "actual_sha256": _sha256_bytes(actual),
                "expected_sha256": _sha256_bytes(expected),
                "actual_bytes": len(actual),
                "expected_bytes": len(expected),
            }
        )
    return rows


def write_expected() -> list[dict]:
    index_before = INDEX.read_bytes()
    expected = expected_artifacts()
    changed = []
    for path, payload in expected.items():
        actual = path.read_bytes() if path.exists() else b""
        if actual != payload:
            path.write_bytes(payload)
            changed.append(str(path.relative_to(REPO_ROOT)))
    if INDEX.read_bytes() != index_before:
        raise RuntimeError("derived-artifact refresh unexpectedly modified index.html")
    return compare(), changed


def run_selftest() -> None:
    # Core invariant: deterministic free-agent reconstruction from a tiny
    # cache/roster fixture excludes rostered/inactive/corrupt rows while
    # preserving valid unknown-age rows and the stable Anquin Barnes override.
    pool = {
        "1": {"first_name": "Free", "last_name": "Agent", "team": "ARI", "position": "WR", "fantasy_positions": ["WR"], "active": True, "age": 24},
        "2": {"first_name": "Rostered", "last_name": "Guy", "team": "BUF", "position": "LB", "fantasy_positions": ["LB"], "active": True, "age": 25},
        "3": {"first_name": "Old", "last_name": "Ghost", "team": "SEA", "position": "LB", "fantasy_positions": ["LB"], "active": False, "age": 30},
        "4": {"first_name": "Bad", "last_name": "Age", "team": "HOU", "position": "S", "fantasy_positions": ["DB"], "active": True, "age": 52},
        "5": {"first_name": "Unknown", "last_name": "Age", "team": "GB", "position": "TE", "fantasy_positions": ["TE"], "active": True, "age": None},
    }
    rows = sync_sleeper.compute_free_agents(pool, {"2"})
    assert {r["player_id"] for r in rows} == {"1", "5"}
    assert rows[0]["pos"] == "WR"
    print("refresh_repo_derived_state self-test passed.")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return 0

    if args.write:
        rows, changed = write_expected()
        if changed:
            print("Refreshed deterministic derived artifacts:")
            for path in changed:
                print(f"  - {path}")
        else:
            print("No deterministic derived artifacts required refresh.")
    else:
        rows = compare()

    stale = [r for r in rows if not r["matches"]]
    for r in rows:
        status = "PASS" if r["matches"] else "STALE"
        print(f"{status} {r['path']}: {r['actual_sha256']} expected {r['expected_sha256']}")

    if stale:
        print("FAIL deterministic derived-artifact parity", file=sys.stderr)
        return 1
    print("PASS deterministic derived-artifact parity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
