#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

import requests
from bs4 import BeautifulSoup


POSITIONS = ("QB", "RB", "WR", "TE")
MIN_ROWS = {"QB": 20, "RB": 40, "WR": 60, "TE": 30}
MIN_TOTAL = 150

EXPECTED_HEADERS = {
    "player": {"player"},
    "pos": {"pos", "position"},
    "team": {"team"},
    "floor": {"floor"},
    "proj": {"proj", "projection", "projected"},
    "ceiling": {"ceiling"},
}


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def norm_head(value):
    return re.sub(r"[^a-z0-9]+", " ", norm(value).lower()).strip()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_float(value):
    s = norm(value).replace(",", "")
    if not s:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        x = float(m.group(0))
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def resolve_headers(headers):
    out = {}
    nh = {norm_head(h): i for i, h in enumerate(headers)}
    for semantic, aliases in EXPECTED_HEADERS.items():
        idx = None
        for alias in aliases:
            if alias in nh:
                idx = nh[alias]
                break
        out[semantic] = idx
    return out


def extract_table(soup):
    candidates = []
    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        if not trs:
            continue
        first = trs[0]
        headers = [
            norm(x.get_text(" ", strip=True))
            for x in first.find_all(["th", "td"])
        ]
        if not headers:
            continue
        resolved = resolve_headers(headers)
        score = sum(v is not None for v in resolved.values())
        candidates.append((score, headers, resolved, trs[1:]))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    best = candidates[0]
    if best[0] < 6:
        return None
    return best


def extract_snapshot(text):
    # Flexible around separators and date rendering.
    patterns = [
        re.compile(
            r"Week\s+(\d+)\s*[·|\-]\s*(20\d{2})\s*[·|\-]\s*"
            r"([A-Za-z0-9_.\-]+)\s*[·|\-]\s*snapshot\s+"
            r"([A-Z][a-z]{2}\s+\d{1,2},\s+\d{1,2}:\d{2}\s+[AP]M)",
            re.I,
        ),
        re.compile(
            r"Week\s+(\d+).{0,80}?snapshot\s+"
            r"([A-Z][a-z]{2}\s+\d{1,2},\s+\d{1,2}:\d{2}\s+[AP]M)",
            re.I,
        ),
    ]
    for i, pat in enumerate(patterns):
        m = pat.search(text)
        if not m:
            continue
        if i == 0:
            return {
                "week": int(m.group(1)),
                "season": int(m.group(2)),
                "model_version": m.group(3),
                "snapshot_display": m.group(4),
                "full_pattern": True,
            }
        return {
            "week": int(m.group(1)),
            "season": None,
            "model_version": None,
            "snapshot_display": m.group(2),
            "full_pattern": False,
        }
    return None


def inspect(url):
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (compatible; LOG-Trade-Calculator-Research/1.0; "
            "+weekly-floor-ceiling-source-feasibility)"
        )
    })
    r = session.get(url, timeout=45, allow_redirects=True)
    r.raise_for_status()
    raw = r.content
    soup = BeautifulSoup(raw, "html.parser")
    text = norm(soup.get_text(" ", strip=True))
    lower = text.lower()

    faq_checks = {
        "explicit_floor_projection_ceiling_weekly_scope": all(
            x in lower
            for x in (
                "every qb, rb, wr, and te",
                "floor",
                "projected",
                "ceiling",
                "this week",
            )
        ),
        "same_model_low_high_band_documented": (
            "floor and ceiling are the same model" in lower
            and "low and high bands" in lower
        ),
        "logged_out_half_ppr_documented": (
            "logged-out mode uses half-ppr" in lower
        ),
        "no_account_required_documented": (
            "do i need an account?" in lower
            and "no." in lower
        ),
        "scoring_format_switch_documented": (
            "switch scoring format" in lower
            or "change how the same raw weekly line is scored" in lower
        ),
    }

    snapshot = extract_snapshot(text)
    table = extract_table(soup)

    result = {
        "schema_version": 1,
        "study_id": "weekly-floor-ceiling-volatility-v1",
        "phase": "1A-nextdyne-public-source-feasibility",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "provider_candidate": "NextDyne",
            "url": url,
            "final_url": r.url,
            "http_status": r.status_code,
            "response_sha256": sha256_bytes(raw),
            "response_bytes": len(raw),
            "account_required_for_default_half_ppr": False,
        },
        "faq_checks": faq_checks,
        "snapshot_metadata": snapshot,
        "table_parser": {
            "semantic_table_found": table is not None,
        },
        "governance": {
            "provider_self_reported_accuracy_metrics_used_in_decision": False,
            "provider_self_reported_accuracy_metrics_persisted": False,
            "realized_player_outcome_rows_ingested": False,
            "realized_player_outcome_association_opened": False,
            "production_change_authorized": False,
            "user_facing_display_authorized": False,
            "fundamental_value_effect_authorized": False,
            "package_adjustment_effect_authorized": False,
            "team_utility_effect_authorized": False,
            "trade_value_effect_authorized": False,
        },
    }

    if table is None:
        result.update({
            "status": "BLOCKED_PUBLIC_HTML_TABLE_PARSER_NO_SOURCE_DECISION",
            "coverage": None,
            "band_integrity": None,
            "historical_archive": {
                "reproducible_full_historical_snapshot_archive_proven": False,
                "retrospective_phase_authorized": False,
            },
            "next": (
                "Inspect public page transport/parser only; do not open outcomes "
                "or alter study architecture."
            ),
        })
        return result

    _, headers, resolved, trs = table
    rows_by_pos = Counter()
    valid_by_pos = Counter()
    invalid_numeric = 0
    ceiling_below_floor = 0
    projection_outside_band = 0
    positive_width = 0
    zero_width = 0
    parsed_rows = 0

    for tr in trs:
        cells = [
            norm(x.get_text(" ", strip=True))
            for x in tr.find_all(["th", "td"])
        ]
        if not cells or len(cells) < len(headers):
            continue

        def cell(key):
            idx = resolved[key]
            return cells[idx] if idx is not None and idx < len(cells) else None

        pos = norm(cell("pos")).upper()
        if pos not in POSITIONS:
            continue

        parsed_rows += 1
        rows_by_pos[pos] += 1
        floor = safe_float(cell("floor"))
        proj = safe_float(cell("proj"))
        ceiling = safe_float(cell("ceiling"))

        if floor is None or proj is None or ceiling is None:
            invalid_numeric += 1
            continue

        if ceiling < floor:
            ceiling_below_floor += 1
            continue

        if proj < floor or proj > ceiling:
            projection_outside_band += 1

        width = ceiling - floor
        if width > 0:
            positive_width += 1
        else:
            zero_width += 1

        valid_by_pos[pos] += 1

    valid_total = sum(valid_by_pos.values())
    positive_width_rate = positive_width / valid_total if valid_total else 0.0

    coverage_gates = {
        p: valid_by_pos[p] >= MIN_ROWS[p]
        for p in POSITIONS
    }

    hard_gates = {
        "faq_source_semantics_verified": all(faq_checks.values()),
        "snapshot_metadata_present": snapshot is not None,
        "semantic_table_found": True,
        "all_required_table_columns_resolved": all(
            resolved[x] is not None
            for x in ("player", "pos", "team", "floor", "proj", "ceiling")
        ),
        "qb_coverage_minimum": coverage_gates["QB"],
        "rb_coverage_minimum": coverage_gates["RB"],
        "wr_coverage_minimum": coverage_gates["WR"],
        "te_coverage_minimum": coverage_gates["TE"],
        "total_valid_rows_at_least_150": valid_total >= MIN_TOTAL,
        "no_ceiling_below_floor_rows": ceiling_below_floor == 0,
        "projection_inside_band_rate_at_least_99pct": (
            (1.0 - projection_outside_band / valid_total) >= 0.99
            if valid_total
            else False
        ),
        "positive_width_rate_at_least_95pct": positive_width_rate >= 0.95,
        "logged_out_half_ppr": faq_checks["logged_out_half_ppr_documented"],
        "no_account_required": faq_checks["no_account_required_documented"],
    }

    passed = all(hard_gates.values())

    # This phase proves only the current public snapshot path.
    # It intentionally does NOT claim a historical full-universe archive.
    status = (
        "PASS_NEXTDYNE_CURRENT_SNAPSHOT_FEASIBILITY_PROSPECTIVE_ONLY_DESIGN_REVIEW_REQUIRED"
        if passed
        else "STOP_NEXTDYNE_CURRENT_SNAPSHOT_SOURCE_FEASIBILITY_BEFORE_OUTCOMES"
    )

    result.update({
        "status": status,
        "table_parser": {
            "semantic_table_found": True,
            "headers": headers,
            "resolved_columns": resolved,
        },
        "coverage": {
            "parsed_target_position_rows": parsed_rows,
            "valid_band_rows": valid_total,
            "rows_by_position": dict(sorted(rows_by_pos.items())),
            "valid_band_rows_by_position": dict(sorted(valid_by_pos.items())),
            "minimum_rows_by_position": MIN_ROWS,
            "minimum_total": MIN_TOTAL,
        },
        "band_integrity": {
            "invalid_numeric_rows": invalid_numeric,
            "ceiling_below_floor_rows": ceiling_below_floor,
            "projection_outside_band_rows": projection_outside_band,
            "positive_width_rows": positive_width,
            "zero_width_rows": zero_width,
            "positive_width_rate": round(positive_width_rate, 9),
        },
        "hard_gates": hard_gates,
        "historical_archive": {
            "reproducible_full_historical_snapshot_archive_proven": False,
            "retrospective_phase_authorized": False,
            "reason": (
                "Phase 1A tested the live public weekly board only. Search-visible "
                "historical articles/player pages are not accepted as a frozen "
                "full-universe pre-kickoff archive."
            ),
        },
        "next": (
            "If pass: preregister a prospective-only architecture amendment and "
            "snapshot freezer before any realized target association. If stop: "
            "close/redesign source path before outcomes."
        ),
    })
    return result


def selftest():
    html = """
    <html><body>
    <p>Every QB, RB, WR, and TE with a floor, projected, and ceiling number for this week.</p>
    <p>Floor and ceiling are the same model's low and high bands.</p>
    <p>Do I need an account? No. Logged-out mode uses Half-PPR unless you pick another format.</p>
    <p>Switch scoring format.</p>
    <p>Week 4 · 2026 · v1.0 · snapshot Oct 2, 1:00 PM</p>
    <table>
      <tr><th>Player</th><th>Pos</th><th>Team</th><th>Floor</th><th>Proj</th><th>Ceiling</th></tr>
      <tr><td>A</td><td>QB</td><td>ARI</td><td>10</td><td>20</td><td>30</td></tr>
    </table>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    text = norm(soup.get_text(" ", strip=True))
    snap = extract_snapshot(text)
    assert snap["week"] == 4
    table = extract_table(soup)
    assert table is not None
    _, headers, resolved, rows = table
    assert resolved["floor"] == 3
    assert resolved["ceiling"] == 5
    assert len(rows) == 1
    print("PASS: NextDyne source feasibility parser synthetic selftest")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--url")
    ap.add_argument("--out")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    if not args.url or not args.out:
        ap.error("--url and --out required")

    result = inspect(args.url)
    Path(args.out).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "status": result["status"],
        "snapshot_metadata": result.get("snapshot_metadata"),
        "coverage": result.get("coverage"),
        "hard_gates": result.get("hard_gates"),
        "historical_archive_proven": result["historical_archive"][
            "reproducible_full_historical_snapshot_archive_proven"
        ],
        "outcome_association_opened": False,
        "production_authorized": False,
    }, indent=2))


if __name__ == "__main__":
    main()
