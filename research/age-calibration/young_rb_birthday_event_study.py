#!/usr/bin/env python3
"""
Young RB Birthday Event Study
=============================

READ-ONLY longitudinal audit of Trade Desk's young-RB age mechanics.

Why this exists
---------------
Cross-sectional external-market calibration could not cleanly distinguish the
current elite-RB curve from smooth alternatives. This follow-up uses SAME-PLAYER
external market history around actual birthdays to test whether Trade Desk's
integer-age jumps resemble real dynasty-market movement.

External source
---------------
Stats Guy Fantasy public API:
  GET /api/v1/rankings?format=sf_dynasty&position=RB
  GET /api/v1/players/:id/value-history?format=sf_dynasty&since=2025-09-01

Stats Guy values are derived from real trades across thousands of Sleeper
leagues. Sleeper player IDs are used directly.

Birthday source
---------------
data/players_cache.json, keyed by Sleeper player ID.

Event definition
----------------
For each matched RB with a real birth date:
- identify the most recent birthday between 2025-09-01 and the external board's
  current snapshot date;
- require that birthday to produce an age transition in the 21->22 through
  25->26 range;
- pre window:  28 to 8 days BEFORE birthday;
- post window: 8 to 28 days AFTER birthday;
- use median external market value in each window;
- compute post/pre market change.

Trade Desk comparison
---------------------
Using the player's CURRENT Trade Desk position, role, and production multiplier,
hold production/role fixed and recompute ageMultiplier() at age_before and
age_after. This isolates the age-only percentage jump implied by the deployed
formula.

This does NOT assume current role/PM perfectly describes the historical player
state at the birthday. That limitation is explicit in the report.

Outputs are research-only. Nothing in index.html is changed.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DIR = REPO_ROOT / "scripts" / "validation"
if str(VALIDATION_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATION_DIR))

import snapshot_values

INDEX_PATH = REPO_ROOT / "index.html"
PLAYERS_CACHE_PATH = REPO_ROOT / "data" / "players_cache.json"
OUT_JSON = REPO_ROOT / "research" / "age-calibration" / "young_rb_birthday_event_study.json"
OUT_MD = REPO_ROOT / "research" / "age-calibration" / "young_rb_birthday_event_study.md"

API_BASE = "https://api.statsguyfantasy.com/api/v1"
RANKINGS_URL = f"{API_BASE}/rankings?format=sf_dynasty&position=RB&limit=1000"
HISTORY_SINCE = "2025-09-01"
USER_AGENT = "TradeDesk-RB-Birthday-Study/1.0"

PRE_START_DAYS = 28
PRE_END_DAYS = 8
POST_START_DAYS = 8
POST_END_DAYS = 28

MIN_POINTS_PER_WINDOW = 3
TRANSITION_MIN_BEFORE = 21
TRANSITION_MAX_BEFORE = 25

# Keep comfortably under the documented 60 requests/minute rate limit.
REQUEST_SLEEP_SECONDS = 1.10


def normalize_name(name: str) -> str:
    s = str(name or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+(jr|sr|ii|iii|iv)$", "", s)
    return s.strip()


def fetch_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        raise RuntimeError(f"Failed GET {url}: {exc}") from exc


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def load_players_cache() -> dict[str, Any]:
    doc = json.loads(PLAYERS_CACHE_PATH.read_text(encoding="utf-8"))
    players = doc.get("players")
    if not isinstance(players, dict):
        raise RuntimeError("data/players_cache.json missing top-level players mapping")
    return players


def parse_birth_date(raw: Any) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def age_on_date(dob: date, on_date: date) -> int:
    return on_date.year - dob.year - ((on_date.month, on_date.day) < (dob.month, dob.day))


def birthday_in_year(dob: date, year: int) -> date | None:
    try:
        return date(year, dob.month, dob.day)
    except ValueError:
        # Feb 29 -> Feb 28 in non-leap years for event-study practicality.
        if dob.month == 2 and dob.day == 29:
            return date(year, 2, 28)
        return None


def most_recent_eligible_birthday(
    dob: date,
    start: date,
    end: date,
) -> tuple[date, int, int] | None:
    candidates = []
    for year in range(start.year, end.year + 1):
        bd = birthday_in_year(dob, year)
        if bd is None or not (start <= bd <= end):
            continue
        before = age_on_date(dob, bd - timedelta(days=1))
        after = age_on_date(dob, bd)
        if (
            TRANSITION_MIN_BEFORE <= before <= TRANSITION_MAX_BEFORE
            and after == before + 1
        ):
            candidates.append((bd, before, after))
    return max(candidates, key=lambda x: x[0]) if candidates else None


def median_history_value(
    history: list[dict[str, Any]],
    start: date,
    end: date,
) -> tuple[float | None, int]:
    vals = []
    for row in history:
        try:
            d = parse_iso_date(str(row["date"]))
            v = float(row["value"])
        except (KeyError, TypeError, ValueError):
            continue
        if start <= d <= end and v > 0:
            vals.append(v)
    if len(vals) < MIN_POINTS_PER_WINDOW:
        return None, len(vals)
    return statistics.median(vals), len(vals)


def current_player_components(
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


def age_only_model_change(
    *,
    pos: str,
    role: str,
    rm: float,
    raw_pm: float | None,
    age_before: int,
    age_after: int,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    am_before = snapshot_values.age_multiplier(
        pos, age_before, role, rm, raw_pm, cfg
    )
    am_after = snapshot_values.age_multiplier(
        pos, age_after, role, rm, raw_pm, cfg
    )
    pct = (am_after / am_before) - 1.0 if am_before else None
    return {
        "age_mult_before": am_before,
        "age_mult_after": am_after,
        "predicted_age_only_change_pct": pct,
    }


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    x = (len(s) - 1) * q
    lo, hi = math.floor(x), math.ceil(x)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (x - lo)


def summarize_transition(rows: list[dict[str, Any]]) -> dict[str, Any]:
    market = [r["market_change_pct"] for r in rows]
    model = [r["model_age_only_change_pct"] for r in rows]
    error = [r["model_minus_market_pct"] for r in rows]
    return {
        "n": len(rows),
        "median_market_change_pct": statistics.median(market) if market else None,
        "p25_market_change_pct": percentile(market, 0.25),
        "p75_market_change_pct": percentile(market, 0.75),
        "median_model_age_only_change_pct": statistics.median(model) if model else None,
        "median_model_minus_market_pct": statistics.median(error) if error else None,
        "mean_abs_model_minus_market_pct": (
            sum(abs(x) for x in error) / len(error) if error else None
        ),
    }


def build_report() -> dict[str, Any]:
    cfg = snapshot_values.load_from_html(INDEX_PATH)
    sleeper_players = load_players_cache()
    board = fetch_json(RANKINGS_URL)

    as_of = parse_iso_date(str(board.get("asOf")))
    archive_start = date.fromisoformat(HISTORY_SINCE)

    # Current external board by normalized name.
    ext_by_name = defaultdict(list)
    for row in board.get("rankings") or []:
        norm = normalize_name(row.get("name"))
        if norm:
            ext_by_name[norm].append(row)

    candidates = []
    identity_issues = []

    for key, info in cfg["player_db"].items():
        if info["pos"] != "RB":
            continue

        ext_rows = ext_by_name.get(normalize_name(key), [])
        if len(ext_rows) != 1:
            if len(ext_rows) > 1:
                identity_issues.append({
                    "player": key,
                    "issue": "ambiguous_external_name",
                    "external_names": [x.get("name") for x in ext_rows],
                })
            continue

        ext = ext_rows[0]
        pid = str(ext.get("id") or "")
        sleeper = sleeper_players.get(pid) or {}
        dob = parse_birth_date(sleeper.get("birth_date"))
        if dob is None:
            continue

        event = most_recent_eligible_birthday(dob, archive_start, as_of)
        if event is None:
            continue

        birthday, age_before, age_after = event
        rm, raw_pm = current_player_components(key, info, cfg)
        model = age_only_model_change(
            pos=info["pos"],
            role=info["role"],
            rm=rm,
            raw_pm=raw_pm,
            age_before=age_before,
            age_after=age_after,
            cfg=cfg,
        )

        candidates.append({
            "player": key,
            "external_id": pid,
            "external_name": ext.get("name"),
            "birthday": birthday,
            "age_before": age_before,
            "age_after": age_after,
            "current_role": info["role"],
            "current_pm": rm,
            "current_raw_pm": raw_pm,
            "model": model,
        })

    rows = []
    fetch_failures = []

    for idx, c in enumerate(candidates):
        url = (
            f"{API_BASE}/players/{c['external_id']}/value-history"
            f"?format=sf_dynasty&since={HISTORY_SINCE}"
        )
        try:
            hist_doc = fetch_json(url)
        except Exception as exc:
            fetch_failures.append({"player": c["player"], "error": str(exc)})
            continue

        history = hist_doc.get("history") or []
        bd = c["birthday"]

        pre_start = bd - timedelta(days=PRE_START_DAYS)
        pre_end = bd - timedelta(days=PRE_END_DAYS)
        post_start = bd + timedelta(days=POST_START_DAYS)
        post_end = bd + timedelta(days=POST_END_DAYS)

        pre_value, pre_n = median_history_value(history, pre_start, pre_end)
        post_value, post_n = median_history_value(history, post_start, post_end)

        if pre_value is None or post_value is None:
            continue

        market_change = post_value / pre_value - 1.0
        model_change = c["model"]["predicted_age_only_change_pct"]

        rows.append({
            "player": c["player"],
            "external_id": c["external_id"],
            "birthday": bd.isoformat(),
            "transition": f"{c['age_before']}->{c['age_after']}",
            "age_before": c["age_before"],
            "age_after": c["age_after"],
            "current_role": c["current_role"],
            "current_pm": round(c["current_pm"], 6),
            "current_raw_pm": (
                round(c["current_raw_pm"], 6)
                if isinstance(c["current_raw_pm"], (int, float))
                else None
            ),
            "pre_window": f"{pre_start.isoformat()}..{pre_end.isoformat()}",
            "post_window": f"{post_start.isoformat()}..{post_end.isoformat()}",
            "pre_n": pre_n,
            "post_n": post_n,
            "pre_median_market_value": round(pre_value, 2),
            "post_median_market_value": round(post_value, 2),
            "market_change_pct": market_change,
            "age_mult_before": c["model"]["age_mult_before"],
            "age_mult_after": c["model"]["age_mult_after"],
            "model_age_only_change_pct": model_change,
            "model_minus_market_pct": model_change - market_change,
        })

        if idx < len(candidates) - 1:
            time.sleep(REQUEST_SLEEP_SECONDS)

    by_transition = defaultdict(list)
    for row in rows:
        by_transition[row["transition"]].append(row)

    transition_summary = {
        transition: summarize_transition(group)
        for transition, group in sorted(by_transition.items())
    }

    overall = summarize_transition(rows)

    # Specific flags for the two structural jumps already identified.
    key_findings = {}
    for transition in ("22->23", "23->24", "24->25"):
        summary = transition_summary.get(transition)
        if summary:
            key_findings[transition] = summary

    return {
        "audit": "young-rb-birthday-event-study-v1",
        "production_changes": False,
        "external_source": {
            "provider": "Stats Guy Fantasy",
            "format": "sf_dynasty",
            "board_as_of": board.get("asOf"),
            "history_since": HISTORY_SINCE,
        },
        "event_windows": {
            "pre_days_before_birthday": [PRE_START_DAYS, PRE_END_DAYS],
            "post_days_after_birthday": [POST_START_DAYS, POST_END_DAYS],
            "minimum_history_points_per_window": MIN_POINTS_PER_WINDOW,
        },
        "important_limitation": (
            "Trade Desk comparison holds CURRENT role and production multiplier fixed. "
            "Those may differ from the player's true historical role/production state at "
            "the birthday; this is a structural age-jump audit, not a causal aging estimate."
        ),
        "counts": {
            "candidate_birthday_events": len(candidates),
            "usable_events": len(rows),
            "identity_issues": len(identity_issues),
            "history_fetch_failures": len(fetch_failures),
        },
        "overall": overall,
        "transition_summary": transition_summary,
        "key_findings": key_findings,
        "events": sorted(rows, key=lambda r: (r["transition"], r["birthday"], r["player"])),
        "identity_issues": identity_issues,
        "history_fetch_failures": fetch_failures,
    }


def pct(v: Any) -> str:
    if v is None:
        return "n/a"
    return f"{100.0 * float(v):+.1f}%"


def write_md(report: dict[str, Any]) -> None:
    lines = [
        "# Young RB Birthday Event Study",
        "",
        "**Status:** research-only; no production values changed.",
        "",
        "## Question",
        "",
        "When the same RB crosses an actual birthday, does the broad external dynasty market "
        "move anything like the discrete age-only jump Trade Desk currently applies?",
        "",
        "## Event window",
        "",
        f"- Pre: {PRE_START_DAYS} to {PRE_END_DAYS} days before birthday",
        f"- Post: {POST_START_DAYS} to {POST_END_DAYS} days after birthday",
        f"- Minimum observations per window: {MIN_POINTS_PER_WINDOW}",
        "",
        f"- Candidate birthday events: **{report['counts']['candidate_birthday_events']}**",
        f"- Usable events: **{report['counts']['usable_events']}**",
        "",
        "## Transition summary",
        "",
        "| Transition | N | Median external market change | Market P25 | Market P75 | "
        "Median Trade Desk age-only change | Median model - market | Mean abs gap |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for transition, s in report["transition_summary"].items():
        lines.append(
            f"| {transition} | {s['n']} | {pct(s['median_market_change_pct'])} | "
            f"{pct(s['p25_market_change_pct'])} | {pct(s['p75_market_change_pct'])} | "
            f"{pct(s['median_model_age_only_change_pct'])} | "
            f"{pct(s['median_model_minus_market_pct'])} | "
            f"{pct(s['mean_abs_model_minus_market_pct'])} |"
        )

    lines += [
        "",
        "## Player events",
        "",
        "| Player | Birthday | Transition | Role now | PM now | Pre market | Post market | "
        "External change | TD age-only change | Gap |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]

    for r in report["events"]:
        lines.append(
            f"| {r['player']} | {r['birthday']} | {r['transition']} | "
            f"{r['current_role']} | {r['current_pm']:.3f} | "
            f"{r['pre_median_market_value']:.0f} | {r['post_median_market_value']:.0f} | "
            f"{pct(r['market_change_pct'])} | {pct(r['model_age_only_change_pct'])} | "
            f"{pct(r['model_minus_market_pct'])} |"
        )

    lines += [
        "",
        "## Interpretation boundary",
        "",
        report["important_limitation"],
        "",
        "The strongest use of this study is to detect implausibly large integer-age discontinuities. "
        "It should not be treated as a full causal estimate of aging because real news, injuries, depth-chart "
        "changes, draft capital, and production can move market value within the same event window.",
        "",
    ]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def run_selftest() -> None:
    dob = date(2002, 5, 10)
    assert age_on_date(dob, date(2026, 5, 9)) == 23
    assert age_on_date(dob, date(2026, 5, 10)) == 24

    event = most_recent_eligible_birthday(
        dob,
        date(2025, 9, 1),
        date(2026, 9, 2),
    )
    assert event is not None
    assert event[0] == date(2026, 5, 10)
    assert event[1:] == (23, 24)

    history = [
        {"date": "2026-04-15", "value": 1000},
        {"date": "2026-04-20", "value": 1100},
        {"date": "2026-04-28", "value": 1200},
        {"date": "2026-05-18", "value": 900},
        {"date": "2026-05-25", "value": 950},
        {"date": "2026-06-01", "value": 1000},
    ]
    pre, pre_n = median_history_value(history, date(2026, 4, 12), date(2026, 5, 2))
    post, post_n = median_history_value(history, date(2026, 5, 18), date(2026, 6, 7))
    assert pre == 1100 and pre_n == 3
    assert post == 950 and post_n == 3

    print("young_rb_birthday_event_study self-test passed.")


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
