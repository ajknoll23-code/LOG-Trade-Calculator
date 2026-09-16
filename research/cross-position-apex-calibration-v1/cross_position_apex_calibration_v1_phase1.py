#!/usr/bin/env python3
"""Cross-Position Apex Calibration V1 Phase 1 diagnostic freeze."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import sys

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
RESEARCH = ROOT / "research" / "cross-position-apex-calibration-v1"

INDEX = ROOT / "index.html"
ROSTERS = ROOT / "data" / "league_rosters.json"
PLAYER_POSITIONS = ROOT / "scripts" / "artifacts" / "generated" / "player_positions.json"
SNAPSHOT_VALUES = ROOT / "scripts" / "validation" / "snapshot_values.py"
STARTER_AUDIT = ROOT / "research" / "team-utility" / "team_utility_starter_objective_audit.py"
OFFENSE_PHASE1 = ROOT / "research" / "offense-position-lineage-v1" / "offense_position_lineage_v1_phase1.json"

PREREG_JSON = RESEARCH / "phase1_preregistration.json"
PREREG_MD = RESEARCH / "phase1_preregistration.md"
OUT_JSON = RESEARCH / "cross_position_apex_calibration_v1_phase1.json"
OUT_MD = RESEARCH / "cross_position_apex_calibration_v1_phase1.md"
MANIFEST = RESEARCH / "phase1_manifest.json"

BURNS = "brian burns"
ALLEN = "josh allen"
POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
TOP_CUTS = (12, 20, 24, 50, 100)
POSITION_DEPTH_RANKS = (1, 3, 6, 12, 24, 32)
HIGH_PRIORITY_RATIO = 1.10
HISTORY_WEIGHT = 0.45
PROJECTION_WEIGHT = 0.55
UNIVERSAL_REPLACEMENT_RANK = 32

def read_json(path: Path):
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

def load_modules():
    sys.path.insert(0, str(ROOT / "scripts" / "validation"))
    import snapshot_values
    sys.path.insert(0, str(ROOT / "research" / "team-utility"))
    import team_utility_starter_objective_audit as starter_audit
    return snapshot_values, starter_audit

def load_current_cfg(snapshot_values, starter_audit):
    base = snapshot_values.load_from_html(INDEX)
    roster_doc = read_json(ROSTERS)
    cfg = starter_audit.merge_live_league_into_cfg(base, roster_doc)
    unresolved = cfg.get("live_merge_stats", {}).get("unresolved_positions") or []
    if unresolved:
        raise RuntimeError(
            "production-parity live merge has unresolved positions: "
            + json.dumps(unresolved[:20], sort_keys=True)
        )
    return cfg, roster_doc

def parse_player_db_embedded_stats():
    text = INDEX.read_text(encoding="utf-8")
    marker = "const PLAYER_DB = {"
    start = text.find(marker)
    if start < 0:
        raise RuntimeError("PLAYER_DB not found in index.html")

    brace = text.find("{", start)
    depth = 0
    quote = None
    escaped = False
    end = None
    for i in range(brace, len(text)):
        ch = text[i]
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        raise RuntimeError("unterminated PLAYER_DB")

    body = text[brace + 1:end]
    rows = {}
    for match in re.finditer(r"'([^']+)'\s*:\s*\{([^{}]*)\}", body):
        key = match.group(1)
        entry = match.group(2)

        def field_num(name):
            m = re.search(rf"\b{re.escape(name)}\s*:\s*([0-9.]+)", entry)
            return float(m.group(1)) if m else None

        def field_str(name):
            m = re.search(rf"\b{re.escape(name)}\s*:\s*'([^']*)'", entry)
            return m.group(1) if m else None

        rows[key] = {
            "pos": field_str("pos"),
            "age": field_num("age"),
            "role": field_str("role"),
            "team": field_str("team"),
            "pts2025": field_num("pts2025"),
            "proj2026": field_num("proj2026"),
        }
    return rows

def js_round_positive(x):
    return math.floor(float(x) + 0.5)

def rank_map(values):
    ordered = sorted(
        values.items(),
        key=lambda kv: (-int(kv[1]["value"]), kv[0]),
    )
    return {key: i + 1 for i, (key, _) in enumerate(ordered)}, ordered

def player_detail(key, cfg, values, overall_rank, embedded):
    if key not in values:
        return None
    v = values[key]
    info = cfg["player_db"].get(key) or {}
    pw = finite(cfg["position_weight"].get(v["pos"]))
    age_mult = finite(v.get("age_mult"))
    prod_mult = finite(v.get("prod_mult"))
    fv = int(v["value"])
    exact_unrounded = (
        100.0 * pw * age_mult * prod_mult * 55.0
        if None not in (pw, age_mult, prod_mult)
        else None
    )
    reproduced = (
        js_round_positive(exact_unrounded)
        if exact_unrounded is not None
        else None
    )
    position_keys = [
        k for k, rec in values.items() if rec.get("pos") == v["pos"]
    ]
    position_order = sorted(
        position_keys,
        key=lambda k: (-int(values[k]["value"]), k),
    )
    position_rank = (
        position_order.index(key) + 1 if key in position_order else None
    )
    stats = embedded.get(key, {})
    weighted_raw_points = None
    history_lift_vs_projection = None
    if (
        finite(stats.get("pts2025")) is not None
        and finite(stats.get("proj2026")) is not None
        and float(stats["proj2026"]) > 0
    ):
        weighted_raw_points = (
            HISTORY_WEIGHT * float(stats["pts2025"])
            + PROJECTION_WEIGHT * float(stats["proj2026"])
        )
        history_lift_vs_projection = (
            weighted_raw_points / float(stats["proj2026"])
        )

    return {
        "key": key,
        "position": v["pos"],
        "age": v["age"],
        "role": v["role"],
        "fv": fv,
        "overall_rank": overall_rank.get(key),
        "position_rank": position_rank,
        "position_weight": pw,
        "age_mult": age_mult,
        "effective_prod_mult": prod_mult,
        "raw_prod_mult": finite(cfg["prod_mult"].get(key)),
        "formula_unrounded": exact_unrounded,
        "formula_reproduced_fv": reproduced,
        "formula_reproduction_exact": reproduced == fv,
        "pts2025": finite(stats.get("pts2025")),
        "proj2026": finite(stats.get("proj2026")),
        "weighted_45_55_raw_points": weighted_raw_points,
        "history_lift_vs_projection_ratio": history_lift_vs_projection,
        "embedded_team": stats.get("team") or info.get("team"),
    }

def position_distribution(values, ordered):
    result = {}
    for cut in TOP_CUTS:
        chosen = ordered[:cut]
        counts = {pos: 0 for pos in POSITIONS}
        for _, rec in chosen:
            pos = rec.get("pos")
            if pos in counts:
                counts[pos] += 1
        result[str(cut)] = {
            "counts": counts,
            "shares": {
                pos: counts[pos] / len(chosen) if chosen else 0.0
                for pos in POSITIONS
            },
        }
    return result

def position_depth_table(values):
    out = {}
    for pos in POSITIONS:
        keys = sorted(
            [k for k, rec in values.items() if rec.get("pos") == pos],
            key=lambda k: (-int(values[k]["value"]), k),
        )
        rows = []
        for rank in POSITION_DEPTH_RANKS:
            if len(keys) >= rank:
                key = keys[rank - 1]
                rec = values[key]
                rows.append({
                    "rank": rank,
                    "key": key,
                    "fv": int(rec["value"]),
                    "prod_mult": finite(rec.get("prod_mult")),
                    "age_mult": finite(rec.get("age_mult")),
                })
            else:
                rows.append({
                    "rank": rank,
                    "key": None,
                    "fv": None,
                    "prod_mult": None,
                    "age_mult": None,
                })
        out[pos] = {
            "player_count": len(keys),
            "depth_rows": rows,
        }
    return out

def starter_demand(starter_audit, roster_count):
    dedicated = dict(starter_audit.DEDICATED)
    flexes = list(starter_audit.FLEXES)
    result = {}
    for pos in POSITIONS:
        per_team_min = int(dedicated.get(pos, 0))
        per_team_flex_max = sum(
            int(count)
            for _label, eligible, count in flexes
            if pos in eligible
        )
        per_team_max = per_team_min + per_team_flex_max
        league_min = roster_count * per_team_min
        league_max = roster_count * per_team_max

        if UNIVERSAL_REPLACEMENT_RANK < league_min:
            rank32_context = "shallower_than_dedicated_starter_demand"
        elif UNIVERSAL_REPLACEMENT_RANK > league_max:
            rank32_context = "deeper_than_theoretical_max_starter_demand"
        else:
            rank32_context = "inside_starter_demand_range"

        result[pos] = {
            "per_team_dedicated_min": per_team_min,
            "per_team_theoretical_max_with_flex": per_team_max,
            "league_dedicated_min": league_min,
            "league_theoretical_max_with_flex": league_max,
            "universal_replacement_rank": UNIVERSAL_REPLACEMENT_RANK,
            "rank32_context": rank32_context,
        }
    return result

def build_result():
    snapshot_values, starter_audit = load_modules()
    cfg, roster_doc = load_current_cfg(snapshot_values, starter_audit)
    values = snapshot_values.compute_all_values(cfg)
    embedded = parse_player_db_embedded_stats()
    offense_trigger = read_json(OFFENSE_PHASE1)

    ranks, ordered = rank_map(values)
    burns = player_detail(BURNS, cfg, values, ranks, embedded)
    allen = player_detail(ALLEN, cfg, values, ranks, embedded)

    trigger_artifact_status = (
        offense_trigger
        .get("apex_cross_position_diagnostic", {})
        .get("status")
    )
    trigger_artifact_high = bool(
        offense_trigger
        .get("apex_cross_position_diagnostic", {})
        .get("high_priority_flag")
    )

    factor_ratio_identity = None
    observed_ratio = None
    observed_gap = None
    tie_thresholds = {}
    history_relative_boost = None

    if burns and allen and allen["fv"] > 0:
        observed_ratio = burns["fv"] / allen["fv"]
        observed_gap = burns["fv"] - allen["fv"]

        factor_ratio_identity = (
            (burns["position_weight"] / allen["position_weight"])
            * (burns["age_mult"] / allen["age_mult"])
            * (burns["effective_prod_mult"] / allen["effective_prod_mult"])
        )

        burns_prod_to_tie = (
            allen["fv"]
            / (100.0 * burns["position_weight"] * burns["age_mult"] * 55.0)
        )
        burns_pw_to_tie = (
            allen["fv"]
            / (100.0 * burns["effective_prod_mult"] * burns["age_mult"] * 55.0)
        )
        allen_pw_to_tie = (
            burns["fv"]
            / (100.0 * allen["effective_prod_mult"] * allen["age_mult"] * 55.0)
        )
        tie_thresholds = {
            "burns_prod_mult_to_tie_allen": burns_prod_to_tie,
            "burns_prod_mult_current": burns["effective_prod_mult"],
            "burns_prod_mult_pct_change_to_tie": (
                burns_prod_to_tie / burns["effective_prod_mult"] - 1.0
            ),
            "burns_dl_position_weight_to_tie_allen": burns_pw_to_tie,
            "burns_dl_position_weight_current": burns["position_weight"],
            "burns_dl_position_weight_pct_change_to_tie": (
                burns_pw_to_tie / burns["position_weight"] - 1.0
            ),
            "allen_qb_position_weight_to_tie_burns": allen_pw_to_tie,
            "allen_qb_position_weight_current": allen["position_weight"],
            "allen_qb_position_weight_pct_change_to_tie": (
                allen_pw_to_tie / allen["position_weight"] - 1.0
            ),
        }

        b_lift = burns.get("history_lift_vs_projection_ratio")
        a_lift = allen.get("history_lift_vs_projection_ratio")
        if b_lift is not None and a_lift is not None and a_lift != 0:
            history_relative_boost = {
                "burns_history_lift_vs_projection_ratio": b_lift,
                "allen_history_lift_vs_projection_ratio": a_lift,
                "burns_vs_allen_relative_history_lift_ratio": b_lift / a_lift,
                "burns_minus_allen_history_lift_pct_points": (
                    (b_lift - 1.0) - (a_lift - 1.0)
                ),
            }

    roster_count = len(roster_doc.get("rosters", []))
    demand = starter_demand(starter_audit, roster_count)
    distribution = position_distribution(values, ordered)
    depth = position_depth_table(values)

    top_20 = [
        {
            "rank": i + 1,
            "key": key,
            "pos": rec.get("pos"),
            "fv": int(rec["value"]),
            "prod_mult": finite(rec.get("prod_mult")),
            "age_mult": finite(rec.get("age_mult")),
        }
        for i, (key, rec) in enumerate(ordered[:20])
    ]

    formula_repro_pass = bool(
        burns and allen
        and burns["formula_reproduction_exact"]
        and allen["formula_reproduction_exact"]
    )
    ratio_repro_pass = bool(
        observed_ratio is not None
        and factor_ratio_identity is not None
        and abs(observed_ratio - factor_ratio_identity) <= 0.001
    )
    trigger_artifact_pass = bool(
        trigger_artifact_high
        and trigger_artifact_status
        == "HIGH_PRIORITY_CROSS_POSITION_CALIBRATION_REVIEW"
    )

    gates = {
        "comparison_players_present": {
            "pass": burns is not None and allen is not None,
        },
        "exact_player_value_factorization_reproduces_both": {
            "pass": formula_repro_pass,
            "burns_reproduced": burns and burns["formula_reproduced_fv"],
            "allen_reproduced": allen and allen["formula_reproduced_fv"],
        },
        "burns_allen_factor_ratio_identity_reproduced": {
            "pass": ratio_repro_pass,
            "observed_fv_ratio": observed_ratio,
            "factor_ratio_identity": factor_ratio_identity,
        },
        "league_format_readable": {
            "pass": roster_count > 0 and bool(starter_audit.DEDICATED),
            "roster_count": roster_count,
            "expected_starters_per_team": starter_audit.EXPECTED_STARTERS,
        },
        "offense_phase1_trigger_still_high_priority": {
            "pass": trigger_artifact_pass,
            "trigger_artifact_status": trigger_artifact_status,
        },
    }

    all_integrity = all(g["pass"] for g in gates.values())
    high_priority_current = bool(
        observed_ratio is not None and observed_ratio >= HIGH_PRIORITY_RATIO
    )

    if not all_integrity:
        decision = (
            "STOP_CROSS_POSITION_APEX_CALIBRATION_V1_PHASE1_INTEGRITY_FAILURE"
        )
    elif high_priority_current:
        decision = (
            "PASS_CROSS_POSITION_APEX_CALIBRATION_V1_PHASE1_REVIEW_REQUIRED"
        )
    else:
        decision = (
            "STOP_CROSS_POSITION_APEX_CALIBRATION_V1_NO_CURRENT_APEX_TRIGGER"
        )

    pw_ratio = (
        burns["position_weight"] / allen["position_weight"]
        if burns and allen else None
    )
    prod_ratio = (
        burns["effective_prod_mult"] / allen["effective_prod_mult"]
        if burns and allen else None
    )
    age_ratio = (
        burns["age_mult"] / allen["age_mult"]
        if burns and allen else None
    )

    return {
        "study_id": "cross-position-apex-calibration-v1",
        "phase": 1,
        "status": "FROZEN_DIAGNOSTIC_COMPLETE",
        "decision": decision,
        "production_change_authorized": False,
        "repo_commit_sha_evaluated": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "trigger": {
            "threshold_ratio": HIGH_PRIORITY_RATIO,
            "current_burns_to_allen_fv_ratio": observed_ratio,
            "current_burns_minus_allen_fv": observed_gap,
            "high_priority_current": high_priority_current,
        },
        "comparison": {
            "brian_burns": burns,
            "josh_allen": allen,
            "factor_decomposition": {
                "position_weight_ratio_burns_over_allen": pw_ratio,
                "age_multiplier_ratio_burns_over_allen": age_ratio,
                "production_multiplier_ratio_burns_over_allen": prod_ratio,
                "multiplicative_factor_ratio_identity": factor_ratio_identity,
                "observed_fv_ratio": observed_ratio,
            },
            "history_projection_diagnostic": history_relative_boost,
            "neutral_tie_thresholds_not_recommendations": tie_thresholds,
        },
        "league_context": {
            "roster_count": roster_count,
            "team_utility_expected_starters_per_team": starter_audit.EXPECTED_STARTERS,
            "starter_demand_by_position": demand,
            "universal_replacement_rank_contextualized": UNIVERSAL_REPLACEMENT_RANK,
        },
        "distribution": {
            "top_cut_position_distribution": distribution,
            "position_depth_table": depth,
            "top_20_overall": top_20,
        },
        "gates": gates,
        "input_sha256": {
            str(INDEX.relative_to(ROOT)): sha256(INDEX),
            str(ROSTERS.relative_to(ROOT)): sha256(ROSTERS),
            str(PLAYER_POSITIONS.relative_to(ROOT)): sha256(PLAYER_POSITIONS),
            str(SNAPSHOT_VALUES.relative_to(ROOT)): sha256(SNAPSHOT_VALUES),
            str(STARTER_AUDIT.relative_to(ROOT)): sha256(STARTER_AUDIT),
            str(OFFENSE_PHASE1.relative_to(ROOT)): sha256(OFFENSE_PHASE1),
        },
    }

def markdown(r):
    c = r["comparison"]
    b = c["brian_burns"]
    a = c["josh_allen"]
    f = c["factor_decomposition"]
    h = c["history_projection_diagnostic"]
    t = c["neutral_tie_thresholds_not_recommendations"]
    lines = [
        "# Cross-Position Apex Calibration V1 — Phase 1 Diagnostic",
        "",
        f"**Decision:** `{r['decision']}`",
        "",
        "Research-only. Production is unchanged.",
        "",
        "## Trigger",
        "",
        f"- Brian Burns FV: **{b['fv']}** (overall **#{b['overall_rank']}**, DL **#{b['position_rank']}**)",
        f"- Josh Allen FV: **{a['fv']}** (overall **#{a['overall_rank']}**, QB **#{a['position_rank']}**)",
        f"- Burns minus Allen: **{r['trigger']['current_burns_minus_allen_fv']:+d} FV**",
        f"- Burns / Allen: **{r['trigger']['current_burns_to_allen_fv_ratio']:.4f}x**",
        f"- High-priority >=1.10x trigger: **{'YES' if r['trigger']['high_priority_current'] else 'NO'}**",
        "",
        "## Exact FV factor decomposition",
        "",
        "| Factor | Burns | Allen | Burns/Allen |",
        "|---|---:|---:|---:|",
        f"| Position weight | {b['position_weight']:.4f} | {a['position_weight']:.4f} | {f['position_weight_ratio_burns_over_allen']:.4f}x |",
        f"| Age multiplier | {b['age_mult']:.6f} | {a['age_mult']:.6f} | {f['age_multiplier_ratio_burns_over_allen']:.4f}x |",
        f"| Effective PROD_MULT | {b['effective_prod_mult']:.4f} | {a['effective_prod_mult']:.4f} | {f['production_multiplier_ratio_burns_over_allen']:.4f}x |",
        f"| Product of factor ratios |  |  | {f['multiplicative_factor_ratio_identity']:.4f}x |",
        f"| Observed FV ratio |  |  | {f['observed_fv_ratio']:.4f}x |",
        "",
    ]

    if h:
        lines += [
            "## 2025-history lift versus 2026 projection",
            "",
            f"- Burns: 2025 **{b['pts2025']:.1f}**, 2026 projection **{b['proj2026']:.1f}**, 45/55 raw blend **{b['weighted_45_55_raw_points']:.1f}**",
            f"- Allen: 2025 **{a['pts2025']:.1f}**, 2026 projection **{a['proj2026']:.1f}**, 45/55 raw blend **{a['weighted_45_55_raw_points']:.1f}**",
            f"- Burns blend / projection: **{h['burns_history_lift_vs_projection_ratio']:.4f}x**",
            f"- Allen blend / projection: **{h['allen_history_lift_vs_projection_ratio']:.4f}x**",
            f"- Burns receives **{h['burns_minus_allen_history_lift_pct_points']*100:+.1f} percentage points** more history lift than Allen before positional normalization.",
            "",
        ]

    lines += [
        "## Neutral tie thresholds",
        "",
        "These are sensitivity measurements, **not recommendations**.",
        "",
        f"- Burns PROD_MULT would tie Allen at **{t['burns_prod_mult_to_tie_allen']:.4f}** vs current **{t['burns_prod_mult_current']:.4f}** ({t['burns_prod_mult_pct_change_to_tie']*100:+.1f}%).",
        f"- DL position weight would tie Burns to Allen at **{t['burns_dl_position_weight_to_tie_allen']:.4f}** vs current **{t['burns_dl_position_weight_current']:.4f}** ({t['burns_dl_position_weight_pct_change_to_tie']*100:+.1f}%).",
        f"- QB position weight would tie Allen to Burns at **{t['allen_qb_position_weight_to_tie_burns']:.4f}** vs current **{t['allen_qb_position_weight_current']:.4f}** ({t['allen_qb_position_weight_pct_change_to_tie']*100:+.1f}%).",
        "",
        "## League starter-demand context",
        "",
        "| Pos | Dedicated league min | Theoretical max with flex | Rank-32 context |",
        "|---|---:|---:|---|",
    ]
    for pos in POSITIONS:
        d = r["league_context"]["starter_demand_by_position"][pos]
        lines.append(
            f"| {pos} | {d['league_dedicated_min']} | "
            f"{d['league_theoretical_max_with_flex']} | "
            f"`{d['rank32_context']}` |"
        )

    lines += [
        "",
        "## Overall top-20 FV",
        "",
        "| Rank | Player | Pos | FV | PROD_MULT | Age mult |",
        "|---:|---|---|---:|---:|---:|",
    ]
    for row in r["distribution"]["top_20_overall"]:
        lines.append(
            f"| {row['rank']} | {row['key']} | {row['pos']} | "
            f"{row['fv']} | {row['prod_mult']:.4f} | {row['age_mult']:.4f} |"
        )

    lines += [
        "",
        "## Integrity gates",
        "",
        "| Gate | Result |",
        "|---|---|",
    ]
    for key, gate in r["gates"].items():
        lines.append(
            f"| `{key}` | {'PASS' if gate['pass'] else 'FAIL'} |"
        )

    lines += [
        "",
        "## Decision semantics",
        "",
        "A PASS confirms that the current cross-position apex trigger is real and",
        "freezes the diagnostic evidence needed to design Phase 2. It does not",
        "identify a winning calibration lever and does not authorize deployment.",
        "",
    ]
    return "\n".join(lines)

def write_outputs():
    result = build_result()
    OUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUT_MD.write_text(markdown(result).rstrip() + "\n", encoding="utf-8")

    manifest = {
        "study_id": result["study_id"],
        "phase": 1,
        "decision": result["decision"],
        "production_change_authorized": False,
        "repo_commit_sha_evaluated": result["repo_commit_sha_evaluated"],
        "preregistration_sha256": sha256(PREREG_JSON),
        "output_sha256": {
            str(PREREG_JSON.relative_to(ROOT)): sha256(PREREG_JSON),
            str(PREREG_MD.relative_to(ROOT)): sha256(PREREG_MD),
            str(SCRIPT.relative_to(ROOT)): sha256(SCRIPT),
            str(OUT_JSON.relative_to(ROOT)): sha256(OUT_JSON),
            str(OUT_MD.relative_to(ROOT)): sha256(OUT_MD),
        },
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "decision": result["decision"],
        "burns_fv": result["comparison"]["brian_burns"]["fv"],
        "allen_fv": result["comparison"]["josh_allen"]["fv"],
        "burns_to_allen_ratio": result["trigger"]["current_burns_to_allen_fv_ratio"],
        "burns_prod_mult": result["comparison"]["brian_burns"]["effective_prod_mult"],
        "allen_prod_mult": result["comparison"]["josh_allen"]["effective_prod_mult"],
        "history_projection_diagnostic": result["comparison"]["history_projection_diagnostic"],
    }, indent=2))

def selftest():
    assert js_round_positive(10.49) == 10
    assert js_round_positive(10.50) == 11
    # Exact multiplicative identity used by live FV before integer rounding.
    burns_ratio = (0.93 / 1.30) * (1.0 / 1.0) * (1.4449 / 0.918)
    assert 1.12 < burns_ratio < 1.13
    print("Cross-Position Apex Calibration V1 Phase 1 self-test PASS")

def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--selftest", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    write_outputs()

if __name__ == "__main__":
    main()
