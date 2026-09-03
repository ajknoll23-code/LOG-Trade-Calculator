#!/usr/bin/env python3
"""
Production V2 Phase 8 — consolidated shadow model.

PURPOSE
-------
Phases 1–7 established the V2 architecture that can be justified BEFORE real
2026 outcomes are available:

LOCKED ARCHITECTURE
-------------------
1. Normal candidate numerator:
   Phase-1 benchmark evidence state (45% canonical 2025 history / 55% forward;
   offense forward = 50/50 FantasyPros + Sleeper when both exist; IDP uses
   canonical IDP V1). These weights remain UNCALIBRATED and are frozen only so
   Phase 9 can score the same preseason evidence prospectively.
2. Candidate-present semantics:
   Phase-5 data-first rule. A valid V2 candidate is used directly for non-Elite
   players; ROLE_MULT is not activated by raw PM <= 0.15.
3. Elite safeguard:
   Existing 0.65 effective-PM floor remains held fixed.
4. Candidate-missing semantics:
   Phase-7 continuity. Preserve the currently deployed value for the 31 players
   without a complete normal V2 candidate; automatically exit continuity once a
   normal V2 candidate exists.
5. Current age / position-weight / global-scale architecture remains held fixed.

STILL UNCALIBRATED
------------------
A. provider blend,
B. history-vs-forward weight,
C. documented vs evidence-hybrid replacement normalization,
D. affine PM floor.

Therefore Phase 8 creates a SHADOW MODEL FAMILY, not a deployment candidate.
It produces every tracked player's value under:
- documented and evidence-hybrid replacement ranks, and
- floor sensitivity values 0.05 / 0.10 / 0.15 / 0.20.

The monitoring reference is:
    evidence-hybrid ranks + current 0.15 floor
because Phase 3 supplied prior denominator evidence while Phase 6 explicitly
refused to select a replacement floor. This is a monitoring reference only.

NO production file is mutated.
NO variant is authorized for deployment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from datetime import datetime, timezone

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
SCRIPTS = REPO_ROOT / "scripts"

PHASE1_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase1_audit.json"
PHASE2_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase2_preseason_baseline.json"
PHASE3_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase3_baseline_normalization_audit.json"
PHASE5_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase5_no_history_semantics_audit.json"
PHASE6_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase6_transform_compression_audit.json"
PHASE7_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase7_missing_candidate_fallback_audit.json"

INDEX_HTML = REPO_ROOT / "index.html"
SNAPSHOT_VALUES_PATH = SCRIPTS / "validation" / "snapshot_values.py"

OUTPUT_JSON = REPO_ROOT / "research" / "production-v2" / "production_v2_phase8_shadow_model.json"
OUTPUT_MD = REPO_ROOT / "research" / "production-v2" / "production_v2_phase8_shadow_model.md"

TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
FLOORS = (0.05, 0.10, 0.15, 0.20)
PM_INTERCEPT = -0.10
PM_RATIO_SLOPE = 0.75
PM_CEILING = 1.55
GLOBAL_VALUE_SCALE = 55.0

EXPECTED_TRACKED = 549
EXPECTED_NORMAL = 518
EXPECTED_CONTINUITY = 31

MONITORING_REFERENCE = "evidence_hybrid__floor_0.15"


def read_json(path: Path):
    if not path.exists():
        raise RuntimeError(f"missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def percentile(values, q):
    vals = sorted(float(v) for v in values)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    idx = (len(vals) - 1) * max(0.0, min(1.0, float(q)))
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
        "min": min(vals),
        "max": max(vals),
        "max_abs": max(abs_vals),
    }


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


def variant_key(rank_family, floor):
    return f"{rank_family}__floor_{floor:.2f}"


def data_first_effective_pm(role, raw_pm):
    # Accepted Phase-5 candidate-present semantics.
    if role == "Elite" and raw_pm < 0.65:
        return 0.65
    return float(raw_pm)


def build_baselines(players, ranks):
    baselines = {}
    for pos in TRACKED_POSITIONS:
        cohort = [
            rec for rec in players.values()
            if rec.get("pos") == pos and rec.get("phase1_combined_points") is not None
        ]
        cohort.sort(key=lambda r: (-float(r["phase1_combined_points"]), r["key"]))
        rank = int(ranks[pos])
        if len(cohort) < rank:
            raise RuntimeError(f"{pos}: cohort {len(cohort)} smaller than rank {rank}")
        anchor = cohort[rank - 1]
        points = float(anchor["phase1_combined_points"])
        if points <= 0:
            raise RuntimeError(f"{pos}: non-positive baseline")
        baselines[pos] = {
            "rank": rank,
            "player": anchor["key"],
            "combined_points": points,
            "cohort_size": len(cohort),
        }
    return baselines


def compute_candidate_value(key, rec, baseline_points, floor, cfg, snapshot_values):
    combined = float(rec["phase1_combined_points"])
    ratio = combined / float(baseline_points)
    unclamped = PM_INTERCEPT + PM_RATIO_SLOPE * ratio
    raw_pm = clamp(unclamped, floor, PM_CEILING)

    info = cfg["player_db"][key]
    role = info["role"]
    pos = info["pos"]
    age = info["age"]

    effective_pm = data_first_effective_pm(role, raw_pm)
    age_mult = snapshot_values.effective_age_multiplier(
        pos,
        age,
        role,
        key,
        effective_pm,
        raw_pm,
        cfg,
    )
    position_weight = float(cfg["position_weight"].get(pos, 1.0))
    value = math.floor(
        100 * position_weight * age_mult * effective_pm * GLOBAL_VALUE_SCALE + 0.5
    )

    return {
        "value": int(value),
        "source": "normal_v2_candidate",
        "combined_points": combined,
        "ratio_to_baseline": ratio,
        "baseline_points": float(baseline_points),
        "raw_unclamped_pm": unclamped,
        "raw_prod_mult": raw_pm,
        "effective_prod_mult": effective_pm,
        "age_mult": float(age_mult),
        "position_weight": position_weight,
        "floor_hit": unclamped <= floor + 1e-12,
        "ceiling_hit": unclamped >= PM_CEILING - 1e-12,
        "elite_floor_applied": role == "Elite" and raw_pm < 0.65,
    }


def compute_variant(players, ranks, floor, cfg, snapshot_values):
    baselines = build_baselines(players, ranks)
    values = {}

    for key in sorted(players):
        rec = players[key]
        current = rec["current"]

        if rec.get("candidate") is None:
            # Accepted Phase-7 continuity fallback. Do not recompute the current
            # value from a different missing-data rule.
            values[key] = {
                "value": int(current["fundamental_value"]),
                "source": "continuity_current_value",
                "combined_points": None,
                "ratio_to_baseline": None,
                "baseline_points": None,
                "raw_unclamped_pm": None,
                "raw_prod_mult": current.get("raw_prod_mult"),
                "effective_prod_mult": current.get("effective_prod_mult"),
                "age_mult": current.get("age_mult"),
                "position_weight": float(cfg["position_weight"].get(rec["pos"], 1.0)),
                "floor_hit": None,
                "ceiling_hit": None,
                "elite_floor_applied": None,
            }
        else:
            values[key] = compute_candidate_value(
                key,
                rec,
                baselines[rec["pos"]]["combined_points"],
                floor,
                cfg,
                snapshot_values,
            )

    return values, baselines


def position_comparison(players, variant_values, ranks):
    out = {}

    for pos in TRACKED_POSITIONS:
        keys = [k for k, rec in players.items() if rec["pos"] == pos]
        cur_values = [int(players[k]["current"]["fundamental_value"]) for k in keys]
        shadow_values = [int(variant_values[k]["value"]) for k in keys]

        pct_changes = []
        continuity_count = 0
        floor_count = 0
        ceiling_count = 0

        for key in keys:
            current = int(players[key]["current"]["fundamental_value"])
            shadow = int(variant_values[key]["value"])
            if current:
                pct_changes.append((shadow - current) / current)
            if variant_values[key]["source"] == "continuity_current_value":
                continuity_count += 1
            if variant_values[key]["floor_hit"] is True:
                floor_count += 1
            if variant_values[key]["ceiling_hit"] is True:
                ceiling_count += 1

        current_order = sorted(
            keys,
            key=lambda k: (-int(players[k]["current"]["fundamental_value"]), k),
        )
        shadow_order = sorted(
            keys,
            key=lambda k: (-int(variant_values[k]["value"]), k),
        )
        current_rank = {k: i + 1 for i, k in enumerate(current_order)}
        shadow_rank = {k: i + 1 for i, k in enumerate(shadow_order)}

        topn = min(int(ranks[pos]), len(keys))
        cur_top = set(current_order[:topn])
        shadow_top = set(shadow_order[:topn])

        out[pos] = {
            "n": len(keys),
            "continuity_count": continuity_count,
            "floor_count": floor_count,
            "floor_share": floor_count / len(keys) if keys else None,
            "ceiling_count": ceiling_count,
            "ceiling_share": ceiling_count / len(keys) if keys else None,
            "fundamental_value_change_pct": summarize(pct_changes),
            "spearman_current_vs_shadow": spearman(cur_values, shadow_values),
            "top_n": topn,
            "top_n_overlap_count": len(cur_top & shadow_top),
            "top_n_overlap_share": len(cur_top & shadow_top) / topn if topn else None,
            "max_absolute_rank_change": max(
                (abs(current_rank[k] - shadow_rank[k]) for k in keys),
                default=0,
            ),
        }

    return out


def largest_movers(players, variant_values, limit=50):
    rows = []
    for key, rec in players.items():
        current = int(rec["current"]["fundamental_value"])
        shadow = int(variant_values[key]["value"])
        pct = (shadow - current) / current if current else None
        rows.append({
            "player": key,
            "pos": rec["pos"],
            "role": rec["role"],
            "current_value": current,
            "shadow_value": shadow,
            "change_pct": pct,
            "source": variant_values[key]["source"],
            "raw_prod_mult": variant_values[key]["raw_prod_mult"],
            "effective_prod_mult": variant_values[key]["effective_prod_mult"],
            "floor_hit": variant_values[key]["floor_hit"],
        })
    rows.sort(key=lambda r: (-abs(r["change_pct"] or 0.0), r["player"]))
    return rows[:limit]


def validate_inputs(phase1, phase2, phase3, phase5, phase6, phase7):
    players = phase1.get("players")
    if not isinstance(players, dict):
        raise RuntimeError("Phase 1 players missing")
    if len(players) != EXPECTED_TRACKED:
        raise RuntimeError(f"expected {EXPECTED_TRACKED} tracked players, got {len(players)}")

    normal = sum(1 for r in players.values() if r.get("candidate") is not None)
    continuity = len(players) - normal
    if normal != EXPECTED_NORMAL or continuity != EXPECTED_CONTINUITY:
        raise RuntimeError(
            f"unexpected candidate split normal={normal}, continuity={continuity}"
        )

    if phase2.get("status") != "FROZEN_PRESEASON_BASELINE_RESEARCH_ONLY":
        raise RuntimeError("Phase 2A preseason baseline is not frozen")
    if phase2.get("calibration_claim_authorized") is not False:
        raise RuntimeError("Phase 2A unexpectedly authorizes calibration")

    if phase3.get("production_mutation_authorized") is not False:
        raise RuntimeError("Phase 3 must remain research-only")

    if phase5.get("decision") != (
        "CARRY_DATA_FIRST_NO_HISTORY_SEMANTICS_FORWARD_FOR_V2_CANDIDATE_COHORT"
    ):
        raise RuntimeError("Phase 5 candidate-present semantics not accepted")
    if not (phase5.get("invariants") or {}).get("data_first_monotonicity_pass"):
        raise RuntimeError("Phase 5 monotonicity did not pass")

    if phase6.get("calibration_claim_authorized") is not False:
        raise RuntimeError("Phase 6 unexpectedly selected calibrated coefficients")
    if phase6.get("decision") != (
        "KEEP_TRANSFORM_FLOOR_UNDEPLOYED_PENDING_PROSPECTIVE_CALIBRATION"
    ):
        raise RuntimeError("Phase 6 transform decision changed unexpectedly")

    if phase7.get("decision") != (
        "CARRY_CURRENT_VALUE_CONTINUITY_FALLBACK_FOR_MISSING_V2_CANDIDATES"
    ):
        raise RuntimeError("Phase 7 continuity fallback not accepted")
    if (phase7.get("fallback_scope") or {}).get("missing_v2_candidate_players") != EXPECTED_CONTINUITY:
        raise RuntimeError("Phase 7 continuity count changed unexpectedly")


def build_result():
    phase1 = read_json(PHASE1_PATH)
    phase2 = read_json(PHASE2_PATH)
    phase3 = read_json(PHASE3_PATH)
    phase5 = read_json(PHASE5_PATH)
    phase6 = read_json(PHASE6_PATH)
    phase7 = read_json(PHASE7_PATH)

    validate_inputs(phase1, phase2, phase3, phase5, phase6, phase7)

    players = phase1["players"]
    documented_ranks = {
        k: int(v) for k, v in phase3["documented_ranks"].items()
    }
    evidence_hybrid_ranks = {
        k: int(v) for k, v in phase3["evidence_hybrid_ranks"].items()
    }

    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)

    rank_families = {
        "documented": documented_ranks,
        "evidence_hybrid": evidence_hybrid_ranks,
    }

    variants = {}
    for rank_family, ranks in rank_families.items():
        for floor in FLOORS:
            key = variant_key(rank_family, floor)
            values, baselines = compute_variant(
                players, ranks, floor, cfg, snapshot_values
            )

            if len(values) != EXPECTED_TRACKED:
                raise RuntimeError(f"{key}: incomplete output {len(values)}")

            continuity = sum(
                1 for row in values.values()
                if row["source"] == "continuity_current_value"
            )
            if continuity != EXPECTED_CONTINUITY:
                raise RuntimeError(
                    f"{key}: expected {EXPECTED_CONTINUITY} continuity rows, got {continuity}"
                )

            # Continuity must be byte-for-byte value neutral for each missing candidate.
            continuity_errors = []
            for player_key, rec in players.items():
                if rec.get("candidate") is not None:
                    continue
                if values[player_key]["value"] != int(rec["current"]["fundamental_value"]):
                    continuity_errors.append(player_key)
            if continuity_errors:
                raise RuntimeError(
                    f"{key}: continuity changed current value for {continuity_errors[:10]}"
                )

            variants[key] = {
                "rank_family": rank_family,
                "floor": floor,
                "ranks": ranks,
                "baselines": baselines,
                "player_count": len(values),
                "normal_candidate_count": EXPECTED_NORMAL,
                "continuity_count": continuity,
                "by_position": position_comparison(players, values, ranks),
                "largest_absolute_movers": largest_movers(players, values),
                "players": values,
            }

    reference = variants[MONITORING_REFERENCE]

    # Cross-variant integrity: with the same rank family, lowering floor may
    # never increase a non-Elite normal candidate's effective PM.
    floor_monotonicity_violations = []
    for rank_family in rank_families:
        ordered = sorted(FLOORS)
        for lo, hi in zip(ordered, ordered[1:]):
            low = variants[variant_key(rank_family, lo)]["players"]
            high = variants[variant_key(rank_family, hi)]["players"]
            for key, rec in players.items():
                if rec.get("candidate") is None or rec["role"] == "Elite":
                    continue
                if low[key]["effective_prod_mult"] > high[key]["effective_prod_mult"] + 1e-12:
                    floor_monotonicity_violations.append({
                        "player": key,
                        "rank_family": rank_family,
                        "lower_floor": lo,
                        "higher_floor": hi,
                        "lower_floor_pm": low[key]["effective_prod_mult"],
                        "higher_floor_pm": high[key]["effective_prod_mult"],
                    })
    if floor_monotonicity_violations:
        raise RuntimeError(
            "floor monotonicity failed; sample="
            + repr(floor_monotonicity_violations[:5])
        )

    # Build compact monitoring reference player table containing current and shadow.
    reference_players = {}
    for key in sorted(players):
        rec = players[key]
        shadow = reference["players"][key]
        current = int(rec["current"]["fundamental_value"])
        value = int(shadow["value"])
        reference_players[key] = {
            "pos": rec["pos"],
            "age": rec["age"],
            "role": rec["role"],
            "current_value": current,
            "shadow_value": value,
            "change": value - current,
            "change_pct": (value - current) / current if current else None,
            "source": shadow["source"],
            "raw_prod_mult": shadow["raw_prod_mult"],
            "effective_prod_mult": shadow["effective_prod_mult"],
            "floor_hit": shadow["floor_hit"],
        }

    return round_numbers({
        "schema_version": 1,
        "phase": "Production V2 Phase 8",
        "status": "CONSOLIDATED_SHADOW_MODEL_RESEARCH_ONLY",
        "production_mutation_authorized": False,
        "deployment_authorized": False,
        "calibration_claim_authorized": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "architecture_locked_for_shadow": {
            "normal_candidate_evidence_state": (
                "Phase-1 frozen benchmark numerator: 45% canonical 2025 history / "
                "55% forward; offense 50/50 FantasyPros+Sleeper when both; IDP V1."
            ),
            "candidate_present_semantics": (
                "Phase-5 data-first: valid V2 candidate is used directly for "
                "non-Elite players; no ROLE_MULT switch at PM 0.15."
            ),
            "elite_safeguard": "existing 0.65 effective-PM floor retained",
            "candidate_missing_semantics": (
                "Phase-7 continuity: preserve current deployed value until a "
                "normal V2 candidate becomes available."
            ),
            "held_fixed": [
                "current POSITION_WEIGHT",
                "current age curves",
                "continuous RB age model",
                "QB/LB decline rules",
                "global value scale 55",
            ],
        },
        "still_uncalibrated_for_phase9": [
            "FantasyPros vs Sleeper provider weight",
            "history vs forward weight",
            "documented vs evidence-hybrid replacement ranks",
            "affine transform floor",
        ],
        "monitoring_reference": {
            "variant": MONITORING_REFERENCE,
            "why": (
                "Evidence-hybrid ranks carry the existing denominator backtest "
                "signal; 0.15 retains the current floor because Phase 6 found "
                "compression but did not authorize a replacement."
            ),
            "not_a_deployment_candidate": True,
        },
        "variant_manifest": [
            {
                "variant": key,
                "rank_family": variants[key]["rank_family"],
                "floor": variants[key]["floor"],
            }
            for key in sorted(variants)
        ],
        "integrity": {
            "tracked_players": len(players),
            "normal_candidate_players": EXPECTED_NORMAL,
            "continuity_players": EXPECTED_CONTINUITY,
            "variant_count": len(variants),
            "full_value_coverage_every_variant": all(
                v["player_count"] == EXPECTED_TRACKED for v in variants.values()
            ),
            "continuity_zero_movement_every_variant": True,
            "floor_monotonicity_violation_count": 0,
        },
        "monitoring_reference_by_position": reference["by_position"],
        "monitoring_reference_largest_absolute_movers": reference["largest_absolute_movers"],
        "monitoring_reference_players": reference_players,
        "variants": variants,
        "phase9_contract": {
            "purpose": (
                "Score the frozen/pre-week shadow variants against realized 2026 "
                "league-scored outcomes. Do not optimize against current Fundamental "
                "Value or market value."
            ),
            "variant_keys": sorted(variants),
            "minimum_decision_rule": (
                "No production deployment until prospective evidence can choose "
                "provider/history weights and can distinguish rank/floor variants "
                "with stable, material out-of-sample improvement."
            ),
        },
        "input_sha256": {
            str(PHASE1_PATH.relative_to(REPO_ROOT)): sha256(PHASE1_PATH),
            str(PHASE2_PATH.relative_to(REPO_ROOT)): sha256(PHASE2_PATH),
            str(PHASE3_PATH.relative_to(REPO_ROOT)): sha256(PHASE3_PATH),
            str(PHASE5_PATH.relative_to(REPO_ROOT)): sha256(PHASE5_PATH),
            str(PHASE6_PATH.relative_to(REPO_ROOT)): sha256(PHASE6_PATH),
            str(PHASE7_PATH.relative_to(REPO_ROOT)): sha256(PHASE7_PATH),
            str(INDEX_HTML.relative_to(REPO_ROOT)): sha256(INDEX_HTML),
            str(SNAPSHOT_VALUES_PATH.relative_to(REPO_ROOT)): sha256(SNAPSHOT_VALUES_PATH),
        },
    })


def pct(x):
    return "—" if x is None else f"{100.0 * float(x):.1f}%"


def signed_pct(x):
    return "—" if x is None else f"{100.0 * float(x):+.1f}%"


def render_md(result):
    integ = result["integrity"]
    ref = result["monitoring_reference"]
    by_pos = result["monitoring_reference_by_position"]

    lines = [
        "# Production V2 — Phase 8 Consolidated Shadow Model",
        "",
        "## Decision",
        "",
        "**SHADOW MODEL COMPLETE — research only; no production deployment authorized.**",
        "",
        f"- Full tracked-player coverage: **{integ['tracked_players']} / {integ['tracked_players']}**",
        f"- Normal V2 candidates: **{integ['normal_candidate_players']}**",
        f"- Continuity fallbacks: **{integ['continuity_players']}**",
        f"- Shadow variants emitted: **{integ['variant_count']}**",
        "- Production files mutated: **0**",
        "- Deployment authorized: **No**",
        "",
        "## What is now locked architecturally",
        "",
        "1. Candidate-present players use the **Phase-5 data-first semantics**: a valid production estimate does not switch into `ROLE_MULT` at the numeric floor.",
        "2. The existing **Elite 0.65 safeguard** remains held fixed.",
        "3. Candidate-missing players use the **Phase-7 continuity fallback**: preserve current deployed value until normal V2 evidence exists.",
        "4. Current position weights, age architecture, RB continuous age, QB/LB decline rules, and global scale remain unchanged.",
        "",
        "## What is still waiting on real 2026 evidence",
        "",
    ]
    for item in result["still_uncalibrated_for_phase9"]:
        lines.append(f"- {item}")

    lines += [
        "",
        "## Shadow variants",
        "",
        "Every variant contains all 549 tracked players. The only varying structural inputs are replacement-rank family and affine floor.",
        "",
        "| Variant | Rank family | Floor |",
        "|---|---|---:|",
    ]
    for row in result["variant_manifest"]:
        lines.append(
            f"| `{row['variant']}` | {row['rank_family']} | {row['floor']:.2f} |"
        )

    lines += [
        "",
        "## Monitoring reference",
        "",
        f"**`{ref['variant']}`**",
        "",
        ref["why"],
        "",
        "This is a monitoring reference, **not a deployment candidate**.",
        "",
        "| Pos | N | Continuity | Floor | Median FV Δ | P95 abs FV Δ | Spearman | Top-N overlap | Max rank move |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for pos in TRACKED_POSITIONS:
        row = by_pos[pos]
        change = row["fundamental_value_change_pct"]
        lines.append(
            f"| {pos} | {row['n']} | {row['continuity_count']} | "
            f"{row['floor_count']} ({pct(row['floor_share'])}) | "
            f"{signed_pct(change.get('median'))} | {pct(change.get('p95_abs'))} | "
            f"{row['spearman_current_vs_shadow']:.4f} | "
            f"{pct(row['top_n_overlap_share'])} | {row['max_absolute_rank_change']} |"
        )

    lines += [
        "",
        "## Largest monitoring-reference movers",
        "",
        "| Player | Pos | Current | Shadow | Change | Source | Floor |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for row in result["monitoring_reference_largest_absolute_movers"][:25]:
        lines.append(
            f"| {row['player']} | {row['pos']} | {row['current_value']} | "
            f"{row['shadow_value']} | {signed_pct(row['change_pct'])} | "
            f"{row['source']} | "
            f"{'yes' if row['floor_hit'] is True else ('no' if row['floor_hit'] is False else 'continuity')} |"
        )

    lines += [
        "",
        "## Integrity gates",
        "",
        f"- Full 549-player value coverage in every variant: **{'PASS' if integ['full_value_coverage_every_variant'] else 'FAIL'}**",
        f"- Continuity fallback is value-neutral in every variant: **{'PASS' if integ['continuity_zero_movement_every_variant'] else 'FAIL'}**",
        f"- Floor monotonicity violations: **{integ['floor_monotonicity_violation_count']}**",
        "",
        "## Phase 9 handoff",
        "",
        result["phase9_contract"]["purpose"],
        "",
        "No coefficient should be selected because it looks better against today's values. Phase 9 must score these frozen/pre-week candidates against realized 2026 league-scored outcomes and require stable, material out-of-sample improvement before deployment.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def canonical_json(result):
    # generated_at_utc is intentionally part of the research artifact; --check
    # compares semantic content with this field normalized away.
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


def semantic_for_check(obj):
    copied = json.loads(json.dumps(obj))
    copied["generated_at_utc"] = "<normalized>"
    return copied


def run_selftest():
    assert variant_key("documented", 0.15) == "documented__floor_0.15"
    assert variant_key("evidence_hybrid", 0.05) == "evidence_hybrid__floor_0.05"
    assert MONITORING_REFERENCE == "evidence_hybrid__floor_0.15"

    # Data-first semantics are monotone for non-Elite players.
    assert data_first_effective_pm("Speculative", 0.10) < data_first_effective_pm("Speculative", 0.15)

    # Elite safeguard stays fixed.
    assert data_first_effective_pm("Elite", 0.15) == 0.65

    # Current affine relationship sanity.
    ratio = 1.0
    assert abs((PM_INTERCEPT + PM_RATIO_SLOPE * ratio) - 0.65) < 1e-12

    print("PASS Production V2 Phase-8 standalone self-test.")


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
        raise RuntimeError("Phase-8 outputs do not exist; run --write first")

    existing = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
    if semantic_for_check(existing) != semantic_for_check(result):
        raise RuntimeError("Phase-8 JSON does not reproduce semantically")
    if OUTPUT_MD.read_text(encoding="utf-8") != md_text:
        raise RuntimeError("Phase-8 Markdown does not reproduce exactly")
    print("PASS Phase-8 semantic-output check.")


if __name__ == "__main__":
    main()
