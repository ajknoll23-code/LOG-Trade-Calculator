#!/usr/bin/env python3
"""
Apply the evidence-backed continuous RB age model to Trade Desk.

PRODUCTION PATCH — intentionally atomic
---------------------------------------
This script updates the existing Trade Desk data/valuation path rather than
creating a parallel model.

It changes:
  1. scripts/sync/sync_sleeper.py
     - carry validated birth_date through roster/free-agent sync records.

  2. index.html
     - add a compact RB_BIRTH_DATE_DATA map built from the committed Sleeper
       cache;
     - preserve the existing ageMultiplier() as the integer-anchor source;
     - add DOB-derived fractional age;
     - linearly interpolate between integer RB age anchors;
     - for qualifying Elite RBs, minimally monotonize the known 23/24 anchor
       inversion by pooling those two anchors;
     - fall back to the deployed integer-age behavior when DOB is unavailable.

  3. scripts/validation/snapshot_values.py
     - mirror the exact new live-JS valuation behavior.

  4. scripts/validation/repo_regression_checks.py
     - make the live JS parity harness exercise the new effective RB age path.

It also adds birth_date fields to the currently committed Sleeper-derived JSON
rows (league_rosters.json, my_roster.json, free_agents.json) from the already
committed players_cache.json. No network access is needed.

Research basis
--------------
- Current deployed integer-age RB birthday jump: up to ~40.9%.
- Continuous age reduces exact birthday jumps to ~0.1%.
- High-production birthday-event MAE improved from 15.5% to 12.0%.
- Anchor-preserving monotone version keeps current anchor levels largely intact
  while removing the elite age-23 -> age-24 inversion.

This script is designed for one production deployment. It refuses to apply
twice.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

INDEX = REPO_ROOT / "index.html"
SYNC_SLEEPER = REPO_ROOT / "scripts" / "sync" / "sync_sleeper.py"
SNAPSHOT = REPO_ROOT / "scripts" / "validation" / "snapshot_values.py"
REGRESSION = REPO_ROOT / "scripts" / "validation" / "repo_regression_checks.py"

PLAYERS_CACHE = REPO_ROOT / "data" / "players_cache.json"
LEAGUE_ROSTERS = REPO_ROOT / "data" / "league_rosters.json"
MY_ROSTER = REPO_ROOT / "data" / "my_roster.json"
FREE_AGENTS = REPO_ROOT / "data" / "free_agents.json"

MIN_RB_DOB_COVERAGE = 85
REQUIRED_PREMIUM_RBS = {
    "bijan robinson",
    "jahmyr gibbs",
    "devon achane",
    "ashton jeanty",
}

PATCH_MARKER = "RB_CONTINUOUS_AGE_V1"


def die(msg: str) -> None:
    raise RuntimeError(msg)


def require(path: Path) -> None:
    if not path.exists():
        die(f"Required file missing: {path.relative_to(REPO_ROOT)}")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        die(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def replace_exact_count(
    text: str, old: str, new: str, expected: int, label: str
) -> str:
    count = text.count(old)
    if count != expected:
        die(f"{label}: expected {expected} matches, found {count}")
    return text.replace(old, new)


def js_normalize_name(name: str) -> str:
    """Mirror index.html normalizeName()."""
    s = str(name or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def match_normalize_name(name: str) -> str:
    """Slightly broader identity-match normalization for source matching."""
    s = js_normalize_name(name)
    s = re.sub(r"\s+(jr|sr|ii|iii|iv)$", "", s)
    return s.strip()


def player_source_name(row: dict[str, Any]) -> str:
    for field in ("full_name", "search_full_name", "player_name", "name"):
        value = row.get(field)
        if value:
            return str(value)
    first = str(row.get("first_name") or "").strip()
    last = str(row.get("last_name") or "").strip()
    return f"{first} {last}".strip()


def parse_dob(raw: Any) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def age_on(dob: date, as_of: date) -> int:
    return as_of.year - dob.year - (
        (as_of.month, as_of.day) < (dob.month, dob.day)
    )


def safe_dob(
    player: dict[str, Any],
    *,
    expected_age: int | float | None = None,
    as_of: date,
) -> str | None:
    dob = parse_dob(player.get("birth_date"))
    if dob is None:
        return None

    calc_age = age_on(dob, as_of)
    if not 18 <= calc_age <= 45:
        return None

    if isinstance(expected_age, (int, float)):
        if abs(calc_age - int(expected_age)) > 1:
            return None

    raw_age = player.get("age")
    if raw_age is not None:
        try:
            raw_age_int = int(raw_age)
        except (TypeError, ValueError):
            raw_age_int = None
        if raw_age_int is not None and not 18 <= raw_age_int <= 45:
            if expected_age is None:
                return None
            if abs(calc_age - int(expected_age)) > 1:
                return None

    return dob.isoformat()


def find_object_statement_end(text: str, marker: str) -> int:
    start = text.find(marker)
    if start < 0:
        die(f"Missing JS marker: {marker}")
    brace = text.find("{", start)
    if brace < 0:
        die(f"Missing opening brace after: {marker}")

    depth = 0
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    i = brace

    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if line_comment:
            if ch == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            if ch == "*" and nxt == "/":
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            i += 1
            continue

        if ch == "/" and nxt == "/":
            line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            block_comment = True
            i += 2
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                while end < len(text) and text[end].isspace():
                    end += 1
                if end < len(text) and text[end] == ";":
                    end += 1
                return end
        i += 1

    die(f"Unterminated JS object: {marker}")


def parse_player_db(index_text: str) -> dict[str, dict[str, Any]]:
    marker = "const PLAYER_DB = {"
    start = index_text.find(marker)
    if start < 0:
        die("Could not locate PLAYER_DB")
    end = find_object_statement_end(index_text, marker)
    body = index_text[start:end]

    pattern = re.compile(
        r"'([^']+)'\s*:\s*\{\s*pos:'([A-Z]+)'\s*,\s*age:(\d+)\s*,\s*role:'([^']+)'"
    )
    out = {
        key: {"pos": pos, "age": int(age), "role": role}
        for key, pos, age, role in pattern.findall(body)
    }
    if len(out) < 500:
        die(f"PLAYER_DB parse unexpectedly small: {len(out)}")
    return out


def load_player_pool() -> dict[str, dict[str, Any]]:
    doc = json.loads(PLAYERS_CACHE.read_text(encoding="utf-8"))
    pool = doc.get("players")
    if not isinstance(pool, dict):
        die("data/players_cache.json missing top-level players mapping")
    return pool


def roster_name_ids() -> dict[str, set[str]]:
    if not LEAGUE_ROSTERS.exists():
        return {}
    doc = json.loads(LEAGUE_ROSTERS.read_text(encoding="utf-8"))
    out: dict[str, set[str]] = {}
    for roster in doc.get("rosters") or []:
        for slot in ("starters", "bench", "taxi", "reserve_ir"):
            for row in roster.get(slot) or []:
                name = match_normalize_name(row.get("name") or "")
                pid = str(row.get("player_id") or "")
                if name and pid:
                    out.setdefault(name, set()).add(pid)
    return out


def build_rb_birth_map(
    player_db: dict[str, dict[str, Any]],
    pool: dict[str, dict[str, Any]],
    *,
    as_of: date,
) -> tuple[dict[str, str], list[str]]:
    by_name: dict[str, list[str]] = {}
    for pid, row in pool.items():
        if not isinstance(row, dict):
            continue
        name = match_normalize_name(player_source_name(row))
        if name:
            by_name.setdefault(name, []).append(str(pid))

    roster_ids = roster_name_ids()

    result: dict[str, str] = {}
    unresolved: list[str] = []

    for key, info in player_db.items():
        if info["pos"] != "RB":
            continue

        match_name = match_normalize_name(key)
        candidates: list[str] = []

        roster_candidates = sorted(roster_ids.get(match_name) or [])
        for pid in roster_candidates:
            if pid in pool:
                candidates.append(pid)

        if not candidates:
            candidates = list(by_name.get(match_name) or [])

        valid: list[tuple[str, str]] = []
        seen = set()
        for pid in candidates:
            if pid in seen:
                continue
            seen.add(pid)
            row = pool.get(pid)
            if not isinstance(row, dict):
                continue
            dob = safe_dob(row, expected_age=info["age"], as_of=as_of)
            if dob:
                valid.append((pid, dob))

        unique_dobs = sorted({dob for _, dob in valid})
        if len(unique_dobs) == 1:
            result[js_normalize_name(key)] = unique_dobs[0]
        else:
            unresolved.append(key)

    if len(result) < MIN_RB_DOB_COVERAGE:
        die(
            f"RB DOB coverage too low: {len(result)} < {MIN_RB_DOB_COVERAGE}. "
            f"Unresolved sample: {unresolved[:10]}"
        )

    missing_required = sorted(
        p for p in REQUIRED_PREMIUM_RBS if p not in result
    )
    if missing_required:
        die(f"Required premium RB DOBs unresolved: {missing_required}")

    return dict(sorted(result.items())), unresolved


def patch_sync_sleeper(text: str) -> str:
    if "def safe_player_birth_date(" in text:
        die("sync_sleeper.py already contains RB continuous-age data patch")

    text = replace_once(
        text,
        "import sys\n",
        "import sys\nfrom datetime import date, datetime, timezone\n",
        "sync imports",
    )

    insertion_anchor = """    return age if 18 <= age <= 45 else None


def load_config():
"""
    birth_fn = r'''    return age if 18 <= age <= 45 else None


def safe_player_birth_date(player_id, player, today=None):
    """Return validated ISO birth date or None.

    Sleeper birth_date is accepted only when it is parseable/plausible and
    consistent with the safe age signal when that signal exists. This keeps
    obviously corrupt DOB rows from feeding fractional-age valuation.
    \"\"\"
    raw = player.get("birth_date")
    if not raw:
        return None
    try:
        dob = date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None

    if today is None:
        today = datetime.now(timezone.utc).date()

    calc_age = today.year - dob.year - (
        (today.month, today.day) < (dob.month, dob.day)
    )
    if not 18 <= calc_age <= 45:
        return None

    safe_age = safe_player_age(player_id, player)
    raw_age = player.get("age")

    if raw_age is not None and safe_age is None:
        return None

    if safe_age is not None and abs(calc_age - safe_age) > 1:
        return None

    return dob.isoformat()


def load_config():
'''
    text = replace_once(
        text, insertion_anchor, birth_fn, "safe_player_birth_date insertion"
    )

    text = replace_once(
        text,
        '            "age": safe_player_age(pid, p),\n            "status": p.get("status"),',
        '            "age": safe_player_age(pid, p),\n'
        '            "birth_date": safe_player_birth_date(pid, p),\n'
        '            "status": p.get("status"),',
        "rostered player birth_date",
    )

    text = replace_once(
        text,
        '"team": pid, "age": None, "status": None, "injury_status": None}',
        '"team": pid, "age": None, "birth_date": None, '
        '"status": None, "injury_status": None}',
        "DEF fallback birth_date",
    )

    text = replace_once(
        text,
        '"team": None, "age": None, "status": None, "injury_status": None}',
        '"team": None, "age": None, "birth_date": None, '
        '"status": None, "injury_status": None}',
        "unknown fallback birth_date",
    )

    text = replace_once(
        text,
        '            "age": age,\n            "status": p.get("status"),',
        '            "age": age,\n'
        '            "birth_date": safe_player_birth_date(pid, p),\n'
        '            "status": p.get("status"),',
        "free-agent birth_date",
    )

    return text


JS_HELPERS = r"""
/* RB_CONTINUOUS_AGE_V1
   Evidence-backed RB age architecture, deployed 2026-09-02.
   - integer ageMultiplier() remains the anchor/fallback source;
   - trusted DOB -> fractional age;
   - interpolation removes once-a-year value cliffs;
   - qualifying Elite RB age-23/24 anchors are minimally pooled to remove
     the deployed 23->24 inversion without wholesale curve repricing. */
function fractionalAgeFromBirthDate(birthDate, fallbackAge, asOfDate=null){
  if(typeof birthDate !== 'string') return fallbackAge;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(birthDate);
  if(!m) return fallbackAge;

  const birthYear = Number(m[1]);
  const birthMonth = Number(m[2]);
  const birthDay = Number(m[3]);
  if(!birthYear || birthMonth < 1 || birthMonth > 12 || birthDay < 1 || birthDay > 31){
    return fallbackAge;
  }

  const now = asOfDate ? new Date(`${asOfDate}T00:00:00Z`) : new Date();
  if(!isFinite(now.getTime())) return fallbackAge;
  const todayMs = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());

  function birthdayMs(year){
    const candidate = new Date(Date.UTC(year, birthMonth - 1, birthDay));
    if(candidate.getUTCMonth() !== birthMonth - 1 || candidate.getUTCDate() !== birthDay){
      return Date.UTC(year, 1, 28);
    }
    return candidate.getTime();
  }

  let birthdayYear = now.getUTCFullYear();
  let lastBirthdayMs = birthdayMs(birthdayYear);
  if(todayMs < lastBirthdayMs){
    birthdayYear -= 1;
    lastBirthdayMs = birthdayMs(birthdayYear);
  }
  const nextBirthdayMs = birthdayMs(birthdayYear + 1);
  const span = nextBirthdayMs - lastBirthdayMs;
  if(!(span > 0)) return fallbackAge;

  const wholeYears = birthdayYear - birthYear;
  const frac = (todayMs - lastBirthdayMs) / span;
  const age = wholeYears + frac;
  return (isFinite(age) && age >= 18 && age <= 45) ? age : fallbackAge;
}

function rbMonotoneAgeAnchor(age, role, realProduction, rawProduction){
  const anchor = ageMultiplier('RB', age, role, realProduction, rawProduction);
  const qualifiesEliteYouth =
    role === 'Elite' &&
    typeof rawProduction === 'number' &&
    rawProduction >= 0.65;

  if(qualifiesEliteYouth && (age === 23 || age === 24)){
    const a23 = ageMultiplier('RB', 23, role, realProduction, rawProduction);
    const a24 = ageMultiplier('RB', 24, role, realProduction, rawProduction);
    return (a23 + a24) / 2;
  }
  return anchor;
}

function rbContinuousAgeMultiplier(age, role, realProduction, rawProduction){
  if(typeof age !== 'number' || !isFinite(age)){
    return ageMultiplier('RB', age, role, realProduction, rawProduction);
  }

  const lo = Math.floor(age);
  const hi = Math.ceil(age);
  if(lo === hi){
    return rbMonotoneAgeAnchor(lo, role, realProduction, rawProduction);
  }

  const a0 = rbMonotoneAgeAnchor(lo, role, realProduction, rawProduction);
  const a1 = rbMonotoneAgeAnchor(hi, role, realProduction, rawProduction);
  const t = age - lo;
  return a0 + t * (a1 - a0);
}

function effectiveAgeMultiplier(pos, age, role, name, realProduction, rawProduction){
  if(pos !== 'RB'){
    return ageMultiplier(pos, age, role, realProduction, rawProduction);
  }

  const normKey = normalizeName(name || '');
  const info = PLAYER_DB[normKey];
  const birthDate =
    (info && typeof info.birth_date === 'string' && info.birth_date) ||
    RB_BIRTH_DATE_DATA[normKey] ||
    null;

  if(!birthDate){
    return ageMultiplier(pos, age, role, realProduction, rawProduction);
  }

  const fractionalAge = fractionalAgeFromBirthDate(birthDate, age);
  return rbContinuousAgeMultiplier(
    fractionalAge, role, realProduction, rawProduction
  );
}
"""


def patch_index(
    text: str,
    rb_birth_map: dict[str, str],
) -> str:
    if PATCH_MARKER in text or "const RB_BIRTH_DATE_DATA =" in text:
        die("index.html already contains RB continuous-age patch")

    player_end = find_object_statement_end(text, "const PLAYER_DB = {")
    birth_const = (
        "\n\n/* Compact trusted DOB map for continuous RB age valuation. "
        "Generated from data/players_cache.json. */\n"
        "const RB_BIRTH_DATE_DATA = "
        + json.dumps(rb_birth_map, indent=2, sort_keys=True)
        + ";\n"
    )
    text = text[:player_end] + birth_const + text[player_end:]

    marker = "\nfunction playerValue(pos, age, role, name){"
    if text.count(marker) != 1:
        die(f"index playerValue marker count != 1: {text.count(marker)}")
    text = text.replace(marker, "\n" + JS_HELPERS + marker, 1)

    text = replace_once(
        text,
        "  const am = ageMultiplier(pos, age, role, rm, rawRm);",
        "  const am = effectiveAgeMultiplier(pos, age, role, name, rm, rawRm);",
        "playerValue effective age",
    )

    # Patch each live roster merge independently. The two functions have
    # slightly different surrounding code/comments, so do not require the
    # age+role lines to be text-identical across both blocks.
    age_pattern = re.compile(
        r"(?m)^(?P<indent>\s*)age: \(typeof p\.age === 'number'\) \? p\.age : "
        r"\(existing \? existing\.age : 24\),\s*$"
    )

    for function_name in ("mergeLiveRoster", "mergeLeagueRosters"):
        fn_marker = f"function {function_name}(data){{"
        fn_start = text.find(fn_marker)
        if fn_start < 0:
            die(f"index missing function: {function_name}")

        next_fn = text.find("\nfunction ", fn_start + len(fn_marker))
        fn_end = next_fn if next_fn >= 0 else len(text)
        block = text[fn_start:fn_end]

        matches = list(age_pattern.finditer(block))
        if len(matches) != 1:
            die(
                f"{function_name}: expected exactly 1 live age assignment, "
                f"found {len(matches)}"
            )

        m = matches[0]
        indent = m.group("indent")
        replacement = (
            m.group(0)
            + "\n"
            + indent
            + "birth_date: (typeof p.birth_date === 'string' && p.birth_date) "
              "? p.birth_date : (existing ? (existing.birth_date || null) : null),"
        )

        patched_block = (
            block[:m.start()] + replacement + block[m.end():]
        )
        text = text[:fn_start] + patched_block + text[fn_end:]

    return text


PY_SNAPSHOT_HELPERS = r"""

def normalize_lookup_name(name):
    s = str(name or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def fractional_age_from_birth_date(birth_date, fallback_age, as_of=None):
    if not isinstance(birth_date, str):
        return fallback_age
    try:
        dob = date.fromisoformat(birth_date[:10])
    except ValueError:
        return fallback_age

    if as_of is None:
        as_of = datetime.now(timezone.utc).date()

    def birthday_in_year(year):
        try:
            return date(year, dob.month, dob.day)
        except ValueError:
            if dob.month == 2 and dob.day == 29:
                return date(year, 2, 28)
            raise

    birthday_year = as_of.year
    last_birthday = birthday_in_year(birthday_year)
    if as_of < last_birthday:
        birthday_year -= 1
        last_birthday = birthday_in_year(birthday_year)

    next_birthday = birthday_in_year(birthday_year + 1)
    span = (next_birthday - last_birthday).days
    if span <= 0:
        return fallback_age

    age = (birthday_year - dob.year) + (as_of - last_birthday).days / span
    return age if 18 <= age <= 45 else fallback_age


def rb_monotone_age_anchor(age, role, real_production, raw_production, cfg):
    anchor = age_multiplier(
        "RB", age, role, real_production, raw_production, cfg
    )
    qualifies_elite_youth = (
        role == "Elite"
        and isinstance(raw_production, (int, float))
        and raw_production >= 0.65
    )
    if qualifies_elite_youth and age in (23, 24):
        a23 = age_multiplier(
            "RB", 23, role, real_production, raw_production, cfg
        )
        a24 = age_multiplier(
            "RB", 24, role, real_production, raw_production, cfg
        )
        return (a23 + a24) / 2.0
    return anchor


def rb_continuous_age_multiplier(
    age, role, real_production, raw_production, cfg
):
    if not isinstance(age, (int, float)) or not math.isfinite(age):
        return age_multiplier(
            "RB", age, role, real_production, raw_production, cfg
        )

    lo = math.floor(age)
    hi = math.ceil(age)
    if lo == hi:
        return rb_monotone_age_anchor(
            lo, role, real_production, raw_production, cfg
        )

    a0 = rb_monotone_age_anchor(
        lo, role, real_production, raw_production, cfg
    )
    a1 = rb_monotone_age_anchor(
        hi, role, real_production, raw_production, cfg
    )
    t = age - lo
    return a0 + t * (a1 - a0)


def effective_age_multiplier(
    pos,
    age,
    role,
    key,
    real_production,
    raw_production,
    cfg,
    as_of=None,
):
    if pos != "RB":
        return age_multiplier(
            pos, age, role, real_production, raw_production, cfg
        )

    norm_key = normalize_lookup_name(key)
    birth_date = cfg["rb_birth_date_data"].get(norm_key)
    if not birth_date:
        return age_multiplier(
            pos, age, role, real_production, raw_production, cfg
        )

    fractional_age = fractional_age_from_birth_date(
        birth_date, age, as_of=as_of
    )
    return rb_continuous_age_multiplier(
        fractional_age, role, real_production, raw_production, cfg
    )
"""


def patch_snapshot(text: str) -> str:
    if "def effective_age_multiplier(" in text:
        die("snapshot_values.py already contains RB continuous-age patch")

    text = replace_once(
        text,
        "from datetime import datetime, timezone",
        "from datetime import date, datetime, timezone",
        "snapshot datetime import",
    )

    parse_anchor = """def load_from_html(html_path):
"""
    parse_fn = r"""def parse_simple_string_object(body):
    pairs = re.findall(
        r'(?:\'([^\']+)\'|"([^"]+)")\s*:\s*(?:\'([^\']*)\'|"([^"]*)")',
        body,
    )
    out = {}
    for key_single, key_double, value_single, value_double in pairs:
        out[key_single or key_double] = value_single or value_double
    return out


def load_from_html(html_path):
"""
    text = replace_once(
        text, parse_anchor, parse_fn, "snapshot string-object parser"
    )

    text = replace_once(
        text,
        '    role_mult = parse_simple_numeric_object(extract_object_body(content, "ROLE_MULT"))\n',
        '    role_mult = parse_simple_numeric_object(extract_object_body(content, "ROLE_MULT"))\n'
        '    rb_birth_date_data = parse_simple_string_object(\n'
        '        extract_object_body(content, "RB_BIRTH_DATE_DATA")\n'
        '    )\n',
        "snapshot RB birth map parse",
    )

    text = replace_once(
        text,
        '        "role_mult": role_mult,\n        "age_curve": age_curve,',
        '        "role_mult": role_mult,\n'
        '        "rb_birth_date_data": rb_birth_date_data,\n'
        '        "age_curve": age_curve,',
        "snapshot cfg birth map",
    )

    compute_marker = "\n\ndef compute_all_values(cfg):"
    if text.count(compute_marker) != 1:
        die("snapshot compute_all_values marker not unique")
    text = text.replace(
        compute_marker,
        PY_SNAPSHOT_HELPERS + compute_marker,
        1,
    )

    text = replace_once(
        text,
        "        am = age_multiplier(pos, age, role, rm, raw_rm, cfg)",
        "        am = effective_age_multiplier(\n"
        "            pos, age, role, key, rm, raw_rm, cfg\n"
        "        )",
        "snapshot effective age",
    )

    text = replace_once(
        text,
        '    assert cfg["lb_post_peak_decay_power"] == 0.5\n',
        '    assert cfg["lb_post_peak_decay_power"] == 0.5\n'
        '    assert len(cfg["rb_birth_date_data"]) >= 85\n',
        "snapshot DOB coverage selftest",
    )

    return text


def patch_regression(text: str) -> str:
    if '_extract_const_object(text, "RB_BIRTH_DATE_DATA")' in text:
        die("repo_regression_checks.py already contains RB continuous-age patch")

    text = replace_once(
        text,
        '        _extract_const_object(text, "PLAYER_DB"),\n',
        '        _extract_const_object(text, "PLAYER_DB"),\n'
        '        _extract_const_object(text, "RB_BIRTH_DATE_DATA"),\n',
        "regression birth const",
    )

    text = replace_once(
        text,
        '        _extract_function(text, "ageMultiplier"),\n'
        '        _extract_function(text, "playerValue"),',
        '        _extract_function(text, "ageMultiplier"),\n'
        '        _extract_function(text, "fractionalAgeFromBirthDate"),\n'
        '        _extract_function(text, "rbMonotoneAgeAnchor"),\n'
        '        _extract_function(text, "rbContinuousAgeMultiplier"),\n'
        '        _extract_function(text, "effectiveAgeMultiplier"),\n'
        '        _extract_function(text, "playerValue"),',
        "regression helper extraction",
    )

    text = replace_once(
        text,
        "  const am = ageMultiplier(info.pos, info.age, info.role, rm, rawRm);",
        "  const am = effectiveAgeMultiplier("
        "info.pos, info.age, info.role, key, rm, rawRm);",
        "regression effective age",
    )

    return text


def enrich_json_birth_dates(
    path: Path,
    pool: dict[str, dict[str, Any]],
    *,
    as_of: date,
) -> int:
    if not path.exists():
        return 0

    doc = json.loads(path.read_text(encoding="utf-8"))
    changed = 0

    def visit(node: Any) -> None:
        nonlocal changed
        if isinstance(node, dict):
            pid_raw = node.get("player_id")
            if pid_raw is not None:
                pid = str(pid_raw)
                source = pool.get(pid)
                if isinstance(source, dict):
                    expected_age = node.get("age")
                    dob = safe_dob(
                        source,
                        expected_age=expected_age
                        if isinstance(expected_age, (int, float))
                        else None,
                        as_of=as_of,
                    )
                    if node.get("birth_date") != dob:
                        node["birth_date"] = dob
                        changed += 1
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(doc)

    if changed:
        path.write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return changed


def validate_patched_sources(
    index_text: str,
    sync_text: str,
    snapshot_text: str,
    regression_text: str,
    birth_map: dict[str, str],
) -> None:
    required_index = [
        "const RB_BIRTH_DATE_DATA =",
        "function fractionalAgeFromBirthDate",
        "function rbMonotoneAgeAnchor",
        "function rbContinuousAgeMultiplier",
        "function effectiveAgeMultiplier",
        "const am = effectiveAgeMultiplier",
        "birth_date: (typeof p.birth_date === 'string'",
    ]
    for marker in required_index:
        if marker not in index_text:
            die(f"Patched index missing marker: {marker}")

    if index_text.count(
        "birth_date: (typeof p.birth_date === 'string'"
    ) != 2:
        die("Expected birth_date merge in exactly two live roster merge paths")

    for marker in (
        "def safe_player_birth_date(",
        '"birth_date": safe_player_birth_date(pid, p)',
    ):
        if marker not in sync_text:
            die(f"Patched sync_sleeper missing marker: {marker}")

    for marker in (
        "def fractional_age_from_birth_date(",
        "def rb_monotone_age_anchor(",
        "def rb_continuous_age_multiplier(",
        "def effective_age_multiplier(",
        '"rb_birth_date_data": rb_birth_date_data',
    ):
        if marker not in snapshot_text:
            die(f"Patched snapshot missing marker: {marker}")

    for marker in (
        '_extract_const_object(text, "RB_BIRTH_DATE_DATA")',
        '_extract_function(text, "effectiveAgeMultiplier")',
        "const am = effectiveAgeMultiplier",
    ):
        if marker not in regression_text:
            die(f"Patched regression missing marker: {marker}")

    if len(birth_map) < MIN_RB_DOB_COVERAGE:
        die("DOB map unexpectedly below required coverage")


def run_selftest() -> None:
    assert js_normalize_name("D'Andre Swift") == "dandre swift"
    assert match_normalize_name("Michael Penix Jr.") == "michael penix"

    dob = date(2002, 1, 30)
    assert age_on(dob, date(2026, 1, 29)) == 23
    assert age_on(dob, date(2026, 1, 30)) == 24

    fake = {"birth_date": "2002-01-30", "age": 24}
    assert (
        safe_dob(fake, expected_age=24, as_of=date(2026, 9, 2))
        == "2002-01-30"
    )
    corrupt = {"birth_date": "2022-10-21", "age": 3}
    assert safe_dob(corrupt, expected_age=23, as_of=date(2026, 9, 2)) is None

    print("apply_rb_continuous_age_model self-test passed.")


def apply_patch() -> None:
    for path in (
        INDEX,
        SYNC_SLEEPER,
        SNAPSHOT,
        REGRESSION,
        PLAYERS_CACHE,
    ):
        require(path)

    index_text = INDEX.read_text(encoding="utf-8")
    sync_text = SYNC_SLEEPER.read_text(encoding="utf-8")
    snapshot_text = SNAPSHOT.read_text(encoding="utf-8")
    regression_text = REGRESSION.read_text(encoding="utf-8")

    if PATCH_MARKER in index_text:
        die("Production RB continuous-age patch already applied")

    as_of = datetime.now(timezone.utc).date()
    player_db = parse_player_db(index_text)
    pool = load_player_pool()

    birth_map, unresolved = build_rb_birth_map(
        player_db, pool, as_of=as_of
    )

    patched_sync = patch_sync_sleeper(sync_text)
    patched_index = patch_index(index_text, birth_map)
    patched_snapshot = patch_snapshot(snapshot_text)
    patched_regression = patch_regression(regression_text)

    validate_patched_sources(
        patched_index,
        patched_sync,
        patched_snapshot,
        patched_regression,
        birth_map,
    )

    SYNC_SLEEPER.write_text(patched_sync, encoding="utf-8")
    INDEX.write_text(patched_index, encoding="utf-8")
    SNAPSHOT.write_text(patched_snapshot, encoding="utf-8")
    REGRESSION.write_text(patched_regression, encoding="utf-8")

    data_changes = {}
    for path in (LEAGUE_ROSTERS, MY_ROSTER, FREE_AGENTS):
        data_changes[str(path.relative_to(REPO_ROOT))] = (
            enrich_json_birth_dates(path, pool, as_of=as_of)
        )

    rb_count = sum(
        1 for info in player_db.values() if info["pos"] == "RB"
    )
    print(
        f"Applied {PATCH_MARKER}: {len(birth_map)}/{rb_count} RB DOBs mapped."
    )
    if unresolved:
        print(
            "Integer-age fallback retained for unresolved RBs: "
            + ", ".join(unresolved)
        )
    print("Sleeper-derived JSON birth_date rows updated:")
    for path, count in data_changes.items():
        print(f"  {path}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return
    if args.apply:
        apply_patch()
        return

    parser.error("Choose --selftest or --apply")


if __name__ == "__main__":
    main()
