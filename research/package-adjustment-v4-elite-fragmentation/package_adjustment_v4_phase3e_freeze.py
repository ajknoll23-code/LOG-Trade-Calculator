#!/usr/bin/env python3
"""Package Adjustment V4 Phase 3E — freeze exact 600 confirmation ballots.

Reconstructs the preregistered exact-600 checkpoint from the live vote sheet
using the successful outcome-blind Phase 3D maturity anchor, verifies every
coverage gate, then reveals only the frozen checkpoint's response/orientation
tokens required for the later one-time evaluation.

No model is fit, scored, compared, ranked, or selected here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "research" / "package-adjustment-v4-elite-fragmentation"

PREREG = D / "phase1_structural_preregistration.json"
FAMILY = D / "frozen_candidate.json"
CATALOG = D / "phase3b_confirmation_catalog.json"
CATALOG_MANIFEST = D / "phase3b_confirmation_catalog_manifest.json"
RELEASE = D / "phase3c_voting_release.json"

DATA_OUT = D / "phase3_exact_600_frozen.json"
MANIFEST_OUT = D / "phase3_exact_600_freeze_manifest.json"
REPORT_OUT = D / "phase3_exact_600_freeze.md"
INTERPRETATION_OUT = D / "phase3f_interpretation_contract.json"

INDEX = ROOT / "index.html"
REGRESSION = ROOT / "scripts" / "validation" / "repo_regression_checks.py"

SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vTuKORGumlKJmUmBdeNWPstkj8VRjPoVkylbqHv1KqwoyziJYOUlkZUKRsSxzB3qHXmyjjLpGpH6W03/"
    "pub?gid=458294959&single=true&output=csv"
)

# Immutable successful Phase 3D outcome-blind maturity anchor.
MATURITY_RUN_ID = 35512427556
MATURITY_JOB_ID = 106085395037
MATURITY_ANCHOR_UTC = "2026-09-20T13:26:20.584016+00:00"
MATURITY_SOURCE_SHEET_SHA256 = (
    "05c282122542a923ac309773b2e5513eb331f811d686e385cc8d224093a9cc2f"
)
MATURITY_ARTIFACT_JSON_SHA256 = (
    "d6fd88e561ba2c7bf8cc74c2e0f1820bba40c0feb7db9760ec07e333fd27340c"
)
MATURITY_ARTIFACT_ZIP_SHA256 = (
    "136b0ab50478f1a962e11ed70abcffa1c3b8c4428754947f64dc734aba4437ae"
)

EXPECTED_ANCHORED = {
    "raw_namespace_rows": 600,
    "valid_post_daily_cap_ballots": 600,
    "effective_votes": 600.0,
    "distinct_voters": 31,
    "distinct_challenges": 231,
    "cells_observed": 24,
    "cells_passing_both_gates": 24,
    "minimum_cell_effective_votes": 17.0,
    "minimum_cell_distinct_voters": 13,
}

EXPECTED_CHECKPOINT = {
    "effective_votes": 600.0,
    "raw_post_daily_cap_ballots": 600,
    "distinct_voters": 31,
    "distinct_challenges": 231,
    "cells_observed": 24,
    "cells_passing_both_gates": 24,
    "minimum_cell_effective_votes": 17.0,
    "minimum_cell_distinct_voters": 13,
}

VOTE_PREFIX = "__pkgv4c1__|"
META_PREFIX = "__pkgv4c1_meta__|"
SCHEMA_MARKER = "__pkgv4c1_schema__|1"


def parse_utc(value):
    s = str(value or "").strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def selftest():
    daily_cap = 20
    lifetime_cap = 30
    rows = []
    for voter in range(31):
        n = 20 if voter < 29 else 10
        for i in range(n):
            rows.append({
                "voter": f"v{voter}",
                "timestamp": datetime(2026, 9, 20, 12, i, tzinfo=timezone.utc),
                "source_index": len(rows),
            })

    # 29*20 + 2*10 = 600.
    assert len(rows) == 600

    daily_counts = Counter()
    valid = []
    for row in rows:
        key = (row["voter"], row["timestamp"].date().isoformat())
        if daily_counts[key] >= daily_cap:
            continue
        daily_counts[key] += 1
        valid.append(row)
    assert len(valid) == 600

    voter_counts = Counter(r["voter"] for r in valid)
    assert len(voter_counts) == 31
    assert sum(min(n, lifetime_cap) for n in voter_counts.values()) == 600

    print("Package Adjustment V4 Phase 3E freeze self-test PASS")


def snapshot(rows_subset, challenges, cells, lifetime_cap,
             min_voters, min_cell_effective, min_cell_voters):
    voter_counts = Counter(r["voter"] for r in rows_subset)
    weights = {
        voter: min(1.0, lifetime_cap / count)
        for voter, count in voter_counts.items()
    }

    per_cell_effective = {cell: 0.0 for cell in cells}
    per_cell_voters = {cell: set() for cell in cells}
    observed_challenges = set()

    for row in rows_subset:
        challenge = challenges[row["challenge_id"]]
        cell = challenge["research_cell"]
        per_cell_effective[cell] += weights[row["voter"]]
        per_cell_voters[cell].add(row["voter"])
        observed_challenges.add(row["challenge_id"])

    cell_rows = []
    for cell in cells:
        eff = per_cell_effective[cell]
        voters = len(per_cell_voters[cell])
        topology, mix, stratum = cell.split("|")
        cell_rows.append({
            "research_cell": cell,
            "topology": topology,
            "asset_mix": mix,
            "challenge_stratum": stratum,
            "effective_votes": round(float(eff), 6),
            "distinct_voters": voters,
            "cell_gate_pass": (
                eff + 1e-12 >= min_cell_effective
                and voters >= min_cell_voters
            ),
        })

    effective_total = sum(
        min(count, lifetime_cap) for count in voter_counts.values()
    )

    return {
        "raw_post_daily_cap_ballots": len(rows_subset),
        "effective_votes": round(float(effective_total), 6),
        "distinct_voters": len(voter_counts),
        "distinct_challenges": len(observed_challenges),
        "cells_observed": sum(c["effective_votes"] > 0 for c in cell_rows),
        "cells_passing_both_gates": sum(c["cell_gate_pass"] for c in cell_rows),
        "minimum_cell_effective_votes": round(
            min(c["effective_votes"] for c in cell_rows), 6
        ),
        "minimum_cell_distinct_voters": min(
            c["distinct_voters"] for c in cell_rows
        ),
        "coverage_gates_pass": (
            len(voter_counts) >= min_voters
            and all(c["cell_gate_pass"] for c in cell_rows)
        ),
        "cells": cell_rows,
    }


def exact_checkpoint_prefix(valid, threshold, lifetime_cap):
    counts = Counter()
    running = 0
    for idx, row in enumerate(valid):
        voter = row["voter"]
        before = min(counts[voter], lifetime_cap)
        counts[voter] += 1
        after = min(counts[voter], lifetime_cap)
        running += after - before
        if running == threshold:
            return valid[:idx + 1]
        if running > threshold:
            raise RuntimeError(
                f"Effective count skipped exact checkpoint {threshold}"
            )
    return None


def close_voting_ui():
    text = INDEX.read_text(encoding="utf-8")

    marker = (
        "const PACKAGE_VOTE_VALID_AFTER_UTC = "
        "'2026-09-19T21:23:56.548189+00:00';"
    )
    replacement = marker + "\nconst PACKAGE_VOTE_V4C1_RESEARCH_CLOSED = true;"
    if text.count(marker) != 1:
        raise RuntimeError("Could not uniquely locate V4 valid-after constant")
    if "PACKAGE_VOTE_V4C1_RESEARCH_CLOSED" in text:
        raise RuntimeError("V4C1 closed flag already exists")
    text = text.replace(marker, replacement, 1)

    submit_marker = "function packageVoteSubmit(displaySide){\n"
    submit_replacement = (
        submit_marker
        + "if(PACKAGE_VOTE_V4C1_RESEARCH_CLOSED) return;\n"
    )
    if text.count(submit_marker) != 1:
        raise RuntimeError("Could not uniquely locate packageVoteSubmit")
    text = text.replace(submit_marker, submit_replacement, 1)

    render_marker = (
        "function renderPackageVote(){\n"
        "const el = document.getElementById('packageVoteWrap');\n"
        "if(!el) return;\n"
    )
    render_replacement = render_marker + r"""
if(PACKAGE_VOTE_V4C1_RESEARCH_CLOSED){
el.innerHTML = `<div style="color:var(--text-dim);font-size:13px;padding:8px 0;">
Package Adjustment V4 confirmation voting is closed. The exact 600-vote checkpoint has been frozen for research evaluation.
</div>`;
return;
}
"""
    if text.count(render_marker) != 1:
        raise RuntimeError("Could not uniquely locate renderPackageVote header")
    text = text.replace(render_marker, render_replacement, 1)

    text = text.replace(
        "/* Package Adjustment V4 Fresh Confirmation: frozen 24-cell catalog.\n"
        "Research-only confirmation evidence. Production Package Adjustment remains V1.6. */",
        "/* Package Adjustment V4 Fresh Confirmation: exact-600 evidence frozen; voting closed.\n"
        "Research-only confirmation evidence. Production Package Adjustment remains V1.6. */",
        1,
    )

    INDEX.write_text(text, encoding="utf-8")


def patch_regression_contract():
    text = REGRESSION.read_text(encoding="utf-8")
    start = text.index("def check_package_sampling_contract():")
    end = text.index("\ndef check_index_js_syntax():", start)
    block = text[start:end]

    old = (
        '    assert "Package Adjustment V4 Fresh Confirmation: frozen 24-cell catalog." in text\n'
    )
    new = (
        '    assert "Package Adjustment V4 Fresh Confirmation: exact-600 evidence frozen; voting closed." in text\n'
        '    assert "const PACKAGE_VOTE_V4C1_RESEARCH_CLOSED = true;" in text\n'
        '    assert "if(PACKAGE_VOTE_V4C1_RESEARCH_CLOSED) return;" in block\n'
        '    assert "Package Adjustment V4 confirmation voting is closed." in block\n'
    )
    if block.count(old) != 1:
        raise RuntimeError("V4 regression active-title assertion drifted")
    block = block.replace(old, new, 1)

    old_print = (
        '    print("PASS V4C1 exact 24-cell fresh-confirmation sampling contract")\n'
    )
    new_print = (
        '    print("PASS V4C1 frozen exact-600 research contract: '
        'sampling preserved; voting closed")\n'
    )
    if block.count(old_print) != 1:
        raise RuntimeError("V4 regression print assertion drifted")
    block = block.replace(old_print, new_print, 1)

    REGRESSION.write_text(text[:start] + block + text[end:], encoding="utf-8")


def main():
    for path in (DATA_OUT, MANIFEST_OUT, REPORT_OUT, INTERPRETATION_OUT):
        if path.exists():
            raise RuntimeError(f"Phase 3E output already exists: {path}")

    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    family = json.loads(FAMILY.read_text(encoding="utf-8"))
    catalog_doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog_manifest = json.loads(CATALOG_MANIFEST.read_text(encoding="utf-8"))
    release = json.loads(RELEASE.read_text(encoding="utf-8"))

    assert prereg["status"] == "FROZEN_BEFORE_SPENT_EVIDENCE_DEVELOPMENT"
    assert prereg["frozen"] is True
    assert prereg["production_change_authorized"] is False

    contract = prereg["fresh_confirmation_contract_if_candidate_frozen"]
    maturity = contract["maturity"]

    assert contract["new_vote_namespace"] == "__pkgv4c1__"
    assert contract["challenge_count"] == 240
    assert contract["challenges_per_cell"] == 10
    assert contract["v3_600_votes_count"] is False
    assert contract["nextgen_900_votes_count"] is False

    assert maturity["outcome_blind_until_exact_checkpoint_freeze"] is True
    assert maturity["exact_effective_vote_checkpoints"] == [600, 700, 800]
    assert maturity["daily_valid_vote_cap_per_voter"] == 20
    assert maturity["effective_lifetime_vote_cap_per_voter"] == 30
    assert maturity["minimum_distinct_voters"] == 30
    assert maturity["minimum_effective_votes_per_cell"] == 15
    assert maturity["minimum_distinct_voters_per_cell"] == 10

    assert family["status"] == "FROZEN_V4_CONFIRMATION_FAMILY"
    assert family["family_count"] == 2
    assert family["v3_spent_votes_count_for_confirmation"] is False

    assert release["status"] == "FRESH_CONFIRMATION_VOTING_ACTIVE"
    assert release["vote_namespace"] == "__pkgv4c1__"
    assert release["vote_meta_namespace"] == "__pkgv4c1_meta__"
    assert release["vote_schema_marker"] == SCHEMA_MARKER
    assert release["catalog_challenge_count"] == 240
    assert release["research_cell_count"] == 24
    assert release["production_change_authorized"] is False

    assert catalog_doc["status"] == "frozen_unreleased_fresh_confirmation_catalog"
    assert catalog_doc["frozen"] is True
    assert len(catalog_doc["challenges"]) == 240
    assert catalog_doc["catalog_diagnostics"]["joe_mixon_occurrences"] == 0
    assert catalog_doc["catalog_diagnostics"]["invalid_pick_year_occurrences"] == 0
    assert catalog_doc["catalog_diagnostics"]["known_ktc_examples_in_selected_catalog"] == 0
    assert catalog_doc["catalog_diagnostics"]["historical_trade_matches_in_selected_catalog"] == 0
    assert (
        catalog_manifest["outputs"]["catalog"]["sha256"]
        == release["catalog_sha256"]
    )

    challenges = {c["id"]: c for c in catalog_doc["challenges"]}
    cells = sorted({c["research_cell"] for c in challenges.values()})
    assert len(challenges) == 240
    assert len(cells) == 24

    cutoff = parse_utc(release["valid_after_utc"])
    anchor = parse_utc(MATURITY_ANCHOR_UTC)
    assert cutoff is not None and anchor is not None
    assert anchor > cutoff

    daily_cap = int(maturity["daily_valid_vote_cap_per_voter"])
    lifetime_cap = int(maturity["effective_lifetime_vote_cap_per_voter"])
    min_voters = int(maturity["minimum_distinct_voters"])
    min_cell_effective = float(maturity["minimum_effective_votes_per_cell"])
    min_cell_voters = int(maturity["minimum_distinct_voters_per_cell"])

    response = requests.get(SHEET_URL, timeout=30)
    response.raise_for_status()
    content_type = str(response.headers.get("content-type") or "").lower()
    if "text/html" in content_type or "<html" in response.text[:500].lower():
        raise RuntimeError("Sheet export returned HTML instead of CSV")

    sheet_bytes = response.content
    sheet_sha256 = hashlib.sha256(sheet_bytes).hexdigest()
    rows = list(csv.DictReader(io.StringIO(response.text)))
    if not rows:
        raise RuntimeError("Sheet export contains no data rows")

    required = {"timestamp", "voter_roster_id", "keep", "trade", "cut"}
    missing = required - set(rows[0].keys())
    if missing:
        raise RuntimeError(f"Sheet missing required columns: {sorted(missing)}")

    total_namespace_rows_at_fetch = 0
    anchored_namespace_rows = 0
    rows_after_anchor = 0
    excluded = Counter()
    structurally_valid = []

    # Outcome-blind checkpoint reconstruction. Choice/orientation suffixes remain
    # opaque until after the exact checkpoint and maturity gates reproduce.
    for source_index, row in enumerate(rows):
        keep = str(row.get("keep") or "")
        if not keep.startswith(VOTE_PREFIX):
            continue
        total_namespace_rows_at_fetch += 1

        ts = parse_utc(row.get("timestamp"))
        if ts is None:
            raise RuntimeError(
                f"V4C1 row has invalid timestamp at CSV row {source_index + 2}"
            )
        if ts > anchor:
            rows_after_anchor += 1
            continue

        anchored_namespace_rows += 1

        if ts <= cutoff:
            excluded["pre_cutoff_or_at_cutoff"] += 1
            continue

        voter = str(row.get("voter_roster_id") or "").strip()
        if not voter:
            excluded["missing_voter_id"] += 1
            continue

        payload = keep[len(VOTE_PREFIX):]
        sep = payload.find("|")
        if sep <= 0:
            excluded["malformed_vote_transport"] += 1
            continue
        challenge_id = payload[:sep].strip()
        if challenge_id not in challenges:
            excluded["unknown_challenge_id"] += 1
            continue

        trade = str(row.get("trade") or "")
        if not trade.startswith(META_PREFIX):
            excluded["invalid_meta_namespace"] += 1
            continue

        cut = str(row.get("cut") or "")
        if cut != SCHEMA_MARKER:
            excluded["invalid_schema_marker"] += 1
            continue

        structurally_valid.append({
            "timestamp": ts,
            "timestamp_raw": str(row.get("timestamp") or ""),
            "source_index": source_index,
            "source_row_number": source_index + 2,
            "voter": voter,
            "challenge_id": challenge_id,
            "keep_raw": keep,
            "trade_raw": trade,
            "cut_raw": cut,
        })

    structurally_valid.sort(key=lambda r: (r["timestamp"], r["source_index"]))

    daily_counts = Counter()
    valid = []
    for row in structurally_valid:
        key = (row["voter"], row["timestamp"].date().isoformat())
        if daily_counts[key] >= daily_cap:
            excluded["daily_cap_excess"] += 1
            continue
        daily_counts[key] += 1
        valid.append(row)

    anchored = snapshot(
        valid, challenges, cells, lifetime_cap,
        min_voters, min_cell_effective, min_cell_voters,
    )

    if anchored_namespace_rows != EXPECTED_ANCHORED["raw_namespace_rows"]:
        raise RuntimeError(
            f"Anchored namespace row drift: {anchored_namespace_rows}"
        )
    if len(valid) != EXPECTED_ANCHORED["valid_post_daily_cap_ballots"]:
        raise RuntimeError(f"Anchored valid-ballot drift: {len(valid)}")
    if excluded:
        raise RuntimeError(f"Unexpected anchored exclusions: {dict(excluded)}")

    for key in (
        "effective_votes",
        "distinct_voters",
        "distinct_challenges",
        "cells_observed",
        "cells_passing_both_gates",
        "minimum_cell_effective_votes",
        "minimum_cell_distinct_voters",
    ):
        if anchored[key] != EXPECTED_ANCHORED[key]:
            raise RuntimeError(
                f"Maturity anchor drift for {key}: "
                f"{anchored[key]} != {EXPECTED_ANCHORED[key]}"
            )

    checkpoint_rows = exact_checkpoint_prefix(valid, 600, lifetime_cap)
    if checkpoint_rows is None:
        raise RuntimeError("Exact 600-effective-vote checkpoint cannot be reconstructed")

    checkpoint = snapshot(
        checkpoint_rows, challenges, cells, lifetime_cap,
        min_voters, min_cell_effective, min_cell_voters,
    )
    for key, expected in EXPECTED_CHECKPOINT.items():
        if checkpoint[key] != expected:
            raise RuntimeError(
                f"Exact-600 drift for {key}: {checkpoint[key]} != {expected}"
            )
    assert checkpoint["coverage_gates_pass"] is True

    # Freeze the Phase 3F interpretation ladder BEFORE any A/B response or
    # randomized orientation token is interpreted. This does not alter any
    # existing threshold or candidate-selection rule; it only prevents an
    # unresolved two-candidate selection from being mislabeled as a failure of
    # the entire V4 architecture.
    interpretation_contract = {
        "schema_version": 1,
        "status": "FROZEN_BEFORE_V4_CONFIRMATION_UNBLINDING",
        "study_id": "package-adjustment-v4-elite-fragmentation",
        "phase": "3F-interpretation-contract",
        "frozen_before_human_outcomes_interpreted": True,
        "changes_existing_preregistered_thresholds": False,
        "changes_frozen_candidate_family": False,
        "production_change_authorized": False,
        "primary_metric": "5-fold voter-grouped held-out log loss",
        "candidate_selection_rule": {
            "rule": "lowest mean held-out log loss",
            "unresolved_if_best_vs_runner_up_gap_below": 0.002,
        },
        "deployment_gates": {
            "minimum_log_loss_improvement_vs_raw_control": 0.005,
            "challenge_cluster_bootstrap_favorable_fraction_vs_raw": 0.90,
            "maximum_topology_x_asset_mix_log_loss_regression_vs_raw": 0.03,
            "all_24_cells_coverage_required": True,
        },
        "interpretation_ladder": [
            {
                "case": "unique_candidate_selected_and_all_deployment_gates_pass",
                "meaning": "V4 has a unique production-candidate-eligible model.",
                "next_action": (
                    "Proceed to a separate deployment audit. Production is not automatic."
                ),
            },
            {
                "case": "unique_candidate_selected_but_any_deployment_gate_fails",
                "meaning": (
                    "V4 confirmation failed the preregistered production-candidate gates."
                ),
                "next_action": (
                    "Do not promote V4. Do not substitute the runner-up post hoc."
                ),
            },
            {
                "case": "candidate_selection_unresolved_gap_below_0_002_and_at_least_one_candidate_individually_clears_all_deployment_gates",
                "meaning": (
                    "The V4 architecture/family has confirmation evidence versus raw, "
                    "but the frozen study cannot uniquely identify which of the two "
                    "candidate parameterizations should represent it."
                ),
                "next_action": (
                    "No production promotion. Pre-register a new, fresh, candidate-"
                    "discrimination study restricted to the same two frozen candidates; "
                    "do not retune parameters against these 600 outcomes."
                ),
            },
            {
                "case": "candidate_selection_unresolved_gap_below_0_002_and_neither_candidate_individually_clears_all_deployment_gates",
                "meaning": (
                    "V4 did not establish a production-worthy candidate or family."
                ),
                "next_action": (
                    "Close V4 confirmation without production. Any later attempt must "
                    "start from a newly preregistered architecture/cycle."
                ),
            },
        ],
        "governance_note": (
            "An unresolved candidate-selection gap is not automatically equivalent "
            "to evidence that the V4 structural architecture has zero value. It blocks "
            "production until a unique candidate is established, while preserving the "
            "preregistered 0.002 selection threshold and every deployment gate."
        ),
    }
    INTERPRETATION_OUT.write_text(
        json.dumps(interpretation_contract, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # Only now reveal the frozen response/orientation tokens.
    voter_counts = Counter(r["voter"] for r in checkpoint_rows)
    frozen_weights = {
        voter: min(1.0, lifetime_cap / count)
        for voter, count in voter_counts.items()
    }

    voter_cluster_map = {}
    ballots = []
    source_commitment_rows = []

    for ordinal, row in enumerate(checkpoint_rows, start=1):
        voter = row["voter"]
        if voter not in voter_cluster_map:
            voter_cluster_map[voter] = f"v{len(voter_cluster_map)+1:02d}"

        payload = row["keep_raw"][len(VOTE_PREFIX):]
        challenge_id, sep, choice = payload.partition("|")
        if not sep or challenge_id != row["challenge_id"] or choice not in {"A", "B"}:
            raise RuntimeError(
                f"Invalid frozen response at source row {row['source_row_number']}"
            )

        display_left = row["trade_raw"][len(META_PREFIX):]
        if display_left not in {"A", "B"}:
            raise RuntimeError(
                f"Invalid display orientation at source row {row['source_row_number']}"
            )

        challenge = challenges[challenge_id]
        ballots.append({
            "ordinal": ordinal,
            "source_row_number": row["source_row_number"],
            "timestamp_utc": row["timestamp"].isoformat(),
            "voter_cluster": voter_cluster_map[voter],
            "challenge_id": challenge_id,
            "research_cell": challenge["research_cell"],
            "topology": challenge["topology"],
            "asset_mix": challenge["asset_mix"],
            "challenge_stratum": challenge["challenge_stratum"],
            "frozen_ballot_weight": float(frozen_weights[voter]),
            "human_choice": choice,
            "display_left": display_left,
            "canonical_a_displayed_left": display_left == "A",
        })

        source_commitment_rows.append({
            "source_index": row["source_index"],
            "timestamp_raw": row["timestamp_raw"],
            "voter": voter,
            "keep": row["keep_raw"],
            "trade": row["trade_raw"],
            "cut": row["cut_raw"],
        })

    assert len(ballots) == 600
    assert len(voter_cluster_map) == 31
    assert abs(sum(b["frozen_ballot_weight"] for b in ballots) - 600.0) < 1e-8

    commitment_bytes = json.dumps(
        source_commitment_rows,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    source_commitment_sha256 = hashlib.sha256(commitment_bytes).hexdigest()

    generated_at = datetime.now(timezone.utc)

    dataset = {
        "schema_version": 1,
        "status": "FROZEN_EXACT_600_CONFIRMATION_EVIDENCE",
        "study_id": "package-adjustment-v4-elite-fragmentation",
        "phase": "3E",
        "frozen": True,
        "research_only": True,
        "production_changed": False,
        "model_evaluation_performed": False,
        "checkpoint_selection_outcome_blind": True,
        "human_outcomes_revealed_only_after_checkpoint_selection": True,
        "checkpoint_effective_votes": 600,
        "valid_ballot_start_utc": cutoff.isoformat(),
        "maturity_anchor_utc": anchor.isoformat(),
        "raw_checkpoint_ballot_count": 600,
        "distinct_voter_clusters": 31,
        "frozen_effective_votes": 600.0,
        "ballots": ballots,
    }
    dataset_text = json.dumps(dataset, indent=2, sort_keys=True) + "\n"
    DATA_OUT.write_text(dataset_text, encoding="utf-8")
    dataset_sha256 = hashlib.sha256(dataset_text.encode()).hexdigest()

    manifest = {
        "schema_version": 1,
        "status": "FROZEN_EXACT_600_CONFIRMATION_EVIDENCE_MANIFEST",
        "study_id": "package-adjustment-v4-elite-fragmentation",
        "phase": "3E",
        "frozen": True,
        "research_only": True,
        "production_change_authorized": False,
        "production_revision_retained": "v1.6-v5-size2-composition-overlay",
        "model_evaluation_performed": False,
        "frozen_at_utc": generated_at.isoformat(),
        "github_source_commit": os.environ.get("GITHUB_SHA"),
        "maturity_anchor": {
            "status": "STOP_AND_FREEZE_AT_600",
            "run_id": MATURITY_RUN_ID,
            "job_id": MATURITY_JOB_ID,
            "generated_at_utc": MATURITY_ANCHOR_UTC,
            "source_sheet_sha256_at_monitor": MATURITY_SOURCE_SHEET_SHA256,
            "artifact_json_sha256": MATURITY_ARTIFACT_JSON_SHA256,
            "artifact_zip_sha256": MATURITY_ARTIFACT_ZIP_SHA256,
            "anchored_current": EXPECTED_ANCHORED,
            "exact_checkpoint": EXPECTED_CHECKPOINT,
        },
        "frozen_contract": {
            "preregistration": {
                "path": str(PREREG.relative_to(ROOT)),
                "git_blob_sha": git_blob(PREREG),
                "sha256": sha256_file(PREREG),
            },
            "candidate_family": {
                "path": str(FAMILY.relative_to(ROOT)),
                "git_blob_sha": git_blob(FAMILY),
                "sha256": sha256_file(FAMILY),
            },
            "catalog": {
                "path": str(CATALOG.relative_to(ROOT)),
                "git_blob_sha": git_blob(CATALOG),
                "sha256": sha256_file(CATALOG),
            },
            "catalog_manifest": {
                "path": str(CATALOG_MANIFEST.relative_to(ROOT)),
                "git_blob_sha": git_blob(CATALOG_MANIFEST),
                "sha256": sha256_file(CATALOG_MANIFEST),
            },
            "voting_release": {
                "path": str(RELEASE.relative_to(ROOT)),
                "git_blob_sha": git_blob(RELEASE),
                "sha256": sha256_file(RELEASE),
            },
        },
        "catalog_integrity": {
            "joe_mixon_occurrences": 0,
            "invalid_pick_year_occurrences": 0,
            "known_ktc_examples_in_selected_catalog": 0,
            "historical_trade_matches_in_selected_catalog": 0,
        },
        "source_sheet": {
            "sha256_at_freeze_fetch": sheet_sha256,
            "total_csv_data_rows_at_fetch": len(rows),
            "v4c1_namespace_rows_at_fetch": total_namespace_rows_at_fetch,
            "v4c1_rows_after_maturity_anchor_ignored": rows_after_anchor,
            "anchored_v4c1_namespace_rows": anchored_namespace_rows,
            "anchored_excluded_row_counts": dict(sorted(excluded.items())),
            "anchored_valid_post_daily_cap_ballots": len(valid),
            "frozen_checkpoint_source_commitment_sha256": source_commitment_sha256,
        },
        "checkpoint": checkpoint,
        "phase3f_interpretation_contract": {
            "path": str(INTERPRETATION_OUT.relative_to(ROOT)),
            "sha256": sha256_file(INTERPRETATION_OUT),
            "frozen_before_human_outcomes_interpreted": True,
            "changes_existing_preregistered_thresholds": False,
        },
        "dataset": {
            "path": str(DATA_OUT.relative_to(ROOT)),
            "sha256": dataset_sha256,
            "byte_length": len(dataset_text.encode()),
            "raw_ballot_count": 600,
            "effective_vote_count": 600.0,
            "voter_cluster_count": 31,
            "contains_human_choice": True,
            "contains_display_orientation": True,
            "contains_model_predictions": False,
            "contains_model_performance_statistics": False,
            "contains_raw_voter_identifiers": False,
        },
        "voting_closed_by_this_phase": True,
        "next_action": (
            "Run the separate one-time V4 confirmation evaluation against this "
            "immutable exact-600 dataset. Do not collect additional evidence "
            "for this V4 confirmation cycle."
        ),
    }
    MANIFEST_OUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = f"""# Package Adjustment V4 — Phase 3E Exact-600 Freeze

**Status:** `FROZEN_EXACT_600_CONFIRMATION_EVIDENCE`

- Frozen raw checkpoint ballots: **600**
- Frozen effective votes: **600.00**
- Distinct voter clusters: **31**
- Distinct challenges: **231 / 240**
- Cells passing both gates: **24 / 24**
- Weakest cell effective votes: **17.00**
- Weakest cell voter coverage: **13**
- Rows after the maturity anchor ignored: **{rows_after_anchor}**
- Joe Mixon occurrences in catalog: **0**
- 2029+ pick occurrences in catalog: **0**
- Production remains: `v1.6-v5-size2-composition-overlay`

## Governance

The successful Phase 3D monitor selected the exact 600 checkpoint without
reading A/B response direction or display orientation. This freeze reproduced
that checkpoint and every maturity gate before revealing the frozen response
tokens.

No model was fit, scored, compared, ranked, or selected here. Before any A/B
response token was interpreted, Phase 3E also froze the Phase 3F interpretation
ladder. In particular, a <0.002 two-candidate gap still blocks production, but
it is not automatically mislabeled as failure of the whole V4 architecture if
at least one frozen candidate independently clears every deployment gate.

Voting is closed after this freeze. The next step is the separate one-time V4
confirmation evaluation.
"""
    REPORT_OUT.write_text(report, encoding="utf-8")

    # Close browser voting only after the frozen evidence was written.
    close_voting_ui()
    patch_regression_contract()

    env_path = os.environ.get("GITHUB_ENV")
    if env_path:
        with open(env_path, "a", encoding="utf-8") as fh:
            fh.write(f"V4_PHASE3E_DATA_SHA256={dataset_sha256}\n")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report)

    print(report)
    print("V4_PHASE3E_STATUS=FROZEN_EXACT_600_CONFIRMATION_EVIDENCE")
    print("DATA_SHA256=" + dataset_sha256)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
    else:
        main()
