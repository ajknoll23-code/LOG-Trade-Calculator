from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CELLS = tuple(f"r{r}_{t}" for r in range(1, 7) for t in ("early", "mid", "late"))
TIERS = ("early", "mid", "late")
ROUNDS = tuple(range(1, 7))
EXPECTED_HOLDOUT_LEAGUES = (
    "10302", "21269", "23907", "64635",
    "65168", "68399", "70523", "74598",
)
EPS = 1e-12


class GateError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open() as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                x = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GateError(f"{path}:{n}: invalid JSONL") from exc
            if not isinstance(x, dict):
                raise GateError(f"{path}:{n}: row is not object")
            out.append(x)
    return out


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def import_file(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise GateError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def finite(v: Any) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def rel(new: float, base: float) -> float:
    if base <= 0:
        if abs(new - base) <= 1e-12:
            return 0.0
        raise GateError("relative comparison has nonpositive baseline")
    return (new - base) / base


def baseline_cells(prereg: dict[str, Any]) -> dict[str, float]:
    d = prereg["frozen_primary_candidate"]["deployed_pick_base_2027"]
    return {
        f"r{r}_{t}": float(d[str(r)][t])
        for r in ROUNDS
        for t in TIERS
    }


def candidate_cells(prereg: dict[str, Any]) -> dict[str, float]:
    d = prereg["frozen_primary_candidate"]["frozen_candidate_pick_base_2027"]
    return {
        f"r{r}_{t}": float(d[str(r)][t])
        for r in ROUNDS
        for t in TIERS
    }


def validate_contracts(prereg: dict[str, Any], phase1: dict[str, Any]) -> None:
    assert prereg["decision"] == "FREEZE_V8_1_C1_CARRYFORWARD_SPARSE_SENSITIVITY_NEXT"
    assert prereg["status"] == "FROZEN_AFTER_V8_DEVELOPMENT_BEFORE_V8_1_SPARSE_SENSITIVITY_OR_2024_HOLDOUT"
    assert prereg["study_id"] == "draft-pick-fv-v8-1-global-scale-sparse-tail-holdout-confirmation"
    assert prereg["evidence_status"]["2024_rookie_holdout_outcomes_read"] is False
    assert prereg["evidence_status"]["2024_rookie_holdout_remains_independent"] is True
    assert prereg["frozen_primary_candidate"]["candidate_id"] == "C1_GLOBAL_SCALE_R1_R6_CARRYFORWARD"
    assert float(prereg["frozen_primary_candidate"]["k"]) == 0.3557942893
    assert prereg["frozen_primary_candidate"]["primary_candidate_refit_after_this_freeze_allowed"] is False
    assert prereg["frozen_primary_candidate"]["YEAR_DISCOUNT_fit_or_change_allowed"] is False

    h2 = prereg["phase2_2024_h2_independent_confirmation"]
    assert h2["outcomes_sealed_until_phase1_pass"] is True
    assert h2["open_exactly_once"] is True
    assert h2["candidate_refit_allowed"] is False
    assert float(h2["candidate_parameter_must_equal"]) == 0.3557942893
    assert h2["comparison_baseline"] == "exact deployed C0 R1-R6 PICK_BASE"
    assert h2["pass_decision"] == "PASS_V8_1_2024_H2_CONTINUE_TO_FUTURE_H3"
    assert h2["failure_decision"] == "STOP_V8_1_2024_H2_CONFIRMATION"
    assert h2["can_authorize_production"] is False
    assert h2["primary_gates"] == [
        "2024 H2 O2 equal-cell macro MAE improvement vs C0 >=5%",
        "no individual round 2024 H2 O2 macro MAE regression vs C0 worse than 5%",
        "combined R5-R6 2024 H2 O2 macro MAE relative regression vs C0 <=5%",
        "2024 H2 O1 normalized 18-cell shape-error regression vs C0 <=2%",
        "all frozen source/identity/retention gates remain satisfied",
        "candidate parameter and 18-cell values unchanged since V8.1 Phase 0 freeze",
    ]

    assert phase1["decision"] == "PASS_V8_1_SPARSE_TAIL_SENSITIVITY_AUTHORIZE_2024_H2_ONCE"
    assert phase1["status"] == "SPARSE_TAIL_SENSITIVITY_PASS"
    assert phase1["sparse_sensitivity_gate_pass"] is True
    assert phase1["2024_H2_outcome_open_authorized_next_stage"] is True
    assert phase1["2024_holdout_pick_identity_file_read"] is False
    assert phase1["2024_holdout_rookie_outcomes_read"] is False
    assert phase1["2024_holdout_outcomes_remain_sealed"] is True
    assert phase1["primary_candidate_refit_or_changed"] is False
    assert phase1["selection_or_tuning_performed"] is False
    assert phase1["production_change_authorized"] is False
    assert phase1["variant_n"] == 7
    assert all(v["pass"] is True for v in phase1["variants"])

    c0 = baseline_cells(prereg)
    c1 = candidate_cells(prereg)
    k = float(prereg["frozen_primary_candidate"]["k"])
    seq = [c1[c] for c in CELLS]
    assert all(v > 0 for v in seq)
    assert all(seq[i] >= seq[i + 1] - 1e-10 for i in range(len(seq) - 1))
    for c in CELLS:
        if not math.isclose(c1[c], c0[c] * k, rel_tol=0, abs_tol=1e-7):
            raise GateError(f"frozen candidate drift {c}: {c1[c]} vs {c0[c] * k}")


def validate_holdout_source(hold: dict[str, Any]) -> dict[str, Any]:
    assert hold["stage"] == "phase1_6_holdout_source_identity_freeze"
    assert hold["research_only"] is True
    assert hold["decision"] == "PASS_V8_1_PHASE1_6_ROOKIE_ONLY_SCOPE_HARDENING_H2_AUTHORIZED"
    assert hold["corrected_source_gate_pass"] is True
    assert int(hold["selected_clean_full72_league_n"]) == 8
    assert int(hold["minimum_clean_full72_leagues"]) == 8
    assert int(hold["retained_occurrence_n"]) == 574
    assert int(hold["expected_raw_occurrence_n"]) == 576
    assert hold["new_2024_search_used"] is False
    assert hold["replacement_or_substitution_used"] is False
    assert hold["manual_league_id_exclusion_used"] is False
    assert hold["2024_rookie_outcomes_read"] is False
    assert hold["2025_rookie_outcomes_read"] is False
    assert hold["candidate_fit_performed"] is False
    assert hold["candidate_parameter_changed"] is False
    assert hold["market_or_ktc_values_read"] is False
    assert hold["package_vote_data_read"] is False
    assert hold["production_change_authorized"] is False

    leagues = tuple(sorted((str(x["league_id"]) for x in hold["clean_leagues"]), key=int))
    if leagues != EXPECTED_HOLDOUT_LEAGUES:
        raise GateError(f"frozen corrected 2024 league cohort drift: {leagues}")
    assert list(leagues) == hold["selected_league_ids"]

    excluded = {
        str(x["league_id"]): x["league_name"]
        for x in hold["excluded_leagues"]
    }
    assert excluded == {
        "48514": "Bevy of Devy Dynasty League",
        "65200": "The Devy's in the Details",
    }
    assert all(
        x["exclusion_reason"] == "explicit_devy_token_in_frozen_league_name"
        for x in hold["excluded_leagues"]
    )

    diag = hold["diagnostics"]
    assert diag["retention_gate_pass"] is True
    assert diag["identity_gate_pass"] is True
    assert diag["sleeper_gate_pass"] is True
    assert float(diag["overall_identity_coverage"]) >= 0.95 - EPS
    assert float(diag["overall_sleeper_ready_coverage"]) >= 0.95 - EPS
    assert diag["weight_normalization_proved"] is True
    assert len(diag["cell_year"]) == 18

    occ = hold["occurrences"]
    if not isinstance(occ, list) or not occ:
        raise GateError("empty holdout occurrence list")
    if len(occ) != 574:
        raise GateError(f"corrected holdout occurrence drift: {len(occ)}")

    seen = set()
    cell_weight = defaultdict(float)
    source_weight = 0.0
    by_cell = Counter()
    by_league = Counter()
    for r in occ:
        key = (str(r["league_id"]), int(r["overall_slot"]))
        if key in seen:
            raise GateError(f"duplicate holdout occurrence {key}")
        seen.add(key)
        if str(r["league_id"]) not in EXPECTED_HOLDOUT_LEAGUES:
            raise GateError("occurrence outside corrected frozen holdout cohort")
        if int(r["draft_year"]) != 2024:
            raise GateError("non-2024 holdout occurrence")
        c = str(r["cell"])
        if c not in CELLS:
            raise GateError(f"invalid cell {c}")
        w = float(r["cell_weight_v8_1_holdout"])
        sw = float(r["source_weight_v8_1_holdout"])
        if w <= 0 or sw <= 0:
            raise GateError("nonpositive source weight")
        cell_weight[c] += w
        source_weight += sw
        by_cell[c] += 1
        by_league[str(r["league_id"])] += 1

    for c in CELLS:
        if not math.isclose(cell_weight[c], 1.0, rel_tol=0, abs_tol=1e-10):
            raise GateError(f"cell source weight drift {c}: {cell_weight[c]}")
        if by_cell[c] <= 0:
            raise GateError(f"empty holdout cell {c}")
    if not math.isclose(source_weight, 1.0, rel_tol=0, abs_tol=1e-10):
        raise GateError(f"source weight total drift: {source_weight}")

    return {
        "retained_occurrence_n": len(occ),
        "expected_raw_occurrence_n": 576,
        "overall_retention_fraction": len(occ) / 576,
        "overall_identity_coverage": float(diag["overall_identity_coverage"]),
        "overall_sleeper_ready_coverage": float(diag["overall_sleeper_ready_coverage"]),
        "league_ids": list(leagues),
        "excluded_preoutcome_devy_league_ids": ["48514", "65200"],
        "occurrences_by_cell": dict(sorted(by_cell.items())),
        "occurrences_by_league": dict(sorted(by_league.items(), key=lambda kv: int(kv[0]))),
    }

def prove_first48_draft_replay(hold: dict[str, Any], frozen_v6_rows: list[dict[str, Any]]) -> dict[str, Any]:
    frozen = {}
    for r in frozen_v6_rows:
        lid = str(r.get("league_id"))
        if lid not in EXPECTED_HOLDOUT_LEAGUES:
            continue
        slot = int(r["overall_slot"])
        if slot > 48:
            continue
        frozen[(lid, slot)] = r

    rebuilt = {}
    for r in hold["occurrences"]:
        lid = str(r["league_id"])
        slot = int(r["overall_slot"])
        if slot <= 48:
            rebuilt[(lid, slot)] = r

    if set(frozen) != set(rebuilt):
        only_frozen = sorted(set(frozen) - set(rebuilt))[:20]
        only_rebuilt = sorted(set(rebuilt) - set(frozen))[:20]
        raise GateError(f"first48 retained-slot drift frozen_only={only_frozen} rebuilt_only={only_rebuilt}")

    fields = ("mfl_player_id", "franchise_id", "round", "within_round_pick")
    mismatches = []
    for key in sorted(frozen, key=lambda x: (int(x[0]), x[1])):
        a = frozen[key]
        b = rebuilt[key]
        for f in fields:
            av = str(a.get(f) or "")
            bv = str(b.get(f) or "")
            if av != bv:
                mismatches.append({"key": key, "field": f, "frozen": av, "rebuilt": bv})
    if mismatches:
        raise GateError(f"first48 raw draft replay mismatch: {mismatches[:10]}")

    return {
        "frozen_first48_retained_occurrence_n": len(frozen),
        "rebuilt_first48_retained_occurrence_n": len(rebuilt),
        "raw_fields_checked": list(fields),
        "exact_match": True,
    }


def build_targets(
    hold: dict[str, Any],
    p2,
    arts: dict[int, dict[str, Any]],
    master: dict[str, dict[str, Any]],
) -> tuple[dict[tuple[int, str], dict[str, Any]], dict[str, Any]]:
    by_sid: dict[str, dict[str, Any]] = {}
    occurrence_ready = 0
    occurrence_identity = 0
    for r in hold["occurrences"]:
        if bool(r.get("identity_resolved")):
            occurrence_identity += 1
        sid = p2.stable(r.get("sleeper_id"))
        if not (bool(r.get("identity_resolved")) and bool(r.get("outcome_ready_sleeper_id")) and sid):
            continue
        pos = p2.norm_pos(r.get("draft_position"))
        if pos not in p2.POSITIONS:
            continue
        occurrence_ready += 1
        gsis = p2.stable(r.get("gsis_id"))
        cur = by_sid.get(sid)
        if cur is None:
            by_sid[sid] = {
                "sleeper_id": sid,
                "gsis_id": gsis,
                "position": pos,
                "name": r.get("name"),
                "stable_player_key": r.get("stable_player_key") or f"sleeper:{sid}",
            }
        else:
            if cur["position"] != pos:
                raise GateError(f"holdout target position conflict for sleeper {sid}: {cur['position']} vs {pos}")
            if cur.get("gsis_id") and gsis and cur["gsis_id"] != gsis:
                raise GateError(f"holdout target GSIS conflict for sleeper {sid}")
            if not cur.get("gsis_id") and gsis:
                cur["gsis_id"] = gsis

    birth_source_counts = Counter()
    birth_conflicts = []
    targets: dict[tuple[int, str], dict[str, Any]] = {}
    missing_birth = []
    for sid, meta in sorted(by_sid.items(), key=lambda kv: kv[0]):
        gsis = meta.get("gsis_id")
        candidates: list[tuple[str, str]] = []
        if gsis and gsis in master and master[gsis].get("birth_date"):
            candidates.append(("pinned_nflverse_players", master[gsis]["birth_date"]))
        for season in (2024, 2025):
            rec = arts[season]["players"].get(sid)
            if isinstance(rec, dict):
                bd = p2.valid_dob(rec.get("birth_date"))
                if bd:
                    candidates.append((f"pinned_nflverse_roster_{season}", bd))
                rgsis = p2.stable(rec.get("gsis_id"))
                if gsis and rgsis and gsis != rgsis:
                    raise GateError(f"season artifact GSIS conflict for sleeper {sid}")
        uniq = sorted({bd for _, bd in candidates})
        if len(uniq) > 1:
            birth_conflicts.append({"sleeper_id": sid, "name": meta.get("name"), "candidates": candidates})
            continue
        birth = uniq[0] if uniq else None
        if birth:
            source = next(src for src, bd in candidates if bd == birth)
            birth_source_counts[source] += 1
        else:
            source = None
            missing_birth.append({"sleeper_id": sid, "name": meta.get("name"), "position": meta["position"], "gsis_id": gsis})
        targets[(2024, sid)] = {
            **meta,
            "birth_date": birth,
            "birth_date_source": source,
        }

    if birth_conflicts:
        raise GateError(f"DOB conflicts in frozen lineage: {birth_conflicts[:10]}")

    supported_occurrence_n = occurrence_ready
    unsupported_occurrence_n = len(hold["occurrences"]) - supported_occurrence_n
    return targets, {
        "source_occurrence_n": len(hold["occurrences"]),
        "supported_model_position_occurrence_n": supported_occurrence_n,
        "unsupported_model_position_occurrence_n": unsupported_occurrence_n,
        "unique_identity_ready_target_n": len(by_sid),
        "unique_scoring_target_n": len(targets),
        "missing_birth_date_unique_target_n": len(missing_birth),
        "missing_birth_date_targets": missing_birth,
        "birth_date_source_counts": dict(birth_source_counts),
        "identity_resolved_occurrence_n": occurrence_identity,
        "sleeper_and_position_ready_occurrence_n": occurrence_ready,
        "manual_matching_used": False,
        "name_matching_used": False,
        "current_sleeper_player_index_read": False,
    }


def score_occurrences(
    hold: dict[str, Any],
    scored_targets: dict[tuple[int, str], dict[str, Any]],
    p2,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cell = {c: {"retained": 0, "identity": 0, "sleeper": 0, "h2_o1": 0, "h2_o2": 0} for c in CELLS}
    for src in hold["occurrences"]:
        r = dict(src)
        c = str(r["cell"])
        cell[c]["retained"] += 1
        cell[c]["identity"] += int(bool(r.get("identity_resolved")))
        cell[c]["sleeper"] += int(bool(r.get("outcome_ready_sleeper_id")))
        sid = p2.stable(r.get("sleeper_id"))
        target = scored_targets.get((2024, sid)) if sid else None
        h2 = target.get("H2") if target else None
        o1_ready = bool(h2 and h2.get("mature") is True and h2.get("O1") is not None)
        o2_ready = bool(h2 and h2.get("mature") is True and h2.get("O2") is not None)
        if o1_ready:
            cell[c]["h2_o1"] += 1
        if o2_ready:
            cell[c]["h2_o2"] += 1
        r.update({
            "holdout_2024_outcomes_read": True,
            "H2": h2,
            "h2_o1_ready": o1_ready,
            "h2_o2_ready": o2_ready,
            "candidate_fit_performed": False,
            "candidate_parameter_changed": False,
            "production_change_authorized": False,
        })
        rows.append(r)

    for c in CELLS:
        d = cell[c]
        n = d["retained"]
        d["identity_coverage"] = d["identity"] / n if n else 0.0
        d["sleeper_ready_coverage"] = d["sleeper"] / n if n else 0.0
        d["h2_o1_ready_coverage"] = d["h2_o1"] / n if n else 0.0
        d["h2_o2_ready_coverage"] = d["h2_o2"] / n if n else 0.0
        if d["h2_o1"] <= 0 or d["h2_o2"] <= 0:
            raise GateError(f"H2 metric not computable in {c}")

    total = len(rows)
    return rows, {
        "overall_h2_o1_ready_coverage": sum(int(r["h2_o1_ready"]) for r in rows) / total,
        "overall_h2_o2_ready_coverage": sum(int(r["h2_o2_ready"]) for r in rows) / total,
        "by_cell": cell,
        "all_18_cells_h2_o1_computable": all(cell[c]["h2_o1"] > 0 for c in CELLS),
        "all_18_cells_h2_o2_computable": all(cell[c]["h2_o2"] > 0 for c in CELLS),
    }


def metric_rows(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    if field not in ("O1", "O2"):
        raise GateError(f"unknown metric field {field}")
    chosen = []
    raw_sum = defaultdict(float)
    for r in rows:
        h2 = r.get("H2") or {}
        val = h2.get(field)
        if val is None:
            continue
        c = str(r["cell"])
        w = float(r["cell_weight_v8_1_holdout"])
        raw_sum[c] += w
        x = dict(r)
        x["_target"] = float(val)
        x["_raw_w"] = w
        chosen.append(x)
    for c in CELLS:
        if raw_sum[c] <= 0:
            raise GateError(f"zero {field} support in {c}")
    check = defaultdict(float)
    for x in chosen:
        c = str(x["cell"])
        x["_w"] = (1.0 / 18.0) * float(x["_raw_w"]) / raw_sum[c]
        check[c] += x["_w"]
    for c in CELLS:
        if not math.isclose(check[c], 1 / 18, rel_tol=0, abs_tol=1e-12):
            raise GateError(f"{field} equal-cell normalization failure {c}: {check[c]}")
    return chosen


def cell_mae(rows: list[dict[str, Any]], values: dict[str, float]) -> dict[str, float]:
    err = defaultdict(float)
    wt = defaultdict(float)
    for r in rows:
        c = str(r["cell"])
        w = float(r["_w"])
        err[c] += w * abs(float(values[c]) - float(r["_target"]))
        wt[c] += w
    out = {}
    for c in CELLS:
        if wt[c] <= 0:
            raise GateError(f"zero MAE weight {c}")
        out[c] = err[c] / wt[c]
    return out


def normalized_shape(values: dict[str, float]) -> dict[str, float]:
    mean = sum(float(values[c]) for c in CELLS) / 18.0
    if mean <= 0:
        raise GateError("nonpositive normalized shape mean")
    return {c: float(values[c]) / mean for c in CELLS}


def shape_error(o1_rows: list[dict[str, Any]], values: dict[str, float]) -> tuple[float, dict[str, float]]:
    by = defaultdict(float)
    wt = defaultdict(float)
    for r in o1_rows:
        c = str(r["cell"])
        w = float(r["_w"])
        by[c] += w * float(r["_target"])
        wt[c] += w
    target = {c: by[c] / wt[c] for c in CELLS}
    a = normalized_shape(target)
    b = normalized_shape(values)
    return sum(abs(a[c] - b[c]) for c in CELLS) / 18.0, target


def evaluate(rows: list[dict[str, Any]], prereg: dict[str, Any]) -> dict[str, Any]:
    c0 = baseline_cells(prereg)
    c1 = candidate_cells(prereg)
    o2 = metric_rows(rows, "O2")
    o1 = metric_rows(rows, "O1")

    c0_cells = cell_mae(o2, c0)
    c1_cells = cell_mae(o2, c1)
    c0_macro = sum(c0_cells.values()) / 18.0
    c1_macro = sum(c1_cells.values()) / 18.0
    improvement = (c0_macro - c1_macro) / c0_macro

    round_rel = {}
    round_mae = {}
    for rnd in ROUNDS:
        cs = [f"r{rnd}_{t}" for t in TIERS]
        b = sum(c0_cells[c] for c in cs) / 3.0
        n = sum(c1_cells[c] for c in cs) / 3.0
        round_mae[str(rnd)] = {"C0": b, "C1": n}
        round_rel[str(rnd)] = rel(n, b)

    tail_cells = [c for c in CELLS if int(c[1]) >= 5]
    c0_tail = sum(c0_cells[c] for c in tail_cells) / 6.0
    c1_tail = sum(c1_cells[c] for c in tail_cells) / 6.0
    tail_rel = rel(c1_tail, c0_tail)

    c0_shape, target_o1_cells = shape_error(o1, c0)
    c1_shape, _ = shape_error(o1, c1)
    if c0_shape <= 1e-15:
        shape_rel = 0.0 if abs(c1_shape - c0_shape) <= 1e-12 else math.inf
    else:
        shape_rel = rel(c1_shape, c0_shape)

    return {
        "h2_o2": {
            "C0_equal_cell_macro_mae": c0_macro,
            "C1_equal_cell_macro_mae": c1_macro,
            "C1_improvement_vs_C0": improvement,
            "cell_mae_C0": c0_cells,
            "cell_mae_C1": c1_cells,
            "round_mae": round_mae,
            "round_relative_regression_vs_C0": round_rel,
            "combined_r5_r6_C0_macro_mae": c0_tail,
            "combined_r5_r6_C1_macro_mae": c1_tail,
            "combined_r5_r6_relative_regression_vs_C0": tail_rel,
        },
        "h2_o1_shape": {
            "target_cell_means": target_o1_cells,
            "C0_normalized_18_cell_shape_error": c0_shape,
            "C1_normalized_18_cell_shape_error": c1_shape,
            "C1_relative_regression_vs_C0": shape_rel,
        },
    }


def score(args) -> None:
    repo = Path(args.repo)
    prereg_path = Path(args.prereg)
    phase1_path = Path(args.phase1)
    holdout_path = Path(args.holdout)
    p2_dir = Path(args.p2_dir)
    season24_path = Path(args.season_2024)
    season25_path = Path(args.season_2025)
    p2_engine_path = Path(args.p2_engine)
    players_path = Path(args.players)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    prereg = load(prereg_path)
    phase1 = load(phase1_path)
    validate_contracts(prereg, phase1)

    hold = load(holdout_path)
    source_diag = validate_holdout_source(hold)
    frozen_v6 = read_jsonl(repo / "research/draft-pick-fv-v6/r1_r4_holdout_2024_pick_identity_v6_1.jsonl")
    replay = prove_first48_draft_replay(hold, frozen_v6)

    p2_summary = load(p2_dir / "v8_phase2_historical_outcome_summary.json")
    p2_manifest = load(p2_dir / "v8_phase2_historical_outcome_manifest.json")
    assert p2_summary["decision"] == "PROCEED_TO_V8_PHASE3_LOYO_DEVELOPMENT_SELECTION"
    assert p2_manifest["decision"] == p2_summary["decision"]
    assert p2_summary["calendar_seasons_read"] == list(range(2018, 2026))
    assert p2_summary["holdout_2024_pick_identity_file_read"] is False
    assert p2_summary["holdout_2024_rookie_outcomes_scored"] is False
    assert p2_summary["holdout_2024_pick_outcomes_remain_sealed"] is True
    assert p2_summary["market_or_ktc_values_read"] is False
    assert p2_summary["package_vote_data_read"] is False
    assert p2_summary["production_change_authorized"] is False

    p2 = import_file(p2_engine_path, "v8_phase2_frozen")
    p2.selftest()
    arts = {2024: load(season24_path), 2025: load(season25_path)}
    for season, art in arts.items():
        assert art["season"] == season
        assert art["availability_pass"] is True
        assert art["historical_player_outcomes_read"] is True
        assert art["holdout_2024_pick_identity_file_read"] is False
        assert art["holdout_2024_rookie_outcomes_scored"] is False
        assert art["candidate_fit_performed"] is False
        assert art["candidate_scores_computed"] is False
        assert art["production_change_authorized"] is False

    baselines_raw = load(p2_dir / "v8_phase2_replacement_baselines.json")
    baselines = {int(k): v for k, v in baselines_raw.items()}
    assert 2024 in baselines and 2025 in baselines

    master = p2.load_players_master(players_path)
    targets, target_diag = build_targets(hold, p2, arts, master)
    # Frozen pre-outcome source-domain fact: three K/P occurrences are outside
    # the seven-position model domain. This is not outcome-dependent and is
    # recorded before H2 is opened in the one-shot lock.
    assert target_diag["source_occurrence_n"] == 574
    assert target_diag["supported_model_position_occurrence_n"] == 571
    assert target_diag["unsupported_model_position_occurrence_n"] == 3
    v7 = load(repo / "research/draft-pick-fv-v7/r1_r6_full_scale_preregistration_v7.json")
    v5 = load(repo / "research/draft-pick-fv-v5/r1_r2_bridge_preregistration_v5.json")
    hist = v7["historical_outcome_contract"]
    scored_targets = p2.score_targets(targets, arts, baselines, hist, v5, repo)

    scored_occ, readiness = score_occurrences(hold, scored_targets, p2)
    metrics = evaluate(scored_occ, prereg)

    source_identity_ok = (
        hold["corrected_source_gate_pass"] is True
        and hold["diagnostics"]["retention_gate_pass"] is True
        and hold["diagnostics"]["identity_gate_pass"] is True
        and hold["diagnostics"]["sleeper_gate_pass"] is True
        and int(hold["selected_clean_full72_league_n"]) == 8
        and replay["exact_match"] is True
    )
    candidate_unchanged = (
        float(prereg["frozen_primary_candidate"]["k"]) == 0.3557942893
        and phase1["frozen_primary"]["k"] == 0.3557942893
        and phase1["primary_candidate_refit_or_changed"] is False
    )

    o2 = metrics["h2_o2"]
    shape = metrics["h2_o1_shape"]
    round_rel = o2["round_relative_regression_vs_C0"]
    gates = {
        "2024_h2_o2_equal_cell_macro_mae_improvement_vs_C0_ge_5pct": o2["C1_improvement_vs_C0"] >= 0.05 - EPS,
        "no_individual_round_2024_h2_o2_macro_mae_regression_vs_C0_worse_than_5pct": max(round_rel.values()) <= 0.05 + EPS,
        "combined_r5_r6_2024_h2_o2_macro_mae_relative_regression_vs_C0_le_5pct": o2["combined_r5_r6_relative_regression_vs_C0"] <= 0.05 + EPS,
        "2024_h2_o1_normalized_18_cell_shape_error_regression_vs_C0_le_2pct": shape["C1_relative_regression_vs_C0"] <= 0.02 + EPS,
        "all_frozen_source_identity_retention_gates_remain_satisfied": source_identity_ok,
        "candidate_parameter_and_18_cell_values_unchanged_since_v8_1_phase0_freeze": candidate_unchanged,
    }
    passed = all(gates.values())
    decision = (
        "PASS_V8_1_2024_H2_CONTINUE_TO_FUTURE_H3"
        if passed else
        "STOP_V8_1_2024_H2_CONFIRMATION"
    )
    next_stage = (
        "draft-pick-fv-v8-1-future-2024-h3-primary-confirmation-after-2026-regular-season"
        if passed else None
    )

    out_scored = out / "v8_1_phase2_2024_h2_scored_occurrences.jsonl"
    write_jsonl(out_scored, scored_occ)

    result = {
        "schema_version": 1,
        "study_id": prereg["study_id"],
        "stage": "phase2_2024_h2_independent_confirmation",
        "status": "H2_CONFIRMATION_PASS" if passed else "H2_CONFIRMATION_STOP",
        "generated_at_utc": now(),
        "decision": decision,
        "research_only": True,
        "frozen_primary": {
            "candidate_id": prereg["frozen_primary_candidate"]["candidate_id"],
            "k": float(prereg["frozen_primary_candidate"]["k"]),
            "candidate_refit_performed": False,
            "candidate_parameter_changed": False,
            "candidate_values": candidate_cells(prereg),
            "baseline_values": baseline_cells(prereg),
        },
        "source_holdout": {
            **source_diag,
            "first48_replay": replay,
            "holdout_source_sha256": sha(holdout_path),
            "v6_frozen_r1_r4_holdout_sha256": sha(repo / "research/draft-pick-fv-v6/r1_r4_holdout_2024_pick_identity_v6_1.jsonl"),
            "new_2024_search_used": False,
            "replacement_or_substitution_used": False,
            "post_outcome_contamination_reclassification_used": False,
        },
        "target_lineage": target_diag,
        "outcome_readiness": readiness,
        "metrics": metrics,
        "gates": gates,
        "gate_pass": passed,
        "holdout_opening": {
            "2024_holdout_pick_identity_read": True,
            "2024_rookie_H2_outcomes_scored": True,
            "H2_seasons": [2024, 2025],
            "2024_H3_confirmation_scored": False,
            "partial_2026_data_read": False,
            "2026_outcomes_read": False,
            "open_exactly_once_contract_satisfied": True,
        },
        "firewalls": {
            "candidate_refit_performed": False,
            "candidate_selection_or_tuning_performed": False,
            "YEAR_DISCOUNT_fit_or_changed": False,
            "market_or_ktc_values_read": False,
            "package_vote_data_read": False,
            "new_2024_league_search_performed": False,
            "partial_2026_H3_scoring_performed": False,
            "production_change_authorized": False,
            "automatic_production_deployment_allowed": False,
        },
        "inputs": {
            "preregistration_sha256": sha(prereg_path),
            "phase1_sparse_sensitivity_sha256": sha(phase1_path),
            "holdout_source_sha256": sha(holdout_path),
            "v8_phase2_summary_sha256": sha(p2_dir / "v8_phase2_historical_outcome_summary.json"),
            "v8_phase2_manifest_sha256": sha(p2_dir / "v8_phase2_historical_outcome_manifest.json"),
            "v8_phase2_replacement_baselines_sha256": sha(p2_dir / "v8_phase2_replacement_baselines.json"),
            "season_2024_sha256": sha(season24_path),
            "season_2025_sha256": sha(season25_path),
            "v8_phase2_engine_sha256": sha(p2_engine_path),
            "pinned_players_master_sha256": sha(players_path),
            "h2_confirmation_engine_sha256": sha(Path(__file__)),
        },
        "outputs": {
            out_scored.name: {"sha256": sha(out_scored), "row_n": len(scored_occ)},
        },
        "next_stage": next_stage,
        "production_change_authorized": False,
    }

    result_path = out / "v8_1_phase2_2024_h2_confirmation.json"
    write_json(result_path, result)

    lines = [
        "# Draft Pick FV V8.1 — Phase 2 2024 H2 Independent Confirmation",
        "",
        f"**Decision:** `{decision}`",
        "",
        f"- Frozen candidate: **C1, k = {result['frozen_primary']['k']:.10f}** (unchanged; no refit)",
        f"- Corrected frozen full-72 holdout leagues: **8 / 10 original**",
        f"- Retained holdout occurrences: **{source_diag['retained_occurrence_n']} / 576 expected after source hardening**",
        f"- H2 O2 ready coverage: **{readiness['overall_h2_o2_ready_coverage']:.2%}**",
        f"- H2 O2 macro-MAE improvement vs C0: **{o2['C1_improvement_vs_C0']:.2%}**",
        f"- Worst round H2 O2 relative regression vs C0: **{max(round_rel.values()):.2%}**",
        f"- Combined R5-R6 H2 O2 relative regression vs C0: **{o2['combined_r5_r6_relative_regression_vs_C0']:.2%}**",
        f"- H2 O1 normalized-shape relative regression vs C0: **{shape['C1_relative_regression_vs_C0']:.2%}**",
        f"- Gates passed: **{sum(bool(v) for v in gates.values())} / {len(gates)}**",
        "",
        "The 2024 holdout is now spent for H2. No 2026 outcome was read, no H3 confirmation was scored, and production remains unauthorized.",
    ]
    md_path = out / "v8_1_phase2_2024_h2_confirmation.md"
    md_path.write_text("\n".join(lines) + "\n")

    manifest = {
        "schema_version": 1,
        "study_id": prereg["study_id"],
        "stage": "phase2_2024_h2_independent_confirmation_manifest",
        "status": result["status"],
        "generated_at_utc": result["generated_at_utc"],
        "decision": decision,
        "gate_pass": passed,
        "primary_candidate_id": result["frozen_primary"]["candidate_id"],
        "primary_candidate_k": result["frozen_primary"]["k"],
        "candidate_refit_performed": False,
        "2024_holdout_H2_opened": True,
        "2024_H3_confirmation_scored": False,
        "2026_outcomes_read": False,
        "production_change_authorized": False,
        "input_hashes": result["inputs"],
        "output_hashes": {
            result_path.name: sha(result_path),
            md_path.name: sha(md_path),
            out_scored.name: sha(out_scored),
        },
        "next_stage": next_stage,
    }
    manifest_path = out / "v8_1_phase2_2024_h2_confirmation_manifest.json"
    write_json(manifest_path, manifest)

    print("DECISION=", decision, sep="")
    print(f"H2_O2_IMPROVEMENT={o2['C1_improvement_vs_C0']:.10f}")
    print(f"WORST_ROUND_REL={max(round_rel.values()):.10f}")
    print(f"R5_R6_REL={o2['combined_r5_r6_relative_regression_vs_C0']:.10f}")
    print(f"O1_SHAPE_REL={shape['C1_relative_regression_vs_C0']:.10f}")
    print(f"GATES={sum(bool(v) for v in gates.values())}/{len(gates)}")
    print("2024_H3_CONFIRMATION_SCORED=false")
    print("PRODUCTION_CHANGE_AUTHORIZED=false")


def check(args) -> None:
    out = Path(args.out_dir)
    r = load(out / "v8_1_phase2_2024_h2_confirmation.json")
    m = load(out / "v8_1_phase2_2024_h2_confirmation_manifest.json")
    allowed = {
        "PASS_V8_1_2024_H2_CONTINUE_TO_FUTURE_H3",
        "STOP_V8_1_2024_H2_CONFIRMATION",
    }
    assert r["decision"] in allowed
    assert m["decision"] == r["decision"]
    assert r["gate_pass"] == all(r["gates"].values())
    assert m["gate_pass"] == r["gate_pass"]
    assert r["frozen_primary"]["k"] == 0.3557942893
    assert r["frozen_primary"]["candidate_refit_performed"] is False
    assert r["frozen_primary"]["candidate_parameter_changed"] is False
    assert r["holdout_opening"]["2024_holdout_pick_identity_read"] is True
    assert r["holdout_opening"]["2024_rookie_H2_outcomes_scored"] is True
    assert r["holdout_opening"]["2024_H3_confirmation_scored"] is False
    assert r["holdout_opening"]["partial_2026_data_read"] is False
    assert r["holdout_opening"]["2026_outcomes_read"] is False
    assert r["firewalls"]["candidate_refit_performed"] is False
    assert r["firewalls"]["candidate_selection_or_tuning_performed"] is False
    assert r["firewalls"]["YEAR_DISCOUNT_fit_or_changed"] is False
    assert r["firewalls"]["market_or_ktc_values_read"] is False
    assert r["firewalls"]["package_vote_data_read"] is False
    assert r["firewalls"]["new_2024_league_search_performed"] is False
    assert r["firewalls"]["partial_2026_H3_scoring_performed"] is False
    assert r["firewalls"]["production_change_authorized"] is False
    assert r["firewalls"]["automatic_production_deployment_allowed"] is False
    assert r["source_holdout"]["league_ids"] == list(EXPECTED_HOLDOUT_LEAGUES)
    assert r["source_holdout"]["first48_replay"]["exact_match"] is True
    assert len(r["metrics"]["h2_o2"]["round_relative_regression_vs_C0"]) == 6
    assert len(r["metrics"]["h2_o2"]["cell_mae_C0"]) == 18
    assert len(r["metrics"]["h2_o2"]["cell_mae_C1"]) == 18
    for v in r["metrics"]["h2_o2"]["round_relative_regression_vs_C0"].values():
        assert finite(v)
    for name, expected in m["output_hashes"].items():
        assert sha(out / name) == expected, (name, sha(out / name), expected)
    scored = read_jsonl(out / "v8_1_phase2_2024_h2_scored_occurrences.jsonl")
    assert len(scored) == r["source_holdout"]["retained_occurrence_n"]
    print("PASS: V8.1 Phase 2 H2 confirmation outputs validate.")


def selftest() -> None:
    # Shape invariance: a global scalar must have identical normalized shape.
    c0 = {c: float(2000 - i * 50) for i, c in enumerate(CELLS)}
    c1 = {c: v * 0.35 for c, v in c0.items()}
    a = normalized_shape(c0)
    b = normalized_shape(c1)
    assert max(abs(a[c] - b[c]) for c in CELLS) < 1e-12

    # Equal-cell weighting remains exactly 1/18 after an arbitrary missing-row pattern.
    rows = []
    for i, c in enumerate(CELLS):
        for j in range(3):
            rows.append({"cell": c, "cell_weight_v8_1_holdout": 1 / 3, "H2": {"O1": 10 + i + j, "O2": 100 + i + j}})
    rows = [r for k, r in enumerate(rows) if k not in {1, 8, 20}]
    for field in ("O1", "O2"):
        xs = metric_rows(rows, field)
        sums = defaultdict(float)
        for x in xs:
            sums[x["cell"]] += x["_w"]
        assert all(math.isclose(sums[c], 1 / 18, abs_tol=1e-12) for c in CELLS)

    # Relative metrics use the frozen direction convention: negative is improvement.
    assert math.isclose(rel(90, 100), -0.1)
    assert math.isclose(rel(105, 100), 0.05)
    print("PASS: V8.1 Phase 2 H2 confirmation engine self-test")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--repo")
    ap.add_argument("--prereg")
    ap.add_argument("--phase1")
    ap.add_argument("--holdout")
    ap.add_argument("--p2-dir")
    ap.add_argument("--season-2024")
    ap.add_argument("--season-2025")
    ap.add_argument("--p2-engine")
    ap.add_argument("--players")
    ap.add_argument("--out-dir")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    elif a.score:
        required = (a.repo, a.prereg, a.phase1, a.holdout, a.p2_dir, a.season_2024, a.season_2025, a.p2_engine, a.players, a.out_dir)
        if not all(required):
            raise SystemExit("--score requires all path arguments")
        score(a)
    elif a.check:
        if not a.out_dir:
            raise SystemExit("--check requires --out-dir")
        check(a)
    else:
        raise SystemExit("choose --selftest, --score, or --check")


if __name__ == "__main__":
    main()
