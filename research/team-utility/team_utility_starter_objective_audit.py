#!/usr/bin/env python3
"""Audit Team Utility's starter-selection objective.

This is research-only. It does NOT change production. V2 mirrors the live
mergeLeagueRosters() valuation universe before evaluating lineups.

Questions:
1. Does the current Team Utility objective (Fundamental Value) choose the same
   legal starting lineup as 2026 Sleeper projected fantasy scoring?
2. How much projected scoring does a Fundamental-selected lineup leave on the
   table, team by team?
3. Does the current roster scope (starters + bench + taxi) allow taxi players
   to be treated as immediate starters?

Inputs are already committed in the repo:
- index.html
- data/league_rosters.json
- scripts/sleeper_2026_projections.json
- scripts/validation/snapshot_values.py

Outputs:
- research/team-utility/team_utility_starter_objective_audit.json
- research/team-utility/team_utility_starter_objective_audit.md
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
import math
from pathlib import Path
import re
import statistics
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX = REPO_ROOT / "index.html"
ROSTERS = REPO_ROOT / "data" / "league_rosters.json"
PROJECTIONS = REPO_ROOT / "scripts" / "sleeper_2026_projections.json"
PLAYER_POSITIONS = REPO_ROOT / "scripts" / "artifacts" / "generated" / "player_positions.json"
OUT_DIR = REPO_ROOT / "research" / "team-utility"
OUT_JSON = OUT_DIR / "team_utility_starter_objective_audit.json"
OUT_MD = OUT_DIR / "team_utility_starter_objective_audit.md"

sys.path.insert(0, str(REPO_ROOT / "scripts" / "validation"))
import snapshot_values  # noqa: E402

DEDICATED = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "K": 1,
    "DL": 2,
    "LB": 2,
    "DB": 2,
}
FLEXES = [
    ("FLEX", {"RB", "WR", "TE"}, 1),
    ("SUPER_FLEX", {"QB", "RB", "WR", "TE"}, 1),
    ("IDP_FLEX", {"DL", "LB", "DB"}, 2),
]
EXPECTED_STARTERS = sum(DEDICATED.values()) + sum(c for _, _, c in FLEXES)
CURRENT_SCOPE_SLOTS = ("starters", "bench", "taxi")
ACTIVE_SCOPE_SLOTS = ("starters", "bench")


def normalize_name(value: str) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"[.'\u2019-]", "", s)
    return re.sub(r"\s+", " ", s)


SLOT_DEFAULTS = {
    "starters": "Starter",
    "bench": "Rotational",
    "taxi": "Speculative",
    "reserve_ir": "Depth",
}


def parse_aliases(index_text: str) -> tuple[dict[str, str], dict[str, str]]:
    """Parse production ALIASES and build the same reverse lookup."""
    body = snapshot_values.extract_object_body(index_text, "ALIASES")
    pairs = re.findall(r"'([^']+)'\s*:\s*'([^']+)'", body)
    aliases = {alias: canonical for alias, canonical in pairs}
    return aliases, {canonical: alias for alias, canonical in pairs}


def resolve_existing_key(
    key: str,
    player_db: dict,
    aliases: dict[str, str],
    aliases_reverse: dict[str, str],
) -> str:
    """Python mirror of production resolveExistingKey()."""
    if key in player_db:
        return key
    alt = aliases.get(key) or aliases_reverse.get(key)
    if alt and alt in player_db:
        return alt
    return key


def canonical_position(raw: dict, key: str, position_map: dict[str, str]) -> str | None:
    """Resolve the same canonical position used by the live roster universe."""
    raw_key = normalize_name(raw.get("name", ""))
    pos = position_map.get(key) or position_map.get(raw_key)
    if pos:
        return pos

    def collapse(pos_value):
        if pos_value in ("DE", "DT"):
            return "DL"
        if pos_value in ("OLB", "ILB"):
            return "LB"
        if pos_value in ("CB", "S", "SS", "FS"):
            return "DB"
        if pos_value in ("QB", "RB", "WR", "TE", "K", "DL", "LB", "DB"):
            return pos_value
        return None

    pos = collapse(raw.get("position"))
    if pos:
        return pos
    for value in raw.get("fantasy_positions") or []:
        pos = collapse(value)
        if pos:
            return pos
    return None


def merge_live_league_into_cfg(cfg: dict, roster_doc: dict) -> dict:
    """Mirror valuation-relevant behavior of production mergeLeagueRosters()."""
    index_text = INDEX.read_text(encoding="utf-8")
    aliases, aliases_reverse = parse_aliases(index_text)
    position_map = json.loads(PLAYER_POSITIONS.read_text(encoding="utf-8"))

    merged = dict(cfg)
    merged["player_db"] = {key: dict(info) for key, info in cfg["player_db"].items()}
    merged["rb_birth_date_data"] = dict(cfg["rb_birth_date_data"])
    merged["aliases"] = aliases
    merged["aliases_reverse"] = aliases_reverse

    added_keys: set[str] = set()
    refreshed_keys: set[str] = set()
    unresolved_positions: list[dict] = []

    for roster in roster_doc.get("rosters", []):
        for slot in ("starters", "bench", "taxi", "reserve_ir"):
            for raw in roster.get(slot, []) or []:
                raw_key = normalize_name(raw.get("name", ""))
                key = resolve_existing_key(
                    raw_key,
                    merged["player_db"],
                    aliases,
                    aliases_reverse,
                )
                existing = merged["player_db"].get(key)

                if existing and existing.get("pos"):
                    pos = existing["pos"]
                else:
                    pos = canonical_position(raw, key, position_map)
                if not pos:
                    unresolved_positions.append({
                        "roster_id": roster.get("roster_id"),
                        "player_id": str(raw.get("player_id") or ""),
                        "player": raw.get("name"),
                        "reason": "production-parity live merge could not resolve position",
                    })
                    continue

                raw_age = raw.get("age")
                if isinstance(raw_age, (int, float)):
                    age = int(raw_age)
                elif existing and existing.get("age") is not None:
                    age = int(existing["age"])
                else:
                    age = 24

                role = (
                    existing["role"]
                    if existing and existing.get("role")
                    else SLOT_DEFAULTS[slot]
                )

                if existing is None:
                    added_keys.add(key)
                else:
                    refreshed_keys.add(key)

                merged["player_db"][key] = {"pos": pos, "age": age, "role": role}

                birth_date = raw.get("birth_date")
                if pos == "RB" and isinstance(birth_date, str) and birth_date:
                    merged["rb_birth_date_data"][normalize_name(key)] = birth_date

    merged["live_merge_stats"] = {
        "added_player_db_rows": len(added_keys),
        "refreshed_player_db_rows": len(refreshed_keys),
        "unresolved_positions": unresolved_positions,
    }
    return merged


@dataclass(frozen=True)
class Player:
    player_id: str
    key: str
    name: str
    pos: str
    slot: str
    fundamental: float
    projection: float | None

    def objective(self, field: str) -> float:
        if field == "fundamental":
            return float(self.fundamental)
        if field == "projection":
            # The current Sleeper projection pipeline does not score kicker
            # categories. K only competes for the dedicated K slot, so use
            # Fundamental Value as a neutral tie-breaker there; this keeps the
            # audit focused on positions with real projected-scoring coverage.
            if self.pos == "K":
                return float(self.fundamental)
            return float(self.projection) if self.projection is not None else -1e18
        raise ValueError(field)


def optimize_lineup(players: list[Player], objective: str) -> dict:
    """Mirror the deployed nested-eligibility greedy optimizer.

    Dedicated position slots are filled first. Then the more restrictive FLEX
    is filled before SUPER_FLEX, followed by the two identical IDP_FLEX slots.
    For this league's nested eligibility, this is optimal.
    """
    remaining = list(players)
    starters: list[dict] = []

    def pop_best(eligible: set[str], label: str, count: int) -> None:
        nonlocal remaining
        for _ in range(count):
            candidates = [p for p in remaining if p.pos in eligible]
            if not candidates:
                break
            best = max(
                candidates,
                key=lambda p: (p.objective(objective), p.fundamental, p.key),
            )
            remaining.remove(best)
            starters.append({"slot": label, "player": best})

    for pos, count in DEDICATED.items():
        pop_best({pos}, pos, count)

    for label, eligible, count in FLEXES:
        pop_best(eligible, label, count)

    return {"starters": starters, "bench": remaining}


def lineup_ids(result: dict) -> set[str]:
    return {row["player"].player_id for row in result["starters"]}


def lineup_projection(result: dict) -> tuple[float, int]:
    total = 0.0
    missing = 0
    for row in result["starters"]:
        p = row["player"]
        if p.pos == "K":
            continue
        proj = p.projection
        if proj is None:
            missing += 1
        else:
            total += proj
    return total, missing


def serialize_lineup(result: dict) -> list[dict]:
    out = []
    for row in result["starters"]:
        p = row["player"]
        out.append(
            {
                "lineup_slot": row["slot"],
                "player_id": p.player_id,
                "player": p.name,
                "pos": p.pos,
                "roster_slot": p.slot,
                "fundamental": round(p.fundamental, 1),
                "sleeper_2026_proj_total": (
                    round(p.projection, 1) if p.projection is not None else None
                ),
            }
        )
    return out


def load_inputs() -> tuple[dict, dict[str, float], dict]:
    for path in (INDEX, ROSTERS, PROJECTIONS, PLAYER_POSITIONS):
        if not path.exists():
            raise RuntimeError(f"missing required input: {path.relative_to(REPO_ROOT)}")

    roster_doc = json.loads(ROSTERS.read_text(encoding="utf-8"))
    base_cfg = snapshot_values.load_from_html(INDEX)
    cfg = merge_live_league_into_cfg(base_cfg, roster_doc)

    projection_rows = json.loads(PROJECTIONS.read_text(encoding="utf-8"))
    projection_by_id = {
        str(r["sleeper_id"]): float(r["sleeper_2026_proj_total"])
        for r in projection_rows
        if r.get("sleeper_id") is not None
        and isinstance(r.get("sleeper_2026_proj_total"), (int, float))
        and r["sleeper_2026_proj_total"] > 0
    }

    return cfg, projection_by_id, roster_doc


def build_roster_players(
    roster: dict,
    cfg: dict,
    fundamental_by_key: dict[str, float],
    projection_by_id: dict[str, float],
    scope_slots: tuple[str, ...],
) -> tuple[list[Player], list[dict]]:
    player_db = cfg["player_db"]
    players = []
    unresolved = []

    for slot in scope_slots:
        for raw in roster.get(slot, []) or []:
            pid = str(raw.get("player_id") or "")
            raw_key = normalize_name(raw.get("name", ""))
            key = resolve_existing_key(
                raw_key,
                player_db,
                cfg.get("aliases", {}),
                cfg.get("aliases_reverse", {}),
            )
            info = player_db.get(key)
            if not info:
                unresolved.append(
                    {
                        "player_id": pid,
                        "player": raw.get("name"),
                        "reason": "normalized name missing from PLAYER_DB",
                    }
                )
                continue
            fundamental_row = fundamental_by_key.get(key)
            fundamental = (
                fundamental_row.get("value")
                if isinstance(fundamental_row, dict)
                else fundamental_row
            )
            if fundamental is None:
                unresolved.append(
                    {
                        "player_id": pid,
                        "player": raw.get("name"),
                        "reason": "no computable Fundamental Value",
                    }
                )
                continue
            players.append(
                Player(
                    player_id=pid,
                    key=key,
                    name=raw.get("name") or key,
                    pos=info["pos"],
                    slot=slot,
                    fundamental=float(fundamental),
                    projection=projection_by_id.get(pid),
                )
            )
    return players, unresolved


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def audit() -> dict:
    cfg, projection_by_id, roster_doc = load_inputs()
    fundamental_by_key = snapshot_values.compute_all_values(cfg)

    team_rows = []
    all_unresolved = []
    complete_losses = []
    complete_efficiencies = []
    overlap_counts = []
    teams_changed = 0
    taxi_fv_starter_count = 0
    taxi_proj_starter_count = 0

    for roster in roster_doc.get("rosters", []):
        current_players, unresolved = build_roster_players(
            roster,
            cfg,
            fundamental_by_key,
            projection_by_id,
            CURRENT_SCOPE_SLOTS,
        )
        active_players, active_unresolved = build_roster_players(
            roster,
            cfg,
            fundamental_by_key,
            projection_by_id,
            ACTIVE_SCOPE_SLOTS,
        )
        all_unresolved.extend(
            [{"roster_id": roster.get("roster_id"), **x} for x in unresolved]
        )

        fv = optimize_lineup(current_players, "fundamental")
        proj = optimize_lineup(current_players, "projection")
        active_proj = optimize_lineup(active_players, "projection")

        fv_ids = lineup_ids(fv)
        proj_ids = lineup_ids(proj)
        active_proj_ids = lineup_ids(active_proj)
        overlap = len(fv_ids & proj_ids)
        overlap_counts.append(overlap)
        if fv_ids != proj_ids:
            teams_changed += 1

        fv_proj_total, fv_missing = lineup_projection(fv)
        optimal_proj_total, optimal_missing = lineup_projection(proj)
        active_optimal_total, active_optimal_missing = lineup_projection(active_proj)

        projection_complete = (
            len(fv["starters"]) == EXPECTED_STARTERS
            and len(proj["starters"]) == EXPECTED_STARTERS
            and fv_missing == 0
            and optimal_missing == 0
        )

        loss = None
        efficiency = None
        if projection_complete and optimal_proj_total > 0:
            loss = optimal_proj_total - fv_proj_total
            efficiency = 100.0 * fv_proj_total / optimal_proj_total
            complete_losses.append(loss)
            complete_efficiencies.append(efficiency)

        fv_taxi = [
            row["player"] for row in fv["starters"] if row["player"].slot == "taxi"
        ]
        proj_taxi = [
            row["player"] for row in proj["starters"] if row["player"].slot == "taxi"
        ]
        taxi_fv_starter_count += len(fv_taxi)
        taxi_proj_starter_count += len(proj_taxi)

        projection_coverage = (
            sum(1 for p in current_players if p.projection is not None)
            / len(current_players)
            * 100.0
            if current_players
            else 0.0
        )

        proj_only = proj_ids - fv_ids
        fv_only = fv_ids - proj_ids
        by_id = {p.player_id: p for p in current_players}

        team_rows.append(
            {
                "roster_id": roster.get("roster_id"),
                "team_name": roster.get("team_name")
                or roster.get("owner_username")
                or f"Roster {roster.get('roster_id')}",
                "roster_player_count_current_scope": len(current_players),
                "projection_coverage_pct": round(projection_coverage, 1),
                "unresolved_count": len(unresolved),
                "active_scope_unresolved_count": len(active_unresolved),
                "fv_starter_count": len(fv["starters"]),
                "projection_starter_count": len(proj["starters"]),
                "starter_overlap_count": overlap,
                "starter_swap_count": len(proj_only),
                "projection_complete": projection_complete,
                "fv_selected_projected_points": round(fv_proj_total, 1),
                "projection_optimal_projected_points": round(optimal_proj_total, 1),
                "projected_points_left_on_table": (
                    round(loss, 1) if loss is not None else None
                ),
                "fv_lineup_projection_efficiency_pct": (
                    round(efficiency, 2) if efficiency is not None else None
                ),
                "fv_selected_taxi_starters": [
                    {"player_id": p.player_id, "player": p.name, "pos": p.pos}
                    for p in fv_taxi
                ],
                "projection_selected_taxi_starters": [
                    {"player_id": p.player_id, "player": p.name, "pos": p.pos}
                    for p in proj_taxi
                ],
                "projection_optimal_points_active_scope": round(active_optimal_total, 1),
                "active_scope_projection_missing_starters": active_optimal_missing,
                "taxi_scope_projected_points_delta": round(
                    optimal_proj_total - active_optimal_total, 1
                ),
                "taxi_changes_projection_optimal_lineup": proj_ids != active_proj_ids,
                "projection_wants_instead": [
                    {
                        "player_id": pid,
                        "player": by_id[pid].name,
                        "pos": by_id[pid].pos,
                        "roster_slot": by_id[pid].slot,
                        "fundamental": round(by_id[pid].fundamental, 1),
                        "projection": (
                            round(by_id[pid].projection, 1)
                            if by_id[pid].projection is not None
                            else None
                        ),
                    }
                    for pid in sorted(proj_only)
                ],
                "fundamental_wants_instead": [
                    {
                        "player_id": pid,
                        "player": by_id[pid].name,
                        "pos": by_id[pid].pos,
                        "roster_slot": by_id[pid].slot,
                        "fundamental": round(by_id[pid].fundamental, 1),
                        "projection": (
                            round(by_id[pid].projection, 1)
                            if by_id[pid].projection is not None
                            else None
                        ),
                    }
                    for pid in sorted(fv_only)
                ],
                "fundamental_selected_lineup": serialize_lineup(fv),
                "projection_selected_lineup": serialize_lineup(proj),
            }
        )

    team_rows.sort(
        key=lambda r: (
            -(r["projected_points_left_on_table"] or -1),
            r["roster_id"] or 0,
        )
    )

    aggregate = {
        "team_count": len(team_rows),
        "expected_starters_per_team": EXPECTED_STARTERS,
        "teams_with_different_lineup": teams_changed,
        "teams_with_complete_projection_comparison": len(complete_losses),
        "median_starter_overlap_count": (
            round(median(overlap_counts), 1) if overlap_counts else None
        ),
        "median_projected_points_left_on_table": (
            round(median(complete_losses), 2) if complete_losses else None
        ),
        "mean_projected_points_left_on_table": (
            round(statistics.mean(complete_losses), 2) if complete_losses else None
        ),
        "max_projected_points_left_on_table": (
            round(max(complete_losses), 2) if complete_losses else None
        ),
        "median_fv_lineup_projection_efficiency_pct": (
            round(median(complete_efficiencies), 2)
            if complete_efficiencies
            else None
        ),
        "taxi_players_selected_as_starters_by_fundamental": taxi_fv_starter_count,
        "taxi_players_selected_as_starters_by_projection": taxi_proj_starter_count,
        "teams_where_taxi_changes_projection_optimal_lineup": sum(
            1 for r in team_rows if r["taxi_changes_projection_optimal_lineup"]
        ),
        "unresolved_player_records": len(all_unresolved),
        "dynamic_player_db_rows_added": cfg.get("live_merge_stats", {}).get(
            "added_player_db_rows", 0
        ),
        "live_merge_unresolved_positions": len(
            cfg.get("live_merge_stats", {}).get("unresolved_positions", [])
        ),
    }

    return {
        "audit": "team_utility_starter_objective_audit",
        "production_changed": False,
        "current_team_utility_starter_objective": "Fundamental Value",
        "comparison_objective": "Sleeper 2026 projected fantasy points under league scoring",
        "current_scope_mirrored": "starters + bench + taxi; reserve_ir excluded",
        "aggregate": aggregate,
        "teams": team_rows,
        "unresolved": all_unresolved,
        "live_merge_unresolved_positions": cfg.get("live_merge_stats", {}).get(
            "unresolved_positions", []
        ),
    }


def render_md(result: dict) -> str:
    a = result["aggregate"]
    lines = [
        "# Team Utility Starter-Objective Audit",
        "",
        "Research-only audit. **No production values or Team Utility constants were changed.**",
        "",
        "## What this tests",
        "",
        "- Current production starter selection: **Fundamental Value**.",
        "- Comparison starter selection: **Sleeper 2026 projected fantasy points**, scored under the league's own scoring rules.",
        "- Both use the same legal 17-slot lineup structure.",
        "- Current Team Utility roster scope is mirrored as **starters + bench + taxi**; IR is excluded.",
        "",
        "## League-wide results",
        "",
        f"- Teams audited: **{a['team_count']}**",
        f"- Teams where the selected starting lineup differs: **{a['teams_with_different_lineup']} / {a['team_count']}**",
        f"- Complete projection comparisons: **{a['teams_with_complete_projection_comparison']} / {a['team_count']}**",
        f"- Median starter overlap: **{a['median_starter_overlap_count']} / {a['expected_starters_per_team']}**",
        f"- Median projected non-K points left on table by FV selection: **{a['median_projected_points_left_on_table']}** season points",
        f"- Mean projected non-K points left on table: **{a['mean_projected_points_left_on_table']}** season points",
        f"- Worst team projected non-K points left on table: **{a['max_projected_points_left_on_table']}** season points",
        f"- Median FV-lineup projection efficiency: **{a['median_fv_lineup_projection_efficiency_pct']}%**",
        f"- Taxi players selected as starters by FV objective: **{a['taxi_players_selected_as_starters_by_fundamental']}**",
        f"- Taxi players selected as starters by projection objective: **{a['taxi_players_selected_as_starters_by_projection']}**",
        f"- Teams where allowing taxi changes projection-optimal lineup: **{a['teams_where_taxi_changes_projection_optimal_lineup']}**",
        f"- Unresolved roster records after production-parity live merge: **{a['unresolved_player_records']}**",
        f"- Runtime PLAYER_DB rows added from live league sync: **{a['dynamic_player_db_rows_added']}**",
        f"- Live-merge position failures: **{a['live_merge_unresolved_positions']}**",
        "",
        "## Team detail",
        "",
        "| Team | Coverage | Overlap | Swaps | FV projected pts | Optimal projected pts | Left on table | Efficiency | Taxi changes optimum? |",
        "|---|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]

    for r in result["teams"]:
        loss = (
            f"{r['projected_points_left_on_table']:.1f}"
            if r["projected_points_left_on_table"] is not None
            else "n/a"
        )
        eff = (
            f"{r['fv_lineup_projection_efficiency_pct']:.2f}%"
            if r["fv_lineup_projection_efficiency_pct"] is not None
            else "n/a"
        )
        lines.append(
            f"| {r['team_name']} | {r['projection_coverage_pct']:.1f}% | "
            f"{r['starter_overlap_count']}/{EXPECTED_STARTERS} | "
            f"{r['starter_swap_count']} | "
            f"{r['fv_selected_projected_points']:.1f} | "
            f"{r['projection_optimal_projected_points']:.1f} | "
            f"{loss} | {eff} | "
            f"{'YES' if r['taxi_changes_projection_optimal_lineup'] else 'no'} |"
        )

    lines.extend(
        [
            "",
            "## Biggest lineup disagreements",
            "",
        ]
    )
    for r in result["teams"][:6]:
        if not r["projection_wants_instead"] and not r["fundamental_wants_instead"]:
            continue
        lines.append(f"### {r['team_name']}")
        lines.append("")
        if r["projection_wants_instead"]:
            adds = ", ".join(
                f"{p['player']} ({p['pos']}, FV {p['fundamental']:.0f}, Proj {p['projection'] if p['projection'] is not None else 'n/a'})"
                for p in r["projection_wants_instead"]
            )
            lines.append(f"- Projection objective starts instead: {adds}")
        if r["fundamental_wants_instead"]:
            subs = ", ".join(
                f"{p['player']} ({p['pos']}, FV {p['fundamental']:.0f}, Proj {p['projection'] if p['projection'] is not None else 'n/a'})"
                for p in r["fundamental_wants_instead"]
            )
            lines.append(f"- Fundamental objective starts instead: {subs}")
        lines.append("")

    lines.extend(
        [
            "## Interpretation guardrails",
            "",
            "- This audit tests the **starter-selection objective only**. It does not determine the correct bench weight.",
            "- Sleeper projections are a forward-looking scoring proxy, not ground truth.",
            "- The report does **not** change Fundamental Value. It asks only which players should count as starters inside Team Utility.",
            "- Taxi findings are reported separately because taxi eligibility is an architecture question, not a scoring-model question.",
            "",
        ]
    )
    return "\n".join(lines)


def run_selftest() -> None:
    # FLEX must be protected before SUPER_FLEX: FLEX takes the best non-QB,
    # then SF can use the QB.
    players = [
        Player("q1", "q1", "QB1", "QB", "bench", 10, 95),
        Player("q2", "q2", "QB2", "QB", "bench", 9, 85),
        Player("r1", "r1", "RB1", "RB", "bench", 10, 100),
        Player("r2", "r2", "RB2", "RB", "bench", 9, 90),
        Player("r3", "r3", "RB3", "RB", "bench", 8, 80),
        Player("w1", "w1", "WR1", "WR", "bench", 10, 70),
        Player("w2", "w2", "WR2", "WR", "bench", 9, 60),
        Player("w3", "w3", "WR3", "WR", "bench", 8, 50),
        Player("t1", "t1", "TE1", "TE", "bench", 10, 40),
        Player("t2", "t2", "TE2", "TE", "bench", 9, 30),
        Player("k1", "k1", "K1", "K", "bench", 10, 10),
        Player("d1", "d1", "DL1", "DL", "bench", 10, 50),
        Player("d2", "d2", "DL2", "DL", "bench", 9, 45),
        Player("d3", "d3", "DL3", "DL", "bench", 8, 40),
        Player("d4", "d4", "DL4", "DL", "bench", 7, 35),
        Player("l1", "l1", "LB1", "LB", "bench", 10, 60),
        Player("l2", "l2", "LB2", "LB", "bench", 9, 55),
        Player("l3", "l3", "LB3", "LB", "bench", 8, 50),
        Player("b1", "b1", "DB1", "DB", "bench", 10, 30),
        Player("b2", "b2", "DB2", "DB", "bench", 9, 25),
        Player("b3", "b3", "DB3", "DB", "bench", 8, 20),
    ]
    result = optimize_lineup(players, "projection")
    assert len(result["starters"]) == EXPECTED_STARTERS
    slots = {row["slot"]: row["player"].player_id for row in result["starters"]}
    assert slots["FLEX"] == "r3"
    assert slots["SUPER_FLEX"] == "q2"

    # Objective should be able to disagree: a lower-FV player with higher
    # projection can replace a higher-FV player in a flex competition.
    toy = [
        Player("a", "a", "YoungDynasty", "WR", "bench", 1000, 100),
        Player("b", "b", "VeteranPoints", "WR", "bench", 700, 200),
    ]
    assert max(toy, key=lambda p: p.objective("fundamental")).player_id == "a"
    assert max(toy, key=lambda p: p.objective("projection")).player_id == "b"

    aliases = {"m penix": "michael penix"}
    reverse = {"michael penix": "m penix"}
    test_db = {"m penix": {"pos": "QB", "age": 26, "role": "Starter"}}
    assert resolve_existing_key("michael penix", test_db, aliases, reverse) == "m penix"
    assert resolve_existing_key("brand new", test_db, aliases, reverse) == "brand new"

    if all(path.exists() for path in (INDEX, ROSTERS, PLAYER_POSITIONS)):
        roster_doc = json.loads(ROSTERS.read_text(encoding="utf-8"))
        base_cfg = snapshot_values.load_from_html(INDEX)
        merged_cfg = merge_live_league_into_cfg(base_cfg, roster_doc)
        stats = merged_cfg["live_merge_stats"]
        assert stats["added_player_db_rows"] >= 1
        assert len(merged_cfg["player_db"]) >= len(base_cfg["player_db"])

    print("team_utility_starter_objective_audit self-test passed.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        run_selftest()
        return 0

    result = audit()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_md(result) + "\n", encoding="utf-8")

    print(json.dumps(result["aggregate"], indent=2))
    print(f"Wrote {OUT_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
