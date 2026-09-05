#!/usr/bin/env python3
"""Replacement Level / Positional Scale V2 — Phase 1 baseline audit.

Research only. This phase inventories the exact replacement-rank / production
transform constants used by the frozen Production V2 Phase-1 transport layer,
reads the live POSITION_WEIGHT values from index.html through the canonical
snapshot parser, and compares the legacy replacement ranks with previously
measured roster/start-rate economics.

No production value, frozen prospective experiment, index.html constant, or
Production V2 candidate is changed.

Outputs:
  research/replacement-level-v2/replacement_level_v2_phase1_audit.json
  research/replacement-level-v2/replacement_level_v2_phase1_audit.md
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
VALIDATION_DIR = REPO_ROOT / "scripts" / "validation"

INDEX_HTML = REPO_ROOT / "index.html"
PRODUCTION_PHASE1 = REPO_ROOT / "research" / "production-v2" / "production_v2_phase1_audit.py"
ROSTER_ROBUSTNESS = REPO_ROOT / "research" / "roster-economics" / "roster_economics_robustness.json"
START_RATE_REPORT = REPO_ROOT / "research" / "roster-economics" / "start_rate_curve_report.md"

OUTPUT_JSON = REPO_ROOT / "research" / "replacement-level-v2" / "replacement_level_v2_phase1_audit.json"
OUTPUT_MD = REPO_ROOT / "research" / "replacement-level-v2" / "replacement_level_v2_phase1_audit.md"

METHOD_VERSION = "replacement-level-v2-phase1-baseline-audit-v1"
TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def literal_assignments(path: Path, names: set[str]) -> dict[str, Any]:
    """Read static literal assignments from a Python source without importing it."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: dict[str, Any] = {}
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value_node = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value_node = node.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id in names and value_node is not None:
                try:
                    found[target.id] = ast.literal_eval(value_node)
                except (ValueError, TypeError):
                    pass
    missing = sorted(names - set(found))
    if missing:
        raise RuntimeError(f"Could not parse required constants from {path.name}: {missing}")
    return found


def load_live_position_weights() -> dict[str, float]:
    if str(VALIDATION_DIR) not in sys.path:
        sys.path.insert(0, str(VALIDATION_DIR))
    import snapshot_values  # type: ignore

    cfg = snapshot_values.load_from_html(INDEX_HTML)
    weights = cfg.get("position_weight") or {}
    out = {p: float(weights[p]) for p in TRACKED_POSITIONS if p in weights}
    if set(out) != set(TRACKED_POSITIONS):
        raise RuntimeError(
            f"Live POSITION_WEIGHT missing tracked positions: {sorted(set(TRACKED_POSITIONS)-set(out))}"
        )
    return out


def as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    return max(1, int(round(x)))


def build_candidate_grid(pos: str, row: dict[str, Any], current_rank: int) -> dict[str, Any]:
    coverage = row.get("coverage_ranks") or {}
    boot = row.get("bootstrap_50pct_crossing") or {}

    signals: dict[str, int | None] = {
        "legacy_current": current_rank,
        "documented_baseline": as_int(row.get("documented_baseline")),
        "empirical_baseline": as_int(row.get("empirical_baseline")),
        "effective_demand": as_int(row.get("effective_demand")),
        "coverage_80": as_int(coverage.get("80")),
        "coverage_90": as_int(coverage.get("90")),
        "coverage_95": as_int(coverage.get("95")),
        "bootstrap_50_median": as_int(boot.get("median")),
        "bootstrap_50_p10": as_int(boot.get("p10")),
        "bootstrap_50_p90": as_int(boot.get("p90")),
    }

    valid = [v for v in signals.values() if isinstance(v, int)]
    if not valid:
        raise RuntimeError(f"No roster-economics candidate signals for {pos}")

    lo = max(1, min(valid))
    hi = max(valid)
    # Add a small symmetric neighborhood around the legacy rank so Phase 2 can
    # distinguish broad structural movement from a local optimum. These are
    # candidates only; Phase 1 makes no calibration claim.
    neighborhood = [max(1, current_rank - 4), max(1, current_rank - 2), current_rank, current_rank + 2, current_rank + 4]
    grid = sorted(set(valid + neighborhood))

    return {
        "signals": signals,
        "evidence_range": {"min": lo, "max": hi},
        "candidate_ranks": grid,
        "candidate_count": len(grid),
    }


def build_payload() -> dict[str, Any]:
    constants = literal_assignments(
        PRODUCTION_PHASE1,
        {
            "REPLACEMENT_RANK",
            "PM_INTERCEPT",
            "PM_RATIO_SLOPE",
            "PM_MIN",
            "PM_MAX",
            "GLOBAL_VALUE_SCALE",
        },
    )
    replacement = {str(k): int(v) for k, v in constants["REPLACEMENT_RANK"].items()}
    if set(replacement) != set(TRACKED_POSITIONS):
        raise RuntimeError("Production V2 replacement rank map changed unexpectedly")

    roster = read_json(ROSTER_ROBUSTNESS)
    positions = roster.get("positions")
    if not isinstance(positions, dict):
        raise RuntimeError("Roster-economics robustness JSON missing positions object")

    live_weights = load_live_position_weights()
    audits: dict[str, Any] = {}
    for pos in TRACKED_POSITIONS:
        row = positions.get(pos)
        if not isinstance(row, dict):
            raise RuntimeError(f"Roster-economics robustness missing {pos}")
        audits[pos] = {
            "legacy_replacement_rank": replacement[pos],
            "live_position_weight": live_weights[pos],
            "effective_demand": row.get("effective_demand"),
            "coverage_ranks": row.get("coverage_ranks"),
            "bootstrap_50pct_crossing": row.get("bootstrap_50pct_crossing"),
            "documented_baseline": row.get("documented_baseline"),
            "empirical_baseline": row.get("empirical_baseline"),
            "bin_width_50pct_stable": (row.get("bin_width_sensitivity") or {}).get("stable"),
            "phase2_grid": build_candidate_grid(pos, row, replacement[pos]),
        }

    transform = {
        "pm_intercept": float(constants["PM_INTERCEPT"]),
        "pm_ratio_slope": float(constants["PM_RATIO_SLOPE"]),
        "pm_min": float(constants["PM_MIN"]),
        "pm_max": float(constants["PM_MAX"]),
        "global_value_scale": float(constants["GLOBAL_VALUE_SCALE"]),
    }

    payload = {
        "method_version": METHOD_VERSION,
        "status": "RESEARCH_ONLY_BASELINE_AUDIT",
        "deployment_authorized": False,
        "production_v2_change_authorized": False,
        "position_weight_change_authorized": False,
        "replacement_rank_change_authorized": False,
        "scale_change_authorized": False,
        "scope": {
            "tracked_positions": list(TRACKED_POSITIONS),
            "phase1_goal": "inventory current research transport constants and build evidence-grounded replacement-rank candidate grids",
            "phase2_strategy": "one-position-at-a-time historical evaluation; no seven-position Cartesian grid",
            "frozen_experiment_policy": "do not modify any existing frozen prospective experiment",
        },
        "sources": {
            "production_v2_phase1": str(PRODUCTION_PHASE1.relative_to(REPO_ROOT)),
            "production_v2_phase1_sha256": sha256(PRODUCTION_PHASE1),
            "roster_economics_robustness": str(ROSTER_ROBUSTNESS.relative_to(REPO_ROOT)),
            "roster_economics_robustness_sha256": sha256(ROSTER_ROBUSTNESS),
            "start_rate_report": str(START_RATE_REPORT.relative_to(REPO_ROOT)),
            "start_rate_report_sha256": sha256(START_RATE_REPORT),
            "index_html": str(INDEX_HTML.relative_to(REPO_ROOT)),
            "index_html_sha256": sha256(INDEX_HTML),
        },
        "legacy_transport": {
            "replacement_ranks": replacement,
            "production_multiplier_transform": transform,
            "note": "These are Production V2 research/transport constants, not a dynamic replacement-rank lookup in the live calculator.",
        },
        "live_position_weights": live_weights,
        "positions": audits,
    }
    return payload


def render_md(payload: dict[str, Any]) -> str:
    t = payload["legacy_transport"]["production_multiplier_transform"]
    lines = [
        "# Replacement Level / Positional Scale V2 — Phase 1 Baseline Audit",
        "",
        "**Research only. No deployment or frozen prospective experiment is changed.**",
        "",
        f"Method: `{payload['method_version']}`",
        "",
        "## Important architecture note",
        "",
        "The live calculator consumes precomputed `PROD_MULT_DATA`; it does not dynamically look up these replacement ranks on every valuation. The ranks below are the legacy Production V2 research/transport anchors being audited for future calibration.",
        "",
        "## Current transport constants",
        "",
        f"- PM transform: `clamp({t['pm_intercept']:+.2f} + {t['pm_ratio_slope']:.2f} × production_ratio, {t['pm_min']:.2f}, {t['pm_max']:.2f})`",
        f"- Global value scale carried by the Production V2 transport: **{t['global_value_scale']:.1f}**",
        "",
        "## Replacement-level evidence inventory",
        "",
        "| Pos | Legacy rank | Live pos wt | Eff demand | 80% starts | 90% | 95% | Boot 50% median | Boot p10-p90 | Empirical baseline | Phase-2 candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for pos in TRACKED_POSITIONS:
        row = payload["positions"][pos]
        cov = row.get("coverage_ranks") or {}
        boot = row.get("bootstrap_50pct_crossing") or {}
        grid = row["phase2_grid"]["candidate_ranks"]
        lines.append(
            f"| {pos} | {row['legacy_replacement_rank']} | {row['live_position_weight']:.2f} | "
            f"{float(row['effective_demand']):.2f} | {cov.get('80')} | {cov.get('90')} | {cov.get('95')} | "
            f"{boot.get('median')} | {boot.get('p10')}-{boot.get('p90')} | {row.get('empirical_baseline')} | "
            f"{', '.join(str(x) for x in grid)} |"
        )

    lines += [
        "",
        "## Phase 1 decision",
        "",
        "- The legacy ranks remain the **control**, not presumed truth.",
        "- Candidate grids are evidence-grounded from actual historical lineup demand plus a narrow local neighborhood around each legacy rank.",
        "- Phase 2 should test **one position at a time** while holding every other position, Production V2 transport input, age curve, opportunity, durability, no-history logic, and position weight fixed.",
        "- Do **not** jointly optimize replacement rank and position weight yet; that would make attribution impossible.",
        "- Do **not** change the PM transform or global scale in Phase 2. Those become a later scale-calibration phase only after replacement ranks are narrowed.",
        "",
        "## Guardrails",
        "",
        "- deployment_authorized: **false**",
        "- replacement_rank_change_authorized: **false**",
        "- position_weight_change_authorized: **false**",
        "- scale_change_authorized: **false**",
        "- frozen prospective experiments: **untouched**",
        "",
    ]
    return "\n".join(lines)


def selftest() -> None:
    sample = {
        "effective_demand": 27.4,
        "coverage_ranks": {"80": 26, "90": 33, "95": 39},
        "bootstrap_50pct_crossing": {"median": 25, "p10": 24, "p90": 28},
        "documented_baseline": 32,
        "empirical_baseline": 37,
    }
    grid = build_candidate_grid("RB", sample, 32)
    assert 32 in grid["candidate_ranks"]
    assert 25 in grid["candidate_ranks"]
    assert 39 in grid["candidate_ranks"]
    assert grid["evidence_range"] == {"min": 24, "max": 39}
    print("Replacement Level V2 Phase-1 self-test passed.")


def check_payload(payload: dict[str, Any]) -> None:
    if payload.get("method_version") != METHOD_VERSION:
        raise RuntimeError("Unexpected method_version")
    for key in (
        "deployment_authorized",
        "production_v2_change_authorized",
        "position_weight_change_authorized",
        "replacement_rank_change_authorized",
        "scale_change_authorized",
    ):
        if payload.get(key) is not False:
            raise RuntimeError(f"Research guardrail failed: {key}")
    positions = payload.get("positions") or {}
    if set(positions) != set(TRACKED_POSITIONS):
        raise RuntimeError("Position audit coverage mismatch")
    for pos, row in positions.items():
        grid = row["phase2_grid"]["candidate_ranks"]
        if row["legacy_replacement_rank"] not in grid:
            raise RuntimeError(f"{pos} candidate grid lost control rank")
        if len(grid) < 3:
            raise RuntimeError(f"{pos} candidate grid too small")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        selftest()
        return

    payload = build_payload()
    check_payload(payload)

    if args.write:
        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        OUTPUT_MD.write_text(render_md(payload), encoding="utf-8")
        print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
        print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")

    if args.check:
        if not OUTPUT_JSON.exists() or not OUTPUT_MD.exists():
            raise RuntimeError("Phase-1 outputs missing; run --write first")
        committed = read_json(OUTPUT_JSON)
        check_payload(committed)
        if committed != payload:
            raise RuntimeError("Committed Phase-1 JSON is stale versus canonical inputs")
        expected_md = render_md(committed)
        if OUTPUT_MD.read_text(encoding="utf-8") != expected_md:
            raise RuntimeError("Committed Phase-1 Markdown is stale")
        print("Replacement Level V2 Phase-1 check passed.")

    if not (args.write or args.check):
        print(render_md(payload))


if __name__ == "__main__":
    main()
