#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import requests

STUDY_ID = "player-role-v2"
CONTINUATION_CLASS = "OUTCOME_BLIND_IDENTITY_SOURCE_AMENDMENT"
PASS_RESULT = "PASS_2025_HOLDOUT_VALIDATION_OUTCOME_BLIND_IDENTITY_SOURCE_AMENDMENT"
FAIL_RESULT = "SCIENTIFIC_STOP_2025_HOLDOUT_VALIDATION_FAILED_OUTCOME_BLIND_IDENTITY_SOURCE_AMENDMENT"
DATA_STOP_RESULT = "SCIENTIFIC_STOP_DATA_INTEGRITY"

B41H_EVALUATOR_SHA256 = "5adf8692cba41165ac84bb86c3b76c55c217c00562367f33c644b11854cbd634"
B41B_BUILDER_SHA256 = "84dcee287a9884976344acb13b844267105da0396fd4c1f02898b7d70c5d15dc"
B41I_IDENTITY_SHA256 = "d531dcff2d3ff681f02210d314f6e9f16c671c0beefa85fd311a55363675d4cc"
B41I_IDENTITY_RELATIVE_PATH = "research/player-role-v2/frozen_inputs/players_b41i_snapshot.csv"

ORIGINAL_PLAYERS_SHA256 = "810c1a8b09de1dc2ef94af7cabce5b66d0a6d5ac0751f99c5eaf09dc21425a21"
B41H_OBSERVED_PLAYERS_SHA256 = "7ea1f10f0c3b0bf5c026a4b5935c6d01e4a72864a3122594a6df493b5bf29d97"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_and_verify_frozen_lineage(repo: Path):
    base = repo / "research/player-role-v2"

    b41h_path = base / "player_role_v2_b41h_one_shot_holdout_evaluator.py"
    if sha256_file(b41h_path) != B41H_EVALUATOR_SHA256:
        raise RuntimeError("B41J_B41H_FROZEN_EVALUATOR_SHA_DRIFT")
    b41h = load_module(b41h_path, "b41j_frozen_b41h_parent")

    prereg, baseline, b41f, c3 = b41h.frozen_preflight(base)

    b41i_path = base / "player_role_v2_b41i_recovery_eligibility_decision.json"
    b41i = json.loads(b41i_path.read_text())

    if b41i.get("result") != "PASS_B41I_OUTCOME_BLIND_RECOVERY_ELIGIBLE_FOR_B41J":
        raise RuntimeError("B41J_B41I_NOT_PASS")
    if b41i.get("continuation_class") != CONTINUATION_CLASS:
        raise RuntimeError("B41J_CONTINUATION_CLASS_DRIFT")
    if b41i.get("recovery_mode") != "CURRENT_UPSTREAM_IDENTITY_SNAPSHOT_FROZEN":
        raise RuntimeError("B41J_B41I_RECOVERY_MODE_DRIFT")
    if b41i.get("requires_identity_source_amendment") is not True:
        raise RuntimeError("B41J_B41I_AMENDMENT_FLAG_DRIFT")
    if b41i.get("human_holdout_performance_read_by_b41i") is not False:
        raise RuntimeError("B41J_B41I_PERFORMANCE_PEEK_FLAG_NOT_FALSE")
    if b41i.get("holdout_metric_computed_by_b41i") is not False:
        raise RuntimeError("B41J_B41I_METRIC_COMPUTED_FLAG_NOT_FALSE")
    if b41i.get("model_or_tier_retuning_performed") is not False:
        raise RuntimeError("B41J_B41I_RETUNING_FLAG_NOT_FALSE")
    if b41i.get("production_change_authorized") is not False:
        raise RuntimeError("B41J_B41I_PRODUCTION_AUTH_NOT_FALSE")
    if b41i.get("production_model_deployed") is not False:
        raise RuntimeError("B41J_B41I_DEPLOYED_NOT_FALSE")
    if b41i.get("B42_owner_blind_role_parity_audit_still_required") is not True:
        raise RuntimeError("B41J_B42_REQUIREMENT_DRIFT")

    req = b41i.get("b41j_requirements") or {}
    expected_true = [
        "carry_continuation_class_in_every_result_and_report",
        "hash_pin_all_four_B41G_tests",
        "hash_pin_frozen_B41E_thresholds",
        "hash_pin_frozen_B41F_model",
        "hash_pin_frozen_feature_list",
        "hash_pin_frozen_imputation_logic",
        "load_identity_only_from_b41j_identity_source",
        "no_retuning",
        "report_outcome_blind_cohort_size",
        "report_outcome_blind_identity_mapping_coverage",
        "report_outcome_blind_position_distribution",
    ]
    for key in expected_true:
        if req.get(key) is not True:
            raise RuntimeError(f"B41J_B41I_REQUIREMENT_NOT_TRUE {key}")

    identity = b41i.get("b41j_identity_source") or {}
    if identity != {
        "kind": "committed_file",
        "path": B41I_IDENTITY_RELATIVE_PATH,
        "sha256": B41I_IDENTITY_SHA256,
    }:
        raise RuntimeError(f"B41J_B41I_IDENTITY_SOURCE_DRIFT {identity}")

    players_path = repo / B41I_IDENTITY_RELATIVE_PATH
    if not players_path.exists():
        raise RuntimeError("B41J_FROZEN_IDENTITY_FILE_MISSING")
    if sha256_file(players_path) != B41I_IDENTITY_SHA256:
        raise RuntimeError("B41J_FROZEN_IDENTITY_SHA_MISMATCH")

    b41h_stop = json.loads((base / "player_role_v2_b41h_scientific_decision.json").read_text())
    expected_reason = (
        "SOURCE_SHA_MISMATCH players "
        f"expected={ORIGINAL_PLAYERS_SHA256} actual={B41H_OBSERVED_PLAYERS_SHA256}"
    )
    if b41h_stop.get("result") != "SCIENTIFIC_STOP_DATA_INTEGRITY":
        raise RuntimeError("B41J_B41H_STOP_RESULT_DRIFT")
    if b41h_stop.get("reason") != expected_reason:
        raise RuntimeError("B41J_B41H_STOP_REASON_DRIFT")

    for forbidden in [
        base / "player_role_v2_b41h_holdout_evidence.json",
        base / "player_role_v2_b41h_scored_holdout_rows.csv",
        base / "player_role_v2_b41h_bootstrap_replicates.csv",
        base / "player_role_v2_b41h_report.md",
    ]:
        if forbidden.exists():
            raise RuntimeError(f"B41J_B41H_PERFORMANCE_OUTPUT_PRESENT {forbidden.name}")

    return base, b41h, prereg, baseline, b41f, c3, b41i, players_path


def build_holdout_cohort(
    repo: Path,
    out: Path,
    prereg: dict,
    session: requests.Session,
    b41h,
    players_path: Path,
):
    base = repo / "research/player-role-v2"
    sources = out / "sources"
    sources.mkdir(parents=True, exist_ok=True)

    stats_path = sources / "stats_player_week_2025.csv"
    snaps_path = sources / "snap_counts_2025.csv"
    source_hashes = {}

    source_hashes[stats_path.name] = b41h.source_integrity_or_stop(
        session,
        prereg["frozen_inputs"]["2025_weekly_stats"],
        stats_path,
        "2025 weekly stats",
    )
    source_hashes[snaps_path.name] = b41h.source_integrity_or_stop(
        session,
        prereg["frozen_inputs"]["2025_snap_counts"],
        snaps_path,
        "2025 snap counts",
    )

    # B41J's only identity-source amendment:
    # consume the exact B41I-committed bytes and never re-download players.csv.
    actual_players_sha = sha256_file(players_path)
    if actual_players_sha != B41I_IDENTITY_SHA256:
        raise ValueError(
            "B41J_FROZEN_IDENTITY_SHA_MISMATCH "
            f"expected={B41I_IDENTITY_SHA256} actual={actual_players_sha}"
        )
    source_hashes["players_b41i_snapshot.csv"] = actual_players_sha

    builder_path = base / "player_role_v2_b41b_cohort_builder.py"
    if sha256_file(builder_path) != B41B_BUILDER_SHA256:
        raise ValueError("B41B_BUILDER_CONTENT_SHA_MISMATCH")
    builder = b41h.load_module(builder_path, "b41j_frozen_b41b_builder")
    builder.DEV_SEASONS = (2025,)
    builder.ORIGIN_WEEKS = tuple(b41h.ORIGIN_WEEKS)

    gsis_meta, pfr_to_gsis = builder.load_players(players_path)
    all_rows, source_audit = builder.load_season(
        stats_path, snaps_path, gsis_meta, pfr_to_gsis
    )
    if {int(r["season"]) for r in all_rows} != {2025}:
        raise ValueError("B41J_HOLDOUT_SOURCE_SEASON_SCOPE_FAILED")

    cohort_rows, excluded = builder.build_origins(all_rows)
    cohort_rows.sort(
        key=lambda r: (
            r["season"],
            r["origin_week"],
            r["position"],
            r["gsis_id"],
        )
    )
    if not cohort_rows:
        raise ValueError("B41J_EMPTY_HOLDOUT_COHORT")

    df = pd.DataFrame(cohort_rows)
    if set(df["season"].astype(int).unique()) != {2025}:
        raise ValueError("B41J_HOLDOUT_COHORT_SEASON_FAILED")
    return df, source_hashes, source_audit, dict(excluded)


def identity_snapshot_structural_audit(
    players_path: Path,
    cohort_ids: pd.DataFrame,
    overall_cov: float,
    pos_cov: dict,
):
    raw = pd.read_csv(players_path, dtype=str, keep_default_na=False)
    headers = set(raw.columns)
    required = {"gsis_id", "pfr_id", "position"}
    if not required.issubset(headers):
        raise ValueError(
            "B41J_FROZEN_IDENTITY_REQUIRED_SCHEMA_MISSING "
            f"{sorted(required - headers)}"
        )

    # Match frozen builder semantics: later duplicate gsis_id rows overwrite earlier ones.
    row_by_gsis = {}
    for _, row in raw.iterrows():
        gsis = str(row.get("gsis_id") or "").strip()
        if gsis:
            row_by_gsis[gsis] = row

    unique_gsis = sorted(
        {str(x).strip() for x in cohort_ids["gsis_id"].tolist() if str(x).strip()}
    )
    resolution = Counter()
    missing_identity_rows = 0
    for gsis in unique_gsis:
        row = row_by_gsis.get(gsis)
        if row is None:
            missing_identity_rows += 1
            resolution["missing_identity_row"] += 1
            continue

        display = str(row.get("display_name") or "").strip()
        full = str(row.get("full_name") or "").strip()
        football = str(row.get("football_name") or "").strip()
        if display:
            resolution["display_name"] += 1
        elif full:
            resolution["full_name_fallback"] += 1
        elif football:
            resolution["football_name_fallback"] += 1
        else:
            resolution["empty_after_all_fallbacks"] += 1

    position_rows = (
        cohort_ids.groupby("position", observed=True).size().astype(int).to_dict()
    )
    unique_players_by_position = (
        cohort_ids.groupby("position", observed=True)["gsis_id"].nunique().astype(int).to_dict()
    )

    return {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "phase": "B41J-outcome-blind-structural-preperformance-report",
        "continuation_class": CONTINUATION_CLASS,
        "identity_source_sha256": B41I_IDENTITY_SHA256,
        "identity_source_path": B41I_IDENTITY_RELATIVE_PATH,
        "identity_required_columns_present": sorted(required),
        "identity_optional_name_columns_present": sorted(
            c for c in ["display_name", "full_name", "football_name"] if c in headers
        ),
        "identity_optional_name_columns_missing": sorted(
            c for c in ["display_name", "full_name", "football_name"] if c not in headers
        ),
        "cohort_rows_before_stable_id_filter": int(len(cohort_ids)),
        "cohort_unique_gsis_ids": int(len(unique_gsis)),
        "cohort_position_rows": {str(k): int(v) for k, v in position_rows.items()},
        "cohort_unique_players_by_position": {
            str(k): int(v) for k, v in unique_players_by_position.items()
        },
        "overall_stable_id_coverage": float(overall_cov),
        "position_stable_id_coverage": {
            str(k): float(v) for k, v in pos_cov.items()
        },
        "identity_name_resolution_for_cohort_unique_gsis": {
            key: int(resolution.get(key, 0))
            for key in [
                "display_name",
                "full_name_fallback",
                "football_name_fallback",
                "empty_after_all_fallbacks",
                "missing_identity_row",
            ]
        },
        "identity_rows_missing_for_cohort_unique_gsis": int(missing_identity_rows),
        "performance_metric_computed_at_report_time": False,
        "model_score_computed_at_report_time": False,
        "target_percentile_computed_at_report_time": False,
        "production_change_authorized": False,
    }


def evaluate(repo: Path, out: Path):
    (
        base,
        b41h,
        prereg,
        baseline,
        b41f,
        c3,
        b41i,
        players_path,
    ) = load_and_verify_frozen_lineage(repo)

    out.mkdir(parents=True, exist_ok=True)

    existing = [
        base / "player_role_v2_b41j_holdout_evidence.json",
        base / "player_role_v2_b41j_scientific_decision.json",
        base / "player_role_v2_b41j_scored_holdout_rows.csv",
        base / "player_role_v2_b41j_bootstrap_replicates.csv",
    ]
    if any(p.exists() for p in existing):
        raise RuntimeError("B41J_ONE_SHOT_EVIDENCE_ALREADY_EXISTS_REFUSE_RERUN")

    witness_path = base / "player_role_v2_b41j_holdout_continuation_open_witness.json"
    if not witness_path.exists():
        raise RuntimeError("B41J_DURABLE_OPEN_WITNESS_MISSING")
    witness = json.loads(witness_path.read_text())
    if witness.get("continuation_class") != CONTINUATION_CLASS:
        raise RuntimeError("B41J_OPEN_WITNESS_CONTINUATION_CLASS_DRIFT")
    if witness.get("b41i_identity_sha256") != B41I_IDENTITY_SHA256:
        raise RuntimeError("B41J_OPEN_WITNESS_IDENTITY_SHA_DRIFT")
    if witness.get("performance_decision_computed_before_witness") is not False:
        raise RuntimeError("B41J_OPEN_WITNESS_PERFORMANCE_FLAG_DRIFT")

    session = requests.Session()
    session.headers.update({"User-Agent": "LOG-Trade-Calculator-player-role-v2-b41j"})

    try:
        cohort, source_hashes, b41b_source_audit, exclusions = build_holdout_cohort(
            repo, out, prereg, session, b41h, players_path
        )
        cohort_ids, cross_sha, overall_cov, pos_cov = b41h.attach_stable_ids(
            cohort, prereg, session
        )

        structural = identity_snapshot_structural_audit(
            players_path, cohort_ids, overall_cov, pos_cov
        )
        structural["modeling_rows_after_stable_id_filter"] = int(
            cohort_ids["identity_mapped"].sum()
        )
        structural_path = out / "player_role_v2_b41j_structural_preperformance.json"
        structural_path.write_text(
            json.dumps(structural, indent=2, sort_keys=True) + "\n"
        )

        # From this point onward, preserve the exact frozen B41H/B41G scoring,
        # model, data-quality, bootstrap, and tier-test implementation.
        model = cohort_ids[cohort_ids["identity_mapped"]].copy()
        model["sleeper_id"] = model["sleeper_id"].astype(str)

        scored_base, sleeper_hashes, history_missing, target_missing = (
            b41h.score_and_normalize(
                model, repo, out, prereg, b41f, session
            )
        )
        scored, imputation = b41h.apply_frozen_models(
            scored_base, baseline, b41f
        )
        dq = b41h.data_quality(
            scored, cohort_ids, prereg, overall_cov, pos_cov
        )

        test1 = test2 = per_pos = bootstrap_df = None
        test3 = test4 = None
        if dq["pass"]:
            test1, test2, per_pos, bootstrap_df = b41h.bootstrap_tests(
                scored, prereg
            )
            test3 = b41h.tier_test(
                scored,
                "target_percentile",
                b41h.POSITIONS,
                int(
                    prereg["primary_holdout_tests"][
                        "test_3_ordered_tier_future_production"
                    ]["minimum_rows_per_tier"]
                ),
            )
            test4 = b41h.tier_test(
                scored,
                "future_snap_percentile",
                b41h.SNAP_POSITIONS,
                int(
                    prereg["primary_holdout_tests"][
                        "test_4_ordered_tier_future_snap_share"
                    ]["minimum_rows_per_tier"]
                ),
            )
            primary_pass = all(
                [test1["pass"], test2["pass"], test3["pass"], test4["pass"]]
            )
        else:
            primary_pass = False

        scored_keep = scored[
            [
                "season",
                "origin_week",
                "gsis_id",
                "sleeper_id",
                "player_name",
                "position",
                "team_at_origin",
                "target_next4_active_ppg",
                "target_percentile",
                "future_snap_share_raw",
                "future_snap_percentile",
                "model_score",
                "baseline_score",
                "baseline_feature",
                "tier_index",
                "role_tier",
            ]
        ].copy()

        scored_path = out / "player_role_v2_b41j_scored_holdout_rows.csv"
        b41h.write_csv_deterministic(scored_keep, scored_path)

        if bootstrap_df is not None:
            bootstrap_path = out / "player_role_v2_b41j_bootstrap_replicates.csv"
            b41h.write_csv_deterministic(bootstrap_df, bootstrap_path)
        else:
            bootstrap_path = None

        evidence = {
            "schema_version": 1,
            "study_id": STUDY_ID,
            "phase": "B41J-2025-holdout-continuation-evidence",
            "holdout_season": 2025,
            "continuation_class": CONTINUATION_CLASS,
            "identity_source_amendment": True,
            "identity_source": {
                "path": B41I_IDENTITY_RELATIVE_PATH,
                "sha256": B41I_IDENTITY_SHA256,
                "original_preregistered_sha256": ORIGINAL_PLAYERS_SHA256,
                "b41h_observed_sha256": B41H_OBSERVED_PLAYERS_SHA256,
            },
            "B41C3_result": c3["result"],
            "B41I_result": b41i["result"],
            "B41H_performance_was_uncomputed_before_B41J": True,
            "source_sha256": source_hashes,
            "stable_id_crosswalk_sha256": cross_sha,
            "sleeper_weekly_raw_stats_sha256": sleeper_hashes,
            "b41b_source_audit": b41b_source_audit,
            "cohort_exclusions": exclusions,
            "history_active_game_raw_stats_missing_count": int(history_missing),
            "target_active_game_raw_stats_missing_count": int(target_missing),
            "future_snap_percentile_nonfinite_count": int(
                (
                    ~np.isfinite(
                        scored["future_snap_percentile"].to_numpy(dtype=float)
                    )
                ).sum()
            ),
            "imputation": imputation,
            "data_quality": dq,
            "primary_tests": {
                "test_1_error_vs_baseline": test1,
                "test_2_spearman_association": test2,
                "test_3_ordered_tier_future_production": test3,
                "test_4_ordered_tier_future_snap_share": test4,
            },
            "secondary_per_position_performance": per_pos,
            "secondary_per_position_tiers_and_clipping": (
                b41h.secondary_descriptives(scored)
            ),
            "structural_preperformance_sha256": sha256_file(structural_path),
            "scored_rows_sha256": sha256_file(scored_path),
            "bootstrap_replicates_sha256": (
                sha256_file(bootstrap_path) if bootstrap_path else None
            ),
            "frozen_B41H_evaluator_sha256": B41H_EVALUATOR_SHA256,
            "model_or_tier_retuning_performed": False,
            "posthoc_exclusions_performed": False,
            "production_change_authorized": False,
        }
        evidence_path = out / "player_role_v2_b41j_holdout_evidence.json"
        evidence_path.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n"
        )

        if not dq["pass"]:
            result = DATA_STOP_RESULT
        elif primary_pass:
            result = PASS_RESULT
        else:
            result = FAIL_RESULT

        decision = {
            "schema_version": 1,
            "study_id": STUDY_ID,
            "phase": "B41J-scientific-decision",
            "result": result,
            "continuation_class": CONTINUATION_CLASS,
            "identity_source_amendment": True,
            "identity_source_sha256": B41I_IDENTITY_SHA256,
            "2025_holdout_performance_evaluated_once_by_B41J": True,
            "B41H_performance_was_uncomputed_before_B41J": True,
            "data_quality_pass": bool(dq["pass"]),
            "all_four_primary_tests_pass": (
                bool(primary_pass) if dq["pass"] else False
            ),
            "model_or_tier_retuning_performed": False,
            "posthoc_exclusions_performed": False,
            "production_model_deployed": False,
            "production_change_authorized": False,
            "B42_owner_blind_role_parity_audit_required_before_production": True,
            "next_stage": (
                "Run B42 owner-blind role parity audit with the frozen Role V2 "
                "system and disclosed B41I identity-source amendment; no production "
                "deployment yet."
                if result == PASS_RESULT
                else "Scientific STOP for Player Role Engine V2 production path; "
                "preserve B41J evidence and do not retune or deploy this version."
            ),
            "evidence_sha256": sha256_file(evidence_path),
        }
        decision_path = out / "player_role_v2_b41j_scientific_decision.json"
        decision_path.write_text(
            json.dumps(decision, indent=2, sort_keys=True) + "\n"
        )

        report = [
            "# Player Role V2 — B41J 2025 Holdout Continuation Evaluation",
            "",
            f"- Continuation class: **{CONTINUATION_CLASS}**",
            "- B41I identity-source amendment used: **Yes**",
            f"- Frozen B41I identity SHA256: `{B41I_IDENTITY_SHA256}`",
            f"- Holdout rows: **{len(scored):,}**",
            f"- Data-quality gate: **{'PASS' if dq['pass'] else 'FAIL'}**",
            "- B41F model retuned: **No**",
            "- B41E tiers retuned: **No**",
            "- Post-hoc exclusions: **No**",
            "- Production deployed: **No**",
            "- Production change authorized: **No**",
            "",
            "## Outcome-blind structural report",
            "",
            f"- Pre-performance structural artifact SHA256: `{sha256_file(structural_path)}`",
            f"- Cohort rows before stable-ID filter: **{structural['cohort_rows_before_stable_id_filter']:,}**",
            f"- Modeling rows after stable-ID filter: **{structural['modeling_rows_after_stable_id_filter']:,}**",
            f"- Overall stable-ID coverage: **{structural['overall_stable_id_coverage']:.6f}**",
            f"- Missing optional identity columns: **{', '.join(structural['identity_optional_name_columns_missing']) or 'none'}**",
            "",
        ]
        if test1 is not None:
            report += [
                "## Frozen primary holdout tests",
                "",
                f"1. MAE vs baseline: **{'PASS' if test1['pass'] else 'FAIL'}** — "
                f"macro Δ={test1['point_macro_position_mae_difference']:.6f}, "
                f"95% CI [{test1['ci95'][0]:.6f}, {test1['ci95'][1]:.6f}]",
                f"2. Pooled Spearman: **{'PASS' if test2['pass'] else 'FAIL'}** — "
                f"ρ={test2['point_pooled_spearman']:.6f}, "
                f"95% CI [{test2['ci95'][0]:.6f}, {test2['ci95'][1]:.6f}]",
                f"3. Ordered future production tiers: **{'PASS' if test3['pass'] else 'FAIL'}**",
                f"4. Ordered future snap tiers: **{'PASS' if test4['pass'] else 'FAIL'}**",
                "",
            ]
        report += [
            "## Scientific decision",
            "",
            f"**{result}**",
            "",
            "## Next stage",
            "",
            decision["next_stage"],
            "",
        ]
        (out / "player_role_v2_b41j_report.md").write_text(
            "\n".join(report), encoding="utf-8"
        )

        # Deliberately do not print PASS/FAIL or test values before the workflow
        # durably commits all B41J evidence.
        print("B41J evaluation completed; outcome sealed pending durable evidence commit.")
        return result

    except RuntimeError as exc:
        text = str(exc)
        if text.startswith("transport failure"):
            abort = {
                "schema_version": 1,
                "study_id": STUDY_ID,
                "phase": "B41J-operational-abort",
                "result": "OPERATIONAL_ABORT_BEFORE_COMPLETE_METRIC_EVALUATION",
                "reason": text,
                "continuation_class": CONTINUATION_CLASS,
                "identity_source_sha256": B41I_IDENTITY_SHA256,
                "performance_decision_computed": False,
                "same_frozen_evaluator_rerun_permitted": True,
                "retuning_permitted": False,
                "production_change_authorized": False,
            }
            (out / "player_role_v2_b41j_operational_abort.json").write_text(
                json.dumps(abort, indent=2, sort_keys=True) + "\n"
            )
        raise

    except ValueError as exc:
        # Never overwrite an already-computed PASS/FAIL decision with a later
        # formatting/output ValueError. If a scientific decision already exists,
        # preserve it exactly and let the workflow durably record the traceback.
        existing_decision = out / "player_role_v2_b41j_scientific_decision.json"
        if existing_decision.exists():
            raise

        decision = {
            "schema_version": 1,
            "study_id": STUDY_ID,
            "phase": "B41J-scientific-decision",
            "result": DATA_STOP_RESULT,
            "reason": str(exc),
            "continuation_class": CONTINUATION_CLASS,
            "identity_source_amendment": True,
            "identity_source_sha256": B41I_IDENTITY_SHA256,
            "2025_holdout_performance_evaluated_once_by_B41J": True,
            "performance_decision_computed": False,
            "production_model_deployed": False,
            "production_change_authorized": False,
        }
        (out / "player_role_v2_b41j_scientific_decision.json").write_text(
            json.dumps(decision, indent=2, sort_keys=True) + "\n"
        )
        raise


def self_test():
    assert CONTINUATION_CLASS == "OUTCOME_BLIND_IDENTITY_SOURCE_AMENDMENT"
    assert len(B41I_IDENTITY_SHA256) == 64
    assert PASS_RESULT.startswith("PASS_2025_HOLDOUT_VALIDATION")
    print("PASS B41J wrapper self-test")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out-dir")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return
    if not args.out_dir:
        raise SystemExit("--out-dir required unless --self-test")

    evaluate(
        Path(args.repo).resolve(),
        Path(args.out_dir).resolve(),
    )


if __name__ == "__main__":
    main()
