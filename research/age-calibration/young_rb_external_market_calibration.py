#!/usr/bin/env python3
"""
Young RB External Market Age Calibration
========================================

READ-ONLY research calibration for Trade Desk's young-RB age curve.

External evidence
-----------------
Uses the public Stats Guy Fantasy API:
  GET /api/v1/rankings?format=sf_dynasty&position=RB&limit=1000

Stats Guy Fantasy describes these values as derived from real trades across
thousands of Sleeper leagues. This script treats that as an INDEPENDENT market
signal, not as fundamental truth and not as a production target.

Question
--------
After controlling for Trade Desk production multiplier and role, what age
premium does the broad external SF dynasty trade market imply for RBs age
21-25? Which continuity-constrained Trade Desk age-curve family is closest?

Method
------
1. Parse CURRENT Trade Desk player/model inputs from index.html.
2. Fetch the current external SF dynasty RB board.
3. Exact-normalized-name match external RBs to Trade Desk PLAYER_DB.
4. Fit a no-age log-value model on RBs age 21-30:
       log(external_value)
         ~ intercept
         + log(prod_mult)
         + log(prod_mult)^2
         + Trade Desk role dummies
5. The residual is the market value left unexplained by production + role.
6. Group residuals by age and exponentiate relative to age 25:
       implied_age_factor(age)
         = exp(median_residual(age) - median_residual(age25))
7. Repeat for:
       meaningful-production cohort: raw/effective PM >= 0.35
       high-production cohort:       raw/effective PM >= 0.65
8. Compare age 21-25 implied factors against:
       current
       linear_to_25
       smoothstep_to_25
       quadratic_to_25
   using log-factor RMSE on ages with enough observations.
9. Bootstrap the high-production age factors for uncertainty.

No production files or live values are modified.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DIR = REPO_ROOT / "scripts" / "validation"
if str(VALIDATION_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATION_DIR))

import snapshot_values

INDEX_PATH = REPO_ROOT / "index.html"
OUT_JSON = REPO_ROOT / "research" / "age-calibration" / "young_rb_external_market_calibration.json"
OUT_MD = REPO_ROOT / "research" / "age-calibration" / "young_rb_external_market_calibration.md"

API_URL = (
    "https://api.statsguyfantasy.com/api/v1/rankings"
    "?format=sf_dynasty&position=RB&limit=1000"
)
USER_AGENT = "TradeDesk-RB-Age-Calibration/1.0"

CURRENT_COEFF = 0.384
CANDIDATES = ("current", "linear_to_25", "smoothstep_to_25", "quadratic_to_25")
ROLE_ORDER = ("Elite", "Every-Down", "Starter", "Rotational", "Understudy", "Depth")
REFERENCE_ROLE = "Speculative"

AGE_MIN = 21
AGE_MAX = 30
FACTOR_AGE_MIN = 21
FACTOR_AGE_MAX = 25
MEANINGFUL_PM = 0.35
HIGH_PM = 0.65
MIN_AGE_N = 2
BOOTSTRAP_ITERATIONS = 500
RANDOM_SEED = 20260902


def normalize_name(name: str) -> str:
    s = str(name or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    s = re.sub(r"\s+", " ", s)
    # Common suffix normalization, because Trade Desk keys generally omit them.
    s = re.sub(r"\s+(jr|sr|ii|iii|iv)$", "", s)
    return s.strip()


def fetch_external_board() -> dict[str, Any]:
    req = urllib.request.Request(API_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        raise RuntimeError(f"Failed to fetch external market board: {exc}") from exc


def live_current_elite_rb_am(age: int, peak_start: int = 23, peak_end: int = 25) -> float:
    years = min(4, max(0, peak_end - age))
    bonus = CURRENT_COEFF * math.sqrt(years)
    flat_base = 0.725 if age <= peak_start else 1.0
    return min(1.5, flat_base + bonus)


DEPLOYED_AGE21_AM = live_current_elite_rb_am(21)
MAX_PREMIUM = DEPLOYED_AGE21_AM - 1.0


def age_x(age: int) -> float:
    return max(0.0, min(1.0, (25.0 - age) / 4.0))


def candidate_am(age: int, candidate: str) -> float:
    if candidate == "current":
        return live_current_elite_rb_am(age)
    if age >= 25:
        return 1.0
    if age <= 21:
        return DEPLOYED_AGE21_AM

    x = age_x(age)
    if candidate == "linear_to_25":
        shape = x
    elif candidate == "smoothstep_to_25":
        shape = 3.0 * x * x - 2.0 * x * x * x
    elif candidate == "quadratic_to_25":
        shape = x * x
    else:
        raise ValueError(candidate)
    return 1.0 + MAX_PREMIUM * shape


def role_features(role: str) -> list[float]:
    return [1.0 if role == r else 0.0 for r in ROLE_ORDER]


def design_row(pm: float, role: str) -> list[float]:
    lp = math.log(max(pm, 1e-6))
    return [1.0, lp, lp * lp] + role_features(role)


def solve_linear_system(a: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting."""
    n = len(b)
    aug = [list(a[i]) + [b[i]] for i in range(n)]

    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            # Gentle ridge fallback for a rare singular bootstrap sample.
            aug[pivot][col] += 1e-8
        aug[col], aug[pivot] = aug[pivot], aug[col]

        div = aug[col][col]
        if abs(div) < 1e-15:
            raise RuntimeError("Singular calibration design matrix.")
        aug[col] = [x / div for x in aug[col]]

        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            if factor == 0:
                continue
            aug[r] = [rv - factor * cv for rv, cv in zip(aug[r], aug[col])]

    return [aug[i][-1] for i in range(n)]


def fit_ols(rows: list[dict[str, Any]]) -> list[float]:
    xs = [design_row(r["pm"], r["role"]) for r in rows]
    ys = [math.log(r["external_value"]) for r in rows]
    p = len(xs[0])

    xtx = [[0.0] * p for _ in range(p)]
    xty = [0.0] * p

    for x, y in zip(xs, ys):
        for i in range(p):
            xty[i] += x[i] * y
            for j in range(p):
                xtx[i][j] += x[i] * x[j]

    # Tiny ridge only on non-intercept terms for numerical stability.
    for i in range(1, p):
        xtx[i][i] += 1e-8

    return solve_linear_system(xtx, xty)


def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def add_residuals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    beta = fit_ols(rows)
    out = []
    for r in rows:
        rr = dict(r)
        pred = dot(design_row(r["pm"], r["role"]), beta)
        rr["log_external_value"] = math.log(r["external_value"])
        rr["predicted_log_value_no_age"] = pred
        rr["residual_log_value"] = rr["log_external_value"] - pred
        out.append(rr)
    return out


def median_age_residuals(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    grouped = defaultdict(list)
    for r in rows:
        if FACTOR_AGE_MIN <= r["age"] <= FACTOR_AGE_MAX:
            grouped[r["age"]].append(r["residual_log_value"])

    if 25 not in grouped:
        return {}

    base = statistics.median(grouped[25])
    out = {}
    for age in range(FACTOR_AGE_MIN, FACTOR_AGE_MAX + 1):
        vals = grouped.get(age, [])
        if not vals:
            continue
        med = statistics.median(vals)
        out[age] = {
            "n": len(vals),
            "median_residual": med,
            "factor_vs_age25": math.exp(med - base),
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


def bootstrap_age_factors(rows: list[dict[str, Any]], iterations: int) -> dict[int, dict[str, Any]]:
    rng = random.Random(RANDOM_SEED)
    samples = defaultdict(list)
    n = len(rows)

    for _ in range(iterations):
        boot = [rows[rng.randrange(n)] for __ in range(n)]
        try:
            resid = add_residuals(boot)
            factors = median_age_residuals(resid)
        except Exception:
            continue

        # Require a valid age-25 anchor in the bootstrap sample.
        if 25 not in factors:
            continue

        for age, rec in factors.items():
            samples[age].append(rec["factor_vs_age25"])

    out = {}
    for age in range(FACTOR_AGE_MIN, FACTOR_AGE_MAX + 1):
        vals = samples.get(age, [])
        if not vals:
            continue
        out[age] = {
            "bootstrap_n": len(vals),
            "median": statistics.median(vals),
            "p10": percentile(vals, 0.10),
            "p90": percentile(vals, 0.90),
        }
    return out


def compare_candidates(factors: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for candidate in CANDIDATES:
        errors = []
        ages = []
        for age in range(FACTOR_AGE_MIN, FACTOR_AGE_MAX + 1):
            rec = factors.get(age)
            if not rec or rec["n"] < MIN_AGE_N:
                continue
            market_factor = rec["factor_vs_age25"]
            model_factor = candidate_am(age, candidate)
            errors.append((math.log(model_factor) - math.log(market_factor)) ** 2)
            ages.append(age)

        rmse = math.sqrt(sum(errors) / len(errors)) if errors else None
        results.append({
            "candidate": candidate,
            "ages_used": ages,
            "log_factor_rmse": rmse,
        })

    results.sort(
        key=lambda r: (
            float("inf") if r["log_factor_rmse"] is None else r["log_factor_rmse"],
            r["candidate"],
        )
    )
    return results


def make_model_rows(cfg: dict[str, Any], board: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    external = board.get("rankings") or []
    by_norm = defaultdict(list)
    for row in external:
        norm = normalize_name(row.get("name"))
        if norm:
            by_norm[norm].append(row)

    matched = []
    unmatched = []
    ambiguous = []

    for key, info in cfg["player_db"].items():
        if info["pos"] != "RB":
            continue
        age = int(info["age"])
        if not AGE_MIN <= age <= AGE_MAX:
            continue

        norm = normalize_name(key)
        candidates = by_norm.get(norm, [])
        if not candidates:
            unmatched.append(key)
            continue
        if len(candidates) != 1:
            ambiguous.append({"player": key, "external": [r.get("name") for r in candidates]})
            continue

        ext = candidates[0]
        value = ext.get("value")
        if not isinstance(value, (int, float)) or value <= 0:
            continue

        pm, raw = snapshot_values.production_multiplier(
            key, info["role"], cfg["prod_mult"], cfg["no_real_history"], cfg["role_mult"]
        )
        pm = float(pm)
        raw_pm = float(raw) if isinstance(raw, (int, float)) else None

        matched.append({
            "player": key,
            "external_id": str(ext.get("id")),
            "external_name": ext.get("name"),
            "external_value": float(value),
            "external_position_rank": ext.get("positionRank"),
            "age": age,
            "role": info["role"],
            "pm": pm,
            "raw_pm": raw_pm,
            "has_raw_pm": raw_pm is not None,
        })

    return matched, {
        "external_total_rb": len(external),
        "matched_model_rb_age_21_30": len(matched),
        "unmatched_model_names": unmatched,
        "ambiguous_model_names": ambiguous,
    }


def analyze_cohort(rows: list[dict[str, Any]], threshold: float, do_bootstrap: bool) -> dict[str, Any]:
    cohort = [r for r in rows if r["pm"] >= threshold]
    if len(cohort) < 12:
        raise RuntimeError(f"Too few rows for threshold {threshold}: {len(cohort)}")

    residual_rows = add_residuals(cohort)
    factors = median_age_residuals(residual_rows)

    factor_serialized = {
        str(age): {
            "n": rec["n"],
            "median_residual": round(rec["median_residual"], 6),
            "factor_vs_age25": round(rec["factor_vs_age25"], 6),
        }
        for age, rec in sorted(factors.items())
    }

    boot = {}
    if do_bootstrap:
        raw_boot = bootstrap_age_factors(cohort, BOOTSTRAP_ITERATIONS)
        boot = {
            str(age): {
                "bootstrap_n": rec["bootstrap_n"],
                "median": round(rec["median"], 6),
                "p10": round(rec["p10"], 6) if rec["p10"] is not None else None,
                "p90": round(rec["p90"], 6) if rec["p90"] is not None else None,
            }
            for age, rec in sorted(raw_boot.items())
        }

    comparisons = compare_candidates(factors)
    for rec in comparisons:
        if rec["log_factor_rmse"] is not None:
            rec["log_factor_rmse"] = round(rec["log_factor_rmse"], 6)

    age_counts = Counter(r["age"] for r in cohort)

    return {
        "pm_threshold": threshold,
        "n": len(cohort),
        "age_counts": {str(k): v for k, v in sorted(age_counts.items())},
        "implied_age_factors": factor_serialized,
        "bootstrap_age_factors": boot,
        "candidate_comparison": comparisons,
        "matched_players": sorted(
            [
                {
                    "player": r["player"],
                    "age": r["age"],
                    "role": r["role"],
                    "pm": round(r["pm"], 6),
                    "raw_pm": round(r["raw_pm"], 6) if r["raw_pm"] is not None else None,
                    "external_value": int(r["external_value"]),
                    "external_position_rank": r["external_position_rank"],
                }
                for r in cohort
            ],
            key=lambda r: (r["age"], -r["external_value"], r["player"]),
        ),
    }


def build_report() -> dict[str, Any]:
    cfg = snapshot_values.load_from_html(INDEX_PATH)
    board = fetch_external_board()
    rows, identity = make_model_rows(cfg, board)

    meaningful = analyze_cohort(rows, MEANINGFUL_PM, do_bootstrap=False)
    high = analyze_cohort(rows, HIGH_PM, do_bootstrap=True)

    return {
        "audit": "young-rb-external-market-age-calibration-v1",
        "production_changes": False,
        "external_source": {
            "provider": "Stats Guy Fantasy",
            "endpoint": API_URL,
            "format": board.get("format"),
            "as_of": board.get("asOf"),
            "description": (
                "External trade-derived SF dynasty market signal. Used as independent "
                "calibration evidence, not as fundamental truth."
            ),
        },
        "method": {
            "outcome": "log(external SF dynasty value)",
            "controls": [
                "log Trade Desk production multiplier",
                "squared log Trade Desk production multiplier",
                "Trade Desk role dummies",
            ],
            "age_factor": "median residual by age, exponentiated relative to age 25",
            "candidate_metric": "RMSE of log implied age factor vs candidate age multiplier",
            "bootstrap_iterations_high_production": BOOTSTRAP_ITERATIONS,
        },
        "identity": identity,
        "candidate_profiles": {
            candidate: {
                str(age): round(candidate_am(age, candidate), 6)
                for age in range(FACTOR_AGE_MIN, FACTOR_AGE_MAX + 1)
            }
            for candidate in CANDIDATES
        },
        "meaningful_production": meaningful,
        "high_production": high,
    }


def fmt_factor(v: Any) -> str:
    return "n/a" if v is None else f"{float(v):.3f}"


def write_md(report: dict[str, Any]) -> None:
    ext = report["external_source"]
    lines = [
        "# Young RB External Market Age Calibration",
        "",
        "**Status:** research-only; no production values changed.",
        "",
        "## External evidence",
        "",
        f"- Provider: **{ext['provider']}**",
        f"- Format: **{ext.get('format')}**",
        f"- External snapshot: **{ext.get('as_of')}**",
        "- Signal: real-trade-derived broad SF dynasty market value.",
        "- Use in this audit: independent calibration evidence only, not fundamental truth.",
        "",
        "## Method",
        "",
        "For RBs age 21-30, fit external log market value after controlling for Trade Desk "
        "production multiplier (linear + squared log term) and Trade Desk role. The remaining "
        "median residual by age is converted into a market-implied age factor relative to age 25.",
        "",
        "Two cohorts are shown:",
        "",
        f"- meaningful production: PM >= {MEANINGFUL_PM}",
        f"- high production: PM >= {HIGH_PM}",
        "",
    ]

    for label, key in [
        ("High-production cohort", "high_production"),
        ("Meaningful-production cohort", "meaningful_production"),
    ]:
        c = report[key]
        lines += [
            f"## {label}",
            "",
            f"- N: **{c['n']}**",
            "",
            "| Age | N | Implied factor vs age 25 | Bootstrap P10 | Bootstrap P90 | Current | Linear | Smoothstep | Quadratic |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]

        factors = c["implied_age_factors"]
        boot = c.get("bootstrap_age_factors") or {}
        profiles = report["candidate_profiles"]

        for age in range(21, 26):
            rec = factors.get(str(age), {})
            b = boot.get(str(age), {})
            lines.append(
                f"| {age} | {rec.get('n', 0)} | {fmt_factor(rec.get('factor_vs_age25'))} | "
                f"{fmt_factor(b.get('p10'))} | {fmt_factor(b.get('p90'))} | "
                f"{profiles['current'][str(age)]:.3f} | "
                f"{profiles['linear_to_25'][str(age)]:.3f} | "
                f"{profiles['smoothstep_to_25'][str(age)]:.3f} | "
                f"{profiles['quadratic_to_25'][str(age)]:.3f} |"
            )

        lines += [
            "",
            "### Candidate fit",
            "",
            "| Rank | Candidate | Ages used | Log-factor RMSE |",
            "|---:|---|---|---:|",
        ]
        for i, rec in enumerate(c["candidate_comparison"], 1):
            rmse = "n/a" if rec["log_factor_rmse"] is None else f"{rec['log_factor_rmse']:.4f}"
            ages = ", ".join(str(x) for x in rec["ages_used"])
            lines.append(f"| {i} | {rec['candidate']} | {ages} | {rmse} |")
        lines.append("")

    lines += [
        "## Interpretation boundary",
        "",
        "This is cross-sectional market calibration, not causal proof of aging. Production and role controls "
        "reduce obvious confounding, but external managers may price draft capital, injury risk, draft pedigree, "
        "contract status, team context, and future upside not fully captured by Trade Desk PM/role.",
        "",
        "A production change should only be considered if the high-production cohort has enough age coverage, "
        "the bootstrap intervals are informative, and one candidate has a materially better fit without "
        "reintroducing a discontinuity.",
        "",
    ]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def run_selftest() -> None:
    # Candidate shape invariants.
    for candidate in ("linear_to_25", "smoothstep_to_25", "quadratic_to_25"):
        vals = [candidate_am(age, candidate) for age in range(21, 26)]
        assert abs(vals[0] - DEPLOYED_AGE21_AM) < 1e-12
        assert abs(vals[-1] - 1.0) < 1e-12
        assert all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1))

    current = [candidate_am(age, "current") for age in range(21, 26)]
    assert current[3] > current[2]  # known age-23 -> 24 bump
    assert abs(current[3] - 1.384) < 1e-12
    assert abs(current[4] - 1.0) < 1e-12

    # OLS synthetic recovery sanity check.
    synthetic = []
    for age in range(21, 31):
        for i, pm in enumerate((0.4, 0.7, 1.0, 1.3)):
            role = ("Starter", "Every-Down", "Elite", "Rotational")[i]
            # Exact no-age relation, so residual age effect should be ~1 at every age.
            lp = math.log(pm)
            y = 6.0 + 0.8 * lp - 0.1 * lp * lp
            synthetic.append({
                "player": f"p{age}_{i}",
                "external_value": math.exp(y),
                "age": age,
                "role": role,
                "pm": pm,
                "raw_pm": pm,
            })
    resid = add_residuals(synthetic)
    factors = median_age_residuals(resid)
    for rec in factors.values():
        assert abs(rec["factor_vs_age25"] - 1.0) < 1e-6

    print("young_rb_external_market_calibration self-test passed.")


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
