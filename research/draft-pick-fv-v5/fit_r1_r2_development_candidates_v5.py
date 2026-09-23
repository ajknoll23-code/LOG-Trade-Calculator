#!/usr/bin/env python3
"""V5 Phase 4: fit frozen C1/C2/C3 on DEVELOPMENT outcomes only.

No validation file path exists in this executable. No network access,
KTC, package-vote evidence, production mutation, YEAR_DISCOUNT fit,
R3-R6 fit, or candidate selection is performed here.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path.cwd()
D = ROOT / "research" / "draft-pick-fv-v5"

PREREG = D / "r1_r2_bridge_preregistration_v5.json"
PHASE3_MANIFEST = D / "r1_r2_historical_outcome_manifest_v5_1.json"
PHASE3_SUMMARY = D / "r1_r2_historical_outcome_summary_v5_1.json"
DEV_FILE = D / "r1_r2_development_outcomes_v5_1.jsonl"

OUT_JSON = D / "r1_r2_development_candidate_fit_v5.json"
OUT_MD = D / "r1_r2_development_candidate_fit_v5.md"
OUT_MANIFEST = D / "r1_r2_development_candidate_fit_manifest_v5.json"

DEV_YEARS = (2018, 2019, 2020, 2021)
CELLS = (
    "r1_early",
    "r1_mid",
    "r1_late",
    "r2_early",
    "r2_mid",
    "r2_late",
)
TIERS = ("early", "mid", "late")
TIE_TOL = 1e-9

class GateError(RuntimeError):
    pass

def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def canonical_sha(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            obj,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise GateError(
                    f"{path.name}:{line_no}: non-object row"
                )
            rows.append(row)
    return rows

def finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )

@dataclass
class CellLoss:
    ys: list[float]
    weights: list[float]
    prefix_w: list[float]
    prefix_wy: list[float]
    total_w: float
    total_wy: float

    @classmethod
    def build(cls, obs: list[tuple[float, float]]) -> "CellLoss":
        if not obs:
            raise GateError("empty cell loss")
        pairs = sorted(
            (float(y), float(w))
            for y, w in obs
            if finite_number(y) and float(w) > 0
        )
        if not pairs:
            raise GateError("cell loss has no valid weighted rows")
        ys = [p[0] for p in pairs]
        ws = [p[1] for p in pairs]
        sw = sum(ws)
        if sw <= 0:
            raise GateError("nonpositive cell weight")
        ws = [w / sw for w in ws]
        pw = [0.0]
        pwy = [0.0]
        for y, w in zip(ys, ws):
            pw.append(pw[-1] + w)
            pwy.append(pwy[-1] + w * y)
        return cls(
            ys=ys,
            weights=ws,
            prefix_w=pw,
            prefix_wy=pwy,
            total_w=pw[-1],
            total_wy=pwy[-1],
        )

    def loss(self, value: float) -> float:
        v = float(value)
        i = bisect.bisect_right(self.ys, v)
        lw = self.prefix_w[i]
        lwy = self.prefix_wy[i]
        rw = self.total_w - lw
        rwy = self.total_wy - lwy
        return v * lw - lwy + rwy - v * rw

    def right_slope(self, value: float) -> float:
        i = bisect.bisect_right(self.ys, float(value))
        return 2.0 * self.prefix_w[i] - self.total_w

    def weighted_median(self) -> float:
        half = 0.5 * self.total_w
        for i, cumulative in enumerate(self.prefix_w[1:]):
            if cumulative >= half:
                return self.ys[i]
        return self.ys[-1]

def cell_round(cell: str) -> int:
    return 1 if cell.startswith("r1_") else 2

def tier(cell: str) -> str:
    return cell.split("_", 1)[1]

def candidate_values_c1(
    baseline: dict[str, float], k1: float
) -> dict[str, float]:
    return {
        cell: (
            baseline[cell] * k1
            if cell_round(cell) == 1
            else baseline[cell]
        )
        for cell in CELLS
    }

def candidate_values_c2(
    baseline: dict[str, float],
    k1: float,
    k2: float,
) -> dict[str, float]:
    return {
        cell: baseline[cell] * (k1 if cell_round(cell) == 1 else k2)
        for cell in CELLS
    }

def candidate_values_c3(
    A: float,
    b: float,
    mid_penalty: float,
    late_penalty: float,
) -> dict[str, float]:
    penalties = {
        "early": 0.0,
        "mid": mid_penalty,
        "late": late_penalty,
    }
    return {
        cell: A
        * math.exp(
            -(
                (b if cell_round(cell) == 2 else 0.0)
                + penalties[tier(cell)]
            )
        )
        for cell in CELLS
    }

def objective(
    losses: dict[str, CellLoss],
    values: dict[str, float],
) -> float:
    return sum(
        losses[cell].loss(values[cell])
        for cell in CELLS
    ) / len(CELLS)

def objective_by_cell(
    losses: dict[str, CellLoss],
    values: dict[str, float],
) -> dict[str, float]:
    return {
        cell: losses[cell].loss(values[cell])
        for cell in CELLS
    }

def scalar_round_objective(
    losses: dict[str, CellLoss],
    baseline: dict[str, float],
    rnd: int,
    k: float,
) -> float:
    cells = [c for c in CELLS if cell_round(c) == rnd]
    return sum(
        losses[c].loss(baseline[c] * k)
        for c in cells
    ) / len(cells)

def exact_scalar_fit(
    raw_rows: list[dict[str, Any]],
    losses: dict[str, CellLoss],
    baseline: dict[str, float],
    rnd: int,
    lo: float,
    hi: float,
) -> float:
    candidates = {float(lo), float(hi)}
    for row in raw_rows:
        cell = row["cell"]
        if cell_round(cell) != rnd:
            continue
        y = float(row["_fit_o2"])
        b = float(baseline[cell])
        r = y / b
        if lo <= r <= hi:
            candidates.add(r)
    best_obj = math.inf
    best = None
    for k in sorted(candidates):
        obj = scalar_round_objective(
            losses, baseline, rnd, k
        )
        if obj < best_obj - TIE_TOL:
            best_obj, best = obj, k
        elif abs(obj - best_obj) <= TIE_TOL and (
            best is None or round(k, 12) < round(best, 12)
        ):
            best = k
    if best is None:
        raise GateError("scalar optimizer failed")
    return float(best)

def c3_coeffs(
    b: float,
    m: float,
    l: float,
) -> dict[str, float]:
    return {
        "r1_early": 1.0,
        "r1_mid": math.exp(-m),
        "r1_late": math.exp(-l),
        "r2_early": math.exp(-b),
        "r2_mid": math.exp(-(b + m)),
        "r2_late": math.exp(-(b + l)),
    }

def best_A_for_c3(
    losses: dict[str, CellLoss],
    b: float,
    m: float,
    l: float,
    lo: float,
    hi: float,
) -> float:
    coeff = c3_coeffs(b, m, l)

    def derivative_right(A: float) -> float:
        return sum(
            coeff[cell]
            * losses[cell].right_slope(A * coeff[cell])
            for cell in CELLS
        ) / len(CELLS)

    if derivative_right(lo) >= 0:
        return lo
    if derivative_right(hi) < 0:
        return hi

    left, right = lo, hi
    for _ in range(72):
        mid = (left + right) / 2.0
        if derivative_right(mid) >= 0:
            right = mid
        else:
            left = mid
    return right

def fit_c3(
    losses: dict[str, CellLoss],
    bounds: dict[str, list[float]],
) -> tuple[dict[str, float], dict[str, float], float]:
    A_lo, A_hi = map(float, bounds["A"])
    b_lo, b_hi = map(float, bounds["b"])
    m_lo, m_hi = map(float, bounds["mid_penalty"])
    l_lo, l_hi = map(float, bounds["late_penalty"])

    def evaluate(
        b: float, m: float, l: float
    ) -> tuple[float, tuple[float, float, float, float]]:
        if not (
            b_lo <= b <= b_hi
            and m_lo <= m <= m_hi
            and l_lo <= l <= l_hi
            and 0.0 <= m <= l
            and l <= b
        ):
            return math.inf, (math.inf,) * 4
        A = best_A_for_c3(
            losses, b, m, l, A_lo, A_hi
        )
        vals = candidate_values_c3(A, b, m, l)
        obj = objective(losses, vals)
        params = (
            round(A, 12),
            round(b, 12),
            round(m, 12),
            round(l, 12),
        )
        return obj, params

    def keep_best(
        candidates: list[
            tuple[float, tuple[float, float, float, float]]
        ],
        n: int = 32,
    ):
        candidates.sort(key=lambda x: (x[0], x[1]))
        out = []
        seen = set()
        for item in candidates:
            key = tuple(round(v, 10) for v in item[1][1:])
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
            if len(out) >= n:
                break
        return out

    coarse = []
    step = 0.025
    b_n = int(round((b_hi - b_lo) / step))
    m_n = int(round((m_hi - m_lo) / step))
    l_n = int(round((l_hi - l_lo) / step))
    for ib in range(b_n + 1):
        b = b_lo + ib * step
        for im in range(m_n + 1):
            m = m_lo + im * step
            for il in range(l_n + 1):
                l = l_lo + il * step
                if m <= l + 1e-15 and l <= b + 1e-15:
                    coarse.append(evaluate(b, m, l))
    seeds = keep_best(coarse)

    for step in (0.005, 0.001, 0.0002, 0.00004, 0.000008):
        cand = list(seeds)
        for _, params in seeds:
            _, b0, m0, l0 = params
            for db in range(-3, 4):
                b = min(b_hi, max(b_lo, b0 + db * step))
                for dm in range(-3, 4):
                    m = min(m_hi, max(m_lo, m0 + dm * step))
                    for dl in range(-3, 4):
                        l = min(l_hi, max(l_lo, l0 + dl * step))
                        if m <= l + 1e-15 and l <= b + 1e-15:
                            cand.append(evaluate(b, m, l))
        seeds = keep_best(cand)

    best_obj = min(x[0] for x in seeds)
    tied = [
        x for x in seeds
        if abs(x[0] - best_obj) <= TIE_TOL
    ]
    tied.sort(key=lambda x: x[1])
    obj, p = tied[0]
    A, b, m, l = p
    values = candidate_values_c3(A, b, m, l)

    # Frozen C3 structural family constraint.
    seq = [values[c] for c in CELLS]
    if not all(
        seq[i] >= seq[i + 1] - 1e-8
        for i in range(len(seq) - 1)
    ):
        raise GateError(
            f"C3 monotonicity constraint failed: {values}"
        )

    return (
        {
            "A": A,
            "b": b,
            "mid_penalty": m,
            "late_penalty": l,
        },
        values,
        obj,
    )

def full_table(
    base_full: dict[str, dict[str, float]],
    fitted: dict[str, float],
) -> dict[str, dict[str, float]]:
    out = {
        str(r): {
            t: float(base_full[str(r)][t])
            for t in TIERS
        }
        for r in range(1, 7)
    }
    for cell, value in fitted.items():
        rnd = str(cell_round(cell))
        out[rnd][tier(cell)] = float(value)
    return out

def structural_diagnostics(
    base_full: dict[str, dict[str, float]],
    fitted: dict[str, float],
) -> dict[str, Any]:
    table = full_table(base_full, fitted)
    flattened = [
        table[str(r)][t]
        for r in range(1, 7)
        for t in TIERS
    ]
    monotone = all(
        flattened[i] >= flattened[i + 1] - 1e-8
        for i in range(len(flattened) - 1)
    )
    positive = all(v > 0 for v in flattened)
    r3_r6_unchanged = all(
        table[str(r)][t]
        == float(base_full[str(r)][t])
        for r in range(3, 7)
        for t in TIERS
    )
    return {
        "all_18_positive": positive,
        "all_18_monotone_nonincreasing": monotone,
        "r3_r6_unchanged": r3_r6_unchanged,
        "selection_structural_gate_pass": (
            positive and monotone and r3_r6_unchanged
        ),
        "spliced_pick_base": table,
    }

def prepare_sample(
    all_rows: list[dict[str, Any]],
    *,
    non_idp_only: bool,
) -> tuple[
    list[dict[str, Any]],
    dict[str, CellLoss],
    dict[str, Any],
]:
    rows = []
    raw_counts = defaultdict(int)
    ready_counts = defaultdict(int)

    for row in all_rows:
        y = int(row["draft_year"])
        cell = str(row["cell"])
        if y not in DEV_YEARS or cell not in CELLS:
            raise GateError(
                f"non-development or invalid cell in dev corpus: "
                f"{y} {cell}"
            )
        if row.get("split") != "development":
            raise GateError("non-development split in dev corpus")
        if non_idp_only and bool(row.get("league_idp", False)):
            continue

        raw_counts[(y, cell)] += 1
        h3 = row.get("H3")
        o2 = h3.get("O2") if isinstance(h3, dict) else None
        if not (
            row.get("primary_o2_ready") is True
            and finite_number(o2)
        ):
            continue

        w = row.get("cell_weight_v5_1")
        if not finite_number(w) or float(w) <= 0:
            raise GateError("invalid frozen cell weight")
        x = dict(row)
        x["_fit_o2"] = float(o2)
        x["_raw_weight"] = float(w)
        rows.append(x)
        ready_counts[(y, cell)] += 1

    # The preregistered fit requires equal draft-class weight.
    # Renormalize available O2 rows within each year x cell to
    # exactly 1/4 total weight while preserving inherited
    # league-balanced relative weights.
    weight_sum = defaultdict(float)
    for row in rows:
        weight_sum[
            (int(row["draft_year"]), str(row["cell"]))
        ] += float(row["_raw_weight"])

    for y in DEV_YEARS:
        for cell in CELLS:
            if raw_counts[(y, cell)] <= 0:
                raise GateError(
                    f"zero source support {y}:{cell}"
                )
            if ready_counts[(y, cell)] <= 0:
                raise GateError(
                    f"zero O2-ready support {y}:{cell}"
                )
            if weight_sum[(y, cell)] <= 0:
                raise GateError(
                    f"zero weight sum {y}:{cell}"
                )

    for row in rows:
        key = (
            int(row["draft_year"]),
            str(row["cell"]),
        )
        row["_fit_weight"] = (
            (1.0 / len(DEV_YEARS))
            * float(row["_raw_weight"])
            / weight_sum[key]
        )

    by_cell_obs = defaultdict(list)
    for row in rows:
        by_cell_obs[str(row["cell"])].append(
            (
                float(row["_fit_o2"]),
                float(row["_fit_weight"]),
            )
        )
    losses = {
        cell: CellLoss.build(by_cell_obs[cell])
        for cell in CELLS
    }

    # Prove exactly equal year weight within every production cell.
    year_cell_fit_weights = defaultdict(float)
    for row in rows:
        year_cell_fit_weights[
            (int(row["draft_year"]), str(row["cell"]))
        ] += float(row["_fit_weight"])
    for y in DEV_YEARS:
        for cell in CELLS:
            if not math.isclose(
                year_cell_fit_weights[(y, cell)],
                0.25,
                rel_tol=0,
                abs_tol=1e-12,
            ):
                raise GateError(
                    f"fit weight normalization failed {y}:{cell}"
                )

    groups = set()
    for row in rows:
        stable = (
            row.get("stable_player_key")
            or row.get("sleeper_id")
            or row.get("gsis_id")
            or row.get("mfl_player_id")
        )
        groups.add((int(row["draft_year"]), str(stable)))

    diag = {
        "non_idp_only": non_idp_only,
        "retained_input_occurrence_n": sum(raw_counts.values()),
        "o2_ready_fit_occurrence_n": len(rows),
        "unique_player_x_draft_class_cluster_n": len(groups),
        "by_year_cell": {
            f"{y}:{cell}": {
                "retained_occurrence_n": raw_counts[(y, cell)],
                "o2_ready_occurrence_n": ready_counts[(y, cell)],
                "o2_ready_fraction": (
                    ready_counts[(y, cell)]
                    / raw_counts[(y, cell)]
                ),
                "fit_weight_total": year_cell_fit_weights[
                    (y, cell)
                ],
            }
            for y in DEV_YEARS
            for cell in CELLS
        },
        "inferential_uncertainty_computed": False,
        "cluster_contract_note": (
            "No inferential uncertainty is computed in Phase 4. "
            "Any later uncertainty analysis must cluster repeated "
            "selections by stable player identity within draft class."
        ),
    }
    return rows, losses, diag

def fit_all(
    rows: list[dict[str, Any]],
    losses: dict[str, CellLoss],
    pre: dict[str, Any],
) -> dict[str, Any]:
    full = pre["frozen_deployed_baseline"][
        "pick_base_2027"
    ]
    baseline = {
        f"r{r}_{t}": float(full[str(r)][t])
        for r in (1, 2)
        for t in TIERS
    }
    fam = pre["candidate_families"]

    c0_values = dict(baseline)
    c0_obj = objective(losses, c0_values)

    k1_c1 = exact_scalar_fit(
        rows,
        losses,
        baseline,
        1,
        *map(
            float,
            fam["C1_R1_GLOBAL_RESCALE"]["bounds"]["k1"],
        ),
    )
    c1_values = candidate_values_c1(baseline, k1_c1)

    k1_c2 = exact_scalar_fit(
        rows,
        losses,
        baseline,
        1,
        *map(
            float,
            fam["C2_R1_R2_ROUND_RESCALE"]["bounds"]["k1"],
        ),
    )
    k2_c2 = exact_scalar_fit(
        rows,
        losses,
        baseline,
        2,
        *map(
            float,
            fam["C2_R1_R2_ROUND_RESCALE"]["bounds"]["k2"],
        ),
    )
    c2_values = candidate_values_c2(
        baseline, k1_c2, k2_c2
    )

    c3_params, c3_values, c3_obj = fit_c3(
        losses,
        fam[
            "C3_R1_R2_LOW_PARAMETER_TIER_CURVE"
        ]["bounds"],
    )

    candidates = {
        "C0_DEPLOYED": {
            "fit_status": "baseline_only_never_refit",
            "effective_parameters": 0,
            "parameters": {},
            "r1_r2_values": c0_values,
            "development_macro_mae_o2": c0_obj,
            "development_mae_o2_by_cell": objective_by_cell(
                losses, c0_values
            ),
        },
        "C1_R1_GLOBAL_RESCALE": {
            "fit_status": "development_fit",
            "effective_parameters": 1,
            "parameters": {"k1": k1_c1},
            "r1_r2_values": c1_values,
            "development_macro_mae_o2": objective(
                losses, c1_values
            ),
            "development_mae_o2_by_cell": objective_by_cell(
                losses, c1_values
            ),
        },
        "C2_R1_R2_ROUND_RESCALE": {
            "fit_status": "development_fit",
            "effective_parameters": 2,
            "parameters": {
                "k1": k1_c2,
                "k2": k2_c2,
            },
            "r1_r2_values": c2_values,
            "development_macro_mae_o2": objective(
                losses, c2_values
            ),
            "development_mae_o2_by_cell": objective_by_cell(
                losses, c2_values
            ),
        },
        "C3_R1_R2_LOW_PARAMETER_TIER_CURVE": {
            "fit_status": "development_fit",
            "effective_parameters": 4,
            "parameters": c3_params,
            "r1_r2_values": c3_values,
            "development_macro_mae_o2": c3_obj,
            "development_mae_o2_by_cell": objective_by_cell(
                losses, c3_values
            ),
        },
    }

    for cid, rec in candidates.items():
        rec["structural_diagnostics"] = (
            structural_diagnostics(full, rec["r1_r2_values"])
        )
        rec["development_objective_only"] = True
        rec["validation_eligibility_determined"] = False
        rec["selected_winner"] = False

    return {
        "baseline_r1_r2": baseline,
        "candidates": candidates,
    }

def clean_numbers(obj: Any) -> Any:
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise GateError("nonfinite output")
        return round(obj, 10)
    if isinstance(obj, dict):
        return {
            k: clean_numbers(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [clean_numbers(v) for v in obj]
    return obj

def main() -> None:
    pre = load(PREREG)
    p3m = load(PHASE3_MANIFEST)
    p3s = load(PHASE3_SUMMARY)

    if p3m["development_fit_authorized_next_stage"] is not True:
        raise GateError("Phase 3 did not authorize development fit")
    if p3m["candidate_fit_performed"] is not False:
        raise GateError("Phase 3 candidate-fit flag drift")
    if p3m["validation_scored"] is not False:
        raise GateError("Phase 3 validation flag drift")
    if p3m["output_hashes"][DEV_FILE.name] != sha(DEV_FILE):
        raise GateError("development outcome hash drift")
    if p3s["development_occurrence_n"] != 4844:
        raise GateError("development occurrence count drift")
    if pre["candidate_fit"]["development_only"] is not True:
        raise GateError("prereg development-only contract drift")
    if pre["candidate_fit"]["validation_reuse_for_refit"] is not False:
        raise GateError("validation-refit contract drift")

    rows = read_jsonl(DEV_FILE)
    if len(rows) != 4844:
        raise GateError(
            f"expected 4844 development rows, got {len(rows)}"
        )

    seen = set()
    for row in rows:
        key = (
            int(row["draft_year"]),
            str(row["league_id"]),
            int(row["overall_slot"]),
        )
        if key in seen:
            raise GateError(f"duplicate development occurrence {key}")
        seen.add(key)
        if int(row["draft_year"]) not in DEV_YEARS:
            raise GateError(
                f"forbidden non-development year {row['draft_year']}"
            )
        if row.get("split") != "development":
            raise GateError(
                f"forbidden non-development split {row.get('split')}"
            )

    primary_rows, primary_losses, primary_diag = (
        prepare_sample(rows, non_idp_only=False)
    )
    nonidp_rows, nonidp_losses, nonidp_diag = (
        prepare_sample(rows, non_idp_only=True)
    )

    primary = fit_all(
        primary_rows, primary_losses, pre
    )
    nonidp = fit_all(
        nonidp_rows, nonidp_losses, pre
    )

    generated = now()
    out = {
        "schema_version": 1,
        "study_id": (
            "draft-pick-fv-v5-r1-r2-player-equivalent-calibration"
        ),
        "stage": "phase4_development_candidate_fit",
        "status": "DEVELOPMENT_FITS_FROZEN",
        "generated_at_utc": generated,
        "research_only": True,
        "historical_player_outcomes_read": True,
        "development_outcomes_read": True,
        "validation_outcomes_read": False,
        "validation_scored": False,
        "candidate_fit_performed": True,
        "candidate_selection_performed": False,
        "production_change_authorized": False,
        "automatic_production_promotion_allowed": False,
        "market_or_ktc_values_read": False,
        "package_vote_data_read": False,
        "year_discount_fit_or_changed": False,
        "r3_r6_fit_or_changed": False,
        "development_years": list(DEV_YEARS),
        "fit_objective": pre["candidate_fit"]["objective"],
        "optimizer_contract": {
            "C1": (
                "exact deterministic breakpoint minimization "
                "of weighted absolute error"
            ),
            "C2": (
                "two exact deterministic round-specific "
                "breakpoint minimizations"
            ),
            "C3": (
                "deterministic bounded global lattice plus "
                "multi-resolution refinement; A solved exactly "
                "conditional on b/mid/late via convex subgradient"
            ),
            "tie_tolerance": TIE_TOL,
            "tie_rule": (
                "Within 1e-9 objective, lexicographically "
                "smallest rounded parameter vector."
            ),
        },
        "primary_fit_sample": primary_diag,
        "primary": primary,
        "non_idp_sensitivity_sample": nonidp_diag,
        "non_idp_sensitivity": nonidp,
        "sensitivity_used_for_primary_fit": False,
        "development_fit_does_not_select_winner": True,
        "next_stage_authorized": True,
        "next_stage": (
            "draft-pick-fv-v5-phase5-locked-validation-scoring"
        ),
        "input_hashes": {
            PREREG.name: sha(PREREG),
            PHASE3_MANIFEST.name: sha(PHASE3_MANIFEST),
            PHASE3_SUMMARY.name: sha(PHASE3_SUMMARY),
            DEV_FILE.name: sha(DEV_FILE),
        },
    }
    out = clean_numbers(out)
    OUT_JSON.write_text(
        json.dumps(out, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    primary_candidates = out["primary"]["candidates"]
    md = [
        "# Draft Pick FV V5 — Phase 4 Development Candidate Fit",
        "",
        "**Status:** `DEVELOPMENT_FITS_FROZEN`",
        "",
        "This phase fit C1/C2/C3 using only 2018–2021 "
        "development outcomes. It did not read or score locked "
        "validation and does not select a winner.",
        "",
        "## Primary development fit",
        "",
        "| Candidate | Development O2 macro MAE | Structural gate | Parameters |",
        "|---|---:|---|---|",
    ]
    for cid in (
        "C0_DEPLOYED",
        "C1_R1_GLOBAL_RESCALE",
        "C2_R1_R2_ROUND_RESCALE",
        "C3_R1_R2_LOW_PARAMETER_TIER_CURVE",
    ):
        rec = primary_candidates[cid]
        md.append(
            f"| {cid} | "
            f"{rec['development_macro_mae_o2']:.2f} | "
            f"{'PASS' if rec['structural_diagnostics']['selection_structural_gate_pass'] else 'FAIL'} | "
            f"`{json.dumps(rec['parameters'], sort_keys=True)}` |"
        )

    md += [
        "",
        "## Firewalls",
        "",
        "- Locked-validation outcomes read: **No**",
        "- Validation scoring performed: **No**",
        "- Candidate winner selected: **No**",
        "- KTC/market values read: **No**",
        "- Package-vote evidence read: **No**",
        "- YEAR_DISCOUNT fit/changed: **No**",
        "- R3–R6 fit/changed: **No**",
        "- Production change authorized: **No**",
        "",
        "## Sensitivity",
        "",
        "A separate non-IDP-only development fit was frozen as "
        "required by the original V3/V5 contract. It is diagnostic "
        "only and cannot alter the primary fitted parameters.",
        "",
        "## Next step",
        "",
        "Phase 5 may open the locked 2022–2023 validation corpus "
        "for the first time and score these already-frozen "
        "candidate parameter vectors. No refitting is permitted.",
        "",
    ]
    OUT_MD.write_text(
        "\n".join(md), encoding="utf-8"
    )

    manifest = {
        "schema_version": 1,
        "study_id": out["study_id"],
        "stage": out["stage"],
        "status": out["status"],
        "generated_at_utc": generated,
        "candidate_fit_performed": True,
        "validation_outcomes_read": False,
        "validation_scored": False,
        "candidate_selection_performed": False,
        "production_change_authorized": False,
        "development_fit_frozen": True,
        "next_stage_authorized": True,
        "next_stage": out["next_stage"],
        "input_hashes": out["input_hashes"],
        "output_hashes": {
            OUT_JSON.name: sha(OUT_JSON),
            OUT_MD.name: sha(OUT_MD),
        },
        "canonical_fit_sha256": canonical_sha(out),
    }
    OUT_MANIFEST.write_text(
        json.dumps(
            manifest, indent=2, sort_keys=True
        ) + "\n",
        encoding="utf-8",
    )

    print(
        "DECISION=PASS_V5_PHASE4_DEVELOPMENT_FITS_FROZEN_"
        "LOCKED_VALIDATION_AUTHORIZED_NEXT_STAGE"
    )
    for cid, rec in primary_candidates.items():
        print(
            cid,
            f"MAE={rec['development_macro_mae_o2']:.4f}",
            f"params={rec['parameters']}",
            "structural="
            f"{rec['structural_diagnostics']['selection_structural_gate_pass']}",
        )

if __name__ == "__main__":
    main()
