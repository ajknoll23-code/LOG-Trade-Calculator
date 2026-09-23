#!/usr/bin/env python3
"""Draft Pick FV V5 Phase 2.1: pre-outcome source-retention amendment.

This is a deterministic, offline rebuild from the immutable Phase-2 STOP
artifacts. It does NOT fetch historical NFL outcomes, does NOT search for
additional leagues, and does NOT alter the original Phase-2 files.

Scientific purpose:
- preserve the frozen 378-league source cohort;
- restore the inherited V3 occurrence-level exclusion rule for unusable
  pick occurrences and later duplicate-player occurrences;
- gate source retention at >=95% overall AND in every year x R1/R2 cell;
- use pick-occurrence identity coverage as the frozen >=95% gate;
- retain unique-source identity coverage as a diagnostic only;
- freeze explicit missing-occurrence weights before any outcomes are read.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path.cwd()
D = ROOT / "research" / "draft-pick-fv-v5"
V3 = ROOT / "research" / "draft-pick-fv-v3"

PREREG = D / "r1_r2_bridge_preregistration_v5.json"
LINEAGE = D / "r1_r2_source_lineage_v5.json"
PREREG_MAN = D / "r1_r2_bridge_preregistration_manifest_v5.json"

P2_CATALOG = D / "r1_r2_source_catalog_v5.json"
P2_PICKS = D / "r1_r2_pick_identity_v5.jsonl"
P2_SUMMARY = D / "r1_r2_source_identity_summary_v5.json"
P2_MANIFEST = D / "r1_r2_source_identity_manifest_v5.json"

V3_PREREG = V3 / "preregistration_v3.json"
V3_REPAIR_SUMMARY = (
    V3 / "historical_draft_pick_contract_repair_summary_v3.json"
)
V3_REPAIR_MANIFEST = (
    V3 / "historical_draft_pick_contract_repair_manifest_v3.json"
)

OUT_SCRIPT = D / "build_r1_r2_source_identity_v5_1.py"
OUT_AMEND = D / "r1_r2_bridge_preoutcome_amendment_v5_1.json"
OUT_AMEND_MD = D / "r1_r2_bridge_preoutcome_amendment_v5_1.md"
OUT_AMEND_MAN = (
    D / "r1_r2_bridge_preoutcome_amendment_manifest_v5_1.json"
)
OUT_PICKS = D / "r1_r2_pick_identity_v5_1.jsonl"
OUT_CATALOG = D / "r1_r2_source_catalog_v5_1.json"
OUT_SUMMARY = D / "r1_r2_source_identity_summary_v5_1.json"
OUT_MD = D / "r1_r2_source_identity_summary_v5_1.md"
OUT_MANIFEST = D / "r1_r2_source_identity_manifest_v5_1.json"

STUDY_ID = "draft-pick-fv-v5-r1-r2-player-equivalent-calibration"
YEARS = (2018, 2019, 2020, 2021, 2022, 2023)
DEV_YEARS = {2018, 2019, 2020, 2021}
EXPECTED_BY_YEAR = {
    2018: 31,
    2019: 50,
    2020: 59,
    2021: 64,
    2022: 90,
    2023: 84,
}
EXPECTED_LEAGUES = 378
EXPECTED_RAW_OCCURRENCES = EXPECTED_LEAGUES * 24
MIN_COVERAGE = 0.95
CELLS = (
    "r1_early",
    "r1_mid",
    "r1_late",
    "r2_early",
    "r2_mid",
    "r2_late",
)

class GateError(RuntimeError):
    pass

def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canonical_sha(obj: Any) -> str:
    raw = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def cell_for_slot(slot: int) -> str:
    if not 1 <= slot <= 24:
        raise GateError(f"invalid R1/R2 slot: {slot}")
    rnd = 1 if slot <= 12 else 2
    within = slot if slot <= 12 else slot - 12
    tier = (
        "early"
        if within <= 4
        else ("mid" if within <= 8 else "late")
    )
    return f"r{rnd}_{tier}"

def occurrence_key(
    year: int | str,
    league_id: int | str,
    slot: int | str,
) -> tuple[int, str, int]:
    return (int(year), str(league_id), int(slot))

def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GateError(
                    f"{path.name}:{line_no}: invalid JSONL: {exc}"
                ) from exc
            if not isinstance(row, dict):
                raise GateError(
                    f"{path.name}:{line_no}: row is not object"
                )
            out.append(row)
    return out

def coverage(n: int, d: int) -> float:
    return n / d if d else 0.0

def main() -> None:
    pre = load(PREREG)
    lineage = load(LINEAGE)
    pre_man = load(PREREG_MAN)
    p2_cat = load(P2_CATALOG)
    p2_sum = load(P2_SUMMARY)
    p2_man = load(P2_MANIFEST)
    v3_pre = load(V3_PREREG)
    v3_sum = load(V3_REPAIR_SUMMARY)
    v3_man = load(V3_REPAIR_MANIFEST)

    # ---------- immutable pre-outcome guards ----------
    if pre["status"] != "FROZEN_PRE_OUTCOME":
        raise GateError("V5 preregistration is not frozen pre-outcome")
    if pre["historical_player_outcomes_read_before_freeze"] is not False:
        raise GateError("V5 prereg reports outcomes already read")
    if pre["candidate_fit_performed_before_freeze"] is not False:
        raise GateError("V5 prereg reports candidate fit already performed")
    if pre["validation_scored_before_freeze"] is not False:
        raise GateError("V5 prereg reports validation already scored")

    if p2_man["decision"] != (
        "STOP_V5_R1_R2_SOURCE_OR_IDENTITY_GATE_NO_OUTCOME_INGESTION"
    ):
        raise GateError("Phase-2 STOP decision drift")
    for key in (
        "historical_player_outcomes_read",
        "candidate_fit_performed",
        "validation_scored",
        "production_change_authorized",
        "outcome_ingestion_authorized_next_stage",
    ):
        if p2_man[key] is not False:
            raise GateError(f"Phase-2 firewall drift: {key}")

    if p2_cat["league_n"] != EXPECTED_LEAGUES:
        raise GateError("Phase-2 frozen league count drift")
    if p2_cat["expected_league_n"] != EXPECTED_LEAGUES:
        raise GateError("Phase-2 expected league count drift")
    if p2_cat["expected_pick_occurrence_n"] != EXPECTED_RAW_OCCURRENCES:
        raise GateError("Phase-2 expected occurrence count drift")
    if p2_cat["ambiguous_draft_unit_league_n"] != 0:
        raise GateError("Phase-2 contains ambiguous draft unit")
    got_by_year = {
        int(k): int(v)
        for k, v in p2_cat["league_n_by_year"].items()
    }
    if got_by_year != EXPECTED_BY_YEAR:
        raise GateError(f"Phase-2 by-year league drift: {got_by_year}")

    dup_rule = (
        v3_pre["draft_harvest_contract"]["pick_rules"]
        ["duplicate_player_within_same_league"]
    )
    if dup_rule != "exclude duplicate occurrence and flag source anomaly":
        raise GateError("inherited V3 duplicate-occurrence rule drift")
    if (
        v3_pre["draft_harvest_contract"]["pick_rules"]
        ["nonempty_player_required"] is not True
    ):
        raise GateError("inherited V3 nonempty-player rule drift")
    interp = v3_sum["pick_occurrence_retention_diagnostic"][
        "contract_interpretation"
    ]
    if interp["frozen_catalog_is_requalified_after_pick_exclusions"]:
        raise GateError("V3 frozen-catalog interpretation drift")
    if v3_man["historical_player_outcomes_read"] is not False:
        raise GateError("V3 lineage unexpectedly read outcomes")

    # ---------- freeze additive pre-outcome amendment ----------
    generated = now()
    amendment = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "stage": "phase2_1_preoutcome_feasibility_amendment",
        "status": "FROZEN_PRE_OUTCOME_AMENDMENT",
        "generated_at_utc": generated,
        "research_only": True,
        "historical_player_outcomes_read": False,
        "market_or_ktc_values_read": False,
        "package_vote_data_read": False,
        "candidate_fit_performed": False,
        "candidate_scores_computed": False,
        "validation_scored": False,
        "production_change_authorized": False,
        "automatic_production_promotion_allowed": False,
        "amendment_triggered_by_target_outcomes": False,
        "reason": (
            "The original Phase-2 implementation converted occurrence-level "
            "source anomalies into whole-league failures and additionally "
            "required >=95% unique-source identity coverage. Both rules were "
            "stricter than the inherited pre-outcome occurrence-level source "
            "contract and the V5 preregistered identity-coverage wording. "
            "No historical NFL outcomes, candidate fits, or validation scores "
            "have been read. This amendment is therefore limited to source "
            "feasibility, identity-denominator clarification, and missing-"
            "occurrence weighting before outcome harvest."
        ),
        "frozen_source_population": {
            "league_n": EXPECTED_LEAGUES,
            "by_year": {
                str(k): v for k, v in EXPECTED_BY_YEAR.items()
            },
            "changed": False,
            "source_search_reopened": False,
            "manual_source_inclusions_allowed": False,
            "manual_source_exclusions_allowed": False,
        },
        "occurrence_exclusion_rule": {
            "basis": "inherited V3 frozen pre-outcome contract",
            "unusable_or_absent_canonical_occurrence": (
                "exclude occurrence and flag it; do not requalify "
                "or remove the frozen league"
            ),
            "later_duplicate_player_occurrence": (
                "exclude later occurrence and flag source anomaly; "
                "do not requalify or remove the frozen league"
            ),
        },
        "source_retention_gate": {
            "minimum": MIN_COVERAGE,
            "overall_r1_r2_occurrence_retention": "must be >=95%",
            "every_draft_year_x_production_cell_occurrence_retention": (
                "must be >=95%"
            ),
            "every_draft_year_x_production_cell_represented_league_fraction": (
                "must be >=95%"
            ),
            "rationale": (
                "95% reuses the already-frozen identity coverage floor and is "
                "applied before outcomes. It prevents a sparse cell/year from "
                "being silently carried into calibration."
            ),
        },
        "identity_gate_clarification": {
            "minimum": MIN_COVERAGE,
            "gate_denominator": (
                "retained valid pick occurrences in the frozen source cohort"
            ),
            "stable_identity_occurrence_coverage": "must be >=95%",
            "sleeper_ready_occurrence_coverage": "must be >=95%",
            "unique_source_identity_coverage": (
                "diagnostic only; not a gate because repeated market "
                "selections are the sampling units for source/identity "
                "availability, while repeated player outcomes will still be "
                "clustered by stable player identity during inference"
            ),
        },
        "missing_occurrence_weighting": {
            "cell_rule": (
                "Within each draft year x production cell, each represented "
                "frozen league receives equal total weight; that league's "
                "retained valid picks in the cell divide its league-cell "
                "weight equally. Each year therefore contributes exactly 1/6 "
                "total weight to each production cell."
            ),
            "overall_r1_r2_rule": (
                "Within each draft year, each represented frozen league "
                "receives equal total R1/R2 weight; retained valid R1/R2 "
                "occurrences divide that league-year weight equally. Each "
                "year contributes exactly 1/6 total weight."
            ),
            "zero_valid_cell_policy": (
                "A frozen league with zero retained occurrences in a cell "
                "cannot receive outcome weight in that cell; its absence is "
                "captured by the represented-league coverage gate."
            ),
        },
        "unchanged_contract": {
            "outcome_provider": pre["historical_outcome_contract"]["provider"],
            "outcome_endpoint_template": (
                pre["historical_outcome_contract"]["endpoint_template"]
            ),
            "outcome_definition_O1": pre["primary_outcomes"]["O1_shape"],
            "outcome_definition_O2": pre["primary_outcomes"]["O2_scale"],
            "candidate_families": pre["candidate_families"],
            "development_validation_split": pre[
                "development_and_validation"
            ],
            "selection": pre["selection"],
            "rounds_fit": pre["analysis_scope"]["rounds_fit"],
            "rounds_3_to_6": pre["analysis_scope"]["rounds_3_to_6"],
            "year_discount_policy": pre["frozen_deployed_baseline"][
                "v5_year_discount_policy"
            ],
        },
        "upstream_stop_observation": {
            "phase2_decision": p2_man["decision"],
            "raw_canonical_occurrence_n": p2_cat[
                "observed_pick_occurrence_n"
            ],
            "expected_occurrence_n": EXPECTED_RAW_OCCURRENCES,
            "phase2_incomplete_league_flag_n": p2_cat[
                "incomplete_league_n"
            ],
            "phase2_identity_occurrence_coverage": p2_sum[
                "identity_gate"
            ]["pick_occurrence_coverage"],
            "phase2_unique_source_identity_coverage": p2_sum[
                "identity_gate"
            ]["unique_source_identity_coverage"],
            "phase2_sleeper_occurrence_coverage": p2_sum[
                "sleeper_outcome_identity_gate"
            ]["pick_occurrence_coverage"],
        },
        "frozen_input_hashes": {
            PREREG.name: sha(PREREG),
            LINEAGE.name: sha(LINEAGE),
            PREREG_MAN.name: sha(PREREG_MAN),
            P2_CATALOG.name: sha(P2_CATALOG),
            P2_PICKS.name: sha(P2_PICKS),
            P2_SUMMARY.name: sha(P2_SUMMARY),
            P2_MANIFEST.name: sha(P2_MANIFEST),
            V3_PREREG.name: sha(V3_PREREG),
            V3_REPAIR_SUMMARY.name: sha(V3_REPAIR_SUMMARY),
            V3_REPAIR_MANIFEST.name: sha(V3_REPAIR_MANIFEST),
        },
    }
    OUT_AMEND.write_text(
        json.dumps(amendment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # ---------- derive occurrence exclusions from frozen Phase 2 ----------
    league_rows = p2_cat["leagues"]
    if len(league_rows) != EXPECTED_LEAGUES:
        raise GateError("unexpected Phase-2 league row count")

    league_meta: dict[tuple[int, str], dict[str, Any]] = {}
    missing_keys: set[tuple[int, str, int]] = set()
    duplicate_keys: set[tuple[int, str, int]] = set()
    excluded_details: list[dict[str, Any]] = []

    for lg in league_rows:
        y = int(lg["draft_year"])
        lid = str(lg["league_id"])
        lk = (y, lid)
        if lk in league_meta:
            raise GateError(f"duplicate frozen league key: {lk}")
        league_meta[lk] = lg

        for slot in lg.get("missing_slots_1_24", []):
            k = occurrence_key(y, lid, slot)
            missing_keys.add(k)
            excluded_details.append({
                "draft_year": y,
                "league_id": lid,
                "overall_slot": int(slot),
                "cell": cell_for_slot(int(slot)),
                "exclusion_reason": "absent_or_unusable_canonical_occurrence",
                "mfl_player_id": None,
            })

        for dup in lg.get("duplicate_players_1_24", []):
            slot = int(
                dup.get("duplicate_slot")
                if dup.get("duplicate_slot") is not None
                else dup.get("removed_slot")
            )
            k = occurrence_key(y, lid, slot)
            duplicate_keys.add(k)
            excluded_details.append({
                "draft_year": y,
                "league_id": lid,
                "overall_slot": slot,
                "cell": cell_for_slot(slot),
                "exclusion_reason": "later_duplicate_player_occurrence",
                "mfl_player_id": dup.get("mfl_player_id"),
                "first_slot": dup.get("first_slot"),
            })

    if missing_keys & duplicate_keys:
        raise GateError("same occurrence classified missing and duplicate")

    expected_keys = {
        occurrence_key(y, lid, slot)
        for (y, lid) in league_meta
        for slot in range(1, 25)
    }
    if len(expected_keys) != EXPECTED_RAW_OCCURRENCES:
        raise GateError("frozen 378x24 key universe drift")

    p2_rows = read_jsonl(P2_PICKS)
    observed_by_key: dict[
        tuple[int, str, int], dict[str, Any]
    ] = {}
    for row in p2_rows:
        k = occurrence_key(
            row["draft_year"],
            row["league_id"],
            row["overall_slot"],
        )
        if k in observed_by_key:
            raise GateError(f"duplicate Phase-2 JSONL key: {k}")
        if k not in expected_keys:
            raise GateError(f"out-of-universe Phase-2 JSONL key: {k}")
        observed_by_key[k] = row

    observed_keys = set(observed_by_key)
    if expected_keys - observed_keys != missing_keys:
        extra_missing = sorted(
            (expected_keys - observed_keys) - missing_keys
        )[:20]
        stale_declared = sorted(
            missing_keys - (expected_keys - observed_keys)
        )[:20]
        raise GateError(
            "Phase-2 JSONL/catalog missing-key mismatch; "
            f"extra_missing={extra_missing}; stale_declared={stale_declared}"
        )
    if not duplicate_keys <= observed_keys:
        raise GateError("duplicate-player exclusion references absent row")

    retained_keys = observed_keys - duplicate_keys
    excluded_keys = missing_keys | duplicate_keys
    if retained_keys & excluded_keys:
        raise GateError("retained/excluded occurrence overlap")
    if retained_keys | excluded_keys != expected_keys:
        raise GateError("retained + excluded does not reconstruct 378x24")
    if len(missing_keys) != 48:
        raise GateError(
            f"unexpected frozen missing occurrence count: {len(missing_keys)}"
        )
    if len(duplicate_keys) != 16:
        raise GateError(
            f"unexpected frozen duplicate exclusion count: {len(duplicate_keys)}"
        )
    if len(retained_keys) != 9008:
        raise GateError(
            f"unexpected retained occurrence count: {len(retained_keys)}"
        )

    # ---------- source-retention diagnostics ----------
    expected_cell_year = {
        (y, cell): EXPECTED_BY_YEAR[y] * 4
        for y in YEARS
        for cell in CELLS
    }
    valid_count_cell_year = Counter()
    represented_cell_year: dict[
        tuple[int, str], set[str]
    ] = defaultdict(set)
    valid_count_league_cell = Counter()
    valid_count_league_year = Counter()
    represented_year: dict[int, set[str]] = defaultdict(set)

    retained_rows: list[dict[str, Any]] = []
    for k in sorted(
        retained_keys,
        key=lambda x: (x[0], int(x[1]), x[2]),
    ):
        row = dict(observed_by_key[k])
        y, lid, slot = k
        expected_cell = cell_for_slot(slot)
        if row.get("cell") != expected_cell:
            raise GateError(
                f"cell drift at {k}: {row.get('cell')} != {expected_cell}"
            )
        lg = league_meta[(y, lid)]
        row["league_idp"] = bool(lg.get("idp", False))
        row["source_occurrence_valid_v5_1"] = True
        row["source_occurrence_policy_v5_1"] = (
            "retained_after_preoutcome_occurrence_level_exclusion"
        )
        retained_rows.append(row)

        valid_count_cell_year[(y, expected_cell)] += 1
        represented_cell_year[(y, expected_cell)].add(lid)
        valid_count_league_cell[(y, lid, expected_cell)] += 1
        valid_count_league_year[(y, lid)] += 1
        represented_year[y].add(lid)

    cell_year_rows: dict[str, dict[str, Any]] = {}
    source_gate = True
    for y in YEARS:
        for cell in CELLS:
            key = (y, cell)
            exp_n = expected_cell_year[key]
            valid_n = valid_count_cell_year[key]
            retention = coverage(valid_n, exp_n)
            repr_n = len(represented_cell_year[key])
            repr_frac = coverage(repr_n, EXPECTED_BY_YEAR[y])
            gate = (
                retention >= MIN_COVERAGE
                and repr_frac >= MIN_COVERAGE
            )
            source_gate = source_gate and gate
            cell_year_rows[f"{y}:{cell}"] = {
                "draft_year": y,
                "cell": cell,
                "expected_occurrence_n": exp_n,
                "retained_occurrence_n": valid_n,
                "excluded_occurrence_n": exp_n - valid_n,
                "retention_fraction": retention,
                "expected_frozen_league_n": EXPECTED_BY_YEAR[y],
                "represented_frozen_league_n": repr_n,
                "represented_league_fraction": repr_frac,
                "pass": gate,
            }

    overall_retention = coverage(
        len(retained_rows), EXPECTED_RAW_OCCURRENCES
    )
    source_gate = source_gate and overall_retention >= MIN_COVERAGE
    source_gate = (
        source_gate
        and len(league_meta) == EXPECTED_LEAGUES
        and p2_cat["ambiguous_draft_unit_league_n"] == 0
    )

    # ---------- freeze missing-occurrence weights ----------
    for row in retained_rows:
        y = int(row["draft_year"])
        lid = str(row["league_id"])
        cell = str(row["cell"])

        n_repr_cell = len(represented_cell_year[(y, cell)])
        n_lg_cell = valid_count_league_cell[(y, lid, cell)]
        n_repr_year = len(represented_year[y])
        n_lg_year = valid_count_league_year[(y, lid)]

        if min(
            n_repr_cell,
            n_lg_cell,
            n_repr_year,
            n_lg_year,
        ) <= 0:
            raise GateError("invalid V5.1 weight denominator")

        row["cell_weight_v5_1"] = (
            (1.0 / len(YEARS))
            / n_repr_cell
            / n_lg_cell
        )
        row["source_weight_r1_r2_v5_1"] = (
            (1.0 / len(YEARS))
            / n_repr_year
            / n_lg_year
        )

    # Prove exact normalization of the amendment weights.
    cell_weight_sums = defaultdict(float)
    year_weight_sums = defaultdict(float)
    for row in retained_rows:
        y = int(row["draft_year"])
        cell = str(row["cell"])
        cell_weight_sums[(y, cell)] += float(
            row["cell_weight_v5_1"]
        )
        year_weight_sums[y] += float(
            row["source_weight_r1_r2_v5_1"]
        )

    target = 1.0 / len(YEARS)
    for key, total in cell_weight_sums.items():
        if not math.isclose(
            total, target, rel_tol=0.0, abs_tol=1e-12
        ):
            raise GateError(
                f"cell weight normalization failed {key}: {total}"
            )
    for y, total in year_weight_sums.items():
        if not math.isclose(
            total, target, rel_tol=0.0, abs_tol=1e-12
        ):
            raise GateError(
                f"year weight normalization failed {y}: {total}"
            )

    # ---------- identity / Sleeper occurrence gates ----------
    identity_resolved_n = sum(
        bool(r.get("identity_resolved")) for r in retained_rows
    )
    sleeper_ready_n = sum(
        bool(r.get("outcome_ready_sleeper_id"))
        for r in retained_rows
    )
    identity_cov = coverage(identity_resolved_n, len(retained_rows))
    sleeper_cov = coverage(sleeper_ready_n, len(retained_rows))

    unique_source: dict[str, dict[str, bool]] = {}
    for r in retained_rows:
        key = str(r.get("source_identity_key") or "")
        if not key:
            continue
        rec = unique_source.setdefault(
            key, {"resolved": False, "sleeper": False}
        )
        rec["resolved"] = (
            rec["resolved"] or bool(r.get("identity_resolved"))
        )
        rec["sleeper"] = (
            rec["sleeper"]
            or bool(r.get("outcome_ready_sleeper_id"))
        )
    unique_n = len(unique_source)
    unique_resolved_n = sum(
        int(x["resolved"]) for x in unique_source.values()
    )
    unique_sleeper_n = sum(
        int(x["sleeper"]) for x in unique_source.values()
    )

    identity_gate = identity_cov >= MIN_COVERAGE
    sleeper_gate = sleeper_cov >= MIN_COVERAGE

    identity_by_cell = {}
    for cell in CELLS:
        rows = [r for r in retained_rows if r["cell"] == cell]
        identity_by_cell[cell] = {
            "retained_occurrence_n": len(rows),
            "identity_resolved_n": sum(
                bool(r.get("identity_resolved")) for r in rows
            ),
            "identity_coverage": coverage(
                sum(bool(r.get("identity_resolved")) for r in rows),
                len(rows),
            ),
            "sleeper_ready_n": sum(
                bool(r.get("outcome_ready_sleeper_id"))
                for r in rows
            ),
            "sleeper_ready_coverage": coverage(
                sum(
                    bool(r.get("outcome_ready_sleeper_id"))
                    for r in rows
                ),
                len(rows),
            ),
        }

    split_diag = {}
    for split in ("development", "locked_validation"):
        rows = [
            r for r in retained_rows
            if r.get("split") == split
        ]
        split_diag[split] = {
            "retained_occurrence_n": len(rows),
            "identity_coverage": coverage(
                sum(
                    bool(r.get("identity_resolved"))
                    for r in rows
                ),
                len(rows),
            ),
            "sleeper_ready_coverage": coverage(
                sum(
                    bool(r.get("outcome_ready_sleeper_id"))
                    for r in rows
                ),
                len(rows),
            ),
        }

    # Required non-IDP source sensitivity support is reported now;
    # outcome sensitivity remains for the later outcome stage.
    nonidp_rows = [
        r for r in retained_rows if not r["league_idp"]
    ]
    nonidp_support = {
        cell: {
            str(y): sum(
                1
                for r in nonidp_rows
                if int(r["draft_year"]) == y
                and r["cell"] == cell
            )
            for y in YEARS
        }
        for cell in CELLS
    }

    outcome_authorized = (
        source_gate and identity_gate and sleeper_gate
    )
    decision = (
        "PASS_V5_1_R1_R2_SOURCE_IDENTITY_FREEZE_"
        "OUTCOME_HARVEST_AUTHORIZED_NEXT_STAGE"
        if outcome_authorized
        else
        "STOP_V5_1_R1_R2_SOURCE_OR_IDENTITY_GATE_"
        "NO_OUTCOME_INGESTION"
    )

    # ---------- write deterministic amended corpus ----------
    with OUT_PICKS.open("w", encoding="utf-8") as f:
        for row in retained_rows:
            f.write(
                json.dumps(
                    row,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )

    frozen_leagues = []
    for lg in league_rows:
        y = int(lg["draft_year"])
        lid = str(lg["league_id"])
        missing = [
            k[2]
            for k in missing_keys
            if k[0] == y and k[1] == lid
        ]
        dup_excluded = [
            k[2]
            for k in duplicate_keys
            if k[0] == y and k[1] == lid
        ]
        frozen_leagues.append({
            "draft_year": y,
            "league_id": lid,
            "league_name": lg.get("league_name"),
            "idp": bool(lg.get("idp", False)),
            "source_origin": lg.get("source_origin"),
            "frozen_league_retained_v5_1": True,
            "missing_occurrence_slots_v5_1": sorted(missing),
            "duplicate_player_excluded_slots_v5_1": sorted(
                dup_excluded
            ),
            "retained_occurrence_n_v5_1": sum(
                1
                for r in retained_rows
                if int(r["draft_year"]) == y
                and str(r["league_id"]) == lid
            ),
        })
    frozen_leagues.sort(
        key=lambda x: (
            int(x["draft_year"]),
            int(x["league_id"]),
        )
    )

    catalog = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "stage": "phase2_1_source_identity_freeze",
        "status": (
            "FROZEN_SOURCE_IDENTITY_PASS"
            if outcome_authorized
            else "FROZEN_SOURCE_IDENTITY_STOP"
        ),
        "generated_at_utc": generated,
        "research_only": True,
        "historical_player_outcomes_read": False,
        "market_or_ktc_values_read": False,
        "package_vote_data_read": False,
        "candidate_fit_performed": False,
        "validation_scored": False,
        "production_change_authorized": False,
        "source_search_performed": False,
        "frozen_source_population_changed": False,
        "expected_league_n": EXPECTED_LEAGUES,
        "league_n": len(frozen_leagues),
        "expected_by_year": {
            str(k): v for k, v in EXPECTED_BY_YEAR.items()
        },
        "league_n_by_year": {
            str(y): sum(
                1
                for lg in frozen_leagues
                if int(lg["draft_year"]) == y
            )
            for y in YEARS
        },
        "expected_raw_pick_occurrence_n": EXPECTED_RAW_OCCURRENCES,
        "phase2_raw_canonical_occurrence_n": len(p2_rows),
        "retained_valid_occurrence_n": len(retained_rows),
        "excluded_occurrence_n": len(excluded_keys),
        "missing_or_unusable_occurrence_n": len(missing_keys),
        "later_duplicate_player_exclusion_n": len(duplicate_keys),
        "overall_retention_fraction": overall_retention,
        "source_retention_gate_pass": source_gate,
        "cell_year_retention": cell_year_rows,
        "excluded_occurrences": sorted(
            excluded_details,
            key=lambda x: (
                int(x["draft_year"]),
                int(x["league_id"]),
                int(x["overall_slot"]),
                x["exclusion_reason"],
            ),
        ),
        "leagues": frozen_leagues,
    }
    OUT_CATALOG.write_text(
        json.dumps(catalog, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "stage": "phase2_1_source_identity_freeze",
        "status": catalog["status"],
        "generated_at_utc": generated,
        "decision": decision,
        "research_only": True,
        "pre_outcome_stage": True,
        "historical_player_outcomes_read": False,
        "market_or_ktc_values_read": False,
        "package_vote_data_read": False,
        "candidate_fit_performed": False,
        "candidate_scores_computed": False,
        "validation_scored": False,
        "production_change_authorized": False,
        "automatic_production_promotion_allowed": False,
        "source_search_performed": False,
        "original_phase2_stop_preserved": True,
        "amendment_file": OUT_AMEND.name,
        "amendment_sha256": sha(OUT_AMEND),
        "source_retention_gate": {
            "pass": source_gate,
            "minimum_required": MIN_COVERAGE,
            "expected_raw_occurrence_n": EXPECTED_RAW_OCCURRENCES,
            "retained_valid_occurrence_n": len(retained_rows),
            "excluded_occurrence_n": len(excluded_keys),
            "missing_or_unusable_occurrence_n": len(missing_keys),
            "later_duplicate_player_exclusion_n": len(
                duplicate_keys
            ),
            "overall_retention_fraction": overall_retention,
            "cell_year": cell_year_rows,
        },
        "identity_gate": {
            "pass": identity_gate,
            "minimum_required": MIN_COVERAGE,
            "gate_denominator": "retained valid pick occurrences",
            "retained_occurrence_n": len(retained_rows),
            "identity_resolved_occurrence_n": identity_resolved_n,
            "pick_occurrence_coverage": identity_cov,
            "unique_source_identity_n": unique_n,
            "resolved_unique_source_identity_n": unique_resolved_n,
            "unique_source_identity_coverage_diagnostic": coverage(
                unique_resolved_n, unique_n
            ),
            "unique_source_identity_is_gate": False,
            "by_cell_diagnostic": identity_by_cell,
            "by_split_diagnostic": split_diag,
        },
        "sleeper_outcome_identity_gate": {
            "pass": sleeper_gate,
            "minimum_required": MIN_COVERAGE,
            "gate_denominator": "retained valid pick occurrences",
            "retained_occurrence_n": len(retained_rows),
            "sleeper_ready_occurrence_n": sleeper_ready_n,
            "pick_occurrence_coverage": sleeper_cov,
            "sleeper_ready_unique_source_identity_n": (
                unique_sleeper_n
            ),
            "unique_source_identity_n": unique_n,
            "unique_source_identity_coverage_diagnostic": coverage(
                unique_sleeper_n, unique_n
            ),
            "unique_source_identity_is_gate": False,
        },
        "weighting_contract_v5_1": {
            "cell_weight_field": "cell_weight_v5_1",
            "overall_r1_r2_weight_field": (
                "source_weight_r1_r2_v5_1"
            ),
            "cell_rule": amendment[
                "missing_occurrence_weighting"
            ]["cell_rule"],
            "overall_rule": amendment[
                "missing_occurrence_weighting"
            ]["overall_r1_r2_rule"],
            "cell_year_weight_target": target,
            "draft_year_weight_target": target,
            "normalization_proved": True,
        },
        "nonidp_source_support_diagnostic": nonidp_support,
        "development_validation_split": {
            "development_years": sorted(DEV_YEARS),
            "locked_validation_years": [2022, 2023],
            "split_changed": False,
        },
        "outcome_ingestion_authorized_next_stage": (
            outcome_authorized
        ),
        "next_stage": (
            "draft-pick-fv-v5-phase3-historical-outcome-harvest-v5-1"
            if outcome_authorized
            else None
        ),
        "frozen_input_hashes": amendment["frozen_input_hashes"],
    }
    OUT_SUMMARY.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    md = [
        "# Draft Pick FV V5.1 — Pre-Outcome Source Retention Amendment",
        "",
        f"**Decision:** `{decision}`",
        "",
        "The original V5 Phase-2 STOP remains immutable. This additive "
        "pre-outcome amendment restores the inherited occurrence-level "
        "source rule without changing the frozen 378-league population.",
        "",
        "## Source retention",
        "",
        f"- Frozen leagues retained: **{len(frozen_leagues)} / 378**",
        f"- Raw expected R1/R2 occurrences: **{EXPECTED_RAW_OCCURRENCES}**",
        f"- Retained valid occurrences: **{len(retained_rows)}**",
        f"- Excluded occurrences: **{len(excluded_keys)}**",
        f"  - absent/unusable canonical slots: **{len(missing_keys)}**",
        f"  - later duplicate-player occurrences: **{len(duplicate_keys)}**",
        f"- Overall retention: **{overall_retention:.2%}**",
        f"- Worst year × cell retention: **{min(x['retention_fraction'] for x in cell_year_rows.values()):.2%}**",
        f"- Worst year × cell represented-league fraction: **{min(x['represented_league_fraction'] for x in cell_year_rows.values()):.2%}**",
        f"- Required: **{MIN_COVERAGE:.0%}**",
        f"- Source-retention gate: **{'PASS' if source_gate else 'FAIL'}**",
        "",
        "## Identity",
        "",
        f"- Retained occurrence identity coverage: **{identity_cov:.2%}**",
        f"- Retained occurrence Sleeper-ready coverage: **{sleeper_cov:.2%}**",
        f"- Unique-source identity coverage: **{coverage(unique_resolved_n, unique_n):.2%}** (diagnostic only)",
        f"- Identity gate: **{'PASS' if identity_gate else 'FAIL'}**",
        f"- Sleeper gate: **{'PASS' if sleeper_gate else 'FAIL'}**",
        "",
        "## Firewall",
        "",
        "- Historical NFL outcomes read: **No**",
        "- KTC/market values read: **No**",
        "- Package-vote evidence read: **No**",
        "- Candidate fitting performed: **No**",
        "- Locked validation scored: **No**",
        "- Source search expanded: **No**",
        "- Frozen source population changed: **No**",
        "- Production change authorized: **No**",
        "",
        "## Next step",
        "",
        (
            "Phase 3 historical outcome harvest is authorized against the "
            "V5.1 retained occurrence corpus. Candidate fitting remains "
            "forbidden during Phase 3."
            if outcome_authorized
            else
            "Stop before historical outcomes. Diagnose the remaining "
            "pre-outcome source/identity gate failure."
        ),
        "",
    ]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    amend_md = [
        "# Draft Pick FV V5.1 — Pre-Outcome Feasibility Amendment",
        "",
        "This amendment is frozen before any historical NFL outcome is "
        "read and preserves the original Phase-2 STOP artifacts.",
        "",
        "It makes three narrow corrections:",
        "",
        "1. Preserve all 378 frozen leagues and exclude unusable pick "
        "occurrences rather than requalifying whole leagues.",
        "2. Apply the frozen 95% identity threshold to retained pick "
        "occurrences; unique-source coverage remains diagnostic.",
        "3. Freeze league-balanced missing-occurrence weights inside "
        "each draft-year × R1/R2 production cell before outcome harvest.",
        "",
        "No outcome definition, candidate family, validation split, "
        "selection gate, R3-R6 value, YEAR_DISCOUNT, production player "
        "formula, Package Adjustment, Market Value, or Team Utility rule "
        "is changed.",
        "",
    ]
    OUT_AMEND_MD.write_text(
        "\n".join(amend_md), encoding="utf-8"
    )

    amend_manifest = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "stage": "phase2_1_preoutcome_feasibility_amendment",
        "status": "FROZEN_PRE_OUTCOME_AMENDMENT",
        "generated_at_utc": generated,
        "historical_player_outcomes_read": False,
        "candidate_fit_performed": False,
        "validation_scored": False,
        "production_change_authorized": False,
        "original_phase2_stop_preserved": True,
        "output_hashes": {
            OUT_AMEND.name: sha(OUT_AMEND),
            OUT_AMEND_MD.name: sha(OUT_AMEND_MD),
        },
        "canonical_amendment_sha256": canonical_sha(amendment),
    }
    OUT_AMEND_MAN.write_text(
        json.dumps(
            amend_manifest, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "stage": "phase2_1_source_identity_freeze",
        "status": summary["status"],
        "generated_at_utc": generated,
        "decision": decision,
        "research_only": True,
        "historical_player_outcomes_read": False,
        "candidate_fit_performed": False,
        "validation_scored": False,
        "production_change_authorized": False,
        "source_catalog_frozen": True,
        "identity_map_frozen": True,
        "original_phase2_stop_preserved": True,
        "preoutcome_amendment_frozen": True,
        "source_retention_gate_pass": source_gate,
        "identity_gate_pass": identity_gate,
        "sleeper_outcome_identity_gate_pass": sleeper_gate,
        "outcome_ingestion_authorized_next_stage": (
            outcome_authorized
        ),
        "input_hashes": amendment["frozen_input_hashes"],
        "amendment_hashes": {
            OUT_AMEND.name: sha(OUT_AMEND),
            OUT_AMEND_MD.name: sha(OUT_AMEND_MD),
            OUT_AMEND_MAN.name: sha(OUT_AMEND_MAN),
        },
        "output_hashes": {
            OUT_PICKS.name: sha(OUT_PICKS),
            OUT_CATALOG.name: sha(OUT_CATALOG),
            OUT_SUMMARY.name: sha(OUT_SUMMARY),
            OUT_MD.name: sha(OUT_MD),
        },
        "canonical_summary_sha256": canonical_sha(summary),
    }
    OUT_MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"DECISION={decision}")
    print(
        f"retained={len(retained_rows)}/{EXPECTED_RAW_OCCURRENCES} "
        f"({overall_retention:.2%}); "
        f"identity={identity_cov:.2%}; sleeper={sleeper_cov:.2%}"
    )
    print(
        "excluded: "
        f"missing/unusable={len(missing_keys)}, "
        f"later-duplicate={len(duplicate_keys)}"
    )

if __name__ == "__main__":
    main()
