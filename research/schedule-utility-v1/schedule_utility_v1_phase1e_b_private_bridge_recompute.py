#!/usr/bin/env python3
"""
Schedule Utility V1 — Phase 1E-B private 4for4 source bridge recomputation.

This script is intended for PRIVATE/local use with licensed 4for4 CSV exports.
It emits aggregate diagnostics only and never emits provider team-level values.

Primary gate was preregistered in Phase 1D:
- median Spearman >= 0.60
- >= 6 of 7 cells Spearman >= 0.50
- no cell Spearman < 0.30
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
from pathlib import Path
from typing import Mapping

EXPECTED_SOURCE_HASHES = {
    "afpa_half": "57c1a228ae849496092ac8404be33072d974a6eb0c251646e58b579b0892b430",
    "qb_half": "d054b074162cfe748e22c4ce00dd3bf07aee97f3eaf04cd4c737be46c5d18b47",
    "rb_half": "1f54c87762ddfff9a47e7219c1e6ea48f4905507f37e119dfaf55c3b49b22f75",
    "wr_half": "c3ae5f0af52beaa3a258785b4dbbf63ca21dcf73847a067f1daa9391db9279e4",
    "te_half": "cfae6b10a1eb6dc428004c2a599f85f4d5ab86499d3585e40e260adc03ddd325",
    "rb_ppr": "cda98824bc3a1f79ccc016a93e31da80c6c477eac1e5281536acc005979856b3",
    "wr_ppr": "ef323c774adcc680944ee2db8414f598eb96b714d09ec44263ba3a49309c8d4d",
    "te_ppr": "cdab088a1a128305acfd7820edf2c19241135a24be1a0f852dd9b8a7cdc1894f",
}

CELL_ORDER = [
    "QB_HALF", "RB_HALF", "WR_HALF", "TE_HALF",
    "RB_PPR", "WR_PPR", "TE_PPR",
]

FROZEN_GATE = {
    "median_spearman_at_least": 0.60,
    "cells_at_or_above_0_50_at_least": 6,
    "no_cell_below": 0.30,
}

CELL_RE = re.compile(r"^(-?\d+(?:\.\d+)?)@?([A-Z]{2,3})$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def verify_hashes(paths: Mapping[str, Path]) -> dict[str, str]:
    observed = {key: sha256(path) for key, path in paths.items()}
    if set(observed) != set(EXPECTED_SOURCE_HASHES):
        raise RuntimeError("private source key set mismatch")
    bad = {
        key: {"expected": EXPECTED_SOURCE_HASHES[key], "observed": observed[key]}
        for key in observed
        if observed[key] != EXPECTED_SOURCE_HASHES[key]
    }
    if bad:
        raise RuntimeError(f"private source SHA mismatch: {bad}")
    return observed


def provider_half_from_master(path: Path) -> dict[str, dict[str, float]]:
    rows = read_csv(path)
    if len(rows) != 32:
        raise ValueError(f"expected 32 master rows, got {len(rows)}")
    required = {"Team", "QB", "RB-HALF", "WR-HALF", "TE-HALF"}
    if not rows:
        raise ValueError("empty aFPA master")
    missing = required - set(rows[0])
    if missing:
        raise KeyError(f"aFPA master missing columns: {sorted(missing)}")

    col_map = {
        "QB_HALF": "QB",
        "RB_HALF": "RB-HALF",
        "WR_HALF": "WR-HALF",
        "TE_HALF": "TE-HALF",
    }
    out = {cell: {} for cell in col_map}
    for row in rows:
        team = str(row["Team"]).strip().upper()
        if not team:
            raise ValueError("blank master team")
        for cell, col in col_map.items():
            out[cell][team] = float(row[col])
    if any(len(v) != 32 for v in out.values()):
        raise ValueError("duplicate/missing master team")
    return out


def provider_ppr_from_hotspots(path: Path) -> dict[str, float]:
    rows = read_csv(path)
    if len(rows) != 32:
        raise ValueError(f"expected 32 Hot Spots rows, got {len(rows)}")
    if not rows or "Wk" not in rows[0]:
        raise KeyError("Hot Spots missing Wk column")
    for wk in map(str, range(1, 19)):
        if wk not in rows[0]:
            raise KeyError(f"Hot Spots missing week {wk}")

    values: dict[str, list[float]] = {}
    for row in rows:
        for wk in map(str, range(1, 19)):
            cell = str(row[wk]).strip()
            if not cell or cell.upper() == "BYE":
                continue
            match = CELL_RE.fullmatch(cell)
            if not match:
                raise ValueError(f"unparseable Hot Spots cell: {cell!r}")
            val = float(match.group(1))
            defense = match.group(2)
            values.setdefault(defense, []).append(val)

    if len(values) != 32:
        raise ValueError(f"expected 32 defenses in Hot Spots, got {len(values)}")

    out: dict[str, float] = {}
    for team, arr in values.items():
        if max(arr) - min(arr) > 1e-12:
            raise ValueError(
                f"Hot Spots defensive value not constant for {team}: "
                f"{min(arr)}..{max(arr)}"
            )
        out[team] = statistics.fmean(arr)
    return out


def average_ranks(values: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted((float(value), team) for team, value in values.items())
    out: dict[str, float] = {}
    i = 0
    n = len(ordered)
    while i < n:
        j = i + 1
        while j < n and ordered[j][0] == ordered[i][0]:
            j += 1
        avg = ((i + 1) + j) / 2.0
        for k in range(i, j):
            out[ordered[k][1]] = avg
        i = j
    return out


def pearson(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or len(x) < 2:
        raise ValueError("invalid Pearson inputs")
    mx = statistics.fmean(x)
    my = statistics.fmean(y)
    dx = [v - mx for v in x]
    dy = [v - my for v in y]
    sx = math.sqrt(sum(v * v for v in dx))
    sy = math.sqrt(sum(v * v for v in dy))
    if sx == 0 or sy == 0:
        raise ValueError("zero-variance rank vector")
    return sum(a * b for a, b in zip(dx, dy)) / (sx * sy)


def spearman(a: Mapping[str, float], b: Mapping[str, float]) -> tuple[float, dict, dict]:
    if set(a) != set(b):
        raise ValueError(f"team-set mismatch: {sorted(set(a) ^ set(b))}")
    ra = average_ranks(a)
    rb = average_ranks(b)
    teams = sorted(a)
    return (
        pearson([ra[t] for t in teams], [rb[t] for t in teams]),
        ra,
        rb,
    )


def exact_eight(values: Mapping[str, float], easiest: bool) -> set[str]:
    # Descriptive secondary diagnostic only. Numeric value is primary; team code
    # deterministically resolves any boundary tie so exactly eight are selected.
    if easiest:
        ordered = sorted(values, key=lambda t: (-float(values[t]), t))
    else:
        ordered = sorted(values, key=lambda t: (float(values[t]), t))
    return set(ordered[:8])


def cell_diagnostic(public: Mapping[str, float], provider: Mapping[str, float]) -> dict:
    rho, rpub, rpro = spearman(public, provider)
    teams = sorted(public)
    diffs = [abs(rpub[t] - rpro[t]) for t in teams]
    return {
        "spearman": round(rho, 12),
        "coverage": len(teams),
        "mean_abs_rank_difference": round(statistics.fmean(diffs), 6),
        "max_abs_rank_difference": round(max(diffs), 6),
        "easiest_quartile_overlap_of_8": len(
            exact_eight(public, True) & exact_eight(provider, True)
        ),
        "hardest_quartile_overlap_of_8": len(
            exact_eight(public, False) & exact_eight(provider, False)
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--public", required=True)
    ap.add_argument("--afpa-half", required=True)
    ap.add_argument("--qb-half", required=True)
    ap.add_argument("--rb-half", required=True)
    ap.add_argument("--wr-half", required=True)
    ap.add_argument("--te-half", required=True)
    ap.add_argument("--rb-ppr", required=True)
    ap.add_argument("--wr-ppr", required=True)
    ap.add_argument("--te-ppr", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    private_paths = {
        "afpa_half": Path(args.afpa_half),
        "qb_half": Path(args.qb_half),
        "rb_half": Path(args.rb_half),
        "wr_half": Path(args.wr_half),
        "te_half": Path(args.te_half),
        "rb_ppr": Path(args.rb_ppr),
        "wr_ppr": Path(args.wr_ppr),
        "te_ppr": Path(args.te_ppr),
    }
    observed_hashes = verify_hashes(private_paths)

    public_doc = json.loads(Path(args.public).read_text(encoding="utf-8"))
    if public_doc.get("status") != "PASS_PUBLIC_IMPLEMENTATION_READY_PRIVATE_BRIDGE_PENDING":
        raise RuntimeError("unexpected public Phase 1E-A status")
    if public_doc.get("frozen_implementation", {}).get("sha256") != (
        "9ab4ec5b21ef9ef57e476e861a7293dbc886b9bc9d7cc5f0bd5cc982cc729ee6"
    ):
        raise RuntimeError("unexpected frozen LOG-SAPA SHA")
    if public_doc.get("predictor_stat_weeks") != [1, 2, 3]:
        raise RuntimeError("unexpected public predictor weeks")
    if public_doc.get("target_week") != 4:
        raise RuntimeError("unexpected public target week")
    if public_doc.get("historical_target_outcomes_opened") is not False:
        raise RuntimeError("outcome firewall violated")

    public_values = {}
    for cell in CELL_ORDER:
        payload = public_doc["cells"][cell]
        vals = payload["raw_log_sapa_by_defense"]
        if len(vals) != 32:
            raise RuntimeError(f"{cell}: expected 32 public defenses")
        public_values[cell] = {team: float(v) for team, v in vals.items()}

    provider = provider_half_from_master(private_paths["afpa_half"])
    provider["RB_PPR"] = provider_ppr_from_hotspots(private_paths["rb_ppr"])
    provider["WR_PPR"] = provider_ppr_from_hotspots(private_paths["wr_ppr"])
    provider["TE_PPR"] = provider_ppr_from_hotspots(private_paths["te_ppr"])

    cells = {
        cell: cell_diagnostic(public_values[cell], provider[cell])
        for cell in CELL_ORDER
    }
    rhos = [cells[cell]["spearman"] for cell in CELL_ORDER]
    median = statistics.median(rhos)
    count50 = sum(r >= 0.50 for r in rhos)
    minimum = min(rhos)
    passed = (
        median >= FROZEN_GATE["median_spearman_at_least"]
        and count50 >= FROZEN_GATE["cells_at_or_above_0_50_at_least"]
        and minimum >= FROZEN_GATE["no_cell_below"]
    )

    result = {
        "schema_version": 1,
        "study_id": "schedule-utility-v1",
        "phase": "1E-B",
        "status": (
            "PASS_PRIVATE_SOURCE_BRIDGE"
            if passed
            else "FAIL_PRIVATE_SOURCE_BRIDGE_STOP_NO_OUTCOME_TESTING"
        ),
        "metric_id": "LOG-SAPA-V1",
        "private_analysis": True,
        "provider_rows_committed": False,
        "provider_team_values_emitted": False,
        "source_hashes_verified": True,
        "source_hashes": observed_hashes,
        "primary_gate": FROZEN_GATE,
        "cell_results": cells,
        "summary": {
            "median_spearman": round(median, 12),
            "cells_at_or_above_0_50": count50,
            "minimum_cell_spearman": round(minimum, 12),
            "all_7_cells_coverage_32": all(c["coverage"] == 32 for c in cells.values()),
            "pass": passed,
        },
        "secondary_diagnostics_are_gate_inputs": False,
        "secondary_quartile_tie_rule": (
            "numeric value then team code; descriptive only; exactly 8 selected"
        ),
        "historical_target_outcomes_opened": False,
        "phase2_outcome_test_authorized": False,
        "production_change_authorized": False,
    }

    Path(args.out).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
