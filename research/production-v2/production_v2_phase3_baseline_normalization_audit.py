#!/usr/bin/env python3
"""
Production V2 Phase 3 — replacement-baseline normalization audit.

PURPOSE
-------
Phase 1 established a transparent benchmark reconstruction.
Phase 2A froze the 2026 preseason provider/history evidence because no
temporally-valid 2025 provider snapshots exist.

Phase 3 isolates ONE remaining structural question that can be tested now:

    How much of PROD_MULT's shape is caused by the position-specific
    replacement denominator, and what happens if we carry forward the
    independently backtested replacement-rank winners?

NO provider weight changes.
NO history/forward weight changes.
NO transform changes.
NO position-weight changes.
NO production mutation.

REFERENCE (documented Phase-1 ranks)
------------------------------------
QB18 RB32 WR36 TE15 DL32 LB32 DB32

EVIDENCE-HYBRID RANKS
---------------------
These are the position-by-position Test-3 winners from the existing
future-production baseline backtester:
QB18  -- no competing candidate tested; retain documented
RB26  -- roster_economics_informed won all 15 4-week folds
WR34  -- roster_economics_informed won all 15 4-week folds
TE15  -- documented won primary Test 3 (tie-equivalent rank 15)
DL23  -- legacy_empirical won all 15 4-week folds
LB32  -- no competing candidate tested; retain documented
DB30  -- legacy_empirical won all 15 4-week folds

Important scope limitation inherited from that backtester:
it used trailing PPG as the training numerator because historical provider
snapshots did not exist. Therefore this is evidence for the denominator
choice, not proof that the final V2 formula is optimal.

INPUTS
------
- research/production-v2/production_v2_phase1_audit.json
- research/production-v2/production_v2_phase2_preseason_baseline.json
- research/baseline-backtester/baseline_backtest_results.json
- research/baseline-backtester/baseline_backtest_report.md
- research/baseline-backtester/baseline_backtester.py
- index.html

OUTPUTS
-------
- research/production-v2/production_v2_phase3_baseline_normalization_audit.json
- research/production-v2/production_v2_phase3_baseline_normalization_audit.md

USAGE
-----
python3 research/production-v2/production_v2_phase3_baseline_normalization_audit.py --selftest
python3 research/production-v2/production_v2_phase3_baseline_normalization_audit.py --write
python3 research/production-v2/production_v2_phase3_baseline_normalization_audit.py --check
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

PHASE1_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase1_audit.json"
PHASE2_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase2_preseason_baseline.json"
BACKTEST_JSON = REPO_ROOT / "research" / "baseline-backtester" / "baseline_backtest_results.json"
BACKTEST_MD = REPO_ROOT / "research" / "baseline-backtester" / "baseline_backtest_report.md"
BACKTEST_PY = REPO_ROOT / "research" / "baseline-backtester" / "baseline_backtester.py"
INDEX_HTML = REPO_ROOT / "index.html"

OUTPUT_JSON = REPO_ROOT / "research" / "production-v2" / "production_v2_phase3_baseline_normalization_audit.json"
OUTPUT_MD = REPO_ROOT / "research" / "production-v2" / "production_v2_phase3_baseline_normalization_audit.md"

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")

DOCUMENTED_RANKS = {
    "QB": 18,
    "RB": 32,
    "WR": 36,
    "TE": 15,
    "DL": 32,
    "LB": 32,
    "DB": 32,
}

EVIDENCE_HYBRID_RANKS = {
    "QB": 18,
    "RB": 26,
    "WR": 34,
    "TE": 15,
    "DL": 23,
    "LB": 32,
    "DB": 30,
}

# Existing baseline-backtester Test-3 primary (4-week) evidence, copied
# explicitly so this audit is transparent about why each rank exists.
# "not_tested" means all named candidate sets used the same rank.
BACKTEST_EVIDENCE = {
    "QB": {
        "decision": "retain_documented_no_competing_candidate",
        "documented_rank": 18,
        "evidence_rank": 18,
        "documented_mae_4w": None,
        "evidence_mae_4w": None,
        "folds_won_4w": None,
    },
    "RB": {
        "decision": "roster_economics_informed",
        "documented_rank": 32,
        "evidence_rank": 26,
        "documented_mae_4w": 0.2774,
        "evidence_mae_4w": 0.2391,
        "folds_won_4w": 15,
    },
    "WR": {
        "decision": "roster_economics_informed",
        "documented_rank": 36,
        "evidence_rank": 34,
        "documented_mae_4w": 0.2485,
        "evidence_mae_4w": 0.2443,
        "folds_won_4w": 15,
    },
    "TE": {
        "decision": "documented",
        "documented_rank": 15,
        "evidence_rank": 15,
        "documented_mae_4w": 0.2213,
        "evidence_mae_4w": 0.2213,
        "folds_won_4w": 10,
    },
    "DL": {
        "decision": "legacy_empirical",
        "documented_rank": 32,
        "evidence_rank": 23,
        "documented_mae_4w": 0.2551,
        "evidence_mae_4w": 0.2280,
        "folds_won_4w": 15,
    },
    "LB": {
        "decision": "retain_documented_no_competing_candidate",
        "documented_rank": 32,
        "evidence_rank": 32,
        "documented_mae_4w": None,
        "evidence_mae_4w": None,
        "folds_won_4w": None,
    },
    "DB": {
        "decision": "legacy_empirical",
        "documented_rank": 32,
        "evidence_rank": 30,
        "documented_mae_4w": 0.2228,
        "evidence_mae_4w": 0.2219,
        "folds_won_4w": 15,
    },
}

PM_INTERCEPT = -0.10
PM_RATIO_SLOPE = 0.75
PM_MIN = 0.15
PM_MAX = 1.55
GLOBAL_VALUE_SCALE = 55.0


def read_json(path: Path):
    if not path.exists():
        raise RuntimeError(f"missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def summarize(values):
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not vals:
        return {"n": 0}
    abs_vals = [abs(v) for v in vals]
    return {
        "n": len(vals),
        "median": statistics.median(vals),
        "median_abs": statistics.median(abs_vals),
        "p90_abs": percentile(abs_vals, 0.90),
        "p95_abs": percentile(abs_vals, 0.95),
        "max_abs": max(abs_vals),
        "min": min(vals),
        "max": max(vals),
    }


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


def validate_inputs(phase1, phase2):
    if phase1.get("production_mutation_authorized") is not False:
        raise RuntimeError("Phase 1 is not marked research-only")
    if phase2.get("production_mutation_authorized") is not False:
        raise RuntimeError("Phase 2A is not marked research-only")
    if phase2.get("calibration_claim_authorized") is not False:
        raise RuntimeError("Phase 2A unexpectedly authorizes a calibration claim")

    p1_ranks = (
        (phase1.get("benchmark_assumptions") or {}).get("replacement_rank") or {}
    )
    if {k: int(v) for k, v in p1_ranks.items()} != DOCUMENTED_RANKS:
        raise RuntimeError(
            f"Phase-1 replacement ranks changed unexpectedly: {p1_ranks}"
        )

    ref = phase2.get("reference_scenario") or {}
    if not ref.get("phase1_exact_reproduction"):
        raise RuntimeError("Phase 2A did not exactly reproduce Phase 1")
    if int(ref.get("max_final_value_reproduction_delta") or 0) != 0:
        raise RuntimeError("Phase 2A reference reproduction delta is nonzero")

    for pos in TRACKED_POSITIONS:
        evidence = BACKTEST_EVIDENCE[pos]
        if evidence["documented_rank"] != DOCUMENTED_RANKS[pos]:
            raise RuntimeError(f"{pos}: embedded backtest documented rank mismatch")
        if evidence["evidence_rank"] != EVIDENCE_HYBRID_RANKS[pos]:
            raise RuntimeError(f"{pos}: embedded evidence-hybrid rank mismatch")


def candidate_final_value(key, raw_pm, cfg, snapshot_values):
    info = cfg["player_db"][key]
    pos = info["pos"]
    role = info["role"]
    age = info["age"]

    effective_pm, raw_pm_returned = snapshot_values.production_multiplier(
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
        raw_pm_returned,
        cfg,
    )
    pw = cfg["position_weight"].get(pos, 1.0)
    value = math.floor(
        100 * pw * age_mult * effective_pm * GLOBAL_VALUE_SCALE + 0.5
    )
    return {
        "raw_prod_mult": raw_pm,
        "effective_prod_mult": effective_pm,
        "age_mult": age_mult,
        "position_weight": pw,
        "pre_age_economic_factor": pw * effective_pm,
        "fundamental_value": value,
    }


def scenario_for_ranks(phase1_players, ranks, cfg, snapshot_values):
    baselines = {}
    for pos in TRACKED_POSITIONS:
        cohort = [
            rec for rec in phase1_players.values()
            if rec.get("pos") == pos
            and rec.get("phase1_combined_points") is not None
        ]
        cohort.sort(
            key=lambda r: (-float(r["phase1_combined_points"]), r["key"])
        )
        rank = ranks[pos]
        if len(cohort) < rank:
            raise RuntimeError(
                f"{pos}: only {len(cohort)} complete rows for baseline rank {rank}"
            )
        anchor = cohort[rank - 1]
        points = float(anchor["phase1_combined_points"])
        if points <= 0:
            raise RuntimeError(f"{pos}: non-positive baseline points {points}")
        baselines[pos] = {
            "rank": rank,
            "player": anchor["key"],
            "combined_points": points,
            "cohort_size": len(cohort),
            "rank_depth_share": rank / len(cohort),
        }

    players = {}
    for key, rec in phase1_players.items():
        combined = rec.get("phase1_combined_points")
        if combined is None:
            players[key] = None
            continue
        pos = rec["pos"]
        baseline = baselines[pos]["combined_points"]
        ratio = float(combined) / baseline
        raw_pm = clamp(
            PM_INTERCEPT + PM_RATIO_SLOPE * ratio,
            PM_MIN,
            PM_MAX,
        )
        row = candidate_final_value(key, raw_pm, cfg, snapshot_values)
        row.update({
            "ratio_to_baseline": ratio,
            "baseline_points": baseline,
            "baseline_rank": ranks[pos],
            "raw_floor_hit": abs(raw_pm - PM_MIN) < 1e-12,
            "raw_ceiling_hit": abs(raw_pm - PM_MAX) < 1e-12,
        })
        players[key] = row

    return players, baselines


def position_distribution(phase1_players, scenario_players, pos):
    rows = [
        (key, scenario_players[key])
        for key, rec in phase1_players.items()
        if rec.get("pos") == pos and scenario_players.get(key) is not None
    ]
    pms = [row["effective_prod_mult"] for _, row in rows]
    pre_age = [row["pre_age_economic_factor"] for _, row in rows]
    floors = sum(1 for _, row in rows if row["raw_floor_hit"])
    ceilings = sum(1 for _, row in rows if row["raw_ceiling_hit"])
    return {
        "n": len(rows),
        "median_effective_prod_mult": statistics.median(pms) if pms else None,
        "median_pre_age_economic_factor": statistics.median(pre_age) if pre_age else None,
        "raw_floor_share": floors / len(rows) if rows else None,
        "raw_ceiling_share": ceilings / len(rows) if rows else None,
    }


def build_result():
    phase1 = read_json(PHASE1_PATH)
    phase2 = read_json(PHASE2_PATH)
    # Read these for integrity/provenance even though the winner constants are
    # embedded above. If a file is missing, this audit must not run.
    read_json(BACKTEST_JSON)
    if not BACKTEST_MD.exists() or not BACKTEST_PY.exists():
        raise RuntimeError("baseline-backtester provenance files are missing")

    validate_inputs(phase1, phase2)

    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)
    phase1_players = phase1.get("players")
    if not isinstance(phase1_players, dict):
        raise RuntimeError("Phase 1 JSON missing players object")

    documented_players, documented_baselines = scenario_for_ranks(
        phase1_players,
        DOCUMENTED_RANKS,
        cfg,
        snapshot_values,
    )
    hybrid_players, hybrid_baselines = scenario_for_ranks(
        phase1_players,
        EVIDENCE_HYBRID_RANKS,
        cfg,
        snapshot_values,
    )

    # Critical isolation gate: our documented-rank reconstruction must exactly
    # equal Phase 1. Otherwise this script is changing more than the denominator.
    mismatches = []
    max_delta = 0
    for key, rec in phase1_players.items():
        p1 = rec.get("candidate")
        doc = documented_players.get(key)
        if p1 is None and doc is None:
            continue
        if p1 is None or doc is None:
            mismatches.append(key)
            continue
        delta = int(doc["fundamental_value"]) - int(p1["value"])
        max_delta = max(max_delta, abs(delta))
        if delta != 0:
            mismatches.append(key)
    if mismatches:
        raise RuntimeError(
            "Documented-rank scenario does not exactly reproduce Phase 1; "
            f"sample={mismatches[:10]}"
        )

    by_position = {}
    movers = []

    for pos in TRACKED_POSITIONS:
        doc_dist = position_distribution(phase1_players, documented_players, pos)
        hybrid_dist = position_distribution(phase1_players, hybrid_players, pos)

        pct_changes = []
        pm_changes = []
        factor_changes = []
        pos_rows = []

        for key, rec in phase1_players.items():
            if rec.get("pos") != pos:
                continue
            doc = documented_players.get(key)
            hyb = hybrid_players.get(key)
            if doc is None or hyb is None:
                continue

            doc_value = doc["fundamental_value"]
            hyb_value = hyb["fundamental_value"]
            pct = (hyb_value - doc_value) / doc_value if doc_value else None
            pm_delta = hyb["effective_prod_mult"] - doc["effective_prod_mult"]
            factor_delta = (
                hyb["pre_age_economic_factor"] - doc["pre_age_economic_factor"]
            )

            if pct is not None:
                pct_changes.append(pct)
            pm_changes.append(pm_delta)
            factor_changes.append(factor_delta)

            row = {
                "player": key,
                "pos": pos,
                "documented_value": doc_value,
                "evidence_hybrid_value": hyb_value,
                "fundamental_value_change_pct": pct,
                "documented_effective_pm": doc["effective_prod_mult"],
                "evidence_hybrid_effective_pm": hyb["effective_prod_mult"],
                "effective_pm_delta": pm_delta,
                "documented_raw_pm": doc["raw_prod_mult"],
                "evidence_hybrid_raw_pm": hyb["raw_prod_mult"],
                "current_position_weight": doc["position_weight"],
            }
            pos_rows.append(row)
            if pct is not None:
                movers.append(row)

        by_position[pos] = {
            "backtest_evidence": BACKTEST_EVIDENCE[pos],
            "current_position_weight_held_fixed": cfg["position_weight"].get(pos, 1.0),
            "documented_baseline": documented_baselines[pos],
            "evidence_hybrid_baseline": hybrid_baselines[pos],
            "documented_distribution": doc_dist,
            "evidence_hybrid_distribution": hybrid_dist,
            "hybrid_minus_documented": {
                "fundamental_value_change_pct": summarize(pct_changes),
                "effective_prod_mult_delta": summarize(pm_changes),
                "pre_age_economic_factor_delta": summarize(factor_changes),
            },
        }

    movers.sort(
        key=lambda row: (
            -abs(row["fundamental_value_change_pct"] or 0.0),
            row["player"],
        )
    )

    changed_positions = [
        pos for pos in TRACKED_POSITIONS
        if DOCUMENTED_RANKS[pos] != EVIDENCE_HYBRID_RANKS[pos]
    ]

    # Structural-overlap diagnostic:
    # A deeper replacement rank lowers the denominator and raises PM across the
    # position. POSITION_WEIGHT is a second explicit position-level multiplier.
    # This does NOT prove double counting; it quantifies how much position-level
    # leverage exists in both layers simultaneously.
    overlap = {}
    for pos in TRACKED_POSITIONS:
        doc = documented_baselines[pos]
        hyb = hybrid_baselines[pos]
        overlap[pos] = {
            "position_weight": cfg["position_weight"].get(pos, 1.0),
            "documented_rank_depth_share": doc["rank_depth_share"],
            "evidence_hybrid_rank_depth_share": hyb["rank_depth_share"],
            "rank_depth_change": (
                hyb["rank_depth_share"] - doc["rank_depth_share"]
            ),
            "baseline_points_change_pct": (
                (hyb["combined_points"] - doc["combined_points"])
                / doc["combined_points"]
            ),
            "interpretation": (
                "position-level denominator changed while POSITION_WEIGHT stayed fixed"
                if pos in changed_positions
                else "denominator unchanged"
            ),
        }

    result = {
        "schema_version": 1,
        "phase": "Production V2 Phase 3",
        "status": "RESEARCH_ONLY_BASELINE_NORMALIZATION_AUDIT",
        "production_mutation_authorized": False,
        "calibration_claim_authorized": False,
        "decision": "CARRY_EVIDENCE_HYBRID_FORWARD_AS_V2_NORMALIZATION_CANDIDATE_NOT_DEPLOYED",
        "why_not_deploy": (
            "The replacement-rank evidence is temporally valid, but the provider "
            "blend and history-vs-forward weights remain prospectively uncalibrated. "
            "Phase 3 isolates denominator behavior only."
        ),
        "documented_ranks": DOCUMENTED_RANKS,
        "evidence_hybrid_ranks": EVIDENCE_HYBRID_RANKS,
        "changed_positions": changed_positions,
        "isolation_gate": {
            "documented_scenario_exactly_reproduces_phase1": True,
            "max_final_value_delta_vs_phase1": max_delta,
        },
        "position_weight_policy": {
            "held_fixed": True,
            "values": cfg["position_weight"],
            "double_counting_conclusion": (
                "NOT PROVEN. This audit quantifies overlap risk: replacement rank "
                "and POSITION_WEIGHT are both position-level levers. Future V2 "
                "should treat production normalization and positional economics as "
                "separate calibration layers."
            ),
        },
        "by_position": by_position,
        "structural_overlap_diagnostic": overlap,
        "largest_absolute_value_movers": movers[:50],
        "input_sha256": {
            str(PHASE1_PATH.relative_to(REPO_ROOT)): sha256(PHASE1_PATH),
            str(PHASE2_PATH.relative_to(REPO_ROOT)): sha256(PHASE2_PATH),
            str(BACKTEST_JSON.relative_to(REPO_ROOT)): sha256(BACKTEST_JSON),
            str(BACKTEST_MD.relative_to(REPO_ROOT)): sha256(BACKTEST_MD),
            str(BACKTEST_PY.relative_to(REPO_ROOT)): sha256(BACKTEST_PY),
            str(INDEX_HTML.relative_to(REPO_ROOT)): sha256(INDEX_HTML),
        },
        "known_scope_limitation": (
            "The baseline backtester used trailing PPG as its training numerator "
            "because historical provider projections did not exist. Therefore the "
            "evidence-hybrid ranks are the best existing denominator evidence, but "
            "not a full historical replay of the eventual V2 blended numerator."
        ),
    }
    return round_numbers(result)


def pct(value):
    return "—" if value is None else f"{100.0 * float(value):.1f}%"


def signed_pct(value):
    if value is None:
        return "—"
    return f"{100.0 * float(value):+.1f}%"


def render_md(result):
    lines = [
        "# Production V2 — Phase 3 Baseline Normalization Audit",
        "",
        "## Decision",
        "",
        "**Carry the evidence-hybrid replacement ranks forward as a V2 normalization candidate; do not deploy them yet.**",
        "",
        "This audit changed only the replacement denominator. Provider blend, history/forward weighting, transform, age, role floors, position weights, and global value scale were all held fixed.",
        "",
        f"- Documented scenario reproduced Phase 1 exactly: **{'Yes' if result['isolation_gate']['documented_scenario_exactly_reproduces_phase1'] else 'No'}**",
        f"- Maximum reproduction delta: **{result['isolation_gate']['max_final_value_delta_vs_phase1']}**",
        "- Production files mutated: **0**",
        "",
        "## Replacement-rank evidence",
        "",
        "| Pos | Documented | Evidence hybrid | Test-3 source | Doc MAE | Evidence MAE | 4wk folds won |",
        "|---|---:|---:|---|---:|---:|---:|",
    ]

    for pos in TRACKED_POSITIONS:
        e = result["by_position"][pos]["backtest_evidence"]
        doc_mae = "—" if e["documented_mae_4w"] is None else f"{e['documented_mae_4w']:.4f}"
        ev_mae = "—" if e["evidence_mae_4w"] is None else f"{e['evidence_mae_4w']:.4f}"
        folds = "—" if e["folds_won_4w"] is None else str(e["folds_won_4w"])
        lines.append(
            f"| {pos} | {e['documented_rank']} | {e['evidence_rank']} | "
            f"{e['decision']} | {doc_mae} | {ev_mae} | {folds} |"
        )

    lines += [
        "",
        "## 2026 Phase-1 blast radius from changing only the denominator",
        "",
        "| Pos | PW fixed | Doc anchor | Hybrid anchor | Baseline pts Δ | Median FV Δ | P95 abs FV Δ | Median PM Δ |",
        "|---|---:|---|---|---:|---:|---:|---:|",
    ]

    for pos in TRACKED_POSITIONS:
        row = result["by_position"][pos]
        doc = row["documented_baseline"]
        hyb = row["evidence_hybrid_baseline"]
        delta = row["hybrid_minus_documented"]
        lines.append(
            f"| {pos} | {row['current_position_weight_held_fixed']:.2f} | "
            f"{doc['rank']} {doc['player']} | {hyb['rank']} {hyb['player']} | "
            f"{signed_pct(result['structural_overlap_diagnostic'][pos]['baseline_points_change_pct'])} | "
            f"{signed_pct(delta['fundamental_value_change_pct'].get('median'))} | "
            f"{pct(delta['fundamental_value_change_pct'].get('p95_abs'))} | "
            f"{delta['effective_prod_mult_delta'].get('median', 0):+.4f} |"
        )

    lines += [
        "",
        "## Structural scarcity-overlap interpretation",
        "",
        "A deeper replacement rank lowers the denominator and increases `PROD_MULT` across that position. `POSITION_WEIGHT` is a separate explicit position-level multiplier. Therefore both layers can create position-level leverage.",
        "",
        "**This audit does not claim double counting is proven.** It does establish that the two mechanisms overlap structurally, so Production V2 should keep their jobs separate: production normalization should be justified by production evidence; positional economics should remain in `POSITION_WEIGHT` / roster economics.",
        "",
        "The evidence-hybrid mostly moves replacement anchors shallower (RB 32→26, WR 36→34, DL 32→23, DB 32→30), which removes some denominator-driven inflation while leaving the explicit position weights untouched.",
        "",
        "## Largest value movers from denominator-only change",
        "",
        "| Player | Pos | Documented | Hybrid | Change | PM documented→hybrid |",
        "|---|---|---:|---:|---:|---|",
    ]

    for row in result["largest_absolute_value_movers"][:25]:
        lines.append(
            f"| {row['player']} | {row['pos']} | {row['documented_value']} | "
            f"{row['evidence_hybrid_value']} | "
            f"{signed_pct(row['fundamental_value_change_pct'])} | "
            f"{row['documented_effective_pm']:.3f}→{row['evidence_hybrid_effective_pm']:.3f} |"
        )

    lines += [
        "",
        "## Why this is not a deployment",
        "",
        result["why_not_deploy"],
        "",
        "The baseline backtester itself also has a known limitation: it isolated the denominator using trailing PPG because historical provider snapshots were unavailable. Phase 2A has now fixed that problem prospectively for 2026, but realized evidence has not accumulated yet.",
        "",
        "## Next Production V2 step",
        "",
        "Carry both normalization candidates into the later prospective evaluation. In parallel, the next structural audit can test the linear `clamp(-0.10 + 0.75 × ratio, 0.15, 1.55)` transform and especially its floor/ceiling compression without changing production.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def canonical_json(result):
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


def run_selftest():
    assert DOCUMENTED_RANKS == {
        "QB": 18, "RB": 32, "WR": 36, "TE": 15, "DL": 32, "LB": 32, "DB": 32
    }
    assert EVIDENCE_HYBRID_RANKS["DL"] == 23
    assert EVIDENCE_HYBRID_RANKS["RB"] == 26
    assert EVIDENCE_HYBRID_RANKS["WR"] == 34
    assert EVIDENCE_HYBRID_RANKS["DB"] == 30
    assert EVIDENCE_HYBRID_RANKS["QB"] == DOCUMENTED_RANKS["QB"]
    assert EVIDENCE_HYBRID_RANKS["LB"] == DOCUMENTED_RANKS["LB"]

    assert clamp(-1, 0.15, 1.55) == 0.15
    assert clamp(2, 0.15, 1.55) == 1.55
    assert abs(percentile([1, 2, 3, 4, 5], 0.5) - 3) < 1e-12

    # A shallower rank in a descending cohort must have >= baseline points,
    # and therefore cannot inflate a player's ratio relative to the deeper rank.
    cohort = [300, 250, 200, 150, 100]
    shallow_baseline = cohort[1]  # rank 2
    deep_baseline = cohort[3]     # rank 4
    player = 300
    assert shallow_baseline >= deep_baseline
    assert player / shallow_baseline <= player / deep_baseline

    # Evidence provenance sanity.
    assert BACKTEST_EVIDENCE["DL"]["evidence_mae_4w"] < BACKTEST_EVIDENCE["DL"]["documented_mae_4w"]
    assert BACKTEST_EVIDENCE["RB"]["evidence_mae_4w"] < BACKTEST_EVIDENCE["RB"]["documented_mae_4w"]

    print("PASS Production V2 Phase-3 standalone self-test.")


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
        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_JSON.write_text(json_text, encoding="utf-8")
        OUTPUT_MD.write_text(md_text, encoding="utf-8")
        print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
        print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")
        return

    if not OUTPUT_JSON.exists() or not OUTPUT_MD.exists():
        raise RuntimeError("Phase-3 outputs do not exist; run --write first")
    if OUTPUT_JSON.read_text(encoding="utf-8") != json_text:
        raise RuntimeError("Phase-3 JSON does not reproduce exactly")
    if OUTPUT_MD.read_text(encoding="utf-8") != md_text:
        raise RuntimeError("Phase-3 Markdown does not reproduce exactly")
    print("PASS Phase-3 exact-output check.")


if __name__ == "__main__":
    main()
