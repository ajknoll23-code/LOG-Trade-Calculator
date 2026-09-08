#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRADE_EVIDENCE = ROOT / "research" / "package-adjustment-v1" / "prospective" / "trade_evidence.json"
BASE_DIR = ROOT / "research" / "package-adjustment-shadow-v2" / "prospective"
FROZEN_CANDIDATE = BASE_DIR / "frozen_candidate.json"
OUT_JSON = BASE_DIR / "prospective_validation.json"
OUT_MD = BASE_DIR / "prospective_validation.md"

MAX_PRETRADE_SNAPSHOT_AGE_HOURS = 48.0
MIN_OOS_SUPPORTED_TRADES = 10
MIN_DISTINCT_TARGETS = 6
MIN_SIZE2_TRADES = 3
MIN_SIZE3_TRADES = 3


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def finite_positive(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and x > 0 else None


def percentile(values, q):
    xs = sorted(float(x) for x in values)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    t = pos - lo
    return xs[lo] * (1 - t) + xs[hi] * t


def log_interp_clamped(target_fv, refs):
    target = finite_positive(target_fv)
    if target is None:
        raise ValueError("target_fv must be positive")
    refs = sorted(refs, key=lambda r: float(r["target_fv"]))
    if target <= float(refs[0]["target_fv"]):
        return float(refs[0]["ratio"]), "clamped_low"
    if target >= float(refs[-1]["target_fv"]):
        return float(refs[-1]["ratio"]), "clamped_high"
    lx = math.log(target)
    for a, b in zip(refs, refs[1:]):
        afv, bfv = float(a["target_fv"]), float(b["target_fv"])
        if afv <= target <= bfv:
            la, lb = math.log(afv), math.log(bfv)
            t = 0.0 if lb == la else (lx - la) / (lb - la)
            ratio = float(a["ratio"]) + t * (float(b["ratio"]) - float(a["ratio"]))
            return ratio, "interpolated"
    raise AssertionError("interpolation interval not found")


def required_multiplier(candidate, target_fv, package_size):
    if int(package_size) == 2:
        mult, status = log_interp_clamped(
            target_fv, candidate["formula"]["size2"]["reference_points"]
        )
        return mult, status, "v3_ratio_plus_size_target_frozen"
    if int(package_size) == 3:
        return (
            float(candidate["formula"]["size3"]["multiplier"]),
            "constant",
            "v4_ratio_only_frozen",
        )
    raise ValueError("unsupported package size")


def classify_trade(trade, candidate):
    created_ms = int(trade.get("created_epoch_ms") or 0)
    frozen_ms = int(candidate["frozen_at_epoch_ms"])
    out = {
        "transaction_id": str(trade.get("transaction_id") or ""),
        "created_at_utc": trade.get("created_at_utc"),
        "created_epoch_ms": created_ms,
        "eligible_for_shadow_v2_oos": False,
    }

    if created_ms <= frozen_ms:
        out["exclusion_reason"] = "trade_not_strictly_after_candidate_freeze"
        return out

    if not trade.get("eligible_for_numeric_package_research"):
        out["exclusion_reason"] = trade.get("exclusion_reason") or "not_numeric_prospective_evidence"
        return out

    snap = trade.get("pretrade_snapshot") or {}
    try:
        age_hours = float(snap.get("age_hours_at_trade"))
    except (TypeError, ValueError):
        out["exclusion_reason"] = "missing_pretrade_snapshot_age"
        return out

    if not math.isfinite(age_hours) or age_hours < 0:
        out["exclusion_reason"] = "invalid_pretrade_snapshot_age"
        return out
    if age_hours > MAX_PRETRADE_SNAPSHOT_AGE_HOURS:
        out["exclusion_reason"] = "pretrade_snapshot_older_than_48h"
        out["pretrade_snapshot_age_hours"] = age_hours
        return out

    sides = trade.get("sides") or []
    if len(sides) != 2:
        out["exclusion_reason"] = "non_two_sided_trade"
        return out

    parsed = []
    for side in sides:
        assets = side.get("received_assets") or []
        if not assets:
            out["exclusion_reason"] = "empty_trade_side"
            return out
        if any(str(a.get("type") or "") != "player" for a in assets):
            out["exclusion_reason"] = "pick_or_nonplayer_asset_present"
            return out
        vals = [finite_positive(a.get("fv")) for a in assets]
        if any(v is None for v in vals):
            out["exclusion_reason"] = "unresolved_player_fv"
            return out
        parsed.append((side, assets, vals))

    counts = [len(x[1]) for x in parsed]
    if counts == [1, 1]:
        out["exclusion_reason"] = "one_for_one_trade"
        return out
    if counts[0] == 1 and counts[1] >= 2:
        target_i, package_i = 0, 1
    elif counts[1] == 1 and counts[0] >= 2:
        target_i, package_i = 1, 0
    else:
        out["exclusion_reason"] = "multi_vs_multi_trade"
        return out

    target_side, target_assets, target_values = parsed[target_i]
    package_side, package_assets, package_values = parsed[package_i]
    target_fv = float(target_values[0])

    if any(float(v) >= target_fv for v in package_values):
        out["exclusion_reason"] = "package_contains_asset_at_or_above_target_fv"
        return out

    threshold = target_fv * float(
        candidate["applicability"]["meaningful_piece_min_target_share"]
    )
    meaningful = [float(v) for v in package_values if float(v) >= threshold]
    tiny = [float(v) for v in package_values if float(v) < threshold]
    size = len(meaningful)

    if size == 1:
        out["exclusion_reason"] = "effective_one_for_one_after_tiny_piece_filter"
        return out
    if size not in (2, 3):
        out["exclusion_reason"] = "unsupported_meaningful_package_size"
        out["meaningful_package_size"] = size
        return out

    package_fv = sum(float(v) for v in package_values)
    actual_ratio = package_fv / target_fv
    multiplier, interp, source = required_multiplier(candidate, target_fv, size)
    required_fv = target_fv * multiplier
    coverage = package_fv / required_fv

    shadow_err = abs(math.log(max(actual_ratio, 1e-12) / multiplier))
    raw_err = abs(math.log(max(actual_ratio, 1e-12)))

    out.update({
        "eligible_for_shadow_v2_oos": True,
        "exclusion_reason": None,
        "pretrade_snapshot": snap,
        "pretrade_snapshot_age_hours": age_hours,
        "target_player": target_assets[0].get("name"),
        "target_player_id": target_assets[0].get("player_id"),
        "target_pos": target_assets[0].get("pos"),
        "target_fv": target_fv,
        "concentrated_roster_id": target_side.get("roster_id"),
        "concentrated_team_name": target_side.get("team_name"),
        "package_roster_id": package_side.get("roster_id"),
        "package_team_name": package_side.get("team_name"),
        "package_players": [a.get("name") for a in package_assets],
        "package_player_fvs": [float(v) for v in package_values],
        "meaningful_package_size": size,
        "tiny_piece_fvs_ignored_for_size": tiny,
        "raw_package_fv": package_fv,
        "raw_package_to_target_ratio": actual_ratio,
        "shadow_required_multiplier": multiplier,
        "shadow_required_package_fv": required_fv,
        "package_to_shadow_requirement_ratio": coverage,
        "package_pct_from_shadow_requirement": (coverage - 1.0) * 100.0,
        "package_meets_or_exceeds_shadow_requirement": package_fv >= required_fv,
        "shadow_abs_log_error_to_observed_exchange_ratio": shadow_err,
        "raw_additive_abs_log_error_to_observed_exchange_ratio": raw_err,
        "shadow_closer_than_raw_additive": shadow_err < raw_err,
        "model_source": source,
        "interpolation_status": interp,
    })
    return out


def summarize(obs, rows):
    reasons = Counter(
        r.get("exclusion_reason") or "unknown"
        for r in rows if not r.get("eligible_for_shadow_v2_oos")
    )
    by_size = {}
    for size in (2, 3):
        sub = [r for r in obs if int(r["meaningful_package_size"]) == size]
        coverage = [r["package_to_shadow_requirement_ratio"] for r in sub]
        actual = [r["raw_package_to_target_ratio"] for r in sub]
        req = [r["shadow_required_multiplier"] for r in sub]
        by_size[str(size)] = {
            "trade_count": len(sub),
            "median_observed_package_to_target_ratio": statistics.median(actual) if actual else None,
            "median_shadow_required_multiplier": statistics.median(req) if req else None,
            "median_package_to_shadow_requirement_ratio": statistics.median(coverage) if coverage else None,
            "within_10pct_of_requirement_pct": (
                100.0 * sum(0.90 <= x <= 1.10 for x in coverage) / len(coverage)
                if coverage else None
            ),
            "within_20pct_of_requirement_pct": (
                100.0 * sum(0.80 <= x <= 1.20 for x in coverage) / len(coverage)
                if coverage else None
            ),
        }

    coverages = [r["package_to_shadow_requirement_ratio"] for r in obs]
    shadow_errors = [r["shadow_abs_log_error_to_observed_exchange_ratio"] for r in obs]
    raw_errors = [r["raw_additive_abs_log_error_to_observed_exchange_ratio"] for r in obs]
    targets = {str(r.get("target_player_id") or r.get("target_player")) for r in obs}

    gates = {
        "supported_oos_trades": len(obs) >= MIN_OOS_SUPPORTED_TRADES,
        "distinct_targets": len(targets) >= MIN_DISTINCT_TARGETS,
        "size2_coverage": by_size["2"]["trade_count"] >= MIN_SIZE2_TRADES,
        "size3_coverage": by_size["3"]["trade_count"] >= MIN_SIZE3_TRADES,
    }

    return {
        "candidate_freeze_cutoff_enforced": True,
        "max_pretrade_snapshot_age_hours": MAX_PRETRADE_SNAPSHOT_AGE_HOURS,
        "logged_trade_count": len(rows),
        "supported_oos_trade_count": len(obs),
        "excluded_trade_count": len(rows) - len(obs),
        "distinct_target_count": len(targets),
        "exclusion_reasons": dict(sorted(reasons.items())),
        "by_package_size": by_size,
        "overall": {
            "median_package_to_shadow_requirement_ratio": statistics.median(coverages) if coverages else None,
            "p25_package_to_shadow_requirement_ratio": percentile(coverages, 0.25) if coverages else None,
            "p75_package_to_shadow_requirement_ratio": percentile(coverages, 0.75) if coverages else None,
            "within_10pct_of_shadow_requirement_pct": (
                100.0 * sum(0.90 <= x <= 1.10 for x in coverages) / len(coverages)
                if coverages else None
            ),
            "within_20pct_of_shadow_requirement_pct": (
                100.0 * sum(0.80 <= x <= 1.20 for x in coverages) / len(coverages)
                if coverages else None
            ),
            "median_shadow_abs_log_error": statistics.median(shadow_errors) if shadow_errors else None,
            "median_raw_additive_abs_log_error": statistics.median(raw_errors) if raw_errors else None,
            "shadow_closer_than_raw_additive_pct": (
                100.0 * sum(r["shadow_closer_than_raw_additive"] for r in obs) / len(obs)
                if obs else None
            ),
        },
        "evidence_maturity_gates": {
            "thresholds": {
                "supported_oos_trades": MIN_OOS_SUPPORTED_TRADES,
                "distinct_targets": MIN_DISTINCT_TARGETS,
                "size2_trades": MIN_SIZE2_TRADES,
                "size3_trades": MIN_SIZE3_TRADES,
            },
            "passed": gates,
            "all_passed": all(gates.values()),
        },
        "interpretation_guardrail": (
            "Completed trades are revealed-preference observations, not exact fair-value labels. "
            "Maturity gates trigger review only and never auto-promote production."
        ),
    }


def build_payload(evidence, candidate):
    assert candidate["status"] == "frozen_oos_candidate"
    assert candidate["frozen"] is True
    assert candidate["production_formula_enabled"] is False

    rows = [classify_trade(t, candidate) for t in (evidence.get("trades") or {}).values()]
    rows.sort(key=lambda r: int(r.get("created_epoch_ms") or 0))
    obs = [r for r in rows if r.get("eligible_for_shadow_v2_oos")]

    return {
        "schema_version": 1,
        "status": "research_only_prospective_oos_validation",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "consumer_changed": False,
        "fundamental_value_consumer_changed": False,
        "market_value_consumer_changed": False,
        "team_utility_consumer_changed": False,
        "trade_verdict_consumer_changed": False,
        "production_formula_enabled": False,
        "production_promotion_allowed": False,
        "candidate": {
            "candidate_id": candidate["candidate_id"],
            "frozen_at_utc": candidate["frozen_at_utc"],
            "frozen_at_epoch_ms": candidate["frozen_at_epoch_ms"],
            "source_shadow_v2_sha256": candidate["source_shadow_v2_sha256"],
        },
        "methodology": {
            "only_trades_strictly_after_candidate_freeze": True,
            "only_pretrade_fv_snapshots": True,
            "max_pretrade_snapshot_age_hours": MAX_PRETRADE_SNAPSHOT_AGE_HOURS,
            "player_only": True,
            "supported_shapes": ["1-for-2 meaningful players", "1-for-3 meaningful players"],
            "picks_excluded": True,
            "multi_vs_multi_excluded": True,
            "comparison_baseline": "raw_additive_FV_multiplier_1.0",
            "team_utility_not_used_as_validation_label": True,
            "market_value_not_used_as_validation_label": True,
        },
        "summary": summarize(obs, rows),
        "observations": obs,
        "all_trade_classifications": rows,
    }


def write_report(doc):
    s = doc["summary"]
    o = s["overall"]
    gates = s["evidence_maturity_gates"]

    def fmt(x, d=3):
        return "n/a" if x is None else f"{float(x):.{d}f}"

    lines = [
        "# Package Adjustment Shadow V2 — Prospective/OOS Validation",
        "",
        "**Status: RESEARCH ONLY — no production consumer changed.**",
        "",
        f"- Frozen candidate: `{doc['candidate']['candidate_id']}`",
        f"- Candidate frozen at: `{doc['candidate']['frozen_at_utc']}`",
        f"- Supported OOS trades: `{s['supported_oos_trade_count']}`",
        f"- Distinct targets: `{s['distinct_target_count']}`",
        f"- 2-player observations: `{s['by_package_size']['2']['trade_count']}`",
        f"- 3-player observations: `{s['by_package_size']['3']['trade_count']}`",
        "",
        "## Calibration diagnostics",
        "",
        f"- Median actual / shadow requirement: `{fmt(o['median_package_to_shadow_requirement_ratio'])}`",
        f"- Within ±10%: `{fmt(o['within_10pct_of_shadow_requirement_pct'], 1)}%`",
        f"- Within ±20%: `{fmt(o['within_20pct_of_shadow_requirement_pct'], 1)}%`",
        f"- Shadow closer than raw additive FV: `{fmt(o['shadow_closer_than_raw_additive_pct'], 1)}%`",
        "",
        "## Evidence maturity",
        "",
        f"- Ready for manual review: `{gates['all_passed']}`",
    ]
    for name, passed in gates["passed"].items():
        lines.append(f"- {name}: `{passed}`")

    lines += ["", "## Exclusions", ""]
    if s["exclusion_reasons"]:
        for reason, count in s["exclusion_reasons"].items():
            lines.append(f"- `{reason}`: {count}")
    else:
        lines.append("- None")

    lines += [
        "",
        "## Production status",
        "",
        "**Production promotion remains disabled regardless of this report.**",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def selftest():
    candidate = {
        "status": "frozen_oos_candidate",
        "frozen": True,
        "frozen_at_epoch_ms": 1000,
        "production_formula_enabled": False,
        "applicability": {"meaningful_piece_min_target_share": 0.06},
        "formula": {
            "size2": {"reference_points": [
                {"target_fv": 4000, "ratio": 1.40},
                {"target_fv": 5000, "ratio": 1.48},
                {"target_fv": 6000, "ratio": 1.54},
                {"target_fv": 7000, "ratio": 1.58},
            ]},
            "size3": {"multiplier": 2.05},
        },
    }

    def side(rid, vals):
        return {"roster_id": rid, "received_assets": [
            {"type": "player", "player_id": f"{rid}-{i}", "name": f"P{i}", "pos": "WR", "fv": v}
            for i, v in enumerate(vals)
        ]}

    base = {
        "created_epoch_ms": 2000,
        "eligible_for_numeric_package_research": True,
        "pretrade_snapshot": {"age_hours_at_trade": 5.0},
    }
    t2 = {**base, "transaction_id": "t2", "sides": [side("A", [5000]), side("B", [4000, 3400])]}
    assert classify_trade(t2, candidate)["meaningful_package_size"] == 2
    t3 = {**base, "transaction_id": "t3", "sides": [side("A", [5000]), side("B", [4000, 3500, 2750])]}
    assert classify_trade(t3, candidate)["meaningful_package_size"] == 3
    pre = {**t2, "created_epoch_ms": 900}
    assert classify_trade(pre, candidate)["exclusion_reason"] == "trade_not_strictly_after_candidate_freeze"
    old = {**t2, "pretrade_snapshot": {"age_hours_at_trade": 49.0}}
    assert classify_trade(old, candidate)["exclusion_reason"] == "pretrade_snapshot_older_than_48h"
    print("Package Adjustment Shadow V2 prospective evaluator self-test passed.")


def check_output():
    candidate = read_json(FROZEN_CANDIDATE)
    doc = read_json(OUT_JSON)
    assert candidate["status"] == "frozen_oos_candidate"
    assert candidate["frozen"] is True
    assert doc["status"] == "research_only_prospective_oos_validation"
    assert doc["production_formula_enabled"] is False
    assert doc["production_promotion_allowed"] is False
    freeze_ms = int(candidate["frozen_at_epoch_ms"])
    for r in doc["observations"]:
        assert int(r["created_epoch_ms"]) > freeze_ms
        assert float(r["pretrade_snapshot_age_hours"]) <= MAX_PRETRADE_SNAPSHOT_AGE_HOURS
    print("Package Adjustment Shadow V2 prospective output check passed.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--write", action="store_true")
    p.add_argument("--check", action="store_true")
    args = p.parse_args()

    if args.selftest:
        selftest()
        return
    if args.check:
        check_output()
        return
    if not args.write:
        raise SystemExit("Use --write, --check, or --selftest")

    doc = build_payload(read_json(TRADE_EVIDENCE), read_json(FROZEN_CANDIDATE))
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(doc)
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")
    print("Supported OOS trades:", doc["summary"]["supported_oos_trade_count"])


if __name__ == "__main__":
    main()
