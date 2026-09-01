#!/usr/bin/env python3
"""
build_value_uncertainty.py

Build a deterministic per-player Trade Desk VALUE UNCERTAINTY artifact.

IMPORTANT SEMANTICS
-------------------
This is NOT a calibrated 80%, 90%, or 95% confidence interval.

The historical out-of-sample system is live, but future horizons have not yet
matured enough to estimate empirical interval coverage. V1 therefore reports a
transparent SENSITIVITY ENVELOPE around the current deployed point value.

The point estimate is never changed here.

V1 uses three observable sources of dispersion:
1. Projection-provider disagreement
   - Sleeper vs FantasyPros, on the same Sleeper identity.
   - If only one provider exists, use the position cohort's observed median
     provider half-spread.
   - If neither exists, use the position cohort's observed 75th percentile.
2. Historical sampling noise
   - Standard error of 2025 active-game fantasy points from ppg_results.json,
     normalized by the position's median active-game PPG.
   - Players with insufficient/no history receive the position cohort's
     observed 75th-percentile sampling component.
3. Availability-history uncertainty
   - 2025 missed-game share × sqrt(position durability R²).
   - This intentionally uses persistence strength, not 1-R²: if missed games
     have little demonstrated year-over-year persistence, V1 does not pretend
     that the specific prior absence should strongly carry forward.
   - Players with no history receive the position cohort's observed
     75th-percentile availability component.

The three relative components are combined by root-sum-square. The final
half-width is capped at 100% only as a numerical guard against pathological
inputs. Uncertainty tiers are quartiles of the CURRENT model population, not
hard-coded claims about probability.

Outputs
-------
scripts/artifacts/generated/value_uncertainty.json
scripts/artifacts/reports/value_uncertainty_report.md

Usage
-----
python3 scripts/validation/build_value_uncertainty.py --write
python3 scripts/validation/build_value_uncertainty.py --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any



REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = REPO_ROOT / "index.html"
SLEEPER_IDENTITY_PATH = (
    REPO_ROOT / "scripts" / "artifacts" / "generated" / "sleeper_2026_raw_categories.json"
)
SLEEPER_PROJECTIONS_PATH = REPO_ROOT / "scripts" / "sleeper_2026_projections.json"
FANTASYPROS_PATH = REPO_ROOT / "scripts" / "fantasypros_api_normalized_2026.json"
IDENTITY_CROSSWALK_PATH = REPO_ROOT / "scripts" / "identity_crosswalk.json"
PPG_PATH = REPO_ROOT / "scripts" / "ppg_results.json"
DURABILITY_PATH = REPO_ROOT / "scripts" / "durability_results.json"

OUTPUT_JSON = REPO_ROOT / "scripts" / "artifacts" / "generated" / "value_uncertainty.json"
OUTPUT_MD = REPO_ROOT / "scripts" / "artifacts" / "reports" / "value_uncertainty_report.md"

METHOD_VERSION = "sensitivity-envelope-v1"
RANGE_SEMANTICS = "sensitivity_envelope_v1_not_probability_interval"
REGULAR_SEASON_GAMES = 17
MAX_RELATIVE_HALF_WIDTH = 1.0

POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB", "K")

POLICY = {
    "method_version": METHOD_VERSION,
    "range_semantics": RANGE_SEMANTICS,
    "center_value_policy": "exact deployed snapshot_values.compute_all_values value; never modified",
    "projection_component": (
        "abs(Sleeper-FantasyPros)/(Sleeper+FantasyPros), which is the provider "
        "half-spread divided by their mean; one-provider uses position median; "
        "zero-provider uses position p75"
    ),
    "history_component": (
        "sample standard error of active-game 2025 fantasy points divided by "
        "position median active-game PPG; <2 games uses position p75"
    ),
    "availability_component": (
        "2025 missed-game share * sqrt(position durability R^2); no history uses position p75"
    ),
    "combination": "root-sum-square of the three relative components",
    "max_relative_half_width": MAX_RELATIVE_HALF_WIDTH,
    "tiers": "quartiles of current-player relative half-width; descriptive, not probability levels",
}

POLICY_SHA256 = hashlib.sha256(
    json.dumps(POLICY, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


def read_json(path: Path) -> Any:
    if not path.exists():
        raise RuntimeError(f"Required uncertainty input is missing: {path.relative_to(REPO_ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON: {path.relative_to(REPO_ROOT)}: {exc}") from exc


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def finite_nonnegative(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or x < 0:
        return None
    return x


def percentile(values: list[float], q: float) -> float:
    vals = sorted(float(v) for v in values if math.isfinite(float(v)))
    if not vals:
        return 0.0
    if len(vals) == 1:
        return vals[0]
    q = max(0.0, min(1.0, q))
    idx = (len(vals) - 1) * q
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    frac = idx - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def sample_sd(values: list[float]) -> float | None:
    clean = [float(v) for v in values if math.isfinite(float(v))]
    if len(clean) < 2:
        return None
    return statistics.stdev(clean)


def provider_half_spread(a: float, b: float) -> float:
    """
    Half of the provider spread divided by provider mean:
       (|a-b|/2) / ((a+b)/2) == |a-b|/(a+b)
    Naturally bounded [0,1] for nonnegative projections.
    """
    if a < 0 or b < 0:
        raise RuntimeError("Projection totals must be nonnegative")
    denom = a + b
    if denom <= 0:
        return 0.0
    return abs(a - b) / denom


def normalize_fp_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        rows = payload.get("players")
    else:
        rows = payload
    if not isinstance(rows, list):
        raise RuntimeError("FantasyPros normalized payload must contain a players list")
    return [row for row in rows if isinstance(row, dict)]


def build_fp_points_by_sleeper(
    fp_payload: Any,
    crosswalk_rows: Any,
) -> dict[str, list[dict[str, Any]]]:
    fp_rows = normalize_fp_payload(fp_payload)
    if not isinstance(crosswalk_rows, list):
        raise RuntimeError("identity_crosswalk.json must contain a JSON list")

    fp_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in fp_rows:
        fid = str(row.get("fantasypros_id") or "").strip()
        points = finite_nonnegative(row.get("trade_desk_normalized_points"))
        if not fid or points is None:
            continue
        fp_by_id[fid].append({
            "points": points,
            "source_position": str(row.get("source_position") or ""),
            "query_position": str(row.get("query_position") or ""),
            "name": row.get("normalized_name") or row.get("name"),
        })

    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in crosswalk_rows:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("sleeper_id") or "").strip()
        fid = str(row.get("fantasypros_id") or "").strip()
        if not sid or not fid:
            continue
        for fp in fp_by_id.get(fid, []):
            out[sid].append({
                **fp,
                "crosswalk_fp_position": str(row.get("fp_position") or ""),
            })
    return dict(out)


def choose_fp_points(candidates: list[dict[str, Any]], model_pos: str) -> float | None:
    usable = [c for c in candidates if finite_nonnegative(c.get("points")) is not None]
    if not usable:
        return None

    exact = [
        c for c in usable
        if model_pos in {
            str(c.get("source_position") or ""),
            str(c.get("query_position") or ""),
            str(c.get("crosswalk_fp_position") or ""),
        }
    ]
    pool = exact if exact else usable

    # De-duplicate identical numeric projection totals.
    unique_values = sorted({round(float(c["points"]), 8) for c in pool})
    if len(unique_values) == 1:
        return unique_values[0]

    # If exact-position filtering isolated one row, trust it. Otherwise ambiguity
    # is safer to treat as missing than to silently choose the wrong dual-eligible row.
    if len(exact) == 1:
        return float(exact[0]["points"])
    if not exact and len(usable) == 1:
        return float(usable[0]["points"])
    return None


def build_history_by_sleeper(rows: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        raise RuntimeError("ppg_results.json must contain a JSON list")
    out = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("sleeper_id") or "").strip()
        if not sid:
            continue
        points = row.get("weekly_points") or []
        if not isinstance(points, list):
            points = []
        clean_points = []
        for value in points:
            x = finite_nonnegative(value)
            if x is not None:
                clean_points.append(x)
        out[sid] = {
            "player": row.get("player"),
            "pos": str(row.get("pos") or ""),
            "games": int(row.get("games_played") or len(clean_points) or 0),
            "weekly_points": clean_points,
            "ppg": finite_nonnegative(row.get("true_ppg")),
        }
    return out


def build_sleeper_projection_map(rows: Any) -> dict[str, float]:
    if not isinstance(rows, list):
        raise RuntimeError("Sleeper projection file must contain a JSON list")
    out = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("sleeper_id") or "").strip()
        points = finite_nonnegative(row.get("sleeper_2026_proj_total"))
        if sid and points is not None:
            out[sid] = points
    return out


def history_component_raw(history: dict[str, Any], position_scale_ppg: float) -> float | None:
    points = history.get("weekly_points") or []
    if len(points) < 2 or position_scale_ppg <= 0:
        return None
    sd = sample_sd(points)
    if sd is None:
        return None
    sem = sd / math.sqrt(len(points))
    return sem / position_scale_ppg


def availability_component_raw(
    history: dict[str, Any],
    durability_r2: float | None,
) -> float | None:
    if durability_r2 is None:
        return None
    games = max(0, min(REGULAR_SEASON_GAMES, int(history.get("games") or 0)))
    missed_share = (REGULAR_SEASON_GAMES - games) / REGULAR_SEASON_GAMES
    return missed_share * math.sqrt(max(0.0, min(1.0, durability_r2)))


def build_position_cohorts(
    model_values: dict[str, dict[str, Any]],
    model_to_sleeper: dict[str, str],
    sleeper_points: dict[str, float],
    fp_candidates: dict[str, list[dict[str, Any]]],
    history_by_sid: dict[str, dict[str, Any]],
    durability: dict[str, Any],
) -> dict[str, dict[str, float]]:
    provider_by_pos: dict[str, list[float]] = defaultdict(list)
    history_ppg_by_pos: dict[str, list[float]] = defaultdict(list)
    history_component_by_pos: dict[str, list[float]] = defaultdict(list)
    availability_by_pos: dict[str, list[float]] = defaultdict(list)

    # First pass: position PPG scales.
    for model_key, info in model_values.items():
        pos = str(info.get("pos") or "")
        sid = model_to_sleeper.get(model_key)
        hist = history_by_sid.get(sid or "")
        if hist:
            ppg = finite_nonnegative(hist.get("ppg"))
            if ppg is None and hist.get("weekly_points"):
                ppg = sum(hist["weekly_points"]) / len(hist["weekly_points"])
            if ppg is not None and ppg > 0:
                history_ppg_by_pos[pos].append(ppg)

    global_ppg = [x for vals in history_ppg_by_pos.values() for x in vals]
    global_ppg_median = percentile(global_ppg, 0.5) or 1.0

    ppg_scale = {
        pos: (percentile(history_ppg_by_pos.get(pos, []), 0.5) or global_ppg_median)
        for pos in POSITIONS
    }

    for model_key, info in model_values.items():
        pos = str(info.get("pos") or "")
        sid = model_to_sleeper.get(model_key)
        if not sid:
            continue

        sp = sleeper_points.get(sid)
        fp = choose_fp_points(fp_candidates.get(sid, []), pos)
        if sp is not None and fp is not None:
            provider_by_pos[pos].append(provider_half_spread(sp, fp))

        hist = history_by_sid.get(sid)
        if hist:
            hc = history_component_raw(hist, ppg_scale.get(pos, global_ppg_median))
            if hc is not None:
                history_component_by_pos[pos].append(hc)

            r2 = finite_nonnegative((durability.get(pos) or {}).get("r_squared"))
            ac = availability_component_raw(hist, r2)
            if ac is not None:
                availability_by_pos[pos].append(ac)

    global_provider = [x for vals in provider_by_pos.values() for x in vals]
    global_history = [x for vals in history_component_by_pos.values() for x in vals]
    global_availability = [x for vals in availability_by_pos.values() for x in vals]

    cohorts = {}
    for pos in POSITIONS:
        providers = provider_by_pos.get(pos, [])
        histories = history_component_by_pos.get(pos, [])
        availability = availability_by_pos.get(pos, [])
        cohorts[pos] = {
            "provider_half_spread_median": round(
                percentile(providers or global_provider, 0.50), 6
            ),
            "provider_half_spread_p75": round(
                percentile(providers or global_provider, 0.75), 6
            ),
            "history_relative_sem_p75": round(
                percentile(histories or global_history, 0.75), 6
            ),
            "availability_component_p75": round(
                percentile(availability or global_availability, 0.75), 6
            ),
            "position_median_active_ppg": round(ppg_scale.get(pos, global_ppg_median), 6),
            "durability_r_squared": (
                round(float((durability.get(pos) or {}).get("r_squared")), 6)
                if finite_nonnegative((durability.get(pos) or {}).get("r_squared")) is not None
                else None
            ),
            "provider_both_sample_n": len(providers),
            "history_sampling_sample_n": len(histories),
            "availability_sample_n": len(availability),
        }
    return cohorts


def build_records(
    model_values: dict[str, dict[str, Any]],
    model_to_sleeper: dict[str, str],
    sleeper_points: dict[str, float],
    fp_candidates: dict[str, list[dict[str, Any]]],
    history_by_sid: dict[str, dict[str, Any]],
    durability: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, float]]]:
    cohorts = build_position_cohorts(
        model_values,
        model_to_sleeper,
        sleeper_points,
        fp_candidates,
        history_by_sid,
        durability,
    )

    players: dict[str, dict[str, Any]] = {}
    widths = []

    for model_key, info in model_values.items():
        pos = str(info.get("pos") or "")
        cohort = cohorts.get(pos) or {}
        sid = model_to_sleeper.get(model_key)
        sp = sleeper_points.get(sid or "")
        fp = choose_fp_points(fp_candidates.get(sid or "", []), pos)
        hist = history_by_sid.get(sid or "")

        if sp is not None and fp is not None:
            provider_component = provider_half_spread(sp, fp)
            provider_basis = "observed_two_provider_half_spread"
            provider_count = 2
        elif sp is not None or fp is not None:
            provider_component = float(cohort.get("provider_half_spread_median") or 0.0)
            provider_basis = "position_median_imputed_one_provider"
            provider_count = 1
        else:
            provider_component = float(cohort.get("provider_half_spread_p75") or 0.0)
            provider_basis = "position_p75_imputed_zero_provider"
            provider_count = 0

        if hist:
            history_component = history_component_raw(
                hist, float(cohort.get("position_median_active_ppg") or 1.0)
            )
        else:
            history_component = None
        if history_component is None:
            history_component = float(cohort.get("history_relative_sem_p75") or 0.0)
            history_basis = "position_p75_imputed_insufficient_history"
        else:
            history_basis = "observed_2025_sampling_sem"

        durability_r2 = finite_nonnegative(cohort.get("durability_r_squared"))
        availability_component = (
            availability_component_raw(hist, durability_r2) if hist else None
        )
        if availability_component is None:
            availability_component = float(cohort.get("availability_component_p75") or 0.0)
            availability_basis = "position_p75_imputed_no_history"
        else:
            availability_basis = "observed_missed_game_share_times_sqrt_persistence"

        raw_width = math.sqrt(
            provider_component ** 2
            + history_component ** 2
            + availability_component ** 2
        )
        half_width = min(MAX_RELATIVE_HALF_WIDTH, raw_width)

        center = int(info.get("value") or 0)
        low = max(0, int(math.floor(center * (1.0 - half_width) + 0.5)))
        high = max(center, int(math.floor(center * (1.0 + half_width) + 0.5)))

        games = int(hist.get("games") or 0) if hist else 0
        record = {
            "pos": pos,
            "age": info.get("age"),
            "role": info.get("role"),
            "center_value": center,
            "range_low": low,
            "range_high": high,
            "relative_half_width": round(half_width, 6),
            "range_semantics": RANGE_SEMANTICS,
            "sleeper_id": sid,
            "signals": {
                "projection_provider_count": provider_count,
                "sleeper_projection_points": round(sp, 4) if sp is not None else None,
                "fantasypros_projection_points": round(fp, 4) if fp is not None else None,
                "provider_disagreement_component": round(provider_component, 6),
                "provider_component_basis": provider_basis,
                "history_games_2025": games,
                "history_sampling_component": round(history_component, 6),
                "history_component_basis": history_basis,
                "availability_component": round(availability_component, 6),
                "availability_component_basis": availability_basis,
                "durability_r_squared": (
                    round(durability_r2, 6) if durability_r2 is not None else None
                ),
                "no_real_production_history": bool(info.get("no_real_production_history")),
            },
        }
        players[model_key] = record
        widths.append(half_width)

    q25 = percentile(widths, 0.25)
    q50 = percentile(widths, 0.50)
    q75 = percentile(widths, 0.75)

    for record in players.values():
        width = float(record["relative_half_width"])
        if width <= q25:
            tier = "low"
        elif width <= q50:
            tier = "moderate"
        elif width <= q75:
            tier = "high"
        else:
            tier = "very_high"
        record["uncertainty_tier"] = tier

    cohorts["_population_width_quartiles"] = {
        "q25": round(q25, 6),
        "q50": round(q50, 6),
        "q75": round(q75, 6),
    }
    return players, cohorts


def build_payload() -> dict[str, Any]:
    # Imported lazily so --selftest can exercise the pure uncertainty math in
    # isolation; in the repo these sibling validation modules are on sys.path.
    import snapshot_values
    import capture_realized_outcomes
    required_paths = {
        "index_html": INDEX_PATH,
        "sleeper_identity": SLEEPER_IDENTITY_PATH,
        "sleeper_projections": SLEEPER_PROJECTIONS_PATH,
        "fantasypros_normalized": FANTASYPROS_PATH,
        "identity_crosswalk": IDENTITY_CROSSWALK_PATH,
        "ppg_results": PPG_PATH,
        "durability_results": DURABILITY_PATH,
    }
    for path in required_paths.values():
        if not path.exists():
            raise RuntimeError(f"Missing required uncertainty input: {path.relative_to(REPO_ROOT)}")

    cfg = snapshot_values.load_from_html(INDEX_PATH)
    model_values = snapshot_values.compute_all_values(cfg)

    identity_rows = read_json(SLEEPER_IDENTITY_PATH)
    by_name, by_id = capture_realized_outcomes.build_sleeper_identity_index(identity_rows)
    resolved, unresolved = capture_realized_outcomes.resolve_model_identities(
        cfg["player_db"], by_name, by_id
    )
    if unresolved:
        raise RuntimeError(
            f"Uncertainty engine requires complete model identity coverage; unresolved={unresolved[:5]}"
        )
    model_to_sleeper = {
        key: str(row["sleeper_id"])
        for key, row in resolved.items()
    }

    sleeper_points = build_sleeper_projection_map(read_json(SLEEPER_PROJECTIONS_PATH))
    fp_candidates = build_fp_points_by_sleeper(
        read_json(FANTASYPROS_PATH),
        read_json(IDENTITY_CROSSWALK_PATH),
    )
    history = build_history_by_sleeper(read_json(PPG_PATH))
    durability = read_json(DURABILITY_PATH)
    if not isinstance(durability, dict):
        raise RuntimeError("durability_results.json must contain a JSON object")

    players, cohorts = build_records(
        model_values,
        model_to_sleeper,
        sleeper_points,
        fp_candidates,
        history,
        durability,
    )

    provider_counts = defaultdict(int)
    tier_counts = defaultdict(int)
    history_counts = defaultdict(int)
    for row in players.values():
        provider_counts[str(row["signals"]["projection_provider_count"])] += 1
        tier_counts[row["uncertainty_tier"]] += 1
        history_counts["with_2plus_games" if row["signals"]["history_games_2025"] >= 2 else "insufficient"] += 1

    payload = {
        "schema_version": 1,
        "method_version": METHOD_VERSION,
        "range_semantics": RANGE_SEMANTICS,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "policy": POLICY,
        "policy_sha256": POLICY_SHA256,
        "source_file_sha256": {
            name: sha256_file(path)
            for name, path in required_paths.items()
        },
        "counts": {
            "player_count": len(players),
            "projection_provider_count": dict(sorted(provider_counts.items())),
            "uncertainty_tiers": dict(sorted(tier_counts.items())),
            "history_coverage": dict(sorted(history_counts.items())),
        },
        "position_cohorts": cohorts,
        "players": players,
    }
    validate_payload(payload)
    return payload


def validate_payload(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise RuntimeError("Unexpected uncertainty schema version")
    if payload.get("method_version") != METHOD_VERSION:
        raise RuntimeError("Unexpected uncertainty method version")
    if payload.get("range_semantics") != RANGE_SEMANTICS:
        raise RuntimeError("Uncertainty semantics drifted")
    players = payload.get("players")
    if not isinstance(players, dict) or len(players) < 500:
        raise RuntimeError(
            f"Uncertainty player coverage unexpectedly small: "
            f"{len(players) if isinstance(players, dict) else 'invalid'}"
        )
    for key, row in players.items():
        center = int(row["center_value"])
        low = int(row["range_low"])
        high = int(row["range_high"])
        if low > center or high < center:
            raise RuntimeError(f"Uncertainty range does not contain center for {key}")
        width = float(row["relative_half_width"])
        if not (0.0 <= width <= MAX_RELATIVE_HALF_WIDTH):
            raise RuntimeError(f"Invalid uncertainty width for {key}: {width}")
        if row.get("range_semantics") != RANGE_SEMANTICS:
            raise RuntimeError(f"Missing range semantics for {key}")


def render_report(payload: dict[str, Any]) -> str:
    counts = payload["counts"]
    quartiles = payload["position_cohorts"]["_population_width_quartiles"]

    by_pos = defaultdict(list)
    for key, row in payload["players"].items():
        by_pos[row["pos"]].append((key, row))

    lines = [
        "# Trade Desk Value Uncertainty — Sensitivity Envelope V1",
        "",
        f"Method: `{METHOD_VERSION}`  ",
        f"Policy SHA256: `{payload['policy_sha256']}`",
        "",
        "## Critical interpretation",
        "",
        "**These ranges are not probability confidence intervals.** They are deterministic "
        "sensitivity envelopes around the deployed point value using currently observable "
        "projection disagreement, historical sampling noise, and availability-history signal.",
        "",
        f"- Players: **{counts['player_count']}**",
        f"- Width quartiles: Q25 **{quartiles['q25']:.1%}**, median **{quartiles['q50']:.1%}**, Q75 **{quartiles['q75']:.1%}**",
        f"- Provider coverage (0/1/2): **{counts['projection_provider_count']}**",
        f"- History coverage: **{counts['history_coverage']}**",
        "",
        "## Position summary",
        "",
        "| Pos | N | Median half-width | Median provider component | Median history component | Median availability component |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for pos in POSITIONS:
        rows = by_pos.get(pos, [])
        if not rows:
            continue
        widths = [float(r["relative_half_width"]) for _, r in rows]
        providers = [float(r["signals"]["provider_disagreement_component"]) for _, r in rows]
        histories = [float(r["signals"]["history_sampling_component"]) for _, r in rows]
        availability = [float(r["signals"]["availability_component"]) for _, r in rows]
        lines.append(
            f"| {pos} | {len(rows)} | {percentile(widths, .5):.1%} | "
            f"{percentile(providers, .5):.1%} | {percentile(histories, .5):.1%} | "
            f"{percentile(availability, .5):.1%} |"
        )

    widest = sorted(
        payload["players"].items(),
        key=lambda kv: (-float(kv[1]["relative_half_width"]), kv[0]),
    )[:20]
    lines.extend([
        "",
        "## Widest current envelopes",
        "",
        "| Player | Pos | Center | Low | High | Half-width | Tier |",
        "|---|---|---:|---:|---:|---:|---|",
    ])
    for key, row in widest:
        lines.append(
            f"| {key} | {row['pos']} | {row['center_value']} | {row['range_low']} | "
            f"{row['range_high']} | {float(row['relative_half_width']):.1%} | "
            f"{row['uncertainty_tier']} |"
        )

    lines.extend([
        "",
        "## V1 guardrails",
        "",
        "- The center value is unchanged from the deployed calculator.",
        "- KTC/internal market ratings are not used as fundamental uncertainty truth.",
        "- Injury status is not converted into an unvalidated point-value penalty.",
        "- Missing-source imputation comes from observed position-cohort dispersion.",
        "- The envelope will only receive a probability label after out-of-sample calibration supports one.",
        "",
    ])
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUTPUT_MD.write_text(render_report(payload), encoding="utf-8")
    print(
        f"Value uncertainty written: {OUTPUT_JSON.relative_to(REPO_ROOT)} "
        f"({payload['counts']['player_count']} players)"
    )
    print(f"Report written: {OUTPUT_MD.relative_to(REPO_ROOT)}")
    print(f"Range semantics: {RANGE_SEMANTICS}")


def run_selftest() -> None:
    # 16 players provides enough population to exercise quartile tiering.
    model_values = {}
    model_to_sid = {}
    sleeper = {}
    fp = {}
    history = {}
    durability = {
        "WR": {"r_squared": 0.16},
        "LB": {"r_squared": 0.09},
    }

    for i in range(16):
        key = f"player {i:02d}"
        sid = str(1000 + i)
        pos = "WR" if i < 8 else "LB"
        model_values[key] = {
            "pos": pos,
            "age": 24 + (i % 5),
            "role": "Starter",
            "value": 4000 + i * 100,
            "no_real_production_history": False,
        }
        model_to_sid[key] = sid

        # Most players have two providers with varying disagreement.
        sleeper[sid] = 200.0 + i * 4
        fp[sid] = [{
            "points": 200.0 + i * 4 + (i % 4) * 10,
            "source_position": pos,
            "query_position": pos,
            "crosswalk_fp_position": pos,
        }]

        weekly = [10.0 + i * 0.2, 12.0 + i * 0.2, 11.0 + i * 0.2, 13.0 + i * 0.2]
        history[sid] = {
            "pos": pos,
            "games": 17 - (i % 4),
            "weekly_points": weekly,
            "ppg": sum(weekly) / len(weekly),
        }

    players, cohorts = build_records(
        model_values, model_to_sid, sleeper, fp, history, durability
    )
    assert len(players) == 16
    assert all(r["range_low"] <= r["center_value"] <= r["range_high"] for r in players.values())
    assert all(r["range_semantics"] == RANGE_SEMANTICS for r in players.values())
    assert set(r["uncertainty_tier"] for r in players.values()) == {
        "low", "moderate", "high", "very_high"
    }

    # Force a large provider disagreement and verify it widens the envelope
    # relative to the otherwise-similar first player.
    fp2 = {k: list(v) for k, v in fp.items()}
    fp2["1001"] = [{
        "points": 90.0,
        "source_position": "WR",
        "query_position": "WR",
        "crosswalk_fp_position": "WR",
    }]
    widened, _ = build_records(
        model_values, model_to_sid, sleeper, fp2, history, durability
    )
    assert widened["player 01"]["relative_half_width"] > players["player 01"]["relative_half_width"]

    # Missing history must be handled by cohort imputation without altering center.
    history2 = dict(history)
    history2.pop("1002")
    missing_hist, _ = build_records(
        model_values, model_to_sid, sleeper, fp, history2, durability
    )
    assert missing_hist["player 02"]["center_value"] == model_values["player 02"]["value"]
    assert missing_hist["player 02"]["signals"]["history_component_basis"].startswith("position_p75")

    # Provider half-spread formula sanity.
    assert abs(provider_half_spread(120.0, 80.0) - 0.2) < 1e-12

    print(
        "build_value_uncertainty self-test passed: center preservation, provider "
        "disagreement widening, cohort imputation, quartile tiers, and range containment."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Trade Desk value sensitivity envelopes.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    payload = build_payload()
    if args.write:
        write_outputs(payload)
    else:
        q = payload["position_cohorts"]["_population_width_quartiles"]
        print(json.dumps({
            "method_version": METHOD_VERSION,
            "range_semantics": RANGE_SEMANTICS,
            "player_count": payload["counts"]["player_count"],
            "width_quartiles": q,
            "projection_provider_count": payload["counts"]["projection_provider_count"],
        }, indent=2))


if __name__ == "__main__":
    main()
