#!/usr/bin/env python3
"""
Age Curve V2 — Phase 3 current-player shadow audit.

RESEARCH ONLY. No deployed AGE_CURVE or player value is changed.

Purpose
-------
Phase 2 showed that empirical historical age-retention curves outperform the
deployed age-policy proxy out of sample. Phase 3 applies a small candidate family
to the CURRENT player database as shadow age multipliers so we can inspect:

- player-value movement,
- position-level movement,
- rank stability,
- largest movers,
- whether tier-sensitive curves behave sensibly.

Candidate family
----------------
1. deployed_control
2. empirical_position_age_k25
3. empirical_tier_age_k25
4. empirical_tier_age_k50

Isolation rule
--------------
Players in NO_REAL_PRODUCTION_HISTORY retain their current deployed age factor
in every Age Curve V2 shadow. Rookie / no-history valuation is already being
tested separately in No-History / Rookie V2. This prevents the two research
programs from contaminating one another.

Current production tier proxy
-----------------------------
Phase 2 historical tiers were defined within position-season from current
production:
    elite >= P90
    starter P60-P90
    rotation P30-P60
    depth < P30

For the live player database, real-history players are classified the same way
using the CURRENT effective production multiplier within position. This is a
research bridge from the historical scoring scale to the deployed PM scale.

RB fractional age
-----------------
For RBs with a known birth date, empirical integer-age factors are linearly
interpolated at the current fractional age. This preserves the production
model's existing continuous-RB-age principle.

Outputs
-------
research/age-curve-v2/age_curve_v2_phase3_shadow_audit.json
research/age-curve-v2/age_curve_v2_phase3_shadow_audit.md

Usage
-----
python3 research/age-curve-v2/age_curve_v2_phase3_shadow_audit.py --selftest
python3 research/age-curve-v2/age_curve_v2_phase3_shadow_audit.py --write
python3 research/age-curve-v2/age_curve_v2_phase3_shadow_audit.py --check
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
SCRIPTS = REPO_ROOT / "scripts"

INDEX_HTML = REPO_ROOT / "index.html"
PHASE2_PATH = (
    REPO_ROOT
    / "research"
    / "age-curve-v2"
    / "age_curve_v2_phase2_candidate_evaluation.json"
)

OUTPUT_JSON = (
    REPO_ROOT
    / "research"
    / "age-curve-v2"
    / "age_curve_v2_phase3_shadow_audit.json"
)
OUTPUT_MD = (
    REPO_ROOT
    / "research"
    / "age-curve-v2"
    / "age_curve_v2_phase3_shadow_audit.md"
)

METHOD_VERSION = "age-curve-v2-phase3-shadow-audit-v1"
TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
GLOBAL_VALUE_SCALE = 55.0

VARIANTS = {
    "deployed_control": {
        "source": "deployed",
        "curve_key": None,
        "tier_sensitive": False,
    },
    "empirical_position_age_k25": {
        "source": "empirical",
        "curve_key": "k25",
        "tier_sensitive": False,
    },
    "empirical_tier_age_k25": {
        "source": "empirical",
        "curve_key": "k25",
        "tier_sensitive": True,
    },
    "empirical_tier_age_k50": {
        "source": "empirical",
        "curve_key": "k50",
        "tier_sensitive": True,
    },
}

TIER_THRESHOLDS = {
    "elite": 0.90,
    "starter": 0.60,
    "rotation": 0.30,
}
FACTOR_MIN = 0.25
FACTOR_MAX = 1.50


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path.relative_to(REPO_ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid JSON: {path.relative_to(REPO_ROOT)}: {exc}"
        ) from exc


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(float(v) for v in values)
    if len(vals) == 1:
        return vals[0]
    q = clamp(float(q), 0.0, 1.0)
    idx = (len(vals) - 1) * q
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    t = idx - lo
    return vals[lo] * (1.0 - t) + vals[hi] * t


def rankdata(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda x: (x[1], x[0]))
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


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    denom = math.sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    if denom <= 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / denom


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    return pearson(rankdata(xs), rankdata(ys))


def load_snapshot_values():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from validation import snapshot_values  # type: ignore
    return snapshot_values


def validate_phase2(phase2: dict[str, Any]) -> None:
    if phase2.get("method_version") != (
        "age-curve-v2-phase2-candidate-evaluation-v1"
    ):
        raise RuntimeError("Unexpected Age Curve Phase-2 method version")
    if phase2.get("deployment_authorized") is not False:
        raise RuntimeError("Phase 2 unexpectedly authorizes deployment")
    if phase2.get("age_curve_change_authorized") is not False:
        raise RuntimeError("Phase 2 unexpectedly authorizes AGE_CURVE change")

    curves = phase2.get("full_sample_candidate_curves")
    if not isinstance(curves, dict):
        raise RuntimeError("Phase-2 full_sample_candidate_curves missing")
    for key in ("k25", "k50"):
        if key not in curves:
            raise RuntimeError(f"Phase-2 curve family missing {key}")


def current_player_state(cfg: dict[str, Any], snapshot_values) -> dict[str, dict[str, Any]]:
    players = {}

    for player, info in cfg["player_db"].items():
        pos = info["pos"]
        if pos not in TRACKED_POSITIONS:
            continue

        role = info["role"]
        effective_pm, raw_pm = snapshot_values.production_multiplier(
            player,
            role,
            cfg["prod_mult"],
            cfg["no_real_history"],
            cfg["role_mult"],
        )

        deployed_age = snapshot_values.effective_age_multiplier(
            pos,
            info["age"],
            role,
            player,
            effective_pm,
            raw_pm,
            cfg,
        )

        value = round_value(
            cfg["position_weight"].get(pos, 1.0),
            deployed_age,
            effective_pm,
        )

        players[player] = {
            "player": player,
            "pos": pos,
            "age": info["age"],
            "role": role,
            "effective_prod_mult": float(effective_pm),
            "raw_prod_mult": (
                float(raw_pm) if isinstance(raw_pm, (int, float)) else None
            ),
            "deployed_age_mult": float(deployed_age),
            "deployed_value": int(value),
            "no_real_production_history": player in cfg["no_real_history"],
        }

    if len(players) < 500:
        raise RuntimeError(
            f"Tracked current-player cohort unexpectedly small: {len(players)}"
        )

    return players


def round_value(
    position_weight: float,
    age_mult: float,
    production_mult: float,
) -> int:
    raw = (
        100.0
        * float(position_weight)
        * float(age_mult)
        * float(production_mult)
        * GLOBAL_VALUE_SCALE
    )
    return int(math.floor(raw + 0.5))


def assign_current_tiers(players: dict[str, dict[str, Any]]) -> None:
    for pos in TRACKED_POSITIONS:
        cohort = [
            row
            for row in players.values()
            if row["pos"] == pos
            and not row["no_real_production_history"]
        ]
        values = [float(r["effective_prod_mult"]) for r in cohort]
        if not values:
            raise RuntimeError(f"No real-history production cohort for {pos}")

        p90 = percentile(values, 0.90)
        p60 = percentile(values, 0.60)
        p30 = percentile(values, 0.30)
        assert p90 is not None and p60 is not None and p30 is not None

        for row in cohort:
            value = float(row["effective_prod_mult"])
            if value >= p90:
                tier = "elite"
            elif value >= p60:
                tier = "starter"
            elif value >= p30:
                tier = "rotation"
            else:
                tier = "depth"
            row["production_tier_proxy"] = tier
            row["position_pm_percentile_thresholds"] = {
                "p90": p90,
                "p60": p60,
                "p30": p30,
            }

    for row in players.values():
        if row["no_real_production_history"]:
            row["production_tier_proxy"] = None
            row["position_pm_percentile_thresholds"] = None


def nearest_curve_age(
    age_map: dict[str, Any],
    age: int,
) -> int:
    ages = sorted(int(k) for k in age_map)
    if not ages:
        raise RuntimeError("Empty empirical age curve")
    if age in ages:
        return age
    return min(ages, key=lambda a: (abs(a - age), a))


def factor_at_integer_age(
    curve_block: dict[str, Any],
    pos: str,
    tier: str | None,
    age: int,
    tier_sensitive: bool,
) -> float:
    if tier_sensitive:
        if not tier:
            raise RuntimeError("Tier-sensitive factor requested without tier")
        age_map = (
            curve_block.get("tier_age", {})
            .get(pos, {})
            .get(tier, {})
        )
    else:
        age_map = curve_block.get("position_age", {}).get(pos, {})

    if not age_map:
        # For a sparse tier-age cell, fall back to position-age.
        age_map = curve_block.get("position_age", {}).get(pos, {})
    if not age_map:
        raise RuntimeError(f"No empirical age curve available for {pos}")

    use_age = nearest_curve_age(age_map, int(age))
    payload = age_map[str(use_age)]
    factor = float(payload["factor"])
    return clamp(factor, FACTOR_MIN, FACTOR_MAX)


def current_rb_fractional_age(
    player: str,
    fallback_age: int,
    cfg: dict[str, Any],
    snapshot_values,
) -> float:
    birth_date = cfg["rb_birth_date_data"].get(player)
    return float(
        snapshot_values.fractional_age_from_birth_date(
            birth_date,
            fallback_age,
        )
    )


def empirical_age_factor(
    player: str,
    row: dict[str, Any],
    curve_block: dict[str, Any],
    tier_sensitive: bool,
    cfg: dict[str, Any],
    snapshot_values,
) -> float:
    pos = row["pos"]
    tier = row["production_tier_proxy"]
    integer_age = int(row["age"])

    if pos != "RB":
        return factor_at_integer_age(
            curve_block,
            pos,
            tier,
            integer_age,
            tier_sensitive,
        )

    frac_age = current_rb_fractional_age(
        player,
        integer_age,
        cfg,
        snapshot_values,
    )
    lo = math.floor(frac_age)
    hi = math.ceil(frac_age)

    f_lo = factor_at_integer_age(
        curve_block,
        pos,
        tier,
        lo,
        tier_sensitive,
    )
    if hi == lo:
        return f_lo

    f_hi = factor_at_integer_age(
        curve_block,
        pos,
        tier,
        hi,
        tier_sensitive,
    )
    t = frac_age - lo
    return clamp(
        f_lo * (1.0 - t) + f_hi * t,
        FACTOR_MIN,
        FACTOR_MAX,
    )


def build_variants(
    players: dict[str, dict[str, Any]],
    phase2: dict[str, Any],
    cfg: dict[str, Any],
    snapshot_values,
) -> dict[str, Any]:
    curves = phase2["full_sample_candidate_curves"]
    variants = {}

    for variant, spec in VARIANTS.items():
        outputs = {}

        for player, row in players.items():
            if spec["source"] == "deployed":
                age_mult = float(row["deployed_age_mult"])
                source = "deployed_age_multiplier"
            elif row["no_real_production_history"]:
                age_mult = float(row["deployed_age_mult"])
                source = "deployed_age_multiplier_no_history_isolation"
            else:
                curve_block = curves[spec["curve_key"]]
                age_mult = empirical_age_factor(
                    player,
                    row,
                    curve_block,
                    bool(spec["tier_sensitive"]),
                    cfg,
                    snapshot_values,
                )
                source = (
                    "empirical_tier_age"
                    if spec["tier_sensitive"]
                    else "empirical_position_age"
                )

            value = round_value(
                cfg["position_weight"].get(row["pos"], 1.0),
                age_mult,
                row["effective_prod_mult"],
            )

            control_value = int(row["deployed_value"])
            change = value - control_value
            change_pct = (
                change / control_value if control_value else None
            )

            outputs[player] = {
                "pos": row["pos"],
                "age": row["age"],
                "role": row["role"],
                "production_tier_proxy": row["production_tier_proxy"],
                "no_real_production_history": row[
                    "no_real_production_history"
                ],
                "effective_prod_mult": row["effective_prod_mult"],
                "deployed_age_mult": row["deployed_age_mult"],
                "shadow_age_mult": float(age_mult),
                "deployed_value": control_value,
                "shadow_value": int(value),
                "change": int(change),
                "change_pct": change_pct,
                "source": source,
            }

        variants[variant] = {
            "spec": spec,
            "players": outputs,
        }

    return variants


def summarize_variant(
    variant_players: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    changed = [
        row
        for row in variant_players.values()
        if row["shadow_value"] != row["deployed_value"]
    ]
    pct_changes = [
        float(row["change_pct"])
        for row in changed
        if row["change_pct"] is not None
    ]

    by_position = {}
    for pos in TRACKED_POSITIONS:
        cohort = [
            (player, row)
            for player, row in variant_players.items()
            if row["pos"] == pos
        ]
        if not cohort:
            continue

        current_values = [float(row["deployed_value"]) for _, row in cohort]
        shadow_values = [float(row["shadow_value"]) for _, row in cohort]
        pos_changes = [
            abs(float(row["change_pct"]))
            for _, row in cohort
            if row["change_pct"] is not None
            and row["shadow_value"] != row["deployed_value"]
        ]

        current_order = [
            player
            for player, _ in sorted(
                cohort,
                key=lambda item: (
                    -item[1]["deployed_value"],
                    item[0],
                ),
            )
        ]
        shadow_order = [
            player
            for player, _ in sorted(
                cohort,
                key=lambda item: (
                    -item[1]["shadow_value"],
                    item[0],
                ),
            )
        ]
        current_rank = {
            player: i + 1 for i, player in enumerate(current_order)
        }
        shadow_rank = {
            player: i + 1 for i, player in enumerate(shadow_order)
        }
        top_n = min(24, len(cohort))
        top_overlap = len(
            set(current_order[:top_n]) & set(shadow_order[:top_n])
        )

        by_position[pos] = {
            "n": len(cohort),
            "changed_count": sum(
                1
                for _, row in cohort
                if row["shadow_value"] != row["deployed_value"]
            ),
            "median_abs_change_pct_changed": median(pos_changes),
            "spearman_deployed_vs_shadow": spearman(
                current_values,
                shadow_values,
            ),
            "top_n": top_n,
            "top_n_overlap_share": (
                top_overlap / top_n if top_n else None
            ),
            "max_absolute_rank_change": max(
                (
                    abs(current_rank[p] - shadow_rank[p])
                    for p, _ in cohort
                ),
                default=0,
            ),
        }

    movers = []
    for player, row in variant_players.items():
        if row["change_pct"] is None:
            continue
        movers.append(
            {
                "player": player,
                "pos": row["pos"],
                "age": row["age"],
                "tier": row["production_tier_proxy"],
                "deployed_age_mult": row["deployed_age_mult"],
                "shadow_age_mult": row["shadow_age_mult"],
                "deployed_value": row["deployed_value"],
                "shadow_value": row["shadow_value"],
                "change_pct": row["change_pct"],
                "source": row["source"],
            }
        )
    movers.sort(
        key=lambda r: (
            -abs(float(r["change_pct"])),
            r["player"],
        )
    )

    return {
        "player_count": len(variant_players),
        "changed_count": len(changed),
        "median_abs_change_pct_changed": median(
            [abs(x) for x in pct_changes]
        ),
        "p90_abs_change_pct_changed": percentile(
            [abs(x) for x in pct_changes],
            0.90,
        ),
        "by_position": by_position,
        "largest_absolute_movers": movers[:50],
    }


def build_result() -> dict[str, Any]:
    phase2 = read_json(PHASE2_PATH)
    validate_phase2(phase2)

    snapshot_values = load_snapshot_values()
    cfg = snapshot_values.load_from_html(INDEX_HTML)

    players = current_player_state(cfg, snapshot_values)
    assign_current_tiers(players)
    variants = build_variants(
        players,
        phase2,
        cfg,
        snapshot_values,
    )

    summaries = {
        key: summarize_variant(payload["players"])
        for key, payload in variants.items()
    }

    # Control must be byte-for-byte neutral in values.
    control_errors = [
        player
        for player, row in variants["deployed_control"]["players"].items()
        if row["deployed_value"] != row["shadow_value"]
    ]
    if control_errors:
        raise RuntimeError(
            f"Deployed control moved values: {control_errors[:10]}"
        )

    # No-history players must remain neutral in EVERY candidate.
    isolation_errors = []
    for variant, payload in variants.items():
        for player, row in payload["players"].items():
            if (
                row["no_real_production_history"]
                and row["deployed_value"] != row["shadow_value"]
            ):
                isolation_errors.append((variant, player))
    if isolation_errors:
        raise RuntimeError(
            "No-history isolation failed; sample="
            + repr(isolation_errors[:10])
        )

    return {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "generated_at_utc": now_utc(),
        "status": "RESEARCH_ONLY_CURRENT_PLAYER_AGE_SHADOW_AUDIT",
        "production_files_mutated": 0,
        "deployment_authorized": False,
        "age_curve_change_authorized": False,
        "tracked_player_count": len(players),
        "real_history_player_count": sum(
            1
            for row in players.values()
            if not row["no_real_production_history"]
        ),
        "no_history_isolated_player_count": sum(
            1
            for row in players.values()
            if row["no_real_production_history"]
        ),
        "tier_proxy": {
            "method": (
                "within current real-history players at each position: "
                "elite >= P90, starter P60-P90, rotation P30-P60, depth < P30 "
                "using deployed effective production multiplier"
            ),
            "no_history_players_classified": False,
        },
        "candidate_family": list(VARIANTS),
        "phase2_historical_monitoring": {
            "monitoring_leader": phase2.get("monitoring_leader"),
            "monitoring_leader_is_deployment_choice": phase2.get(
                "monitoring_leader_is_deployment_choice"
            ),
            "candidate_deltas_vs_controls": phase2.get(
                "candidate_deltas_vs_controls"
            ),
        },
        "variant_summaries": summaries,
        "variants": variants,
        "integrity": {
            "deployed_control_zero_movement": True,
            "no_history_zero_movement_every_variant": True,
            "all_variants_full_coverage": all(
                len(payload["players"]) == len(players)
                for payload in variants.values()
            ),
        },
        "guardrail": (
            "Phase 3 only audits current-player shadow movement. Historical "
            "out-of-sample superiority does not authorize production deployment."
        ),
        "phase4_handoff": (
            "If current-player movement is stable and position/tier behavior is "
            "sensible, freeze the surviving age candidates before 2026 evidence "
            "and grade them prospectively against future realized outcomes."
        ),
    }


def pct(value: Any) -> str:
    if value is None:
        return "—"
    return f"{100.0 * float(value):.1f}%"


def signed_pct(value: Any) -> str:
    if value is None:
        return "—"
    return f"{100.0 * float(value):+.1f}%"


def fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Age Curve V2 — Phase 3 Current-Player Shadow Audit",
        "",
        f"Method: `{result['method_version']}`  ",
        f"Status: **`{result['status']}`**",
        "",
        "## Guardrail",
        "",
        "**Research only. No deployed AGE_CURVE or player value is changed.**",
        "",
        f"- Tracked players: **{result['tracked_player_count']}**",
        f"- Real-history players eligible for empirical age shadow: "
        f"**{result['real_history_player_count']}**",
        f"- No-history players isolated at deployed age factor: "
        f"**{result['no_history_isolated_player_count']}**",
        "",
        "## Candidate movement",
        "",
        "| Variant | Changed | Median abs Δ | P90 abs Δ |",
        "|---|---:|---:|---:|",
    ]

    for variant in result["candidate_family"]:
        row = result["variant_summaries"][variant]
        lines.append(
            f"| `{variant}` | {row['changed_count']} | "
            f"{pct(row['median_abs_change_pct_changed'])} | "
            f"{pct(row['p90_abs_change_pct_changed'])} |"
        )

    lines.extend(
        [
            "",
            "## Position-level rank stability",
            "",
            "| Variant | Pos | N | Changed | Median abs Δ | Spearman | "
            "Top-24 overlap | Max rank move |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for variant in result["candidate_family"]:
        if variant == "deployed_control":
            continue
        for pos in TRACKED_POSITIONS:
            row = result["variant_summaries"][variant]["by_position"][pos]
            lines.append(
                f"| `{variant}` | {pos} | {row['n']} | "
                f"{row['changed_count']} | "
                f"{pct(row['median_abs_change_pct_changed'])} | "
                f"{fmt(row['spearman_deployed_vs_shadow'], 4)} | "
                f"{pct(row['top_n_overlap_share'])} | "
                f"{row['max_absolute_rank_change']} |"
            )

    for variant in (
        "empirical_tier_age_k25",
        "empirical_tier_age_k50",
        "empirical_position_age_k25",
    ):
        lines.extend(
            [
                "",
                f"## Largest movers — `{variant}`",
                "",
                "| Player | Pos | Age | Tier | Deployed age | Shadow age | "
                "Current | Shadow | Change |",
                "|---|---|---:|---|---:|---:|---:|---:|---:|",
            ]
        )
        movers = result["variant_summaries"][variant][
            "largest_absolute_movers"
        ][:25]
        for row in movers:
            lines.append(
                f"| {row['player']} | {row['pos']} | {row['age']} | "
                f"{row['tier'] or 'no-history'} | "
                f"{fmt(row['deployed_age_mult'])} | "
                f"{fmt(row['shadow_age_mult'])} | "
                f"{row['deployed_value']} | {row['shadow_value']} | "
                f"{signed_pct(row['change_pct'])} |"
            )

    lines.extend(
        [
            "",
            "## Integrity",
            "",
            "- Deployed control zero movement: **PASS**",
            "- No-history players zero movement in every candidate: **PASS**",
            "- Full tracked-player coverage in every variant: **PASS**",
            "",
            "## Next step",
            "",
            result["phase4_handoff"],
            "",
        ]
    )

    return "\n".join(lines)


def write_outputs(result: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUTPUT_MD.write_text(render_markdown(result), encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")


def check_outputs() -> None:
    result = read_json(OUTPUT_JSON)

    if result.get("method_version") != METHOD_VERSION:
        raise RuntimeError("Age Curve Phase-3 method_version mismatch")
    if result.get("production_files_mutated") != 0:
        raise RuntimeError("Phase 3 lost production mutation guardrail")
    if result.get("deployment_authorized") is not False:
        raise RuntimeError("Phase 3 unexpectedly authorizes deployment")
    if result.get("age_curve_change_authorized") is not False:
        raise RuntimeError("Phase 3 unexpectedly authorizes AGE_CURVE change")

    if int(result.get("tracked_player_count") or 0) < 500:
        raise RuntimeError("Phase-3 tracked cohort is implausibly small")

    integrity = result.get("integrity") or {}
    if not integrity.get("deployed_control_zero_movement"):
        raise RuntimeError("Deployed control movement integrity failed")
    if not integrity.get("no_history_zero_movement_every_variant"):
        raise RuntimeError("No-history isolation integrity failed")
    if not integrity.get("all_variants_full_coverage"):
        raise RuntimeError("Variant full-coverage integrity failed")

    names = set((result.get("variants") or {}).keys())
    if names != set(VARIANTS):
        raise RuntimeError("Age Curve Phase-3 variant family mismatch")

    if not OUTPUT_MD.exists():
        raise RuntimeError("Phase-3 markdown report missing")
    text = OUTPUT_MD.read_text(encoding="utf-8")
    for marker in (
        "Research only",
        "Candidate movement",
        "Position-level rank stability",
        "Largest movers",
        "No-history players zero movement",
    ):
        if marker not in text:
            raise RuntimeError(f"Phase-3 markdown missing marker: {marker}")

    print("Age Curve V2 Phase-3 outputs passed guardrails.")


def run_selftest() -> None:
    age_map = {
        "23": {"factor": 1.10, "n": 20},
        "24": {"factor": 1.00, "n": 20},
        "26": {"factor": 0.80, "n": 20},
    }
    block = {
        "position_age": {"RB": age_map},
        "tier_age": {"RB": {"starter": age_map}},
    }

    assert nearest_curve_age(age_map, 25) == 24
    f = factor_at_integer_age(
        block,
        "RB",
        "starter",
        23,
        True,
    )
    assert abs(f - 1.10) < 1e-9

    assert round_value(1.0, 1.0, 1.0) == 5500
    assert clamp(2.0, FACTOR_MIN, FACTOR_MAX) == FACTOR_MAX
    assert clamp(0.1, FACTOR_MIN, FACTOR_MAX) == FACTOR_MIN

    assert abs(spearman([1, 2, 3], [10, 20, 30]) - 1.0) < 1e-9

    print(
        "Age Curve V2 Phase-3 self-test passed: curve lookup, value rounding, "
        "factor bounds, and rank metric."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    if args.check:
        check_outputs()
        return

    result = build_result()

    if args.write:
        write_outputs(result)
    else:
        print(render_markdown(result))


if __name__ == "__main__":
    main()
