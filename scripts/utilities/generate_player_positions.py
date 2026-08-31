#!/usr/bin/env python3
"""Generate scripts/artifacts/generated/player_positions.json from canonical Trade Desk data.

The lookup contains, in precedence order:
1. every current PLAYER_DB canonical key -> position;
2. known legacy/abbreviated aliases -> the SAME canonical position; and
3. collision-safe active Sleeper names from data/players_cache.json, used only
   as a fallback for historical KTC-rated players no longer present in PLAYER_DB.

Canonical entries are never replaced by aliases or Sleeper fallbacks. Ambiguous
normalized Sleeper names are never guessed.

This fixes the old failure mode where player_positions.json had the same row
count as PLAYER_DB but 29 canonical players were missing because old alias keys
occupied their places.

Canonical implementation:
    python3 scripts/utilities/generate_player_positions.py

"""

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
REPO_ROOT = SCRIPTS_DIR.parent
INDEX_PATH = REPO_ROOT / "index.html"
PPG_PATH = SCRIPTS_DIR / "model" / "ppg_pipeline.py"
PLAYERS_CACHE_PATH = REPO_ROOT / "data" / "players_cache.json"
OUT_PATH = SCRIPTS_DIR / "artifacts" / "generated" / "player_positions.json"

POS_BUCKET = {
    "DE": "DL", "DT": "DL", "DL": "DL",
    "OLB": "LB", "ILB": "LB", "LB": "LB",
    "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB", "DB": "DB",
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "K",
}

KTC_LEGACY_ALIASES = {
    "harold perkins": "harold perkins jr",
    "michael penix": "michael penix jr",
    "zonovan knight": "bam knight",
}


def normalize_name(s):
    return re.sub(r"\s+", " ", re.sub(r"[.'\u2019-]", "", (s or "").strip().lower()))


def parse_player_positions(index_path=INDEX_PATH):
    text = Path(index_path).read_text(encoding="utf-8")
    m = re.search(r"const PLAYER_DB = \{(.*?)\n\};", text, re.S)
    if not m:
        raise RuntimeError("Could not find PLAYER_DB in index.html")
    positions = {
        key: pos
        for key, pos in re.findall(r"'([^']+)'\s*:\s*\{\s*pos:'([A-Z]+)'", m.group(1))
    }
    if not positions:
        raise RuntimeError("PLAYER_DB position parse produced zero rows")
    return positions


def load_known_aliases(ppg_path=PPG_PATH):
    src = Path(ppg_path).read_text(encoding="utf-8")
    m = re.search(r"ALIASES\s*=\s*\{.*?\n\}", src, re.S)
    if not m:
        raise RuntimeError("Could not find ALIASES in scripts/model/ppg_pipeline.py")
    ns = {}
    exec(m.group(0), ns)
    aliases = dict(ns["ALIASES"])
    aliases.update(KTC_LEGACY_ALIASES)
    return aliases


def load_collision_safe_sleeper_positions(cache_path=PLAYERS_CACHE_PATH):
    """Return unique active Sleeper normalized-name -> Trade Desk bucket."""
    cache_path = Path(cache_path)
    if not cache_path.exists():
        return {}
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    pool = data.get("players", data)

    by_name = {}
    for p in pool.values():
        if not p.get("team"):
            continue
        name = (p.get("full_name") or f"{p.get('first_name','')} {p.get('last_name','')}").strip()
        if not name:
            continue
        key = normalize_name(name)
        fantasy_positions = p.get("fantasy_positions") or []
        buckets = []
        for fp in fantasy_positions:
            bucket = POS_BUCKET.get(fp)
            if bucket and bucket not in buckets:
                buckets.append(bucket)
        bucket = buckets[0] if buckets else POS_BUCKET.get(p.get("position"))
        if not bucket:
            continue
        by_name.setdefault(key, set()).add(bucket)

    return {name: next(iter(buckets)) for name, buckets in by_name.items() if len(buckets) == 1}


def build_player_position_lookup(index_path=INDEX_PATH, ppg_path=PPG_PATH, cache_path=PLAYERS_CACHE_PATH):
    canonical = parse_player_positions(index_path)
    lookup = dict(canonical)

    for alias, target in load_known_aliases(ppg_path).items():
        if target in canonical and alias not in lookup:
            lookup[alias] = canonical[target]

    for name, pos in load_collision_safe_sleeper_positions(cache_path).items():
        lookup.setdefault(name, pos)

    return lookup


def write_positions(index_path=INDEX_PATH, out_path=OUT_PATH):
    lookup = build_player_position_lookup(index_path)
    Path(out_path).write_text(json.dumps(dict(sorted(lookup.items())), indent=2) + "\n", encoding="utf-8")
    return lookup


def run_selftest():
    sample = """<script>
const PLAYER_DB = {
 'alpha full':{pos:'LB',age:25,role:'Starter'},
 'beta':{pos:'DL',age:26,role:'Rotational'},
};
</script>"""
    aliases = """ALIASES = {
    'a full': 'alpha full',
}
"""
    cache = {
        "players": {
            "1": {"full_name": "Gamma", "team": "ARI", "position": "CB", "fantasy_positions": ["CB"]},
            "2": {"full_name": "Collision", "team": "BUF", "position": "LB", "fantasy_positions": ["LB"]},
            "3": {"full_name": "Collision", "team": "SEA", "position": "DE", "fantasy_positions": ["DL"]},
        }
    }
    tmp_html = SCRIPT_DIR / ".player_positions_selftest.html"
    tmp_ppg = SCRIPT_DIR / ".player_positions_selftest.py"
    tmp_cache = SCRIPT_DIR / ".player_positions_selftest.json"
    try:
        tmp_html.write_text(sample, encoding="utf-8")
        tmp_ppg.write_text(aliases, encoding="utf-8")
        tmp_cache.write_text(json.dumps(cache), encoding="utf-8")
        got = build_player_position_lookup(tmp_html, tmp_ppg, tmp_cache)
        assert got["alpha full"] == "LB"
        assert got["beta"] == "DL"
        assert got["a full"] == "LB"
        assert got["gamma"] == "DB"
        assert "collision" not in got
    finally:
        tmp_html.unlink(missing_ok=True)
        tmp_ppg.unlink(missing_ok=True)
        tmp_cache.unlink(missing_ok=True)
    print("generate_player_positions self-test passed.")


def main():
    if "--selftest" in sys.argv:
        run_selftest()
        return
    lookup = write_positions()
    canonical_n = len(parse_player_positions())
    print(
        f"Wrote {OUT_PATH}: {canonical_n} canonical PLAYER_DB positions + "
        f"{len(lookup) - canonical_n} safe alias/Sleeper fallback lookups."
    )


if __name__ == "__main__":
    main()
