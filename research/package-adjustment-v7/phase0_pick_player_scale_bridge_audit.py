#!/usr/bin/env python3
"""V7 Phase 0 — Pick/Player Scale Bridge Audit.

Diagnostic-only audit. It compares current LOG draft-pick FV with
current LOG player FV for players occupying approximately the same
frozen KTC market neighborhood. KTC is used only to define external
market neighborhoods; KTC numeric values are never copied into LOG FV.

No network access. No scraping. No production writes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INDEX = ROOT / "index.html"
ANCHORS = HERE / "phase0_market_anchor_snapshot_v1.json"
SNAPSHOT_VALUES = ROOT / "scripts" / "validation" / "snapshot_values.py"
LIVE_DEPLOYMENT = (
    ROOT
    / "research"
    / "package-adjustment-production-candidate-v1"
    / "live_deployment.json"
)

OUT_JSON = HERE / "phase0_pick_player_scale_bridge_v1.json"
OUT_MD = HERE / "phase0_pick_player_scale_bridge_v1.md"
OUT_MANIFEST = HERE / "phase0_pick_player_scale_bridge_manifest_v1.json"

sys.path.insert(0, str(ROOT / "scripts" / "validation"))
import snapshot_values  # noqa: E402

OFFENSE = {"QB", "RB", "WR", "TE"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_sha(obj: Any) -> str:
    raw = json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def js_round_positive(value: float) -> int:
    if value < 0 or not math.isfinite(value):
        raise ValueError(f"Expected finite nonnegative value, got {value!r}")
    return math.floor(value + 0.5)


def extract_pick_tables(index_text: str) -> tuple[dict[int, dict[str, float]], dict[str, float]]:
    body = snapshot_values.extract_object_body(index_text, "PICK_BASE")
    rows: dict[int, dict[str, float]] = {}
    for m in re.finditer(r"(\d+)\s*:\s*\{([^{}]+)\}", body, re.S):
        rnd = int(m.group(1))
        slots = {
            sm.group(1): float(sm.group(2))
            for sm in re.finditer(
                r"\b(early|mid|late)\s*:\s*([0-9]+(?:\.[0-9]+)?)",
                m.group(2),
            )
        }
        if slots:
            rows[rnd] = slots

    year_body = snapshot_values.extract_object_body(
        index_text, "YEAR_DISCOUNT"
    )
    years = {
        m.group(1): float(m.group(2))
        for m in re.finditer(
            r"['\"]?(\d{4})['\"]?\s*:\s*([0-9]+(?:\.[0-9]+)?)",
            year_body,
        )
    }

    if not rows or not years:
        raise AssertionError("Could not parse live PICK_BASE/YEAR_DISCOUNT")
    for rnd in range(1, 7):
        if rnd not in rows:
            raise AssertionError(f"PICK_BASE missing round {rnd}")
        if set(rows[rnd]) != {"early", "mid", "late"}:
            raise AssertionError(
                f"PICK_BASE round {rnd} slots drifted: {rows[rnd]}"
            )
    return rows, years


def pick_value(
    pick_base: dict[int, dict[str, float]],
    year_discount: dict[str, float],
    year: str,
    rnd: int,
    slot: str,
) -> int:
    base = pick_base.get(rnd, pick_base[6]).get(
        slot, pick_base[6]["late"]
    )
    disc = year_discount.get(year, 0.6)
    return js_round_positive(base * disc)


def offense_rank(player_values: dict[str, dict[str, Any]], value: float) -> int:
    vals = [
        float(row["value"])
        for row in player_values.values()
        if row.get("pos") in OFFENSE
    ]
    return 1 + sum(v > value for v in vals)


def classify_gap(gap_fraction: float, contract: dict[str, Any]) -> str:
    a = float(contract["aligned_abs_gap_max_fraction"])
    m = float(contract["material_abs_gap_min_fraction"])
    x = abs(gap_fraction)
    if x <= a + 1e-12:
        return "ALIGNED"
    if x < m - 1e-12:
        return "WATCH"
    return "MATERIAL_HIGH" if gap_fraction > 0 else "MATERIAL_LOW"


def validate_anchor_consistency(anchors: dict[str, Any]) -> dict[str, Any]:
    screenshot = anchors["user_screenshot_snapshot"]["values"]
    public = anchors["public_ranking_snapshots"][0]["values"]
    names = [
        "2027 Early 1st",
        "Jahmyr Gibbs",
        "Josh Allen",
        "Bijan Robinson",
        "Ja'Marr Chase",
    ]
    rows = []
    for name in names:
        a = float(screenshot[name])
        b = float(public[name])
        rel = abs(a - b) / ((a + b) / 2.0)
        rows.append(
            {
                "asset": name,
                "screenshot_value": a,
                "public_snapshot_value": b,
                "absolute_difference": abs(a - b),
                "relative_difference": rel,
            }
        )
    max_rel = max(r["relative_difference"] for r in rows)
    if max_rel > 0.01:
        raise AssertionError(
            f"Manual KTC snapshots disagree by >1%: max={max_rel:.4%}"
        )
    return {
        "rows": rows,
        "max_relative_difference": max_rel,
        "pass": True,
        "threshold": 0.01,
    }


def build_case(
    case: dict[str, Any],
    player_values: dict[str, dict[str, Any]],
    pick_base: dict[int, dict[str, float]],
    year_discount: dict[str, float],
    contract: dict[str, Any],
) -> dict[str, Any]:
    p = case["pick"]
    market_pick = float(p["market_value"])
    log_pick = float(
        pick_value(
            pick_base,
            year_discount,
            str(p["year"]),
            int(p["round"]),
            str(p["slot"]),
        )
    )

    comparator_rows = []
    max_dist = float(contract["comparator_market_distance_max_fraction"])
    for comp in case["comparators"]:
        key = comp["log_key"]
        if key not in player_values:
            raise AssertionError(
                f"{case['case_id']}: LOG player key missing: {key}"
            )
        row = player_values[key]
        if row.get("pos") not in OFFENSE:
            raise AssertionError(
                f"{case['case_id']}: comparator {key} is not offense: {row.get('pos')}"
            )
        market_value = float(comp["market_value"])
        market_distance = abs(market_value / market_pick - 1.0)
        if market_distance > max_dist + 1e-12:
            raise AssertionError(
                f"{case['case_id']}: comparator {comp['name']} is "
                f"{market_distance:.2%} from pick market value, over {max_dist:.2%}"
            )
        log_value = float(row["value"])
        comparator_rows.append(
            {
                "name": comp["name"],
                "log_key": key,
                "position": row["pos"],
                "market_value": market_value,
                "market_distance_fraction": market_distance,
                "log_fv": log_value,
                "log_offense_rank": offense_rank(player_values, log_value),
            }
        )

    if len(comparator_rows) < 4:
        raise AssertionError(
            f"{case['case_id']}: need at least four comparators"
        )

    log_vals = [r["log_fv"] for r in comparator_rows]
    median_fv = float(statistics.median(log_vals))
    mean_fv = float(statistics.fmean(log_vals))
    ratio = log_pick / median_fv
    gap = ratio - 1.0
    label = classify_gap(gap, contract)

    nearest = min(
        comparator_rows,
        key=lambda r: (
            r["market_distance_fraction"],
            r["name"].lower(),
        ),
    )
    pick_rank = offense_rank(player_values, log_pick)
    comp_rank_median = float(
        statistics.median(r["log_offense_rank"] for r in comparator_rows)
    )

    return {
        "case_id": case["case_id"],
        "primary": bool(case["primary"]),
        "pick": {
            "year": str(p["year"]),
            "round": int(p["round"]),
            "slot": str(p["slot"]),
            "market_value": market_pick,
            "log_fv": log_pick,
            "log_offense_insertion_rank": pick_rank,
        },
        "comparators": comparator_rows,
        "comparator_summary": {
            "count": len(comparator_rows),
            "log_fv_median": median_fv,
            "log_fv_mean": mean_fv,
            "log_fv_min": min(log_vals),
            "log_fv_max": max(log_vals),
            "log_offense_rank_median": comp_rank_median,
            "nearest_market_comparator": nearest["name"],
            "nearest_market_comparator_log_fv": nearest["log_fv"],
        },
        "bridge": {
            "pick_to_comparator_median_ratio": ratio,
            "pick_minus_comparator_median_fraction": gap,
            "absolute_gap_fraction": abs(gap),
            "rank_displacement_vs_comparator_median": (
                comp_rank_median - pick_rank
            ),
            "classification": label,
        },
    }


def build_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Package Adjustment V7 Phase 0 — Pick/Player Scale Bridge Audit",
        "",
        f"**Decision:** `{result['decision']}`",
        "",
        "This is a diagnostic-only upstream scale audit. It does **not** "
        "change Fundamental Value, draft-pick values, Market Value, Team "
        "Utility, or Package Adjustment.",
        "",
        "## Bridge cases",
        "",
        "| Case | LOG pick FV | Same-market player FV median | Gap | LOG rank displacement | Classification |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in result["cases"]:
        gap = row["bridge"]["pick_minus_comparator_median_fraction"]
        disp = row["bridge"]["rank_displacement_vs_comparator_median"]
        lines.append(
            f"| {row['case_id']} | "
            f"{row['pick']['log_fv']:.0f} | "
            f"{row['comparator_summary']['log_fv_median']:.0f} | "
            f"{gap:+.1%} | "
            f"{disp:+.1f} | "
            f"{row['bridge']['classification']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        result["interpretation"],
        "",
        "The KTC snapshots define only the external market neighborhood. "
        "Their numeric values are not imported into LOG FV. The comparison "
        "asks whether a pick and players valued similarly by the external "
        "market land in a similar region of LOG's Fundamental Value scale.",
        "",
        "## Snapshot consistency",
        "",
        f"User screenshot vs public KTC snapshot max drift: "
        f"{result['anchor_consistency']['max_relative_difference']:.2%} "
        f"(gate ≤ {result['anchor_consistency']['threshold']:.0%}).",
        "",
        "## Firewall",
        "",
        "- KTC network access from repository code: **No**",
        "- Scraping performed by repository code: **No**",
        "- Package Adjustment changed: **No**",
        "- Draft-pick values changed: **No**",
        "- Fundamental Value changed: **No**",
        "- Production change authorized: **No**",
        "",
        "## Next step",
        "",
        result["next_step"],
        "",
    ]
    return "\n".join(lines)


def run() -> None:
    anchors = json.loads(ANCHORS.read_text(encoding="utf-8"))
    contract = anchors["diagnostic_contract"]
    live = json.loads(LIVE_DEPLOYMENT.read_text(encoding="utf-8"))

    assert anchors["frozen"] is True
    assert anchors["research_only"] is True
    assert anchors["production_change_authorized"] is False
    assert anchors["network_access_required"] is False
    assert anchors["scraping_performed_by_repo"] is False
    assert live["production_revision"] == "v1.7-v6-size3-c2-overlay"
    assert live["audit_hardening"]["v6_picks_excluded"] is True

    anchor_consistency = validate_anchor_consistency(anchors)

    index_text = INDEX.read_text(encoding="utf-8")
    pick_base, year_discount = extract_pick_tables(index_text)

    cfg = snapshot_values.load_from_html(INDEX)
    player_values = snapshot_values.compute_all_values(cfg)
    if len(player_values) < 450:
        raise AssertionError(
            f"Unexpectedly small current player universe: {len(player_values)}"
        )

    cases = [
        build_case(
            case,
            player_values,
            pick_base,
            year_discount,
            contract,
        )
        for case in anchors["bridge_cases"]
    ]

    primary_ids = set(contract["primary_cases"])
    primary = [r for r in cases if r["case_id"] in primary_ids]
    if len(primary) != len(primary_ids):
        raise AssertionError("Primary case set does not match frozen contract")

    material_high = [
        r for r in primary
        if r["bridge"]["classification"] == "MATERIAL_HIGH"
    ]
    material_low = [
        r for r in primary
        if r["bridge"]["classification"] == "MATERIAL_LOW"
    ]

    is_material = max(len(material_high), len(material_low)) >= 2
    if is_material:
        decision = contract["decision_if_material"]
        direction = (
            "PICKS_HIGH_RELATIVE_TO_SAME_MARKET_PLAYERS"
            if len(material_high) >= 2
            else "PICKS_LOW_RELATIVE_TO_SAME_MARKET_PLAYERS"
        )
        interpretation = (
            "The current LOG pick/player bridge is materially displaced "
            f"in a consistent direction across the primary first-round "
            f"cases ({direction}). Treat this as an upstream draft-pick "
            "FV calibration research problem before asking a downstream "
            "package modifier to absorb the discrepancy."
        )
        next_step = (
            "Freeze V7 Package Adjustment Phase 1. Open a separate "
            "draft-pick-to-player FV bridge investigation first; keep "
            "V1.7/V6 Package Adjustment untouched."
        )
    else:
        decision = contract["decision_if_not_material"]
        direction = "NO_CONSISTENT_MATERIAL_PRIMARY_DISPLACEMENT"
        interpretation = (
            "The primary first-round cases do not show a consistent "
            "material pick/player scale displacement under the frozen "
            "diagnostic rule."
        )
        next_step = (
            "Proceed to the preregistered 24-cell V7 asset-type "
            "experiment while keeping current production unchanged."
        )

    result = {
        "schema_version": 1,
        "study_id": anchors["study_id"],
        "status": "completed_diagnostic_only",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "production_change_authorized": False,
        "automatic_production_promotion_allowed": False,
        "package_adjustment_changed": False,
        "draft_pick_values_changed": False,
        "fundamental_value_changed": False,
        "market_value_changed": False,
        "team_utility_changed": False,
        "network_access_used": False,
        "scraping_performed": False,
        "production_revision_observed": live["production_revision"],
        "player_universe_count": len(player_values),
        "offense_player_count": sum(
            row.get("pos") in OFFENSE for row in player_values.values()
        ),
        "live_pick_tables": {
            "pick_base": {
                str(k): v for k, v in sorted(pick_base.items())
            },
            "year_discount": year_discount,
        },
        "anchor_consistency": anchor_consistency,
        "cases": cases,
        "primary_summary": {
            "primary_case_count": len(primary),
            "material_high_count": len(material_high),
            "material_low_count": len(material_low),
            "overall_material": is_material,
            "direction": direction,
            "rule": contract["overall_material_rule"],
        },
        "decision": decision,
        "interpretation": interpretation,
        "next_step": next_step,
        "source_fingerprints": {
            "index_html_sha256": sha256_file(INDEX),
            "anchor_snapshot_sha256": sha256_file(ANCHORS),
            "snapshot_values_py_sha256": sha256_file(SNAPSHOT_VALUES),
            "live_deployment_sha256": sha256_file(LIVE_DEPLOYMENT),
        },
    }

    OUT_JSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUT_MD.write_text(build_markdown(result), encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "study_id": anchors["study_id"],
        "stage": "phase0_pick_player_scale_bridge_audit",
        "status": "frozen_completed_diagnostic",
        "generated_at_utc": result["generated_at_utc"],
        "decision": decision,
        "overall_material": is_material,
        "direction": direction,
        "research_only": True,
        "production_change_authorized": False,
        "automatic_production_promotion_allowed": False,
        "network_access_used": False,
        "scraping_performed": False,
        "input_hashes": result["source_fingerprints"],
        "output_hashes": {
            OUT_JSON.name: sha256_file(OUT_JSON),
            OUT_MD.name: sha256_file(OUT_MD),
        },
        "canonical_result_sha256": canonical_json_sha(result),
    }
    OUT_MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"DECISION={decision}")
    for row in cases:
        print(
            row["case_id"],
            f"pick={row['pick']['log_fv']:.0f}",
            f"median={row['comparator_summary']['log_fv_median']:.0f}",
            f"gap={row['bridge']['pick_minus_comparator_median_fraction']:+.1%}",
            row["bridge"]["classification"],
        )


def selftest() -> None:
    sample = """
    const PICK_BASE = {
      1: {early:7500, mid:5854, late:5244},
      2: {early:3906, mid:3624, late:3291},
      3: {early:2692, mid:2682, late:2319},
      4: {early:1972, mid:1831, late:1689},
      5: {early:1414, mid:1250, late:1118},
      6: {early:1014, mid:853, late:740},
    };
    const YEAR_DISCOUNT = { '2027':1.0, '2028':0.85, '2029':0.72 };
    """
    pb, yd = extract_pick_tables(sample)
    assert pb[1]["early"] == 7500
    assert yd["2028"] == 0.85
    assert pick_value(pb, yd, "2027", 1, "early") == 7500
    assert pick_value(pb, yd, "2028", 1, "early") == 6375

    c = {
        "aligned_abs_gap_max_fraction": 0.10,
        "material_abs_gap_min_fraction": 0.15,
    }
    assert classify_gap(0.10, c) == "ALIGNED"
    assert classify_gap(0.149, c) == "WATCH"
    assert classify_gap(0.15, c) == "MATERIAL_HIGH"
    assert classify_gap(-0.15, c) == "MATERIAL_LOW"
    print("Phase 0 audit self-test passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
    else:
        run()
