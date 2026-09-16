#!/usr/bin/env python3
"""Free-Agent Production V2 — Phase 1 lineage audit and freeze.

Research only. This script reconstructs the currently active
FA_PROD_MULT_DATA cohort from canonical 2025 history plus frozen 2026
projection inputs while reusing the already-audited Production V2
benchmark architecture. It NEVER mutates production files.

Frozen Phase-1 methodology
--------------------------
* cohort: current free agents that actually resolve to FA_PROD_MULT_DATA
* kickers excluded
* identity authority: current Sleeper player_id + position
* history: canonical production_history_component.py, unchanged
* offense forward: 50/50 FantasyPros/Sleeper when both are present;
  single-source fallback otherwise
* IDP forward: canonical idp_v1_projection.py V1 category ensemble
* history/forward blend: 45% / 55%
* replacement ranks: QB18/RB32/WR36/TE15/DL32/LB32/DB32
* prod transform: clamp(-0.10 + 0.75 * ratio, 0.15, 1.55)
* primary coverage gate: >= 90% of actively-used non-K FA entries must
  have a reproducible candidate production multiplier
* offense provider integrity gate: FantasyPros coverage must be >= 50%
  of active offense entries that have a Sleeper forward projection
* no production deployment is authorized by Phase 1
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import sys

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
RESEARCH = ROOT / "research" / "free-agent-production-v2"
CORE_PATH = ROOT / "research" / "production-v2" / "production_v2_phase1_audit.py"
BOARD = ROOT / "free-agent-board.html"
FREE_AGENTS = ROOT / "data" / "free_agents.json"
INDEX = ROOT / "index.html"
PPG = ROOT / "scripts" / "ppg_results.json"
DURABILITY = ROOT / "scripts" / "durability_results.json"
SLEEPER_TOTALS = ROOT / "scripts" / "sleeper_2026_projections.json"
SLEEPER_RAW = ROOT / "scripts" / "artifacts" / "generated" / "sleeper_2026_raw_categories.json"
FP = ROOT / "scripts" / "fantasypros_api_normalized_2026.json"
CROSSWALK = ROOT / "scripts" / "identity_crosswalk.json"
HISTORY_MOD = ROOT / "scripts" / "model" / "production_history_component.py"
IDP_MOD = ROOT / "scripts" / "model" / "idp_v1_projection.py"
LINEUP_BUILDER = ROOT / "scripts" / "projections" / "build_team_utility_lineup_projections.py"
SNAPSHOT_VALUES = ROOT / "scripts" / "validation" / "snapshot_values.py"
FA_VALIDATOR = ROOT / "scripts" / "validation" / "validate_free_agent_valuation_parity.py"
FA_SYNC = ROOT / "scripts" / "sync" / "sync_free_agent_valuation.py"

OUT_JSON = RESEARCH / "free_agent_production_v2_phase1.json"
OUT_MD = RESEARCH / "free_agent_production_v2_phase1.md"
MANIFEST = RESEARCH / "phase1_manifest.json"

TRACKED = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
OFFENSE = {"QB", "RB", "WR", "TE"}
HISTORY_WEIGHT = 0.45
FORWARD_WEIGHT = 0.55
MIN_REPRO_COVERAGE = 0.90
MIN_OFFENSE_FP_VS_SLEEPER = 0.50
REPLACEMENT_RANK = {
    "QB": 18, "RB": 32, "WR": 36, "TE": 15,
    "DL": 32, "LB": 32, "DB": 32,
}
PM_INTERCEPT = -0.10
PM_RATIO_SLOPE = 0.75
PM_MIN = 0.15
PM_MAX = 1.55


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm_name(value) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_team(value):
    if value in (None, ""):
        return None
    return {"JAC": "JAX"}.get(str(value).strip().upper(), str(value).strip().upper())


def finite(value):
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def load_core():
    spec = importlib.util.spec_from_file_location("production_v2_phase1_core", CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not import frozen Production V2 Phase 1 core")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def eval_js_const_object(const_source: str, variable: str):
    """Evaluate trusted repository JavaScript with Node and return JSON data."""
    js = (
        const_source
        + "\nprocess.stdout.write(JSON.stringify("
        + variable
        + "));\n"
    )
    proc = subprocess.run(
        ["node", "-e", js],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Node failed evaluating {variable}: {proc.stderr.strip()[:2000]}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Node returned invalid JSON for {variable}: {proc.stdout[:500]!r}"
        ) from exc


def parse_fa_prod_table():
    # FA_PROD_MULT_DATA is JavaScript. Reuse the repo's canonical constant
    # extractor and let Node evaluate the exact JS syntax instead of translating
    # it into Python. This correctly handles JS-only numeric syntax.
    scripts_dir = ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from sync import sync_free_agent_valuation

    board_text = BOARD.read_text(encoding="utf-8")
    const_source = sync_free_agent_valuation._extract_const_object(
        board_text, "FA_PROD_MULT_DATA"
    )[2]
    obj = eval_js_const_object(const_source, "FA_PROD_MULT_DATA")
    if not isinstance(obj, dict):
        raise RuntimeError("FA_PROD_MULT_DATA did not evaluate to an object")

    rows = []
    for raw_name, value in obj.items():
        values = value if isinstance(value, list) else [value]
        for entry in values:
            if not isinstance(entry, dict):
                raise RuntimeError(f"Invalid FA entry for {raw_name!r}")
            pos = str(entry.get("pos") or "").upper()
            prod = finite(entry.get("prod"))
            if not pos or prod is None:
                raise RuntimeError(f"FA entry missing pos/prod for {raw_name!r}")
            rows.append({
                "name": str(raw_name),
                "key": norm_name(raw_name),
                "pos": pos,
                "team": norm_team(entry.get("team")),
                "role": entry.get("role"),
                "deployed_prod": prod,
            })
    return rows

def index_free_agents():
    doc = read_json(FREE_AGENTS)
    rows = doc.get("free_agents") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError("data/free_agents.json missing free_agents list")
    by_name_pos = defaultdict(list)
    for row in rows:
        pos = str(row.get("pos") or "").upper()
        if pos not in TRACKED:
            continue
        sid = row.get("player_id")
        if sid in (None, ""):
            continue
        rec = {
            "sleeper_id": str(sid),
            "name": str(row.get("name") or ""),
            "key": norm_name(row.get("name")),
            "pos": pos,
            "team": norm_team(row.get("team")),
            "status": row.get("status"),
            "injury_status": row.get("injury_status"),
        }
        by_name_pos[(rec["key"], pos)].append(rec)
    return by_name_pos, doc


def resolve_active_entry(deployed, fa_index):
    candidates = list(fa_index.get((deployed["key"], deployed["pos"]), []))
    if not candidates:
        return None, "not_current_free_agent"
    if len(candidates) == 1:
        return candidates[0], "name_position_unique"
    team = deployed.get("team")
    if team:
        same_team = [r for r in candidates if r.get("team") == team]
        if len(same_team) == 1:
            return same_team[0], "name_position_team"
    return None, "ambiguous_current_free_agent_identity"


def ppg_by_sid(rows):
    groups = defaultdict(list)
    for row in rows:
        sid = row.get("sleeper_id")
        if sid not in (None, ""):
            groups[str(sid)].append(row)
    out = {}
    for sid, group in groups.items():
        if len(group) == 1:
            out[sid] = group[0]
            continue
        # Alias duplicates are acceptable only if the actual historical
        # lineage is identical. Ignore display key/name only.
        def fp(r):
            return {
                k: r.get(k)
                for k in sorted(r)
                if k not in {"player"}
            }
        first = fp(group[0])
        if any(fp(r) != first for r in group[1:]):
            raise RuntimeError(f"Conflicting PPG lineage for Sleeper ID {sid}")
        out[sid] = group[0]
    return out


def summarize(values):
    vals = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not vals:
        return {"n": 0}
    def pct(q):
        if len(vals) == 1:
            return vals[0]
        x = (len(vals) - 1) * q
        lo = int(math.floor(x))
        hi = int(math.ceil(x))
        if lo == hi:
            return vals[lo]
        f = x - lo
        return vals[lo] * (1 - f) + vals[hi] * f
    return {
        "n": len(vals),
        "mean": statistics.fmean(vals),
        "median": statistics.median(vals),
        "p10": pct(0.10),
        "p90": pct(0.90),
        "min": vals[0],
        "max": vals[-1],
    }


def build_result():
    core = load_core()

    # Freeze against silent drift in the already-established Production V2
    # benchmark. Free-Agent V2 is extending lineage/coverage, not quietly
    # changing the benchmark formula while doing so.
    frozen_core = {
        "HISTORY_WEIGHT": HISTORY_WEIGHT,
        "FORWARD_WEIGHT": FORWARD_WEIGHT,
        "OFFENSE_FP_WEIGHT": 0.50,
        "PM_INTERCEPT": PM_INTERCEPT,
        "PM_RATIO_SLOPE": PM_RATIO_SLOPE,
        "PM_MIN": PM_MIN,
        "PM_MAX": PM_MAX,
    }
    for attr, expected in frozen_core.items():
        actual = getattr(core, attr, None)
        if actual != expected:
            raise RuntimeError(
                f"Frozen Production V2 constant drift: {attr}={actual!r}; "
                f"expected {expected!r}"
            )
    if getattr(core, "REPLACEMENT_RANK", None) != REPLACEMENT_RANK:
        raise RuntimeError(
            f"Frozen Production V2 replacement-rank drift: "
            f"{getattr(core, 'REPLACEMENT_RANK', None)!r}"
        )

    core_result = core.build_audit()
    baselines = core_result.get("phase1_baselines")
    if not isinstance(baselines, dict):
        raise RuntimeError("Production V2 core did not expose phase1_baselines")
    for pos, rank in REPLACEMENT_RANK.items():
        b = baselines.get(pos)
        if not isinstance(b, dict) or int(b.get("rank", -1)) != rank:
            raise RuntimeError(f"Frozen replacement rank mismatch for {pos}")
        if finite(b.get("combined_points")) is None or float(b["combined_points"]) <= 0:
            raise RuntimeError(f"Invalid baseline for {pos}")

    idp_v1, history_mod, lineup_builder, _snapshot = core.get_repo_modules()

    # validate_free_agent_valuation_parity.py imports snapshot_values
    # as a flat sibling module, so scripts/validation itself must be
    # on sys.path before importing the validator.
    validation_dir = ROOT / "scripts" / "validation"
    if str(validation_dir) not in sys.path:
        sys.path.insert(0, str(validation_dir))
    import validate_free_agent_valuation_parity as fa_validator

    ppg_rows = read_json(PPG)
    durability = read_json(DURABILITY)
    sleeper_total_rows = read_json(SLEEPER_TOTALS)
    sleeper_raw_rows = read_json(SLEEPER_RAW)
    fp_doc = read_json(FP)
    crosswalk = read_json(CROSSWALK)

    sleeper_totals = core.index_unique(
        sleeper_total_rows, lambda r: r.get("sleeper_id"), "Sleeper totals"
    )
    sleeper_raw = core.index_unique(
        sleeper_raw_rows, lambda r: r.get("sleeper_id"), "Sleeper raw"
    )
    fp_by_sleeper, fp_identity_stats = lineup_builder.build_fp_by_sleeper(
        fp_doc["players"], crosswalk
    )
    hist_constants = history_mod.derive_history_constants(ppg_rows, durability)
    hist_by_sid = ppg_by_sid(ppg_rows)

    deployed_rows = parse_fa_prod_table()
    fa_index, fa_doc = index_free_agents()

    board_text = BOARD.read_text(encoding="utf-8")
    runtime = fa_validator._board_runtime_rows(board_text, fa_doc)
    runtime_source_by_id = {
        str(k): str(v) for k, v in runtime["production_source_by_id"].items()
    }
    runtime_fa_specific_ids = {
        str(fa["player_id"])
        for fa in (fa_doc.get("free_agents") or [])
        if str(fa.get("pos") or "").upper() in TRACKED
        and runtime_source_by_id.get(str(fa.get("player_id"))) == "fa_specific_prod"
    }

    rows = []
    inactive_reasons = Counter()
    identity_methods = Counter()
    source_counts = Counter()
    coverage_by_pos = {p: Counter() for p in TRACKED}

    for dep in deployed_rows:
        if dep["pos"] == "K":
            inactive_reasons["kicker_excluded"] += 1
            continue
        if dep["pos"] not in TRACKED:
            inactive_reasons["unsupported_position"] += 1
            continue

        fa, identity_method = resolve_active_entry(dep, fa_index)
        if fa is None:
            inactive_reasons[identity_method] += 1
            continue

        sid = fa["sleeper_id"]
        runtime_source = runtime_source_by_id.get(sid)
        if runtime_source != "fa_specific_prod":
            inactive_reasons[
                f"runtime_source_{runtime_source or 'missing'}"
            ] += 1
            continue

        identity_methods[identity_method] += 1
        pos = dep["pos"]
        cov = coverage_by_pos[pos]
        cov["active_deployed_entries"] += 1
        cov["stable_sleeper_id"] += 1

        ppg_row = hist_by_sid.get(sid)
        if ppg_row is not None:
            ppg_pos = str(ppg_row.get("pos") or "").upper()
            if ppg_pos and ppg_pos != pos:
                # Stable identity is authoritative, but a historical
                # position mismatch changes replacement semantics, so do
                # not silently consume it.
                ppg_row = None
                cov["ppg_position_mismatch"] += 1
            else:
                cov["ppg_row"] += 1

        history = history_mod.compute_history_for_player(pos, ppg_row, hist_constants)

        fp_row = fp_by_sleeper.get(sid)
        forward = core.build_forward_projection(
            pos,
            sid,
            sleeper_totals,
            sleeper_raw,
            fp_row,
            idp_v1,
        )
        source_counts[forward["source"]] += 1

        if sid in sleeper_totals:
            cov["sleeper_projection_row"] += 1
        if fp_row is not None:
            cov["fantasypros_projection_row"] += 1
        if sid in sleeper_totals and fp_row is not None:
            cov["both_provider_rows"] += 1
        if finite(forward.get("projection")) is not None:
            cov["usable_forward_projection"] += 1

        history_points = finite(history.get("history_component"))
        forward_points = finite(forward.get("projection"))
        combined = None
        candidate_pm = None
        ratio = None
        if history_points is not None and forward_points is not None:
            combined = HISTORY_WEIGHT * history_points + FORWARD_WEIGHT * forward_points
            baseline = float(baselines[pos]["combined_points"])
            ratio = combined / baseline
            candidate_pm = clamp(PM_INTERCEPT + PM_RATIO_SLOPE * ratio, PM_MIN, PM_MAX)
            cov["reproducible_candidate"] += 1

        rows.append({
            "name": dep["name"],
            "key": dep["key"],
            "pos": pos,
            "team_deployed": dep.get("team"),
            "team_current": fa.get("team"),
            "sleeper_id": sid,
            "identity_method": identity_method,
            "deployed_prod": dep["deployed_prod"],
            "history": history,
            "forward": forward,
            "combined_points": combined,
            "replacement_baseline_points": float(baselines[pos]["combined_points"]),
            "ratio_to_replacement": ratio,
            "candidate_prod": candidate_pm,
            "candidate_minus_deployed": (
                candidate_pm - dep["deployed_prod"] if candidate_pm is not None else None
            ),
        })

    runtime_active_n = len(runtime_fa_specific_ids)
    mapped_runtime_ids = [r["sleeper_id"] for r in rows]
    mapped_counts = Counter(mapped_runtime_ids)
    duplicate_runtime_ids = sorted(
        sid for sid, n in mapped_counts.items() if n > 1
    )
    mapped_runtime_id_set = set(mapped_runtime_ids)
    missing_runtime_ids = sorted(runtime_fa_specific_ids - mapped_runtime_id_set)
    extra_runtime_ids = sorted(mapped_runtime_id_set - runtime_fa_specific_ids)
    runtime_identity_exact = (
        not duplicate_runtime_ids
        and not missing_runtime_ids
        and not extra_runtime_ids
    )

    candidate_ids = {
        r["sleeper_id"]
        for r in rows
        if r["candidate_prod"] is not None
        and r["sleeper_id"] in runtime_fa_specific_ids
    }
    candidate_n = len(candidate_ids)
    coverage = candidate_n / runtime_active_n if runtime_active_n else 0.0

    active_offense_with_sleeper = 0
    active_offense_with_sleeper_and_fp = 0
    for r in rows:
        if r["pos"] not in OFFENSE:
            continue
        sid = r["sleeper_id"]
        if sid in sleeper_totals:
            active_offense_with_sleeper += 1
            if sid in fp_by_sleeper:
                active_offense_with_sleeper_and_fp += 1
    offense_fp_share = (
        active_offense_with_sleeper_and_fp / active_offense_with_sleeper
        if active_offense_with_sleeper else 1.0
    )

    gates = {
        "runtime_fa_specific_identity_exact": {
            "pass": runtime_identity_exact,
            "runtime_count": runtime_active_n,
            "mapped_unique_count": len(mapped_runtime_id_set),
            "missing_ids": missing_runtime_ids,
            "extra_ids": extra_runtime_ids,
            "duplicate_ids": duplicate_runtime_ids,
        },
        "reproducible_candidate_coverage": {
            "value": coverage,
            "minimum": MIN_REPRO_COVERAGE,
            "pass": coverage >= MIN_REPRO_COVERAGE,
            "numerator": candidate_n,
            "denominator": runtime_active_n,
        },
        "offense_fantasypros_coverage_vs_sleeper": {
            "value": offense_fp_share,
            "minimum": MIN_OFFENSE_FP_VS_SLEEPER,
            "pass": offense_fp_share >= MIN_OFFENSE_FP_VS_SLEEPER,
            "numerator": active_offense_with_sleeper_and_fp,
            "denominator": active_offense_with_sleeper,
        },
        "replacement_baselines_present": {
            "pass": all(
                pos in baselines and finite(baselines[pos].get("combined_points")) is not None
                for pos in TRACKED
            )
        },
    }
    all_pass = all(g["pass"] for g in gates.values())
    decision = (
        "PASS_FA_PROD_V2_PHASE1_LINEAGE_AND_FREEZE"
        if all_pass
        else "STOP_FA_PROD_V2_PHASE1_LINEAGE_OR_COVERAGE_INSUFFICIENT"
    )

    deltas = [r["candidate_minus_deployed"] for r in rows if r["candidate_minus_deployed"] is not None]
    abs_movers = sorted(
        (r for r in rows if r["candidate_prod"] is not None),
        key=lambda r: (-abs(r["candidate_minus_deployed"]), r["key"], r["pos"]),
    )[:25]

    input_paths = [
        BOARD, FREE_AGENTS, INDEX, PPG, DURABILITY, SLEEPER_TOTALS,
        SLEEPER_RAW, FP, CROSSWALK, HISTORY_MOD, IDP_MOD, CORE_PATH,
        LINEUP_BUILDER, SNAPSHOT_VALUES, FA_VALIDATOR, FA_SYNC,
    ]

    return {
        "study_id": "free-agent-production-v2",
        "phase": 1,
        "repo_commit_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "status": "FROZEN_LINEAGE_AUDIT_COMPLETE",
        "decision": decision,
        "scientific_scope": "RESEARCH_ONLY_NO_PRODUCTION_MUTATION",
        "production_change_authorized": False,
        "methodology": {
            "cohort": "current free agents actively resolving to deployed FA_PROD_MULT_DATA; kickers excluded",
            "identity": "current Sleeper player_id + calculator position; team only disambiguates duplicate name+position",
            "history": "scripts/model/production_history_component.py unchanged canonical 2025 shrinkage + durability math",
            "offense_forward": "50% FantasyPros Trade-Desk-normalized + 50% Sleeper when both; single-source fallback",
            "idp_forward": "scripts/model/idp_v1_projection.py canonical IDP V1 category ensemble",
            "history_weight": HISTORY_WEIGHT,
            "forward_weight": FORWARD_WEIGHT,
            "replacement_rank": REPLACEMENT_RANK,
            "prod_transform": {
                "formula": "clamp(-0.10 + 0.75 * ratio, 0.15, 1.55)",
                "intercept": PM_INTERCEPT,
                "slope": PM_RATIO_SLOPE,
                "min": PM_MIN,
                "max": PM_MAX,
            },
            "held_fixed": [
                "canonical Trade Desk player-value engine",
                "position weights",
                "age curves",
                "role logic",
                "durability methodology",
                "global scale",
                "core PROD_MULT_DATA",
            ],
        },
        "gates": gates,
        "counts": {
            "fa_prod_entries_total_including_k": len(deployed_rows),
            "current_free_agents_file_count": int(fa_doc.get("count") or 0),
            "active_non_k_deployed_entries": runtime_active_n,
            "mapped_active_non_k_entries": len(rows),
            "runtime_fa_specific_non_k_entries": runtime_active_n,
            "runtime_production_source_counts": runtime["production_source_counts"],
            "reproducible_candidates": candidate_n,
            "inactive_or_excluded_reasons": dict(sorted(inactive_reasons.items())),
            "identity_methods": dict(sorted(identity_methods.items())),
            "forward_source_counts": dict(sorted(source_counts.items())),
        },
        "coverage_by_position": {
            p: dict(sorted(coverage_by_pos[p].items())) for p in TRACKED
        },
        "phase1_baselines": baselines,
        "delta_summary_candidate_minus_deployed": summarize(deltas),
        "largest_absolute_prod_movers": [
            {
                "name": r["name"],
                "pos": r["pos"],
                "sleeper_id": r["sleeper_id"],
                "deployed_prod": r["deployed_prod"],
                "candidate_prod": r["candidate_prod"],
                "delta": r["candidate_minus_deployed"],
                "forward_source": r["forward"]["source"],
            }
            for r in abs_movers
        ],
        "input_sha256": {
            str(p.relative_to(ROOT)): sha256(p) for p in input_paths
        },
        "core_phase1_input_sha256": core_result.get("input_sha256"),
        "fantasypros_identity_stats": fp_identity_stats,
        "rows": rows,
        "next_step_if_pass": "FREE_AGENT_PRODUCTION_V2_SHADOW_VALIDATION_PREREGISTRATION_ONLY",
        "next_step_if_fail": "STOP_AND_REPAIR_SOURCE_OR_IDENTITY_COVERAGE_BEFORE_ANY_MODEL_SELECTION",
    }


def build_markdown(r):
    g = r["gates"]
    c = r["counts"]
    lines = [
        "# Free-Agent Production V2 — Phase 1 Lineage Audit & Freeze",
        "",
        f"**Decision:** `{r['decision']}`",
        "",
        "This phase is research-only. It does not change `FA_PROD_MULT_DATA`, `PROD_MULT_DATA`, `index.html`, or any production valuation logic.",
        "",
        "## Frozen design",
        "",
        "- Cohort: current free agents that actively resolve to deployed `FA_PROD_MULT_DATA`; kickers excluded.",
        "- Identity: stable Sleeper ID + position; team is only a duplicate-name disambiguator.",
        "- History: canonical 2025 shrinkage + durability component, unchanged.",
        "- Offense projection: 50/50 FantasyPros + Sleeper when both are available; one-source fallback otherwise.",
        "- IDP projection: canonical IDP V1 category ensemble.",
        "- History/forward blend: 45% / 55%.",
        "- Replacement ranks: QB18, RB32, WR36, TE15, DL32, LB32, DB32.",
        "- Transform: `clamp(-0.10 + 0.75 × ratio, 0.15, 1.55)`.",
        "",
        "## Primary gates",
        "",
        "| Gate | Result | Requirement |",
        "|---|---:|---:|",
        f"| Runtime FA-specific identity | {'PASS' if g['runtime_fa_specific_identity_exact']['pass'] else 'FAIL'} ({g['runtime_fa_specific_identity_exact']['mapped_unique_count']}/{g['runtime_fa_specific_identity_exact']['runtime_count']}) | exact |",
        f"| Reproducible active-cohort candidate coverage | {g['reproducible_candidate_coverage']['value']:.1%} ({g['reproducible_candidate_coverage']['numerator']}/{g['reproducible_candidate_coverage']['denominator']}) | ≥ {g['reproducible_candidate_coverage']['minimum']:.0%} |",
        f"| Offense FantasyPros coverage among Sleeper-covered active entries | {g['offense_fantasypros_coverage_vs_sleeper']['value']:.1%} ({g['offense_fantasypros_coverage_vs_sleeper']['numerator']}/{g['offense_fantasypros_coverage_vs_sleeper']['denominator']}) | ≥ {g['offense_fantasypros_coverage_vs_sleeper']['minimum']:.0%} |",
        f"| Replacement baselines present | {'PASS' if g['replacement_baselines_present']['pass'] else 'FAIL'} | all 7 positions |",
        "",
        "## Cohort",
        "",
        f"- `FA_PROD_MULT_DATA` entries including kickers: **{c['fa_prod_entries_total_including_k']}**",
        f"- Current free agents in committed Sleeper snapshot: **{c['current_free_agents_file_count']}**",
        f"- Runtime FA-specific non-K cohort: **{c['active_non_k_deployed_entries']}**",
        f"- Mapped active entries: **{c['mapped_active_non_k_entries']}**",
        f"- Reproducible candidates: **{c['reproducible_candidates']}**",
        f"- Production files mutated: **0**",
        "",
        "## Replacement anchors",
        "",
        "| Pos | Rank | Anchor | Combined points | Cohort |",
        "|---|---:|---|---:|---:|",
    ]
    for pos in TRACKED:
        b = r["phase1_baselines"][pos]
        lines.append(f"| {pos} | {b['rank']} | {b['player']} | {b['combined_points']:.2f} | {b['cohort_size']} |")

    lines += [
        "",
        "## Largest raw production-multiplier differences",
        "",
        "These are diagnostics only, not deployment recommendations.",
        "",
        "| Player | Pos | Deployed | Phase-1 candidate | Delta | Source |",
        "|---|---|---:|---:|---:|---|",
    ]
    for m in r["largest_absolute_prod_movers"][:15]:
        lines.append(
            f"| {m['name']} | {m['pos']} | {m['deployed_prod']:.3f} | {m['candidate_prod']:.3f} | {m['delta']:+.3f} | {m['forward_source']} |"
        )

    lines += [
        "",
        "## Decision semantics",
        "",
        "A PASS freezes only the lineage/candidate construction and permits a separate shadow-validation preregistration. It does **not** authorize a production change.",
        "",
        "A STOP means source/identity coverage must be repaired before any model selection or production consideration.",
        "",
    ]
    return "\n".join(lines)


def round_floats(obj, digits=9):
    if isinstance(obj, dict):
        return {k: round_floats(v, digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_floats(v, digits) for v in obj]
    if isinstance(obj, float):
        return round(obj, digits)
    return obj


def write_outputs():
    result = round_floats(build_result())
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(build_markdown(result) + "\n", encoding="utf-8")
    manifest = {
        "study_id": result["study_id"],
        "phase": 1,
        "repo_commit_sha": result["repo_commit_sha"],
        "decision": result["decision"],
        "production_change_authorized": False,
        "frozen_methodology": result["methodology"],
        "gates": result["gates"],
        "input_sha256": result["input_sha256"],
        "output_sha256": {
            str(OUT_JSON.relative_to(ROOT)): sha256(OUT_JSON),
            str(OUT_MD.relative_to(ROOT)): sha256(OUT_MD),
            str(SCRIPT.relative_to(ROOT)): sha256(SCRIPT),
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision": result["decision"],
        "active_non_k": result["counts"]["active_non_k_deployed_entries"],
        "reproducible_candidates": result["counts"]["reproducible_candidates"],
        "coverage": result["gates"]["reproducible_candidate_coverage"]["value"],
        "offense_fp_share": result["gates"]["offense_fantasypros_coverage_vs_sleeper"]["value"],
    }, indent=2))


def selftest():
    assert norm_name("D.J. Reed") == "dj reed"
    assert norm_name("A.J.-Brown") == "ajbrown"
    assert clamp(-5, PM_MIN, PM_MAX) == PM_MIN
    assert clamp(5, PM_MIN, PM_MAX) == PM_MAX
    sample = (
        "const FA_PROD_MULT_DATA = {"
        "'same name':[{prod:0.3,pos:'RB',team:'ARI'}],"
        "/* expanded coverage added 2026-08-20 */"
        "'legacy numeric':{prod:01,pos:'WR',team:'TST'}"
        "};"
    )
    parsed = eval_js_const_object(sample, "FA_PROD_MULT_DATA")
    assert parsed["same name"][0]["pos"] == "RB"
    assert parsed["legacy numeric"]["prod"] == 1
    assert HISTORY_WEIGHT + FORWARD_WEIGHT == 1.0
    assert PM_RATIO_SLOPE == 0.75
    assert REPLACEMENT_RANK == {
        "QB": 18, "RB": 32, "WR": 36, "TE": 15,
        "DL": 32, "LB": 32, "DB": 32,
    }
    print("Free-Agent Production V2 Phase 1 self-test PASS")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if args.write:
        write_outputs()
        return
    ap.error("choose --selftest or --write")


if __name__ == "__main__":
    main()
