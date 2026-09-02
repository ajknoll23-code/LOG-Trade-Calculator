#!/usr/bin/env python3
"""Robustness audit for Team Utility's starter-selection objective.

Research-only. Does NOT change production.

Uses the corrected production-parity starter audit as the roster/value engine,
then compares Fundamental-Value starter selection with:
  1. Sleeper 2026 projected points
  2. FantasyPros API projections rescored under Trade Desk league scoring
  3. A 50/50 Sleeper/FantasyPros blend when both exist, with single-source
     fallback when only one provider is available

FantasyPros identity is resolved through the committed fpid -> Sleeper
crosswalk, not by ad-hoc name matching.

Outputs:
  research/team-utility/team_utility_projection_robustness_audit.json
  research/team-utility/team_utility_projection_robustness_audit.md
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_AUDIT_PATH = (
    REPO_ROOT
    / "research"
    / "team-utility"
    / "team_utility_starter_objective_audit.py"
)
FP_NORMALIZED = REPO_ROOT / "scripts" / "fantasypros_api_normalized_2026.json"
IDENTITY = REPO_ROOT / "scripts" / "identity_crosswalk.json"
OUT_DIR = REPO_ROOT / "research" / "team-utility"
OUT_JSON = OUT_DIR / "team_utility_projection_robustness_audit.json"
OUT_MD = OUT_DIR / "team_utility_projection_robustness_audit.md"


def load_base_module():
    spec = importlib.util.spec_from_file_location("team_utility_base_audit", BASE_AUDIT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not import base Team Utility audit")
    mod = importlib.util.module_from_spec(spec)
    # Python 3.13 dataclasses expects the class's defining module to already
    # exist in sys.modules while decorators execute.
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return mod


def load_fantasypros_by_sleeper_id() -> tuple[dict[str, float], dict]:
    normalized_doc = json.loads(FP_NORMALIZED.read_text(encoding="utf-8"))
    rows = normalized_doc.get("players", [])
    by_fpid = {
        str(row["fantasypros_id"]): row
        for row in rows
        if row.get("fantasypros_id") is not None
    }

    crosswalk = json.loads(IDENTITY.read_text(encoding="utf-8"))
    by_sleeper = {}
    stats = {
        "fantasypros_normalized_rows": len(rows),
        "identity_rows": len(crosswalk),
        "mapped_with_points": 0,
        "manual_review_skipped": 0,
        "missing_fpid_row": 0,
        "missing_points": 0,
    }

    for link in crosswalk:
        sleeper_id = link.get("sleeper_id")
        fpid = link.get("fantasypros_id")
        if sleeper_id is None or fpid is None:
            continue
        if link.get("requires_manual_review"):
            stats["manual_review_skipped"] += 1
            continue

        row = by_fpid.get(str(fpid))
        if row is None:
            stats["missing_fpid_row"] += 1
            continue

        points = row.get("trade_desk_normalized_points")
        if not isinstance(points, (int, float)):
            stats["missing_points"] += 1
            continue

        by_sleeper[str(sleeper_id)] = float(points)
        stats["mapped_with_points"] += 1

    return by_sleeper, stats


def optimize_for_projection(base, players, projection_by_id):
    projected = [
        base.Player(
            player_id=p.player_id,
            key=p.key,
            name=p.name,
            pos=p.pos,
            slot=p.slot,
            fundamental=p.fundamental,
            projection=projection_by_id.get(p.player_id),
        )
        for p in players
    ]
    return base.optimize_lineup(projected, "projection")


def projection_total(result):
    total = 0.0
    missing = 0
    for row in result["starters"]:
        p = row["player"]
        if p.pos == "K":
            continue
        if p.projection is None:
            missing += 1
        else:
            total += p.projection
    return total, missing


def lineup_ids(result):
    return {row["player"].player_id for row in result["starters"]}


def build_blend(sleeper, fantasypros):
    ids = set(sleeper) | set(fantasypros)
    out = {}
    both = 0
    sleeper_only = 0
    fp_only = 0
    for pid in ids:
        s = sleeper.get(pid)
        f = fantasypros.get(pid)
        if s is not None and f is not None:
            out[pid] = 0.5 * s + 0.5 * f
            both += 1
        elif s is not None:
            out[pid] = s
            sleeper_only += 1
        elif f is not None:
            out[pid] = f
            fp_only += 1
    return out, {
        "both_sources": both,
        "sleeper_only": sleeper_only,
        "fantasypros_only": fp_only,
    }


def median(values):
    return statistics.median(values) if values else None


def summarize_source(team_rows, prefix):
    complete = [r for r in team_rows if r[f"{prefix}_complete"]]
    losses = [r[f"{prefix}_points_left_on_table"] for r in complete]
    efficiencies = [r[f"{prefix}_fv_efficiency_pct"] for r in complete]
    return {
        "teams_with_different_lineup": sum(
            1 for r in team_rows if r[f"{prefix}_different_from_fv"]
        ),
        "teams_with_complete_comparison": len(complete),
        "median_starter_overlap_with_fv": round(
            median([r[f"{prefix}_overlap_with_fv"] for r in team_rows]), 2
        ),
        "median_points_left_on_table": round(median(losses), 2) if losses else None,
        "mean_points_left_on_table": round(statistics.mean(losses), 2)
        if losses
        else None,
        "max_points_left_on_table": round(max(losses), 2) if losses else None,
        "median_fv_efficiency_pct": round(median(efficiencies), 2)
        if efficiencies
        else None,
    }


def run_audit():
    base = load_base_module()
    cfg, sleeper_by_id, roster_doc = base.load_inputs()
    fundamental_by_key = base.snapshot_values.compute_all_values(cfg)
    fp_by_id, fp_stats = load_fantasypros_by_sleeper_id()
    blend_by_id, blend_stats = build_blend(sleeper_by_id, fp_by_id)

    team_rows = []

    for roster in roster_doc.get("rosters", []):
        players, unresolved = base.build_roster_players(
            roster,
            cfg,
            fundamental_by_key,
            sleeper_by_id,
            base.CURRENT_SCOPE_SLOTS,
        )
        if unresolved:
            raise RuntimeError(
                f"production-parity base audit unexpectedly unresolved roster "
                f"{roster.get('roster_id')}: {unresolved}"
            )

        fv = base.optimize_lineup(players, "fundamental")
        fv_ids = lineup_ids(fv)

        source_results = {}
        for label, projections in (
            ("sleeper", sleeper_by_id),
            ("fantasypros", fp_by_id),
            ("blend", blend_by_id),
        ):
            opt = optimize_for_projection(base, players, projections)
            opt_ids = lineup_ids(opt)
            opt_total, opt_missing = projection_total(opt)

            # Evaluate the FV-selected lineup in this same provider's units.
            fv_with_provider = {
                "starters": [
                    {
                        "slot": row["slot"],
                        "player": base.Player(
                            player_id=row["player"].player_id,
                            key=row["player"].key,
                            name=row["player"].name,
                            pos=row["player"].pos,
                            slot=row["player"].slot,
                            fundamental=row["player"].fundamental,
                            projection=projections.get(row["player"].player_id),
                        ),
                    }
                    for row in fv["starters"]
                ]
            }
            fv_total, fv_missing = projection_total(fv_with_provider)

            complete = (
                len(opt["starters"]) == base.EXPECTED_STARTERS
                and len(fv["starters"]) == base.EXPECTED_STARTERS
                and opt_missing == 0
                and fv_missing == 0
            )
            loss = opt_total - fv_total if complete else None
            efficiency = (
                100.0 * fv_total / opt_total
                if complete and opt_total > 0
                else None
            )

            coverage_non_k = [
                p for p in players if p.pos != "K"
            ]
            covered = sum(
                1 for p in coverage_non_k if projections.get(p.player_id) is not None
            )
            coverage_pct = (
                100.0 * covered / len(coverage_non_k) if coverage_non_k else 0.0
            )

            source_results[label] = {
                "different_from_fv": opt_ids != fv_ids,
                "overlap_with_fv": len(opt_ids & fv_ids),
                "complete": complete,
                "coverage_pct": round(coverage_pct, 1),
                "fv_projected_points": round(fv_total, 1),
                "optimal_projected_points": round(opt_total, 1),
                "points_left_on_table": round(loss, 1) if loss is not None else None,
                "fv_efficiency_pct": round(efficiency, 2)
                if efficiency is not None
                else None,
                "lineup_ids": sorted(opt_ids),
            }

        sleeper_ids = set(source_results["sleeper"]["lineup_ids"])
        fp_ids = set(source_results["fantasypros"]["lineup_ids"])
        blend_ids = set(source_results["blend"]["lineup_ids"])

        team_rows.append(
            {
                "roster_id": roster.get("roster_id"),
                "team_name": roster.get("team_name")
                or roster.get("owner_username")
                or f"Roster {roster.get('roster_id')}",
                **{
                    f"{label}_{key}": value
                    for label, payload in source_results.items()
                    for key, value in payload.items()
                    if key != "lineup_ids"
                },
                "sleeper_vs_fantasypros_overlap": len(sleeper_ids & fp_ids),
                "sleeper_vs_blend_overlap": len(sleeper_ids & blend_ids),
                "fantasypros_vs_blend_overlap": len(fp_ids & blend_ids),
            }
        )

    aggregate = {
        "team_count": len(team_rows),
        "expected_starters_per_team": base.EXPECTED_STARTERS,
        "sleeper": summarize_source(team_rows, "sleeper"),
        "fantasypros": summarize_source(team_rows, "fantasypros"),
        "blend": summarize_source(team_rows, "blend"),
        "median_sleeper_vs_fantasypros_overlap": round(
            median([r["sleeper_vs_fantasypros_overlap"] for r in team_rows]), 2
        ),
        "median_sleeper_vs_blend_overlap": round(
            median([r["sleeper_vs_blend_overlap"] for r in team_rows]), 2
        ),
        "median_fantasypros_vs_blend_overlap": round(
            median([r["fantasypros_vs_blend_overlap"] for r in team_rows]), 2
        ),
        "fantasypros_identity": fp_stats,
        "blend_population": blend_stats,
    }

    return {
        "audit": "team_utility_projection_robustness_audit",
        "production_changed": False,
        "fundamental_objective": "current Team Utility starter objective",
        "projection_sources": {
            "sleeper": "scripts/sleeper_2026_projections.json",
            "fantasypros": (
                "scripts/fantasypros_api_normalized_2026.json "
                "via scripts/identity_crosswalk.json"
            ),
            "blend": "50% Sleeper + 50% FantasyPros when both available; single-source fallback otherwise",
        },
        "aggregate": aggregate,
        "teams": team_rows,
        "guardrails": [
            "This tests starter selection only, not the bench-weight coefficient.",
            "FantasyPros normalized totals explicitly omit categories unavailable from its confirmed schema, including IDP QB hits.",
            "Provider agreement does not make projections ground truth; it tests whether the conclusion is source-specific.",
            "Current production roster scope (including taxi) is held fixed to isolate starter-objective choice.",
        ],
    }


def render_md(result):
    a = result["aggregate"]
    lines = [
        "# Team Utility Projection Robustness Audit",
        "",
        "Research-only. **No production values or Team Utility constants were changed.**",
        "",
        "## Question",
        "",
        "Does the conclusion that Fundamental Value is a poor starter-selection objective survive an independent projection provider?",
        "",
        "## Aggregate results",
        "",
        "| Objective used to select starters | Teams differing from FV | Complete comparisons | Median overlap with FV | Median points FV leaves on table | Median FV efficiency |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for label, display in (
        ("sleeper", "Sleeper"),
        ("fantasypros", "FantasyPros normalized"),
        ("blend", "50/50 blend"),
    ):
        s = a[label]
        lines.append(
            f"| {display} | {s['teams_with_different_lineup']}/{a['team_count']} | "
            f"{s['teams_with_complete_comparison']}/{a['team_count']} | "
            f"{s['median_starter_overlap_with_fv']}/{a['expected_starters_per_team']} | "
            f"{s['median_points_left_on_table'] if s['median_points_left_on_table'] is not None else 'n/a'} | "
            f"{str(s['median_fv_efficiency_pct']) + '%' if s['median_fv_efficiency_pct'] is not None else 'n/a'} |"
        )

    lines += [
        "",
        "## Projection-provider agreement",
        "",
        f"- Median Sleeper vs FantasyPros starter overlap: **{a['median_sleeper_vs_fantasypros_overlap']} / {a['expected_starters_per_team']}**",
        f"- Median Sleeper vs blend starter overlap: **{a['median_sleeper_vs_blend_overlap']} / {a['expected_starters_per_team']}**",
        f"- Median FantasyPros vs blend starter overlap: **{a['median_fantasypros_vs_blend_overlap']} / {a['expected_starters_per_team']}**",
        "",
        "## Team detail",
        "",
        "| Team | Sleeper vs FV | FP vs FV | Blend vs FV | Sleeper/FP overlap | Sleeper cov. | FP cov. | Blend cov. |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for r in result["teams"]:
        lines.append(
            f"| {r['team_name']} | "
            f"{r['sleeper_overlap_with_fv']}/{a['expected_starters_per_team']} | "
            f"{r['fantasypros_overlap_with_fv']}/{a['expected_starters_per_team']} | "
            f"{r['blend_overlap_with_fv']}/{a['expected_starters_per_team']} | "
            f"{r['sleeper_vs_fantasypros_overlap']}/{a['expected_starters_per_team']} | "
            f"{r['sleeper_coverage_pct']:.1f}% | "
            f"{r['fantasypros_coverage_pct']:.1f}% | "
            f"{r['blend_coverage_pct']:.1f}% |"
        )

    lines += [
        "",
        "## Data-integrity notes",
        "",
        f"- FantasyPros normalized rows: **{a['fantasypros_identity']['fantasypros_normalized_rows']}**",
        f"- Crosswalk rows mapped to Sleeper IDs with normalized points: **{a['fantasypros_identity']['mapped_with_points']}**",
        f"- Manual-review crosswalk rows skipped: **{a['fantasypros_identity']['manual_review_skipped']}**",
        "",
        "## Guardrails",
        "",
    ]
    lines.extend(f"- {x}" for x in result["guardrails"])
    lines.append("")
    return "\n".join(lines)


def selftest():
    base = load_base_module()
    assert base.EXPECTED_STARTERS == 17

    blend, stats = build_blend(
        {"1": 100.0, "2": 50.0},
        {"1": 80.0, "3": 40.0},
    )
    assert blend["1"] == 90.0
    assert blend["2"] == 50.0
    assert blend["3"] == 40.0
    assert stats == {
        "both_sources": 1,
        "sleeper_only": 1,
        "fantasypros_only": 1,
    }

    if all(p.exists() for p in (FP_NORMALIZED, IDENTITY, BASE_AUDIT_PATH)):
        fp, stats = load_fantasypros_by_sleeper_id()
        assert len(fp) >= 100
        assert stats["mapped_with_points"] == len(fp)

    print("team_utility_projection_robustness_audit self-test passed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return 0

    result = run_audit()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_md(result) + "\n", encoding="utf-8")
    print(json.dumps(result["aggregate"], indent=2))
    print(f"Wrote {OUT_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
