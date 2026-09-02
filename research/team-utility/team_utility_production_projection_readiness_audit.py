#!/usr/bin/env python3
"""Audit whether production PLAYER_DB.proj2026 is ready to drive Team Utility lineup selection.

Research-only. Does NOT change production.

This audit answers:
1. How much of each current roster has baked PLAYER_DB.proj2026 coverage?
2. How much of each team's *actual current Sleeper starter set* has coverage?
3. Can every legal 17-slot lineup be filled using projected players?
4. How closely does the baked production field agree with the validated
   Sleeper/FantasyPros 50/50 projection blend?
5. If Team Utility selected starters using baked proj2026, how close would that
   lineup be to the blend-optimal lineup?
6. Which live-merged roster players lose projection availability because they
   are not represented by the same PLAYER_DB key as the baked projection row?

Outputs:
  research/team-utility/team_utility_production_projection_readiness_audit.json
  research/team-utility/team_utility_production_projection_readiness_audit.md
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX = REPO_ROOT / "index.html"
BASE_AUDIT_PATH = REPO_ROOT / "research" / "team-utility" / "team_utility_starter_objective_audit.py"
SLEEPER_PROJ = REPO_ROOT / "scripts" / "sleeper_2026_projections.json"
FP_NORMALIZED = REPO_ROOT / "scripts" / "fantasypros_api_normalized_2026.json"
IDENTITY = REPO_ROOT / "scripts" / "identity_crosswalk.json"
OUT_DIR = REPO_ROOT / "research" / "team-utility"
OUT_JSON = OUT_DIR / "team_utility_production_projection_readiness_audit.json"
OUT_MD = OUT_DIR / "team_utility_production_projection_readiness_audit.md"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return mod


def parse_player_db_numeric_field(index_text: str, field: str) -> dict[str, float]:
    """Parse a numeric field from single-line PLAYER_DB object entries."""
    body_start = index_text.find("const PLAYER_DB = {")
    if body_start < 0:
        raise RuntimeError("PLAYER_DB not found in index.html")
    body_end = index_text.find("\n};", body_start)
    if body_end < 0:
        raise RuntimeError("PLAYER_DB closing delimiter not found")

    body = index_text[body_start:body_end]
    entry_re = re.compile(r"(?m)^\s*'([^']+)'\s*:\s*\{([^\n}]*)\}")
    field_re = re.compile(rf"\b{re.escape(field)}\s*:\s*(-?[0-9]+(?:\.[0-9]+)?)\b")
    out = {}
    for key, payload in entry_re.findall(body):
        m = field_re.search(payload)
        if m:
            out[key] = float(m.group(1))
    return out


def load_sleeper_projection_by_id() -> dict[str, float]:
    rows = json.loads(SLEEPER_PROJ.read_text(encoding="utf-8"))
    return {
        str(r["sleeper_id"]): float(r["sleeper_2026_proj_total"])
        for r in rows
        if r.get("sleeper_id") is not None
        and isinstance(r.get("sleeper_2026_proj_total"), (int, float))
        and r["sleeper_2026_proj_total"] > 0
    }


def load_fantasypros_projection_by_id() -> tuple[dict[str, float], dict]:
    doc = json.loads(FP_NORMALIZED.read_text(encoding="utf-8"))
    rows = doc.get("players", [])
    by_fpid = {
        str(r["fantasypros_id"]): r
        for r in rows
        if r.get("fantasypros_id") is not None
    }
    crosswalk = json.loads(IDENTITY.read_text(encoding="utf-8"))
    out = {}
    skipped_review = 0
    for link in crosswalk:
        if link.get("requires_manual_review"):
            skipped_review += 1
            continue
        sid = link.get("sleeper_id")
        fpid = link.get("fantasypros_id")
        if sid is None or fpid is None:
            continue
        row = by_fpid.get(str(fpid))
        if not row:
            continue
        pts = row.get("trade_desk_normalized_points")
        if isinstance(pts, (int, float)):
            out[str(sid)] = float(pts)
    return out, {
        "normalized_rows": len(rows),
        "mapped_with_points": len(out),
        "manual_review_skipped": skipped_review,
    }


def build_blend(sleeper: dict[str, float], fp: dict[str, float]) -> tuple[dict[str, float], dict]:
    out = {}
    counts = {"both": 0, "sleeper_only": 0, "fantasypros_only": 0}
    for pid in set(sleeper) | set(fp):
        s = sleeper.get(pid)
        f = fp.get(pid)
        if s is not None and f is not None:
            out[pid] = 0.5 * s + 0.5 * f
            counts["both"] += 1
        elif s is not None:
            out[pid] = s
            counts["sleeper_only"] += 1
        elif f is not None:
            out[pid] = f
            counts["fantasypros_only"] += 1
    return out, counts


def optimize(base, players, score_by_key: dict[str, float], missing_policy: str = "last"):
    """Legal lineup optimizer using a supplied key->score map.

    missing_policy="last": players with a real projection always rank ahead of
    missing-projection players; Fundamental Value breaks ties and fills a slot
    only when no projected candidate is available.
    """
    remaining = list(players)
    starters = []

    def score_tuple(p):
        score = score_by_key.get(p.key)
        if score is None:
            if missing_policy == "last":
                return (0, -math.inf, p.fundamental, p.key)
            raise ValueError(missing_policy)
        return (1, float(score), p.fundamental, p.key)

    def pop_best(eligible, label, count):
        nonlocal remaining
        for _ in range(count):
            candidates = [p for p in remaining if p.pos in eligible]
            if not candidates:
                break
            best = max(candidates, key=score_tuple)
            remaining.remove(best)
            starters.append({"slot": label, "player": best, "score": score_by_key.get(best.key)})

    for pos, count in base.DEDICATED.items():
        pop_best({pos}, pos, count)
    for label, eligible, count in base.FLEXES:
        pop_best(eligible, label, count)

    return {"starters": starters, "bench": remaining}


def optimize_by_id(base, players, score_by_id: dict[str, float]):
    remaining = list(players)
    starters = []

    def score_tuple(p):
        score = score_by_id.get(p.player_id)
        if score is None:
            return (0, -math.inf, p.fundamental, p.key)
        return (1, float(score), p.fundamental, p.key)

    def pop_best(eligible, label, count):
        nonlocal remaining
        for _ in range(count):
            candidates = [p for p in remaining if p.pos in eligible]
            if not candidates:
                break
            best = max(candidates, key=score_tuple)
            remaining.remove(best)
            starters.append({"slot": label, "player": best, "score": score_by_id.get(best.player_id)})

    for pos, count in base.DEDICATED.items():
        pop_best({pos}, pos, count)
    for label, eligible, count in base.FLEXES:
        pop_best(eligible, label, count)

    return {"starters": starters, "bench": remaining}


def lineup_ids(result):
    return {row["player"].player_id for row in result["starters"]}


def non_k_projection_total(result, projection_by_id):
    total = 0.0
    missing = []
    for row in result["starters"]:
        p = row["player"]
        if p.pos == "K":
            continue
        val = projection_by_id.get(p.player_id)
        if val is None:
            missing.append(p.player_id)
        else:
            total += val
    return total, missing


def spearman(xs, ys):
    if len(xs) < 3:
        return None

    def ranks(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        out = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j + 2) / 2.0
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    deny = math.sqrt(sum((b - my) ** 2 for b in ry))
    if denx == 0 or deny == 0:
        return None
    return num / (denx * deny)


def median(values):
    return statistics.median(values) if values else None


def run_audit():
    base = load_module(BASE_AUDIT_PATH, "team_utility_starter_objective_base")
    cfg, _, roster_doc = base.load_inputs()
    fundamental_by_key = base.snapshot_values.compute_all_values(cfg)

    index_text = INDEX.read_text(encoding="utf-8")
    prod_proj_by_key = parse_player_db_numeric_field(index_text, "proj2026")
    prod_pts2025_by_key = parse_player_db_numeric_field(index_text, "pts2025")

    sleeper = load_sleeper_projection_by_id()
    fp, fp_stats = load_fantasypros_projection_by_id()
    blend, blend_stats = build_blend(sleeper, fp)

    team_rows = []
    overlap_prod_blend = []
    complete_blend_losses = []
    complete_fv_blend_losses = []
    actual_starter_missing = []
    runtime_projection_gaps = []

    all_overlap_prod = []
    all_overlap_blend = []
    all_overlap_pts2025 = []

    for roster in roster_doc.get("rosters", []):
        # Active-only scope: taxi players cannot occupy a current starting slot.
        players, unresolved = base.build_roster_players(
            roster,
            cfg,
            fundamental_by_key,
            sleeper,
            base.ACTIVE_SCOPE_SLOTS,
        )
        if unresolved:
            raise RuntimeError(f"unexpected unresolved roster rows: {unresolved}")

        by_id = {p.player_id: p for p in players}
        by_key = {p.key: p for p in players}

        prod = optimize(base, players, prod_proj_by_key)
        blend_opt = optimize_by_id(base, players, blend)
        fv = base.optimize_lineup(players, "fundamental")

        prod_ids = lineup_ids(prod)
        blend_ids = lineup_ids(blend_opt)
        fv_ids = lineup_ids(fv)

        # Current actual Sleeper starters in the source roster.
        raw_actual_starters = roster.get("starters", []) or []
        resolved_actual = []
        for raw in raw_actual_starters:
            pid = str(raw.get("player_id") or "")
            p = by_id.get(pid)
            if p:
                resolved_actual.append(p)

        actual_non_k = [p for p in resolved_actual if p.pos != "K"]
        actual_missing = [p for p in actual_non_k if p.key not in prod_proj_by_key]
        actual_starter_missing.extend(
            {
                "roster_id": roster.get("roster_id"),
                "team_name": roster.get("team_name") or roster.get("owner_username"),
                "player_id": p.player_id,
                "player": p.name,
                "key": p.key,
                "pos": p.pos,
            }
            for p in actual_missing
        )

        # Any active roster player whose live-resolved key lacks proj2026 but
        # whose Sleeper ID has a projection elsewhere is a key-lineage gap.
        for p in players:
            if p.key in prod_proj_by_key:
                continue
            external = blend.get(p.player_id) or sleeper.get(p.player_id) or fp.get(p.player_id)
            if external is not None:
                runtime_projection_gaps.append(
                    {
                        "roster_id": roster.get("roster_id"),
                        "team_name": roster.get("team_name") or roster.get("owner_username"),
                        "player_id": p.player_id,
                        "player": p.name,
                        "key": p.key,
                        "pos": p.pos,
                        "external_projection": round(float(external), 1),
                    }
                )

        prod_total, prod_blend_missing = non_k_projection_total(prod, blend)
        blend_total, blend_missing = non_k_projection_total(blend_opt, blend)
        fv_total, fv_blend_missing = non_k_projection_total(fv, blend)

        prod_complete = len(prod["starters"]) == base.EXPECTED_STARTERS
        blend_eval_complete = not prod_blend_missing and not blend_missing
        fv_eval_complete = not fv_blend_missing and not blend_missing

        prod_loss = blend_total - prod_total if blend_eval_complete else None
        fv_loss = blend_total - fv_total if fv_eval_complete else None
        if prod_loss is not None:
            complete_blend_losses.append(prod_loss)
        if fv_loss is not None:
            complete_fv_blend_losses.append(fv_loss)

        prod_scored_starters = sum(
            1
            for row in prod["starters"]
            if row["player"].pos == "K" or row["player"].key in prod_proj_by_key
        )
        missing_selected = [
            row["player"]
            for row in prod["starters"]
            if row["player"].pos != "K" and row["player"].key not in prod_proj_by_key
        ]

        active_non_k = [p for p in players if p.pos != "K"]
        prod_cov = (
            100.0 * sum(1 for p in active_non_k if p.key in prod_proj_by_key) / len(active_non_k)
            if active_non_k
            else 0.0
        )
        actual_cov = (
            100.0 * (len(actual_non_k) - len(actual_missing)) / len(actual_non_k)
            if actual_non_k
            else 100.0
        )

        overlap = len(prod_ids & blend_ids)
        overlap_prod_blend.append(overlap)

        team_rows.append(
            {
                "roster_id": roster.get("roster_id"),
                "team_name": roster.get("team_name")
                or roster.get("owner_username")
                or f"Roster {roster.get('roster_id')}",
                "active_player_count": len(players),
                "active_non_k_prod2026_coverage_pct": round(prod_cov, 1),
                "actual_non_k_starter_prod2026_coverage_pct": round(actual_cov, 1),
                "actual_non_k_starters_missing_prod2026": len(actual_missing),
                "prod2026_lineup_starter_count": len(prod["starters"]),
                "prod2026_lineup_scored_or_k_count": prod_scored_starters,
                "prod2026_lineup_missing_projection_count": len(missing_selected),
                "prod2026_lineup_missing_projection_players": [
                    {"player_id": p.player_id, "player": p.name, "pos": p.pos, "key": p.key}
                    for p in missing_selected
                ],
                "prod2026_vs_blend_starter_overlap": overlap,
                "fv_vs_blend_starter_overlap": len(fv_ids & blend_ids),
                "blend_eval_complete_for_prod2026_lineup": blend_eval_complete,
                "blend_points_prod2026_lineup": round(prod_total, 1),
                "blend_points_optimal_lineup": round(blend_total, 1),
                "blend_points_left_on_table_by_prod2026": round(prod_loss, 1)
                if prod_loss is not None
                else None,
                "blend_points_left_on_table_by_fv": round(fv_loss, 1)
                if fv_loss is not None
                else None,
            }
        )

        # Player-level numeric alignment among active players with both signals.
        for p in players:
            pp = prod_proj_by_key.get(p.key)
            bp = blend.get(p.player_id)
            if pp is not None and bp is not None:
                all_overlap_prod.append(pp)
                all_overlap_blend.append(bp)
                hist = prod_pts2025_by_key.get(p.key)
                if hist is not None:
                    all_overlap_pts2025.append(hist)

    team_rows.sort(
        key=lambda r: (
            -(r["blend_points_left_on_table_by_prod2026"] or -1),
            r["roster_id"] or 0,
        )
    )

    aggregate = {
        "team_count": len(team_rows),
        "expected_starters_per_team": base.EXPECTED_STARTERS,
        "baked_prod2026_player_rows": len(prod_proj_by_key),
        "teams_with_full_legal_prod2026_lineup": sum(
            1
            for r in team_rows
            if r["prod2026_lineup_starter_count"] == base.EXPECTED_STARTERS
            and r["prod2026_lineup_missing_projection_count"] == 0
        ),
        "median_active_non_k_prod2026_coverage_pct": round(
            median([r["active_non_k_prod2026_coverage_pct"] for r in team_rows]), 2
        ),
        "median_actual_non_k_starter_prod2026_coverage_pct": round(
            median([r["actual_non_k_starter_prod2026_coverage_pct"] for r in team_rows]), 2
        ),
        "actual_non_k_starters_missing_prod2026": len(actual_starter_missing),
        "runtime_key_projection_gaps_with_external_signal": len(runtime_projection_gaps),
        "median_prod2026_vs_blend_starter_overlap": round(median(overlap_prod_blend), 2),
        "complete_blend_evaluations_for_prod2026_lineup": len(complete_blend_losses),
        "median_blend_points_left_on_table_by_prod2026": round(
            median(complete_blend_losses), 2
        )
        if complete_blend_losses
        else None,
        "median_blend_points_left_on_table_by_fv": round(
            median(complete_fv_blend_losses), 2
        )
        if complete_fv_blend_losses
        else None,
        "active_player_overlap_prod2026_vs_blend_n": len(all_overlap_prod),
        "active_player_prod2026_vs_blend_spearman": round(
            spearman(all_overlap_prod, all_overlap_blend), 4
        )
        if spearman(all_overlap_prod, all_overlap_blend) is not None
        else None,
        "active_player_prod2026_vs_blend_median_abs_diff": round(
            median([abs(a - b) for a, b in zip(all_overlap_prod, all_overlap_blend)]), 2
        )
        if all_overlap_prod
        else None,
        "fantasypros_identity": fp_stats,
        "blend_population": blend_stats,
    }

    return {
        "audit": "team_utility_production_projection_readiness_audit",
        "production_changed": False,
        "candidate": (
            "Use PLAYER_DB.proj2026 to select starters; Fundamental Value remains "
            "the Team Utility accounting unit; taxi excluded from starter candidates."
        ),
        "aggregate": aggregate,
        "teams": team_rows,
        "actual_starters_missing_prod2026": actual_starter_missing,
        "runtime_projection_key_gaps": runtime_projection_gaps,
        "guardrails": [
            "This does not calibrate TU_BENCH_WEIGHT.",
            "This does not replace Fundamental Value with projected points.",
            "Missing proj2026 is treated as a fallback condition, not as a zero projection.",
            "Taxi players are excluded from starter candidates because they are not currently startable without activation.",
            "The blend is an evaluation reference, not automatically the production source.",
        ],
    }


def render_md(result):
    a = result["aggregate"]
    lines = [
        "# Team Utility Production Projection Readiness Audit",
        "",
        "Research-only. **No production values or Team Utility constants were changed.**",
        "",
        "## Candidate architecture",
        "",
        result["candidate"],
        "",
        "## Readiness summary",
        "",
        f"- Baked PLAYER_DB rows with `proj2026`: **{a['baked_prod2026_player_rows']}**",
        f"- Teams able to fill all 17 legal starter slots without a non-K projection fallback: **{a['teams_with_full_legal_prod2026_lineup']} / {a['team_count']}**",
        f"- Median active non-K roster coverage: **{a['median_active_non_k_prod2026_coverage_pct']}%**",
        f"- Median actual non-K Sleeper-starter coverage: **{a['median_actual_non_k_starter_prod2026_coverage_pct']}%**",
        f"- Actual non-K current starters missing `proj2026`: **{a['actual_non_k_starters_missing_prod2026']}**",
        f"- Active roster key gaps where another projection source has signal: **{a['runtime_key_projection_gaps_with_external_signal']}**",
        "",
        "## Agreement with validated blend",
        "",
        f"- Active players with both baked `proj2026` and blend signal: **{a['active_player_overlap_prod2026_vs_blend_n']}**",
        f"- Spearman correlation, baked `proj2026` vs blend: **{a['active_player_prod2026_vs_blend_spearman']}**",
        f"- Median absolute point difference: **{a['active_player_prod2026_vs_blend_median_abs_diff']}**",
        f"- Median starter overlap, baked `proj2026` vs blend-optimal: **{a['median_prod2026_vs_blend_starter_overlap']} / {a['expected_starters_per_team']}**",
        f"- Complete blend evaluations for baked-projection lineup: **{a['complete_blend_evaluations_for_prod2026_lineup']} / {a['team_count']}**",
        f"- Median blend points left on table by baked-projection lineup: **{a['median_blend_points_left_on_table_by_prod2026']}**",
        f"- Median blend points left on table by current FV lineup: **{a['median_blend_points_left_on_table_by_fv']}**",
        "",
        "## Team detail",
        "",
        "| Team | Active proj cov. | Actual starter cov. | Missing selected proj | Prod/Blend overlap | Prod points left | FV points left |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in result["teams"]:
        lines.append(
            f"| {r['team_name']} | {r['active_non_k_prod2026_coverage_pct']:.1f}% | "
            f"{r['actual_non_k_starter_prod2026_coverage_pct']:.1f}% | "
            f"{r['prod2026_lineup_missing_projection_count']} | "
            f"{r['prod2026_vs_blend_starter_overlap']}/{a['expected_starters_per_team']} | "
            f"{r['blend_points_left_on_table_by_prod2026'] if r['blend_points_left_on_table_by_prod2026'] is not None else 'n/a'} | "
            f"{r['blend_points_left_on_table_by_fv'] if r['blend_points_left_on_table_by_fv'] is not None else 'n/a'} |"
        )

    if result["actual_starters_missing_prod2026"]:
        lines += ["", "## Current starters missing baked `proj2026`", ""]
        for row in result["actual_starters_missing_prod2026"]:
            lines.append(
                f"- {row['team_name']}: {row['player']} ({row['pos']}, Sleeper {row['player_id']}, key `{row['key']}`)"
            )

    if result["runtime_projection_key_gaps"]:
        lines += ["", "## Runtime key gaps with projection signal elsewhere", ""]
        for row in result["runtime_projection_key_gaps"]:
            lines.append(
                f"- {row['team_name']}: {row['player']} ({row['pos']}, Sleeper {row['player_id']}, "
                f"live key `{row['key']}`, external projection {row['external_projection']})"
            )

    lines += ["", "## Guardrails", ""]
    lines.extend(f"- {g}" for g in result["guardrails"])
    lines.append("")
    return "\n".join(lines)


def selftest():
    base = load_module(BASE_AUDIT_PATH, "team_utility_readiness_base")
    assert base.EXPECTED_STARTERS == 17

    fixture = """const PLAYER_DB = {
 'alpha':{pos:'RB',age:24,role:'Starter',proj2026:123.4,pts2025:88.1},
 'beta':{pos:'WR',age:25,role:'Starter'},
 'gamma':{pos:'LB',age:26,role:'Starter',proj2026:0.0},
};"""
    parsed = parse_player_db_numeric_field(fixture, "proj2026")
    assert parsed == {"alpha": 123.4, "gamma": 0.0}, parsed

    if all(p.exists() for p in (INDEX, SLEEPER_PROJ, FP_NORMALIZED, IDENTITY)):
        prod = parse_player_db_numeric_field(INDEX.read_text(encoding="utf-8"), "proj2026")
        assert len(prod) >= 300, len(prod)
        sleeper = load_sleeper_projection_by_id()
        fp, _ = load_fantasypros_projection_by_id()
        blend, _ = build_blend(sleeper, fp)
        assert len(sleeper) >= 100
        assert len(fp) >= 100
        assert len(blend) >= 100

    print("team_utility_production_projection_readiness_audit self-test passed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return 0

    result = run_audit()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_md(result) + "\n", encoding="utf-8")
    print(json.dumps(result["aggregate"], indent=2))
    print(f"Wrote {OUT_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
