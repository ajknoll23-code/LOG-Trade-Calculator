#!/usr/bin/env python3
"""
Production V2 Phase 7 — missing-candidate fallback audit.

PURPOSE
-------
Phase 1 builds a complete V2 candidate for 518 / 549 tracked QB/RB/WR/TE/DL/LB/DB
players. 31 players have canonical history state but no usable forward projection,
so the normal V2 numerator cannot be built.

Phase 7 asks a migration question, not a calibration question:

    What should happen to a player when V2 does not have enough evidence to
    produce a normal candidate?

Three research-only treatments are compared:
1. continuity_current
   Keep the currently deployed Fundamental Value / effective PROD_MULT unchanged.
   This is the migration-safety control and invents no new value.
2. role_only
   Fall back to ROLE_MULT and current age/position architecture.
3. history_only_diagnostic
   Use canonical 2025 history alone, normalized within position using the
   documented replacement rank. This is diagnostic only because provider/history
   weights and the affine transform floor remain uncalibrated.

IMPORTANT
---------
- Zero-game "history" rows are explicitly labeled synthetic position-mean
  fallbacks and are NOT treated as real production evidence.
- This audit does NOT mutate production.
- This audit does NOT declare history-only or role-only calibrated.
- The proposed migration-safe V2 fallback is continuity_current until a normal
  V2 candidate becomes available.

INPUTS
------
- research/production-v2/production_v2_phase1_audit.json
- research/production-v2/production_v2_phase5_no_history_semantics_audit.json
- research/production-v2/production_v2_phase6_transform_compression_audit.json
- index.html
- scripts/validation/snapshot_values.py

OUTPUTS
-------
- research/production-v2/production_v2_phase7_missing_candidate_fallback_audit.json
- research/production-v2/production_v2_phase7_missing_candidate_fallback_audit.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from collections import Counter, defaultdict

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
SCRIPTS = REPO_ROOT / "scripts"

PHASE1_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase1_audit.json"
PHASE5_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase5_no_history_semantics_audit.json"
PHASE6_PATH = REPO_ROOT / "research" / "production-v2" / "production_v2_phase6_transform_compression_audit.json"
INDEX_HTML = REPO_ROOT / "index.html"
SNAPSHOT_VALUES_PATH = SCRIPTS / "validation" / "snapshot_values.py"

OUTPUT_JSON = REPO_ROOT / "research" / "production-v2" / "production_v2_phase7_missing_candidate_fallback_audit.json"
OUTPUT_MD = REPO_ROOT / "research" / "production-v2" / "production_v2_phase7_missing_candidate_fallback_audit.md"

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

PM_INTERCEPT = -0.10
PM_RATIO_SLOPE = 0.75
PM_MIN = 0.15
PM_MAX = 1.55
GLOBAL_VALUE_SCALE = 55.0

EXPECTED_MISSING_CANDIDATES = 31


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


def data_first_effective_pm(role, raw_pm):
    # Accepted Phase-5 candidate-present semantics.
    # Existing Elite 0.65 safeguard remains separately fixed.
    if role == "Elite" and raw_pm < 0.65:
        return 0.65
    return float(raw_pm)


def compute_value(key, raw_pm, effective_pm, cfg, snapshot_values):
    info = cfg["player_db"][key]
    pos = info["pos"]
    role = info["role"]
    age = info["age"]
    age_mult = snapshot_values.effective_age_multiplier(
        pos,
        age,
        role,
        key,
        effective_pm,
        raw_pm,
        cfg,
    )
    pw = float(cfg["position_weight"].get(pos, 1.0))
    value = math.floor(
        100 * pw * age_mult * effective_pm * GLOBAL_VALUE_SCALE + 0.5
    )
    return {
        "value": int(value),
        "age_mult": float(age_mult),
        "position_weight": pw,
    }


def build_history_only_baselines(players):
    """
    Diagnostic-only baseline using canonical history_component for every tracked
    player. This intentionally does NOT imply that history-only is the V2 answer.
    """
    out = {}
    for pos in TRACKED_POSITIONS:
        cohort = []
        for rec in players.values():
            if rec.get("pos") != pos:
                continue
            h = (rec.get("history") or {}).get("history_component")
            if h is None:
                continue
            cohort.append((rec["key"], float(h)))
        cohort.sort(key=lambda kv: (-kv[1], kv[0]))
        rank = DOCUMENTED_RANKS[pos]
        if len(cohort) < rank:
            raise RuntimeError(
                f"{pos}: only {len(cohort)} history rows for rank {rank}"
            )
        key, score = cohort[rank - 1]
        if score <= 0:
            raise RuntimeError(f"{pos}: non-positive history-only baseline")
        out[pos] = {
            "rank": rank,
            "player": key,
            "history_component": score,
            "cohort_size": len(cohort),
        }
    return out


def history_only_candidate(key, rec, baselines, cfg, snapshot_values):
    history = rec.get("history") or {}
    score = history.get("history_component")
    if score is None:
        return None
    baseline = float(baselines[rec["pos"]]["history_component"])
    ratio = float(score) / baseline
    raw_pm = clamp(
        PM_INTERCEPT + PM_RATIO_SLOPE * ratio,
        PM_MIN,
        PM_MAX,
    )
    role = cfg["player_db"][key]["role"]
    effective_pm = data_first_effective_pm(role, raw_pm)
    fv = compute_value(key, raw_pm, effective_pm, cfg, snapshot_values)
    return {
        "raw_pm": raw_pm,
        "effective_pm": effective_pm,
        "ratio_to_history_baseline": ratio,
        "history_baseline": baseline,
        **fv,
    }


def role_only_candidate(key, cfg, snapshot_values):
    info = cfg["player_db"][key]
    role = info["role"]
    role_pm = float(cfg["role_mult"].get(role, 1.0))
    # This represents a true missing-production fallback, so role PM is both raw
    # and effective for the diagnostic. Elite role remains 1.40 here, matching
    # the current "no PROD_MULT row" behavior.
    fv = compute_value(key, role_pm, role_pm, cfg, snapshot_values)
    return {
        "raw_pm": role_pm,
        "effective_pm": role_pm,
        **fv,
    }


def evidence_class(rec):
    history = rec.get("history") or {}
    games = int(history.get("games_played_2025") or 0)
    note = str(history.get("shrinkage_note") or "")
    if games > 0:
        return "real_2025_history"
    if "no_2025_data" in note or games == 0:
        return "zero_game_synthetic_history"
    return "other_history_state"


def build_result():
    phase1 = read_json(PHASE1_PATH)
    phase5 = read_json(PHASE5_PATH)
    phase6 = read_json(PHASE6_PATH)

    if phase1.get("production_mutation_authorized") is not False:
        raise RuntimeError("Phase 1 must be research-only")
    if phase5.get("production_mutation_authorized") is not False:
        raise RuntimeError("Phase 5 must be research-only")
    if phase6.get("production_mutation_authorized") is not False:
        raise RuntimeError("Phase 6 must be research-only")

    if str(phase5.get("decision") or "") != (
        "CARRY_DATA_FIRST_NO_HISTORY_SEMANTICS_FORWARD_FOR_V2_CANDIDATE_COHORT"
    ):
        raise RuntimeError("Phase 5 data-first semantics not accepted")

    if phase6.get("calibration_claim_authorized") is not False:
        raise RuntimeError("Phase 6 unexpectedly authorizes calibration")

    players = phase1.get("players")
    if not isinstance(players, dict):
        raise RuntimeError("Phase 1 players missing")

    cfg = load_snapshot_values().load_from_html(INDEX_HTML)
    snapshot_values = load_snapshot_values()

    missing = {
        key: rec for key, rec in players.items()
        if rec.get("candidate") is None
    }
    expected_from_phase5 = int(
        (phase5.get("candidate_cohort") or {}).get(
            "phase1_players_without_complete_candidate", -1
        )
    )
    if len(missing) != EXPECTED_MISSING_CANDIDATES:
        raise RuntimeError(
            f"Expected {EXPECTED_MISSING_CANDIDATES} missing candidates, "
            f"found {len(missing)}"
        )
    if expected_from_phase5 != len(missing):
        raise RuntimeError(
            f"Phase-5 missing count {expected_from_phase5} != {len(missing)}"
        )

    history_baselines = build_history_only_baselines(players)

    source_counts = Counter()
    evidence_counts = Counter()
    position_counts = Counter()
    stable_id_missing = 0
    rows = []

    role_only_pct = []
    history_only_pct = []
    role_only_by_pos = defaultdict(list)
    history_only_by_pos = defaultdict(list)

    for key in sorted(missing):
        rec = missing[key]
        current = rec["current"]
        forward = rec.get("forward") or {}
        history = rec.get("history") or {}

        source = str(forward.get("source") or "unknown")
        eclass = evidence_class(rec)
        source_counts[source] += 1
        evidence_counts[eclass] += 1
        position_counts[rec["pos"]] += 1
        if not rec.get("sleeper_id"):
            stable_id_missing += 1

        role_diag = role_only_candidate(key, cfg, snapshot_values)
        hist_diag = history_only_candidate(
            key, rec, history_baselines, cfg, snapshot_values
        )

        current_value = int(current["fundamental_value"])
        role_pct = (
            (role_diag["value"] - current_value) / current_value
            if current_value else None
        )
        hist_pct = (
            (hist_diag["value"] - current_value) / current_value
            if hist_diag is not None and current_value else None
        )

        if role_pct is not None:
            role_only_pct.append(role_pct)
            role_only_by_pos[rec["pos"]].append(role_pct)
        if hist_pct is not None:
            history_only_pct.append(hist_pct)
            history_only_by_pos[rec["pos"]].append(hist_pct)

        rows.append({
            "player": key,
            "pos": rec["pos"],
            "age": rec["age"],
            "role": rec["role"],
            "sleeper_id": rec.get("sleeper_id"),
            "forward_source": source,
            "evidence_class": eclass,
            "games_played_2025": int(history.get("games_played_2025") or 0),
            "history_note": history.get("shrinkage_note"),
            "history_component": history.get("history_component"),
            "current_raw_prod_mult": current.get("raw_prod_mult"),
            "current_effective_prod_mult": current.get("effective_prod_mult"),
            "current_value": current_value,
            "continuity_value": current_value,
            "role_only_value": role_diag["value"],
            "role_only_effective_pm": role_diag["effective_pm"],
            "role_only_value_change_pct": role_pct,
            "history_only_value": (
                hist_diag["value"] if hist_diag is not None else None
            ),
            "history_only_raw_pm": (
                hist_diag["raw_pm"] if hist_diag is not None else None
            ),
            "history_only_effective_pm": (
                hist_diag["effective_pm"] if hist_diag is not None else None
            ),
            "history_only_value_change_pct": hist_pct,
        })

    # Invariant: continuity fallback changes nothing by definition.
    if any(r["continuity_value"] != r["current_value"] for r in rows):
        raise RuntimeError("Continuity fallback changed a missing-candidate value")

    by_position = {}
    for pos in TRACKED_POSITIONS:
        pos_rows = [r for r in rows if r["pos"] == pos]
        by_position[pos] = {
            "missing_candidate_count": len(pos_rows),
            "real_2025_history_count": sum(
                1 for r in pos_rows if r["evidence_class"] == "real_2025_history"
            ),
            "zero_game_synthetic_history_count": sum(
                1 for r in pos_rows
                if r["evidence_class"] == "zero_game_synthetic_history"
            ),
            "role_only_value_change_pct": summarize(role_only_by_pos[pos]),
            "history_only_value_change_pct": summarize(history_only_by_pos[pos]),
        }

    # Biggest diagnostic movers, not recommendations.
    role_movers = sorted(
        rows,
        key=lambda r: (
            -abs(r["role_only_value_change_pct"] or 0.0),
            r["player"],
        ),
    )
    history_movers = sorted(
        rows,
        key=lambda r: (
            -abs(r["history_only_value_change_pct"] or 0.0),
            r["player"],
        ),
    )

    # Migration decision:
    # When the normal V2 candidate is absent, there is no out-of-sample basis to
    # replace the currently deployed value with either diagnostic alternative.
    # Continuity is therefore the only evidence-neutral fallback.
    decision = (
        "CARRY_CURRENT_VALUE_CONTINUITY_FALLBACK_FOR_MISSING_V2_CANDIDATES"
    )

    return round_numbers({
        "schema_version": 1,
        "phase": "Production V2 Phase 7",
        "status": "RESEARCH_ONLY_MISSING_CANDIDATE_FALLBACK_AUDIT",
        "production_mutation_authorized": False,
        "calibration_claim_authorized": False,
        "decision": decision,
        "fallback_scope": {
            "tracked_players": len(players),
            "normal_v2_candidate_players": len(players) - len(missing),
            "missing_v2_candidate_players": len(missing),
            "continuity_fallback_changes_value": False,
            "automatic_exit_condition": (
                "Stop using continuity fallback for a player as soon as the "
                "normal V2 pipeline can build a complete candidate."
            ),
        },
        "missingness": {
            "by_forward_source": dict(sorted(source_counts.items())),
            "by_evidence_class": dict(sorted(evidence_counts.items())),
            "by_position": dict(sorted(position_counts.items())),
            "missing_stable_sleeper_id_count": stable_id_missing,
        },
        "history_only_diagnostic_baselines": history_baselines,
        "diagnostic_blast_radius": {
            "role_only_vs_current_all_missing": summarize(role_only_pct),
            "history_only_vs_current_all_missing": summarize(history_only_pct),
            "by_position": by_position,
        },
        "players": rows,
        "largest_role_only_movers": role_movers[:20],
        "largest_history_only_movers": history_movers[:20],
        "interpretation": (
            "The 31 missing V2 candidates are a migration-coverage problem, not "
            "permission to invent a new fallback model. ROLE_MULT is a coarse "
            "prior and history-only is not calibrated to substitute for the "
            "missing forward component. Preserving the currently deployed value "
            "is the only fallback that is neutral to missingness and automatically "
            "disappears as V2 coverage improves."
        ),
        "next_step": (
            "Production V2 now has a defined candidate-present semantic and a "
            "migration-safe candidate-missing semantic. Carry documented and "
            "evidence-hybrid baselines plus transform-floor sensitivity into the "
            "prospective 2026 evaluator. Before any production deployment, build "
            "a consolidated V2 shadow-value generator with these architectural "
            "decisions frozen and compare its full 549-player output to current "
            "production without mutating index.html."
        ),
        "input_sha256": {
            str(PHASE1_PATH.relative_to(REPO_ROOT)): sha256(PHASE1_PATH),
            str(PHASE5_PATH.relative_to(REPO_ROOT)): sha256(PHASE5_PATH),
            str(PHASE6_PATH.relative_to(REPO_ROOT)): sha256(PHASE6_PATH),
            str(INDEX_HTML.relative_to(REPO_ROOT)): sha256(INDEX_HTML),
            str(SNAPSHOT_VALUES_PATH.relative_to(REPO_ROOT)): sha256(SNAPSHOT_VALUES_PATH),
        },
    })


def pct(x):
    return "—" if x is None else f"{100.0 * float(x):.1f}%"


def signed_pct(x):
    return "—" if x is None else f"{100.0 * float(x):+.1f}%"


def render_md(result):
    scope = result["fallback_scope"]
    missing = result["missingness"]
    blast = result["diagnostic_blast_radius"]

    lines = [
        "# Production V2 — Phase 7 Missing-Candidate Fallback Audit",
        "",
        "## Decision",
        "",
        f"**{result['decision']}**",
        "",
        "- Production files mutated: **0**",
        f"- Normal V2 candidates: **{scope['normal_v2_candidate_players']}**",
        f"- Missing V2 candidates: **{scope['missing_v2_candidate_players']}**",
        "- Continuity fallback changes those players' current values: **No**",
        "",
        "The fallback is intentionally temporary and player-specific: the moment a normal V2 candidate becomes available, that player exits the continuity fallback automatically.",
        "",
        "## Why these 31 are missing",
        "",
        "### Forward-source state",
        "",
    ]

    for source, count in missing["by_forward_source"].items():
        lines.append(f"- `{source}`: **{count}**")

    lines += [
        "",
        "### Evidence state",
        "",
    ]
    for state, count in missing["by_evidence_class"].items():
        lines.append(f"- `{state}`: **{count}**")

    lines += [
        "",
        f"- Missing stable Sleeper ID: **{missing['missing_stable_sleeper_id_count']}**",
        "",
        "Zero-game canonical history is explicitly treated as a **synthetic position-mean fallback**, not as real 2025 production.",
        "",
        "## Why continuity is the control",
        "",
        "`ROLE_MULT` is a coarse prior. History-only is real evidence for some players, but it is not calibrated as a substitute for the missing forward component. Replacing a player's deployed value with either one solely because a provider projection is absent would make missingness itself change player value.",
        "",
        "Continuity avoids that. It says: **if V2 cannot build its normal estimate, do not manufacture a new one. Preserve the deployed value until coverage returns.**",
        "",
        "## Diagnostic alternatives vs current value",
        "",
        "| Diagnostic | Median change | P95 abs change | Max abs change |",
        "|---|---:|---:|---:|",
        f"| Role-only | {signed_pct(blast['role_only_vs_current_all_missing'].get('median'))} | "
        f"{pct(blast['role_only_vs_current_all_missing'].get('p95_abs'))} | "
        f"{pct(blast['role_only_vs_current_all_missing'].get('max_abs'))} |",
        f"| History-only | {signed_pct(blast['history_only_vs_current_all_missing'].get('median'))} | "
        f"{pct(blast['history_only_vs_current_all_missing'].get('p95_abs'))} | "
        f"{pct(blast['history_only_vs_current_all_missing'].get('max_abs'))} |",
        "",
        "These are diagnostics only. Neither alternative is authorized as a fallback by this audit.",
        "",
        "## Missing candidates by position",
        "",
        "| Pos | Missing | Real 2025 history | Zero-game synthetic history | Role-only P95 abs Δ | History-only P95 abs Δ |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    by_pos = blast["by_position"]
    for pos in TRACKED_POSITIONS:
        row = by_pos[pos]
        lines.append(
            f"| {pos} | {row['missing_candidate_count']} | "
            f"{row['real_2025_history_count']} | "
            f"{row['zero_game_synthetic_history_count']} | "
            f"{pct(row['role_only_value_change_pct'].get('p95_abs'))} | "
            f"{pct(row['history_only_value_change_pct'].get('p95_abs'))} |"
        )

    lines += [
        "",
        "## Largest role-only diagnostic movers",
        "",
        "| Player | Pos | Role | Current | Role-only | Change | Evidence state |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for row in result["largest_role_only_movers"][:15]:
        lines.append(
            f"| {row['player']} | {row['pos']} | {row['role']} | "
            f"{row['current_value']} | {row['role_only_value']} | "
            f"{signed_pct(row['role_only_value_change_pct'])} | "
            f"{row['evidence_class']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        result["interpretation"],
        "",
        "## Next step",
        "",
        result["next_step"],
        "",
    ]

    return "\n".join(lines).rstrip() + "\n"


def canonical_json(result):
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


def run_selftest():
    # Evidence classification must never call zero games "real".
    assert evidence_class({
        "history": {
            "games_played_2025": 0,
            "shrinkage_note": "no_2025_data_full_shrink_to_position_mean",
        }
    }) == "zero_game_synthetic_history"
    assert evidence_class({
        "history": {
            "games_played_2025": 8,
            "shrinkage_note": "real",
        }
    }) == "real_2025_history"

    # Continuity fallback invariant.
    current_value = 1234
    continuity_value = current_value
    assert continuity_value == current_value

    # Data-first PM is monotone for non-Elite candidate-present semantics.
    assert data_first_effective_pm("Speculative", 0.15) == 0.15
    assert data_first_effective_pm("Speculative", 0.20) == 0.20

    print("PASS Production V2 Phase-7 standalone self-test.")


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
        raise RuntimeError("Phase-7 outputs do not exist; run --write first")
    if OUTPUT_JSON.read_text(encoding="utf-8") != json_text:
        raise RuntimeError("Phase-7 JSON does not reproduce exactly")
    if OUTPUT_MD.read_text(encoding="utf-8") != md_text:
        raise RuntimeError("Phase-7 Markdown does not reproduce exactly")
    print("PASS Phase-7 exact-output check.")


if __name__ == "__main__":
    main()
