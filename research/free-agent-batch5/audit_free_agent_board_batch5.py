#!/usr/bin/env python3
"""Reproduce the Batch 4 -> Batch 5 free-agent board impact report.

The immutable pre-Batch5 runtime snapshot freezes exactly what the deployed
Batch4 board rendered. This audit executes the current board against the
committed free-agent source, joins by stable Sleeper player_id, and reports
population/value/metadata movement without network access.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
PRE_PATH = SCRIPT_DIR / "free_agent_board_pre_batch5_snapshot.json"
OUT_JSON = SCRIPT_DIR / "free_agent_board_batch5_impact.json"
OUT_MD = SCRIPT_DIR / "free_agent_board_batch5_impact_report.md"
BOARD = REPO_ROOT / "free-agent-board.html"
FREE_AGENTS = REPO_ROOT / "data" / "free_agents.json"

sys.path.insert(0, str(SCRIPT_DIR))
import validate_free_agent_valuation_parity as parity


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _current_rows() -> tuple[dict[str, dict], dict]:
    board_text = BOARD.read_text(encoding="utf-8")
    free_doc = json.load(open(FREE_AGENTS, encoding="utf-8"))
    runtime = parity._board_runtime_rows(board_text, free_doc)
    source = [
        r for r in free_doc.get("free_agents", [])
        if (parity.normalize_name(r.get("name")), r.get("pos")) not in parity.EXCLUDED_FREE_AGENTS
    ]
    rows = runtime["rows"]
    assert len(source) == len(rows), (len(source), len(rows))
    by_id = {}
    for src, row in zip(source, rows):
        assert (src.get("name"), src.get("pos"), src.get("team")) == (
            row.get("name"), row.get("pos"), row.get("team")
        ), (src, row)
        pid = str(src["player_id"])
        by_id[pid] = {
            "player_id": pid,
            **row,
            "production_source": runtime["production_source_by_id"][pid],
        }
    return by_id, runtime


def _pct(old: int, new: int) -> float | None:
    return None if not old else (new / old - 1.0) * 100.0


def build_report() -> dict:
    pre = json.load(open(PRE_PATH, encoding="utf-8"))
    pre_by_id = {str(r["player_id"]): r for r in pre["rows"]}
    cur_by_id, runtime = _current_rows()

    pre_ids, cur_ids = set(pre_by_id), set(cur_by_id)
    removed_ids = sorted(pre_ids - cur_ids)
    added_ids = sorted(cur_ids - pre_ids)
    common_ids = sorted(pre_ids & cur_ids)

    changed = []
    unchanged = 0
    visible_fields = ("val", "age", "role", "pos", "team", "hasRealData")
    for pid in common_ids:
        old, new = pre_by_id[pid], cur_by_id[pid]
        fields = [f for f in visible_fields if old.get(f) != new.get(f)]
        if not fields:
            unchanged += 1
            continue
        changed.append({
            "player_id": pid,
            "name": new["name"],
            "pos": new["pos"],
            "team": new.get("team"),
            "old_value": old["val"],
            "new_value": new["val"],
            "value_change": new["val"] - old["val"],
            "pct_change": _pct(old["val"], new["val"]),
            "old_age": old.get("age"),
            "new_age": new.get("age"),
            "old_role": old.get("role"),
            "new_role": new.get("role"),
            "old_has_real_data": old.get("hasRealData"),
            "new_has_real_data": new.get("hasRealData"),
            "production_source": new.get("production_source"),
            "changed_fields": fields,
        })

    removed = [
        {
            "player_id": pid,
            "name": pre_by_id[pid]["name"],
            "pos": pre_by_id[pid]["pos"],
            "team": pre_by_id[pid].get("team"),
            "old_value": pre_by_id[pid]["val"],
            "old_age": pre_by_id[pid].get("age"),
            "old_role": pre_by_id[pid].get("role"),
        }
        for pid in removed_ids
    ]
    added = [cur_by_id[pid] for pid in added_ids]

    value_only = [r for r in changed if r["changed_fields"] == ["val"]]
    metadata_changed = [r for r in changed if any(f != "val" for f in r["changed_fields"])]
    pct_values = sorted(r["pct_change"] for r in changed if r["pct_change"] is not None)

    result = {
        "status": "PASS",
        "snapshot_type": "free_agent_board_batch5_impact",
        "pre_batch5": {
            "snapshot_file": str(PRE_PATH.relative_to(REPO_ROOT)),
            "board_sha256": pre["free_agent_board_sha256"],
            "free_agents_json_sha256": pre["free_agents_json_sha256"],
            "source_free_agent_count": pre["source_free_agent_count"],
            "rendered_free_agent_count": pre["rendered_free_agent_count"],
        },
        "batch5": {
            "board_sha256": _sha256(BOARD),
            "free_agents_json_sha256": _sha256(FREE_AGENTS),
            "source_free_agent_count": json.load(open(FREE_AGENTS, encoding="utf-8"))["count"],
            "rendered_free_agent_count": len(cur_by_id),
            "production_source_counts": runtime["production_source_counts"],
            "fa_prod_entry_count": runtime["fa_prod_entry_count"],
        },
        "population": {
            "common": len(common_ids),
            "removed": len(removed),
            "added": len(added),
            "changed_common_rows": len(changed),
            "unchanged_common_rows": unchanged,
            "value_only_changes": len(value_only),
            "rows_with_metadata_changes": len(metadata_changed),
        },
        "value_change_distribution_common_changed": {
            "median_pct": statistics.median(pct_values) if pct_values else None,
            "min_pct": min(pct_values) if pct_values else None,
            "max_pct": max(pct_values) if pct_values else None,
        },
        "removed_rows": removed,
        "added_rows": added,
        "top_risers": sorted(changed, key=lambda r: (r["pct_change"] if r["pct_change"] is not None else -1e9), reverse=True)[:20],
        "top_fallers": sorted(changed, key=lambda r: (r["pct_change"] if r["pct_change"] is not None else 1e9))[:20],
        "changed_rows": sorted(changed, key=lambda r: (r["name"].lower(), r["pos"], r["player_id"])),
        "open_workstream": {
            "name": "free-agent production lineage / V1 extension",
            "reason": (
                "385 currently displayed rows use the board-specific FA_PROD_MULT_DATA table. "
                "Core valuation-engine parity is enforced in Batch5, but the provenance/calibration "
                "of that separate production table is not silently redefined here."
            ),
        },
    }
    assert result["batch5"]["production_source_counts"]["fa_specific_prod"] == 385
    assert result["batch5"]["production_source_counts"]["canonical_prod"] == 13
    assert result["batch5"]["production_source_counts"]["canonical_role_only"] == 1
    assert result["batch5"]["production_source_counts"]["speculative_estimate"] == 1599
    return result


def _fmt_row(r: dict) -> str:
    pct = r.get("pct_change")
    pct_s = "n/a" if pct is None else f"{pct:+.1f}%"
    return f"| {r['name']} | {r['pos']} | {r.get('team') or '—'} | {r['old_value']} | {r['new_value']} | {pct_s} |"


def write_outputs(result: dict) -> None:
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    src = result["batch5"]["production_source_counts"]
    pop = result["population"]
    md = [
        "# Batch 5 — Free-Agent Board Impact Audit",
        "",
        "This report compares the immutable deployed Batch 4 free-agent-board runtime snapshot with the current Batch 5 candidate. No network data is used.",
        "",
        "## Population",
        "",
        f"- Batch 4 rendered: **{result['pre_batch5']['rendered_free_agent_count']}**",
        f"- Batch 5 rendered: **{result['batch5']['rendered_free_agent_count']}**",
        f"- Common stable Sleeper IDs: **{pop['common']}**",
        f"- Removed stale/corrupt rows: **{pop['removed']}**",
        f"- Added rows: **{pop['added']}**",
        f"- Common rows with any value/metadata change: **{pop['changed_common_rows']}**",
        f"- Common rows unchanged: **{pop['unchanged_common_rows']}**",
        "",
        "The 21 removals come from the Batch 5 Sleeper-data hygiene rules (explicitly inactive legacy/duplicate records plus an impossible-age ghost record). They are not model-driven cuts.",
        "",
        "## Current production-source coverage",
        "",
        f"- Speculative role estimate only: **{src['speculative_estimate']}**",
        f"- Board-specific `FA_PROD_MULT_DATA`: **{src['fa_specific_prod']}**",
        f"- Canonical main-calculator `PROD_MULT_DATA`: **{src['canonical_prod']}**",
        f"- Canonical PLAYER_DB metadata with no real production source: **{src['canonical_role_only']}**",
        "",
        "Batch 5 also fixes a real source-precedence bug: a PLAYER_DB metadata match can no longer suppress a verified FA-specific production number when that player has no canonical PROD_MULT entry.",
        "",
        "## Top value risers",
        "",
        "| Player | Pos | Team | Old | New | Change |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    md += [_fmt_row(r) for r in result["top_risers"]]
    md += [
        "",
        "## Top value fallers",
        "",
        "| Player | Pos | Team | Old | New | Change |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    md += [_fmt_row(r) for r in result["top_fallers"]]
    md += [
        "",
        "## Removed rows",
        "",
        "| Player | Pos | Team | Old value | Old age |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in result["removed_rows"]:
        md.append(f"| {r['name']} | {r['pos']} | {r.get('team') or '—'} | {r['old_value']} | {r.get('old_age')} |")
    md += [
        "",
        "## Scope boundary / open workstream",
        "",
        "**Free-agent valuation-engine parity is closed by Batch 5.** The board's position weights, age curves, role multipliers, canonical PROD_MULT table, PLAYER_DB, aliases, and valuation functions are now generated from `index.html` and CI-enforced.",
        "",
        "**Free-agent production lineage remains OPEN.** The 385 displayed rows sourced from `FA_PROD_MULT_DATA` use a separate off-roster production table. Batch 5 ensures those numbers are applied correctly; it does not claim that table has been rebuilt under the newly deployed IDP V1 methodology. That should be audited as its own workstream rather than silently bundled into a frontend parity fix.",
        "",
    ]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    result = build_report()
    write_outputs(result)
    print(
        "PASS Batch5 free-agent impact audit: "
        f"{result['pre_batch5']['rendered_free_agent_count']} -> {result['batch5']['rendered_free_agent_count']} rendered; "
        f"{result['population']['changed_common_rows']} common rows changed; "
        f"{result['population']['removed']} removed"
    )
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
