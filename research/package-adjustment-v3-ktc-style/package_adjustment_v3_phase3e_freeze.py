#!/usr/bin/env python3
"""Package Adjustment V3 Phase 3E — freeze exact 600 confirmation ballots.

This script reconstructs the exact preregistered 600-effective-vote checkpoint
from the live vote sheet, verifies the outcome-blind maturity anchor, then
reveals only the frozen checkpoint's response/orientation tokens needed for the
later one-time evaluation.

It does not fit, score, compare, rank, or select any model.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "research" / "package-adjustment-v3-ktc-style"

PREREG = D / "phase3_confirmation_preregistration.json"
CATALOG = D / "phase3_confirmation_catalog.json"
CATALOG_MANIFEST = D / "phase3_confirmation_catalog_manifest.json"
RELEASE = D / "phase3_voting_release.json"
PHASE3B = D / "package_adjustment_v3_phase3b.py"

DATA_OUT = D / "phase3_exact_600_frozen.json"
MANIFEST_OUT = D / "phase3_exact_600_freeze_manifest.json"
REPORT_OUT = Path("/tmp/package-adjustment-v3-phase3e-freeze-report.md")

SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vTuKORGumlKJmUmBdeNWPstkj8VRjPoVkylbqHv1KqwoyziJYOUlkZUKRsSxzB3qHXmyjjLpGpH6W03/"
    "pub?gid=458294959&single=true&output=csv"
)

# Immutable successful outcome-blind Phase 3D maturity anchor.
MATURITY_ANCHOR_UTC = "2026-09-19T18:35:33.806650+00:00"
MATURITY_ARTIFACT_JSON_SHA256 = (
    "16a6b42cd4c0000b406551cd7336ae6ab488a0f726e683c9669ef6818a425e2b"
)
MATURITY_ARTIFACT_ZIP_SHA256 = (
    "6158ef4f453e793e7babd1710a4fda3868cb598824688c70a40420c1add7d96d"
)
MATURITY_SOURCE_SHEET_SHA256 = (
    "65ceee98cf3f43c5d55110fd34244176af0dce53eb7d9a2fd34a8de2d8c2e8e9"
)

EXPECTED_ANCHORED = {
    "raw_namespace_rows": 620,
    "valid_post_daily_cap_ballots": 620,
    "effective_votes": 620.0,
    "distinct_voters": 31,
    "distinct_challenges": 219,
    "cells_observed": 24,
    "cells_passing_both_gates": 24,
    "minimum_cell_effective_votes": 18.0,
    "minimum_cell_distinct_voters": 14,
}

EXPECTED_CHECKPOINT = {
    "effective_votes": 600.0,
    "raw_post_daily_cap_ballots": 600,
    "distinct_voters": 30,
    "distinct_challenges": 218,
    "cells_observed": 24,
    "cells_passing_both_gates": 24,
    "minimum_cell_effective_votes": 17.0,
    "minimum_cell_distinct_voters": 13,
}

VOTE_PREFIX = "__pkgv3c1__|"
META_PREFIX = "__pkgv3c1_meta__|"
SCHEMA_MARKER = "__pkgv3c1_schema__|1"

# Corrected development examples from the five supplied KTC screenshots.
# These are used ONLY to independently prove the frozen catalog did not contain
# a development example. No screenshot outcome/value is used in evaluation.
CORRECT_KTC_EXAMPLES = [
    (
        frozenset(["jahmyr gibbs"]),
        frozenset(["devon achane", "tee higgins"]),
    ),
    (
        frozenset(["ceedee lamb", "sam laporta"]),
        frozenset(["rome odunze", "saquon barkley"]),
    ),
    (
        frozenset(["george pickens", "marshawn lloyd"]),
        frozenset(["isaiah likely", "ryan flournoy", "rico dowdle"]),
    ),
    (
        frozenset(["josh allen"]),
        frozenset(["caleb williams", "saquon barkley"]),
    ),
    (
        frozenset(["george pickens", "kaelon black"]),
        frozenset(["jayden reed", "parker washington", "jonathon brooks"]),
    ),
]


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


def normalize_name(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_bytes(data: bytes) -> str:
    return hashlib.sha1(
        f"blob {len(data)}\0".encode("utf-8") + data
    ).hexdigest()


def side_name_set(side):
    return frozenset(normalize_name(a.get("name")) for a in side)


def catalog_matches_corrected_ktc_examples(catalog_doc):
    matches = []
    for idx, (known_a, known_b) in enumerate(CORRECT_KTC_EXAMPLES, start=1):
        found = []
        for challenge in catalog_doc["challenges"]:
            ca = side_name_set(challenge["side_a"])
            cb = side_name_set(challenge["side_b"])
            if (ca == known_a and cb == known_b) or (ca == known_b and cb == known_a):
                found.append(challenge["id"])
        matches.append({"example_number": idx, "selected_challenge_ids": found})
    return matches


def selftest():
    # Exact-checkpoint arithmetic.
    rows = []
    for voter in range(30):
        for day, n in (("2026-09-19", 20), ("2026-09-20", 10)):
            for i in range(n):
                rows.append({"voter": f"v{voter}", "day": day, "i": i})

    daily_counts = Counter()
    valid = []
    for row in rows:
        k = (row["voter"], row["day"])
        if daily_counts[k] >= 20:
            continue
        daily_counts[k] += 1
        valid.append(row)

    assert len(valid) == 900
    counts = Counter()
    running = 0
    hits = {}
    for idx, row in enumerate(valid):
        voter = row["voter"]
        before = min(counts[voter], 30)
        counts[voter] += 1
        after = min(counts[voter], 30)
        running += after - before
        if running in (600, 700, 800) and running not in hits:
            hits[running] = idx + 1
    assert set(hits) == {600, 700, 800}

    # Side-orientation independent exact-example matching.
    fake = {
        "challenges": [
            {
                "id": "x",
                "side_a": [{"name": "Parker Washington"}, {"name": "Jayden Reed"}, {"name": "Jonathon Brooks"}],
                "side_b": [{"name": "George Pickens"}, {"name": "Kaelon Black"}],
            }
        ]
    }
    m = catalog_matches_corrected_ktc_examples(fake)
    assert m[4]["selected_challenge_ids"] == ["x"]
    assert all(not row["selected_challenge_ids"] for row in m[:4])

    print("Package Adjustment V3 Phase 3E freeze self-test PASS")


def main():
    if DATA_OUT.exists() or MANIFEST_OUT.exists():
        raise RuntimeError("Phase 3E exact-600 freeze already exists; refusing overwrite")

    cfg = json.loads(PREREG.read_text(encoding="utf-8"))
    catalog_doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog_manifest = json.loads(CATALOG_MANIFEST.read_text(encoding="utf-8"))
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    phase3b_text = PHASE3B.read_text(encoding="utf-8")

    assert cfg["status"] == "FROZEN_FRESH_CONFIRMATION_PREREGISTRATION"
    assert cfg["frozen"] is True
    assert cfg["production_change_authorized"] is False
    assert cfg["production_revision_must_remain"] == "v1.6-v5-size2-composition-overlay"

    rules = cfg["collection_and_maturity"]
    assert rules["outcome_blind_until_exact_checkpoint_freeze"] is True
    assert rules["exact_effective_vote_checkpoints"] == [600, 700, 800]
    assert rules["first_checkpoint"] == 600
    assert rules["hard_cap"] == 800
    assert rules["daily_valid_vote_cap_per_voter"] == 20
    assert rules["effective_lifetime_vote_cap_per_voter"] == 30
    assert rules["minimum_distinct_voters"] == 30
    assert rules["minimum_effective_votes_per_cell"] == 15
    assert rules["minimum_distinct_voters_per_cell"] == 10
    assert rules["required_cell_count"] == 24

    assert release["status"] == "FRESH_CONFIRMATION_VOTING_ACTIVE"
    assert release["vote_namespace"] == "__pkgv3c1__"
    assert release["vote_meta_namespace"] == "__pkgv3c1_meta__"
    assert release["vote_schema_marker"] == SCHEMA_MARKER
    assert release["catalog_challenge_count"] == 240
    assert release["research_cell_count"] == 24
    assert release["production_change_authorized"] is False

    assert catalog_doc["status"] == "frozen_unreleased_fresh_confirmation_catalog"
    assert catalog_doc["frozen"] is True
    assert catalog_doc["released"] is False
    assert catalog_doc["voting_activated"] is False
    assert len(catalog_doc["challenges"]) == 240
    assert catalog_manifest["catalog_sha256"] == release["catalog_sha256"]
    assert (
        catalog_manifest["catalog_fingerprint_sha256"]
        == release["catalog_fingerprint_sha256"]
    )

    # Pre-unblinding provenance exception audit.
    # The Phase 3B source typo is real, but the actual frozen catalog is clean.
    assert '"mike washington"' in phase3b_text
    corrected_matches = catalog_matches_corrected_ktc_examples(catalog_doc)
    if any(row["selected_challenge_ids"] for row in corrected_matches):
        raise RuntimeError(
            "Corrected KTC development-example audit found contamination in frozen catalog"
        )

    challenges = {c["id"]: c for c in catalog_doc["challenges"]}
    assert len(challenges) == 240
    cells = sorted({c["research_cell"] for c in challenges.values()})
    assert cells == sorted(cfg["catalog_design"]["research_cells"])

    cutoff = parse_utc(release["valid_after_utc"])
    maturity_anchor = parse_utc(MATURITY_ANCHOR_UTC)
    assert cutoff is not None and maturity_anchor is not None
    assert maturity_anchor > cutoff

    generated_at = datetime.now(timezone.utc)

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

    required_columns = {"timestamp", "voter_roster_id", "keep", "trade", "cut"}
    missing = required_columns - set(rows[0].keys())
    if missing:
        raise RuntimeError(f"Sheet missing required columns: {sorted(missing)}")

    total_namespace_rows_at_fetch = 0
    anchored_namespace_rows = 0
    rows_after_anchor = 0
    excluded = Counter()
    structurally_valid = []

    # Outcome-blind checkpoint eligibility reconstruction. Choice/orientation
    # suffixes are preserved opaquely but are not interpreted here.
    for source_index, row in enumerate(rows):
        keep = str(row.get("keep") or "")
        if not keep.startswith(VOTE_PREFIX):
            continue
        total_namespace_rows_at_fetch += 1

        ts = parse_utc(row.get("timestamp"))
        if ts is None:
            raise RuntimeError(
                f"V3C1 row has invalid timestamp at CSV row {source_index + 2}"
            )
        if ts > maturity_anchor:
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

        structurally_valid.append(
            {
                "timestamp": ts,
                "timestamp_raw": str(row.get("timestamp") or ""),
                "source_index": source_index,
                "source_row_number": source_index + 2,
                "voter": voter,
                "challenge_id": challenge_id,
                "keep_raw": keep,
                "trade_raw": trade,
                "cut_raw": cut,
            }
        )

    structurally_valid.sort(key=lambda r: (r["timestamp"], r["source_index"]))

    DAILY_CAP = int(rules["daily_valid_vote_cap_per_voter"])
    LIFETIME_CAP = int(rules["effective_lifetime_vote_cap_per_voter"])
    MIN_VOTERS = int(rules["minimum_distinct_voters"])
    MIN_CELL_EFFECTIVE = float(rules["minimum_effective_votes_per_cell"])
    MIN_CELL_VOTERS = int(rules["minimum_distinct_voters_per_cell"])

    daily_counts = Counter()
    valid = []
    for row in structurally_valid:
        day = row["timestamp"].date().isoformat()
        key = (row["voter"], day)
        if daily_counts[key] >= DAILY_CAP:
            excluded["daily_cap_excess"] += 1
            continue
        daily_counts[key] += 1
        valid.append(row)

    def snapshot(rows_subset):
        voter_counts = Counter(r["voter"] for r in rows_subset)
        weights = {
            voter: min(1.0, LIFETIME_CAP / count)
            for voter, count in voter_counts.items()
        }
        per_cell_effective = {cell: 0.0 for cell in cells}
        per_cell_voters = {cell: set() for cell in cells}
        challenge_ids = set()

        for row in rows_subset:
            cell = challenges[row["challenge_id"]]["research_cell"]
            per_cell_effective[cell] += weights[row["voter"]]
            per_cell_voters[cell].add(row["voter"])
            challenge_ids.add(row["challenge_id"])

        cell_rows = []
        for cell in cells:
            eff = per_cell_effective[cell]
            voters = len(per_cell_voters[cell])
            topology, mix, band = cell.split("|")
            cell_rows.append(
                {
                    "research_cell": cell,
                    "topology": topology,
                    "asset_mix": mix,
                    "disagreement_band": band,
                    "effective_votes": round(float(eff), 6),
                    "distinct_voters": voters,
                    "cell_gate_pass": (
                        eff + 1e-12 >= MIN_CELL_EFFECTIVE
                        and voters >= MIN_CELL_VOTERS
                    ),
                }
            )

        effective_total = sum(
            min(count, LIFETIME_CAP) for count in voter_counts.values()
        )
        return {
            "raw_post_daily_cap_ballots": len(rows_subset),
            "effective_votes": round(float(effective_total), 6),
            "distinct_voters": len(voter_counts),
            "distinct_challenges": len(challenge_ids),
            "cells_observed": sum(c["effective_votes"] > 0 for c in cell_rows),
            "cells_passing_both_gates": sum(c["cell_gate_pass"] for c in cell_rows),
            "minimum_cell_effective_votes": round(
                min(c["effective_votes"] for c in cell_rows), 6
            ),
            "minimum_cell_distinct_voters": min(
                c["distinct_voters"] for c in cell_rows
            ),
            "coverage_gates_pass": (
                len(voter_counts) >= MIN_VOTERS
                and all(c["cell_gate_pass"] for c in cell_rows)
            ),
            "cells": cell_rows,
        }

    def exact_checkpoint_prefix(threshold):
        counts = Counter()
        running = 0
        for idx, row in enumerate(valid):
            voter = row["voter"]
            before = min(counts[voter], LIFETIME_CAP)
            counts[voter] += 1
            after = min(counts[voter], LIFETIME_CAP)
            running += after - before
            if running == threshold:
                return valid[: idx + 1]
            if running > threshold:
                raise RuntimeError(
                    f"Effective count skipped exact checkpoint {threshold}"
                )
        return None

    anchored_current = snapshot(valid)
    assert anchored_namespace_rows == EXPECTED_ANCHORED["raw_namespace_rows"]
    assert len(valid) == EXPECTED_ANCHORED["valid_post_daily_cap_ballots"]
    assert excluded == Counter(), dict(excluded)
    for key in (
        "effective_votes",
        "distinct_voters",
        "distinct_challenges",
        "cells_observed",
        "cells_passing_both_gates",
        "minimum_cell_effective_votes",
        "minimum_cell_distinct_voters",
    ):
        assert anchored_current[key] == EXPECTED_ANCHORED[key], (
            key, anchored_current[key], EXPECTED_ANCHORED[key]
        )

    checkpoint_rows = exact_checkpoint_prefix(600)
    if checkpoint_rows is None:
        raise RuntimeError("Exact 600-effective-vote checkpoint cannot be reconstructed")

    checkpoint = snapshot(checkpoint_rows)
    for key, expected in EXPECTED_CHECKPOINT.items():
        assert checkpoint[key] == expected, (key, checkpoint[key], expected)
    assert checkpoint["coverage_gates_pass"] is True

    # Only after exact checkpoint selection and maturity reproduction pass do we
    # interpret frozen human response and randomized orientation tokens.
    voter_counts = Counter(r["voter"] for r in checkpoint_rows)
    frozen_weights = {
        voter: min(1.0, LIFETIME_CAP / count)
        for voter, count in voter_counts.items()
    }

    voter_cluster_map = {}
    ballots = []
    source_commitment_rows = []

    for ordinal, row in enumerate(checkpoint_rows, start=1):
        voter = row["voter"]
        if voter not in voter_cluster_map:
            voter_cluster_map[voter] = f"v{len(voter_cluster_map) + 1:02d}"

        payload = row["keep_raw"][len(VOTE_PREFIX):]
        challenge_id, sep, choice = payload.partition("|")
        if (
            not sep
            or challenge_id != row["challenge_id"]
            or choice not in {"A", "B"}
        ):
            raise RuntimeError(
                f"Invalid frozen response token at source row {row['source_row_number']}"
            )

        display_left = row["trade_raw"][len(META_PREFIX):]
        if display_left not in {"A", "B"}:
            raise RuntimeError(
                f"Invalid frozen display orientation at source row {row['source_row_number']}"
            )

        challenge = challenges[challenge_id]
        ballots.append(
            {
                "ordinal": ordinal,
                "source_row_number": row["source_row_number"],
                "timestamp_utc": row["timestamp"].isoformat(),
                "voter_cluster": voter_cluster_map[voter],
                "challenge_id": challenge_id,
                "research_cell": challenge["research_cell"],
                "topology": challenge["topology"],
                "asset_mix": challenge["asset_mix"],
                "disagreement_band": challenge["disagreement_band"],
                "frozen_ballot_weight": float(frozen_weights[voter]),
                "human_choice": choice,
                "display_left": display_left,
                "canonical_a_displayed_left": display_left == "A",
            }
        )

        source_commitment_rows.append(
            {
                "source_index": row["source_index"],
                "timestamp_raw": row["timestamp_raw"],
                "voter": voter,
                "keep": row["keep_raw"],
                "trade": row["trade_raw"],
                "cut": row["cut_raw"],
            }
        )

    assert len(voter_cluster_map) == 30
    assert len(ballots) == 600
    assert abs(sum(b["frozen_ballot_weight"] for b in ballots) - 600.0) < 1e-8

    source_commitment_bytes = json.dumps(
        source_commitment_rows,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    source_commitment_sha256 = hashlib.sha256(source_commitment_bytes).hexdigest()

    dataset = {
        "schema_version": 1,
        "status": "FROZEN_EXACT_600_CONFIRMATION_EVIDENCE",
        "study_id": "package-adjustment-v3-ktc-style",
        "phase": "3E",
        "frozen": True,
        "research_only": True,
        "production_changed": False,
        "model_evaluation_performed": False,
        "checkpoint_selection_outcome_blind": True,
        "human_outcomes_revealed_only_after_checkpoint_selection": True,
        "checkpoint_effective_votes": 600,
        "valid_ballot_start_utc": cutoff.isoformat(),
        "maturity_anchor_utc": maturity_anchor.isoformat(),
        "ballot_weight_rule": rules["ballot_weight_rule"],
        "raw_checkpoint_ballot_count": len(ballots),
        "distinct_voter_clusters": len(voter_cluster_map),
        "frozen_effective_votes": 600.0,
        "ballots": ballots,
    }
    dataset_text = json.dumps(dataset, indent=2, sort_keys=True) + "\n"
    DATA_OUT.write_text(dataset_text, encoding="utf-8")
    dataset_sha256 = hashlib.sha256(dataset_text.encode("utf-8")).hexdigest()

    provenance_exception = {
        "phase3b_generator_source_contains_typo": True,
        "incorrect_generator_name": "mike washington",
        "intended_name": "parker washington",
        "affected_development_example_number": 5,
        "corrected_independent_catalog_audit_performed_before_model_evaluation": True,
        "corrected_five_ktc_exact_selected_matches": [
            len(row["selected_challenge_ids"]) for row in corrected_matches
        ],
        "corrected_five_ktc_all_absent_from_frozen_catalog": True,
        "catalog_regenerated_after_voting": False,
        "scientific_impact": (
            "No known KTC development example entered the frozen 240-challenge "
            "confirmation catalog. The typo is preserved as provenance and the "
            "post-vote catalog is not regenerated."
        ),
    }

    manifest = {
        "schema_version": 1,
        "status": "FROZEN_EXACT_600_CONFIRMATION_EVIDENCE_MANIFEST",
        "study_id": "package-adjustment-v3-ktc-style",
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
            "generated_at_utc": MATURITY_ANCHOR_UTC,
            "artifact_json_sha256": MATURITY_ARTIFACT_JSON_SHA256,
            "artifact_zip_sha256": MATURITY_ARTIFACT_ZIP_SHA256,
            "source_sheet_sha256_at_monitor": MATURITY_SOURCE_SHEET_SHA256,
            "anchored_current": EXPECTED_ANCHORED,
            "exact_checkpoint": EXPECTED_CHECKPOINT,
        },
        "frozen_contract": {
            "preregistration": {
                "path": str(PREREG.relative_to(ROOT)),
                "git_blob_sha": "19966121899d41bdbc754a6a260758cf175b12e2",
                "sha256": sha256_file(PREREG),
            },
            "catalog": {
                "path": str(CATALOG.relative_to(ROOT)),
                "git_blob_sha": "3d4615e590697341ee8c27785d8b22e16b82ac44",
                "sha256": sha256_file(CATALOG),
            },
            "catalog_manifest": {
                "path": str(CATALOG_MANIFEST.relative_to(ROOT)),
                "git_blob_sha": "6ecd25f01b758a5ea5bd69f513f775c55fc84d4c",
                "sha256": sha256_file(CATALOG_MANIFEST),
            },
            "voting_release": {
                "path": str(RELEASE.relative_to(ROOT)),
                "git_blob_sha": "ae62546cbff5974d895cf43931819b15e7c3a222",
                "sha256": sha256_file(RELEASE),
            },
            "phase3b_generator": {
                "path": str(PHASE3B.relative_to(ROOT)),
                "git_blob_sha": "4356e8b5af591cbd9cf5ed7d2af3ca2077e2bf91",
                "sha256": sha256_file(PHASE3B),
            },
        },
        "pre_unblinding_provenance_exception": provenance_exception,
        "source_sheet": {
            "sha256_at_freeze_fetch": sheet_sha256,
            "total_csv_data_rows_at_fetch": len(rows),
            "v3c1_namespace_rows_at_fetch": total_namespace_rows_at_fetch,
            "v3c1_rows_after_maturity_anchor_ignored": rows_after_anchor,
            "anchored_v3c1_namespace_rows": anchored_namespace_rows,
            "anchored_excluded_row_counts": dict(sorted(excluded.items())),
            "anchored_valid_post_daily_cap_ballots": len(valid),
            "frozen_checkpoint_source_commitment_sha256": source_commitment_sha256,
        },
        "checkpoint": checkpoint,
        "dataset": {
            "path": str(DATA_OUT.relative_to(ROOT)),
            "sha256": dataset_sha256,
            "byte_length": len(dataset_text.encode("utf-8")),
            "raw_ballot_count": len(ballots),
            "effective_vote_count": 600.0,
            "voter_cluster_count": len(voter_cluster_map),
            "contains_human_choice": True,
            "contains_display_orientation": True,
            "contains_model_predictions": False,
            "contains_model_performance_statistics": False,
            "contains_raw_voter_identifiers": False,
        },
        "next_action": (
            "Run the separate preregistered one-time Phase 3F evaluation against "
            "this immutable exact-600 dataset. Do not collect additional evidence "
            "for this confirmation cycle."
        ),
    }
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    MANIFEST_OUT.write_text(manifest_text, encoding="utf-8")
    manifest_sha256 = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()

    report = f"""# Package Adjustment V3 — Phase 3E Exact-600 Freeze

**Status:** `FROZEN_EXACT_600_CONFIRMATION_EVIDENCE`

- Maturity anchor: `{MATURITY_ANCHOR_UTC}`
- Frozen raw checkpoint ballots: **600**
- Frozen effective votes: **600.00**
- Distinct voter clusters: **30**
- Distinct challenges: **{checkpoint['distinct_challenges']} / 240**
- Cells passing both gates: **24 / 24**
- Weakest cell effective votes: **{checkpoint['minimum_cell_effective_votes']:.2f}**
- Weakest cell voter coverage: **{checkpoint['minimum_cell_distinct_voters']}**
- Post-checkpoint anchored valid ballots excluded: **{len(valid) - len(checkpoint_rows)}**
- Later rows after maturity anchor ignored: **{rows_after_anchor}**
- Production remains: `v1.6-v5-size2-composition-overlay`

## Pre-unblinding provenance exception

The committed Phase 3B generator contains `mike washington` in the fifth
development-example exclusion signature where `parker washington` was intended.
Before any model evaluation, the frozen 240-challenge catalog was independently
re-audited using the corrected five exact KTC examples.

**Corrected exact matches in selected catalog: 0 / 5.**

Therefore no known KTC development example contaminated the confirmation catalog.
The already-voted catalog was deliberately **not regenerated**.

## Governance

Checkpoint selection was reproduced outcome-blind before response/orientation
tokens were interpreted. No candidate prediction, loss, ranking, selection, or
production decision was computed by this freeze.

Next: one-time preregistered Phase 3F evaluation of the immutable exact-600 dataset.
"""
    REPORT_OUT.write_text(report, encoding="utf-8")

    env_path = os.environ.get("GITHUB_ENV")
    if env_path:
        with open(env_path, "a", encoding="utf-8") as fh:
            fh.write(f"PHASE3E_DATA_SHA256={dataset_sha256}\n")
            fh.write(f"PHASE3E_MANIFEST_SHA256={manifest_sha256}\n")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(report)

    print(report)
    print("PHASE3E_STATUS=FROZEN_EXACT_600_CONFIRMATION_EVIDENCE")
    print("DATA_SHA256=" + dataset_sha256)
    print("MANIFEST_SHA256=" + manifest_sha256)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
    else:
        main()
