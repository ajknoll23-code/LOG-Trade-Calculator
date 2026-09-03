#!/usr/bin/env python3
"""
Production V2 Phase 2A — immutable 2026 preseason baseline + sensitivity audit.

WHY THIS EXISTS
---------------
The repository does not contain temporally-valid 2025 FantasyPros/Sleeper
preseason projection snapshots. Therefore we cannot honestly backtest the
provider blend or history-vs-forward weight today.

Phase 2A does two things before 2026 games begin:

1. Freeze the current 2026 preseason evidence state so future realized results
   can be evaluated against what the model actually knew BEFORE the season.
2. Run a sensitivity grid over plausible offense provider weights and
   history-vs-forward weights. This measures blast radius only. It does NOT
   declare any weight optimal.

THIS SCRIPT NEVER MUTATES PRODUCTION.

INPUTS
------
- research/production-v2/production_v2_phase1_audit.json
- index.html
- scripts/fantasypros_api_normalized_2026.json
- scripts/sleeper_2026_projections.json
- scripts/identity_crosswalk.json

OUTPUTS (immutable once created)
--------------------------------
- research/production-v2/production_v2_phase2_preseason_baseline.json
- research/production-v2/production_v2_phase2_preseason_baseline.md

If current inputs later change, --write/--check REFUSE to overwrite the frozen
baseline. That is intentional; changing a preseason baseline after games begin
would destroy out-of-sample validity.

USAGE
-----
python3 research/production-v2/production_v2_phase2_preseason_baseline.py --selftest
python3 research/production-v2/production_v2_phase2_preseason_baseline.py --write
python3 research/production-v2/production_v2_phase2_preseason_baseline.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
SCRIPTS = REPO_ROOT / "scripts"

PHASE1 = REPO_ROOT / "research" / "production-v2" / "production_v2_phase1_audit.json"
INDEX_HTML = REPO_ROOT / "index.html"
FP_NORMALIZED = SCRIPTS / "fantasypros_api_normalized_2026.json"
SLEEPER_TOTALS = SCRIPTS / "sleeper_2026_projections.json"
IDENTITY = SCRIPTS / "identity_crosswalk.json"

OUTPUT_JSON = REPO_ROOT / "research" / "production-v2" / "production_v2_phase2_preseason_baseline.json"
OUTPUT_MD = REPO_ROOT / "research" / "production-v2" / "production_v2_phase2_preseason_baseline.md"

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
OFFENSE = {"QB", "RB", "WR", "TE"}

# Sensitivity only. These are NOT recommendations.
FP_WEIGHT_GRID = (0.00, 0.25, 0.50, 0.75, 1.00)
HISTORY_WEIGHT_GRID = (0.25, 0.45, 0.65)

REFERENCE_FP_WEIGHT = 0.50
REFERENCE_HISTORY_WEIGHT = 0.45

REPLACEMENT_RANK = {
    "QB": 18,
    "RB": 32,
    "WR": 36,
    "TE": 15,
    "DL": 32,
    "LB": 32,
    "DB": 32,
}

PM_INTERCEPT = -0.10
PM_RATIO_SLOPE = 0.75
PM_MIN = 0.15
PM_MAX = 1.55
GLOBAL_VALUE_SCALE = 55.0

MIN_PHASE1_CANDIDATE_COVERAGE = 0.90
MIN_OFFENSE_BOTH_SOURCE = {
    "QB": 20,
    "RB": 40,
    "WR": 50,
    "TE": 20,
}


def read_json(path: Path):
    if not path.exists():
        raise RuntimeError(f"missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value):
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def percentile(values, q):
    vals = sorted(float(v) for v in values)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    q = clamp(float(q), 0.0, 1.0)
    idx = (len(vals) - 1) * q
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    frac = idx - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def average_ranks(values):
    indexed = sorted(enumerate(values), key=lambda x: (-x[1], x[0]))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg = ((i + 1) + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg
        i = j
    return ranks


def pearson(xs, ys):
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    if den == 0:
        return None
    return sum(a*b for a, b in zip(dx, dy)) / den


def spearman(xs, ys):
    return pearson(average_ranks(xs), average_ranks(ys))


def round_numbers(obj, digits=6):
    if isinstance(obj, dict):
        return {k: round_numbers(v, digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_numbers(v, digits) for v in obj]
    if isinstance(obj, float):
        return round(obj, digits) if math.isfinite(obj) else None
    return obj


def load_snapshot_values():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from validation import snapshot_values  # type: ignore
    return snapshot_values


def validate_phase1(phase1):
    if phase1.get("production_mutation_authorized") is not False:
        raise RuntimeError("Phase 1 is not marked research-only")

    dq = phase1.get("data_quality") or {}
    share = finite(dq.get("candidate_coverage_share")) or 0.0
    if share < MIN_PHASE1_CANDIDATE_COVERAGE:
        raise RuntimeError(
            f"Phase 1 candidate coverage {share:.1%} is below required "
            f"{MIN_PHASE1_CANDIDATE_COVERAGE:.0%}"
        )

    coverage = phase1.get("coverage_by_position") or {}
    failures = []
    for pos, minimum in MIN_OFFENSE_BOTH_SOURCE.items():
        both = int((coverage.get(pos) or {}).get("both_provider_rows", 0))
        if both < minimum:
            failures.append(f"{pos} both-provider rows {both} < {minimum}")
    if failures:
        raise RuntimeError(
            "Phase 2A refuses to freeze a weak two-provider baseline: "
            + "; ".join(failures)
        )


def offense_forward(rec, fp_weight):
    forward = rec.get("forward") or {}
    fp = finite(forward.get("fantasypros_points"))
    sleeper = finite(forward.get("sleeper_points"))

    if fp is not None and sleeper is not None:
        return fp_weight * fp + (1.0 - fp_weight) * sleeper
    if fp is not None:
        return fp
    if sleeper is not None:
        return sleeper
    return None


def scenario_forward(rec, fp_weight):
    if rec.get("pos") in OFFENSE:
        return offense_forward(rec, fp_weight)
    return finite((rec.get("forward") or {}).get("projection"))


def candidate_final_value(key, raw_pm, cfg, snapshot_values):
    info = cfg["player_db"][key]
    pos = info["pos"]
    role = info["role"]
    age = info["age"]

    effective_pm, raw_effective_input = snapshot_values.production_multiplier(
        key,
        role,
        {key: raw_pm},
        cfg["no_real_history"],
        cfg["role_mult"],
    )
    age_mult = snapshot_values.effective_age_multiplier(
        pos,
        age,
        role,
        key,
        effective_pm,
        raw_effective_input,
        cfg,
    )
    pw = cfg["position_weight"].get(pos, 1.0)
    value = math.floor(
        100 * pw * age_mult * effective_pm * GLOBAL_VALUE_SCALE + 0.5
    )
    return {
        "value": value,
        "effective_prod_mult": effective_pm,
        "age_mult": age_mult,
    }


def compute_scenario(players, cfg, snapshot_values, fp_weight, history_weight):
    interim = {}
    for key, rec in players.items():
        pos = rec.get("pos")
        if pos not in TRACKED_POSITIONS:
            continue

        history = finite((rec.get("history") or {}).get("history_component"))
        forward = scenario_forward(rec, fp_weight)
        combined = None
        if history is not None and forward is not None:
            combined = history_weight * history + (1.0 - history_weight) * forward

        interim[key] = {
            "key": key,
            "pos": pos,
            "history": history,
            "forward": forward,
            "combined": combined,
        }

    baselines = {}
    for pos in TRACKED_POSITIONS:
        cohort = [
            r for r in interim.values()
            if r["pos"] == pos and r["combined"] is not None
        ]
        cohort.sort(key=lambda r: (-r["combined"], r["key"]))
        rank = REPLACEMENT_RANK[pos]
        if len(cohort) < rank:
            raise RuntimeError(
                f"scenario fp={fp_weight:.2f}, history={history_weight:.2f}: "
                f"{pos} only has {len(cohort)} complete rows for rank {rank}"
            )
        anchor = cohort[rank - 1]
        baseline = float(anchor["combined"])
        if baseline <= 0:
            raise RuntimeError(f"{pos} scenario baseline is non-positive")
        baselines[pos] = {
            "rank": rank,
            "player": anchor["key"],
            "combined_points": baseline,
            "cohort_size": len(cohort),
        }

    out = {}
    for key, rec in interim.items():
        if rec["combined"] is None:
            out[key] = None
            continue
        baseline = baselines[rec["pos"]]["combined_points"]
        ratio = rec["combined"] / baseline
        raw_pm = clamp(
            PM_INTERCEPT + PM_RATIO_SLOPE * ratio,
            PM_MIN,
            PM_MAX,
        )
        final = candidate_final_value(key, raw_pm, cfg, snapshot_values)
        final.update({
            "combined_points": rec["combined"],
            "forward_points": rec["forward"],
            "history_points": rec["history"],
            "raw_prod_mult": raw_pm,
            "ratio_to_baseline": ratio,
        })
        out[key] = final

    return out, baselines


def compare_scenarios(reference, candidate, phase1_players):
    by_pos = {}
    overall_deltas = []

    for pos in TRACKED_POSITIONS:
        keys = [
            key for key, ref in reference.items()
            if ref is not None
            and candidate.get(key) is not None
            and phase1_players[key].get("pos") == pos
        ]
        ref_values = [reference[k]["value"] for k in keys]
        cand_values = [candidate[k]["value"] for k in keys]

        pct_deltas = []
        abs_pct = []
        for key in keys:
            ref_v = reference[key]["value"]
            cand_v = candidate[key]["value"]
            pct = (cand_v - ref_v) / ref_v if ref_v else None
            if pct is not None:
                pct_deltas.append(pct)
                abs_pct.append(abs(pct))
                overall_deltas.append(abs(pct))

        by_pos[pos] = {
            "n": len(keys),
            "spearman_vs_reference": spearman(ref_values, cand_values),
            "median_change_pct": statistics.median(pct_deltas) if pct_deltas else None,
            "median_abs_change_pct": statistics.median(abs_pct) if abs_pct else None,
            "p90_abs_change_pct": percentile(abs_pct, 0.90),
            "p95_abs_change_pct": percentile(abs_pct, 0.95),
            "max_abs_change_pct": max(abs_pct) if abs_pct else None,
        }

    return {
        "overall_median_abs_change_pct": (
            statistics.median(overall_deltas) if overall_deltas else None
        ),
        "overall_p95_abs_change_pct": percentile(overall_deltas, 0.95),
        "by_position": by_pos,
    }


def scenario_key(fp_weight, history_weight):
    return f"fp_{fp_weight:.2f}__history_{history_weight:.2f}"


def build_result():
    phase1 = read_json(PHASE1)
    validate_phase1(phase1)

    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)

    phase1_players = phase1.get("players")
    if not isinstance(phase1_players, dict):
        raise RuntimeError("Phase 1 JSON missing players object")

    # Freeze the exact pre-season evidence per current calculator player.
    frozen_players = {}
    provider_disagreement = {p: [] for p in ("QB", "RB", "WR", "TE")}

    for key in sorted(phase1_players):
        rec = phase1_players[key]
        pos = rec.get("pos")
        if pos not in TRACKED_POSITIONS:
            continue
        history = finite((rec.get("history") or {}).get("history_component"))
        forward = rec.get("forward") or {}
        fp = finite(forward.get("fantasypros_points"))
        sleeper = finite(forward.get("sleeper_points"))

        frozen_players[key] = {
            "pos": pos,
            "age": rec.get("age"),
            "role": rec.get("role"),
            "sleeper_id": rec.get("sleeper_id"),
            "history_component_2025": history,
            "history_note": (rec.get("history") or {}).get("shrinkage_note"),
            "fantasypros_2026_points": fp,
            "sleeper_2026_points": sleeper,
            "canonical_forward_2026_points": finite(forward.get("projection")),
            "forward_source": forward.get("source"),
            "current_fundamental_value": (
                (rec.get("current") or {}).get("fundamental_value")
            ),
        }

        if pos in OFFENSE and fp is not None and sleeper is not None:
            mean = (abs(fp) + abs(sleeper)) / 2.0
            rel = abs(fp - sleeper) / mean if mean > 0 else None
            if rel is not None:
                provider_disagreement[pos].append(rel)

    disagreement_summary = {}
    for pos, values in provider_disagreement.items():
        disagreement_summary[pos] = {
            "n": len(values),
            "median_absolute_relative_difference": (
                statistics.median(values) if values else None
            ),
            "p90_absolute_relative_difference": percentile(values, 0.90),
            "p95_absolute_relative_difference": percentile(values, 0.95),
            "max_absolute_relative_difference": max(values) if values else None,
        }

    # Reference must reconstruct Phase 1 exactly.
    reference, reference_baselines = compute_scenario(
        phase1_players,
        cfg,
        snapshot_values,
        REFERENCE_FP_WEIGHT,
        REFERENCE_HISTORY_WEIGHT,
    )

    reproduction_deltas = []
    mismatches = []
    for key, rec in phase1_players.items():
        p1_candidate = rec.get("candidate")
        ref = reference.get(key)
        if p1_candidate is None and ref is None:
            continue
        if p1_candidate is None or ref is None:
            mismatches.append(key)
            continue
        delta = int(ref["value"]) - int(p1_candidate["value"])
        reproduction_deltas.append(abs(delta))
        if delta != 0:
            mismatches.append(key)

    if mismatches:
        raise RuntimeError(
            "Phase 2A reference scenario does not exactly reproduce Phase 1; "
            f"sample mismatches={mismatches[:10]}"
        )

    sensitivity = {}
    for fp_weight in FP_WEIGHT_GRID:
        for history_weight in HISTORY_WEIGHT_GRID:
            key = scenario_key(fp_weight, history_weight)
            scenario, baselines = compute_scenario(
                phase1_players,
                cfg,
                snapshot_values,
                fp_weight,
                history_weight,
            )
            sensitivity[key] = {
                "fp_weight": fp_weight,
                "sleeper_weight_when_both": 1.0 - fp_weight,
                "history_weight": history_weight,
                "forward_weight": 1.0 - history_weight,
                "comparison_vs_reference": compare_scenarios(
                    reference,
                    scenario,
                    phase1_players,
                ),
                "baselines": baselines,
            }

    result = {
        "schema_version": 1,
        "phase": "Production V2 Phase 2A",
        "status": "FROZEN_PRESEASON_BASELINE_RESEARCH_ONLY",
        "production_mutation_authorized": False,
        "calibration_claim_authorized": False,
        "reason_no_retrospective_calibration": (
            "Repository has no temporally-valid 2025 FantasyPros/Sleeper "
            "preseason projection snapshots. Sensitivity is measurable now; "
            "optimal weights require future realized 2026 outcomes."
        ),
        "immutability_policy": (
            "Once written, this file may only be reproduced byte-for-byte from "
            "the same inputs. Changed inputs must never overwrite the frozen "
            "preseason baseline."
        ),
        "reference_scenario": {
            "fantasypros_weight": REFERENCE_FP_WEIGHT,
            "sleeper_weight_when_both": 1.0 - REFERENCE_FP_WEIGHT,
            "history_weight": REFERENCE_HISTORY_WEIGHT,
            "forward_weight": 1.0 - REFERENCE_HISTORY_WEIGHT,
            "phase1_exact_reproduction": len(mismatches) == 0,
            "max_final_value_reproduction_delta": max(reproduction_deltas, default=0),
            "baselines": reference_baselines,
        },
        "sensitivity_grids": {
            "fantasypros_weight": list(FP_WEIGHT_GRID),
            "history_weight": list(HISTORY_WEIGHT_GRID),
            "interpretation": "blast-radius sensitivity only; not optimization",
        },
        "provider_disagreement_by_position": disagreement_summary,
        "sensitivity": sensitivity,
        "input_sha256": {
            str(PHASE1.relative_to(REPO_ROOT)): sha256(PHASE1),
            str(INDEX_HTML.relative_to(REPO_ROOT)): sha256(INDEX_HTML),
            str(FP_NORMALIZED.relative_to(REPO_ROOT)): sha256(FP_NORMALIZED),
            str(SLEEPER_TOTALS.relative_to(REPO_ROOT)): sha256(SLEEPER_TOTALS),
            str(IDENTITY.relative_to(REPO_ROOT)): sha256(IDENTITY),
        },
        "frozen_players": frozen_players,
    }
    return round_numbers(result)


def pct(value):
    return "—" if value is None else f"{100.0 * value:.1f}%"


def render_md(result):
    lines = [
        "# Production V2 — Phase 2A Preseason Baseline",
        "",
        "## Decision",
        "",
        "**FROZEN RESEARCH BASELINE — no production change and no optimal-weight claim is authorized.**",
        "",
        result["reason_no_retrospective_calibration"],
        "",
        "This snapshot exists so 2026 results can later be scored against information that was genuinely available before the season.",
        "",
        "## Reference integrity",
        "",
        f"- Phase-1 exact reproduction: **{'Yes' if result['reference_scenario']['phase1_exact_reproduction'] else 'No'}**",
        f"- Maximum final-value reproduction delta: **{result['reference_scenario']['max_final_value_reproduction_delta']}**",
        "- Reference provider blend: **50% FantasyPros / 50% Sleeper when both exist**",
        "- Reference history/forward: **45% / 55%**",
        "",
        "## Current provider disagreement — offense",
        "",
        "| Pos | Both-provider N | Median abs disagreement | P90 | P95 | Max |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for pos in ("QB", "RB", "WR", "TE"):
        row = result["provider_disagreement_by_position"][pos]
        lines.append(
            f"| {pos} | {row['n']} | "
            f"{pct(row['median_absolute_relative_difference'])} | "
            f"{pct(row['p90_absolute_relative_difference'])} | "
            f"{pct(row['p95_absolute_relative_difference'])} | "
            f"{pct(row['max_absolute_relative_difference'])} |"
        )

    lines += [
        "",
        "## Sensitivity grid",
        "",
        "Each row changes only the displayed provider/history weights relative to the Phase-1 reference. These are **not calibrated recommendations**.",
        "",
        "| FP weight | History weight | Median abs FV move | P95 abs FV move |",
        "|---:|---:|---:|---:|",
    ]

    for fp_weight in FP_WEIGHT_GRID:
        for history_weight in HISTORY_WEIGHT_GRID:
            key = scenario_key(fp_weight, history_weight)
            comp = result["sensitivity"][key]["comparison_vs_reference"]
            lines.append(
                f"| {fp_weight:.0%} | {history_weight:.0%} | "
                f"{pct(comp['overall_median_abs_change_pct'])} | "
                f"{pct(comp['overall_p95_abs_change_pct'])} |"
            )

    lines += [
        "",
        "## What this does NOT prove",
        "",
        "- It does not identify the best FantasyPros/Sleeper blend.",
        "- It does not identify the best history/forward weight.",
        "- It does not authorize changing `PROD_MULT`.",
        "- It does not use future information or market value to train Fundamental Value.",
        "",
        "## Prospective Phase 2B",
        "",
        "After real 2026 games exist, score the frozen preseason provider projections and later pre-week snapshots against realized league-scored production. Only then may provider/history weights be estimated from out-of-sample evidence.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def canonical_json(result):
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


def write_immutable(path: Path, content: str):
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing != content:
            try:
                display_path = path.relative_to(REPO_ROOT)
            except ValueError:
                display_path = path
            raise RuntimeError(
                f"IMMUTABLE BASELINE REFUSAL: {display_path} "
                "already exists and current inputs would change it. Do not "
                "overwrite a preseason baseline."
            )
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def run_selftest():
    assert offense_forward(
        {"forward": {"fantasypros_points": 120, "sleeper_points": 100}},
        0.50,
    ) == 110
    assert offense_forward(
        {"forward": {"fantasypros_points": 120, "sleeper_points": None}},
        0.00,
    ) == 120
    assert offense_forward(
        {"forward": {"fantasypros_points": None, "sleeper_points": 100}},
        1.00,
    ) == 100
    assert offense_forward(
        {"forward": {"fantasypros_points": None, "sleeper_points": None}},
        0.50,
    ) is None

    assert scenario_key(0.5, 0.45) == "fp_0.50__history_0.45"
    assert percentile([1, 2, 3, 4, 5], 0.5) == 3
    assert abs(spearman([1, 2, 3], [1, 2, 3]) - 1.0) < 1e-12

    # Immutability primitive: same bytes are okay, changed bytes fail.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.txt"
        assert write_immutable(p, "abc\n") is True
        assert write_immutable(p, "abc\n") is False
        try:
            write_immutable(p, "changed\n")
            raise AssertionError("expected immutable overwrite refusal")
        except RuntimeError as exc:
            assert "IMMUTABLE BASELINE REFUSAL" in str(exc)

    print("PASS Production V2 Phase-2A standalone self-test.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    if not args.write and not args.check:
        parser.error("choose --write or --check")

    result = build_result()
    json_text = canonical_json(result)
    md_text = render_md(result)

    if args.write:
        wrote_json = write_immutable(OUTPUT_JSON, json_text)
        wrote_md = write_immutable(OUTPUT_MD, md_text)
        print(
            "Phase 2A baseline "
            + ("created." if wrote_json or wrote_md else "already exists identically.")
        )
        print(OUTPUT_JSON.relative_to(REPO_ROOT))
        print(OUTPUT_MD.relative_to(REPO_ROOT))
        return

    # --check
    if not OUTPUT_JSON.exists() or not OUTPUT_MD.exists():
        raise RuntimeError("Phase 2A baseline outputs do not exist; run --write first")
    if OUTPUT_JSON.read_text(encoding="utf-8") != json_text:
        raise RuntimeError(
            "Frozen Phase 2A JSON no longer reproduces from current inputs. "
            "This is expected if inputs changed; do NOT overwrite the baseline."
        )
    if OUTPUT_MD.read_text(encoding="utf-8") != md_text:
        raise RuntimeError("Frozen Phase 2A Markdown does not reproduce exactly")
    print("PASS Phase 2A immutable baseline check.")


if __name__ == "__main__":
    main()
