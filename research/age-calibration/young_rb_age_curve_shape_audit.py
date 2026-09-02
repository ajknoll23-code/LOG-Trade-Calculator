#!/usr/bin/env python3
"""
Young RB Age-Curve Shape Audit
==============================

READ-ONLY follow-up to young_rb_age_sensitivity_audit.py.

Question
--------
The first sensitivity audit proved that the deployed elite-young-RB override is
high-leverage. This audit asks whether the SHAPE itself is structurally sound.

It compares the deployed curve with three continuity-constrained alternatives.
All alternatives:
- preserve the deployed age-21 elite-RB ceiling implied by coefficient 0.384;
- end exactly at age multiplier 1.0 at age 25;
- are monotone non-increasing from age 21 through 25;
- do not change production, role, position weight, or any non-age input.

Candidates
----------
current
    Exact deployed formula.

linear_to_25
    Linearly tapers the age-21 premium to zero by age 25.

smoothstep_to_25
    Uses cubic smoothstep 3x^2-2x^3 for a gentler endpoint taper.

quadratic_to_25
    Uses x^2, strongly reducing the age-24 cliff.

Market Value is used only as an external rank diagnostic. It is NOT treated as
fundamental truth and is not fitted directly.

Outputs are research-only.
"""

from __future__ import annotations

import argparse
import json
import math
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
OUT_JSON = REPO_ROOT / "research" / "age-calibration" / "young_rb_age_curve_shape_audit.json"
OUT_MD = REPO_ROOT / "research" / "age-calibration" / "young_rb_age_curve_shape_audit.md"

CURRENT_COEFF = 0.384
MIN_RAW_PM = 0.65
YOUNG_MIN_AGE = 21
YOUNG_MAX_AGE = 25
CANDIDATES = ("current", "linear_to_25", "smoothstep_to_25", "quadratic_to_25")


def js_round_positive(x: float) -> int:
    return math.floor(x + 0.5)


def load_market() -> dict[str, dict[str, Any]]:
    if not MARKET_PATH.exists():
        return {}
    try:
        doc = json.loads(MARKET_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    players = doc.get("players")
    return players if isinstance(players, dict) else {}


def qualifies(pos: str, age: int, role: str, raw_pm: float | None) -> bool:
    return (
        pos == "RB"
        and role == "Elite"
        and age <= 25
        and isinstance(raw_pm, (int, float))
        and raw_pm >= MIN_RAW_PM
    )


def live_current_elite_rb_am(age: int, peak_start: int = 23, peak_end: int = 25) -> float:
    years = min(4, max(0, peak_end - age))
    bonus = CURRENT_COEFF * math.sqrt(years)
    flat_base = 0.725 if age <= peak_start else 1.0
    return min(1.5, flat_base + bonus)


# The deployed age-21 premium is the common anchor for all smooth candidates.
DEPLOYED_AGE21_AM = live_current_elite_rb_am(21)
MAX_PREMIUM = DEPLOYED_AGE21_AM - 1.0


def normalized_age_x(age: int) -> float:
    # age 21 -> 1.0; age 25 -> 0.0
    return max(0.0, min(1.0, (25.0 - age) / 4.0))


def candidate_elite_rb_am(age: int, candidate: str) -> float:
    if candidate == "current":
        return live_current_elite_rb_am(age)

    if age >= 25:
        return 1.0
    if age <= 21:
        return DEPLOYED_AGE21_AM

    x = normalized_age_x(age)

    if candidate == "linear_to_25":
        shape = x
    elif candidate == "smoothstep_to_25":
        shape = 3.0 * x * x - 2.0 * x * x * x
    elif candidate == "quadratic_to_25":
        shape = x * x
    else:
        raise ValueError(f"Unknown candidate: {candidate}")

    return 1.0 + MAX_PREMIUM * shape


def effective_prod(key: str, info: dict[str, Any], cfg: dict[str, Any]) -> tuple[float, float | None]:
    rm, raw = snapshot_values.production_multiplier(
        key, info["role"], cfg["prod_mult"], cfg["no_real_history"], cfg["role_mult"]
    )
    return float(rm), float(raw) if isinstance(raw, (int, float)) else None


def scenario_age_mult(
    *,
    key: str,
    info: dict[str, Any],
    rm: float,
    raw_pm: float | None,
    cfg: dict[str, Any],
    candidate: str,
) -> float:
    if qualifies(info["pos"], int(info["age"]), info["role"], raw_pm):
        return candidate_elite_rb_am(int(info["age"]), candidate)

    # Non-qualifiers remain EXACT current production behavior.
    return snapshot_values.age_multiplier(
        info["pos"], int(info["age"]), info["role"], rm, raw_pm, cfg
    )


def compute_values(cfg: dict[str, Any], candidate: str) -> dict[str, dict[str, Any]]:
    out = {}
    for key, info in cfg["player_db"].items():
        rm, raw_pm = effective_prod(key, info, cfg)
        am = scenario_age_mult(
            key=key,
            info=info,
            rm=rm,
            raw_pm=raw_pm,
            cfg=cfg,
            candidate=candidate,
        )
        pw = float(cfg["position_weight"].get(info["pos"], 1.0))
        value = js_round_positive(100.0 * pw * am * rm * 55.0)
        out[key] = {
            "pos": info["pos"],
            "age": int(info["age"]),
            "role": info["role"],
            "rm": rm,
            "raw_pm": raw_pm,
            "am": am,
            "value": value,
            "qualifies": qualifies(info["pos"], int(info["age"]), info["role"], raw_pm),
        }

    rb_keys = sorted(
        (k for k, r in out.items() if r["pos"] == "RB"),
        key=lambda k: (-out[k]["value"], k),
    )
    for rank, key in enumerate(rb_keys, start=1):
        out[key]["rb_rank"] = rank
    return out


def rankdata(values: list[float], reverse: bool = False) -> list[float]:
    """Average ranks for ties; 1 is best if reverse=True."""
    indexed = list(enumerate(values))
    indexed.sort(key=lambda t: (-t[1], t[0]) if reverse else (t[1], t[0]))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg
        i = j
    return ranks


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    if den == 0:
        return None
    return sum(x * y for x, y in zip(dx, dy)) / den


def spearman_from_values(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    return pearson(rankdata(xs, reverse=True), rankdata(ys, reverse=True))


def curve_diagnostics(candidate: str) -> dict[str, Any]:
    profile = [{"age": age, "age_mult": candidate_elite_rb_am(age, candidate)}
               for age in range(21, 26)]
    transitions = []
    monotone = True
    max_abs = 0.0
    for left, right in zip(profile, profile[1:]):
        delta = right["age_mult"] - left["age_mult"]
        pct = delta / left["age_mult"]
        if delta > 1e-12:
            monotone = False
        max_abs = max(max_abs, abs(pct))
        transitions.append({
            "from_age": left["age"],
            "to_age": right["age"],
            "from_am": round(left["age_mult"], 6),
            "to_am": round(right["age_mult"], 6),
            "delta_am": round(delta, 6),
            "delta_pct": round(pct, 6),
        })
    return {
        "profile": [{"age": r["age"], "age_mult": round(r["age_mult"], 6)} for r in profile],
        "monotone_nonincreasing": monotone,
        "max_abs_one_year_pct": round(max_abs, 6),
        "transitions": transitions,
    }


def build_report() -> dict[str, Any]:
    cfg = snapshot_values.load_from_html(INDEX_PATH)
    market = load_market()
    scenarios = {name: compute_values(cfg, name) for name in CANDIDATES}
    current = scenarios["current"]

    young_rb_keys = sorted(
        key for key, row in current.items()
        if row["pos"] == "RB" and YOUNG_MIN_AGE <= row["age"] <= YOUNG_MAX_AGE
    )
    premium_keys = [key for key in young_rb_keys if current[key]["qualifies"]]

    candidate_blocks = {}
    for candidate, rows in scenarios.items():
        affected = []
        for key in premium_keys:
            base = current[key]
            alt = rows[key]
            delta = alt["value"] - base["value"]
            affected.append({
                "player": key,
                "age": base["age"],
                "raw_pm": round(base["raw_pm"], 6) if base["raw_pm"] is not None else None,
                "current_value": base["value"],
                "candidate_value": alt["value"],
                "delta_points": delta,
                "delta_pct": round(delta / base["value"], 6) if base["value"] else None,
                "current_rb_rank": base["rb_rank"],
                "candidate_rb_rank": alt["rb_rank"],
                "rank_move": base["rb_rank"] - alt["rb_rank"],
                "current_am": round(base["am"], 6),
                "candidate_am": round(alt["am"], 6),
                "market_value": (market.get(key) or {}).get("market_value")
                    if isinstance(market.get(key), dict) else None,
            })
        affected.sort(key=lambda r: (-abs(r["delta_points"]), r["player"]))

        market_pairs = []
        for key in young_rb_keys:
            m = market.get(key)
            if not isinstance(m, dict) or not isinstance(m.get("market_value"), (int, float)):
                continue
            market_pairs.append((rows[key]["value"], float(m["market_value"])))

        candidate_blocks[candidate] = {
            "curve": curve_diagnostics(candidate),
            "affected_players": affected,
            "young_rb_market_rank_spearman": round(
                spearman_from_values(
                    [p[0] for p in market_pairs],
                    [p[1] for p in market_pairs],
                ), 6
            ) if len(market_pairs) >= 3 else None,
            "market_comparison_n": len(market_pairs),
        }

    return {
        "audit": "young-rb-age-curve-shape-v1",
        "production_changes": False,
        "design_boundary": (
            "Market Value is rank diagnostic only; candidates are continuity-constrained "
            "and are not fitted to market point values."
        ),
        "anchors": {
            "current_coefficient": CURRENT_COEFF,
            "deployed_age21_age_mult": round(DEPLOYED_AGE21_AM, 6),
            "common_candidate_age21_age_mult": round(DEPLOYED_AGE21_AM, 6),
            "common_candidate_age25_age_mult": 1.0,
        },
        "counts": {
            "young_rb_age_21_25": len(young_rb_keys),
            "live_premium_qualifiers": len(premium_keys),
        },
        "candidates": candidate_blocks,
    }


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100*x:+.1f}%"


def write_md(report: dict[str, Any]) -> None:
    lines = [
        "# Young RB Age-Curve Shape Audit",
        "",
        "**Status:** research-only; no production values changed.",
        "",
        "## What changed from the first audit",
        "",
        "The first audit established leverage. This follow-up tests whether the deployed elite-RB "
        "age curve has an avoidable shape/discontinuity problem.",
        "",
        "All smooth candidates preserve the deployed age-21 multiplier and end at exactly 1.0 at age 25.",
        "Market Value is used only as an external rank diagnostic.",
        "",
        "## Synthetic elite-RB age profiles",
        "",
        "| Candidate | Age 21 | Age 22 | Age 23 | Age 24 | Age 25 | Monotone? | Largest 1-year swing |",
        "|---|---:|---:|---:|---:|---:|---|---:|",
    ]

    for name in CANDIDATES:
        c = report["candidates"][name]["curve"]
        vals = {r["age"]: r["age_mult"] for r in c["profile"]}
        lines.append(
            f"| {name} | {vals[21]:.3f} | {vals[22]:.3f} | {vals[23]:.3f} | "
            f"{vals[24]:.3f} | {vals[25]:.3f} | "
            f"{'yes' if c['monotone_nonincreasing'] else 'NO'} | "
            f"{pct(c['max_abs_one_year_pct'])} |"
        )

    lines += [
        "",
        "## Market-rank diagnostic across current young RBs",
        "",
        "This is **not** a truth score. Higher Spearman means the candidate's young-RB ordering is "
        "more consistent with current league Market Value ordering for players with coverage.",
        "",
        "| Candidate | N with market | Spearman |",
        "|---|---:|---:|",
    ]
    for name in CANDIDATES:
        b = report["candidates"][name]
        s = "n/a" if b["young_rb_market_rank_spearman"] is None else f"{b['young_rb_market_rank_spearman']:.3f}"
        lines.append(f"| {name} | {b['market_comparison_n']} | {s} |")

    for name in CANDIDATES:
        lines += [
            "",
            f"## {name}",
            "",
            "| Player | Age | Current AM | Candidate AM | Current value | Candidate value | Delta | Delta % | Current RB rank | Candidate RB rank | Market |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for r in report["candidates"][name]["affected_players"]:
            market = "n/a" if r["market_value"] is None else str(r["market_value"])
            lines.append(
                f"| {r['player']} | {r['age']} | {r['current_am']:.3f} | {r['candidate_am']:.3f} | "
                f"{r['current_value']} | {r['candidate_value']} | {r['delta_points']:+d} | "
                f"{pct(r['delta_pct'])} | {r['current_rb_rank']} | {r['candidate_rb_rank']} | {market} |"
            )

    lines += [
        "",
        "## Interpretation boundary",
        "",
        "A candidate is not production-ready merely because it is smoother or tracks market rank better. "
        "The purpose here is to identify whether the current curve contains a structural artifact worth "
        "replacing, and which candidate families deserve real calibration next.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def run_selftest() -> None:
    # Deployed profile should expose the known non-monotonic age-23 -> age-24 bump.
    cur = curve_diagnostics("current")
    assert cur["monotone_nonincreasing"] is False
    p = {r["age"]: r["age_mult"] for r in cur["profile"]}
    assert abs(p[24] - 1.384) < 1e-12
    assert abs(p[25] - 1.0) < 1e-12
    assert p[24] > p[23]

    # Smooth alternatives must preserve common endpoints and be monotone.
    for name in ("linear_to_25", "smoothstep_to_25", "quadratic_to_25"):
        d = curve_diagnostics(name)
        prof = {r["age"]: r["age_mult"] for r in d["profile"]}
        assert d["monotone_nonincreasing"] is True, name
        assert abs(prof[21] - DEPLOYED_AGE21_AM) < 1e-12, name
        assert abs(prof[25] - 1.0) < 1e-12, name

    print("young_rb_age_curve_shape_audit self-test passed.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    report = build_report()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_md(report)
    print(OUT_MD.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
