#!/usr/bin/env python3
"""
Young RB Age Sensitivity Audit
==============================

READ-ONLY research audit for the deployed Trade Desk age model.

Purpose
-------
Quantify the live trade-value leverage of the elite-young-RB youth premium
before proposing any production change.

This script:
1. Parses CURRENT production constants/player data from index.html through
   scripts/validation/snapshot_values.py.
2. Identifies every current RB age 21-25 and the exact subset that qualifies
   for the live youth-premium override:
       pos == RB
       role == Elite
       age <= 25
       raw PROD_MULT_DATA >= 0.65
3. Recomputes final Fundamental Value under a coefficient sweep:
       0.000, 0.250, 0.300, 0.340, 0.384, 0.430, 0.480
4. Measures RB positional-rank movement.
5. Runs a same-player-one-year-older shock with production/role held fixed.
6. Joins current Market Value when available as context only.
7. Writes research-only JSON + Markdown reports.

It does NOT modify index.html, PLAYER_DB, PROD_MULT_DATA, AGE_CURVE, any frozen
release, or any generated production artifact.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DIR = REPO_ROOT / "scripts" / "validation"
if str(VALIDATION_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATION_DIR))

import snapshot_values

INDEX_PATH = REPO_ROOT / "index.html"
MARKET_PATH = REPO_ROOT / "scripts" / "artifacts" / "generated" / "market_values.json"
OUT_JSON = REPO_ROOT / "research" / "age-calibration" / "young_rb_age_sensitivity.json"
OUT_MD = REPO_ROOT / "research" / "age-calibration" / "young_rb_age_sensitivity.md"

CURRENT_COEFFICIENT = 0.384
COEFFICIENTS = [0.0, 0.25, 0.30, 0.34, CURRENT_COEFFICIENT, 0.43, 0.48]
YOUNG_RB_MIN_AGE = 21
YOUNG_RB_MAX_AGE = 25
PREMIUM_MIN_RAW_PROD = 0.65


def js_round_positive(value: float) -> int:
    return math.floor(value + 0.5)


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    x = (len(vals) - 1) * q
    lo = math.floor(x)
    hi = math.ceil(x)
    if lo == hi:
        return vals[lo]
    return vals[lo] + (vals[hi] - vals[lo]) * (x - lo)


def load_market_values() -> dict[str, dict[str, Any]]:
    if not MARKET_PATH.exists():
        return {}
    try:
        doc = json.loads(MARKET_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    players = doc.get("players")
    return players if isinstance(players, dict) else {}


def production_for_player(key: str, info: dict[str, Any], cfg: dict[str, Any]):
    rm, raw_rm = snapshot_values.production_multiplier(
        key, info["role"], cfg["prod_mult"], cfg["no_real_history"], cfg["role_mult"]
    )
    return float(rm), (float(raw_rm) if isinstance(raw_rm, (int, float)) else None)


def qualifies_for_live_youth_premium(pos, age, role, raw_production):
    return (
        pos == "RB"
        and role == "Elite"
        and age <= 25
        and isinstance(raw_production, (int, float))
        and raw_production >= PREMIUM_MIN_RAW_PROD
    )


def age_multiplier_with_rb_coefficient(
    *, pos, age, role, effective_production, raw_production, cfg, rb_youth_coefficient
):
    age_curve = cfg["age_curve"]
    c = age_curve.get(pos, age_curve["WR"])

    if pos == "K":
        return 0.5

    if age <= c["peakEnd"]:
        if isinstance(effective_production, (int, float)):
            lo, hi = 0.15, 1.55
            ratio = max(0.0, min(1.0, (effective_production - lo) / (hi - lo)))
            pre_floor = 0.55 + ratio * (0.98 - 0.55)
        else:
            pre_floor = 0.725 if role == "Elite" else 0.55

        denom = c["peakStart"] - 21
        t = max(0.0, (age - 21) / denom) if denom else 0.0
        pre_floor_base = pre_floor + t * (1.0 - pre_floor)
        base = pre_floor_base if age <= c["peakStart"] else 1.0

        if qualifies_for_live_youth_premium(pos, age, role, raw_production):
            years_of_upside = min(4, max(0, c["peakEnd"] - age))
            youth_bonus = rb_youth_coefficient * math.sqrt(years_of_upside)
            flat_base = 0.725 if age <= c["peakStart"] else 1.0
            return min(1.5, flat_base + youth_bonus)
        return base

    decline_span = c["floor"] - c["peakEnd"]
    t = max(0.0, min(1.0, (age - c["peakEnd"]) / decline_span)) if decline_span else 1.0

    if pos == "QB":
        qb_floor = cfg["qb_post_peak_floor"]
        return max(qb_floor, 1.0 - t * (1.0 - qb_floor))
    if pos == "LB":
        power = cfg["lb_post_peak_decay_power"]
        return max(0.62, 1.0 - 0.38 * math.pow(t, power))
    return max(0.62, 1.0 - t * 0.38)


def value_from_components(*, pos, age_mult, prod_mult, cfg):
    pw = float(cfg["position_weight"].get(pos, 1.0))
    return js_round_positive(100.0 * pw * age_mult * prod_mult * 55.0)


def compute_scenario(cfg, coefficient):
    out = {}
    for key, info in cfg["player_db"].items():
        pos, age, role = info["pos"], int(info["age"]), info["role"]
        rm, raw_rm = production_for_player(key, info, cfg)
        am = age_multiplier_with_rb_coefficient(
            pos=pos,
            age=age,
            role=role,
            effective_production=rm,
            raw_production=raw_rm,
            cfg=cfg,
            rb_youth_coefficient=coefficient,
        )
        value = value_from_components(pos=pos, age_mult=am, prod_mult=rm, cfg=cfg)
        out[key] = {
            "pos": pos,
            "age": age,
            "role": role,
            "prod_mult": rm,
            "raw_prod_mult": raw_rm,
            "age_mult": am,
            "value": value,
            "qualifies_for_live_youth_premium": qualifies_for_live_youth_premium(
                pos, age, role, raw_rm
            ),
        }

    rb_order = sorted(
        (key for key, row in out.items() if row["pos"] == "RB"),
        key=lambda key: (-out[key]["value"], key),
    )
    for rank, key in enumerate(rb_order, start=1):
        out[key]["rb_rank"] = rank
    return out


def one_year_older_shock(key, row, cfg):
    older_age = int(row["age"]) + 1
    older_am = age_multiplier_with_rb_coefficient(
        pos=row["pos"],
        age=older_age,
        role=row["role"],
        effective_production=row["prod_mult"],
        raw_production=row["raw_prod_mult"],
        cfg=cfg,
        rb_youth_coefficient=CURRENT_COEFFICIENT,
    )
    older_value = value_from_components(
        pos=row["pos"], age_mult=older_am, prod_mult=row["prod_mult"], cfg=cfg
    )
    current_value = int(row["value"])
    delta = older_value - current_value
    pct = delta / current_value if current_value else None
    return {
        "player": key,
        "age_now": row["age"],
        "age_plus_one": older_age,
        "age_mult_now": round(row["age_mult"], 6),
        "age_mult_plus_one": round(older_am, 6),
        "value_now": current_value,
        "value_plus_one": older_value,
        "delta_points": delta,
        "delta_pct": round(pct, 6) if pct is not None else None,
    }


def summarize_deltas(rows):
    abs_points = [abs(float(r["delta_points"])) for r in rows]
    abs_pct = [abs(float(r["delta_pct"])) for r in rows if r["delta_pct"] is not None]
    rank_move = [abs(int(r["rank_move"])) for r in rows]
    return {
        "n": len(rows),
        "median_abs_points": round(statistics.median(abs_points), 2) if abs_points else None,
        "p90_abs_points": round(percentile(abs_points, 0.90), 2) if abs_points else None,
        "max_abs_points": round(max(abs_points), 2) if abs_points else None,
        "median_abs_pct": round(statistics.median(abs_pct), 6) if abs_pct else None,
        "p90_abs_pct": round(percentile(abs_pct, 0.90), 6) if abs_pct else None,
        "max_abs_pct": round(max(abs_pct), 6) if abs_pct else None,
        "max_abs_rb_rank_move": max(rank_move) if rank_move else 0,
    }


def build_report():
    cfg = snapshot_values.load_from_html(INDEX_PATH)
    market = load_market_values()
    scenarios = {coeff: compute_scenario(cfg, coeff) for coeff in COEFFICIENTS}
    current = scenarios[CURRENT_COEFFICIENT]

    young_rb_keys = sorted(
        key
        for key, row in current.items()
        if row["pos"] == "RB"
        and YOUNG_RB_MIN_AGE <= int(row["age"]) <= YOUNG_RB_MAX_AGE
    )
    premium_keys = [
        key for key in young_rb_keys if current[key]["qualifies_for_live_youth_premium"]
    ]

    scenario_reports = {}
    for coeff in COEFFICIENTS:
        scenario = scenarios[coeff]
        rows = []
        for key in premium_keys:
            base, alt = current[key], scenario[key]
            delta = int(alt["value"]) - int(base["value"])
            pct = delta / base["value"] if base["value"] else None
            market_row = market.get(key) if isinstance(market.get(key), dict) else {}
            rows.append({
                "player": key,
                "age": base["age"],
                "role": base["role"],
                "raw_prod_mult": base["raw_prod_mult"],
                "current_age_mult": round(base["age_mult"], 6),
                "scenario_age_mult": round(alt["age_mult"], 6),
                "current_value": base["value"],
                "scenario_value": alt["value"],
                "delta_points": delta,
                "delta_pct": round(pct, 6) if pct is not None else None,
                "current_rb_rank": base["rb_rank"],
                "scenario_rb_rank": alt["rb_rank"],
                "rank_move": int(base["rb_rank"]) - int(alt["rb_rank"]),
                "market_value": market_row.get("market_value"),
                "market_rating": market_row.get("market_rating"),
            })
        rows.sort(key=lambda r: (-abs(r["delta_points"]), r["player"]))
        scenario_reports[f"{coeff:.3f}"] = {
            "coefficient": coeff,
            "summary": summarize_deltas(rows),
            "players": rows,
        }

    aging_shocks = [one_year_older_shock(key, current[key], cfg) for key in young_rb_keys]
    aging_shocks.sort(
        key=lambda r: (-abs(r["delta_pct"] or 0.0), -abs(r["delta_points"]), r["player"])
    )

    cohort = []
    for key in young_rb_keys:
        row = current[key]
        market_row = market.get(key) if isinstance(market.get(key), dict) else {}
        cohort.append({
            "player": key,
            "age": row["age"],
            "role": row["role"],
            "prod_mult": round(row["prod_mult"], 6),
            "raw_prod_mult": round(row["raw_prod_mult"], 6)
            if isinstance(row["raw_prod_mult"], (int, float))
            else None,
            "age_mult": round(row["age_mult"], 6),
            "fundamental_value": row["value"],
            "rb_rank": row["rb_rank"],
            "qualifies_for_live_youth_premium": row["qualifies_for_live_youth_premium"],
            "market_value": market_row.get("market_value"),
            "market_rating": market_row.get("market_rating"),
            "market_rank": market_row.get("market_rank"),
        })
    cohort.sort(key=lambda r: (-r["fundamental_value"], r["player"]))

    return {
        "audit": "young-rb-age-sensitivity-v1",
        "production_changes": False,
        "live_rb_youth_coefficient": CURRENT_COEFFICIENT,
        "coefficient_sweep": COEFFICIENTS,
        "live_qualification_rule": {
            "position": "RB",
            "role": "Elite",
            "max_age": 25,
            "minimum_raw_prod_mult": PREMIUM_MIN_RAW_PROD,
        },
        "counts": {
            "young_rb_age_21_25": len(young_rb_keys),
            "live_premium_qualifiers": len(premium_keys),
            "market_rows_joined_for_young_rbs": sum(
                1 for key in young_rb_keys if isinstance(market.get(key), dict)
            ),
        },
        "young_rb_cohort": cohort,
        "coefficient_scenarios_vs_current": scenario_reports,
        "one_year_older_shocks_current_formula": aging_shocks,
    }


def pct_text(value):
    return "n/a" if value is None else f"{100.0 * value:+.1f}%"


def write_markdown(report):
    lines = [
        "# Young RB Age Sensitivity Audit",
        "",
        "**Status:** research-only; no production values changed.",
        "",
        "## Audit question",
        "",
        "How much can the current elite-young-RB age premium move real Fundamental Values, "
        "RB ranks, and one-year age transitions before we decide whether the curve should be recalibrated?",
        "",
        "## Live rule being audited",
        "",
        "```text",
        "position = RB",
        "role = Elite",
        "age <= 25",
        "raw PROD_MULT_DATA >= 0.65",
        "youth_bonus = 0.384 × sqrt(peakEnd - age)",
        "```",
        "",
        f"- Current young RBs age 21-25: **{report['counts']['young_rb_age_21_25']}**",
        f"- Current premium qualifiers: **{report['counts']['live_premium_qualifiers']}**",
        f"- Young RBs with Market Value context: **{report['counts']['market_rows_joined_for_young_rbs']}**",
        "",
        "## Current young-RB cohort",
        "",
        "| Player | Age | Role | Raw PM | Age mult | Fundamental | RB rank | Premium? | Market |",
        "|---|---:|---|---:|---:|---:|---:|---|---:|",
    ]

    for row in report["young_rb_cohort"]:
        raw_pm = "n/a" if row["raw_prod_mult"] is None else f"{row['raw_prod_mult']:.3f}"
        market = "n/a" if row["market_value"] is None else str(row["market_value"])
        lines.append(
            f"| {row['player']} | {row['age']} | {row['role']} | {raw_pm} | "
            f"{row['age_mult']:.3f} | {row['fundamental_value']} | {row['rb_rank']} | "
            f"{'yes' if row['qualifies_for_live_youth_premium'] else 'no'} | {market} |"
        )

    lines += [
        "",
        "## Coefficient sensitivity",
        "",
        "Every scenario keeps position, production, role, and every non-age model input fixed.",
        "",
        "| Coefficient | N | Median abs move | P90 abs move | Max abs move | Median abs % | P90 abs % | Max abs % | Max RB-rank move |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for key in [f"{c:.3f}" for c in COEFFICIENTS]:
        block = report["coefficient_scenarios_vs_current"][key]
        s = block["summary"]
        lines.append(
            f"| {block['coefficient']:.3f} | {s['n']} | {s['median_abs_points']} | "
            f"{s['p90_abs_points']} | {s['max_abs_points']} | "
            f"{pct_text(s['median_abs_pct'])} | {pct_text(s['p90_abs_pct'])} | "
            f"{pct_text(s['max_abs_pct'])} | {s['max_abs_rb_rank_move']} |"
        )

    lines += [
        "",
        "### Largest movers with the youth premium removed",
        "",
        "| Player | Age | Current | No premium | Delta | Delta % | RB rank now | RB rank no premium | Market |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["coefficient_scenarios_vs_current"]["0.000"]["players"][:20]:
        market = "n/a" if row["market_value"] is None else str(row["market_value"])
        lines.append(
            f"| {row['player']} | {row['age']} | {row['current_value']} | "
            f"{row['scenario_value']} | {row['delta_points']:+d} | {pct_text(row['delta_pct'])} | "
            f"{row['current_rb_rank']} | {row['scenario_rb_rank']} | {market} |"
        )

    lines += [
        "",
        "## One-year aging shock under the CURRENT formula",
        "",
        "Production and role are held fixed; only age changes by +1.",
        "",
        "| Player | Age → Age+1 | Age mult now | Age mult +1 | Value now | Value +1 | Delta | Delta % |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["one_year_older_shocks_current_formula"][:30]:
        lines.append(
            f"| {row['player']} | {row['age_now']} → {row['age_plus_one']} | "
            f"{row['age_mult_now']:.3f} | {row['age_mult_plus_one']:.3f} | "
            f"{row['value_now']} | {row['value_plus_one']} | {row['delta_points']:+d} | "
            f"{pct_text(row['delta_pct'])} |"
        )

    lines += [
        "",
        "## Interpretation boundary",
        "",
        "This measures **leverage, not truth**. Large movement proves the age assumption is consequential; "
        "it does not prove a different coefficient is more accurate.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_selftest():
    cfg = {
        "age_curve": {
            "RB": {"peakStart": 23, "peakEnd": 25, "floor": 30},
            "WR": {"peakStart": 24, "peakEnd": 28, "floor": 33},
        },
        "position_weight": {"RB": 0.89},
        "qb_post_peak_floor": 0.546,
        "lb_post_peak_decay_power": 0.5,
    }

    assert qualifies_for_live_youth_premium("RB", 24, "Elite", 0.65)
    assert not qualifies_for_live_youth_premium("RB", 24, "Starter", 0.90)
    assert not qualifies_for_live_youth_premium("RB", 24, "Elite", 0.649)

    am_24 = age_multiplier_with_rb_coefficient(
        pos="RB", age=24, role="Elite", effective_production=1.0,
        raw_production=1.0, cfg=cfg, rb_youth_coefficient=0.384
    )
    assert abs(am_24 - 1.384) < 1e-12

    am_25 = age_multiplier_with_rb_coefficient(
        pos="RB", age=25, role="Elite", effective_production=1.0,
        raw_production=1.0, cfg=cfg, rb_youth_coefficient=0.384
    )
    assert abs(am_25 - 1.0) < 1e-12

    no_premium = age_multiplier_with_rb_coefficient(
        pos="RB", age=24, role="Elite", effective_production=1.0,
        raw_production=1.0, cfg=cfg, rb_youth_coefficient=0.0
    )
    assert abs(no_premium - 1.0) < 1e-12

    print("young_rb_age_sensitivity_audit self-test passed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    report = build_report()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_markdown(report)
    print(OUT_MD.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
