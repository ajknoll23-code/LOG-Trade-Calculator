#!/usr/bin/env python3
"""
Schedule Utility V1 — Phase 1B private coverage/dependence audit.

Runs only against user-supplied private 4for4 CSV exports. It produces
aggregate-only output suitable for a public repository. It does not read
fantasy outcomes and does not authorize production use.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import re
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
P1A_PATH = HERE / "schedule_utility_v1_private_ingest.py"
CELL_RE = re.compile(r"^([0-9]+(?:\.[0-9]+)?)(@?)([A-Z]{2,3})$")

HOT_KEYS = (
    "qb_half", "rb_half", "wr_half", "te_half",
    "rb_ppr", "wr_ppr", "te_ppr",
)
HALF_MASTER_COLUMN = {
    "RB": "RB-HALF",
    "WR": "WR-HALF",
    "TE": "TE-HALF",
}
PAIR_KEYS = {
    "RB": ("rb_half", "rb_ppr"),
    "WR": ("wr_half", "wr_ppr"),
    "TE": ("te_half", "te_ppr"),
}

def load_p1a():
    spec = importlib.util.spec_from_file_location("schedule_utility_v1_p1a", P1A_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Phase 1A helper: {P1A_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def read_csv(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    return list(reader)

def parse_cell(value):
    s = str(value or "").strip()
    if not s or s.upper() == "BYE":
        return None
    m = CELL_RE.fullmatch(s)
    if not m:
        raise ValueError(f"invalid weekly matchup cell: {s!r}")
    return float(m.group(1)), bool(m.group(2)), m.group(3)

def opponent_values(rows):
    out = {}
    for row in rows:
        for week in range(1, 19):
            parsed = parse_cell(row[str(week)])
            if parsed is None:
                continue
            value, _away, opp = parsed
            if opp in out and abs(out[opp] - value) > 1e-12:
                raise ValueError(f"inconsistent opponent value for {opp}")
            out[opp] = value
    if len(out) != 32:
        raise ValueError(f"expected 32 opponent values, got {len(out)}")
    return out

def average_ranks(values):
    ordered = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j][1] == ordered[i][1]:
            j += 1
        avg = ((i + 1) + j) / 2.0
        for k in range(i, j):
            ranks[ordered[k][0]] = avg
        i = j
    return ranks

def pearson(a, b):
    ma = statistics.mean(a)
    mb = statistics.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    if da == 0 or db == 0:
        raise ValueError("zero variance")
    return num / (da * db)

def mean_week_range(row, start, end):
    vals = []
    for week in range(start, end + 1):
        parsed = parse_cell(row[str(week)])
        if parsed is not None:
            vals.append(parsed[0])
    if not vals:
        raise ValueError("empty candidate ROS window")
    return statistics.mean(vals)

def analyze(paths: dict[str, Path], source_capture_utc: str, as_of_week: int):
    p1a = load_p1a()
    base = p1a.validate_source_bundle(paths, source_capture_utc, as_of_week)

    afpa_rows = read_csv(paths["afpa_half"])
    afpa = {row["Team"].strip().upper(): row for row in afpa_rows}
    hot = {key: read_csv(paths[key]) for key in HOT_KEYS}

    format_disagreement = {}
    for pos, (_half_key, ppr_key) in PAIR_KEYS.items():
        ppr = opponent_values(hot[ppr_key])
        teams = sorted(afpa)
        half_vals = [float(afpa[t][HALF_MASTER_COLUMN[pos]]) for t in teams]
        ppr_vals = [float(ppr[t]) for t in teams]
        diffs = [p - h for h, p in zip(half_vals, ppr_vals)]
        half_ranks = average_ranks(half_vals)
        ppr_ranks = average_ranks(ppr_vals)
        rank_shift = [abs(a - b) for a, b in zip(half_ranks, ppr_ranks)]

        easy_half = set(sorted(range(32), key=lambda i: half_vals[i])[-8:])
        easy_ppr = set(sorted(range(32), key=lambda i: ppr_vals[i])[-8:])
        hard_half = set(sorted(range(32), key=lambda i: half_vals[i])[:8])
        hard_ppr = set(sorted(range(32), key=lambda i: ppr_vals[i])[:8])

        format_disagreement[pos] = {
            "half_mean": round(statistics.mean(half_vals), 6),
            "ppr_mean": round(statistics.mean(ppr_vals), 6),
            "mean_ppr_minus_half": round(statistics.mean(diffs), 6),
            "min_ppr_minus_half": round(min(diffs), 6),
            "max_ppr_minus_half": round(max(diffs), 6),
            "spearman_rank_correlation": round(pearson(half_ranks, ppr_ranks), 9),
            "mean_abs_rank_shift": round(statistics.mean(rank_shift), 6),
            "max_abs_rank_shift": round(max(rank_shift), 6),
            "easiest_quartile_overlap_of_8": len(easy_half & easy_ppr),
            "hardest_quartile_overlap_of_8": len(hard_half & hard_ppr),
        }

    # Infer which contiguous displayed-week window best reproduces provider ROS.
    candidates = []
    for start in range(1, 19):
        for end in range(start, 19):
            errors = []
            for rows in hot.values():
                for row in rows:
                    derived = mean_week_range(row, start, end)
                    errors.append(abs(derived - float(row["ROS"])))
            candidates.append({
                "start": start,
                "end": end,
                "mean_abs_error": statistics.mean(errors),
                "max_abs_error": max(errors),
            })
    candidates.sort(key=lambda x: x["mean_abs_error"])
    best, second = candidates[0], candidates[1]

    return {
        "schema_version": 1,
        "study_id": "schedule-utility-v1",
        "phase": "1B",
        "status": "PASS_COVERAGE_DEPENDENCE_AUDIT_FRESHNESS_GUARD",
        "outcome_data_read": False,
        "outcome_association_opened": False,
        "production_change_authorized": False,
        "phase2_outcome_test_authorized": False,
        "source_bundle_phase1a_status": base["status"],
        "coverage": base["coverage"],
        "source_dependence": {
            "afpa_and_hot_spots_independent_predictors": False,
            "half_ppr_exact_cell_checks": base["validation"]["half_ppr_afpa_exact_checks"],
            "half_ppr_exact_cell_mismatches": base["validation"]["half_ppr_afpa_value_mismatches"],
            "interpretation": (
                "Hot Spots is the schedule/window presentation of the same opponent "
                "aFPA matchup values, not an independent signal."
            ),
            "double_counting_guard": (
                "Do not blend or weight aFPA and Hot Spots as separate predictors."
            ),
        },
        "scoring_format_audit": format_disagreement,
        "provider_summary_semantics": {
            "ros_best_displayed_week_window": [best["start"], best["end"]],
            "ros_best_mean_abs_display_rounding_error": round(best["mean_abs_error"], 9),
            "ros_best_max_abs_display_rounding_error": round(best["max_abs_error"], 9),
            "ros_second_best_mean_abs_error": round(second["mean_abs_error"], 9),
            "po2_semantics_from_phase1a": "Weeks 16-17 average within display rounding",
            "po3_semantics_from_phase1a": "Weeks 15-17 average within display rounding",
            "provider_ros_po2_po3_used_as_primary_v1_scores": False,
        },
        "freshness": {
            "csv_embeds_capture_timestamp": False,
            "csv_embeds_as_of_week": False,
            "externally_supplied_capture_timestamp_required": True,
            "externally_supplied_as_of_week_required": True,
            "ros_structure_strongly_consistent_with_as_of_week": best["start"],
            "inference_is_not_authoritative_metadata": True,
            "current_snapshot_freshness_formally_verified": False,
        },
        "phase2_readiness": {
            "ready": False,
            "blocking_reasons": [
                "Current CSV snapshot lacks authoritative embedded capture timestamp/as-of week.",
                "Only one current provider snapshot is available.",
                "Retrospective predictive validation requires time-valid historical predictor snapshots or an equivalent look-ahead-safe source archive."
            ],
            "next_phase": "1C historical snapshot and freshness feasibility",
            "outcomes_remain_sealed": True,
        },
    }

def selftest():
    assert average_ranks([1, 2, 2, 4]) == [1.0, 2.5, 2.5, 4.0]
    assert abs(pearson([1, 2, 3], [1, 2, 3]) - 1.0) < 1e-12
    assert parse_cell("10.9@LAC") == (10.9, True, "LAC")
    assert parse_cell("13.4SEA") == (13.4, False, "SEA")
    assert parse_cell("BYE") is None
    print("PASS: Phase 1B private audit selftest")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    for arg in (
        "afpa-half", "qb-half", "rb-half", "wr-half", "te-half",
        "rb-ppr", "wr-ppr", "te-ppr"
    ):
        ap.add_argument(f"--{arg}")
    ap.add_argument("--source-capture-utc")
    ap.add_argument("--as-of-week", type=int)
    ap.add_argument("--public-summary")
    ns = ap.parse_args()

    if ns.selftest:
        selftest()
        return

    mapping = {
        "afpa_half": ns.afpa_half,
        "qb_half": ns.qb_half,
        "rb_half": ns.rb_half,
        "wr_half": ns.wr_half,
        "te_half": ns.te_half,
        "rb_ppr": ns.rb_ppr,
        "wr_ppr": ns.wr_ppr,
        "te_ppr": ns.te_ppr,
    }
    missing = [k for k, v in mapping.items() if not v]
    if missing:
        raise SystemExit(f"missing private source paths: {missing}")
    if not ns.source_capture_utc or ns.as_of_week is None:
        raise SystemExit("source capture UTC and as-of week are required")
    if not ns.public_summary:
        raise SystemExit("--public-summary is required")

    paths = {k: Path(v).expanduser().resolve() for k, v in mapping.items()}
    result = analyze(paths, ns.source_capture_utc, ns.as_of_week)
    Path(ns.public_summary).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "decision": result["status"],
        "phase2_ready": result["phase2_readiness"]["ready"],
        "outcomes_read": False,
    }, indent=2))

if __name__ == "__main__":
    main()
