#!/usr/bin/env python3
"""
Replacement Level / Positional Scale V2 — Phase 2 historical backtest.

Research-only comprehensive replacement-rank evaluation.

This phase reuses the already-reviewed Revision-2 baseline backtester Test 3:
for each historical fold it derives the replacement structure entirely from
future production, then measures how well each candidate training-time
replacement rank predicted that future relative-production magnitude.

Important:
- one position is evaluated at a time;
- no seven-position Cartesian optimization;
- POSITION_WEIGHT is not changed;
- the PM transform is not changed;
- the global value scale is not changed;
- no deployed file or frozen prospective experiment is changed.

Historical data limitation inherited from the reviewed backtester:
historical provider-projection snapshots do not exist, so trailing PPG is the
training numerator. This isolates the denominator question but is not a full
historical replay of the eventual blended Production V2 numerator.

Outputs:
  research/replacement-level-v2/replacement_level_v2_phase2_historical_backtest.json
  research/replacement-level-v2/replacement_level_v2_phase2_historical_backtest.md
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]

PHASE1_PATH = (
    REPO_ROOT
    / "research"
    / "replacement-level-v2"
    / "replacement_level_v2_phase1_audit.json"
)
BACKTEST_PY = (
    REPO_ROOT
    / "research"
    / "baseline-backtester"
    / "baseline_backtester.py"
)
# Canonical historical weekly-points dataset is owned by the roster-economics
# research pipeline. The reviewed baseline_backtester.py was later organized
# into research/baseline-backtester/, but this input intentionally remained
# under research/roster-economics/.
POINTS_PATH = (
    REPO_ROOT
    / "research"
    / "roster-economics"
    / "weekly_points_by_season.json"
)
PRIOR_NORMALIZATION_PATH = (
    REPO_ROOT
    / "research"
    / "production-v2"
    / "production_v2_phase3_baseline_normalization_audit.json"
)

OUTPUT_JSON = (
    REPO_ROOT
    / "research"
    / "replacement-level-v2"
    / "replacement_level_v2_phase2_historical_backtest.json"
)
OUTPUT_MD = (
    REPO_ROOT
    / "research"
    / "replacement-level-v2"
    / "replacement_level_v2_phase2_historical_backtest.md"
)

METHOD_VERSION = "replacement-level-v2-phase2-historical-backtest-v1"
TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
FORWARD_WINDOWS = (2, 4, 6)
PRIMARY_WINDOW = 4
MAX_CANDIDATE_RANK = 60

# Prior limited denominator-only Production V2 evidence. Phase 2 does not assume
# these are correct; they are carried as explicit comparators.
PRIOR_EVIDENCE_HYBRID = {
    "QB": 18,
    "RB": 26,
    "WR": 34,
    "TE": 15,
    "DL": 23,
    "LB": 32,
    "DB": 30,
}


def read_json(path: Path):
    if not path.exists():
        raise RuntimeError(f"missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(values):
    out = []
    for value in values:
        try:
            x = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(x):
            out.append(x)
    return out


def median(values):
    vals = finite(values)
    return statistics.median(vals) if vals else None


def mean(values):
    vals = finite(values)
    return statistics.fmean(vals) if vals else None


def pct_delta(value, control):
    if value is None or control in (None, 0):
        return None
    return (float(value) - float(control)) / float(control)


def round_numbers(obj, digits=6):
    if isinstance(obj, dict):
        return {k: round_numbers(v, digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_numbers(v, digits) for v in obj]
    if isinstance(obj, float):
        return round(obj, digits) if math.isfinite(obj) else None
    return obj


def load_backtester():
    if not BACKTEST_PY.exists():
        raise RuntimeError(
            f"missing reviewed baseline backtester: {BACKTEST_PY.relative_to(REPO_ROOT)}"
        )
    spec = importlib.util.spec_from_file_location(
        "replacement_level_v2_reviewed_backtester", BACKTEST_PY
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not import reviewed baseline_backtester.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_phase1(phase1):
    if phase1.get("method_version") != "replacement-level-v2-phase1-baseline-audit-v1":
        raise RuntimeError("unexpected Phase 1 method version")

    required_false = (
        "deployment_authorized",
        "production_v2_change_authorized",
        "position_weight_change_authorized",
        "replacement_rank_change_authorized",
        "scale_change_authorized",
    )
    for field in required_false:
        if phase1.get(field) is not False:
            raise RuntimeError(f"Phase 1 guardrail changed unexpectedly: {field}")

    strategy = (phase1.get("scope") or {}).get("phase2_strategy")
    if "one-position-at-a-time" not in str(strategy):
        raise RuntimeError("Phase 1 no longer authorizes one-position-at-a-time Phase 2")

    positions = phase1.get("positions")
    if not isinstance(positions, dict):
        raise RuntimeError("Phase 1 positions object missing")

    legacy = (phase1.get("legacy_transport") or {}).get("replacement_ranks") or {}
    for pos in TRACKED_POSITIONS:
        if pos not in positions or pos not in legacy:
            raise RuntimeError(f"Phase 1 missing position {pos}")
        grid = ((positions[pos].get("phase2_grid") or {}).get("candidate_ranks"))
        if not isinstance(grid, list) or not grid:
            raise RuntimeError(f"{pos}: missing Phase 2 candidate grid")
        ranks = [int(x) for x in grid]
        if len(ranks) != len(set(ranks)) or ranks != sorted(ranks):
            raise RuntimeError(f"{pos}: candidate ranks must be unique and sorted")
        if min(ranks) < 1 or max(ranks) > MAX_CANDIDATE_RANK:
            raise RuntimeError(f"{pos}: candidate rank outside 1..{MAX_CANDIDATE_RANK}")
        if int(legacy[pos]) not in ranks:
            raise RuntimeError(f"{pos}: legacy control rank not in Phase 2 grid")
        if PRIOR_EVIDENCE_HYBRID[pos] not in ranks:
            raise RuntimeError(
                f"{pos}: prior evidence-hybrid comparator "
                f"{PRIOR_EVIDENCE_HYBRID[pos]} not in Phase 2 grid"
            )


def candidate_name(rank: int) -> str:
    return f"rank_{int(rank):02d}"


def candidate_rank(name: str) -> int:
    if not name.startswith("rank_"):
        raise RuntimeError(f"unexpected candidate name {name!r}")
    return int(name.split("_", 1)[1])


def evaluate_position(backtester, points_data, pos, ranks):
    original_candidates = backtester.BASELINE_CANDIDATES
    try:
        backtester.BASELINE_CANDIDATES = {
            candidate_name(rank): {pos: int(rank)}
            for rank in ranks
        }

        by_window = {}
        for window in FORWARD_WINDOWS:
            folds = backtester.build_folds(points_data, window)
            raw = backtester.run_test3(folds, pos)

            # Every rank should have been evaluated against the same folds.
            fold_name_sets = {
                tuple((raw.get(candidate_name(rank)) or {}).get("fold_names") or ())
                for rank in ranks
            }
            if len(fold_name_sets) != 1:
                raise RuntimeError(
                    f"{pos} window {window}: candidates did not share identical folds"
                )

            rows = {}
            for rank in ranks:
                name = candidate_name(rank)
                rec = raw.get(name) or {}
                maes = [float(x) for x in rec.get("mae") or []]
                rmses = [float(x) for x in rec.get("rmse") or []]
                fold_names = list(rec.get("fold_names") or [])
                if len(maes) != len(rmses) or len(maes) != len(fold_names):
                    raise RuntimeError(
                        f"{pos} rank {rank} window {window}: malformed fold arrays"
                    )

                pairs = list(zip(fold_names, maes, rmses))
                segment_mae = {
                    "2024": [m for f, m, _ in pairs if f.startswith("2024_wk")],
                    "2025": [m for f, m, _ in pairs if f.startswith("2025_wk")],
                    "cross": [m for f, m, _ in pairs if f == "2024_full_to_2025_full"],
                }
                rows[str(rank)] = {
                    "rank": int(rank),
                    "n_folds": len(maes),
                    "median_mae": median(maes),
                    "mean_mae": mean(maes),
                    "median_rmse": median(rmses),
                    "mean_rmse": mean(rmses),
                    "segment_median_mae": {
                        k: median(v) for k, v in segment_mae.items()
                    },
                    "folds": [
                        {"name": f, "mae": m, "rmse": r}
                        for f, m, r in pairs
                    ],
                }

            valid = [
                rec for rec in rows.values()
                if rec["median_mae"] is not None
            ]
            if not valid:
                raise RuntimeError(f"{pos} window {window}: no candidates resolved")
            # Deterministic tie-break: primary statistic, then mean MAE, then
            # closeness to the legacy control is applied later only if still tied.
            min_median = min(float(r["median_mae"]) for r in valid)
            leaders = [
                r for r in valid
                if abs(float(r["median_mae"]) - min_median) < 1e-12
            ]
            min_mean = min(float(r["mean_mae"]) for r in leaders)
            leaders = [
                r for r in leaders
                if abs(float(r["mean_mae"]) - min_mean) < 1e-12
            ]

            # Per-fold best-or-tied counts. These rolling folds are overlapping,
            # so this is descriptive evidence, not independent trial counts.
            names = list(valid[0]["folds"])
            best_or_tied = {str(rank): 0 for rank in ranks}
            strict_wins = {str(rank): 0 for rank in ranks}
            for i in range(len(names)):
                fold_scores = {
                    str(rank): rows[str(rank)]["folds"][i]["mae"]
                    for rank in ranks
                }
                best = min(fold_scores.values())
                tied = [
                    key for key, val in fold_scores.items()
                    if abs(float(val) - float(best)) < 1e-12
                ]
                for key in tied:
                    best_or_tied[key] += 1
                if len(tied) == 1:
                    strict_wins[tied[0]] += 1

            for rank in ranks:
                rows[str(rank)]["strict_fold_wins"] = strict_wins[str(rank)]
                rows[str(rank)]["fold_best_or_tied"] = best_or_tied[str(rank)]

            by_window[str(window)] = {
                "leader_candidates_after_metric_tiebreak": [
                    int(r["rank"]) for r in leaders
                ],
                "candidates": rows,
            }

        return by_window
    finally:
        backtester.BASELINE_CANDIDATES = original_candidates


def select_context_leader(candidates, legacy_rank):
    valid = [r for r in candidates if r.get("value") is not None]
    if not valid:
        return None
    best_value = min(float(r["value"]) for r in valid)
    tied = [r for r in valid if abs(float(r["value"]) - best_value) < 1e-12]
    tied.sort(key=lambda r: (abs(int(r["rank"]) - int(legacy_rank)), int(r["rank"])))
    return int(tied[0]["rank"])


def build_position_summary(pos, phase1, by_window):
    p1 = phase1["positions"][pos]
    ranks = [int(x) for x in p1["phase2_grid"]["candidate_ranks"]]
    legacy_rank = int(p1["legacy_replacement_rank"])
    prior_rank = int(PRIOR_EVIDENCE_HYBRID[pos])

    primary = by_window[str(PRIMARY_WINDOW)]["candidates"]
    legacy_primary = primary[str(legacy_rank)]
    prior_primary = primary[str(prior_rank)]

    # Primary-window leader using median MAE, then mean MAE, then closeness
    # to legacy only as a deterministic final tie-break.
    primary_context = [
        {
            "rank": r,
            "value": primary[str(r)]["median_mae"],
            "mean": primary[str(r)]["mean_mae"],
        }
        for r in ranks
    ]
    min_med = min(float(x["value"]) for x in primary_context if x["value"] is not None)
    med_tied = [
        x for x in primary_context
        if x["value"] is not None
        and abs(float(x["value"]) - min_med) < 1e-12
    ]
    min_mean = min(float(x["mean"]) for x in med_tied)
    mean_tied = [
        x for x in med_tied
        if abs(float(x["mean"]) - min_mean) < 1e-12
    ]
    mean_tied.sort(key=lambda x: (abs(x["rank"] - legacy_rank), x["rank"]))
    primary_leader = int(mean_tied[0]["rank"])

    window_leaders = {}
    for window in FORWARD_WINDOWS:
        rows = by_window[str(window)]["candidates"]
        context = [
            {"rank": r, "value": rows[str(r)]["median_mae"]}
            for r in ranks
        ]
        window_leaders[str(window)] = select_context_leader(context, legacy_rank)

    segment_leaders = {}
    for segment in ("2024", "2025", "cross"):
        context = [
            {
                "rank": r,
                "value": primary[str(r)]["segment_median_mae"][segment],
            }
            for r in ranks
        ]
        segment_leaders[segment] = select_context_leader(context, legacy_rank)

    primary_rec = primary[str(primary_leader)]
    leader_better_than_legacy = (
        primary_rec["median_mae"] is not None
        and legacy_primary["median_mae"] is not None
        and float(primary_rec["median_mae"]) < float(legacy_primary["median_mae"])
    )

    windows_beating_legacy = 0
    for window in FORWARD_WINDOWS:
        rows = by_window[str(window)]["candidates"]
        cand = rows[str(primary_leader)]["median_mae"]
        ctl = rows[str(legacy_rank)]["median_mae"]
        if cand is not None and ctl is not None and float(cand) <= float(ctl):
            windows_beating_legacy += 1

    season_blocks_beating_legacy = 0
    for segment in ("2024", "2025", "cross"):
        cand = primary[str(primary_leader)]["segment_median_mae"][segment]
        ctl = legacy_primary["segment_median_mae"][segment]
        if cand is not None and ctl is not None and float(cand) <= float(ctl):
            season_blocks_beating_legacy += 1

    window_leader_values = list(window_leaders.values())
    stable_all_windows = len(set(window_leader_values)) == 1

    # Phase 3 shortlist is deliberately conservative: every winner under a
    # meaningful context, plus the legacy control and prior limited-evidence
    # comparator. This avoids pretending overlapping rolling windows are 15
    # independent votes.
    shortlist = {legacy_rank, prior_rank, primary_leader}
    shortlist.update(x for x in window_leaders.values() if x is not None)
    shortlist.update(x for x in segment_leaders.values() if x is not None)

    return {
        "candidate_ranks": ranks,
        "legacy_control_rank": legacy_rank,
        "prior_limited_evidence_rank": prior_rank,
        "primary_window": PRIMARY_WINDOW,
        "primary_leader_rank": primary_leader,
        "primary_leader_median_mae": primary_rec["median_mae"],
        "legacy_median_mae": legacy_primary["median_mae"],
        "primary_leader_vs_legacy_mae_delta": (
            float(primary_rec["median_mae"]) - float(legacy_primary["median_mae"])
            if primary_rec["median_mae"] is not None
            and legacy_primary["median_mae"] is not None
            else None
        ),
        "primary_leader_vs_legacy_mae_pct": pct_delta(
            primary_rec["median_mae"], legacy_primary["median_mae"]
        ),
        "prior_limited_evidence_median_mae": prior_primary["median_mae"],
        "primary_leader_vs_prior_mae_pct": pct_delta(
            primary_rec["median_mae"], prior_primary["median_mae"]
        ),
        "window_leaders": window_leaders,
        "stable_same_leader_across_2_4_6_week_windows": stable_all_windows,
        "segment_leaders_at_primary_window": segment_leaders,
        "primary_leader_strict_fold_wins": primary_rec["strict_fold_wins"],
        "primary_leader_fold_best_or_tied": primary_rec["fold_best_or_tied"],
        "primary_leader_beats_legacy_primary": leader_better_than_legacy,
        "primary_leader_nonworse_than_legacy_windows": windows_beating_legacy,
        "primary_leader_nonworse_than_legacy_season_blocks": (
            season_blocks_beating_legacy
        ),
        "historical_screen_pass": bool(
            leader_better_than_legacy
            and windows_beating_legacy >= 2
            and season_blocks_beating_legacy >= 2
        ),
        "phase3_shortlist_ranks": sorted(shortlist),
        "all_candidate_metrics_by_window": by_window,
    }


def build_result():
    phase1 = read_json(PHASE1_PATH)
    validate_phase1(phase1)
    points_data = read_json(POINTS_PATH)
    prior_normalization = read_json(PRIOR_NORMALIZATION_PATH)
    backtester = load_backtester()

    if getattr(backtester, "PRIMARY_WINDOW", None) != PRIMARY_WINDOW:
        raise RuntimeError("reviewed backtester primary window changed unexpectedly")
    if tuple(getattr(backtester, "FORWARD_WINDOWS", ())) != FORWARD_WINDOWS:
        raise RuntimeError("reviewed backtester forward windows changed unexpectedly")
    if getattr(backtester, "MIN_TRAILING_GAMES", None) != 3:
        raise RuntimeError("reviewed backtester trailing-games minimum changed unexpectedly")

    prior_ranks = prior_normalization.get("evidence_hybrid_ranks") or {}
    for pos in TRACKED_POSITIONS:
        if int(prior_ranks.get(pos, -1)) != PRIOR_EVIDENCE_HYBRID[pos]:
            raise RuntimeError(f"{pos}: prior Production V2 evidence rank changed")

    positions = {}
    for pos in TRACKED_POSITIONS:
        ranks = [
            int(x)
            for x in phase1["positions"][pos]["phase2_grid"]["candidate_ranks"]
        ]
        by_window = evaluate_position(backtester, points_data, pos, ranks)
        positions[pos] = build_position_summary(pos, phase1, by_window)

    return round_numbers({
        "method_version": METHOD_VERSION,
        "status": "RESEARCH_ONLY_REPLACEMENT_LEVEL_HISTORICAL_BACKTEST",
        "deployment_authorized": False,
        "production_v2_change_authorized": False,
        "replacement_rank_change_authorized": False,
        "position_weight_change_authorized": False,
        "scale_change_authorized": False,
        "frozen_prospective_experiments_touched": False,
        "evaluation_method": {
            "source": "research/baseline-backtester/baseline_backtester.py Revision 2 Test 3",
            "decision_target": (
                "future-only relative-production structure; MAE/RMSE of "
                "training-time predicted ratios versus realized future ratios"
            ),
            "primary_forward_window_weeks": PRIMARY_WINDOW,
            "robustness_forward_windows_weeks": list(FORWARD_WINDOWS),
            "minimum_trailing_games": 3,
            "candidate_strategy": "one position at a time; no Cartesian grid",
            "rolling_fold_warning": (
                "rolling weekly folds overlap heavily and are not treated as "
                "independent trials; season-block and window stability are reported"
            ),
            "historical_numerator_limitation": (
                "historical provider snapshots do not exist, so trailing PPG is "
                "the training numerator; this isolates replacement denominator "
                "quality rather than replaying the final blended Production V2 numerator"
            ),
        },
        "phase2_decision_policy": {
            "historical_screen_pass_requires": [
                "primary 4-week leader strictly beats legacy median MAE",
                "leader is non-worse than legacy in at least 2 of 3 forward windows",
                "leader is non-worse than legacy in at least 2 of 3 season blocks (2024, 2025, cross-season)",
            ],
            "phase3_shortlist_policy": (
                "carry legacy control, prior limited-evidence rank, primary leader, "
                "all 2/4/6-week leaders, and all 2024/2025/cross-season leaders"
            ),
            "no_deployment_claim": True,
        },
        "positions": positions,
        "input_sha256": {
            str(PHASE1_PATH.relative_to(REPO_ROOT)): sha256(PHASE1_PATH),
            str(BACKTEST_PY.relative_to(REPO_ROOT)): sha256(BACKTEST_PY),
            str(POINTS_PATH.relative_to(REPO_ROOT)): sha256(POINTS_PATH),
            str(PRIOR_NORMALIZATION_PATH.relative_to(REPO_ROOT)): sha256(
                PRIOR_NORMALIZATION_PATH
            ),
        },
    })


def fmt(value, digits=4):
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def fmt_pct(value):
    if value is None:
        return "—"
    return f"{100.0 * float(value):+.1f}%"


def render_md(result):
    lines = [
        "# Replacement Level / Positional Scale V2 — Phase 2 Historical Backtest",
        "",
        "**Research only. No deployment, position-weight, scale, Production V2, or frozen-experiment change is authorized.**",
        "",
        f"Method: `{result['method_version']}`",
        "",
        "## Method",
        "",
        "This phase reuses the reviewed Revision-2 baseline backtester's **Test 3**. "
        "Each fold derives its replacement structure entirely from future production, "
        "then scores each training-time candidate rank by MAE/RMSE against that future "
        "relative-production structure.",
        "",
        "The 4-week window is primary; 2- and 6-week windows are robustness checks. "
        "Rolling weekly folds overlap, so fold-win counts are descriptive rather than "
        "independent trials. 2024, 2025, and cross-season blocks are reported separately.",
        "",
        "Historical provider projection snapshots do not exist, so trailing PPG remains "
        "the training numerator. This is a denominator test, not a perfect historical "
        "replay of the final blended Production V2 formula.",
        "",
        "## Position results",
        "",
        "| Pos | Legacy | Prior limited | Phase-2 leader | 4wk leader MAE | Legacy MAE | Δ vs legacy | Window leaders 2/4/6 | Season leaders 2024/2025/cross | Hist pass | Phase-3 shortlist |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|---|---|",
    ]

    for pos in TRACKED_POSITIONS:
        p = result["positions"][pos]
        wl = p["window_leaders"]
        sl = p["segment_leaders_at_primary_window"]
        lines.append(
            f"| {pos} | {p['legacy_control_rank']} | "
            f"{p['prior_limited_evidence_rank']} | {p['primary_leader_rank']} | "
            f"{fmt(p['primary_leader_median_mae'])} | {fmt(p['legacy_median_mae'])} | "
            f"{fmt_pct(p['primary_leader_vs_legacy_mae_pct'])} | "
            f"{wl['2']}/{wl['4']}/{wl['6']} | "
            f"{sl['2024']}/{sl['2025']}/{sl['cross']} | "
            f"{'PASS' if p['historical_screen_pass'] else 'NO'} | "
            f"{', '.join(str(x) for x in p['phase3_shortlist_ranks'])} |"
        )

    lines += [
        "",
        "## Candidate detail",
        "",
    ]

    for pos in TRACKED_POSITIONS:
        p = result["positions"][pos]
        primary = p["all_candidate_metrics_by_window"]["4"]["candidates"]
        lines += [
            f"### {pos}",
            "",
            f"- Legacy control: **{p['legacy_control_rank']}**",
            f"- Prior limited Production V2 comparator: **{p['prior_limited_evidence_rank']}**",
            f"- Primary 4-week leader: **{p['primary_leader_rank']}**",
            f"- Same leader across 2/4/6 weeks: **{p['stable_same_leader_across_2_4_6_week_windows']}**",
            f"- Historical screen: **{'PASS' if p['historical_screen_pass'] else 'NO'}**",
            f"- Phase-3 shortlist: **{', '.join(str(x) for x in p['phase3_shortlist_ranks'])}**",
            "",
            "| Rank | Median MAE | Mean MAE | Median RMSE | 2024 MAE | 2025 MAE | Cross MAE | Strict fold wins | Best/tied folds | Δ MAE vs legacy |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        legacy_mae = primary[str(p["legacy_control_rank"])]["median_mae"]
        for rank in p["candidate_ranks"]:
            rec = primary[str(rank)]
            seg = rec["segment_median_mae"]
            lines.append(
                f"| {rank} | {fmt(rec['median_mae'])} | {fmt(rec['mean_mae'])} | "
                f"{fmt(rec['median_rmse'])} | {fmt(seg['2024'])} | "
                f"{fmt(seg['2025'])} | {fmt(seg['cross'])} | "
                f"{rec['strict_fold_wins']} | {rec['fold_best_or_tied']} | "
                f"{fmt_pct(pct_delta(rec['median_mae'], legacy_mae))} |"
            )
        lines.append("")

    lines += [
        "## Guardrails",
        "",
        "- deployment_authorized: **false**",
        "- production_v2_change_authorized: **false**",
        "- replacement_rank_change_authorized: **false**",
        "- position_weight_change_authorized: **false**",
        "- scale_change_authorized: **false**",
        "- frozen prospective experiments touched: **false**",
        "",
        "## Next step",
        "",
        "Phase 3 should run the shortlisted replacement ranks through the current 2026 "
        "board while holding Production V2 inputs, age, opportunity, durability, "
        "no-history logic, PM transform, position weights, and global scale fixed. "
        "That phase measures blast radius and ranking stability; it still does not deploy.",
        "",
    ]
    return "\n".join(lines)


def run_selftest():
    # Deterministic helper tests.
    assert median([3, 1, 2]) == 2
    assert abs(pct_delta(0.9, 1.0) + 0.1) < 1e-12
    assert candidate_name(5) == "rank_05"
    assert candidate_rank("rank_34") == 34
    assert select_context_leader(
        [{"rank": 30, "value": 1.0}, {"rank": 32, "value": 1.0}], 32
    ) == 32

    # If the repo inputs are present, also run the reviewed backtester's own
    # synthetic self-test, which proves Test 3 discriminates a known-correct
    # denominator from wrong ones.
    if BACKTEST_PY.exists():
        module = load_backtester()
        module.run_selftest()

    print("PASS Replacement Level V2 Phase 2 self-test.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        if not args.write and not args.check:
            return

    result = build_result()
    rendered_json = json.dumps(result, indent=2, sort_keys=True) + "\n"
    rendered_md = render_md(result).rstrip() + "\n"

    if args.write:
        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_JSON.write_text(rendered_json, encoding="utf-8")
        OUTPUT_MD.write_text(rendered_md, encoding="utf-8")
        print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
        print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")

    if args.check:
        if not OUTPUT_JSON.exists() or not OUTPUT_MD.exists():
            raise RuntimeError("Phase 2 outputs do not exist; run --write first")
        if OUTPUT_JSON.read_text(encoding="utf-8") != rendered_json:
            raise RuntimeError("Phase 2 JSON is stale or non-deterministic")
        if OUTPUT_MD.read_text(encoding="utf-8") != rendered_md:
            raise RuntimeError("Phase 2 Markdown is stale or non-deterministic")
        for field in (
            "deployment_authorized",
            "production_v2_change_authorized",
            "replacement_rank_change_authorized",
            "position_weight_change_authorized",
            "scale_change_authorized",
        ):
            if result.get(field) is not False:
                raise RuntimeError(f"guardrail failed: {field}")
        if result.get("frozen_prospective_experiments_touched") is not False:
            raise RuntimeError("frozen experiment guardrail failed")
        print("PASS Replacement Level V2 Phase 2 checks.")

    if not args.write and not args.check and not args.selftest:
        print(rendered_md)


if __name__ == "__main__":
    main()
