#!/usr/bin/env python3
"""
Young RB Continuous-Age Production Candidate Blast Radius
=========================================================

READ-ONLY final research gate before any live age-model change.

Purpose
-------
Apply the three continuous RB age architectures to TODAY'S full RB board using
Sleeper DOBs, while holding every non-age model input fixed.

This answers:
- how many current RBs move?
- by how much?
- which valuable players move most?
- how many RB ranks change?
- are any changes large enough to resemble meaningful draft-pick value?
- do the three continuous shapes materially disagree in live blast radius?

Nothing in index.html is modified.

Candidate architecture
----------------------
For all RBs:
- exact fractional age from data/players_cache.json;
- ordinary RB pre-peak and post-peak logic preserves current Trade Desk
  endpoints but evaluates age continuously;
- elite young-RB override is replaced by a monotone age-21 -> age-25 taper.

Candidates:
- continuous_linear
- continuous_smoothstep
- continuous_quadratic

Current/deployed values are read from scripts/validation/snapshot_values.py.

Research date
-------------
Uses the machine's current UTC date by default. Can be overridden with
--as-of YYYY-MM-DD for reproducibility.
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
OUT_JSON = (
    REPO_ROOT / "research" / "age-calibration" /
    "young_rb_continuous_age_blast_radius.json"
)
OUT_MD = (
    REPO_ROOT / "research" / "age-calibration" /
    "young_rb_continuous_age_blast_radius.md"
)

CANDIDATES = (
    "continuous_linear",
    "continuous_smoothstep",
    "continuous_quadratic",
)

CURRENT_COEFF = 0.384
ELITE_MIN_RAW_PM = 0.65

# Current documented pick-value anchors. These are used only to contextualize
# the SIZE of a player-value movement; they do not alter player values.
PICK_VALUE_ANCHORS = {
    "2027 R1 early": 7500,
    "2027 R1 mid": 5854,
    "2027 R1 late": 5244,
    "2027 R2 early": 3906,
    "2027 R2 mid": 3624,
    "2027 R2 late": 3291,
    "2027 R3 early": 2692,
    "2027 R3 mid": 2682,
    "2027 R3 late": 2319,
    "2027 R4 early": 1972,
    "2027 R4 mid": 1831,
    "2027 R4 late": 1689,
    "2027 R5 early": 1414,
    "2027 R5 mid": 1250,
    "2027 R5 late": 1118,
    "2027 R6 early": 1014,
    "2027 R6 mid": 853,
    "2027 R6 late": 740,
}


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


def fractional_age(dob: date, on_date: date) -> float:
    try:
        this_bd = date(on_date.year, dob.month, dob.day)
    except ValueError:
        this_bd = date(on_date.year, 2, 28)

    if on_date >= this_bd:
        last_bd = this_bd
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


def player_cache_name(row: dict[str, Any]) -> str:
    for field in ("full_name", "search_full_name", "player_name", "name"):
        value = row.get(field)
        if value:
            return str(value)
    first = str(row.get("first_name") or "").strip()
    last = str(row.get("last_name") or "").strip()
    return f"{first} {last}".strip()


def load_player_cache_index() -> tuple[dict[str, list[tuple[str, dict[str, Any]]]], dict[str, Any]]:
    doc = json.loads(PLAYERS_CACHE_PATH.read_text(encoding="utf-8"))
    players = doc.get("players")
    if not isinstance(players, dict):
        raise RuntimeError("players_cache.json missing top-level players mapping")

    by_name: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    usable_dob = 0

    for pid, row in players.items():
        if not isinstance(row, dict):
            continue
        name = player_cache_name(row)
        norm = normalize_name(name)
        if norm:
            by_name[norm].append((str(pid), row))
        if parse_dob(row.get("birth_date")) is not None:
            usable_dob += 1

    return by_name, {
        "cache_players": len(players),
        "cache_players_with_parseable_dob": usable_dob,
    }


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

    x = max(0.0, min(1.0, (25.0 - age) / 4.0))

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
    shape: str,
) -> float:
    c = cfg["age_curve"]["RB"]

    if (
        role == "Elite"
        and age <= 25.0
        and isinstance(raw_pm, (int, float))
        and raw_pm >= ELITE_MIN_RAW_PM
    ):
        return elite_continuous_am(age, shape)

    # Preserve current pre-floor formula.
    lo, hi = 0.15, 1.55
    ratio = max(0.0, min(1.0, (rm - lo) / (hi - lo)))
    pre_floor = 0.55 + ratio * (0.98 - 0.55)

    peak_start = float(c["peakStart"])
    peak_end = float(c["peakEnd"])
    floor_age = float(c["floor"])

    if age <= peak_end:
        denom = peak_start - 21.0
        t = max(0.0, min(1.0, (age - 21.0) / denom)) if denom else 1.0
        pre_floor_base = pre_floor + t * (1.0 - pre_floor)
        return pre_floor_base if age <= peak_start else 1.0

    decline_span = floor_age - peak_end
    t = (
        max(0.0, min(1.0, (age - peak_end) / decline_span))
        if decline_span else 1.0
    )
    return max(0.62, 1.0 - 0.38 * t)


def js_round_positive(x: float) -> int:
    return math.floor(x + 0.5)


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


def candidate_value(
    *,
    info: dict[str, Any],
    rm: float,
    raw_pm: float | None,
    frac_age: float,
    cfg: dict[str, Any],
    candidate: str,
) -> tuple[int, float]:
    shape = candidate.removeprefix("continuous_")
    am = continuous_rb_age_multiplier(
        age=frac_age,
        role=info["role"],
        rm=rm,
        raw_pm=raw_pm,
        cfg=cfg,
        shape=shape,
    )
    pw = float(cfg["position_weight"]["RB"])
    value = js_round_positive(100.0 * pw * am * rm * 55.0)
    return value, am


def nearest_pick_equivalent(abs_delta: int) -> dict[str, Any] | None:
    if abs_delta <= 0:
        return None
    label, value = min(
        PICK_VALUE_ANCHORS.items(),
        key=lambda kv: abs(kv[1] - abs_delta),
    )
    return {
        "label": label,
        "anchor_value": value,
        "gap_points": abs(value - abs_delta),
    }


def pct_move(delta: int, current: int) -> float:
    return delta / current if current else 0.0


def percentile(vals: list[float], q: float) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    x = (len(s) - 1) * q
    lo, hi = math.floor(x), math.ceil(x)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (x - lo)


def summarize_candidate(rows: list[dict[str, Any]], candidate: str) -> dict[str, Any]:
    moves = [abs(r["candidates"][candidate]["delta_points"]) for r in rows]
    pcts = [abs(r["candidates"][candidate]["delta_pct"]) for r in rows]
    rank_moves = [abs(r["candidates"][candidate]["rank_move"]) for r in rows]

    valuable = [r for r in rows if r["current_value"] >= 3000]
    valuable_pcts = [
        abs(r["candidates"][candidate]["delta_pct"]) for r in valuable
    ]

    return {
        "n": len(rows),
        "changed_n": sum(1 for x in moves if x != 0),
        "median_abs_points": statistics.median(moves) if moves else None,
        "p90_abs_points": percentile(moves, 0.90),
        "max_abs_points": max(moves) if moves else None,
        "median_abs_pct": statistics.median(pcts) if pcts else None,
        "p90_abs_pct": percentile(pcts, 0.90),
        "max_abs_pct": max(pcts) if pcts else None,
        "max_abs_rank_move": max(rank_moves) if rank_moves else None,
        "valuable_n": len(valuable),
        "valuable_median_abs_pct": (
            statistics.median(valuable_pcts) if valuable_pcts else None
        ),
        "valuable_max_abs_pct": max(valuable_pcts) if valuable_pcts else None,
        "moves_ge_5_pct": sum(1 for x in pcts if x >= 0.05),
        "moves_ge_10_pct": sum(1 for x in pcts if x >= 0.10),
        "moves_ge_20_pct": sum(1 for x in pcts if x >= 0.20),
        "moves_ge_r6_early_points": sum(1 for x in moves if x >= 1014),
        "moves_ge_r4_early_points": sum(1 for x in moves if x >= 1972),
        "moves_ge_r2_early_points": sum(1 for x in moves if x >= 3906),
    }


def build_report(as_of: date) -> dict[str, Any]:
    cfg = snapshot_values.load_from_html(INDEX_PATH)
    current_values = snapshot_values.compute_all_values(cfg)
    cache_by_name, cache_meta = load_player_cache_index()

    rows = []
    unmatched = []
    ambiguous = []

    for key, info in cfg["player_db"].items():
        if info["pos"] != "RB":
            continue

        matches = cache_by_name.get(normalize_name(key), [])
        dob_matches = [
            (pid, row, parse_dob(row.get("birth_date")))
            for pid, row in matches
            if parse_dob(row.get("birth_date")) is not None
        ]

        if not dob_matches:
            unmatched.append(key)
            continue
        if len(dob_matches) > 1:
            ambiguous.append({
                "player": key,
                "matches": [
                    {
                        "id": pid,
                        "name": player_cache_name(row),
                        "birth_date": dob.isoformat() if dob else None,
                    }
                    for pid, row, dob in dob_matches
                ],
            })
            continue

        pid, cache_row, dob = dob_matches[0]
        assert dob is not None
        frac_age = fractional_age(dob, as_of)

        rm, raw_pm = production_components(key, info, cfg)
        current = current_values[key]

        rows.append({
            "player": key,
            "sleeper_id": pid,
            "birth_date": dob.isoformat(),
            "integer_age_in_player_db": info["age"],
            "fractional_age": frac_age,
            "role": info["role"],
            "rm": rm,
            "raw_pm": raw_pm,
            "current_value": int(current["value"]),
            "current_age_mult": float(current["age_mult"]),
            "candidates": {},
        })

    # Current RB ranks across full PLAYER_DB.
    current_rb = sorted(
        [
            (key, int(row["value"]))
            for key, row in current_values.items()
            if row["pos"] == "RB"
        ],
        key=lambda x: (-x[1], x[0]),
    )
    current_rank = {key: rank for rank, (key, _) in enumerate(current_rb, 1)}

    # Candidate values for matched rows, current values for unmatched rows so ranks
    # remain comparable across the whole live RB board.
    for candidate in CANDIDATES:
        candidate_values = {
            key: int(row["value"])
            for key, row in current_values.items()
            if row["pos"] == "RB"
        }

        for r in rows:
            info = cfg["player_db"][r["player"]]
            value, am = candidate_value(
                info=info,
                rm=r["rm"],
                raw_pm=r["raw_pm"],
                frac_age=r["fractional_age"],
                cfg=cfg,
                candidate=candidate,
            )
            candidate_values[r["player"]] = value
            r["candidates"][candidate] = {
                "value": value,
                "age_mult": am,
            }

        ranking = sorted(candidate_values.items(), key=lambda x: (-x[1], x[0]))
        rank_map = {key: rank for rank, (key, _) in enumerate(ranking, 1)}

        for r in rows:
            c = r["candidates"][candidate]
            delta = c["value"] - r["current_value"]
            c["delta_points"] = delta
            c["delta_pct"] = pct_move(delta, r["current_value"])
            c["current_rb_rank"] = current_rank[r["player"]]
            c["candidate_rb_rank"] = rank_map[r["player"]]
            c["rank_move"] = current_rank[r["player"]] - rank_map[r["player"]]
            c["nearest_pick_equivalent"] = nearest_pick_equivalent(abs(delta))

    summaries = {
        candidate: summarize_candidate(rows, candidate)
        for candidate in CANDIDATES
    }

    top_movers = {}
    for candidate in CANDIDATES:
        top_movers[candidate] = sorted(
            [
                {
                    "player": r["player"],
                    "fractional_age": round(r["fractional_age"], 4),
                    "role": r["role"],
                    "current_value": r["current_value"],
                    "candidate_value": r["candidates"][candidate]["value"],
                    "delta_points": r["candidates"][candidate]["delta_points"],
                    "delta_pct": r["candidates"][candidate]["delta_pct"],
                    "current_rb_rank": r["candidates"][candidate]["current_rb_rank"],
                    "candidate_rb_rank": r["candidates"][candidate]["candidate_rb_rank"],
                    "rank_move": r["candidates"][candidate]["rank_move"],
                    "nearest_pick_equivalent": r["candidates"][candidate]["nearest_pick_equivalent"],
                }
                for r in rows
            ],
            key=lambda x: (-abs(x["delta_points"]), x["player"]),
        )[:25]

    return {
        "audit": "young-rb-continuous-age-blast-radius-v1",
        "production_changes": False,
        "as_of": as_of.isoformat(),
        "architecture": (
            "Fractional age for all RBs; current ordinary-RB endpoints preserved; "
            "monotone elite age-21 to age-25 taper."
        ),
        "counts": {
            "live_rb_count": len(current_rb),
            "matched_rb_with_dob": len(rows),
            "unmatched_rb": len(unmatched),
            "ambiguous_rb": len(ambiguous),
        },
        "player_cache": cache_meta,
        "candidate_summary": summaries,
        "top_movers": top_movers,
        "players": rows,
        "unmatched": unmatched,
        "ambiguous": ambiguous,
        "pick_equivalent_note": (
            "Nearest pick anchor contextualizes absolute point movement only. "
            "It does not mean the player literally gained/lost that draft pick."
        ),
    }


def pct(v: Any) -> str:
    return "n/a" if v is None else f"{100.0 * float(v):+.1f}%"


def write_md(report: dict[str, Any]) -> None:
    lines = [
        "# Young RB Continuous-Age Production Candidate Blast Radius",
        "",
        "**Status:** research-only; no production values changed.",
        "",
        f"- As of: **{report['as_of']}**",
        f"- Live RBs: **{report['counts']['live_rb_count']}**",
        f"- RBs matched to DOB: **{report['counts']['matched_rb_with_dob']}**",
        f"- Unmatched RBs: **{report['counts']['unmatched_rb']}**",
        "",
        "## Candidate summary",
        "",
        "| Candidate | Changed | Median abs move | P90 abs move | Max abs move | "
        "Median abs % | P90 abs % | Max abs % | Max rank move | >=5% | >=10% | >=20% | "
        ">=R6-early pts | >=R4-early pts | >=R2-early pts |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for candidate in CANDIDATES:
        s = report["candidate_summary"][candidate]
        lines.append(
            f"| {candidate} | {s['changed_n']}/{s['n']} | "
            f"{s['median_abs_points']:.0f} | {s['p90_abs_points']:.0f} | "
            f"{s['max_abs_points']:.0f} | {pct(s['median_abs_pct'])} | "
            f"{pct(s['p90_abs_pct'])} | {pct(s['max_abs_pct'])} | "
            f"{s['max_abs_rank_move']} | {s['moves_ge_5_pct']} | "
            f"{s['moves_ge_10_pct']} | {s['moves_ge_20_pct']} | "
            f"{s['moves_ge_r6_early_points']} | {s['moves_ge_r4_early_points']} | "
            f"{s['moves_ge_r2_early_points']} |"
        )

    lines += [
        "",
        "## Valuable RB blast radius (current Fundamental >= 3000)",
        "",
        "| Candidate | N | Median abs % | Max abs % |",
        "|---|---:|---:|---:|",
    ]
    for candidate in CANDIDATES:
        s = report["candidate_summary"][candidate]
        lines.append(
            f"| {candidate} | {s['valuable_n']} | "
            f"{pct(s['valuable_median_abs_pct'])} | {pct(s['valuable_max_abs_pct'])} |"
        )

    for candidate in CANDIDATES:
        lines += [
            "",
            f"## Largest movers — {candidate}",
            "",
            "| Player | Fractional age | Role | Current | Candidate | Delta | Delta % | "
            "RB rank now | RB rank candidate | Rank move | Nearest pick-sized anchor |",
            "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
        for r in report["top_movers"][candidate]:
            eq = r["nearest_pick_equivalent"]
            eq_text = (
                "n/a"
                if not eq
                else f"{eq['label']} ({eq['anchor_value']})"
            )
            lines.append(
                f"| {r['player']} | {r['fractional_age']:.2f} | {r['role']} | "
                f"{r['current_value']} | {r['candidate_value']} | "
                f"{r['delta_points']:+d} | {pct(r['delta_pct'])} | "
                f"{r['current_rb_rank']} | {r['candidate_rb_rank']} | "
                f"{r['rank_move']:+d} | {eq_text} |"
            )

    if report["unmatched"]:
        lines += [
            "",
            "## DOB unmatched RBs",
            "",
            ", ".join(report["unmatched"]),
            "",
        ]

    lines += [
        "",
        "## Interpretation boundary",
        "",
        report["pick_equivalent_note"],
        "",
        "This is the final blast-radius gate, not a production write. A candidate should only "
        "advance if the live movement is acceptable, DOB coverage is high, and it remains "
        "consistent with the earlier birthday-event evidence.",
        "",
    ]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def run_selftest() -> None:
    dob = date(2002, 1, 30)
    a = fractional_age(dob, date(2026, 9, 2))
    assert 24.5 < a < 24.7

    for shape in ("linear", "smoothstep", "quadratic"):
        vals = [elite_continuous_am(21 + i / 20.0, shape) for i in range(81)]
        assert abs(vals[0] - AGE21_ELITE_AM) < 1e-12
        assert abs(vals[-1] - 1.0) < 1e-12
        assert all(vals[i] >= vals[i + 1] - 1e-12 for i in range(len(vals) - 1))

    eq = nearest_pick_equivalent(1000)
    assert eq is not None and eq["label"] in {"2027 R6 early", "2027 R6 mid"}

    print("young_rb_continuous_age_blast_radius self-test passed.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--as-of", type=str, default=None)
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    report = build_report(as_of)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_md(report)
    print(OUT_MD.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
