#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTRACT_PATH = ROOT / "phase0a_precision_contract.json"

Z975 = 1.959963984540054


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def quantile_sorted(xs: list[float], q: float) -> float:
    if not xs:
        raise ValueError("empty quantile input")
    if q <= 0:
        return xs[0]
    if q >= 1:
        return xs[-1]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    frac = pos - lo
    return xs[lo] * (1.0 - frac) + xs[hi] * frac


def cell_for_slot(contract: dict, slot: int) -> str:
    found = []
    for cell, slots in contract["axis"]["cell_slots"].items():
        if slot in slots:
            found.append(cell)
    if len(found) != 1:
        raise RuntimeError(f"slot {slot} maps to {found}")
    return found[0]


def validate_support(contract: dict, support: dict) -> None:
    expected_top = set(contract["support_summary_contract"]["top_level_keys_exact"])
    if set(support) != expected_top:
        raise RuntimeError(
            f"support top-level keys drift: {sorted(support)} != {sorted(expected_top)}"
        )

    if support["study_id"] != contract["study_id"]:
        raise RuntimeError("study_id mismatch")
    if support["outcome_blind"] is not True:
        raise RuntimeError("support summary must be outcome_blind=true")

    years = [int(x) for x in support["years"]]
    expected_years = contract["support_summary_contract"]["required_year_set"]
    if years != expected_years:
        raise RuntimeError(f"year set drift: {years}")

    expected_slots = set(
        contract["support_summary_contract"]["required_slot_set"]
    )
    actual_slots = {int(k) for k in support["slots"]}
    if actual_slots != expected_slots:
        raise RuntimeError("support slot set must be exactly 1..48")

    expected_slot_keys = set(
        contract["support_summary_contract"]["slot_keys_exact"]
    )
    expected_year_keys = set(
        contract["support_summary_contract"]["year_keys_exact"]
    )

    for slot in sorted(expected_slots):
        row = support["slots"][str(slot)]
        if set(row) != expected_slot_keys:
            raise RuntimeError(f"slot {slot}: keys drift")
        if row["cell"] != cell_for_slot(contract, slot):
            raise RuntimeError(f"slot {slot}: cell mismatch")
        by_year = row["by_year"]
        if {int(k) for k in by_year} != set(expected_years):
            raise RuntimeError(f"slot {slot}: year keys drift")
        for year in expected_years:
            y = by_year[str(year)]
            if set(y) != expected_year_keys:
                raise RuntimeError(f"slot {slot} year {year}: keys drift")
            s = float(y["slot_cluster_kish_neff"])
            c = float(y["cell_cluster_kish_neff"])
            if not math.isfinite(s) or not math.isfinite(c):
                raise RuntimeError(f"slot {slot} year {year}: nonfinite n_eff")
            if s <= 0 or c <= 0:
                raise RuntimeError(f"slot {slot} year {year}: n_eff must be >0")


def evaluate(contract: dict, support: dict) -> dict:
    validate_support(contract, support)

    years = contract["axis"]["years"]
    ref = contract["v10_reference_uncertainty"][
        "relative_95_halfwidth_by_cell"
    ]
    mc = contract["precision_model"]["monte_carlo"]
    reps = int(mc["replicates_per_slot"])
    seed_base = int(mc["seed_base"])
    mc_tol = float(mc["empirical_vs_analytic_abs_tolerance"])

    slot_results = {}
    mc_ok = True

    for slot in range(1, 49):
        cell = cell_for_slot(contract, slot)
        raw_year_ratios = {}
        effective_year_ratios = {}
        slot_inverse_information = 0.0
        cell_inverse_information = 0.0
        floor_applied_years = []

        for year in years:
            y = support["slots"][str(slot)]["by_year"][str(year)]
            s = float(y["slot_cluster_kish_neff"])
            c = float(y["cell_cluster_kish_neff"])

            raw_year_ratios[str(year)] = c / s
            if s > c:
                floor_applied_years.append(int(year))
            s_eff = min(s, c)
            effective_year_ratios[str(year)] = c / s_eff

            slot_inverse_information += 1.0 / s_eff
            cell_inverse_information += 1.0 / c

        variance_ratio = slot_inverse_information / cell_inverse_information
        inflation = math.sqrt(max(1.0, variance_ratio))
        analytic_hw = float(ref[cell]) * inflation
        sigma = analytic_hw / Z975

        rng = random.Random(seed_base + slot)
        draws = sorted(rng.gauss(0.0, sigma) for _ in range(reps))
        empirical_hw = (
            quantile_sorted(draws, 0.975)
            - quantile_sorted(draws, 0.025)
        ) / 2.0
        calibration_abs_error = abs(empirical_hw - analytic_hw)
        if calibration_abs_error > mc_tol:
            mc_ok = False

        slot_results[str(slot)] = {
            "cell": cell,
            "variance_information_ratio": variance_ratio,
            "information_inflation": inflation,
            "analytic_relative_95_halfwidth": analytic_hw,
            "mc_empirical_relative_95_halfwidth": empirical_hw,
            "mc_calibration_abs_error": calibration_abs_error,
            "raw_year_cell_to_slot_neff_ratios": raw_year_ratios,
            "effective_year_cell_to_slot_neff_ratios": effective_year_ratios,
            "ratio_floor_applied_years": floor_applied_years,
            "ratio_floor_applied_slot_year_count": len(floor_applied_years),
        }

    bucket_results = {}
    for cell, slots in contract["axis"]["cell_slots"].items():
        first = slots[0]
        last = slots[-1]
        hf = slot_results[str(first)]["analytic_relative_95_halfwidth"]
        hl = slot_results[str(last)]["analytic_relative_95_halfwidth"]
        bucket_results[cell] = {
            "first_slot": first,
            "last_slot": last,
            "conservative_spacing_relative_95_halfwidth":
                math.sqrt(hf * hf + hl * hl),
        }

    gates = contract["precision_pass_gates"]
    slot_hws = {
        int(k): float(v["analytic_relative_95_halfwidth"])
        for k, v in slot_results.items()
    }
    spacing_hws = {
        k: float(v["conservative_spacing_relative_95_halfwidth"])
        for k, v in bucket_results.items()
    }
    variance_ratios = [
        float(v["variance_information_ratio"])
        for v in slot_results.values()
    ]
    floor_applied_slot_years = sum(
        int(v["ratio_floor_applied_slot_year_count"])
        for v in slot_results.values()
    )

    gate_results = {
        "all_48_slots_under_hard_ceiling":
            max(slot_hws.values())
            <= float(gates["all_48_slots_relative_95_halfwidth_max"]),
        "at_least_43_slots_under_target":
            sum(
                hw <= float(gates["slot_target_relative_95_halfwidth_max"])
                for hw in slot_hws.values()
            ) >= int(gates["slots_meeting_target_required"]),
        "slots_1_4_under_top_pick_ceiling":
            all(
                slot_hws[s]
                <= float(gates["slots_1_4_relative_95_halfwidth_max"])
                for s in range(1, 5)
            ),
        "all_12_buckets_under_spacing_hard_ceiling":
            max(spacing_hws.values())
            <= float(
                gates["all_12_buckets_spacing_relative_95_halfwidth_max"]
            ),
        "at_least_10_buckets_under_spacing_target":
            sum(
                hw <= float(
                    gates["bucket_spacing_target_relative_95_halfwidth_max"]
                )
                for hw in spacing_hws.values()
            ) >= int(gates["buckets_meeting_spacing_target_required"]),
        "monte_carlo_calibration":
            (mc_ok if gates["monte_carlo_calibration_required"] else True),
    }

    passed = all(gate_results.values())
    decision = (
        contract["decision_rule"]["pass"]
        if passed
        else contract["decision_rule"]["fail"]
    )

    return {
        "schema_version": 1,
        "study_id": contract["study_id"],
        "stage": "phase0a_precision_simulation_result",
        "decision": decision,
        "pass": passed,
        "gate_results": gate_results,
        "slot_results": slot_results,
        "bucket_results": bucket_results,
        "summary": {
            "max_slot_relative_95_halfwidth": max(slot_hws.values()),
            "slots_at_or_below_target": sum(
                hw <= float(gates["slot_target_relative_95_halfwidth_max"])
                for hw in slot_hws.values()
            ),
            "max_bucket_spacing_relative_95_halfwidth":
                max(spacing_hws.values()),
            "buckets_at_or_below_spacing_target": sum(
                hw <= float(
                    gates["bucket_spacing_target_relative_95_halfwidth_max"]
                )
                for hw in spacing_hws.values()
            ),
            "variance_information_ratio_min": min(variance_ratios),
            "variance_information_ratio_median": statistics.median(variance_ratios),
            "variance_information_ratio_max": max(variance_ratios),
            "ratio_floor_applied_slot_years": floor_applied_slot_years,
        },
        "outcome_data_read": False,
        "market_data_read": False,
        "production_change_authorized": False,
    }


def synthetic_support(contract: dict, slot_fraction: float = 0.25) -> dict:
    years = contract["axis"]["years"]
    slots = {}
    for slot in range(1, 49):
        cell = cell_for_slot(contract, slot)
        by_year = {}
        for year in years:
            cell_neff = 100.0 + (year - years[0]) * 5.0
            by_year[str(year)] = {
                "slot_cluster_kish_neff": cell_neff * slot_fraction,
                "cell_cluster_kish_neff": cell_neff,
            }
        slots[str(slot)] = {"cell": cell, "by_year": by_year}
    return {
        "schema_version": 1,
        "study_id": contract["study_id"],
        "stage": "synthetic_selftest_support",
        "outcome_blind": True,
        "years": years,
        "slots": slots,
    }


def selftest(contract: dict) -> None:
    for slot in range(1, 49):
        assert cell_for_slot(contract, slot)

    support = synthetic_support(contract, 0.25)
    validate_support(contract, support)

    # A balanced four-slot cell gives variance-information ratio 4 and inflation 2.
    for slot in range(1, 49):
        slot_inv = 0.0
        cell_inv = 0.0
        for year in contract["axis"]["years"]:
            y = support["slots"][str(slot)]["by_year"][str(year)]
            s = float(y["slot_cluster_kish_neff"])
            c = float(y["cell_cluster_kish_neff"])
            slot_inv += 1.0 / min(s, c)
            cell_inv += 1.0 / c
        ratio = slot_inv / cell_inv
        assert abs(ratio - 4.0) < 1e-12
        assert abs(math.sqrt(ratio) - 2.0) < 1e-12

    # slot n_eff may exceed cell n_eff; this must not crash and must apply the floor.
    floor_case = synthetic_support(contract, 0.25)
    floor_case["slots"]["1"]["by_year"]["2018"]["slot_cluster_kish_neff"] = 150.0
    floor_case["slots"]["1"]["by_year"]["2018"]["cell_cluster_kish_neff"] = 100.0
    validate_support(contract, floor_case)
    floor_result = evaluate(contract, floor_case)
    assert floor_result["slot_results"]["1"]["ratio_floor_applied_slot_year_count"] == 1
    assert floor_result["summary"]["ratio_floor_applied_slot_years"] == 1

    # Exercise evaluate for one clearly precise PASS case and one thin FAIL case.
    pass_result = evaluate(contract, synthetic_support(contract, 1.0))
    assert pass_result["pass"] is True
    fail_result = evaluate(contract, synthetic_support(contract, 1.0 / 6.0))
    assert fail_result["pass"] is False

    # Reject extra keys so an outcome-bearing support object cannot silently pass.
    bad = json.loads(json.dumps(support))
    bad["slots"]["1"]["by_year"]["2018"]["outcome_value"] = 1.0
    try:
        validate_support(contract, bad)
    except RuntimeError:
        pass
    else:
        raise AssertionError("allowlist failed to reject extra field")

    print("PASS: Phase 0A precision simulation self-test")


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--selftest", action="store_true")
    group.add_argument("--evaluate", action="store_true")
    parser.add_argument("--support")
    parser.add_argument("--output")
    args = parser.parse_args()

    contract = load_json(CONTRACT_PATH)

    if args.selftest:
        selftest(contract)
        return

    if not args.support or not args.output:
        parser.error("--evaluate requires --support and --output")

    support = load_json(Path(args.support))
    result = evaluate(contract, support)
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "decision": result["decision"],
        "pass": result["pass"],
        **result["summary"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
