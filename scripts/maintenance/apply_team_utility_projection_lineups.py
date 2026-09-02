#!/usr/bin/env python3
"""Deploy projection-selected Team Utility starter lineups.

TEAM_UTILITY_PROJECTION_LINEUP_V1

Projection points choose starters. Fundamental Value remains the accounting
unit for lineupDelta, benchDelta, and Team Utility. Taxi/reserve-IR players
remain in bench economics but are not startable. TU_BENCH_WEIGHT is untouched.
"""

from pathlib import Path
import argparse
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
SCHEDULED = ROOT / ".github/workflows/scheduled-data-refresh.yml"
REGRESSION = ROOT / "scripts/validation/repo_regression_checks.py"
MARKER = "TEAM_UTILITY_PROJECTION_LINEUP_V1"


def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {n}")
    return text.replace(old, new, 1)


def patch_index(text):
    if MARKER in text:
        return text

    text = replace_once(
        text,
        """let MY_ROSTER = MY_ROSTER_FALLBACK.slice();
let MY_ROSTER_ID = null; // set from live sync; used to exclude my own team from the trade-target scan
let OWN_ROSTER_ID = null; // set ONLY by the personal sync below, never by switchToTeam —
""",
        """const MY_ROSTER_TAXI_FALLBACK = new Set([
  'devin neal','drew allar','michael trigg','bryce lance','derrick moore',
]);
let MY_ROSTER = MY_ROSTER_FALLBACK.slice();
let MY_ROSTER_SLOT_BY_KEY = Object.fromEntries(MY_ROSTER.map(k => [k, 'bench']));
for(const key of MY_ROSTER_TAXI_FALLBACK) MY_ROSTER_SLOT_BY_KEY[key] = 'taxi';
let MY_ROSTER_ID = null; // set from live sync; used to exclude my own team from the trade-target scan
let OWN_ROSTER_ID = null; // set ONLY by the personal sync below, never by switchToTeam —
""",
        "roster slot fallback state",
    )

    text = replace_once(
        text,
        """function mergeLiveRoster(data){
  const keys = [];
  const slotDefaults = { starters:'Starter', bench:'Rotational', taxi:'Speculative' };
""",
        """function mergeLiveRoster(data){
  const keys = [];
  const slotByKey = {};
  const slotDefaults = { starters:'Starter', bench:'Rotational', taxi:'Speculative' };
""",
        "personal roster slot map",
    )

    old = """        birth_date: (typeof p.birth_date === 'string' && p.birth_date) ? p.birth_date : (existing ? (existing.birth_date || null) : null),
        role: existing ? existing.role : slotDefaults[slot],
"""
    new = """        birth_date: (typeof p.birth_date === 'string' && p.birth_date) ? p.birth_date : (existing ? (existing.birth_date || null) : null),
        sleeper_id: (p.player_id !== undefined && p.player_id !== null) ? String(p.player_id) : (existing ? (existing.sleeper_id || null) : null),
        role: existing ? existing.role : slotDefaults[slot],
"""
    n = text.count(old)
    if n != 2:
        raise RuntimeError(f"Sleeper ID merge: expected 2 matches, found {n}")
    text = text.replace(old, new, 2)

    text = replace_once(
        text,
        """      };
      keys.push(key);
    }
  }
  MY_ROSTER = keys;
""",
        """      };
      keys.push(key);
      slotByKey[key] = slot;
    }
  }
  MY_ROSTER = keys;
  MY_ROSTER_SLOT_BY_KEY = slotByKey;
""",
        "personal roster slot capture",
    )

    text = replace_once(
        text,
        """        seenThisSync.add(key);
        players.push({ key, slot });
        playerCount++;
""",
        """        seenThisSync.add(key);
        players.push({
          key,
          slot,
          sleeper_id: (p.player_id !== undefined && p.player_id !== null) ? String(p.player_id) : null,
        });
        playerCount++;
""",
        "league roster stable ID preservation",
    )

    text = replace_once(
        text,
        """function switchToTeam(rosterId){
  const team = LEAGUE_ROSTERS[rosterId];
  if(!team) return;
  MY_ROSTER = team.players.map(p => p.key);
  MY_ROSTER_ID = rosterId;
""",
        """function switchToTeam(rosterId){
  const team = LEAGUE_ROSTERS[rosterId];
  if(!team) return;
  MY_ROSTER = team.players.map(p => p.key);
  MY_ROSTER_SLOT_BY_KEY = Object.fromEntries(team.players.map(p => [p.key, p.slot]));
  MY_ROSTER_ID = rosterId;
""",
        "switchToTeam slot preservation",
    )

    text = replace_once(
        text,
        """function playerValueByKey(key){
  const info = PLAYER_DB[key];
  if(!info) return null;
  return playerValue(info.pos, info.age, info.role, titleCase(key));
}

/* ---------- Team Utility Engine ----------
""",
        """function playerValueByKey(key){
  const info = PLAYER_DB[key];
  if(!info) return null;
  return playerValue(info.pos, info.age, info.role, titleCase(key));
}

/* ---------- Team Utility lineup projections ----------
   TEAM_UTILITY_PROJECTION_LINEUP_V1

   Projection points decide WHO starts. Fundamental Value still decides WHAT
   those starters and bench players are worth. The two scales are never mixed.
   Stable Sleeper player_id is the projection identity. K intentionally falls
   back to Fundamental Value because the projection artifact omits kickers.
   If the artifact fails to load, all players fall back to the prior FV order. */
const TEAM_UTILITY_PROJECTION_URL =
  'https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/refs/heads/main/scripts/artifacts/generated/team_utility_lineup_projections.json';
let TEAM_UTILITY_LINEUP_PROJECTIONS = null;
let TEAM_UTILITY_PROJECTION_STATUS = 'loading';

function syncTeamUtilityLineupProjections(){
  TEAM_UTILITY_PROJECTION_STATUS = 'loading';
  fetch(TEAM_UTILITY_PROJECTION_URL)
    .then(r => { if(!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(data => {
      const players = data && data.players;
      const playerCount = players && typeof players === 'object' ? Object.keys(players).length : 0;
      if(data.schema_version !== 1 || Number(data.season) !== 2026 || playerCount < 400){
        throw new Error('unexpected Team Utility projection artifact schema/coverage');
      }
      TEAM_UTILITY_LINEUP_PROJECTIONS = data;
      TEAM_UTILITY_PROJECTION_STATUS = 'ready';
      render();
    })
    .catch(err => {
      TEAM_UTILITY_LINEUP_PROJECTIONS = null;
      TEAM_UTILITY_PROJECTION_STATUS = 'failed';
      console.warn('Team Utility projection sync failed; using Fundamental Value starter ordering:', err);
      render();
    });
}

function teamUtilityProjectionByKey(key){
  if(TEAM_UTILITY_PROJECTION_STATUS !== 'ready' || !TEAM_UTILITY_LINEUP_PROJECTIONS) return null;
  const info = PLAYER_DB[key];
  if(!info || info.pos === 'K' || info.sleeper_id === undefined || info.sleeper_id === null) return null;
  const row = TEAM_UTILITY_LINEUP_PROJECTIONS.players[String(info.sleeper_id)];
  if(!row) return null;
  const projection = Number(row.projection);
  return Number.isFinite(projection) ? projection : null;
}

/* ---------- Team Utility Engine ----------
""",
        "Team Utility projection runtime",
    )

    text = replace_once(
        text,
        """/* Greedy lineup fill: dedicated slots first (each takes the highest-value
   remaining eligible player), then flex slots (each round takes the
   single highest-value remaining player eligible for any still-open flex
   slot). Provably optimal for this specific league's nested eligibility
   structure (flex sets are supersets of the dedicated sets feeding them)
   -- see the design doc's Section 6 for the actual argument, not repeated
   here. Returns {starters: [{key,pos,value}], bench: [{key,pos,value}]}. */
function tuOptimizeLineup(players){
  // players: [{key, pos, value}] -- expects real playerValueByKey() output
  // already attached, not raw PLAYER_DB entries, so this function has no
  // value-calculation logic of its own (see the architecture note above).
  const remaining = players.slice().sort((a,b) => b.value - a.value);
  const starters = [];
""",
        """/* Legal lineup fill is unchanged; only the ordering objective changes.
   Projection points select starters when available. Fundamental Value is the
   explicit fallback and remains the only Team Utility accounting scale. */
function tuLineupCompare(a, b){
  if(a.pos === 'K' && b.pos === 'K') return b.value - a.value;
  const ap = Number.isFinite(a.lineupProjection);
  const bp = Number.isFinite(b.lineupProjection);
  if(ap && bp){
    const diff = b.lineupProjection - a.lineupProjection;
    return diff !== 0 ? diff : (b.value - a.value);
  }
  if(ap !== bp) return ap ? -1 : 1;
  return b.value - a.value;
}

function tuOptimizeLineup(players){
  const remaining = players.slice().sort(tuLineupCompare);
  const starters = [];
""",
        "projection lineup comparator",
    )

    text = replace_once(
        text,
        """      if(remaining[i].pos === slot.pos){
        starters.push(remaining[i]);
""",
        """      if(remaining[i].starterEligible !== false && remaining[i].pos === slot.pos){
        starters.push(remaining[i]);
""",
        "dedicated starter eligibility",
    )

    text = replace_once(
        text,
        """      const p = remaining[i];
      const openSlot = flexRemaining.find(f => f.count > 0 && f.eligible.includes(p.pos));
""",
        """      const p = remaining[i];
      if(p.starterEligible === false) continue;
      const openSlot = flexRemaining.find(f => f.count > 0 && f.eligible.includes(p.pos));
""",
        "flex starter eligibility",
    )

    text = replace_once(
        text,
        """/* Builds the {key,pos,value} list tuOptimizeLineup expects, from a list of
   PLAYER_DB keys. Silently skips anyone with no PLAYER_DB entry or no
   computable value -- consistent with how the rest of this file treats
   missing data (skip, don't fabricate), not a Team-Utility-specific
   choice. */
function tuPlayersFromKeys(keys){
  const out = [];
  for(const key of keys){
    const info = PLAYER_DB[key];
    if(!info) continue;
    const val = playerValueByKey(key);
    if(val && val > 0) out.push({ key, pos: info.pos, value: val });
  }
  return out;
}
""",
        """/* Build Team Utility player objects with both selection and accounting data.
   Taxi/reserve-IR players remain in bench economics but cannot start. */
function tuPlayersFromKeys(keys, slotByKey = {}){
  const out = [];
  for(const key of keys){
    const info = PLAYER_DB[key];
    if(!info) continue;
    const val = playerValueByKey(key);
    if(!val || val <= 0) continue;
    const slot = slotByKey[key] || 'bench';
    out.push({
      key,
      pos: info.pos,
      value: val,
      lineupProjection: teamUtilityProjectionByKey(key),
      starterEligible: slot !== 'taxi' && slot !== 'reserve_ir',
      rosterSlot: slot,
    });
  }
  return out;
}

function tuBuildPostSlotMap(preRosterKeys, postRosterKeys, preSlotByKey){
  const preSet = new Set(preRosterKeys);
  const out = {};
  for(const key of postRosterKeys){
    out[key] = (preSet.has(key) && preSlotByKey && preSlotByKey[key])
      ? preSlotByKey[key]
      : 'bench';
  }
  return out;
}
""",
        "Team Utility player construction",
    )

    text = replace_once(
        text,
        """function calculateTeamUtility(preRosterKeys, postRosterKeys){
  const pre = tuOptimizeLineup(tuPlayersFromKeys(preRosterKeys));
  const post = tuOptimizeLineup(tuPlayersFromKeys(postRosterKeys));
  const lineupDelta = tuSum(post.starters) - tuSum(pre.starters);
""",
        """function calculateTeamUtility(
  preRosterKeys,
  postRosterKeys,
  preSlotByKey = MY_ROSTER_SLOT_BY_KEY,
  postSlotByKey = null
){
  const resolvedPostSlots = postSlotByKey || tuBuildPostSlotMap(
    preRosterKeys,
    postRosterKeys,
    preSlotByKey || {}
  );
  const pre = tuOptimizeLineup(tuPlayersFromKeys(preRosterKeys, preSlotByKey || {}));
  const post = tuOptimizeLineup(tuPlayersFromKeys(postRosterKeys, resolvedPostSlots));
  const lineupDelta = tuSum(post.starters) - tuSum(pre.starters);
""",
        "slot-aware Team Utility calculation",
    )

    text = replace_once(
        text,
        """syncValueUncertaintyFromGitHub();
syncMarketValueFromGitHub();
syncRosterFromGitHub();
syncLeagueFromGitHub();
""",
        """syncValueUncertaintyFromGitHub();
syncMarketValueFromGitHub();
syncTeamUtilityLineupProjections();
syncRosterFromGitHub();
syncLeagueFromGitHub();
""",
        "Team Utility projection startup",
    )
    return text


def patch_scheduled(text):
    if "Refresh Team Utility lineup projections" in text:
        return text
    text = replace_once(
        text,
        """      - name: Refresh FantasyPros-Sleeper identity crosswalk
        run: python3 scripts/projections/resolve_fantasypros_sleeper_identity.py

      - name: Dual-eligibility self-test
""",
        """      - name: Refresh FantasyPros-Sleeper identity crosswalk
        run: python3 scripts/projections/resolve_fantasypros_sleeper_identity.py

      - name: Team Utility lineup projection self-test
        run: python3 scripts/projections/build_team_utility_lineup_projections.py --selftest

      - name: Refresh Team Utility lineup projections
        run: python3 scripts/projections/build_team_utility_lineup_projections.py --write

      - name: Verify Team Utility lineup projection artifact
        run: python3 scripts/projections/build_team_utility_lineup_projections.py --check

      - name: Dual-eligibility self-test
""",
        "scheduled Team Utility projection build",
    )
    text = replace_once(
        text,
        """          git add scripts/identity_crosswalk.json
          git add scripts/artifacts/reports/identity_collision_report.md
          git add scripts/artifacts/generated/dual_eligibility_results.json
""",
        """          git add scripts/identity_crosswalk.json
          git add scripts/artifacts/reports/identity_collision_report.md
          git add scripts/artifacts/generated/team_utility_lineup_projections.json
          git add scripts/artifacts/reports/team_utility_lineup_projection_report.md
          git add scripts/artifacts/generated/dual_eligibility_results.json
""",
        "scheduled Team Utility artifact staging",
    )
    return text


def patch_regression(text):
    if "check_team_utility_projection_lineup_invariants" in text:
        return text
    fn = r'''
def check_team_utility_projection_lineup_invariants():
    builder = REPO_ROOT / "scripts" / "projections" / "build_team_utility_lineup_projections.py"
    subprocess.run([sys.executable, str(builder), "--check"], cwd=REPO_ROOT, check=True)

    text = INDEX.read_text(encoding="utf-8")
    required = (
        "TEAM_UTILITY_PROJECTION_LINEUP_V1",
        "syncTeamUtilityLineupProjections();",
        "teamUtilityProjectionByKey",
        "tuLineupCompare",
        "MY_ROSTER_SLOT_BY_KEY",
        "starterEligible: slot !== 'taxi' && slot !== 'reserve_ir'",
        "preSlotByKey = MY_ROSTER_SLOT_BY_KEY",
        "sleeper_id:",
    )
    for token in required:
        assert token in text, f"missing Team Utility projection-lineup invariant: {token}"
    assert "const TU_BENCH_WEIGHT = 0.15;" in text, "starter-objective release changed TU_BENCH_WEIGHT"
    print("PASS Team Utility projection-lineup invariants: artifact current, projection objective wired, taxi/IR guarded, bench weight unchanged")
'''
    text = replace_once(text, "def check_index_js_syntax():\n", fn + "\n\ndef check_index_js_syntax():\n", "regression function")
    text = replace_once(
        text,
        """        check_deployed_idp_v1_invariants,
        check_free_agent_board_parity,
        check_index_js_syntax,
""",
        """        check_deployed_idp_v1_invariants,
        check_free_agent_board_parity,
        check_team_utility_projection_lineup_invariants,
        check_index_js_syntax,
""",
        "regression registration",
    )
    return text


def js_syntax(index_text):
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", index_text, re.S | re.I)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write("\n".join(scripts))
        path = Path(f.name)
    try:
        subprocess.run(["node", "--check", str(path)], check=True, capture_output=True, text=True)
    finally:
        path.unlink(missing_ok=True)


def build():
    old_index = INDEX.read_text(encoding="utf-8")
    old_sched = SCHEDULED.read_text(encoding="utf-8")
    old_reg = REGRESSION.read_text(encoding="utf-8")
    new_index = patch_index(old_index)
    new_sched = patch_scheduled(old_sched)
    new_reg = patch_regression(old_reg)

    compile(new_reg, str(REGRESSION), "exec")
    js_syntax(new_index)

    before = re.search(r"const TU_BENCH_WEIGHT = ([^;]+);", old_index)
    after = re.search(r"const TU_BENCH_WEIGHT = ([^;]+);", new_index)
    if not before or not after or before.group(1) != after.group(1):
        raise RuntimeError("TU_BENCH_WEIGHT changed unexpectedly")

    for token in (MARKER, "tuLineupCompare", "MY_ROSTER_SLOT_BY_KEY", "syncTeamUtilityLineupProjections();"):
        if token not in new_index:
            raise RuntimeError(f"generated index missing {token}")
    if "Refresh Team Utility lineup projections" not in new_sched:
        raise RuntimeError("scheduled refresh missing Team Utility builder")
    if "check_team_utility_projection_lineup_invariants" not in new_reg:
        raise RuntimeError("regression suite missing Team Utility check")
    return new_index, new_sched, new_reg


def selftest():
    build()
    print("PASS Team Utility production patch dry run")
    print("PASS generated index.html JavaScript syntax")
    print("PASS generated regression Python syntax")
    print("PASS TU_BENCH_WEIGHT unchanged")


def apply():
    new_index, new_sched, new_reg = build()
    INDEX.write_text(new_index, encoding="utf-8")
    SCHEDULED.write_text(new_sched, encoding="utf-8")
    REGRESSION.write_text(new_reg, encoding="utf-8")
    print("Applied TEAM_UTILITY_PROJECTION_LINEUP_V1")


def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = p.parse_args()
    selftest() if args.selftest else apply()


if __name__ == "__main__":
    main()
