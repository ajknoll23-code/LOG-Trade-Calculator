#!/usr/bin/env python3
"""Build and deploy Free Agent Utility V1 derived priority ranks.

Production policy frozen by Free Agent Utility V1 Phases 1-4:
* exact current data-backed free agents only
* cohort-relative 4for4-vs-LOG delta transport: 15%
* absolute score-shift cap: +/- 0.040
* unmatched player score: exact existing LOG percentile
* ALL section remains current LOG value order
* position sections may sort by derived priority rank
* persisted player rows contain only player_id, pos, priority_rank

Raw/private 4for4 rows never enter the repository.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
PHASE1 = ROOT / "research" / "free-agent-utility-v1" / "free_agent_utility_v1_phase1.py"
PHASE4 = ROOT / "research" / "free-agent-utility-v1" / "phase4_production_candidate_shadow_summary.json"
FREE_AGENTS = ROOT / "data" / "free_agents.json"
BOARD = ROOT / "free-agent-board.html"
OUT = ROOT / "data" / "free_agent_utility_v1.json"

TRACKED = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
TRANSPORT_STRENGTH = 0.15
SHIFT_CAP = 0.04
POLICY_ID = "phase3-selected-15pct-cap040"

EXPECTED_PHASE4_BLOB = "2492711ce73eb0203025a5fe20c2a5b88a5887c1"
EXPECTED_PHASE4_FREE_AGENTS_BLOB = "2a007c0b2febd47cb29543fbe191959c8234f0dd"
EXPECTED_ARTIFACT_SHA_PHASE4 = "ca0445c3f6826aa28d76846c8a5904c7f5ec406ead6db62da6f9849eb7ebb3a5"

BOARD_MARKER = "FREE_AGENT_UTILITY_V1_BOARD_INTEGRATION"


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def load_phase1():
    spec = importlib.util.spec_from_file_location("fa_utility_v1_prod_core", PHASE1)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to import frozen Free Agent Utility V1 Phase 1 helper")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def canonical_sha(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def validate_phase4_contract():
    if git_blob_sha(PHASE4) != EXPECTED_PHASE4_BLOB:
        raise RuntimeError("frozen Phase 4 production-candidate summary drifted")
    d = json.loads(PHASE4.read_text(encoding="utf-8"))
    if d.get("status") != "PASS_PHASE4_EXACT_PRODUCTION_CANDIDATE_SHADOW":
        raise RuntimeError("Phase 4 is not green")
    p = d.get("selected_policy") or {}
    if p.get("transport_strength") != TRANSPORT_STRENGTH:
        raise RuntimeError("Phase 4 transport strength drifted")
    if p.get("absolute_score_shift_cap") != SHIFT_CAP:
        raise RuntimeError("Phase 4 cap drifted")
    if p.get("all_section_policy") != "existing_log_value_order_unchanged":
        raise RuntimeError("Phase 4 ALL-section policy drifted")
    return d


def build_artifact(offense: Path, dl: Path, lb: Path, db: Path) -> dict:
    phase1 = load_phase1()
    phase4 = validate_phase4_contract()

    current, _runtime_meta = phase1.current_board_rows()
    data_backed = [r for r in current if r["has_real_data"]]

    provider = (
        phase1.read_offense(offense)
        + phase1.read_idp(dl, "DL")
        + phase1.read_idp(lb, "LB")
        + phase1.read_idp(db, "DB")
    )
    provider_idx = phase1.index_provider(provider)

    by_pos = defaultdict(list)
    for r in data_backed:
        by_pos[r["pos"]].append(r)

    players = []
    total_matched = 0
    total_capped = 0
    total_move3 = 0
    total_move5 = 0

    for pos in TRACKED:
        cohort = by_pos[pos]
        current_values = {r["sleeper_id"]: float(r["value"]) for r in cohort}
        full_log_pct = phase1.midrank_percentiles(current_values)

        matched = []
        provider_points = {}
        for r in cohort:
            cands = provider_idx.get((r["norm_name"], pos, r["team"]), [])
            if len(cands) == 1:
                matched.append(r)
                provider_points[r["sleeper_id"]] = float(cands[0]["points"])
            elif len(cands) > 1:
                raise RuntimeError(
                    f"ambiguous private-provider identity: {r['name']} {pos} {r['team']}"
                )

        matched_values = {r["sleeper_id"]: float(r["value"]) for r in matched}
        matched_log_pct = phase1.midrank_percentiles(matched_values)
        matched_f4_pct = phase1.midrank_percentiles(provider_points)
        deltas = {
            sid: matched_f4_pct[sid] - matched_log_pct[sid]
            for sid in matched_log_pct
        }
        if deltas and abs(statistics.fmean(deltas.values())) > 1e-12:
            raise RuntimeError(f"{pos}: matched-cohort delta lost mean-zero property")

        candidate_scores = {}
        capped = 0
        for r in cohort:
            sid = r["sleeper_id"]
            base = full_log_pct[sid]
            if sid not in deltas:
                candidate_scores[sid] = base
                continue
            raw_shift = TRANSPORT_STRENGTH * deltas[sid]
            shift = clamp(raw_shift, -SHIFT_CAP, SHIFT_CAP)
            if abs(raw_shift - shift) > 1e-12:
                capped += 1
            candidate_scores[sid] = clamp(base + shift, 0.0, 1.0)

        current_rank = phase1.ranks_desc(current_values)
        priority_rank = phase1.ranks_desc(candidate_scores)
        moves = [current_rank[sid] - priority_rank[sid] for sid in deltas]

        for r in cohort:
            players.append({
                "player_id": r["sleeper_id"],
                "pos": pos,
                "priority_rank": int(priority_rank[r["sleeper_id"]]),
            })

        total_matched += len(deltas)
        total_capped += capped
        total_move3 += sum(abs(x) >= 3 for x in moves)
        total_move5 += sum(abs(x) >= 5 for x in moves)

    players.sort(key=lambda r: (r["pos"], r["priority_rank"], r["player_id"]))

    free_doc = json.loads(FREE_AGENTS.read_text(encoding="utf-8"))
    artifact = {
        "schema_version": 1,
        "policy_id": POLICY_ID,
        "source": {
            "league_id": free_doc.get("league_id"),
            "free_agents_synced_at": free_doc.get("synced_at"),
            "free_agents_count": free_doc.get("count"),
        },
        "scope": "data_backed_free_agents_only",
        "all_section_policy": "existing_log_value_order_unchanged",
        "position_section_policy": "priority_rank_ascending",
        "players": players,
    }

    # Exact Phase 4 reproduction is a historical-source proof, not a rule
    # for every later refresh. The original guard used "408 data-backed free
    # agents" as a proxy for the frozen Phase 4 snapshot. That cardinality can
    # legitimately recur after free-agent membership/sync data change.
    #
    # Run the byte-for-byte Phase 4 proof only when the public free-agent
    # source is the exact historical Phase 4 source. The private 4for4 inputs
    # are independently SHA-pinned by the frozen Phase 1 reader.
    current_free_agents_blob = git_blob_sha(FREE_AGENTS)
    if current_free_agents_blob == EXPECTED_PHASE4_FREE_AGENTS_BLOB:
        if phase4["source_integrity"].get("data_backed_free_agent_count") != 408:
            raise RuntimeError("frozen Phase 4 data-backed cohort count drifted")
        if len(players) != 408:
            raise RuntimeError(
                "production builder does not reproduce frozen Phase 4 cohort size"
            )

        phase4_shape = {
            "schema_version": 1,
            "study_id": "free-agent-utility-v1",
            "policy_id": POLICY_ID,
            "scope": "data_backed_free_agents_only",
            "all_section_policy": "existing_log_value_order_unchanged",
            "position_section_policy": "priority_rank_ascending",
            "players": players,
        }
        if canonical_sha(phase4_shape) != EXPECTED_ARTIFACT_SHA_PHASE4:
            raise RuntimeError("production builder does not reproduce frozen Phase 4 artifact")
        if (total_matched, total_capped, total_move3, total_move5) != (304, 118, 72, 11):
            raise RuntimeError(
                "production builder failed exact Phase 4 diagnostics: "
                f"{(total_matched, total_capped, total_move3, total_move5)}"
            )

    validate_artifact(artifact, free_doc)
    return artifact


def validate_artifact(artifact: dict, free_doc: dict | None = None):
    if artifact.get("schema_version") != 1:
        raise RuntimeError("utility artifact schema_version must be 1")
    if artifact.get("policy_id") != POLICY_ID:
        raise RuntimeError("utility artifact policy_id drifted")
    if artifact.get("all_section_policy") != "existing_log_value_order_unchanged":
        raise RuntimeError("ALL section policy drifted")
    if artifact.get("position_section_policy") != "priority_rank_ascending":
        raise RuntimeError("position section policy drifted")

    source = artifact.get("source")
    if not isinstance(source, dict):
        raise RuntimeError("utility artifact missing source contract")
    for k in ("league_id", "free_agents_synced_at", "free_agents_count"):
        if k not in source:
            raise RuntimeError(f"utility artifact source missing {k}")

    rows = artifact.get("players")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("utility artifact players must be nonempty")

    seen = set()
    by_pos = defaultdict(list)
    for row in rows:
        if set(row) != {"player_id", "pos", "priority_rank"}:
            raise RuntimeError(f"unexpected utility player schema: {sorted(row)}")
        sid = str(row["player_id"])
        pos = str(row["pos"])
        rank = row["priority_rank"]
        if not sid or pos not in TRACKED or not isinstance(rank, int) or rank < 1:
            raise RuntimeError(f"invalid utility player row: {row}")
        if sid in seen:
            raise RuntimeError(f"duplicate utility player_id: {sid}")
        seen.add(sid)
        by_pos[pos].append(rank)

    for pos in TRACKED:
        ranks = sorted(by_pos[pos])
        if ranks != list(range(1, len(ranks) + 1)):
            raise RuntimeError(f"{pos}: utility ranks are not contiguous")

    if free_doc is not None:
        if source["league_id"] != free_doc.get("league_id"):
            raise RuntimeError("utility/free-agent league_id mismatch")
        if source["free_agents_synced_at"] != free_doc.get("synced_at"):
            raise RuntimeError("utility/free-agent synced_at mismatch")
        if source["free_agents_count"] != free_doc.get("count"):
            raise RuntimeError("utility/free-agent count mismatch")


def patch_board_text(text: str) -> str:
    if BOARD_MARKER in text:
        return text

    anchor1 = """let FREE_AGENTS = [];
let state = { dataOnly: true };

const FREE_AGENTS_URL = 'https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/main/data/free_agents.json?t=' + Date.now();
"""
    repl1 = """let FREE_AGENTS = [];
let FREE_AGENT_UTILITY = new Map();
let FREE_AGENT_UTILITY_ACTIVE = false;
let state = { dataOnly: true };

/* FREE_AGENT_UTILITY_V1_BOARD_INTEGRATION
   Derived waiver-priority ranks are position-local only. They never replace
   LOG/Fundamental Value and never control the ALL section. The artifact is
   fail-closed: stale, missing, malformed, or incomplete data falls back to
   the existing LOG order automatically. */
const FREE_AGENTS_URL = 'https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/main/data/free_agents.json?t=' + Date.now();
const FREE_AGENT_UTILITY_URL = 'https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/main/data/free_agent_utility_v1.json?t=' + Date.now();
"""
    if anchor1 not in text:
        raise RuntimeError("board integration anchor 1 not found")
    text = text.replace(anchor1, repl1, 1)

    anchor2 = """    const data = await resp.json();
    const raw = data.free_agents || [];
"""
    repl2 = """    const data = await resp.json();
    const raw = data.free_agents || [];

    let utilityDoc = null;
    try {
      const utilityResp = await fetch(FREE_AGENT_UTILITY_URL);
      if(utilityResp.ok) utilityDoc = await utilityResp.json();
    } catch(_) {
      utilityDoc = null;
    }

    FREE_AGENT_UTILITY = new Map();
    FREE_AGENT_UTILITY_ACTIVE = !!(
      utilityDoc &&
      utilityDoc.schema_version === 1 &&
      utilityDoc.policy_id === 'phase3-selected-15pct-cap040' &&
      utilityDoc.source &&
      utilityDoc.source.league_id === data.league_id &&
      utilityDoc.source.free_agents_synced_at === data.synced_at &&
      utilityDoc.source.free_agents_count === data.count &&
      Array.isArray(utilityDoc.players)
    );

    if(FREE_AGENT_UTILITY_ACTIVE){
      let valid = true;
      for(const row of utilityDoc.players){
        const sid = String(row && row.player_id || '');
        const pos = String(row && row.pos || '');
        const rank = row && row.priority_rank;
        const mapKey = sid + '|' + pos;
        if(!sid || !['QB','RB','WR','TE','DL','LB','DB'].includes(pos) ||
           !Number.isInteger(rank) || rank < 1 || FREE_AGENT_UTILITY.has(mapKey)){
          valid = false;
          break;
        }
        FREE_AGENT_UTILITY.set(mapKey, rank);
      }
      if(!valid){
        FREE_AGENT_UTILITY.clear();
        FREE_AGENT_UTILITY_ACTIVE = false;
      }
    }
"""
    if anchor2 not in text:
        raise RuntimeError("board integration anchor 2 not found")
    text = text.replace(anchor2, repl2, 1)

    anchor3 = """      const val = playerValue(pos, age, role, valueKey);
      return {
        key, name: fa.name, pos, age, role, val, hasRealData,
        team: fa.team, injuryStatus: fa.injury_status,
      };
    }).filter(fa => fa.pos && fa.val > 0);

    const dataCount = FREE_AGENTS.filter(fa => fa.hasRealData).length;
"""
    repl3 = """      const val = playerValue(pos, age, role, valueKey);
      const playerId = String(fa.player_id || '');
      const utilityKey = playerId + '|' + pos;
      const utilityRank = (
        FREE_AGENT_UTILITY_ACTIVE &&
        hasRealData &&
        FREE_AGENT_UTILITY.has(utilityKey)
      ) ? FREE_AGENT_UTILITY.get(utilityKey) : null;
      return {
        key, playerId, name: fa.name, pos, age, role, val, hasRealData,
        utilityRank, team: fa.team, injuryStatus: fa.injury_status,
      };
    }).filter(fa => fa.pos && fa.val > 0);

    const dataCount = FREE_AGENTS.filter(fa => fa.hasRealData).length;
    const utilityCoveredCount = FREE_AGENTS.filter(
      fa => fa.hasRealData && Number.isInteger(fa.utilityRank)
    ).length;
    if(FREE_AGENT_UTILITY_ACTIVE && utilityCoveredCount !== dataCount){
      FREE_AGENT_UTILITY_ACTIVE = false;
      FREE_AGENT_UTILITY.clear();
      FREE_AGENTS.forEach(fa => { fa.utilityRank = null; });
    }
"""
    if anchor3 not in text:
        raise RuntimeError("board integration anchor 3 not found")
    text = text.replace(anchor3, repl3, 1)

    anchor4 = """      <div class="row ${fa.hasRealData ? 'has-data' : ''}">
"""
    repl4 = """      <div class="row ${fa.hasRealData ? 'has-data' : ''}" data-player-id="${escapeHtml(fa.playerId)}">
"""
    if anchor4 not in text:
        raise RuntimeError("board integration anchor 4 not found")
    text = text.replace(anchor4, repl4, 1)

    anchor5 = """    list.sort((a,b) => (b.hasRealData - a.hasRealData) || (b.val - a.val));

    const rows = buildRows(list);
"""
    repl5 = """    if(pos === 'ALL'){
      list.sort((a,b) => (b.hasRealData - a.hasRealData) || (b.val - a.val));
    } else {
      list.sort((a,b) =>
        (b.hasRealData - a.hasRealData) ||
        (
          a.hasRealData && b.hasRealData
            ? (
                (Number.isInteger(a.utilityRank) ? a.utilityRank : Number.MAX_SAFE_INTEGER) -
                (Number.isInteger(b.utilityRank) ? b.utilityRank : Number.MAX_SAFE_INTEGER)
              ) || (b.val - a.val)
            : (b.val - a.val)
        )
      );
    }

    const rows = buildRows(list);
"""
    if anchor5 not in text:
        raise RuntimeError("board integration anchor 5 not found")
    text = text.replace(anchor5, repl5, 1)

    return text


def run_selftest():
    sample = {
        "schema_version": 1,
        "policy_id": POLICY_ID,
        "source": {
            "league_id": "x",
            "free_agents_synced_at": 1,
            "free_agents_count": 2,
        },
        "scope": "data_backed_free_agents_only",
        "all_section_policy": "existing_log_value_order_unchanged",
        "position_section_policy": "priority_rank_ascending",
        "players": [
            {"player_id": "1", "pos": "WR", "priority_rank": 1},
            {"player_id": "2", "pos": "WR", "priority_rank": 2},
        ],
    }
    validate_artifact(sample)
    assert clamp(0.1, -SHIFT_CAP, SHIFT_CAP) == SHIFT_CAP
    assert clamp(-0.1, -SHIFT_CAP, SHIFT_CAP) == -SHIFT_CAP

    # Historical reproduction must be bound to the exact source snapshot,
    # never to a row-count coincidence.
    assert EXPECTED_PHASE4_FREE_AGENTS_BLOB == (
        "2a007c0b2febd47cb29543fbe191959c8234f0dd"
    )
    assert EXPECTED_PHASE4_FREE_AGENTS_BLOB != (
        "baca3c506f90e4373639932ebdb15cb5f58f141c"
    )

    print("build_free_agent_utility_v1 self-test passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--offense", type=Path)
    parser.add_argument("--dl", type=Path)
    parser.add_argument("--lb", type=Path)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--write-artifact", action="store_true")
    parser.add_argument("--patch-board", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return 0

    if args.check:
        d = json.loads(OUT.read_text(encoding="utf-8"))
        free_doc = json.loads(FREE_AGENTS.read_text(encoding="utf-8"))
        validate_artifact(d, free_doc)
        if BOARD_MARKER not in BOARD.read_text(encoding="utf-8"):
            raise RuntimeError("free-agent board is missing Utility V1 integration")
        print("PASS: deployed Free Agent Utility V1 artifact is current and board integration exists.")
        return 0

    if args.write_artifact:
        if any(p is None for p in (args.offense, args.dl, args.lb, args.db)):
            parser.error("--offense, --dl, --lb and --db are required with --write-artifact")
        artifact = build_artifact(args.offense, args.dl, args.lb, args.db)
        OUT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"WROTE {OUT.relative_to(ROOT)} with {len(artifact['players'])} rows")

    if args.patch_board:
        old = BOARD.read_text(encoding="utf-8")
        new = patch_board_text(old)
        BOARD.write_text(new, encoding="utf-8")
        if patch_board_text(new) != new:
            raise RuntimeError("board patch is not idempotent")
        print("PATCHED free-agent-board.html for Free Agent Utility V1")

    if not args.write_artifact and not args.patch_board:
        parser.error("choose --selftest, --check, --write-artifact and/or --patch-board")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
