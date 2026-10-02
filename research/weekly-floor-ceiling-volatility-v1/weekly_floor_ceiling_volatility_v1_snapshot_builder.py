#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup


SEASON = 2026
ORIGIN_WEEK = 4
POSITIONS = ("QB", "RB", "WR", "TE")
EASTERN = ZoneInfo("America/New_York")

TEAM_ALIAS = {
    "ARZ": "ARI", "ARI": "ARI",
    "BLT": "BAL", "BAL": "BAL",
    "CLV": "CLE", "CLE": "CLE",
    "HST": "HOU", "HOU": "HOU",
    "JAC": "JAX", "JAX": "JAX",
    "LA": "LAR", "LAR": "LAR", "STL": "LAR",
    "OAK": "LV", "LV": "LV",
    "SD": "LAC", "LAC": "LAC",
    "WSH": "WAS", "WAS": "WAS",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def norm_name(value):
    s = norm(value).lower()
    s = s.replace("’", "'")
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\.?\b", "", s)
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def canon_team(value):
    s = norm(value).upper()
    return TEAM_ALIAS.get(s, s)


def safe_float(value):
    s = norm(value).replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        x = float(m.group(0))
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def read_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_kickoff_utc(gameday, gametime):
    d = norm(gameday)
    t = norm(gametime)
    if not d or not t:
        raise RuntimeError(f"missing kickoff fields: {d!r} {t!r}")
    local = datetime.fromisoformat(f"{d}T{t}:00").replace(tzinfo=EASTERN)
    return local.astimezone(timezone.utc)


def week_cutoff(schedule_path):
    rows = read_csv(schedule_path)
    games = []
    for row in rows:
        try:
            season = int(row.get("season"))
            week = int(row.get("week"))
        except (TypeError, ValueError):
            continue
        if season != SEASON:
            continue
        if norm(row.get("game_type")).upper() != "REG":
            continue
        if week != ORIGIN_WEEK:
            continue
        games.append(
            (
                parse_kickoff_utc(row.get("gameday"), row.get("gametime")),
                norm(row.get("game_id")),
            )
        )
    if not games:
        raise RuntimeError("NO_2026_WEEK4_REG_GAMES_IN_SCHEDULE")
    games.sort()
    return games[0][0], [g[1] for g in games]


def resolve_table(soup):
    aliases = {
        "player": {"player"},
        "pos": {"pos", "position"},
        "team": {"team"},
        "floor": {"floor"},
        "proj": {"proj", "projection", "projected"},
        "ceiling": {"ceiling"},
    }

    def nh(x):
        return re.sub(r"[^a-z0-9]+", " ", norm(x).lower()).strip()

    candidates = []
    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        if not trs:
            continue
        headers = [
            norm(x.get_text(" ", strip=True))
            for x in trs[0].find_all(["th", "td"])
        ]
        if not headers:
            continue
        mapping = {}
        hmap = {nh(h): i for i, h in enumerate(headers)}
        for key, aset in aliases.items():
            idx = None
            for alias in aset:
                if alias in hmap:
                    idx = hmap[alias]
                    break
            mapping[key] = idx
        score = sum(v is not None for v in mapping.values())
        candidates.append((score, headers, mapping, trs[1:]))

    if not candidates:
        raise RuntimeError("NO_HTML_TABLE")
    candidates.sort(key=lambda x: x[0], reverse=True)
    best = candidates[0]
    if best[0] != 6:
        raise RuntimeError(f"SEMANTIC_TABLE_INCOMPLETE score={best[0]}")
    return best


def extract_snapshot_meta(text):
    pat = re.compile(
        r"Week\s+(\d+)\s*[·|\-]\s*(20\d{2})\s*[·|\-]\s*"
        r"([A-Za-z0-9_.\-]+)\s*[·|\-]\s*snapshot\s+"
        r"([A-Z][a-z]{2}\s+\d{1,2},\s+\d{1,2}:\d{2}\s+[AP]M)",
        re.I,
    )
    m = pat.search(text)
    if not m:
        raise RuntimeError("SNAPSHOT_METADATA_NOT_FOUND")
    return {
        "week": int(m.group(1)),
        "season": int(m.group(2)),
        "model_version": m.group(3),
        "snapshot_display": m.group(4),
    }


def midrank_percentiles(values):
    # values: list[(stable_key, value)]
    if not values:
        return {}
    ordered = sorted(values, key=lambda x: (x[1], x[0]))
    n = len(ordered)
    out = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and ordered[j + 1][1] == ordered[i][1]:
            j += 1
        avg_rank0 = (i + j) / 2.0
        pct = 0.5 if n == 1 else avg_rank0 / (n - 1)
        for k in range(i, j + 1):
            out[ordered[k][0]] = pct
        i = j + 1
    return out


def build(html_path, schedule_path, protocol_path, out_path, manifest_path):
    protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
    assert protocol["status"] == "PREREGISTERED_PROSPECTIVE_ONLY_VALIDATION"
    assert protocol["first_candidate_origin_week"] == ORIGIN_WEEK
    assert protocol["season"] == SEASON

    now = datetime.now(timezone.utc)
    cutoff, game_ids = week_cutoff(schedule_path)
    if not now < cutoff:
        raise RuntimeError(
            f"WEEK4_FREEZE_DEADLINE_MISSED_NO_BACKFILL now={now.isoformat()} "
            f"cutoff={cutoff.isoformat()}"
        )

    raw = Path(html_path).read_bytes()
    soup = BeautifulSoup(raw, "html.parser")
    text = norm(soup.get_text(" ", strip=True))
    lower = text.lower()

    if "logged-out mode uses half-ppr" not in lower:
        raise RuntimeError("HALF_PPR_PUBLIC_MODE_NOT_VERIFIED_AT_FREEZE")

    snap = extract_snapshot_meta(text)
    if snap["season"] != SEASON or snap["week"] != ORIGIN_WEEK:
        raise RuntimeError(
            f"NEXTDYNE_WRONG_ORIGIN current={snap['season']}-W{snap['week']}"
        )

    _, headers, resolved, trs = resolve_table(soup)

    raw_rows = []
    duplicates = set()
    duplicate_count = 0

    for tr in trs:
        cells = [
            norm(x.get_text(" ", strip=True))
            for x in tr.find_all(["th", "td"])
        ]
        if len(cells) < len(headers):
            continue

        def cell(key):
            idx = resolved[key]
            return cells[idx] if idx is not None and idx < len(cells) else None

        pos = norm(cell("pos")).upper()
        if pos not in POSITIONS:
            continue

        name = norm(cell("player"))
        team = canon_team(cell("team"))
        floor = safe_float(cell("floor"))
        proj = safe_float(cell("proj"))
        ceiling = safe_float(cell("ceiling"))

        if not name or not team:
            continue
        if floor is None or proj is None or ceiling is None:
            continue
        if ceiling < floor or proj < floor or proj > ceiling:
            continue

        key = f"{norm_name(name)}|{team}|{pos}"
        if key in duplicates:
            duplicate_count += 1
            continue
        duplicates.add(key)

        width = ceiling - floor
        commitment_payload = json.dumps(
            [name, team, pos, floor, proj, ceiling],
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        raw_rows.append({
            "stable_key": key,
            "player_name": name,
            "team": team,
            "position": pos,
            "floor": floor,
            "projection": proj,
            "ceiling": ceiling,
            "width": width,
            "source_row_commitment_sha256": sha256_bytes(commitment_payload),
        })

    if len(raw_rows) < 150:
        raise RuntimeError(f"IMPLAUSIBLY_FEW_VALID_ROWS {len(raw_rows)}")

    by_pos = defaultdict(list)
    for row in raw_rows:
        by_pos[row["position"]].append(row)

    output_rows = []
    counts = {}

    for pos in POSITIONS:
        rows = by_pos[pos]
        if not rows:
            raise RuntimeError(f"NO_ROWS_FOR_POSITION {pos}")
        counts[pos] = len(rows)

        pct_floor = midrank_percentiles(
            [(r["stable_key"], r["floor"]) for r in rows]
        )
        pct_proj = midrank_percentiles(
            [(r["stable_key"], r["projection"]) for r in rows]
        )
        pct_ceil = midrank_percentiles(
            [(r["stable_key"], r["ceiling"]) for r in rows]
        )
        pct_width = midrank_percentiles(
            [(r["stable_key"], r["width"]) for r in rows]
        )

        for r in sorted(rows, key=lambda x: x["stable_key"]):
            k = r["stable_key"]
            output_rows.append({
                "stable_key": k,
                "player_name": r["player_name"],
                "team": r["team"],
                "position": r["position"],
                "projection_strength_pct": round(pct_proj[k], 9),
                "floor_strength_pct": round(pct_floor[k], 9),
                "ceiling_strength_pct": round(pct_ceil[k], 9),
                "volatility_width_pct": round(pct_width[k], 9),
                "floor_resilience": round(pct_floor[k] - pct_proj[k], 9),
                "ceiling_upside": round(pct_ceil[k] - pct_proj[k], 9),
                "source_row_commitment_sha256": r[
                    "source_row_commitment_sha256"
                ],
            })

    snapshot = {
        "schema_version": 1,
        "study_id": "weekly-floor-ceiling-volatility-v1",
        "phase": "prospective-predictor-snapshot",
        "status": "FROZEN_PREKICKOFF_PREDICTOR_SNAPSHOT",
        "season": SEASON,
        "origin_week": ORIGIN_WEEK,
        "freeze_runtime_utc": now.isoformat(),
        "first_actual_kickoff_utc": cutoff.isoformat(),
        "source": {
            "provider": "NextDyne",
            "url": "https://www.nextdyne.io/tools/dynasty-weekly-projections",
            "response_sha256": sha256(html_path),
            "model_version": snap["model_version"],
            "source_snapshot_display": snap["snapshot_display"],
            "scoring_mode": "logged-out Half-PPR",
        },
        "predictor_contract": {
            "raw_floor_projection_ceiling_values_persisted": False,
            "within_position_midrank_percentiles": True,
            "floor_resilience_definition": (
                "floor_strength_pct - projection_strength_pct"
            ),
            "ceiling_upside_definition": (
                "ceiling_strength_pct - projection_strength_pct"
            ),
            "volatility_width_definition": (
                "within-position percentile of (ceiling - floor)"
            ),
            "overall_score_authorized": False,
        },
        "coverage": {
            "row_count": len(output_rows),
            "by_position": counts,
            "duplicate_rows_dropped": duplicate_count,
        },
        "rows": output_rows,
        "governance": {
            "realized_outcomes_read": False,
            "outcome_association_opened": False,
            "production_change_authorized": False,
            "user_facing_display_authorized": False,
            "fundamental_value_effect_authorized": False,
            "package_adjustment_effect_authorized": False,
            "team_utility_effect_authorized": False,
            "trade_value_effect_authorized": False,
        },
    }

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": 1,
        "study_id": "weekly-floor-ceiling-volatility-v1",
        "origin": f"{SEASON}-W{ORIGIN_WEEK:02d}",
        "status": "PASS_PREKICKOFF_FREEZE",
        "protocol_sha256": sha256(protocol_path),
        "snapshot_sha256": sha256(out),
        "source_html_sha256": sha256(html_path),
        "schedule_sha256": sha256(schedule_path),
        "first_actual_kickoff_utc": cutoff.isoformat(),
        "week_game_ids": game_ids,
        "freeze_runtime_utc": now.isoformat(),
        "raw_provider_values_persisted": False,
        "realized_outcomes_read": False,
        "production_change_authorized": False,
    }
    Path(manifest_path).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "status": snapshot["status"],
        "origin": f"{SEASON}-W{ORIGIN_WEEK:02d}",
        "first_actual_kickoff_utc": cutoff.isoformat(),
        "row_count": len(output_rows),
        "by_position": counts,
        "raw_provider_values_persisted": False,
        "outcomes_read": False,
        "production_authorized": False,
    }, indent=2))


def selftest():
    vals = [("a", 1.0), ("b", 2.0), ("c", 2.0), ("d", 4.0)]
    p = midrank_percentiles(vals)
    assert p["a"] == 0.0
    assert abs(p["b"] - 0.5) < 1e-12
    assert abs(p["c"] - 0.5) < 1e-12
    assert p["d"] == 1.0
    assert norm_name("Marvin Harrison Jr.") == "marvinharrison"
    assert canon_team("ARZ") == "ARI"
    print("PASS: B38 predictor snapshot builder synthetic selftest")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--html")
    ap.add_argument("--schedule")
    ap.add_argument("--protocol")
    ap.add_argument("--out")
    ap.add_argument("--manifest")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    needed = ("html", "schedule", "protocol", "out", "manifest")
    for key in needed:
        if getattr(args, key) is None:
            ap.error(f"--{key} is required")

    build(
        args.html,
        args.schedule,
        args.protocol,
        args.out,
        args.manifest,
    )


if __name__ == "__main__":
    main()
