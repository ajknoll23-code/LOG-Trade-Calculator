#!/usr/bin/env python3
"""Draft Pick FV V6.1 Phase 4: LOYO development selection.

Reads only the frozen 2018-2023 DOB-repaired development corpus.
The 2024 temporal holdout pick corpus and its outcomes are forbidden inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix, csr_matrix, vstack

ROOT = Path.cwd()
V6 = ROOT / "research" / "draft-pick-fv-v6"

PREREG = V6 / "structural_continuity_preregistration_v6.json"
P2_SUM = V6 / "r1_r4_source_identity_summary_v6_1.json"
P2_MAN = V6 / "r1_r4_source_identity_manifest_v6_1.json"
REPAIR_SUM = V6 / "r1_r4_dob_repair_summary_v6_1.json"
REPAIR_MAN = V6 / "r1_r4_dob_repair_manifest_v6_1.json"
DEV = V6 / "r1_r4_development_outcomes_dob_repaired_v6_1.jsonl"
CONTRACT = V6 / "r1_r4_phase4_metric_implementation_contract_v6_1.json"
CONTRACT_MAN = V6 / "r1_r4_phase4_metric_implementation_contract_manifest_v6_1.json"
SOLVER_ERRATUM = V6 / "r1_r4_phase4_solver_erratum_v6_1.json"
SOLVER_ERRATUM_MAN = V6 / "r1_r4_phase4_solver_erratum_manifest_v6_1.json"

OUT_SCRIPT = V6 / "fit_r1_r4_loyo_candidates_v6_1.py"
OUT_RESULT = V6 / "r1_r4_loyo_development_selection_v6_1.json"
OUT_BOOT = V6 / "r1_r4_loyo_bootstrap_v6_1.json"
OUT_CAND = V6 / "r1_r4_frozen_development_candidate_v6_1.json"
OUT_MD = V6 / "r1_r4_loyo_development_selection_v6_1.md"
OUT_MAN = V6 / "r1_r4_loyo_development_selection_manifest_v6_1.json"

YEARS = (2018, 2019, 2020, 2021, 2022, 2023)
TIERS = ("early", "mid", "late")
CELLS = tuple(f"r{r}_{t}" for r in range(1, 5) for t in TIERS)
ALPHAS = (3, 6, 12, 24, 48, 96, 192)
WINNER_ORDER = (
    "C1_ROUNDWISE_RESCALE_R1_R4",
    "C2_ANCHORED_ADDITIVE_ROUND_TIER_CURVE",
    "C3_SHRUNK_MONOTONE_SLOT_CURVE_R1_R4",
)
ALL_CANDIDATES = (
    "C0_DEPLOYED",
    *WINNER_ORDER,
    "D1_BOUNDARY_FREE_ROUNDWISE_DIAGNOSTIC",
)
BOOT_REPS = 10000
BOOT_SEED = 20260923
BOUND_REL_TOL = 1e-6
LP_OBJ_TOL_REL = 1e-9
# Numerical fixation band for a lexicographically resolved parameter.
# This is deliberately tighter than the preregistered hard-bound gate
# tolerance (1e-6 relative) and only prevents exact binary-float pinning
# from making the next HiGHS solve spuriously infeasible.
LEX_FIX_REL_TOL = 5e-8
LEX_FIX_ABS_TOL = 5e-7
EPS = 1e-12


class GateError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(obj: Any) -> str:
    raw = json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GateError(f"{path}:{n}: invalid JSONL") from exc
            if not isinstance(obj, dict):
                raise GateError(f"{path}:{n}: row not object")
            rows.append(obj)
    return rows


def write_json(path: Path, obj: Any) -> None:
    path.write_text(
        json.dumps(clean(obj), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def finite(v: Any) -> bool:
    return (
        isinstance(v, (int, float))
        and not isinstance(v, bool)
        and math.isfinite(float(v))
    )


def clean(obj: Any) -> Any:
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise GateError("non-finite result")
        return round(obj, 10)
    if isinstance(obj, np.floating):
        return clean(float(obj))
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    return obj


def outcome(row: dict[str, Any], horizon: str, field: str) -> float | None:
    h = row.get(horizon)
    if not isinstance(h, dict):
        return None
    v = h.get(field)
    return float(v) if finite(v) else None


def cell_round(cell: str) -> int:
    return int(cell[1])


def cell_tier(cell: str) -> str:
    return cell.split("_", 1)[1]


def baseline_cells(pre: dict[str, Any]) -> dict[str, float]:
    table = pre["frozen_deployed_baseline"]["pick_base_2027"]
    return {
        f"r{r}_{t}": float(table[str(r)][t])
        for r in range(1, 7)
        for t in TIERS
    }


def full_table_from_cells(
    pre: dict[str, Any],
    fitted_r1_r4: dict[str, float],
) -> dict[str, dict[str, float]]:
    base = pre["frozen_deployed_baseline"]["pick_base_2027"]
    out = {
        str(r): {t: float(base[str(r)][t]) for t in TIERS}
        for r in range(1, 7)
    }
    for cell, value in fitted_r1_r4.items():
        out[str(cell_round(cell))][cell_tier(cell)] = float(value)
    return out


def structural(
    pre: dict[str, Any],
    fitted_r1_r4: dict[str, float],
    *,
    boundary_required: bool,
) -> dict[str, Any]:
    table = full_table_from_cells(pre, fitted_r1_r4)
    seq = [
        table[str(r)][t]
        for r in range(1, 7)
        for t in TIERS
    ]
    positive = all(v > 0 for v in seq)
    mono_all = all(seq[i] >= seq[i + 1] - 1e-8 for i in range(17))
    mono_except_r4r5 = all(
        seq[i] >= seq[i + 1] - 1e-8
        for i in range(17)
        if i != 11
    )
    r5r6 = all(
        table[str(r)][t]
        == float(pre["frozen_deployed_baseline"]["pick_base_2027"][str(r)][t])
        for r in (5, 6)
        for t in TIERS
    )
    r4_anchor = table["4"]["late"] >= 1414.0 - 1e-8
    return {
        "all_18_positive": positive,
        "all_18_monotone_nonincreasing": mono_all,
        "all_monotone_except_optional_r4_r5_boundary": mono_except_r4r5,
        "r5_r6_unchanged": r5r6,
        "r4_late_ge_1414": r4_anchor,
        "structural_gate_pass": (
            positive
            and r5r6
            and mono_except_r4r5
            and (r4_anchor if boundary_required else True)
            and (mono_all if boundary_required else True)
        ),
        "spliced_pick_base": table,
    }


def guard_contract() -> dict[str, Any]:
    pre = load(PREREG)
    p2s = load(P2_SUM)
    p2m = load(P2_MAN)
    rs = load(REPAIR_SUM)
    rm = load(REPAIR_MAN)
    contract = load(CONTRACT)
    cm = load(CONTRACT_MAN)
    solver_erratum = load(SOLVER_ERRATUM)
    solver_erratum_m = load(SOLVER_ERRATUM_MAN)

    if pre["status"] != "FROZEN_PRE_V6_R3_R4_OUTCOME_ACCESS":
        raise GateError("V6 preregistration drift")
    if rm["decision"] != (
        "PASS_V6_1_PHASE3_1_DOB_REPAIR_"
        "DEVELOPMENT_SELECTION_AUTHORIZED_NEXT_STAGE"
    ):
        raise GateError("Phase 3.1 did not authorize Phase 4")
    if rm["readiness_gate_pass"] is not True:
        raise GateError("Phase 3.1 readiness gate drift")
    if rm["development_selection_authorized_next_stage"] is not True:
        raise GateError("Phase 4 not authorized")
    if rs["next_stage"] != "draft-pick-fv-v6-phase4-loyo-development-selection":
        raise GateError("Phase 3.1 next-stage drift")
    if rm["output_hashes"][DEV.name] != sha(DEV):
        raise GateError("DOB-repaired development corpus hash drift")
    if rs["input_development_occurrence_n"] != 17915:
        raise GateError("development denominator drift")
    if rs["holdout_2024_pick_identity_file_read"] is not False:
        raise GateError("2024 holdout firewall drift")
    if rs["holdout_2024_rookie_outcomes_scored"] is not False:
        raise GateError("2024 holdout outcome firewall drift")
    for obj in (rs, rm):
        for key in (
            "candidate_fit_performed",
            "candidate_scores_computed",
            "candidate_selection_performed",
            "production_change_authorized",
        ):
            if obj[key] is not False:
                raise GateError(f"pre-Phase4 firewall drift: {key}")

    if p2m["development_source_gate_pass"] is not True:
        raise GateError("Phase 2 development source gate drift")
    if p2m["holdout_2024_source_gate_pass"] is not True:
        raise GateError("Phase 2 holdout source gate drift")
    if p2m["holdout_2024_outcome_ingestion_authorized"] is not False:
        raise GateError("2024 holdout ingestion unexpectedly authorized")
    if p2s["development_source_gate"]["overall_identity_coverage"] < 0.95:
        raise GateError("development identity coverage drift")

    expected_decision = (
        "FREEZE_V6_1_PHASE4_IMPLEMENTATION_CONTRACT_"
        "LOYO_SELECTION_AUTHORIZED"
    )
    if contract["decision"] != expected_decision or cm["decision"] != expected_decision:
        raise GateError("Phase 4 implementation contract drift")
    if cm["candidate_scores_computed"] is not False:
        raise GateError("implementation contract already scored candidates")

    expected_erratum = "FREEZE_V6_1_PHASE4_SOLVER_ERRATUM_RERUN_AUTHORIZED"
    if solver_erratum["decision"] != expected_erratum:
        raise GateError("Phase 4 solver erratum drift")
    if solver_erratum_m["decision"] != expected_erratum:
        raise GateError("Phase 4 solver erratum manifest drift")
    if solver_erratum["scientific_contract_changed"] is not False:
        raise GateError("solver erratum changed scientific contract")
    numerical = solver_erratum["numerical_remedy"]
    if float(numerical["lex_fix_relative_tolerance"]) != LEX_FIX_REL_TOL:
        raise GateError("solver erratum relative tolerance drift")
    if float(numerical["lex_fix_absolute_tolerance"]) != LEX_FIX_ABS_TOL:
        raise GateError("solver erratum absolute tolerance drift")
    if numerical["primary_LAD_objective_or_face_changed"] is not False:
        raise GateError("solver erratum changed LAD objective face")
    if solver_erratum["phase4_selection_outputs_committed"] is not False:
        raise GateError("solver erratum incorrectly claims Phase 4 outputs")

    impl = contract["implementation"]
    required = {
        "c3_alpha_pseudodraft_formula",
        "bootstrap_evaluation",
        "boundary_saturation_gate_resolution",
        "loyo_metric_weighting",
        "h2_h4_matching",
        "o1_shape_scoring",
        "lp_tie_break",
    }
    if not required <= set(impl):
        raise GateError("Phase 4 implementation contract incomplete")

    ds = pre["development_selection"]
    if ds["bootstrap"]["replicates"] != BOOT_REPS:
        raise GateError("bootstrap replicate drift")
    if ds["bootstrap"]["seed"] != BOOT_SEED:
        raise GateError("bootstrap seed drift")
    if tuple(pre["candidate_families"][
        "C3_SHRUNK_MONOTONE_SLOT_CURVE_R1_R4"
    ]["alpha_grid"]) != ALPHAS:
        raise GateError("C3 alpha grid drift")

    return {
        "pre": pre,
        "p2s": p2s,
        "p2m": p2m,
        "rs": rs,
        "rm": rm,
        "contract": contract,
        "cm": cm,
        "solver_erratum": solver_erratum,
        "solver_erratum_m": solver_erratum_m,
    }


def validate_rows(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 17915:
        raise GateError(f"expected 17915 rows, got {len(rows)}")
    seen = set()
    for r in rows:
        y = int(r["draft_year"])
        cell = str(r["cell"])
        if y not in YEARS or cell not in CELLS:
            raise GateError(f"invalid development row {y}/{cell}")
        if r.get("split") != "development":
            raise GateError("non-development split")
        key = (y, str(r["league_id"]), int(r["overall_slot"]))
        if key in seen:
            raise GateError(f"duplicate occurrence {key}")
        seen.add(key)
        w = r.get("cell_weight_v6_1")
        if not finite(w) or float(w) <= 0:
            raise GateError("invalid frozen cell weight")
        if r.get("primary_o2_ready") is True:
            if outcome(r, "H3", "O2") is None:
                raise GateError("primary_o2_ready row missing H3 O2")
            if not r.get("stable_player_key"):
                raise GateError("O2-ready row missing stable player cluster key")


def weighted_rows(
    rows: list[dict[str, Any]],
    years: tuple[int, ...],
    horizon: str,
    field: str,
    *,
    require_h3_o2: bool = False,
) -> list[dict[str, Any]]:
    chosen = []
    sums = defaultdict(float)
    counts = defaultdict(int)
    yset = set(years)
    for r in rows:
        y = int(r["draft_year"])
        if y not in yset:
            continue
        h = r.get(horizon)
        if not isinstance(h, dict) or h.get("mature") is not True:
            continue
        val = outcome(r, horizon, field)
        if val is None:
            continue
        if require_h3_o2 and outcome(r, "H3", "O2") is None:
            continue
        if horizon == "H3" and field == "O2" and r.get("primary_o2_ready") is not True:
            continue
        key = (y, str(r["cell"]))
        w = float(r["cell_weight_v6_1"])
        sums[key] += w
        counts[key] += 1
        x = dict(r)
        x["_target"] = val
        x["_raw_w"] = w
        chosen.append(x)

    for y in years:
        for cell in CELLS:
            if counts[(y, cell)] <= 0 or sums[(y, cell)] <= 0:
                raise GateError(
                    f"zero support {horizon}/{field} {y}:{cell}"
                )
    share = 1.0 / len(years) / len(CELLS)
    check = defaultdict(float)
    for x in chosen:
        key = (int(x["draft_year"]), str(x["cell"]))
        x["_w"] = share * x["_raw_w"] / sums[key]
        check[key] += x["_w"]
    for y in years:
        for cell in CELLS:
            if not math.isclose(
                check[(y, cell)], share, rel_tol=0, abs_tol=1e-12
            ):
                raise GateError(f"weight normalization failure {y}:{cell}")
    return chosen


def c0_values(pre: dict[str, Any]) -> dict[str, float]:
    base = baseline_cells(pre)
    return {c: base[c] for c in CELLS}


def fit_lad(
    rows: list[dict[str, Any]],
    param_names: tuple[str, ...],
    param_bounds: tuple[tuple[float, float], ...],
    coeff_fn: Callable[[dict[str, Any]], np.ndarray],
    structural_A: list[list[float]],
    structural_b: list[float],
) -> tuple[dict[str, float], float]:
    """Exact weighted LAD LP using a sparse constraint matrix.

    Each observation contributes only p parameter coefficients plus one
    residual coefficient, so dense construction would be wasteful at the
    real ~18k-occurrence scale.
    """
    p = len(param_names)
    n = len(rows)
    c = np.zeros(p + n, dtype=float)
    for i, r in enumerate(rows):
        c[p + i] = float(r["_w"])

    rr: list[int] = []
    cc: list[int] = []
    dd: list[float] = []
    bub: list[float] = []
    rowno = 0

    for i, r in enumerate(rows):
        a = np.asarray(coeff_fn(r), dtype=float)
        if a.shape != (p,):
            raise GateError("coefficient shape mismatch")
        y = float(r["_target"])

        # prediction - residual <= y
        for j, val in enumerate(a):
            if val != 0.0:
                rr.append(rowno); cc.append(j); dd.append(float(val))
        rr.append(rowno); cc.append(p + i); dd.append(-1.0)
        bub.append(y)
        rowno += 1

        # -prediction - residual <= -y
        for j, val in enumerate(a):
            if val != 0.0:
                rr.append(rowno); cc.append(j); dd.append(float(-val))
        rr.append(rowno); cc.append(p + i); dd.append(-1.0)
        bub.append(-y)
        rowno += 1

    for a, b in zip(structural_A, structural_b):
        for j, val in enumerate(a):
            if float(val) != 0.0:
                rr.append(rowno); cc.append(j); dd.append(float(val))
        bub.append(float(b))
        rowno += 1

    A_base = coo_matrix(
        (np.asarray(dd, dtype=float), (rr, cc)),
        shape=(rowno, p + n),
    ).tocsr()
    b_base = np.asarray(bub, dtype=float)
    bounds = [tuple(map(float, b)) for b in param_bounds] + [(0, None)] * n

    res = linprog(
        c,
        A_ub=A_base,
        b_ub=b_base,
        bounds=bounds,
        method="highs",
    )
    if not res.success:
        raise GateError(f"LAD primary LP failed: {res.message}")
    optimum = float(res.fun)
    tol = LP_OBJ_TOL_REL * max(1.0, abs(optimum))

    # Deterministic lexicographic tie-break over numeric parameters.
    #
    # The first Phase-4 run established that pinning a previously resolved
    # floating-point value as an exact (v, v) HiGHS bound can make the next
    # solve numerically infeasible even though the previous solution itself
    # lies on the allowed LAD objective face. The frozen solver erratum
    # therefore represents each resolved parameter by a tiny symmetric
    # numerical fixation band, intersected with its original hard bounds.
    # This does not change the primary LAD objective or objective face.
    objective_row = csr_matrix(c.reshape(1, -1))
    A2 = vstack([A_base, objective_row], format="csr")
    b2 = np.concatenate([b_base, np.asarray([optimum + tol])])
    working_bounds = list(bounds)
    fixation = {}
    x = res.x.copy()
    for j in range(p):
        cj = np.zeros(p + n)
        cj[j] = 1.0
        fit = linprog(
            cj,
            A_ub=A2,
            b_ub=b2,
            bounds=working_bounds,
            method="highs",
        )
        if not fit.success:
            raise GateError(
                f"LAD lexicographic LP failed at {param_names[j]}: "
                f"{fit.message}"
            )
        val = float(fit.x[j])
        orig_lo, orig_hi = map(float, bounds[j])
        scale = max(
            1.0,
            abs(val),
            abs(orig_lo),
            abs(orig_hi),
            abs(orig_hi - orig_lo),
        )
        fix_tol = max(
            LEX_FIX_ABS_TOL,
            LEX_FIX_REL_TOL * scale,
        )
        lo = max(orig_lo, val - fix_tol)
        hi = min(orig_hi, val + fix_tol)
        if lo > hi:
            raise GateError(
                f"invalid numerical fixation band for {param_names[j]}"
            )
        working_bounds[j] = (lo, hi)
        fixation[param_names[j]] = {
            "lexicographic_minimum": val,
            "fixation_lower": lo,
            "fixation_upper": hi,
            "fixation_tolerance": fix_tol,
        }
        x = fit.x.copy()

    # One final feasibility solve using the original LAD objective over all
    # resolved fixation bands returns a jointly feasible deterministic point.
    final = linprog(
        c,
        A_ub=A2,
        b_ub=b2,
        bounds=working_bounds,
        method="highs",
    )
    if not final.success:
        raise GateError(
            "LAD final lexicographic fixation solve failed: "
            f"{final.message}"
        )
    x = final.x.copy()
    for j, name in enumerate(param_names):
        lo, hi = working_bounds[j]
        if not (float(lo) - 1e-10 <= float(x[j]) <= float(hi) + 1e-10):
            raise GateError(
                f"final parameter escaped fixation band: {name}"
            )

    final_obj = float(np.dot(c, x))
    if final_obj > optimum + tol + 1e-8:
        raise GateError("lexicographic solution exceeded objective tolerance")
    return (
        {name: float(x[i]) for i, name in enumerate(param_names)},
        optimum,
    )
def c1_fit(
    rows: list[dict[str, Any]],
    pre: dict[str, Any],
    *,
    enforce_r4_anchor: bool,
) -> dict[str, Any]:
    fam = pre["candidate_families"]["C1_ROUNDWISE_RESCALE_R1_R4"]
    names = ("k1", "k2", "k3", "k4")
    bounds = tuple(tuple(map(float, fam["bounds"][n])) for n in names)
    base = c0_values(pre)

    def coeff(r):
        a = np.zeros(4)
        rnd = cell_round(str(r["cell"]))
        a[rnd - 1] = base[str(r["cell"])]
        return a

    A = []
    b = []
    # Cross-round monotonic boundaries.
    A.append([-base["r1_late"], base["r2_early"], 0, 0]); b.append(0)
    A.append([0, -base["r2_late"], base["r3_early"], 0]); b.append(0)
    A.append([0, 0, -base["r3_late"], base["r4_early"]]); b.append(0)
    if enforce_r4_anchor:
        A.append([0, 0, 0, -base["r4_late"]]); b.append(-1414.0)

    params, obj = fit_lad(rows, names, bounds, coeff, A, b)
    vals = {
        cell: base[cell] * params[f"k{cell_round(cell)}"]
        for cell in CELLS
    }
    return {
        "parameters": params,
        "r1_r4_values": vals,
        "training_weighted_mae": obj,
        "structural": structural(
            pre, vals, boundary_required=enforce_r4_anchor
        ),
    }


def c2_coeff(cell: str) -> np.ndarray:
    rnd = cell_round(cell)
    tier = cell_tier(cell)
    return np.asarray([
        1.0,
        -1.0 if rnd >= 2 else 0.0,
        -float(max(rnd - 2, 0)),
        -1.0 if tier == "mid" else 0.0,
        -1.0 if tier == "late" else 0.0,
    ])


def c2_values(params: dict[str, float]) -> dict[str, float]:
    p = np.asarray([
        params["A"],
        params["s12"],
        params["s34"],
        params["mid_penalty"],
        params["late_penalty"],
    ])
    return {cell: float(c2_coeff(cell) @ p) for cell in CELLS}


def c2_fit(rows: list[dict[str, Any]], pre: dict[str, Any]) -> dict[str, Any]:
    fam = pre["candidate_families"][
        "C2_ANCHORED_ADDITIVE_ROUND_TIER_CURVE"
    ]
    names = ("A", "s12", "s34", "mid_penalty", "late_penalty")
    bounds = tuple(tuple(map(float, fam["bounds"][n])) for n in names)

    def coeff(r):
        return c2_coeff(str(r["cell"]))

    # mid <= late; late <= s12; late <= s34; R4 late >= 1414.
    A = [
        [0, 0, 0, 1, -1],
        [0, -1, 0, 0, 1],
        [0, 0, -1, 0, 1],
        [-1, 1, 2, 0, 1],
    ]
    b = [0, 0, 0, -1414.0]
    params, obj = fit_lad(rows, names, bounds, coeff, A, b)
    vals = c2_values(params)
    return {
        "parameters": params,
        "r1_r4_values": vals,
        "training_weighted_mae": obj,
        "structural": structural(pre, vals, boundary_required=True),
    }


def pava_decreasing(
    values: list[float],
    weights: list[float],
    lower: float,
) -> list[float]:
    blocks = []
    for i, (v, w) in enumerate(zip(values, weights)):
        if w <= 0:
            raise GateError("nonpositive PAVA weight")
        blocks.append([i, i, float(w), float(v)])
        while len(blocks) >= 2 and blocks[-2][3] < blocks[-1][3] - 1e-12:
            b2 = blocks.pop()
            b1 = blocks.pop()
            wt = b1[2] + b2[2]
            mean = (b1[2] * b1[3] + b2[2] * b2[3]) / wt
            blocks.append([b1[0], b2[1], wt, mean])
    out = [0.0] * len(values)
    for start, end, _w, mean in blocks:
        m = max(float(lower), float(mean))
        for i in range(start, end + 1):
            out[i] = m
    if not all(out[i] >= out[i + 1] - 1e-10 for i in range(len(out) - 1)):
        raise GateError("PAVA monotonicity failure")
    if min(out) < lower - 1e-10:
        raise GateError("PAVA lower-anchor failure")
    return out


def c3_from_train(
    rows: list[dict[str, Any]],
    train_years: tuple[int, ...],
    pre: dict[str, Any],
    alpha: int,
    *,
    c2_prior_fit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    c2 = c2_prior_fit if c2_prior_fit is not None else c2_fit(rows, pre)
    prior = c2["r1_r4_values"]

    # Year-balanced exact-slot means, with each year first normalized inside
    # a slot using the inherited league-balanced cell weights.
    by_year_slot = defaultdict(list)
    for r in rows:
        y = int(r["draft_year"])
        slot = int(r["overall_slot"])
        if y in train_years:
            by_year_slot[(y, slot)].append(r)

    slot_mean = {}
    nobs = {}
    shrunk = []
    pava_weights = []
    for slot in range(1, 49):
        year_means = []
        total_n = 0
        for y in train_years:
            xs = by_year_slot[(y, slot)]
            if not xs:
                raise GateError(f"C3 zero exact-slot support {y}/slot{slot}")
            sw = sum(float(x["_raw_w"]) for x in xs)
            if sw <= 0:
                raise GateError("C3 nonpositive slot weight")
            ym = sum(
                float(x["_raw_w"]) * float(x["_target"]) for x in xs
            ) / sw
            year_means.append(ym)
            total_n += len(xs)
        mean = sum(year_means) / len(year_means)
        slot_mean[slot] = mean
        nobs[slot] = total_n
        rnd = (slot - 1) // 12 + 1
        within = (slot - 1) % 12 + 1
        tier = "early" if within <= 4 else "mid" if within <= 8 else "late"
        cell = f"r{rnd}_{tier}"
        prior_v = prior[cell]
        sh = (total_n * mean + alpha * prior_v) / (total_n + alpha)
        shrunk.append(sh)
        pava_weights.append(float(total_n + alpha))

    slots = pava_decreasing(shrunk, pava_weights, 1414.0)
    vals = {}
    for r in range(1, 5):
        for tier, lo in (("early", 1), ("mid", 5), ("late", 9)):
            slot_ids = [
                (r - 1) * 12 + p
                for p in range(lo, lo + 4)
            ]
            vals[f"r{r}_{tier}"] = (
                sum(slots[s - 1] for s in slot_ids) / 4.0
            )
    return {
        "parameters": {
            "alpha": int(alpha),
            "c2_prior_parameters": c2["parameters"],
        },
        "r1_r4_values": vals,
        "exact_slot_values": {
            str(i + 1): slots[i] for i in range(48)
        },
        "year_balanced_exact_slot_means": {
            str(k): v for k, v in slot_mean.items()
        },
        "exact_slot_observed_draft_n": {
            str(k): int(v) for k, v in nobs.items()
        },
        "structural": structural(pre, vals, boundary_required=True),
    }


def fit_sample(
    all_rows: list[dict[str, Any]],
    years: tuple[int, ...],
) -> list[dict[str, Any]]:
    return weighted_rows(all_rows, years, "H3", "O2")


def mae_for_year(
    rows: list[dict[str, Any]],
    year: int,
    values: dict[str, float],
    *,
    horizon: str = "H3",
    require_h3_o2: bool = False,
) -> float:
    xs = weighted_rows(
        rows,
        (year,),
        horizon,
        "O2",
        require_h3_o2=require_h3_o2,
    )
    return sum(
        float(x["_w"])
        * abs(float(values[str(x["cell"])]) - float(x["_target"]))
        for x in xs
    )


def normalized_shape(values: dict[str, float]) -> dict[str, float]:
    m = sum(float(values[c]) for c in CELLS) / len(CELLS)
    if m <= 0:
        raise GateError("nonpositive shape mean")
    return {c: float(values[c]) / m for c in CELLS}


def o1_shape_error_for_year(
    rows: list[dict[str, Any]],
    year: int,
    values: dict[str, float],
) -> float:
    xs = weighted_rows(rows, (year,), "H3", "O1")
    by = defaultdict(float)
    wt = defaultdict(float)
    for x in xs:
        c = str(x["cell"])
        by[c] += float(x["_w"]) * float(x["_target"])
        wt[c] += float(x["_w"])
    target = {}
    for c in CELLS:
        if wt[c] <= 0:
            raise GateError(f"zero O1 cell weight {year}/{c}")
        target[c] = by[c] / wt[c]
    a = normalized_shape(target)
    b = normalized_shape(values)
    return sum(abs(a[c] - b[c]) for c in CELLS) / len(CELLS)


def score_fold_predictions(
    rows: list[dict[str, Any]],
    predictions: dict[str, dict[int, dict[str, float]]],
) -> dict[str, Any]:
    scores = {}
    for cid, by_year in predictions.items():
        h3_by = {
            str(y): mae_for_year(rows, y, by_year[y])
            for y in YEARS
        }
        h2_by = {
            str(y): mae_for_year(
                rows, y, by_year[y], horizon="H2", require_h3_o2=True
            )
            for y in YEARS
        }
        h4_by = {
            str(y): mae_for_year(
                rows, y, by_year[y], horizon="H4", require_h3_o2=True
            )
            for y in YEARS
            if y <= 2022
        }
        o1_by = {
            str(y): o1_shape_error_for_year(rows, y, by_year[y])
            for y in YEARS
        }
        scores[cid] = {
            "loyo_h3_o2_macro_mae": sum(h3_by.values()) / len(YEARS),
            "h3_o2_mae_by_heldout_class": h3_by,
            "loyo_h2_o2_macro_mae": sum(h2_by.values()) / len(h2_by),
            "h2_o2_mae_by_heldout_class": h2_by,
            "loyo_mature_h4_o2_macro_mae": sum(h4_by.values()) / len(h4_by),
            "mature_h4_o2_mae_by_heldout_class": h4_by,
            "loyo_h3_o1_normalized_shape_error": (
                sum(o1_by.values()) / len(o1_by)
            ),
            "h3_o1_shape_error_by_heldout_class": o1_by,
        }
    return scores


def at_bound(
    value: float,
    bounds: tuple[float, float],
) -> dict[str, Any]:
    lo, hi = map(float, bounds)
    scale = max(1.0, abs(lo), abs(hi), abs(hi - lo))
    tol = BOUND_REL_TOL * scale
    dlo = abs(float(value) - lo)
    dhi = abs(float(value) - hi)
    return {
        "value": float(value),
        "lower": lo,
        "upper": hi,
        "absolute_tolerance": tol,
        "at_lower": dlo <= tol,
        "at_upper": dhi <= tol,
        "at_hard_bound": dlo <= tol or dhi <= tol,
    }


def boundary_diagnostic(
    cid: str,
    fit: dict[str, Any],
    pre: dict[str, Any],
) -> dict[str, Any]:
    fams = pre["candidate_families"]
    if cid == "C1_ROUNDWISE_RESCALE_R1_R4":
        checks = {
            n: at_bound(
                fit["parameters"][n],
                tuple(fams[cid]["bounds"][n]),
            )
            for n in ("k1", "k2", "k3", "k4")
        }
        passed = not any(v["at_hard_bound"] for v in checks.values())
        return {"pass": passed, "parameter_checks": checks}
    if cid == "C2_ANCHORED_ADDITIVE_ROUND_TIER_CURVE":
        checks = {
            n: at_bound(
                fit["parameters"][n],
                tuple(fams[cid]["bounds"][n]),
            )
            for n in ("A", "s12", "s34", "mid_penalty", "late_penalty")
        }
        passed = not any(v["at_hard_bound"] for v in checks.values())
        return {"pass": passed, "parameter_checks": checks}
    if cid == "C3_SHRUNK_MONOTONE_SLOT_CURVE_R1_R4":
        prior = fit["parameters"]["c2_prior_parameters"]
        c2fam = fams["C2_ANCHORED_ADDITIVE_ROUND_TIER_CURVE"]
        checks = {
            n: at_bound(prior[n], tuple(c2fam["bounds"][n]))
            for n in ("A", "s12", "s34", "mid_penalty", "late_penalty")
        }
        alpha = int(fit["parameters"]["alpha"])
        edge = alpha in (ALPHAS[0], ALPHAS[-1])
        passed = (not edge) and not any(
            v["at_hard_bound"] for v in checks.values()
        )
        return {
            "pass": passed,
            "parameter_checks": checks,
            "selected_alpha": alpha,
            "alpha_grid_edge": edge,
        }
    raise GateError(f"boundary diagnostic unsupported candidate {cid}")


def bootstrap_draws(
    rows: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    rng = np.random.default_rng(BOOT_SEED)
    out = {}
    for y in YEARS:
        xs = [
            r for r in rows
            if int(r["draft_year"]) == y
            and r.get("primary_o2_ready") is True
            and outcome(r, "H3", "O2") is not None
        ]
        clusters = sorted({str(r["stable_player_key"]) for r in xs})
        cidx = {c: i for i, c in enumerate(clusters)}
        W = np.zeros((len(clusters), len(CELLS)))
        cell_idx = {c: i for i, c in enumerate(CELLS)}
        for r in xs:
            W[cidx[str(r["stable_player_key"])], cell_idx[str(r["cell"])]] += (
                float(r["cell_weight_v6_1"])
            )
        ncl = len(clusters)
        probs = np.full(ncl, 1.0 / ncl)
        accepted = []
        need = BOOT_REPS
        attempts = 0
        while need > 0:
            attempts += 1
            if attempts > 30:
                raise GateError(f"bootstrap valid-draw exhaustion for {y}")
            batch = max(need + 500, 2000)
            M = rng.multinomial(ncl, probs, size=batch)
            den = M @ W
            good = np.all(den > 0, axis=1)
            if np.any(good):
                take = M[good][:need]
                accepted.append(take)
                need -= len(take)
        M = np.vstack(accepted)[:BOOT_REPS]
        out[y] = {
            "clusters": clusters,
            "cluster_index": cidx,
            "W": W,
            "M": M,
            "valid_draw_n": int(M.shape[0]),
        }
    return out


def bootstrap_candidate(
    rows: list[dict[str, Any]],
    draws: dict[int, dict[str, Any]],
    pred: dict[int, dict[str, float]],
    c0: dict[str, float],
) -> dict[str, Any]:
    year_diffs = []
    ci = {c: i for i, c in enumerate(CELLS)}
    for y in YEARS:
        d = draws[y]
        ncl = len(d["clusters"])
        EC = np.zeros((ncl, len(CELLS)))
        E0 = np.zeros((ncl, len(CELLS)))
        for r in rows:
            if int(r["draft_year"]) != y:
                continue
            if r.get("primary_o2_ready") is not True:
                continue
            yy = outcome(r, "H3", "O2")
            if yy is None:
                continue
            i = d["cluster_index"][str(r["stable_player_key"])]
            j = ci[str(r["cell"])]
            w = float(r["cell_weight_v6_1"])
            EC[i, j] += w * abs(float(pred[y][str(r["cell"])]) - yy)
            E0[i, j] += w * abs(float(c0[str(r["cell"])]) - yy)
        M = d["M"]
        den = M @ d["W"]
        if np.any(den <= 0):
            raise GateError("bootstrap zero cell denominator")
        cand = (M @ EC) / den
        base = (M @ E0) / den
        year_diffs.append(np.mean(cand - base, axis=1))
    diffs = np.mean(np.vstack(year_diffs), axis=0)
    if len(diffs) != BOOT_REPS:
        raise GateError("bootstrap replicate count drift")
    return {
        "replicates": BOOT_REPS,
        "seed": BOOT_SEED,
        "paired": True,
        "cluster": "stable player identity within draft class",
        "quantity": "candidate minus C0 LOYO H3 O2 macro MAE",
        "mean_difference": float(np.mean(diffs)),
        "median_difference": float(np.median(diffs)),
        "one_sided_upper_95": float(
            np.quantile(diffs, 0.95, method="linear")
        ),
        "min": float(np.min(diffs)),
        "max": float(np.max(diffs)),
    }


def fit_fold_families(
    rows: list[dict[str, Any]],
    pre: dict[str, Any],
) -> tuple[
    dict[str, dict[int, dict[str, float]]],
    dict[str, dict[int, Any]],
    dict[str, Any],
]:
    preds = {
        cid: {} for cid in ALL_CANDIDATES
    }
    fits = {
        cid: {} for cid in ALL_CANDIDATES
        if cid != "C0_DEPLOYED"
    }
    c0 = c0_values(pre)
    for y in YEARS:
        preds["C0_DEPLOYED"][y] = dict(c0)

    # C1/C2/D1 are fit independently in each LOYO fold.
    for hold in YEARS:
        train = tuple(y for y in YEARS if y != hold)
        sample = fit_sample(rows, train)
        c1 = c1_fit(sample, pre, enforce_r4_anchor=True)
        c2 = c2_fit(sample, pre)
        d1 = c1_fit(sample, pre, enforce_r4_anchor=False)
        for cid, fit in (
            ("C1_ROUNDWISE_RESCALE_R1_R4", c1),
            ("C2_ANCHORED_ADDITIVE_ROUND_TIER_CURVE", c2),
            ("D1_BOUNDARY_FREE_ROUNDWISE_DIAGNOSTIC", d1),
        ):
            fits[cid][hold] = fit
            preds[cid][hold] = fit["r1_r4_values"]

    # C3 alpha is selected globally by six-fold LOYO H3 O2 MAE.
    # Reuse the already-fitted fold-specific C2 prior across every alpha;
    # alpha changes only the deterministic shrinkage/PAVA step.
    alpha_results = {}
    alpha_fold_fits = {}
    for alpha in ALPHAS:
        alpha_fold_fits[alpha] = {}
        alpha_pred = {}
        for hold in YEARS:
            train = tuple(y for y in YEARS if y != hold)
            sample = fit_sample(rows, train)
            fit = c3_from_train(
                sample,
                train,
                pre,
                alpha,
                c2_prior_fit=fits[
                    "C2_ANCHORED_ADDITIVE_ROUND_TIER_CURVE"
                ][hold],
            )
            alpha_fold_fits[alpha][hold] = fit
            alpha_pred[hold] = fit["r1_r4_values"]
        h3 = {
            str(y): mae_for_year(rows, y, alpha_pred[y])
            for y in YEARS
        }
        alpha_results[alpha] = {
            "loyo_h3_o2_macro_mae": sum(h3.values()) / len(YEARS),
            "by_heldout_class": h3,
        }
    best = min(
        alpha_results[a]["loyo_h3_o2_macro_mae"] for a in ALPHAS
    )
    near = [
        a for a in ALPHAS
        if alpha_results[a]["loyo_h3_o2_macro_mae"]
        <= best * 1.01 + EPS
    ]
    selected_alpha = max(near)
    fits["C3_SHRUNK_MONOTONE_SLOT_CURVE_R1_R4"] = (
        alpha_fold_fits[selected_alpha]
    )
    for hold in YEARS:
        preds["C3_SHRUNK_MONOTONE_SLOT_CURVE_R1_R4"][hold] = (
            alpha_fold_fits[selected_alpha][hold]["r1_r4_values"]
        )

    alpha_diag = {
        "grid": list(ALPHAS),
        "results": {str(a): alpha_results[a] for a in ALPHAS},
        "best_macro_mae": best,
        "within_1pct_of_best": near,
        "selected_alpha": selected_alpha,
        "selected_alpha_is_grid_edge": selected_alpha in (ALPHAS[0], ALPHAS[-1]),
    }
    return preds, fits, alpha_diag


def full_data_diagnostics(
    rows: list[dict[str, Any]],
    pre: dict[str, Any],
    selected_alpha: int,
) -> dict[str, Any]:
    sample = fit_sample(rows, YEARS)
    c1 = c1_fit(sample, pre, enforce_r4_anchor=True)
    c2 = c2_fit(sample, pre)
    d1 = c1_fit(sample, pre, enforce_r4_anchor=False)
    c3 = c3_from_train(
        sample,
        YEARS,
        pre,
        selected_alpha,
        c2_prior_fit=c2,
    )
    return {
        "C1_ROUNDWISE_RESCALE_R1_R4": c1,
        "C2_ANCHORED_ADDITIVE_ROUND_TIER_CURVE": c2,
        "C3_SHRUNK_MONOTONE_SLOT_CURVE_R1_R4": c3,
        "D1_BOUNDARY_FREE_ROUNDWISE_DIAGNOSTIC": d1,
    }


def select_and_refit(
    rows: list[dict[str, Any]],
    pre: dict[str, Any],
    eligibility: dict[str, Any],
    scores: dict[str, Any],
    selected_alpha: int,
) -> tuple[str | None, dict[str, Any] | None]:
    eligible = [
        cid for cid in WINNER_ORDER
        if eligibility[cid]["eligible"]
    ]
    if not eligible:
        return None, None
    best = min(scores[c]["loyo_h3_o2_macro_mae"] for c in eligible)
    near = [
        c for c in eligible
        if scores[c]["loyo_h3_o2_macro_mae"] <= best * 1.01 + EPS
    ]
    order = {c: i for i, c in enumerate(WINNER_ORDER)}
    near.sort(key=lambda c: order[c])
    selected = near[0]

    # Final parameter fit occurs once, after family selection.
    sample = fit_sample(rows, YEARS)
    if selected == "C1_ROUNDWISE_RESCALE_R1_R4":
        fit = c1_fit(sample, pre, enforce_r4_anchor=True)
    elif selected == "C2_ANCHORED_ADDITIVE_ROUND_TIER_CURVE":
        fit = c2_fit(sample, pre)
    elif selected == "C3_SHRUNK_MONOTONE_SLOT_CURVE_R1_R4":
        fit = c3_from_train(sample, YEARS, pre, selected_alpha)
    else:
        raise GateError("unknown selected family")
    return selected, fit


def main_fit() -> None:
    state = guard_contract()
    pre = state["pre"]
    rows = read_jsonl(DEV)
    validate_rows(rows)

    preds, fold_fits, alpha_diag = fit_fold_families(rows, pre)
    scores = score_fold_predictions(rows, preds)
    c0s = scores["C0_DEPLOYED"]

    # Freeze boundary-saturation diagnostics from deterministic all-development
    # fits for all families.  These diagnostics are used only for the
    # preregistered boundary gate, never for performance ranking.
    full_diag = full_data_diagnostics(
        rows, pre, int(alpha_diag["selected_alpha"])
    )
    boundary = {
        cid: boundary_diagnostic(cid, full_diag[cid], pre)
        for cid in WINNER_ORDER
    }

    draws = bootstrap_draws(rows)
    bootstrap = {
        cid: bootstrap_candidate(
            rows, draws, preds[cid], c0_values(pre)
        )
        for cid in WINNER_ORDER
    }

    p2s = state["p2s"]
    identity_overall = float(
        p2s["development_source_gate"]["overall_identity_coverage"]
    )
    p2_cells = p2s["development_source_gate"]["cell_year"]
    all_retention = all(
        float(v["retention_fraction"]) >= 0.95 - EPS
        for v in p2_cells.values()
    )
    all_identity = all(
        float(v["identity_coverage"]) >= 0.95 - EPS
        for v in p2_cells.values()
    )

    eligibility = {}
    eligible_ids = []
    for cid in WINNER_ORDER:
        s = scores[cid]
        improvement = (
            c0s["loyo_h3_o2_macro_mae"] - s["loyo_h3_o2_macro_mae"]
        ) / c0s["loyo_h3_o2_macro_mae"]
        year_rel = {
            str(y): (
                s["h3_o2_mae_by_heldout_class"][str(y)]
                - c0s["h3_o2_mae_by_heldout_class"][str(y)]
            ) / c0s["h3_o2_mae_by_heldout_class"][str(y)]
            for y in YEARS
        }
        improved_n = sum(v < 0 for v in year_rel.values())
        worst_reg = max(year_rel.values())
        o1_rel = (
            s["loyo_h3_o1_normalized_shape_error"]
            / c0s["loyo_h3_o1_normalized_shape_error"]
            - 1.0
        )
        h2_rel = (
            s["loyo_h2_o2_macro_mae"]
            / c0s["loyo_h2_o2_macro_mae"]
            - 1.0
        )
        h4_rel = (
            s["loyo_mature_h4_o2_macro_mae"]
            / c0s["loyo_mature_h4_o2_macro_mae"]
            - 1.0
        )
        struct_all = all(
            fold_fits[cid][y]["structural"]["structural_gate_pass"]
            for y in YEARS
        )
        full_struct = full_diag[cid]["structural"]
        gates = {
            "loyo_h3_o2_improvement_ge_5pct": improvement >= 0.05 - EPS,
            "improves_at_least_5_of_6_heldout_classes": improved_n >= 5,
            "worst_heldout_class_relative_regression_le_10pct":
                worst_reg <= 0.10 + EPS,
            "paired_cluster_bootstrap_upper95_lt_0":
                bootstrap[cid]["one_sided_upper_95"] < 0.0,
            "h3_o1_shape_regression_vs_C0_le_2pct": o1_rel <= 0.02 + EPS,
            "h2_o2_regression_vs_C0_le_2pct": h2_rel <= 0.02 + EPS,
            "mature_h4_o2_regression_vs_C0_le_2pct": h4_rel <= 0.02 + EPS,
            "all_folds_structurally_valid": struct_all,
            "all_18_positive": full_struct["all_18_positive"] is True,
            "all_18_monotone_nonincreasing":
                full_struct["all_18_monotone_nonincreasing"] is True,
            "r5_r6_exactly_unchanged": full_struct["r5_r6_unchanged"] is True,
            "r4_late_ge_1414": full_struct["r4_late_ge_1414"] is True,
            "development_occurrence_identity_ge_95pct":
                identity_overall >= 0.95 - EPS,
            "every_development_year_cell_retention_ge_95pct": all_retention,
            "every_development_year_cell_identity_ge_95pct": all_identity,
            "no_forbidden_outcome_market_vote_leakage": (
                state["rs"]["market_or_ktc_values_read"] is False
                and state["rs"]["package_vote_data_read"] is False
                and state["rs"]["holdout_2024_pick_identity_file_read"] is False
                and state["rs"]["holdout_2024_rookie_outcomes_scored"] is False
            ),
            "no_hard_numeric_bound_saturation":
                boundary[cid]["pass"] is True,
        }
        if cid == "C3_SHRUNK_MONOTONE_SLOT_CURVE_R1_R4":
            gates["c3_selected_alpha_not_grid_edge"] = (
                int(alpha_diag["selected_alpha"]) not in (3, 192)
            )
        passed = all(gates.values())
        eligibility[cid] = {
            "eligible": passed,
            "loyo_h3_o2_improvement_vs_C0": improvement,
            "heldout_class_relative_mae_vs_C0": year_rel,
            "improved_heldout_class_n": improved_n,
            "worst_heldout_class_relative_regression": worst_reg,
            "o1_shape_relative_regression_vs_C0": o1_rel,
            "h2_o2_relative_regression_vs_C0": h2_rel,
            "mature_h4_o2_relative_regression_vs_C0": h4_rel,
            "bootstrap": bootstrap[cid],
            "boundary_saturation": boundary[cid],
            "gates": gates,
        }
        if passed:
            eligible_ids.append(cid)

    selected, final_fit = select_and_refit(
        rows,
        pre,
        eligibility,
        scores,
        int(alpha_diag["selected_alpha"]),
    )

    # Determinism proof: selected final refit must match the earlier
    # all-development boundary diagnostic fit numerically.
    if selected is not None:
        diag_fit = full_diag[selected]
        if clean(final_fit["parameters"]) != clean(diag_fit["parameters"]):
            raise GateError("selected final refit parameter mismatch")
        for c in CELLS:
            if not math.isclose(
                final_fit["r1_r4_values"][c],
                diag_fit["r1_r4_values"][c],
                rel_tol=0,
                abs_tol=1e-8,
            ):
                raise GateError("selected final refit value mismatch")
        if not boundary[selected]["pass"]:
            raise GateError("selected family failed boundary gate")

    decision = (
        "PASS_V6_1_PHASE4_LOYO_DEVELOPMENT_WINNER_FROZEN_"
        "2024_H2_AUTHORIZED_NEXT_STAGE"
        if selected is not None
        else pre["development_selection"]["none_eligible"]
    )
    generated = now()

    # D1 diagnostic explicitly quantifies the frozen R5 boundary cost.
    d1 = scores["D1_BOUNDARY_FREE_ROUNDWISE_DIAGNOSTIC"]
    c1s = scores["C1_ROUNDWISE_RESCALE_R1_R4"]
    d1_diag = {
        "can_win": False,
        "loyo_h3_o2_macro_mae": d1["loyo_h3_o2_macro_mae"],
        "C1_boundary_constrained_loyo_h3_o2_macro_mae":
            c1s["loyo_h3_o2_macro_mae"],
        "mae_difference_D1_minus_C1":
            d1["loyo_h3_o2_macro_mae"]
            - c1s["loyo_h3_o2_macro_mae"],
        "relative_difference_vs_C1": (
            d1["loyo_h3_o2_macro_mae"]
            / c1s["loyo_h3_o2_macro_mae"] - 1.0
        ),
        "all_development_fit": full_diag[
            "D1_BOUNDARY_FREE_ROUNDWISE_DIAGNOSTIC"
        ],
    }

    result = {
        "schema_version": 1,
        "study_id": "draft-pick-fv-v6-r1-r4-structural-continuity",
        "stage": "phase4_loyo_development_selection",
        "status": (
            "LOYO_DEVELOPMENT_WINNER_FROZEN"
            if selected is not None
            else "LOYO_DEVELOPMENT_NO_ELIGIBLE_CANDIDATE"
        ),
        "generated_at_utc": generated,
        "decision": decision,
        "research_only": True,
        "development_outcomes_read": True,
        "holdout_2024_pick_identity_file_read": False,
        "holdout_2024_outcomes_read": False,
        "candidate_fit_performed": True,
        "candidate_scores_computed": True,
        "candidate_selection_performed": True,
        "market_or_ktc_values_read": False,
        "package_vote_data_read": False,
        "production_change_authorized": False,
        "automatic_production_promotion_allowed": False,
        "year_discount_fit_or_changed": False,
        "r5_r6_fit_or_changed": False,
        "folds": pre["development_selection"]["folds"],
        "implementation_contract_file": CONTRACT.name,
        "implementation_contract_sha256": sha(CONTRACT),
        "candidate_scores": scores,
        "c3_alpha_selection": alpha_diag,
        "bootstrap_results": bootstrap,
        "boundary_saturation_diagnostics": boundary,
        "eligibility_gate_results": eligibility,
        "eligible_candidates": eligible_ids,
        "selected_candidate": selected,
        "winner_rule": pre["development_selection"]["winner_rule"],
        "D1_boundary_free_diagnostic": d1_diag,
        "final_candidate_frozen": selected is not None,
        "final_candidate": (
            {
                "candidate_id": selected,
                "parameters": final_fit["parameters"],
                "r1_r4_values": final_fit["r1_r4_values"],
                "structural": final_fit["structural"],
                "exact_slot_values": final_fit.get("exact_slot_values"),
            }
            if selected is not None else None
        ),
        "2024_H2_outcome_open_authorized_next_stage":
            selected is not None,
        "2024_H3_outcomes_remain_sealed": True,
        "next_stage": (
            "draft-pick-fv-v6-phase5-2024-h2-temporal-confirmation"
            if selected is not None
            else "draft-pick-fv-v6-phase4-closeout-no-development-candidate"
        ),
        "input_hashes": {
            PREREG.name: sha(PREREG),
            P2_SUM.name: sha(P2_SUM),
            P2_MAN.name: sha(P2_MAN),
            REPAIR_SUM.name: sha(REPAIR_SUM),
            REPAIR_MAN.name: sha(REPAIR_MAN),
            DEV.name: sha(DEV),
            CONTRACT.name: sha(CONTRACT),
            CONTRACT_MAN.name: sha(CONTRACT_MAN),
            SOLVER_ERRATUM.name: sha(SOLVER_ERRATUM),
            SOLVER_ERRATUM_MAN.name: sha(SOLVER_ERRATUM_MAN),
        },
    }
    write_json(OUT_RESULT, result)

    boot_out = {
        "schema_version": 1,
        "stage": "phase4_loyo_paired_cluster_bootstrap",
        "generated_at_utc": generated,
        "replicates": BOOT_REPS,
        "seed": BOOT_SEED,
        "paired": True,
        "cluster": "stable player identity within draft class",
        "results": bootstrap,
        "candidate_fit_performed_inside_bootstrap": False,
        "out_of_fold_predictions_held_fixed": True,
    }
    write_json(OUT_BOOT, boot_out)

    cand_out = {
        "schema_version": 1,
        "stage": "phase4_frozen_development_candidate",
        "generated_at_utc": generated,
        "decision": decision,
        "selected_candidate": selected,
        "eligible_candidates": eligible_ids,
        "candidate_parameters_frozen_before_2024_outcome_access":
            selected is not None,
        "candidate": result["final_candidate"],
        "holdout_2024_outcomes_read": False,
        "production_change_authorized": False,
        "next_stage": result["next_stage"],
    }
    write_json(OUT_CAND, cand_out)

    lines = [
        "# Draft Pick FV V6.1 — Phase 4 LOYO Development Selection",
        "",
        f"**Decision:** `{decision}`",
        "",
        "| Candidate | LOYO H3 O2 MAE | Improvement vs C0 | Eligible |",
        "|---|---:|---:|---|",
    ]
    for cid in ("C0_DEPLOYED", *WINNER_ORDER):
        s = result["candidate_scores"][cid]
        if cid == "C0_DEPLOYED":
            imp = 0.0
            elig = "BASELINE"
        else:
            imp = result["eligibility_gate_results"][cid][
                "loyo_h3_o2_improvement_vs_C0"
            ]
            elig = (
                "YES"
                if result["eligibility_gate_results"][cid]["eligible"]
                else "NO"
            )
        lines.append(
            f"| {cid} | {s['loyo_h3_o2_macro_mae']:.2f} | "
            f"{imp:.2%} | {elig} |"
        )
    lines += [
        "",
        "## C3 shrinkage",
        "",
        f"- Selected alpha: **{alpha_diag['selected_alpha']}**",
        f"- Grid-edge alpha: **{'Yes' if alpha_diag['selected_alpha_is_grid_edge'] else 'No'}**",
        "",
        "## D1 boundary diagnostic",
        "",
        f"- D1 LOYO H3 O2 MAE: **{d1_diag['loyo_h3_o2_macro_mae']:.2f}**",
        f"- C1 constrained LOYO H3 O2 MAE: **{d1_diag['C1_boundary_constrained_loyo_h3_o2_macro_mae']:.2f}**",
        "",
        "## Selection",
        "",
        (
            f"Frozen development winner: **{selected}**."
            if selected is not None
            else "No C1/C2/C3 family passed every preregistered development gate."
        ),
        "",
        "## Firewalls",
        "",
        "- 2024 holdout outcomes read: **No**",
        "- KTC/market values read: **No**",
        "- Package-vote evidence read: **No**",
        "- R5–R6 changed: **No**",
        "- YEAR_DISCOUNT changed: **No**",
        "- Production change authorized: **No**",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "study_id": result["study_id"],
        "stage": result["stage"],
        "status": result["status"],
        "generated_at_utc": generated,
        "decision": decision,
        "candidate_fit_performed": True,
        "candidate_scores_computed": True,
        "candidate_selection_performed": True,
        "selected_candidate": selected,
        "eligible_candidate_n": len(eligible_ids),
        "final_candidate_frozen": selected is not None,
        "holdout_2024_outcomes_read": False,
        "2024_H2_outcome_open_authorized_next_stage":
            selected is not None,
        "2024_H3_outcomes_remain_sealed": True,
        "production_change_authorized": False,
        "next_stage": result["next_stage"],
        "input_hashes": result["input_hashes"],
        "output_hashes": {
            OUT_RESULT.name: sha(OUT_RESULT),
            OUT_BOOT.name: sha(OUT_BOOT),
            OUT_CAND.name: sha(OUT_CAND),
            OUT_MD.name: sha(OUT_MD),
        },
        "canonical_result_sha256": canonical_sha(clean(result)),
    }
    write_json(OUT_MAN, manifest)

    print(f"DECISION={decision}")
    print(f"ELIGIBLE={eligible_ids}")
    print(f"SELECTED={selected}")
    for cid in ("C0_DEPLOYED", *WINNER_ORDER):
        print(
            cid,
            f"H3_MAE={scores[cid]['loyo_h3_o2_macro_mae']:.6f}",
        )
    print("2024_HOLDOUT_OUTCOMES_READ=false")
    print("PRODUCTION_CHANGE_AUTHORIZED=false")


def selftest() -> None:
    # PAVA and structure.
    x = pava_decreasing(
        [10, 12, 9, 8, 6],
        [1, 1, 1, 1, 1],
        7,
    )
    assert all(x[i] >= x[i + 1] - 1e-12 for i in range(len(x) - 1))
    assert min(x) >= 7

    # C2 coefficient contract.
    assert np.allclose(
        c2_coeff("r4_late"),
        np.array([1, -1, -2, 0, -1], dtype=float),
    )

    # Synthetic LAD C1 fit.
    pre = {
        "frozen_deployed_baseline": {
            "pick_base_2027": {
                "1": {"early": 7500, "mid": 5854, "late": 5244},
                "2": {"early": 3906, "mid": 3624, "late": 3291},
                "3": {"early": 2692, "mid": 2682, "late": 2319},
                "4": {"early": 1972, "mid": 1831, "late": 1689},
                "5": {"early": 1414, "mid": 1250, "late": 1118},
                "6": {"early": 1014, "mid": 853, "late": 740},
            }
        },
        "candidate_families": {
            "C1_ROUNDWISE_RESCALE_R1_R4": {
                "bounds": {f"k{i}": [0.15, 1.25] for i in range(1, 5)}
            },
            "C2_ANCHORED_ADDITIVE_ROUND_TIER_CURVE": {
                "bounds": {
                    "A": [2000, 9000],
                    "s12": [0, 5000],
                    "s34": [0, 3000],
                    "mid_penalty": [0, 2500],
                    "late_penalty": [0, 3500],
                }
            },
        },
    }
    rows = []
    for y in YEARS[:2]:
        for cell in CELLS:
            for slotrep in range(2):
                rows.append({
                    "draft_year": y,
                    "cell": cell,
                    "overall_slot": (
                        (cell_round(cell) - 1) * 12
                        + {"early": 1, "mid": 5, "late": 9}[cell_tier(cell)]
                        + slotrep
                    ),
                    "_target": c0_values(pre)[cell] * 0.75,
                    "_raw_w": 1.0,
                    "_w": 1.0 / (2 * len(CELLS) * 2),
                })
    c1 = c1_fit(rows, pre, enforce_r4_anchor=True)
    assert c1["structural"]["structural_gate_pass"] is True
    assert c1["parameters"]["k4"] >= 1414 / 1689 - 1e-8

    # Bound detector.
    assert at_bound(0.15, (0.15, 1.25))["at_hard_bound"]
    assert not at_bound(0.5, (0.15, 1.25))["at_hard_bound"]

    # Numerical lexicographic fixation tolerance is materially tighter than
    # the preregistered hard-bound saturation tolerance.
    k_scale = max(1.0, 0.15, 1.25, 1.25 - 0.15)
    k_fix = max(LEX_FIX_ABS_TOL, LEX_FIX_REL_TOL * k_scale)
    k_hard = BOUND_REL_TOL * k_scale
    assert 0 < k_fix < k_hard

    print("PASS: V6.1 Phase 4 LOYO-selection self-test")


def guard_only() -> None:
    guard_contract()
    print("PASS: Phase 4 frozen preregistration/repair/implementation contract guard")


def check_outputs() -> None:
    r = load(OUT_RESULT)
    m = load(OUT_MAN)
    allowed = {
        "PASS_V6_1_PHASE4_LOYO_DEVELOPMENT_WINNER_FROZEN_"
        "2024_H2_AUTHORIZED_NEXT_STAGE",
        "STOP_NO_V6_R1_R4_DEVELOPMENT_CANDIDATE",
    }
    if r["decision"] not in allowed:
        raise GateError("unexpected Phase 4 decision")
    if m["decision"] != r["decision"]:
        raise GateError("Phase 4 manifest decision mismatch")
    if r["holdout_2024_outcomes_read"] is not False:
        raise GateError("2024 holdout outcomes were read")
    if r["2024_H3_outcomes_remain_sealed"] is not True:
        raise GateError("2024 H3 holdout unsealed")
    for key in (
        "market_or_ktc_values_read",
        "package_vote_data_read",
        "production_change_authorized",
        "year_discount_fit_or_changed",
        "r5_r6_fit_or_changed",
    ):
        if r[key] is not False:
            raise GateError(f"Phase 4 firewall violation: {key}")
    if bool(r["selected_candidate"]) != bool(m["final_candidate_frozen"]):
        raise GateError("final candidate freeze mismatch")
    if bool(r["selected_candidate"]) != bool(
        m["2024_H2_outcome_open_authorized_next_stage"]
    ):
        raise GateError("2024 H2 authorization mismatch")
    for name, expected in m["output_hashes"].items():
        if sha(V6 / name) != expected:
            raise GateError(f"Phase 4 output hash mismatch: {name}")
    print("PASS: V6.1 Phase 4 frozen outputs validated")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--guard", action="store_true")
    ap.add_argument("--fit", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
    elif args.guard:
        guard_only()
    elif args.fit:
        main_fit()
    elif args.check:
        check_outputs()
    else:
        raise SystemExit("choose --selftest/--guard/--fit/--check")


if __name__ == "__main__":
    main()
