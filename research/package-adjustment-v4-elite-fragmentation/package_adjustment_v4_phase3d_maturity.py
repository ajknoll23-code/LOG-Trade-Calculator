#!/usr/bin/env python3
"""Package Adjustment V4 Phase 3D — outcome-blind maturity monitor.

Reads only V4C1 namespace membership, timestamp, voter identity, and challenge
ID. It deliberately does not parse A/B response direction, randomized display
orientation, candidate predictions, losses, or winners.

Repository is read-only. Aggregate-only maturity artifacts are written to /tmp.
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

SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vTuKORGumlKJmUmBdeNWPstkj8VRjPoVkylbqHv1KqwoyziJYOUlkZUKRsSxzB3qHXmyjjLpGpH6W03/"
    "pub?gid=458294959&single=true&output=csv"
)

OUT_DIR = Path("/tmp/package-adjustment-v4-phase3d-maturity")
OUT_JSON = OUT_DIR / "phase3d_maturity.json"
OUT_MD = OUT_DIR / "phase3d_maturity.md"


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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def selftest():
    daily_cap = 20
    lifetime_cap = 30
    rows = []

    for voter in range(30):
        for i in range(20):
            rows.append({
                "voter": f"v{voter}",
                "timestamp": datetime(2026, 9, 20, 12, i, tzinfo=timezone.utc),
                "source_index": len(rows),
                "challenge_id": f"c{voter % 24}",
            })
        for i in range(10):
            rows.append({
                "voter": f"v{voter}",
                "timestamp": datetime(2026, 9, 21, 12, i, tzinfo=timezone.utc),
                "source_index": len(rows),
                "challenge_id": f"c{voter % 24}",
            })

    daily_counts = Counter()
    valid = []
    for row in rows:
        key = (row["voter"], row["timestamp"].date().isoformat())
        if daily_counts[key] >= daily_cap:
            continue
        daily_counts[key] += 1
        valid.append(row)

    assert len(valid) == 900

    voter_counts = Counter(r["voter"] for r in valid)
    assert sum(min(n, lifetime_cap) for n in voter_counts.values()) == 900

    running_counts = Counter()
    running = 0
    hit = set()
    for row in valid:
        voter = row["voter"]
        before = min(running_counts[voter], lifetime_cap)
        running_counts[voter] += 1
        after = min(running_counts[voter], lifetime_cap)
        running += after - before
        if running in (600, 700, 800):
            hit.add(running)

    assert hit == {600, 700, 800}
    print("Package Adjustment V4 Phase 3D maturity self-test PASS")


def main():
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
    assert contract["research_cell_design"] == "6 topologies x 2 asset mixes x 2 strata = 24 cells"
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
    assert release["vote_schema_marker"] == "__pkgv4c1_schema__|1"
    assert release["catalog_challenge_count"] == 240
    assert release["research_cell_count"] == 24
    assert release["challenges_per_cell"] == 10
    assert release["targeted_challenge_count"] == 120
    assert release["broad_balanced_challenge_count"] == 120
    assert release["joe_mixon_excluded"] is True
    assert release["pick_years_allowed"] == [2027, 2028]
    assert release["old_v3_600_vote_rows_count_for_this_study"] is False
    assert release["old_nextgen_900_vote_rows_count_for_this_study"] is False
    assert release["production_change_authorized"] is False

    assert catalog_doc["status"] == "frozen_unreleased_fresh_confirmation_catalog"
    assert len(catalog_doc["challenges"]) == 240
    assert catalog_doc["catalog_diagnostics"]["research_cell_count"] == 24
    assert catalog_doc["catalog_diagnostics"]["joe_mixon_occurrences"] == 0
    assert catalog_doc["catalog_diagnostics"]["invalid_pick_year_occurrences"] == 0
    assert catalog_manifest["outputs"]["catalog"]["sha256"] == release["catalog_sha256"]

    challenges = {c["id"]: c for c in catalog_doc["challenges"]}
    assert len(challenges) == 240

    all_cells = sorted({c["research_cell"] for c in challenges.values()})
    assert len(all_cells) == 24

    cutoff = parse_utc(release["valid_after_utc"])
    assert cutoff is not None

    daily_cap = int(maturity["daily_valid_vote_cap_per_voter"])
    lifetime_cap = int(maturity["effective_lifetime_vote_cap_per_voter"])
    min_voters = int(maturity["minimum_distinct_voters"])
    min_cell_effective = float(maturity["minimum_effective_votes_per_cell"])
    min_cell_voters = int(maturity["minimum_distinct_voters_per_cell"])
    checkpoints = list(maturity["exact_effective_vote_checkpoints"])
    hard_cap = max(checkpoints)

    vote_prefix = "__pkgv4c1__|"
    meta_prefix = "__pkgv4c1_meta__|"
    schema_marker = "__pkgv4c1_schema__|1"

    generated_at = datetime.now(timezone.utc)

    resp = requests.get(SHEET_URL, timeout=30)
    resp.raise_for_status()
    sheet_sha256 = sha256_bytes(resp.content)
    sheet_rows = list(csv.DictReader(io.StringIO(resp.text)))

    excluded = Counter()
    raw_namespace_rows = 0
    structurally_valid = []

    for source_index, row in enumerate(sheet_rows):
        keep = str(row.get("keep") or "")
        if not keep.startswith(vote_prefix):
            continue

        raw_namespace_rows += 1

        ts = parse_utc(row.get("timestamp"))
        if ts is None:
            excluded["invalid_timestamp"] += 1
            continue
        if ts <= cutoff:
            excluded["pre_cutoff_or_at_cutoff"] += 1
            continue
        if ts > generated_at:
            excluded["future_timestamp"] += 1
            continue

        voter = str(row.get("voter_roster_id") or "").strip()
        if not voter:
            excluded["missing_voter_id"] += 1
            continue

        # Outcome-blind: isolate only challenge ID. Never parse A/B choice.
        payload = keep[len(vote_prefix):]
        sep = payload.find("|")
        if sep <= 0:
            excluded["malformed_vote_transport"] += 1
            continue
        challenge_id = payload[:sep].strip()
        if challenge_id not in challenges:
            excluded["unknown_challenge_id"] += 1
            continue

        # Validate namespace only. Never parse randomized left/right token.
        meta = str(row.get("trade") or "")
        if not meta.startswith(meta_prefix):
            excluded["invalid_meta_namespace"] += 1
            continue
        if str(row.get("cut") or "") != schema_marker:
            excluded["invalid_schema_marker"] += 1
            continue

        structurally_valid.append({
            "timestamp": ts,
            "source_index": source_index,
            "voter": voter,
            "challenge_id": challenge_id,
        })

    structurally_valid.sort(key=lambda r: (r["timestamp"], r["source_index"]))

    daily_counts = Counter()
    valid = []
    for row in structurally_valid:
        day = row["timestamp"].date().isoformat()
        key = (row["voter"], day)
        if daily_counts[key] >= daily_cap:
            excluded["daily_cap_excess"] += 1
            continue
        daily_counts[key] += 1
        valid.append(row)

    def snapshot(rows_subset):
        voter_counts = Counter(r["voter"] for r in rows_subset)
        weights = {
            voter: min(1.0, lifetime_cap / count)
            for voter, count in voter_counts.items()
        }

        per_cell_effective = {cell: 0.0 for cell in all_cells}
        per_cell_voters = {cell: set() for cell in all_cells}
        observed_challenges = set()

        for row in rows_subset:
            challenge = challenges[row["challenge_id"]]
            cell = challenge["research_cell"]
            per_cell_effective[cell] += weights[row["voter"]]
            per_cell_voters[cell].add(row["voter"])
            observed_challenges.add(row["challenge_id"])

        effective_total = sum(min(count, lifetime_cap) for count in voter_counts.values())

        cells = []
        for cell in all_cells:
            eff = per_cell_effective[cell]
            voters = len(per_cell_voters[cell])
            parts = cell.split("|")
            if len(parts) != 3:
                raise RuntimeError(f"Unexpected V4 research cell: {cell}")

            cells.append({
                "research_cell": cell,
                "topology": parts[0],
                "asset_mix": parts[1],
                "challenge_stratum": parts[2],
                "effective_votes": round(eff, 6),
                "distinct_voters": voters,
                "effective_vote_gate_pass": eff + 1e-12 >= min_cell_effective,
                "voter_gate_pass": voters >= min_cell_voters,
                "cell_gate_pass": (
                    eff + 1e-12 >= min_cell_effective
                    and voters >= min_cell_voters
                ),
            })

        distinct_voters = len(voter_counts)
        coverage_pass = (
            distinct_voters >= min_voters
            and all(c["cell_gate_pass"] for c in cells)
        )

        return {
            "raw_post_daily_cap_ballots": len(rows_subset),
            "effective_votes": round(float(effective_total), 6),
            "distinct_voters": distinct_voters,
            "distinct_challenges": len(observed_challenges),
            "cells_observed": sum(c["effective_votes"] > 0 for c in cells),
            "cells_passing_both_gates": sum(c["cell_gate_pass"] for c in cells),
            "minimum_cell_effective_votes": round(
                min(c["effective_votes"] for c in cells), 6
            ),
            "minimum_cell_distinct_voters": min(
                c["distinct_voters"] for c in cells
            ),
            "coverage_gates_pass": coverage_pass,
            "cells": cells,
        }

    def exact_checkpoint_prefix(threshold):
        counts = Counter()
        running = 0

        for index, row in enumerate(valid):
            voter = row["voter"]
            before = min(counts[voter], lifetime_cap)
            counts[voter] += 1
            after = min(counts[voter], lifetime_cap)
            running += after - before

            if running == threshold:
                return valid[: index + 1]
            if running > threshold:
                raise RuntimeError(
                    f"Effective count skipped exact checkpoint {threshold}"
                )
        return None

    current = snapshot(valid)
    checkpoint_reports = {}
    for checkpoint in checkpoints:
        prefix = exact_checkpoint_prefix(checkpoint)
        checkpoint_reports[str(checkpoint)] = (
            None if prefix is None else snapshot(prefix)
        )

    cp600 = checkpoint_reports["600"]
    cp700 = checkpoint_reports["700"]
    cp800 = checkpoint_reports["800"]

    if cp600 is not None and cp600["coverage_gates_pass"]:
        status = "STOP_AND_FREEZE_AT_600"
        stop_checkpoint = 600
        next_action = (
            "Stop collecting. Freeze the exact 600-effective-vote checkpoint "
            "before any candidate evaluation."
        )
    elif cp700 is not None and cp700["coverage_gates_pass"]:
        status = "STOP_AND_FREEZE_AT_700"
        stop_checkpoint = 700
        next_action = (
            "The exact 600 checkpoint did not qualify, but 700 did. Stop "
            "collecting and freeze the exact 700-effective-vote checkpoint."
        )
    elif cp800 is not None:
        stop_checkpoint = 800
        if cp800["coverage_gates_pass"]:
            status = "STOP_AND_FREEZE_AT_800"
            next_action = (
                "Earlier checkpoints did not qualify. Stop collecting and "
                "freeze the exact 800-effective-vote hard-cap checkpoint."
            )
        else:
            status = "STOP_UNRESOLVED_AT_HARD_CAP_800"
            next_action = (
                "Stop collecting. The 800-effective-vote hard cap was reached "
                "without every frozen coverage gate."
            )
    elif cp700 is not None:
        status = "CONTINUE_TO_EXACT_800"
        stop_checkpoint = None
        next_action = (
            "The 600 and 700 checkpoints failed at least one coverage gate. "
            "Continue to the exact 800 hard cap."
        )
    elif cp600 is not None:
        status = "CONTINUE_TO_EXACT_700"
        stop_checkpoint = None
        next_action = (
            "The exact 600 checkpoint failed at least one coverage gate. "
            "Continue to the exact 700 checkpoint."
        )
    else:
        status = "COLLECT_TO_EXACT_600"
        stop_checkpoint = None
        next_action = (
            "Continue collecting fresh V4C1 ballots until the exact "
            "600-effective-vote checkpoint."
        )

    result = {
        "schema_version": 1,
        "study_id": "package-adjustment-v4-elite-fragmentation",
        "phase": "3D",
        "status": status,
        "generated_at_utc": generated_at.isoformat(),
        "research_only": True,
        "outcome_blind": True,
        "model_evaluation_performed": False,
        "candidate_predictions_read": False,
        "vote_response_tokens_read": False,
        "display_orientation_tokens_read": False,
        "production_changed": False,
        "source": {
            "sheet_sha256": sheet_sha256,
            "total_sheet_rows": len(sheet_rows),
            "raw_v4c1_namespace_rows": raw_namespace_rows,
        },
        "contract": {
            "valid_ballot_start_utc": cutoff.isoformat(),
            "daily_valid_vote_cap_per_voter": daily_cap,
            "effective_lifetime_cap_per_voter": lifetime_cap,
            "minimum_distinct_voters": min_voters,
            "minimum_effective_votes_per_cell": min_cell_effective,
            "minimum_distinct_voters_per_cell": min_cell_voters,
            "required_cell_count": 24,
            "exact_checkpoints_effective_votes": checkpoints,
            "hard_cap_effective_votes": hard_cap,
        },
        "excluded_row_counts": dict(sorted(excluded.items())),
        "current": current,
        "exact_checkpoints": checkpoint_reports,
        "stop_checkpoint": stop_checkpoint,
        "next_action": next_action,
    }

    forbidden_keys = {
        "voter", "voter_id", "voter_roster_id",
        "keep", "trade", "cut",
        "response", "choice", "choice_side",
        "displayed_left", "left_side", "ballots",
    }

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in forbidden_keys:
                    raise RuntimeError(
                        f"Forbidden persisted outcome/identity key: {key}"
                    )
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(result)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Package Adjustment V4 — Phase 3D Outcome-Blind Maturity Monitor",
        "",
        f"**Status:** `{status}`",
        "",
        f"- Valid-ballot cutoff: `{cutoff.isoformat()}`",
        f"- Raw V4C1 namespace rows: **{raw_namespace_rows}**",
        f"- Valid post-daily-cap ballots: **{current['raw_post_daily_cap_ballots']}**",
        f"- Effective votes: **{current['effective_votes']:.2f}**",
        f"- Distinct voters: **{current['distinct_voters']} / {min_voters}**",
        f"- Distinct challenges observed: **{current['distinct_challenges']} / 240**",
        f"- Cells observed: **{current['cells_observed']} / 24**",
        f"- Cells passing both gates now: **{current['cells_passing_both_gates']} / 24**",
        f"- Weakest cell effective votes: **{current['minimum_cell_effective_votes']:.2f} / {min_cell_effective:.0f}**",
        f"- Weakest cell voter coverage: **{current['minimum_cell_distinct_voters']} / {min_cell_voters}**",
        "",
        "## Exact checkpoint status",
        "",
    ]

    for checkpoint in checkpoints:
        cp = checkpoint_reports[str(checkpoint)]
        if cp is None:
            lines.append(f"- **{checkpoint}: not reached**")
        else:
            verdict = "PASS" if cp["coverage_gates_pass"] else "FAIL"
            lines.append(
                f"- **{checkpoint}: {verdict}** — "
                f"{cp['distinct_voters']} voters; "
                f"{cp['cells_passing_both_gates']}/24 cells pass; "
                f"weakest cell {cp['minimum_cell_effective_votes']:.2f} effective / "
                f"{cp['minimum_cell_distinct_voters']} voters"
            )

    lines += [
        "",
        "## Current 24-cell coverage",
        "",
        "| Topology | Asset mix | Stratum | Effective | Voters | Gate |",
        "|---|---|---|---:|---:|---|",
    ]

    for cell in current["cells"]:
        gate = "PASS" if cell["cell_gate_pass"] else "WAIT"
        lines.append(
            f"| {cell['topology']} | {cell['asset_mix']} | "
            f"{cell['challenge_stratum']} | "
            f"{cell['effective_votes']:.2f} | "
            f"{cell['distinct_voters']} | {gate} |"
        )

    if excluded:
        lines += ["", "## Excluded rows", ""]
        for reason, count in sorted(excluded.items()):
            lines.append(f"- `{reason}`: **{count}**")

    lines += [
        "",
        "## Next action",
        "",
        next_action,
        "",
        "> Outcome-blind monitor: no A/B response direction, randomized display "
        "orientation, candidate prediction, loss, significance, or candidate "
        "performance statistic is read or reported.",
        "",
    ]

    md = "\n".join(lines)
    OUT_MD.write_text(md, encoding="utf-8")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(md)

    print(md)
    print("V4_PHASE3D_MONITOR_STATUS=" + status)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
    else:
        main()
