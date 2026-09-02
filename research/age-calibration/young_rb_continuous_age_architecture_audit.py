#!/usr/bin/env python3
"""
Young RB Continuous-Age Architecture Audit
==========================================

READ-ONLY follow-up to young_rb_birthday_event_study.py.

Goal
----
Test whether Trade Desk should replace integer-age step changes for RBs with a
continuous fractional-age architecture.

This audit DOES NOT change production.

Evidence source
---------------
Consumes the already-generated birthday event study:
  research/age-calibration/young_rb_birthday_event_study.json

That report contains same-player external dynasty market changes around real
birthdays. Here we compare those observed changes against:

1. deployed_integer
   The current production behavior already recorded by the birthday study.

2. continuous_linear
3. continuous_smoothstep
4. continuous_quadratic

For every continuous candidate:
- exact fractional age is computed from Sleeper DOB on the midpoint of the
  pre/post event windows;
- ordinary RB pre-peak and post-peak logic preserves CURRENT Trade Desk
  endpoints but evaluates age continuously;
- the elite young-RB override is replaced by a monotone premium taper from the
  deployed age-21 elite multiplier to 1.0 at age 25;
- only the elite taper SHAPE differs among candidates.

Why this is a structural test
-----------------------------
A continuous age model should not create a large value discontinuity on the
birthday itself. The event-study market movement is noisy and confounded, so
absolute fit is only diagnostic. The more important questions are:
- does continuous age eliminate implausible birthday cliffs?
- does it reduce paired event error without creating rank/pathology issues?
- is the result robust in meaningful/high-production cohorts?

Outputs are research-only.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DIR = REPO_ROOT / "scripts" / "validation"
if str(VALIDATION_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATION_DIR))

import snapshot_values

INDEX_PATH = REPO_ROOT / "index.html"
PLAYERS_CACHE_PATH = REPO_ROOT / "data" / "players_cache.json"
BIRTHDAY_REPORT_PATH = (
    REPO_ROOT / "research" / "age-calibration" / "young_rb_birthday_event_study.json"
)
OUT_JSON = (
    REPO_ROOT / "research" / "age-calibration" /
    "young_rb_continuous_age_architecture_audit.json"
)
OUT_MD = (
    REPO_ROOT / "research" / "age-calibration" /
    "young_rb_continuous_age_architecture_audit.md"
)

CANDIDATES = (
    "deployed_integer",
    "continuous_linear",
    "continuous_smoothstep",
    "continuous_quadratic",
)
CONTINUOUS_CANDIDATES = CANDIDATES[1:]

CURRENT_COEFF = 0.384
ELITE_MIN_RAW_PM = 0.65
MEANINGFUL_PM = 0.35
HIGH_PM = 0.65
BOOTSTRAP_ITERATIONS = 2000
RANDOM_SEED = 20260902


def parse_date(s: str) -> date:
    return date.fromisoformat(s[:10])


def midpoint_date(window_text: str) -> date:
    left, right = window_text.split("..", 1)
    a = parse_date(left)
    b = parse_date(right)
    return a + (b - a) / 2


def normalize_name(name: str) -> str:
    s = str(name or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+(jr|sr|ii|iii|iv)$", "", s)
    return s.strip()


def load_players_cache() -> dict[str, Any]:
    doc = json.loads(PLAYERS_CACHE_PATH.read_text(encoding="utf-8"))
    players = doc.get("players")
    if not isinstance(players, dict):
        raise RuntimeError("players_cache.json missing top-level players mapping")
    return players


def parse_dob(raw: Any) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def fractional_age(dob: date, on_date: date) -> float:
    """
    Exact-ish fractional age using the surrounding birthdays.
    Fraction runs 0..1 between last and next birthday.
    """
    year = on_date.year
    try:
        this_bd = date(year, dob.month, dob.day)
    except ValueError:
        this_bd = date(year, 2, 28)

    if on_date >= this_bd:
        last_bd = this_bd
        next_year = year + 1
    else:
        next_year = year
        try:
            last_bd = date(year - 1, dob.month, dob.day)
        except ValueError:
            last_bd = date(year - 1, 2, 28)

    try:
        next_bd = date(next_year, dob.month, dob.day)
    except ValueError:
        next_bd = date(next_year, 2, 28)

    whole = last_bd.year - dob.year
    if (last_bd.month, last_bd.day) < (dob.month, dob.day):
        whole -= 1

    span = (next_bd - last_bd).days
    elapsed = (on_date - last_bd).days
    return whole + elapsed / span


def deployed_age21_elite_am() -> float:
    years = min(4.0, max(0.0, 25.0 - 21.0))
    return min(1.5, 0.725 + CURRENT_COEFF * math.sqrt(years))


AGE21_ELITE_AM = deployed_age21_elite_am()
ELITE_PREMIUM = AGE21_ELITE_AM - 1.0


def elite_continuous_am(age: float, shape: str) -> float:
    if age <= 21.0:
        return AGE21_ELITE_AM
    if age >= 25.0:
        return 1.0

    x = (25.0 - age) / 4.0  # age21=1, age25=0
    x = max(0.0, min(1.0, x))

    if shape == "linear":
        s = x
    elif shape == "smoothstep":
        s = 3.0 * x * x - 2.0 * x * x * x
    elif shape == "quadratic":
        s = x * x
    else:
        raise ValueError(shape)

    return 1.0 + ELITE_PREMIUM * s


def continuous_rb_age_multiplier(
    *,
    age: float,
    role: str,
    rm: float,
    raw_pm: float | None,
    cfg: dict[str, Any],
    elite_shape: str,
) -> float:
    """
    Minimal continuous redesign:
    - preserve current non-elite RB endpoints/logic, replacing integer age with float;
    - replace only the discontinuous elite youth override with monotone taper;
    - preserve current post-peak floor/shape, evaluated continuously.
    """
    c = cfg["age_curve"]["RB"]

    if (
        role == "Elite"
        and age <= 25.0
        and isinstance(raw_pm, (int, float))
        and raw_pm >= ELITE_MIN_RAW_PM
    ):
        return elite_continuous_am(age, elite_shape)

    # Current pre-floor logic.
    if isinstance(rm, (int, float)):
        lo, hi = 0.15, 1.55
        ratio = max(0.0, min(1.0, (rm - lo) / (hi - lo)))
        pre_floor = 0.55 + ratio * (0.98 - 0.55)
    else:
        pre_floor = 0.725 if role == "Elite" else 0.55

    peak_start = float(c["peakStart"])
    peak_end = float(c["peakEnd"])
    floor_age = float(c["floor"])

    if age <= peak_end:
        denom = peak_start - 21.0
        t = max(0.0, min(1.0, (age - 21.0) / denom)) if denom else 1.0
        pre_floor_base = pre_floor + t * (1.0 - pre_floor)
        return pre_floor_base if age <= peak_start else 1.0

    # Current RB post-peak shape, continuous.
    denom = floor_age - peak_end
    t = max(0.0, min(1.0, (age - peak_end) / denom)) if denom else 1.0
    return max(0.62, 1.0 - 0.38 * t)


def production_components(
    key: str,
    info: dict[str, Any],
    cfg: dict[str, Any],
) -> tuple[float, float | None]:
    rm, raw = snapshot_values.production_multiplier(
        key,
        info["role"],
        cfg["prod_mult"],
        cfg["no_real_history"],
        cfg["role_mult"],
    )
    return float(rm), float(raw) if isinstance(raw, (int, float)) else None


def candidate_change(
    *,
    candidate: str,
    age_pre: float,
    age_post: float,
    role: str,
    rm: float,
    raw_pm: float | None,
    cfg: dict[str, Any],
) -> float:
    if candidate == "deployed_integer":
        raise ValueError("deployed_integer is read from prior event report")

    shape = candidate.removeprefix("continuous_")
    am_pre = continuous_rb_age_multiplier(
        age=age_pre, role=role, rm=rm, raw_pm=raw_pm, cfg=cfg, elite_shape=shape
    )
    am_post = continuous_rb_age_multiplier(
        age=age_post, role=role, rm=rm, raw_pm=raw_pm, cfg=cfg, elite_shape=shape
    )
    return am_post / am_pre - 1.0


def abs_error(pred: float, actual: float) -> float:
    return abs(pred - actual)


def mean(vals: list[float]) -> float | None:
    return sum(vals) / len(vals) if vals else None


def percentile(vals: list[float], q: float) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    x = (len(s) - 1) * q
    lo, hi = math.floor(x), math.ceil(x)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (x - lo)


def bootstrap_mae_delta(
    rows: list[dict[str, Any]],
    challenger: str,
    iterations: int = BOOTSTRAP_ITERATIONS,
) -> dict[str, Any]:
    """
    Paired bootstrap: deployed MAE - challenger MAE.
    Positive = challenger improves absolute error.
    """
    rng = random.Random(RANDOM_SEED + sum(ord(c) for c in challenger))
    n = len(rows)
    deltas = []
    for _ in range(iterations):
        sample = [rows[rng.randrange(n)] for __ in range(n)]
        deployed = mean([
            abs_error(r["predictions"]["deployed_integer"], r["market_change_pct"])
            for r in sample
        ])
        alt = mean([
            abs_error(r["predictions"][challenger], r["market_change_pct"])
            for r in sample
        ])
        if deployed is not None and alt is not None:
            deltas.append(deployed - alt)

    return {
        "bootstrap_n": len(deltas),
        "median_mae_improvement": statistics.median(deltas) if deltas else None,
        "p10": percentile(deltas, 0.10),
        "p90": percentile(deltas, 0.90),
        "probability_improves": (
            sum(1 for x in deltas if x > 0) / len(deltas) if deltas else None
        ),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = {"n": len(rows), "candidates": {}}
    if not rows:
        return out

    for candidate in CANDIDATES:
        errs = [
            abs_error(r["predictions"][candidate], r["market_change_pct"])
            for r in rows
        ]
        bias = [
            r["predictions"][candidate] - r["market_change_pct"]
            for r in rows
        ]
        preds = [r["predictions"][candidate] for r in rows]

        rec = {
            "mae": mean(errs),
            "median_abs_error": statistics.median(errs),
            "median_bias": statistics.median(bias),
            "median_predicted_change": statistics.median(preds),
        }
        if candidate != "deployed_integer":
            rec["paired_bootstrap_vs_deployed"] = bootstrap_mae_delta(rows, candidate)
        out["candidates"][candidate] = rec
    return out


def exact_birthday_jump(
    *,
    birthday: date,
    dob: date,
    role: str,
    rm: float,
    raw_pm: float | None,
    cfg: dict[str, Any],
    candidate: str,
) -> float:
    """Change from day before birthday to birthday under candidate."""
    if candidate == "deployed_integer":
        age_before = birthday.year - dob.year - 1
        age_after = age_before + 1
        before = snapshot_values.age_multiplier(
            "RB", age_before, role, rm, raw_pm, cfg
        )
        after = snapshot_values.age_multiplier(
            "RB", age_after, role, rm, raw_pm, cfg
        )
        return after / before - 1.0

    shape = candidate.removeprefix("continuous_")
    a0 = fractional_age(dob, birthday.fromordinal(birthday.toordinal() - 1))
    a1 = fractional_age(dob, birthday)
    before = continuous_rb_age_multiplier(
        age=a0, role=role, rm=rm, raw_pm=raw_pm, cfg=cfg, elite_shape=shape
    )
    after = continuous_rb_age_multiplier(
        age=a1, role=role, rm=rm, raw_pm=raw_pm, cfg=cfg, elite_shape=shape
    )
    return after / before - 1.0


def build_report() -> dict[str, Any]:
    cfg = snapshot_values.load_from_html(INDEX_PATH)
    player_cache = load_players_cache()
    prior = json.loads(BIRTHDAY_REPORT_PATH.read_text(encoding="utf-8"))

    # Sleeper external id -> DOB lookup.
    dob_by_id = {}
    for pid, row in player_cache.items():
        dob = parse_dob((row or {}).get("birth_date"))
        if dob:
            dob_by_id[str(pid)] = dob

    # Model keys normalized for safe lookup.
    db_by_norm = {normalize_name(k): (k, v) for k, v in cfg["player_db"].items()}

    rows = []
    skipped = []

    for event in prior.get("events") or []:
        pid = str(event.get("external_id") or "")
        dob = dob_by_id.get(pid)
        if dob is None:
            skipped.append({"player": event.get("player"), "reason": "missing_dob"})
            continue

        norm = normalize_name(event["player"])
        db_rec = db_by_norm.get(norm)
        if not db_rec:
            skipped.append({"player": event.get("player"), "reason": "missing_player_db"})
            continue
        key, info = db_rec

        rm, raw_pm = production_components(key, info, cfg)
        pre_mid = midpoint_date(event["pre_window"])
        post_mid = midpoint_date(event["post_window"])
        age_pre = fractional_age(dob, pre_mid)
        age_post = fractional_age(dob, post_mid)

        predictions = {
            "deployed_integer": float(event["model_age_only_change_pct"])
        }
        for candidate in CONTINUOUS_CANDIDATES:
            predictions[candidate] = candidate_change(
                candidate=candidate,
                age_pre=age_pre,
                age_post=age_post,
                role=info["role"],
                rm=rm,
                raw_pm=raw_pm,
                cfg=cfg,
            )

        birthday = parse_date(event["birthday"])
        jumps = {}
        for candidate in CANDIDATES:
            jumps[candidate] = exact_birthday_jump(
                birthday=birthday,
                dob=dob,
                role=info["role"],
                rm=rm,
                raw_pm=raw_pm,
                cfg=cfg,
                candidate=candidate,
            )

        rows.append({
            "player": key,
            "transition": event["transition"],
            "birthday": event["birthday"],
            "role": info["role"],
            "pm": rm,
            "raw_pm": raw_pm,
            "pre_midpoint": pre_mid.isoformat(),
            "post_midpoint": post_mid.isoformat(),
            "fractional_age_pre": age_pre,
            "fractional_age_post": age_post,
            "market_change_pct": float(event["market_change_pct"]),
            "predictions": predictions,
            "exact_birthday_jump": jumps,
        })

    cohorts = {
        "all_usable": rows,
        "meaningful_production": [r for r in rows if r["pm"] >= MEANINGFUL_PM],
        "high_production": [r for r in rows if r["pm"] >= HIGH_PM],
        "elite_role": [r for r in rows if r["role"] == "Elite"],
    }

    cohort_summaries = {name: summarize(group) for name, group in cohorts.items()}

    # Structural jump maxima: the core architecture criterion.
    jump_summary = {}
    for candidate in CANDIDATES:
        vals = [abs(r["exact_birthday_jump"][candidate]) for r in rows]
        jump_summary[candidate] = {
            "max_abs_exact_birthday_jump": max(vals) if vals else None,
            "median_abs_exact_birthday_jump": statistics.median(vals) if vals else None,
        }

    # Transition-specific summary for direct interpretation.
    transitions = {}
    for transition in sorted({r["transition"] for r in rows}):
        group = [r for r in rows if r["transition"] == transition]
        transitions[transition] = summarize(group)

    return {
        "audit": "young-rb-continuous-age-architecture-v1",
        "production_changes": False,
        "architecture_tested": (
            "Fractional age + current non-elite endpoints + monotone elite youth taper."
        ),
        "candidate_definitions": {
            "deployed_integer": "Current production behavior.",
            "continuous_linear": "Fractional age; elite premium linear from age 21 to 25.",
            "continuous_smoothstep": "Fractional age; elite premium cubic smoothstep from age 21 to 25.",
            "continuous_quadratic": "Fractional age; elite premium quadratic from age 21 to 25.",
        },
        "counts": {
            "prior_usable_events": prior.get("counts", {}).get("usable_events"),
            "audited_events": len(rows),
            "skipped": len(skipped),
        },
        "structural_birthday_jump": jump_summary,
        "cohorts": cohort_summaries,
        "transitions": transitions,
        "events": rows,
        "skipped": skipped,
        "interpretation_boundary": (
            "Observed market changes remain confounded by football news and changing historical "
            "roles. This audit is strongest as a structural discontinuity test. Paired error "
            "improvement is supporting evidence, not causal proof of the exact age curve."
        ),
    }


def pct(v: Any) -> str:
    return "n/a" if v is None else f"{100.0 * float(v):+.1f}%"


def write_candidate_table(lines: list[str], summary: dict[str, Any]) -> None:
    lines += [
        "| Candidate | MAE | Median abs error | Median bias | Median predicted change | Bootstrap P(improves vs deployed) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for candidate in CANDIDATES:
        rec = summary["candidates"][candidate]
        boot = rec.get("paired_bootstrap_vs_deployed") or {}
        p_imp = boot.get("probability_improves")
        lines.append(
            f"| {candidate} | {pct(rec['mae'])} | {pct(rec['median_abs_error'])} | "
            f"{pct(rec['median_bias'])} | {pct(rec['median_predicted_change'])} | "
            f"{('n/a' if p_imp is None else f'{100*p_imp:.1f}%')} |"
        )


def write_md(report: dict[str, Any]) -> None:
    lines = [
        "# Young RB Continuous-Age Architecture Audit",
        "",
        "**Status:** research-only; no production values changed.",
        "",
        "## Architecture being tested",
        "",
        "Replace integer-age step changes with exact fractional age. Preserve the current ordinary-RB "
        "pre/post-peak endpoints, but evaluate them continuously. Replace the elite young-RB override "
        "with a monotone premium taper from the deployed age-21 anchor to 1.0 at age 25.",
        "",
        f"- Birthday events audited: **{report['counts']['audited_events']}**",
        "",
        "## Structural birthday discontinuity",
        "",
        "| Candidate | Median abs exact birthday jump | Max abs exact birthday jump |",
        "|---|---:|---:|",
    ]
    for candidate in CANDIDATES:
        rec = report["structural_birthday_jump"][candidate]
        lines.append(
            f"| {candidate} | {pct(rec['median_abs_exact_birthday_jump'])} | "
            f"{pct(rec['max_abs_exact_birthday_jump'])} |"
        )

    for title, key in [
        ("All usable events", "all_usable"),
        ("Meaningful-production events", "meaningful_production"),
        ("High-production events", "high_production"),
        ("Elite-role events", "elite_role"),
    ]:
        summary = report["cohorts"][key]
        lines += [
            "",
            f"## {title}",
            "",
            f"- N: **{summary['n']}**",
            "",
        ]
        write_candidate_table(lines, summary)

    lines += [
        "",
        "## By birthday transition",
        "",
    ]
    for transition, summary in report["transitions"].items():
        lines += [
            f"### {transition}",
            "",
            f"- N: **{summary['n']}**",
            "",
        ]
        write_candidate_table(lines, summary)
        lines.append("")

    lines += [
        "## Interpretation boundary",
        "",
        report["interpretation_boundary"],
        "",
        "A production candidate should only advance if it eliminates the structural birthday jump "
        "and does not materially worsen paired external-event error in the meaningful/high-production cohorts.",
        "",
    ]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def run_selftest() -> None:
    # Fractional age must move smoothly across birthday.
    dob = date(2002, 1, 30)
    d0 = date(2026, 1, 29)
    d1 = date(2026, 1, 30)
    a0 = fractional_age(dob, d0)
    a1 = fractional_age(dob, d1)
    assert a0 < 24.0 <= a1
    assert abs((a1 - a0) - 1.0 / 365.0) < 0.01

    # Elite alternatives preserve endpoints and are monotone.
    for shape in ("linear", "smoothstep", "quadratic"):
        vals = [elite_continuous_am(21 + i / 10.0, shape) for i in range(41)]
        assert abs(vals[0] - AGE21_ELITE_AM) < 1e-12
        assert abs(vals[-1] - 1.0) < 1e-12
        assert all(vals[i] >= vals[i + 1] - 1e-12 for i in range(len(vals) - 1))

    print("young_rb_continuous_age_architecture_audit self-test passed.")


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
