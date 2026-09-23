#!/usr/bin/env python3
"""Freeze V6.1 clean-source amendment before any V6 outcomes are read."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path.cwd()
D = ROOT / "research" / "draft-pick-fv-v6"

PRE = D / "structural_continuity_preregistration_v6.json"
PRE_MAN = D / "structural_continuity_preregistration_manifest_v6.json"
V3_CONTAM = (
    ROOT / "research" / "draft-pick-fv-v3" /
    "rookie_scope_contamination_audit_v3.json"
)
V4 = (
    ROOT / "research" / "draft-pick-fv-v4" /
    "clean_source_recovery_v4.json"
)
V4_MAN = (
    ROOT / "research" / "draft-pick-fv-v4" /
    "clean_source_recovery_manifest_v4.json"
)
V5_LINEAGE = (
    ROOT / "research" / "draft-pick-fv-v5" /
    "r1_r2_source_lineage_v5.json"
)
V3_FEAS = (
    ROOT / "research" / "draft-pick-fv-v3" /
    "mfl_validated_proxy_feasibility_v1.json"
)

OUT_JSON = D / "structural_continuity_preoutcome_amendment_v6_1.json"
OUT_MD = D / "structural_continuity_preoutcome_amendment_v6_1.md"
OUT_MAN = (
    D /
    "structural_continuity_preoutcome_amendment_manifest_v6_1.json"
)

EXPECTED_BY_YEAR = {
    "2018": 31,
    "2019": 50,
    "2020": 59,
    "2021": 64,
    "2022": 90,
    "2023": 84,
}
SEARCH_TERMS = [
    "dynasty", "superflex", "super flex", "2qb", "2 qb",
    "rookie", "idp", "devy", "empire", "contract", "salary",
    "taxi", "fantasy", "football", "league",
]

class GateError(RuntimeError):
    pass

def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canonical_sha(obj: Any) -> str:
    raw = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def validate_inputs(
    pre: dict[str, Any],
    pm: dict[str, Any],
    contam: dict[str, Any],
    v4: dict[str, Any],
    v4m: dict[str, Any],
    lineage: dict[str, Any],
    feas: dict[str, Any],
) -> None:
    if pre["status"] != "FROZEN_PRE_V6_R3_R4_OUTCOME_ACCESS":
        raise GateError("V6 Phase 1 status drift")
    if pre["production_change_authorized"] is not False:
        raise GateError("Phase 1 unexpectedly authorizes production")
    if pre["source_population"]["frozen_v3_primary_r1_r4_league_n"] != 213:
        raise GateError("Phase 1 original source count drift")
    if pre["source_population"]["2024_holdout_source"]["minimum_eligible_leagues"] != 19:
        raise GateError("2024 minimum source threshold drift")

    for key in (
        "historical_r3_r4_outcomes_read",
        "holdout_2024_outcomes_read",
        "candidate_fit_performed",
        "candidate_selection_performed",
        "production_change_authorized",
    ):
        if pm[key] is not False:
            raise GateError(f"Phase 1 firewall drift: {key}")

    if contam["audit_counts"]["frozen_catalog_league_n"] != 213:
        raise GateError("V3 audited source count drift")
    if contam["audit_counts"]["clean_league_n"] != 172:
        raise GateError("V3 clean source count drift")
    if contam["audit_counts"]["positive_contaminated_league_n"] != 41:
        raise GateError("V3 contamination count drift")
    if contam["historical_player_outcomes_read"] is not False:
        raise GateError("V3 contamination audit read outcomes")

    if v4["clean_totals"]["primary_r1_r4"] != 378:
        raise GateError("V4 clean R1-R4 total drift")
    if v4["historical_player_outcomes_read"] is not False:
        raise GateError("V4 clean source evidence read outcomes")
    if v4m["historical_player_outcomes_read"] is not False:
        raise GateError("V4 manifest outcome firewall drift")

    if lineage["status"] != "frozen_pre_outcome_source_lineage":
        raise GateError("V5 clean source lineage status drift")
    if lineage["historical_player_outcomes_read"] is not False:
        raise GateError("V5 source lineage unexpectedly read outcomes")
    if lineage["clean_full_r4_total"] != 378:
        raise GateError("V5 clean source total drift")
    if lineage["v3_clean_seed_total"] != 172:
        raise GateError("V5 clean V3 seed count drift")
    if lineage["v4_new_clean_total"] != 206:
        raise GateError("V5 V4 expansion count drift")
    if lineage["clean_full_r4_counts_by_year"] != EXPECTED_BY_YEAR:
        raise GateError("V5 clean source year distribution drift")
    if lineage["exact_phase2_catalog_rule"]["no_additional_source_search"] is not True:
        raise GateError("historical source-search lock drift")
    if lineage["exact_phase2_catalog_rule"]["no_post_freeze_manual_inclusions"] is not True:
        raise GateError("historical manual-inclusion lock drift")

    dd = feas["discovery_design"]
    if dd["max_per_term"] != 50:
        raise GateError("V3 2024 search cap source drift")
    if dd["search_terms"] != SEARCH_TERMS:
        raise GateError("V3 2024 search terms drift")
    if dd["probe_entire_bounded_unique_union"] is not True:
        raise GateError("V3 discovery-union rule drift")
    if dd["search_failures_are_fatal"] is not True:
        raise GateError("V3 search failure policy drift")
    if feas["historical_player_outcomes_read"] is not False:
        raise GateError("V3 feasibility unexpectedly read outcomes")

def build(
    pre: dict[str, Any],
    pm: dict[str, Any],
    contam: dict[str, Any],
    v4: dict[str, Any],
    v4m: dict[str, Any],
    lineage: dict[str, Any],
    feas: dict[str, Any],
    *,
    generated_at: str,
) -> dict[str, Any]:
    validate_inputs(pre, pm, contam, v4, v4m, lineage, feas)

    return {
        "schema_version": 1,
        "study_id": "draft-pick-fv-v6-r1-r4-structural-continuity",
        "stage": "phase1_1_preoutcome_clean_source_amendment",
        "status": "FROZEN_PRE_OUTCOME_SOURCE_AMENDMENT",
        "decision": (
            "PASS_V6_1_CLEAN_SOURCE_AMENDMENT_FROZEN_"
            "PHASE2_AUTHORIZED"
        ),
        "generated_at_utc": generated_at,
        "research_only": True,
        "original_phase1_preserved": True,
        "amendment_triggered_by_v6_outcomes": False,
        "historical_r3_r4_outcomes_read": False,
        "holdout_2024_outcomes_read": False,
        "candidate_fit_performed": False,
        "candidate_selection_performed": False,
        "market_or_ktc_values_read": False,
        "package_vote_data_read": False,
        "production_change_authorized": False,
        "automatic_production_promotion_allowed": False,
        "reason": (
            "Phase 2 preflight identified that the Phase 1 source "
            "reference pointed to the original 213-league V3 "
            "primary R1-R4 catalog even though a later pre-outcome "
            "audit had already confirmed 41 positively contaminated "
            "league drafts. Before any V6 R3/R4 or 2024 outcomes "
            "were read, V6 therefore adopts the already-frozen V5 "
            "clean full-R4 source lineage: 172 clean V3 seeds plus "
            "206 clean V4 expansion leagues, 378 total."
        ),
        "evidence_timing": {
            "v3_contamination_audit_predates_v6": True,
            "v4_clean_source_recovery_predates_v6": True,
            "v5_clean_source_lineage_predates_v6": True,
            "v6_outcomes_used_to_trigger_amendment": False,
            "scientific_scope_change_after_outcomes": False,
        },
        "source_contract_replacement": {
            "superseded_phase1_development_source": {
                "league_n": 213,
                "description": (
                    "original V3 primary_r1_r4 catalog including "
                    "41 leagues later confirmed contaminated"
                ),
                "development_occurrence_source": (
                    "historical_draft_pick_contract_repair_v3.jsonl"
                ),
                "may_be_used_as_complete_v6_development_corpus": False,
            },
            "frozen_clean_development_source": {
                "provider": "MyFantasyLeague",
                "years": [2018, 2019, 2020, 2021, 2022, 2023],
                "format": "12-team Superflex/2QB dynasty rookie drafts",
                "required_depth": "complete through Round 4",
                "league_n": 378,
                "counts_by_year": dict(EXPECTED_BY_YEAR),
                "v3_clean_seed_n": 172,
                "v4_new_clean_n": 206,
                "lineage_file": "r1_r2_source_lineage_v5.json",
                "lineage_construction": (
                    "V3 league_audit rows with "
                    "positive_rookie_scope_contamination=false and "
                    "scope.primary_r1_r4=true, plus V4 "
                    "new_source_evidence rows with "
                    "positive_contamination=false and "
                    "primary_r1_r4=true; deduplicate by "
                    "draft_year + league_id."
                ),
                "new_2018_2023_source_search_allowed": False,
                "manual_source_inclusions_allowed": False,
                "manual_source_exclusions_allowed": False,
                "phase2_allowed_transport": [
                    (
                        "MFL draftResults for the exact frozen "
                        "378 league IDs to rebuild R1-R4 occurrences"
                    ),
                    (
                        "MFL players metadata only for identity and "
                        "contamination verification"
                    ),
                ],
                "phase2_must_rebuild_r1_r4_occurrences": True,
            },
        },
        "contamination_contract": {
            "basis": (
                "V4 frozen contamination contract, itself derived "
                "before historical player outcomes"
            ),
            "league_rule": v4["frozen_contamination_contract"][
                "league_rule"
            ],
            "identity_namespace_rule": v4[
                "frozen_contamination_contract"
            ]["identity_namespace_rule"],
            "positive_contamination_evidence": v4[
                "frozen_contamination_contract"
            ]["positive_contamination_evidence"],
            "diagnostic_unknown_policy": (
                "Report diagnostic unknowns; do not silently convert "
                "them into same-year identities and do not exclude a "
                "league unless positive contamination evidence exists."
            ),
            "post_result_manual_rescue_allowed": False,
        },
        "holdout_2024_source_contract": {
            "provider": "MyFantasyLeague",
            "source_search_allowed": True,
            "source_search_is_pre_outcome": True,
            "base_eligibility": (
                "12 teams; QB limit 1-2 or 2; Rookie-only draft "
                "pool; explicit dynasty or validated missing-keeper "
                "proxy; non-mock; complete Rounds 1-4"
            ),
            "contamination_rule": (
                "Apply the same V4 positive-contamination exclusion "
                "contract before freezing the 2024 holdout cohort."
            ),
            "minimum_clean_full4_leagues": 19,
            "freeze_rule": (
                "Freeze every clean eligible league in the complete "
                "bounded discovery union; never cherry-pick only the "
                "minimum 19."
            ),
            "discovery_design": {
                "search_terms": list(SEARCH_TERMS),
                "max_per_term": 50,
                "probe_entire_bounded_unique_union": True,
                "deterministic_ordering": True,
                "search_failures_are_fatal": True,
                "candidate_deduplication": "2024 + league_id",
            },
            "manual_inclusions_after_freeze_allowed": False,
            "manual_exclusions_after_freeze_allowed": False,
            "alternate_provider_after_results_allowed": False,
            "outcomes_remain_sealed": True,
        },
        "identity_contract": {
            "minimum_occurrence_identity_coverage": pre[
                "source_and_identity_contract"
            ]["minimum_occurrence_identity_coverage"],
            "minimum_year_cell_identity_coverage": pre[
                "source_and_identity_contract"
            ]["minimum_year_cell_identity_coverage"],
            "minimum_year_cell_retention": pre[
                "source_and_identity_contract"
            ]["minimum_year_cell_retention"],
            "operational_denominator": pre[
                "source_and_identity_contract"
            ]["operational_identity_denominator"],
            "unique_player_identity_coverage": pre[
                "source_and_identity_contract"
            ]["unique_player_identity_coverage"],
            "stable_identity_priority": pre[
                "source_and_identity_contract"
            ]["stable_identity_priority"],
            "manual_post_outcome_identity_adjudication_allowed": False,
        },
        "unchanged_v6_contract": {
            "candidate_families": pre["candidate_families"],
            "development_selection": pre["development_selection"],
            "historical_outcome_contract": pre[
                "historical_outcome_contract"
            ],
            "fit_weighting": pre["fit_weighting"],
            "temporal_holdout_2024": pre["temporal_holdout_2024"],
            "frozen_deployed_baseline": pre[
                "frozen_deployed_baseline"
            ],
            "forbidden": pre["forbidden"],
            "r5_r6_remain_frozen": True,
            "year_discount_remains_frozen": True,
            "2022_2023_remain_spent_evidence": True,
            "2024_h3_remains_future_clean_confirmation": True,
        },
        "phase2_gate": {
            "development_clean_league_n_exact": 378,
            "development_counts_by_year_exact":
                dict(EXPECTED_BY_YEAR),
            "development_every_year_cell_retention_min": 0.95,
            "development_every_year_cell_identity_min": 0.95,
            "development_every_year_cell_sleeper_ready_min": 0.95,
            "holdout_2024_clean_league_n_min": 19,
            "holdout_every_cell_retention_min": 0.95,
            "holdout_every_cell_identity_min": 0.95,
            "holdout_every_cell_sleeper_ready_min": 0.95,
            "historical_outcomes_read": False,
            "holdout_outcomes_read": False,
            "candidate_fit_performed": False,
        },
        "next_stage": (
            "draft-pick-fv-v6-phase2-r1-r4-"
            "source-identity-freeze-v6-1"
        ),
    }

def selftest() -> None:
    pre = {
        "status": "FROZEN_PRE_V6_R3_R4_OUTCOME_ACCESS",
        "production_change_authorized": False,
        "source_population": {
            "frozen_v3_primary_r1_r4_league_n": 213,
            "2024_holdout_source": {
                "minimum_eligible_leagues": 19,
            },
        },
        "source_and_identity_contract": {
            "minimum_occurrence_identity_coverage": 0.95,
            "minimum_year_cell_identity_coverage": 0.95,
            "minimum_year_cell_retention": 0.95,
            "operational_identity_denominator":
                "retained pick occurrences",
            "unique_player_identity_coverage":
                "diagnostic_only_not_gate",
            "stable_identity_priority": ["a", "b"],
        },
        "candidate_families": {"C1": {}},
        "development_selection": {"method": "LOYO"},
        "historical_outcome_contract": {"provider": "Sleeper"},
        "fit_weighting": {"draft_class_weight": "equal"},
        "temporal_holdout_2024": {"outcomes_sealed": True},
        "frozen_deployed_baseline": {"r5_r6_fit_status": "frozen"},
        "forbidden": ["outcome leakage"],
    }
    pm = {
        "historical_r3_r4_outcomes_read": False,
        "holdout_2024_outcomes_read": False,
        "candidate_fit_performed": False,
        "candidate_selection_performed": False,
        "production_change_authorized": False,
    }
    contam = {
        "audit_counts": {
            "frozen_catalog_league_n": 213,
            "clean_league_n": 172,
            "positive_contaminated_league_n": 41,
        },
        "historical_player_outcomes_read": False,
    }
    v4 = {
        "clean_totals": {"primary_r1_r4": 378},
        "historical_player_outcomes_read": False,
        "frozen_contamination_contract": {
            "league_rule": "exclude positive",
            "identity_namespace_rule": "league scoped",
            "positive_contamination_evidence": ["earlier", "later"],
        },
    }
    v4m = {"historical_player_outcomes_read": False}
    lineage = {
        "status": "frozen_pre_outcome_source_lineage",
        "historical_player_outcomes_read": False,
        "clean_full_r4_total": 378,
        "v3_clean_seed_total": 172,
        "v4_new_clean_total": 206,
        "clean_full_r4_counts_by_year": dict(EXPECTED_BY_YEAR),
        "exact_phase2_catalog_rule": {
            "no_additional_source_search": True,
            "no_post_freeze_manual_inclusions": True,
        },
    }
    feas = {
        "historical_player_outcomes_read": False,
        "discovery_design": {
            "max_per_term": 50,
            "search_terms": list(SEARCH_TERMS),
            "probe_entire_bounded_unique_union": True,
            "search_failures_are_fatal": True,
        },
    }
    a = build(
        pre, pm, contam, v4, v4m, lineage, feas,
        generated_at="TEST",
    )
    assert a["source_contract_replacement"][
        "frozen_clean_development_source"
    ]["league_n"] == 378
    assert a["holdout_2024_source_contract"][
        "minimum_clean_full4_leagues"
    ] == 19
    assert a["historical_r3_r4_outcomes_read"] is False
    assert a["holdout_2024_outcomes_read"] is False
    assert a["production_change_authorized"] is False
    print("PASS: V6.1 clean-source amendment self-test")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return

    if any(p.exists() for p in (OUT_JSON, OUT_MD, OUT_MAN)):
        raise GateError("V6.1 amendment output already exists")

    pre = load(PRE)
    pm = load(PRE_MAN)
    contam = load(V3_CONTAM)
    v4 = load(V4)
    v4m = load(V4_MAN)
    lineage = load(V5_LINEAGE)
    feas = load(V3_FEAS)

    generated = datetime.now(timezone.utc).isoformat()
    amendment = build(
        pre, pm, contam, v4, v4m, lineage, feas,
        generated_at=generated,
    )

    OUT_JSON.write_text(
        json.dumps(amendment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Draft Pick FV V6.1 — Clean Source Pre-Outcome Amendment",
        "",
        f"**Decision:** `{amendment['decision']}`",
        "",
        "This is an additive pre-outcome correction. The original "
        "V6 Phase 1 preregistration remains immutable.",
        "",
        "## Why the amendment is necessary",
        "",
        "- Original Phase 1 development source: **213 V3 leagues**",
        "- Later pre-outcome V3 audit: **41 positively contaminated**",
        "- Clean V3 seed: **172 leagues**",
        "- Frozen V4 clean expansion: **206 leagues**",
        "- Amended clean full-R4 development cohort: **378 leagues**",
        "",
        "No V6 R3/R4 NFL outcomes, 2024 holdout outcomes, candidate "
        "fits, KTC/market values, or package votes triggered this "
        "change.",
        "",
        "## 2018–2023 source contract",
        "",
        "Phase 2 must use the already-frozen V5 clean full-R4 "
        "lineage: 172 clean V3 seeds + 206 clean V4 expansion "
        "leagues. No new historical source search is allowed.",
        "",
        "## 2024 holdout",
        "",
        "Phase 2 may run the frozen V3 bounded MFL search design "
        "for 2024, then must apply the V4 positive-contamination "
        "rule before freezing every clean eligible full-R4 league. "
        "At least 19 clean leagues are required.",
        "",
        "## Firewalls",
        "",
        "- Historical R3/R4 outcomes read: **No**",
        "- 2024 holdout outcomes read: **No**",
        "- Candidate fit performed: **No**",
        "- Production change authorized: **No**",
        "",
        f"Next stage: `{amendment['next_stage']}`",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "study_id": amendment["study_id"],
        "stage": amendment["stage"],
        "status": amendment["status"],
        "decision": amendment["decision"],
        "generated_at_utc": generated,
        "original_phase1_preserved": True,
        "historical_r3_r4_outcomes_read": False,
        "holdout_2024_outcomes_read": False,
        "candidate_fit_performed": False,
        "candidate_selection_performed": False,
        "production_change_authorized": False,
        "next_stage": amendment["next_stage"],
        "input_hashes": {
            PRE.name: sha256(PRE),
            PRE_MAN.name: sha256(PRE_MAN),
            V3_CONTAM.name: sha256(V3_CONTAM),
            V4.name: sha256(V4),
            V4_MAN.name: sha256(V4_MAN),
            V5_LINEAGE.name: sha256(V5_LINEAGE),
            V3_FEAS.name: sha256(V3_FEAS),
        },
        "output_hashes": {
            OUT_JSON.name: sha256(OUT_JSON),
            OUT_MD.name: sha256(OUT_MD),
        },
        "canonical_amendment_sha256":
            canonical_sha(amendment),
    }
    OUT_MAN.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"DECISION={amendment['decision']}")
    print("DEVELOPMENT_SOURCE=378_clean_full_R4")
    print("V3_CLEAN=172 V4_NEW_CLEAN=206")
    print("2024_HOLDOUT=search_then_contamination_audit_min19")
    print("OUTCOMES_READ=false")

if __name__ == "__main__":
    main()
