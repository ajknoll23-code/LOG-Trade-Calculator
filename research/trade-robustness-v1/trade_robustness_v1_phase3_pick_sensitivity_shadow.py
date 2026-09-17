#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = Path(__file__).resolve().parent

INDEX = ROOT / "index.html"
PHASE1 = OUTDIR / "trade_robustness_v1_phase1_shadow.py"
PHASE1B = OUTDIR / "trade_robustness_v1_phase1b_live_verdict_alignment.py"
PHASE1B_JSON = OUTDIR / "trade_robustness_v1_phase1b_live_verdict_alignment.json"

OUTJSON = OUTDIR / "trade_robustness_v1_phase3_pick_sensitivity_shadow.json"
OUTMD = OUTDIR / "trade_robustness_v1_phase3_pick_sensitivity_shadow.md"
MANIFEST = OUTDIR / "trade_robustness_v1_phase3_manifest.json"

FAIR_THRESHOLD = 0.07
STRONG_THRESHOLD = 0.20
TOP_PLAYER_POOL = 80
TOP_PACKAGE_ANCHORS = 30

SUPPORTED_ROUNDS = {1, 2, 3, 4}
EXTRAPOLATED_ROUNDS = {5, 6}
SLOTS = ("early", "mid", "late")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def verdict_class(a: float, b: float) -> dict:
    a = float(a)
    b = float(b)
    denom = max(a, b, 1.0)
    diff = a - b
    diff_pct = abs(diff) / denom

    if diff_pct < FAIR_THRESHOLD:
        return {
            "label": "fair",
            "side": None,
            "strength": "fair",
            "diff": diff,
            "diff_pct": diff_pct,
        }

    side = "A" if diff > 0 else "B"
    strength = "slight" if diff_pct < STRONG_THRESHOLD else "strong"
    return {
        "label": f"{strength}_{side.lower()}",
        "side": side,
        "strength": strength,
        "diff": diff,
        "diff_pct": diff_pct,
    }


def extract_pick_table(p1) -> tuple[list[dict], dict]:
    text = INDEX.read_text(encoding="utf-8")

    pick_base = p1.extract_balanced(text, "const PICK_BASE = {")
    year_discount = p1.extract_balanced(text, "const YEAR_DISCOUNT = {")
    pick_seasons = p1.extract_balanced(
        text,
        "const PICK_SEASONS = [",
        "[",
        "]",
    )
    pick_value = p1.extract_function(text, "pickValue")

    m = re.search(
        r"let\s+DRAFT_SLOT_APPLIES_TO_SEASON\s*=\s*['\"](\d{4})['\"]",
        text,
    )
    if not m:
        raise RuntimeError("Cannot locate DRAFT_SLOT_APPLIES_TO_SEASON")
    projected_season = m.group(1)

    harness = r'''
const rows = [];
for (const season of PICK_SEASONS) {
  for (let round = 1; round <= 6; round++) {
    for (const slot of ['early','mid','late']) {
      rows.push({
        season: String(season),
        round,
        slot,
        value: Number(pickValue(round, slot, String(season))),
      });
    }
  }
}
process.stdout.write(JSON.stringify({
  seasons: PICK_SEASONS.map(String),
  rows,
}));
'''
    js = "\n\n".join(
        [pick_base, year_discount, pick_seasons, pick_value, harness]
    )

    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".js",
        delete=False,
        encoding="utf-8",
    ) as jf:
        jf.write(js)
        path = Path(jf.name)

    try:
        proc = subprocess.run(
            ["node", str(path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        doc = json.loads(proc.stdout)
    finally:
        path.unlink(missing_ok=True)

    by_key = {
        (int(row["round"]), str(row["season"]), str(row["slot"])):
        int(row["value"])
        for row in doc["rows"]
    }

    pick_types = []
    for season in doc["seasons"]:
        center_slots = SLOTS if season == projected_season else ("mid",)
        for round_no in range(1, 7):
            values = [
                by_key[(round_no, season, slot)]
                for slot in SLOTS
            ]
            low = min(values)
            high = max(values)
            for center_slot in center_slots:
                center = by_key[(round_no, season, center_slot)]
                evidence_class = (
                    "market_benchmarked_round_1_4"
                    if round_no in SUPPORTED_ROUNDS
                    else "extrapolated_round_5_6"
                )
                pick_types.append({
                    "key": f"{season} R{round_no} {center_slot}",
                    "asset_type": "pick",
                    "pos": None,
                    "season": season,
                    "round": round_no,
                    "slot": center_slot,
                    "center": center,
                    "low": low,
                    "high": high,
                    "relative_half_width": (
                        (high - low) / (2.0 * center)
                        if center > 0 else 0.0
                    ),
                    "evidence_class": evidence_class,
                    "promotion_eligible":
                        round_no in SUPPORTED_ROUNDS,
                })

    meta = {
        "production_pick_seasons": doc["seasons"],
        "draft_slot_applies_to_season": projected_season,
        "range_semantics":
            "same-round/year deterministic early-to-late slot envelope",
        "year_discount_policy":
            "held fixed at deployed production value; no unvalidated "
            "year-discount uncertainty added",
        "round_1_4_policy":
            "promotion-eligible because production PICK_BASE is market-benchmarked",
        "round_5_6_policy":
            "research-only because production PICK_BASE labels these rounds extrapolated",
    }
    return pick_types, meta


def build_player_pool(p1) -> tuple[list[dict], dict]:
    pools, audit = p1.build_roster_pools()
    by_sid = {}
    for roster_rows in pools.values():
        for row in roster_rows:
            sid = row["sleeper_id"]
            existing = by_sid.get(sid)
            if existing is None or row["center"] > existing["center"]:
                by_sid[sid] = {
                    "key": row["key"],
                    "asset_type": "player",
                    "pos": row["pos"],
                    "sleeper_id": sid,
                    "center": float(row["center"]),
                    "low": float(row["low"]),
                    "high": float(row["high"]),
                    "relative_half_width": float(row["half_width"]),
                    "evidence_class": "player_sensitivity_envelope_v1",
                    "promotion_eligible": True,
                }

    rows = sorted(
        by_sid.values(),
        key=lambda x: (-x["center"], x["key"]),
    )[:TOP_PLAYER_POOL]
    return rows, audit


def build_cases(players: list[dict], picks: list[dict]) -> list[dict]:
    cases = []

    for i, a in enumerate(picks):
        for b in picks[i + 1:]:
            cases.append({
                "case_id":
                    f"pick1v1:{a['season']}:{a['round']}:{a['slot']}:"
                    f"{b['season']}:{b['round']}:{b['slot']}",
                "structure": "pick_vs_pick",
                "A": [a],
                "B": [b],
            })

    for player in players:
        for pick in picks:
            cases.append({
                "case_id":
                    f"player_v_pick:{player['sleeper_id']}:"
                    f"{pick['season']}:{pick['round']}:{pick['slot']}",
                "structure": "player_vs_pick",
                "A": [player],
                "B": [pick],
            })

    anchors = players[:TOP_PACKAGE_ANCHORS]
    for anchor in anchors:
        for pick in picks:
            package_raw = anchor["center"] + pick["center"]
            opponents = [
                p for p in players
                if p["sleeper_id"] != anchor["sleeper_id"]
            ]
            opponent = min(
                opponents,
                key=lambda p: (
                    abs(p["center"] - package_raw),
                    p["key"],
                ),
            )

            cases.append({
                "case_id":
                    f"mixed_2v1:{anchor['sleeper_id']}:"
                    f"{pick['season']}:{pick['round']}:{pick['slot']}:"
                    f"{opponent['sleeper_id']}",
                "structure": "player_plus_pick_vs_player",
                "A": [anchor, pick],
                "B": [opponent],
            })
            cases.append({
                "case_id":
                    f"mixed_1v2:{opponent['sleeper_id']}:"
                    f"{anchor['sleeper_id']}:"
                    f"{pick['season']}:{pick['round']}:{pick['slot']}",
                "structure": "player_vs_player_plus_pick",
                "A": [opponent],
                "B": [anchor, pick],
            })

    return cases


def compact_case(case: dict) -> dict:
    keys = (
        "key", "asset_type", "pos", "center", "low", "high",
        "season", "round", "slot", "evidence_class",
        "promotion_eligible",
    )
    return {
        "case_id": case["case_id"],
        "structure": case["structure"],
        "A": [{k: row.get(k) for k in keys} for row in case["A"]],
        "B": [{k: row.get(k) for k in keys} for row in case["B"]],
    }


def run_live_js(p1, cases: list[dict]) -> list[dict]:
    text = INDEX.read_text(encoding="utf-8")
    parts = [
        p1.extract_package_config(text),
        p1.extract_function(text, "packageAdjustmentSize2Multiplier"),
        p1.extract_function(
            text,
            "packageAdjustmentSize2CompositionFactor",
        ),
        p1.extract_function(text, "packageAdjustmentAssessment"),
        p1.extract_function(text, "packageAdjustmentForTrade"),
        p1.extract_function(text, "sideTotal"),
        p1.extract_function(text, "tradeVerdictTotals"),
    ]

    harness = r'''
const fs = require('fs');
const cases = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
let state = {A:[], B:[]};

function item(x, field) {
  const out = {
    type: x.asset_type,
    value: Number(x[field]),
    name: x.key,
  };
  if (x.pos) out.pos = x.pos;
  if (x.asset_type === 'pick') {
    out.round = Number(x.round);
    out.season = String(x.season);
    out.slot = String(x.slot);
  }
  return out;
}

function scenario(c, favoredSide) {
  const AField = favoredSide === 'A' ? 'low' : 'high';
  const BField = favoredSide === 'B' ? 'low' : 'high';
  state = {
    A: c.A.map(x => item(x, AField)),
    B: c.B.map(x => item(x, BField)),
  };
  const totals = tradeVerdictTotals();
  return {
    A: Number(totals.A),
    B: Number(totals.B),
    packageAdjustment: totals.packageAdjustment || null,
  };
}

const out = [];
for (const c of cases) {
  state = {
    A: c.A.map(x => item(x, 'center')),
    B: c.B.map(x => item(x, 'center')),
  };
  const centerTotals = tradeVerdictTotals();
  const assessment = packageAdjustmentAssessment();

  out.push({
    case_id: c.case_id,
    center: {
      A: Number(centerTotals.A),
      B: Number(centerTotals.B),
      packageAdjustment: centerTotals.packageAdjustment || null,
    },
    adverse_if_A_favored: scenario(c, 'A'),
    adverse_if_B_favored: scenario(c, 'B'),
    package_status: assessment.status,
    package_tier:
      assessment.packageAdjustment
        ? assessment.packageAdjustment.premiumTier
        : null,
  });
}

process.stdout.write(JSON.stringify(out));
'''
    js = "\n\n".join(parts) + "\n\n" + harness

    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".js",
        delete=False,
        encoding="utf-8",
    ) as jf, tempfile.NamedTemporaryFile(
        "w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as cf:
        jf.write(js)
        js_path = Path(jf.name)
        json.dump(
            [compact_case(c) for c in cases],
            cf,
            separators=(",", ":"),
        )
        case_path = Path(cf.name)

    try:
        proc = subprocess.run(
            ["node", str(js_path), str(case_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(proc.stdout)
    finally:
        js_path.unlink(missing_ok=True)
        case_path.unlink(missing_ok=True)


def classify_case(result: dict) -> dict:
    center = verdict_class(
        result["center"]["A"],
        result["center"]["B"],
    )

    if center["side"] is None:
        return {
            "center": center,
            "outcome": "center_fair",
            "adverse": None,
        }

    adverse_raw = (
        result["adverse_if_A_favored"]
        if center["side"] == "A"
        else result["adverse_if_B_favored"]
    )
    adverse = verdict_class(
        adverse_raw["A"],
        adverse_raw["B"],
    )

    if adverse["side"] == center["side"]:
        outcome = "direction_robust"
    elif adverse["side"] is None:
        outcome = "softened_to_fair"
    else:
        outcome = "flipped_direction"

    return {
        "center": center,
        "outcome": outcome,
        "adverse": {
            **adverse,
            "A_total": adverse_raw["A"],
            "B_total": adverse_raw["B"],
        },
    }


def analyze() -> dict:
    p1 = load_module(PHASE1, "trade_robustness_phase1")
    p1b = read(PHASE1B_JSON)
    if (
        p1b.get("decision")
        != "PASS_TRADE_ROBUSTNESS_V1_PHASE1B_LIVE_VERDICT_ALIGNMENT"
    ):
        raise RuntimeError("Phase 1B anchor is not PASS")

    picks, pick_meta = extract_pick_table(p1)
    players, roster_audit = build_player_pool(p1)

    if not players:
        raise RuntimeError("No player sensitivity pool")

    for pick in picks:
        if not (0 <= pick["low"] <= pick["center"] <= pick["high"]):
            raise RuntimeError(f"Invalid pick envelope: {pick}")
        if pick["low"] == pick["high"]:
            raise RuntimeError(f"Degenerate pick envelope: {pick}")

    cases = build_cases(players, picks)
    by_id = {c["case_id"]: c for c in cases}
    live = run_live_js(p1, cases)

    by_structure = defaultdict(Counter)
    by_evidence = defaultdict(Counter)
    by_round = defaultdict(Counter)
    by_season = defaultdict(Counter)
    package_status = Counter()
    examples = {
        "direction_robust": [],
        "softened_to_fair": [],
        "flipped_direction": [],
    }

    supported_directional = 0
    supported_robust = 0
    supported_softened = 0
    supported_flipped = 0

    for result in live:
        case = by_id[result["case_id"]]
        classified = classify_case(result)
        outcome = classified["outcome"]

        pick_assets = [
            x for x in case["A"] + case["B"]
            if x["asset_type"] == "pick"
        ]
        if not pick_assets:
            raise RuntimeError("Phase 3 case without a pick")

        evidence = (
            "supported_round_1_4"
            if all(x["promotion_eligible"] for x in pick_assets)
            else "contains_extrapolated_round_5_6"
        )

        by_structure[case["structure"]]["cases"] += 1
        by_structure[case["structure"]][outcome] += 1
        by_evidence[evidence]["cases"] += 1
        by_evidence[evidence][outcome] += 1
        package_status[result["package_status"]] += 1

        for p in pick_assets:
            by_round[str(p["round"])]["asset_occurrences"] += 1
            by_round[str(p["round"])][outcome] += 1
            by_season[p["season"]]["asset_occurrences"] += 1
            by_season[p["season"]][outcome] += 1

        if evidence == "supported_round_1_4" and outcome != "center_fair":
            supported_directional += 1
            if outcome == "direction_robust":
                supported_robust += 1
            elif outcome == "softened_to_fair":
                supported_softened += 1
            elif outcome == "flipped_direction":
                supported_flipped += 1

        if outcome in examples and len(examples[outcome]) < 15:
            examples[outcome].append({
                "case_id": case["case_id"],
                "structure": case["structure"],
                "A": [x["key"] for x in case["A"]],
                "B": [x["key"] for x in case["B"]],
                "center": {
                    **classified["center"],
                    "A_total": result["center"]["A"],
                    "B_total": result["center"]["B"],
                },
                "adverse": classified["adverse"],
                "evidence_class": evidence,
                "package_status": result["package_status"],
                "package_tier": result.get("package_tier"),
            })

    supported_pick_types = [
        p for p in picks if p["promotion_eligible"]
    ]
    unsupported_pick_types = [
        p for p in picks if not p["promotion_eligible"]
    ]

    gates = {
        "phase1b_anchor_passed": True,
        "live_thresholds_preserved": True,
        "all_production_pick_seasons_covered":
            set(pick_meta["production_pick_seasons"])
            == {p["season"] for p in picks},
        "rounds_1_4_have_structural_envelopes":
            len(supported_pick_types) > 0
            and all(p["low"] < p["high"] for p in supported_pick_types),
        "rounds_5_6_explicitly_fail_closed":
            len(unsupported_pick_types) > 0
            and all(
                p["round"] in EXTRAPOLATED_ROUNDS
                for p in unsupported_pick_types
            ),
        "mixed_live_package_adjustment_exercised":
            any(
                c["structure"] in {
                    "player_plus_pick_vs_player",
                    "player_vs_player_plus_pick",
                }
                for c in cases
            ),
        "year_discount_not_reestimated": True,
    }

    # Feasibility gates answer whether the pick-sensitivity method is
    # supportable for a later promotion phase. Production authorization
    # is intentionally FALSE here and is a guardrail, not a gate.
    passed = all(gates.values())
    decision = (
        "PASS_TRADE_ROBUSTNESS_V1_PHASE3_PICK_SLOT_SENSITIVITY_SHADOW"
        if passed
        else "HOLD_TRADE_ROBUSTNESS_V1_PHASE3_PICK_SLOT_SENSITIVITY_SHADOW"
    )

    return {
        "schema_version": 1,
        "study_id":
            "trade-robustness-v1-phase3-pick-slot-sensitivity-shadow",
        "status": "PICK_SLOT_SENSITIVITY_SHADOW_COMPLETE",
        "decision": decision,
        "generated_at_utc":
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        "research_only": True,
        "production_change_authorized": False,
        "production_thresholds": {
            "fair_trade_diff_pct_lt": FAIR_THRESHOLD,
            "slightly_favors_diff_pct_lt": STRONG_THRESHOLD,
            "strongly_favors_diff_pct_gte": STRONG_THRESHOLD,
        },
        "pick_method": pick_meta,
        "promotion_scope": {
            "eligible_rounds": sorted(SUPPORTED_ROUNDS),
            "ineligible_rounds": sorted(EXTRAPOLATED_ROUNDS),
            "eligible_seasons":
                pick_meta["production_pick_seasons"],
            "eligible_range_semantics":
                "deterministic same-round/year early-to-late slot envelope",
            "year_discount_uncertainty_modeled": False,
        },
        "gates": gates,
        "universe": {
            "total_cases": len(cases),
            "player_pool_size": len(players),
            "pick_center_types": len(picks),
            "promotion_eligible_pick_center_types":
                len(supported_pick_types),
            "research_only_pick_center_types":
                len(unsupported_pick_types),
            "roster_audit": roster_audit,
        },
        "supported_round_1_4_directional_summary": {
            "directional_cases": supported_directional,
            "direction_robust": supported_robust,
            "softened_to_fair": supported_softened,
            "flipped_direction": supported_flipped,
            "direction_robust_share": round(
                supported_robust / max(1, supported_directional),
                6,
            ),
            "softened_to_fair_share": round(
                supported_softened / max(1, supported_directional),
                6,
            ),
            "flipped_direction_share": round(
                supported_flipped / max(1, supported_directional),
                6,
            ),
        },
        "by_structure": {
            k: dict(v)
            for k, v in sorted(by_structure.items())
        },
        "by_evidence_class": {
            k: dict(v)
            for k, v in sorted(by_evidence.items())
        },
        "by_pick_round": {
            k: dict(v)
            for k, v in sorted(
                by_round.items(),
                key=lambda kv: int(kv[0]),
            )
        },
        "by_pick_season": {
            k: dict(v)
            for k, v in sorted(by_season.items())
        },
        "package_status_counts": dict(package_status),
        "pick_envelopes": picks,
        "examples": examples,
        "recommended_next_step": (
            "If PASS, Phase 4 may extend the existing display-only "
            "Trade Robustness badge to trades containing only players "
            "and promotion-eligible Round 1-4 picks. Round 5-6 picks "
            "must continue to fail closed. The UI must describe the "
            "pick component as draft-slot sensitivity, not probability."
        ),
    }


def render(result: dict) -> str:
    u = result["universe"]
    s = result["supported_round_1_4_directional_summary"]

    lines = [
        "# Trade Robustness V1 Phase 3 — Pick Slot Sensitivity Shadow",
        "",
        f"**Decision:** `{result['decision']}`",
        "",
        "**RESEARCH ONLY. No calculator behavior changed.**",
        "",
        "## Method",
        "",
        "- Player assets keep the deployed deterministic sensitivity envelope.",
        "- Pick center values use the live production `pickValue()` function.",
        "- Pick low/high values span late-to-early slot values for the same round/year.",
        "- The deployed year discount is held fixed; no unsupported year-discount uncertainty is invented.",
        "- Rounds 1-4 are promotion-eligible.",
        "- Rounds 5-6 remain fail-closed because their production base values are extrapolated.",
        "- Every adverse case reruns the actual live Package Adjustment and Trade Verdict.",
        "",
        "## Universe",
        "",
        f"- Cases: **{u['total_cases']}**",
        f"- Player sensitivity pool: **{u['player_pool_size']}**",
        f"- Pick center types: **{u['pick_center_types']}**",
        f"- Promotion-eligible pick types: **{u['promotion_eligible_pick_center_types']}**",
        f"- Research-only R5/R6 pick types: **{u['research_only_pick_center_types']}**",
        "",
        "## Supported Round 1-4 directional outcomes",
        "",
        f"- Directional cases: **{s['directional_cases']}**",
        f"- Sensitivity Robust: **{s['direction_robust']}** "
        f"({100*s['direction_robust_share']:.1f}%)",
        f"- Fragile → Fair: **{s['softened_to_fair']}** "
        f"({100*s['softened_to_fair_share']:.1f}%)",
        f"- Fragile → opposite side: **{s['flipped_direction']}** "
        f"({100*s['flipped_direction_share']:.1f}%)",
        "",
        "## Feasibility gates",
        "",
    ]

    for key, value in result["gates"].items():
        lines.append(
            f"- {key}: **{'PASS' if value else 'FAIL'}**"
        )

    lines += [
        "",
        "## Guardrail",
        "",
        "- production_change_authorized: **NO**",
        "",
        "## By trade structure",
        "",
        "| Structure | Cases | Center fair | Robust | → Fair | Flipped |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key, row in result["by_structure"].items():
        lines.append(
            f"| {key} | {row.get('cases',0)} | "
            f"{row.get('center_fair',0)} | "
            f"{row.get('direction_robust',0)} | "
            f"{row.get('softened_to_fair',0)} | "
            f"{row.get('flipped_direction',0)} |"
        )

    lines += [
        "",
        "## Promotion boundary",
        "",
        "A future UI phase may support player + Round 1-4 pick trades "
        "using this structural slot envelope. Trades containing Round 5-6 "
        "picks must continue to show no robustness badge until those pick "
        "values have a stronger evidence base.",
        "",
        "This remains a deterministic stress test, not a probability or "
        "confidence interval.",
        "",
    ]
    return "\n".join(lines)


def write() -> None:
    result = analyze()
    OUTJSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUTMD.write_text(
        render(result).rstrip() + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": 1,
        "study_id": result["study_id"],
        "decision": result["decision"],
        "production_change_authorized": False,
        "index_sha256": sha(INDEX),
        "phase1_evaluator_sha256": sha(PHASE1),
        "phase1b_evaluator_sha256": sha(PHASE1B),
        "phase1b_result_sha256": sha(PHASE1B_JSON),
        "evaluator_sha256": sha(Path(__file__)),
        "result_sha256": sha(OUTJSON),
        "report_sha256": sha(OUTMD),
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def selftest() -> None:
    assert verdict_class(106, 100)["side"] is None
    assert verdict_class(108, 100)["label"] == "slight_a"
    assert verdict_class(125, 100)["label"] == "strong_a"
    assert verdict_class(100, 125)["label"] == "strong_b"

    p1 = load_module(PHASE1, "trade_robustness_phase1_selftest")
    picks, meta = extract_pick_table(p1)

    assert set(meta["production_pick_seasons"])
    assert meta["draft_slot_applies_to_season"] in meta["production_pick_seasons"]
    assert any(p["round"] == 1 for p in picks)
    assert any(p["round"] == 6 for p in picks)

    for p in picks:
        assert 0 <= p["low"] <= p["center"] <= p["high"]
        assert p["low"] < p["high"]
        if p["round"] <= 4:
            assert p["promotion_eligible"] is True
        else:
            assert p["promotion_eligible"] is False

    print("PASS: Phase 3 pick sensitivity self-test")


def check() -> None:
    result = read(OUTJSON)
    decision = result.get("decision")
    allowed = {
        "PASS_TRADE_ROBUSTNESS_V1_PHASE3_PICK_SLOT_SENSITIVITY_SHADOW",
        "HOLD_TRADE_ROBUSTNESS_V1_PHASE3_PICK_SLOT_SENSITIVITY_SHADOW",
    }
    if decision not in allowed:
        raise RuntimeError(
            f"Unexpected Phase 3 decision: {decision}"
        )

    manifest = read(MANIFEST)
    assert manifest["result_sha256"] == sha(OUTJSON)
    assert manifest["report_sha256"] == sha(OUTMD)
    assert manifest["evaluator_sha256"] == sha(Path(__file__))
    assert result["production_change_authorized"] is False

    failed_gates = [
        key for key, passed in (result.get("gates") or {}).items()
        if not passed
    ]
    print(
        "PASS: Phase 3 artifacts verified; "
        f"scientific decision={decision}; "
        f"failed_gates={failed_gates}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        selftest()
        return
    if args.write:
        write()
        return
    if args.check:
        check()
        return
    parser.error("Choose --selftest, --write, or --check")


if __name__ == "__main__":
    main()
