#!/usr/bin/env python3
"""
RB Anchor-Preserving Continuous Age Audit
=========================================

READ-ONLY calibration gate.

The prior audit proved that fractional age is structurally superior, but the
tested age-21 -> age-25 tapers materially repriced today's elite age-24 RBs.

This audit separates two decisions:

A) ARCHITECTURE:
   Replace integer-age steps with fractional-age interpolation.

B) LEVELS:
   Preserve the model's existing integer-age anchor values unless evidence
   independently justifies changing them.

Candidates
----------
deployed_integer
    Current production behavior.

continuous_current_anchors
    For each RB/player state, compute the CURRENT deployed age multiplier at
    the surrounding integer ages and linearly interpolate between them.
    Therefore every integer-age anchor is preserved exactly, but birthdays
    cannot create discrete jumps.

continuous_monotone_elite_anchors
    Same as above for ordinary RBs. For qualifying elite young RBs only,
    monotonize the existing age-21..25 anchors with isotonic regression before
    interpolation. This removes the current age-23 -> age-24 bump while changing
    the anchor levels as little as possible in squared-error terms.

Evaluation
----------
1. Same-player birthday-event error from the existing external event study.
2. Exact birthday discontinuity.
3. Current full-RB-board Fundamental Value and rank blast radius as of
   2026-09-02.

Nothing in index.html is modified.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DIR = REPO_ROOT / "scripts" / "validation"
if str(VALIDATION_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATION_DIR))

import snapshot_values

INDEX_PATH = REPO_ROOT / "index.html"
PLAYERS_CACHE_PATH = REPO_ROOT / "data" / "players_cache.json"
EVENT_PATH = REPO_ROOT / "research" / "age-calibration" / "young_rb_birthday_event_study.json"
OUT_JSON = REPO_ROOT / "research" / "age-calibration" / "rb_anchor_preserving_continuous_age_audit.json"
OUT_MD = REPO_ROOT / "research" / "age-calibration" / "rb_anchor_preserving_continuous_age_audit.md"

AS_OF = date(2026, 9, 2)
CANDIDATES = (
    "deployed_integer",
    "continuous_current_anchors",
    "continuous_monotone_elite_anchors",
)

ELITE_MIN_RAW_PM = 0.65


def normalize_name(name: str) -> str:
    s = str(name or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+(jr|sr|ii|iii|iv)$", "", s)
    return s.strip()


def parse_dob(raw: Any) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def player_cache_name(row: dict[str, Any]) -> str:
    for field in ("full_name", "search_full_name", "player_name", "name"):
        if row.get(field):
            return str(row[field])
    return f"{row.get('first_name') or ''} {row.get('last_name') or ''}".strip()


def load_cache() -> tuple[dict[str, list[tuple[str, dict[str, Any], date]]], dict[str, date]]:
    doc = json.loads(PLAYERS_CACHE_PATH.read_text(encoding="utf-8"))
    players = doc.get("players")
    if not isinstance(players, dict):
        raise RuntimeError("players_cache.json missing players mapping")

    by_name = defaultdict(list)
    by_id = {}
    for pid, row in players.items():
        if not isinstance(row, dict):
            continue
        dob = parse_dob(row.get("birth_date"))
        if dob is None:
            continue
        by_id[str(pid)] = dob
        norm = normalize_name(player_cache_name(row))
        if norm:
            by_name[norm].append((str(pid), row, dob))
    return by_name, by_id


def fractional_age(dob: date, on_date: date) -> float:
    try:
        bd_this = date(on_date.year, dob.month, dob.day)
    except ValueError:
        bd_this = date(on_date.year, 2, 28)

    if on_date >= bd_this:
        last_bd = bd_this
        next_year = on_date.year + 1
    else:
        next_year = on_date.year
        try:
            last_bd = date(on_date.year - 1, dob.month, dob.day)
        except ValueError:
            last_bd = date(on_date.year - 1, 2, 28)

    try:
        next_bd = date(next_year, dob.month, dob.day)
    except ValueError:
        next_bd = date(next_year, 2, 28)

    whole = last_bd.year - dob.year
    span = (next_bd - last_bd).days
    elapsed = (on_date - last_bd).days
    return whole + elapsed / span


def midpoint(window_text: str) -> date:
    a_s, b_s = window_text.split("..")
    a = date.fromisoformat(a_s)
    b = date.fromisoformat(b_s)
    return a + (b - a) / 2


def production_components(key: str, info: dict[str, Any], cfg: dict[str, Any]):
    rm, raw = snapshot_values.production_multiplier(
        key, info["role"], cfg["prod_mult"], cfg["no_real_history"], cfg["role_mult"]
    )
    return float(rm), float(raw) if isinstance(raw, (int, float)) else None


def deployed_anchor(
    age: int,
    role: str,
    rm: float,
    raw_pm: float | None,
    cfg: dict[str, Any],
) -> float:
    return float(snapshot_values.age_multiplier("RB", age, role, rm, raw_pm, cfg))


def isotonic_nonincreasing(values: list[float]) -> list[float]:
    """
    Pool-adjacent-violators algorithm for non-increasing least-squares fit.
    Equal weights.
    """
    # Convert non-increasing y into non-decreasing -y.
    blocks = []
    for i, value in enumerate(values):
        blocks.append({"start": i, "end": i, "sum": -value, "n": 1})
        while len(blocks) >= 2:
            left, right = blocks[-2], blocks[-1]
            left_mean = left["sum"] / left["n"]
            right_mean = right["sum"] / right["n"]
            if left_mean <= right_mean:
                break
            merged = {
                "start": left["start"],
                "end": right["end"],
                "sum": left["sum"] + right["sum"],
                "n": left["n"] + right["n"],
            }
            blocks[-2:] = [merged]

    out = [0.0] * len(values)
    for block in blocks:
        fitted = -(block["sum"] / block["n"])
        for i in range(block["start"], block["end"] + 1):
            out[i] = fitted
    return out


def anchor_series(
    role: str,
    rm: float,
    raw_pm: float | None,
    cfg: dict[str, Any],
    candidate: str,
) -> dict[int, float]:
    anchors = {
        age: deployed_anchor(age, role, rm, raw_pm, cfg)
        for age in range(20, 36)
    }

    if (
        candidate == "continuous_monotone_elite_anchors"
        and role == "Elite"
        and isinstance(raw_pm, (int, float))
        and raw_pm >= ELITE_MIN_RAW_PM
    ):
        ages = list(range(21, 26))
        fitted = isotonic_nonincreasing([anchors[a] for a in ages])
        for age, value in zip(ages, fitted):
            anchors[age] = value

    return anchors


def interpolated_am(
    frac_age: float,
    role: str,
    rm: float,
    raw_pm: float | None,
    cfg: dict[str, Any],
    candidate: str,
) -> float:
    anchors = anchor_series(role, rm, raw_pm, cfg, candidate)

    lo = math.floor(frac_age)
    hi = math.ceil(frac_age)
    lo = max(min(lo, max(anchors)), min(anchors))
    hi = max(min(hi, max(anchors)), min(anchors))

    if lo == hi:
        return anchors[lo]

    t = frac_age - lo
    return anchors[lo] + t * (anchors[hi] - anchors[lo])


def js_round_positive(x: float) -> int:
    return math.floor(x + 0.5)


def summarize_errors(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = {"n": len(rows), "candidates": {}}
    for c in CANDIDATES:
        errors = [abs(r["predictions"][c] - r["market_change_pct"]) for r in rows]
        biases = [r["predictions"][c] - r["market_change_pct"] for r in rows]
        out["candidates"][c] = {
            "mae": sum(errors) / len(errors) if errors else None,
            "median_abs_error": statistics.median(errors) if errors else None,
            "median_bias": statistics.median(biases) if biases else None,
        }
    return out


def percentile(vals: list[float], q: float) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    x = (len(s) - 1) * q
    lo, hi = math.floor(x), math.ceil(x)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (x - lo)


def build_report() -> dict[str, Any]:
    cfg = snapshot_values.load_from_html(INDEX_PATH)
    current_values = snapshot_values.compute_all_values(cfg)
    cache_by_name, dob_by_id = load_cache()
    prior = json.loads(EVENT_PATH.read_text(encoding="utf-8"))

    # -------- Event-study comparison --------
    event_rows = []
    db_norm = {normalize_name(k): (k, v) for k, v in cfg["player_db"].items()}

    for e in prior.get("events") or []:
        pid = str(e.get("external_id") or "")
        dob = dob_by_id.get(pid)
        rec = db_norm.get(normalize_name(e["player"]))
        if not dob or not rec:
            continue

        key, info = rec
        rm, raw_pm = production_components(key, info, cfg)
        age_pre = fractional_age(dob, midpoint(e["pre_window"]))
        age_post = fractional_age(dob, midpoint(e["post_window"]))

        preds = {"deployed_integer": float(e["model_age_only_change_pct"])}
        for c in CANDIDATES[1:]:
            pre_am = interpolated_am(age_pre, info["role"], rm, raw_pm, cfg, c)
            post_am = interpolated_am(age_post, info["role"], rm, raw_pm, cfg, c)
            preds[c] = post_am / pre_am - 1.0

        event_rows.append({
            "player": key,
            "transition": e["transition"],
            "market_change_pct": float(e["market_change_pct"]),
            "pm": rm,
            "role": info["role"],
            "predictions": preds,
        })

    event_cohorts = {
        "all": event_rows,
        "meaningful_pm": [r for r in event_rows if r["pm"] >= 0.35],
        "high_pm": [r for r in event_rows if r["pm"] >= 0.65],
        "elite": [r for r in event_rows if r["role"] == "Elite"],
    }
    event_summary = {k: summarize_errors(v) for k, v in event_cohorts.items()}

    # -------- Current-board blast radius --------
    rb_current_rank = {}
    rb_current = sorted(
        [(k, r["value"]) for k, r in current_values.items() if r["pos"] == "RB"],
        key=lambda x: (-x[1], x[0]),
    )
    for i, (k, _) in enumerate(rb_current, 1):
        rb_current_rank[k] = i

    live_rows = []
    unmatched = []
    for key, info in cfg["player_db"].items():
        if info["pos"] != "RB":
            continue
        matches = cache_by_name.get(normalize_name(key), [])
        if len(matches) != 1:
            unmatched.append(key)
            continue

        _, _, dob = matches[0]
        frac = fractional_age(dob, AS_OF)
        rm, raw_pm = production_components(key, info, cfg)

        live_rows.append({
            "player": key,
            "fractional_age": frac,
            "role": info["role"],
            "pm": rm,
            "raw_pm": raw_pm,
            "current_value": int(current_values[key]["value"]),
            "candidates": {},
        })

    for c in CANDIDATES[1:]:
        values = {k: int(r["value"]) for k, r in current_values.items() if r["pos"] == "RB"}

        for r in live_rows:
            info = cfg["player_db"][r["player"]]
            am = interpolated_am(
                r["fractional_age"], info["role"], r["pm"], r["raw_pm"], cfg, c
            )
            value = js_round_positive(
                100 * cfg["position_weight"]["RB"] * am * r["pm"] * 55
            )
            values[r["player"]] = value
            r["candidates"][c] = {"value": value, "age_mult": am}

        ranks = {
            k: i
            for i, (k, _) in enumerate(
                sorted(values.items(), key=lambda x: (-x[1], x[0])), 1
            )
        }
        for r in live_rows:
            rec = r["candidates"][c]
            rec["delta_points"] = rec["value"] - r["current_value"]
            rec["delta_pct"] = (
                rec["delta_points"] / r["current_value"]
                if r["current_value"] else 0.0
            )
            rec["rank_move"] = rb_current_rank[r["player"]] - ranks[r["player"]]
            rec["current_rank"] = rb_current_rank[r["player"]]
            rec["candidate_rank"] = ranks[r["player"]]

    live_summary = {}
    top_movers = {}
    for c in CANDIDATES[1:]:
        pcts = [abs(r["candidates"][c]["delta_pct"]) for r in live_rows]
        points = [abs(r["candidates"][c]["delta_points"]) for r in live_rows]
        valuable = [r for r in live_rows if r["current_value"] >= 3000]
        valuable_pcts = [abs(r["candidates"][c]["delta_pct"]) for r in valuable]

        live_summary[c] = {
            "n": len(live_rows),
            "changed_n": sum(x > 0 for x in points),
            "median_abs_points": statistics.median(points),
            "p90_abs_points": percentile(points, 0.90),
            "max_abs_points": max(points),
            "median_abs_pct": statistics.median(pcts),
            "p90_abs_pct": percentile(pcts, 0.90),
            "max_abs_pct": max(pcts),
            "valuable_n": len(valuable),
            "valuable_median_abs_pct": statistics.median(valuable_pcts),
            "valuable_max_abs_pct": max(valuable_pcts),
            "moves_ge_10_pct": sum(x >= 0.10 for x in pcts),
            "moves_ge_20_pct": sum(x >= 0.20 for x in pcts),
        }

        top_movers[c] = sorted(
            [
                {
                    "player": r["player"],
                    "fractional_age": r["fractional_age"],
                    "role": r["role"],
                    "current_value": r["current_value"],
                    **r["candidates"][c],
                }
                for r in live_rows
            ],
            key=lambda x: (-abs(x["delta_points"]), x["player"]),
        )[:25]

    # Structural exact-birthday jump is zero by continuity (up to one-day slope),
    # report the largest single-day move on current live rows.
    max_one_day = {}
    for c in CANDIDATES[1:]:
        moves = []
        for r in live_rows:
            info = cfg["player_db"][r["player"]]
            a0 = r["fractional_age"]
            a1 = a0 + 1.0 / 365.25
            am0 = interpolated_am(a0, info["role"], r["pm"], r["raw_pm"], cfg, c)
            am1 = interpolated_am(a1, info["role"], r["pm"], r["raw_pm"], cfg, c)
            moves.append(abs(am1 / am0 - 1.0))
        max_one_day[c] = max(moves) if moves else None

    elite_anchor_example = {}
    # Standardized qualifying Elite RB with high raw PM.
    role = "Elite"
    rm = 1.0
    raw_pm = 1.0
    for c in CANDIDATES[1:]:
        elite_anchor_example[c] = {
            str(age): round(anchor_series(role, rm, raw_pm, cfg, c)[age], 6)
            for age in range(21, 27)
        }

    return {
        "audit": "rb-anchor-preserving-continuous-age-v1",
        "production_changes": False,
        "as_of": AS_OF.isoformat(),
        "elite_anchor_example": elite_anchor_example,
        "event_summary": event_summary,
        "live_summary": live_summary,
        "max_abs_one_day_age_move": max_one_day,
        "top_movers": top_movers,
        "counts": {
            "live_rb": len(rb_current),
            "matched_live_rb": len(live_rows),
            "unmatched_live_rb": len(unmatched),
        },
        "unmatched": unmatched,
    }


def pct(v: Any) -> str:
    return "n/a" if v is None else f"{100 * float(v):+.1f}%"


def write_md(report: dict[str, Any]) -> None:
    lines = [
        "# RB Anchor-Preserving Continuous Age Audit",
        "",
        "**Status:** research-only; no production values changed.",
        "",
        "## Elite anchor example",
        "",
        "| Candidate | 21 | 22 | 23 | 24 | 25 | 26 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for c in CANDIDATES[1:]:
        a = report["elite_anchor_example"][c]
        lines.append(
            f"| {c} | {a['21']:.3f} | {a['22']:.3f} | {a['23']:.3f} | "
            f"{a['24']:.3f} | {a['25']:.3f} | {a['26']:.3f} |"
        )

    lines += [
        "",
        "## Birthday-event error",
        "",
        "| Cohort | N | Candidate | MAE | Median abs error | Median bias |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for cohort, summary in report["event_summary"].items():
        for c in CANDIDATES:
            rec = summary["candidates"][c]
            lines.append(
                f"| {cohort} | {summary['n']} | {c} | {pct(rec['mae'])} | "
                f"{pct(rec['median_abs_error'])} | {pct(rec['median_bias'])} |"
            )

    lines += [
        "",
        "## Current-board blast radius",
        "",
        "| Candidate | Changed | Median abs pts | P90 abs pts | Max abs pts | "
        "Median abs % | P90 abs % | Max abs % | Valuable median abs % | "
        "Valuable max abs % | >=10% | >=20% | Max 1-day age move |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for c in CANDIDATES[1:]:
        s = report["live_summary"][c]
        lines.append(
            f"| {c} | {s['changed_n']}/{s['n']} | {s['median_abs_points']:.0f} | "
            f"{s['p90_abs_points']:.0f} | {s['max_abs_points']:.0f} | "
            f"{pct(s['median_abs_pct'])} | {pct(s['p90_abs_pct'])} | "
            f"{pct(s['max_abs_pct'])} | {pct(s['valuable_median_abs_pct'])} | "
            f"{pct(s['valuable_max_abs_pct'])} | {s['moves_ge_10_pct']} | "
            f"{s['moves_ge_20_pct']} | {pct(report['max_abs_one_day_age_move'][c])} |"
        )

    for c in CANDIDATES[1:]:
        lines += [
            "",
            f"## Largest movers — {c}",
            "",
            "| Player | Fractional age | Role | Current | Candidate | Delta | Delta % | "
            "Current RB rank | Candidate RB rank | Rank move |",
            "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for r in report["top_movers"][c]:
            lines.append(
                f"| {r['player']} | {r['fractional_age']:.2f} | {r['role']} | "
                f"{r['current_value']} | {r['value']} | {r['delta_points']:+d} | "
                f"{pct(r['delta_pct'])} | {r['current_rank']} | "
                f"{r['candidate_rank']} | {r['rank_move']:+d} |"
            )

    lines += [
        "",
        "## Decision rule",
        "",
        "Prefer anchor-preserving continuity if it removes birthday discontinuities and keeps "
        "the external-event improvement seen with fractional age while materially reducing "
        "the live-board repricing versus the earlier age-21-to-25 taper candidates.",
        "",
    ]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def run_selftest() -> None:
    # Isotonic must minimally fix the 23->24 violation in the current elite anchors.
    src = [1.493, 1.390, 1.268, 1.384, 1.000]
    fit = isotonic_nonincreasing(src)
    assert all(fit[i] >= fit[i + 1] - 1e-12 for i in range(len(fit) - 1))
    assert abs(fit[2] - fit[3]) < 1e-12

    # Fractional age should be continuous across a birthday.
    dob = date(2002, 1, 30)
    a0 = fractional_age(dob, date(2026, 1, 29))
    a1 = fractional_age(dob, date(2026, 1, 30))
    assert a0 < 24 <= a1
    assert abs((a1 - a0) - 1 / 365.25) < 0.01

    print("rb_anchor_preserving_continuous_age_audit self-test passed.")


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
