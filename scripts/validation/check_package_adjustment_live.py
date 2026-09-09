#!/usr/bin/env python3
"""Permanent regression checks for the controlled-live Package Adjustment.

This validator protects the exact V1.5 live contract:
- frozen V3/V4 evidence-bounded formula
- supported-position scope
- tiny-padding invariance
- unsupported-shape fail-closed behavior
- K exclusion and IDP parity
- frozen release/evidence lineage
- exact-live OOS monitor alignment

It intentionally does not use network access.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

INDEX = REPO_ROOT / "index.html"
LIVE = REPO_ROOT / "research/package-adjustment-production-candidate-v1/live_deployment.json"
PLAN = REPO_ROOT / "research/package-adjustment-production-candidate-v1/audit_clean_plan.md"
STEP6 = REPO_ROOT / "research/package-adjustment-production-candidate-v1/audit_step6_policy_hardening.json"
PRELAUNCH_FREEZE = REPO_ROOT / "research/package-adjustment-production-candidate-v1/prelaunch-vote-freeze/manifest.json"
V1_4_MANIFEST = REPO_ROOT / "research/package-adjustment-production-candidate-v1/prospective/release_manifest.json"
V1_5_MANIFEST = REPO_ROOT / "research/package-adjustment-production-candidate-v1/prospective/release_manifest_v1_5.json"
OOS_VALIDATION = REPO_ROOT / "research/package-adjustment-production-candidate-v1/prospective/exact_live_oos_validation.json"
V3 = REPO_ROOT / "research/package-adjustment-v3/package_vote_challenges_v3.json"
V4 = REPO_ROOT / "research/package-adjustment-v4/package_vote_challenges_v4.json"
MONITOR_WORKFLOW = REPO_ROOT / ".github/workflows/package-adjustment-audit-step4-exact-live-oos.yml"

EXPECTED_POSITIONS = ["QB", "RB", "WR", "TE", "DL", "LB", "DB"]
EPS = 1e-12


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(obj) -> str:
    payload = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _extract_number(text: str, pattern: str, label: str) -> float:
    m = re.search(pattern, text, flags=re.S)
    assert m, f"could not extract {label} from live index"
    return float(m.group(1))


def _extract_envelope(text: str, object_name: str, fields):
    m = re.search(
        rf"{re.escape(object_name)}:\s*Object\.freeze\(\{{(.*?)\}}\),",
        text,
        flags=re.S,
    )
    assert m, f"could not extract {object_name}"
    body = m.group(1)
    out = {}
    for field in fields:
        fm = re.search(rf"\b{re.escape(field)}:\s*([0-9.eE+-]+)", body)
        assert fm, f"could not extract {object_name}.{field}"
        out[field] = float(fm.group(1))
    pm = re.search(r"\bpolicy:\s*'([^']+)'", body)
    assert pm, f"could not extract {object_name}.policy"
    out["policy"] = pm.group(1)
    return out


def _extract_exact_formula(index_text: str):
    meaningful = _extract_number(
        index_text,
        r"meaningfulPieceMinTargetShare:\s*([0-9.eE+-]+)",
        "meaningfulPieceMinTargetShare",
    )
    size3_multiplier = _extract_number(
        index_text,
        r"size3Multiplier:\s*([0-9.eE+-]+)",
        "size3Multiplier",
    )

    pm = re.search(
        r"supportedPlayerPositions:\s*Object\.freeze\(\[(.*?)\]\),",
        index_text,
        flags=re.S,
    )
    assert pm, "could not extract supportedPlayerPositions"
    positions = re.findall(r"['\"]([A-Z]+)['\"]", pm.group(1))
    assert positions == EXPECTED_POSITIONS, (
        f"live Package Adjustment position scope drift: {positions}"
    )

    size2_env = _extract_envelope(
        index_text,
        "size2CompositionEnvelope",
        ("largestMin", "largestMax", "smallestMin", "smallestMax"),
    )
    size3_env = _extract_envelope(
        index_text,
        "size3CompositionEnvelope",
        (
            "largestMin", "largestMax",
            "middleMin", "middleMax",
            "smallestMin", "smallestMax",
        ),
    )

    rm = re.search(
        r"size2ReferencePoints:\s*Object\.freeze\(\[(.*?)\]\),",
        index_text,
        flags=re.S,
    )
    assert rm, "could not extract size2ReferencePoints"
    refs = [
        {"target_fv": float(target), "ratio": float(ratio)}
        for target, ratio in re.findall(
            r"targetFv:\s*([0-9.eE+-]+)\s*,\s*ratio:\s*([0-9.eE+-]+)",
            rm.group(1),
        )
    ]
    assert len(refs) == 4, f"expected 4 size2 reference points, found {len(refs)}"
    refs.sort(key=lambda r: r["target_fv"])

    required_tokens = (
        "function packageAdjustmentAssessment(){",
        "allAssets.some(a => a.type !== 'player')",
        "PACKAGE_ADJUSTMENT_PRODUCTION_V1.supportedPlayerPositions",
        ".filter(pos => !supportedPositions.includes(pos))",
        "reason:'unsupported_position'",
        "if(aAssets.length === 1 && bAssets.length >= 2){",
        "else if(bAssets.length === 1 && aAssets.length >= 2){",
        "packageValues.some(v => v >= targetFv)",
        "if(meaningful.length > 3){",
        "PACKAGE_ADJUSTMENT_PRODUCTION_V1.size2CompositionEnvelope",
        "PACKAGE_ADJUSTMENT_PRODUCTION_V1.size3CompositionEnvelope",
        "const rawPackageFv = packageValues.reduce((s,v) => s + v, 0);",
        "const meaningfulPackageFv = meaningful.reduce((s,v) => s + v, 0);",
        "function packageAdjustmentForTrade(){",
        "Package Adjustment · Not Applied",
        "Raw Fundamental Value and the normal trade verdict still apply.",
    )
    missing = [token for token in required_tokens if token not in index_text]
    assert not missing, f"Package Adjustment live/UI contract markers missing: {missing}"

    return {
        "meaningful_piece_min_target_share": meaningful,
        "size2": {
            "source": "V3 ratio_plus_size_target",
            "reference_points": refs,
            "composition_policy": size2_env["policy"],
            "composition_envelope": {
                "largest_min": size2_env["largestMin"],
                "largest_max": size2_env["largestMax"],
                "smallest_min": size2_env["smallestMin"],
                "smallest_max": size2_env["smallestMax"],
                "comparison_epsilon": EPS,
            },
        },
        "size3": {
            "source": "V4 ratio_only",
            "multiplier": size3_multiplier,
            "composition_policy": size3_env["policy"],
            "composition_envelope": {
                "largest_min": size3_env["largestMin"],
                "largest_max": size3_env["largestMax"],
                "middle_min": size3_env["middleMin"],
                "middle_max": size3_env["middleMax"],
                "smallest_min": size3_env["smallestMin"],
                "smallest_max": size3_env["smallestMax"],
                "comparison_epsilon": EPS,
            },
        },
        "scope_contract": {
            "player_only": True,
            "supported_player_positions": positions,
            "position_scope_policy": (
                "frozen_v3_v4_target_and_package_position_intersection_fail_closed"
            ),
            "one_for_package_only": True,
            "package_piece_must_be_below_target": True,
            "meaningful_package_sizes": [2, 3],
            "tiny_pieces_count_in_raw_package_fv": True,
            "tiny_pieces_excluded_from_composition": True,
            "unsupported_composition_fails_closed": True,
        },
    }


def _extract_balanced_statement(
    text: str,
    marker: str,
    open_char: str = "{",
    close_char: str = "}",
):
    start = text.find(marker)
    assert start >= 0, f"missing JS marker: {marker}"
    open_idx = text.find(open_char, start)
    assert open_idx >= 0, f"missing opening {open_char}: {marker}"

    depth = 0
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    i = open_idx

    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if line_comment:
            if ch == "\n":
                line_comment = False
            i += 1
            continue

        if block_comment:
            if ch == "*" and nxt == "/":
                block_comment = False
                i += 2
                continue
            i += 1
            continue

        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            i += 1
            continue

        if ch == "/" and nxt == "/":
            line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            block_comment = True
            i += 2
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            continue

        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                end = i + 1
                while end < len(text) and text[end].isspace():
                    end += 1
                if end < len(text) and text[end] == ";":
                    end += 1
                return text[start:end]
        i += 1

    raise AssertionError(f"unbalanced JS statement: {marker}")


def _extract_function(text: str, name: str):
    return _extract_balanced_statement(text, f"function {name}(")


def _extract_const_object(text: str, name: str):
    return _extract_balanced_statement(text, f"const {name} =")


def _extract_package_adjustment_config(text: str):
    """Extract the complete Object.freeze({...}); config statement."""
    start_marker = "const PACKAGE_ADJUSTMENT_PRODUCTION_V1 = Object.freeze({"
    end_marker = "function packageAdjustmentSize2Multiplier("
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    assert start >= 0, "missing Package Adjustment production config"
    assert end > start, "missing packageAdjustmentSize2Multiplier after config"
    block = text[start:end].strip()
    assert block.endswith(");"), (
        "Package Adjustment config extraction lost Object.freeze closure"
    )
    return block


def _run_live_js_behavior_tests(index_text: str):
    parts = [
        _extract_package_adjustment_config(index_text),
        _extract_function(index_text, "packageAdjustmentSize2Multiplier"),
        _extract_function(index_text, "packageAdjustmentAssessment"),
        _extract_function(index_text, "packageAdjustmentForTrade"),
        _extract_function(index_text, "sideTotal"),
        _extract_function(index_text, "tradeVerdictTotals"),
    ]

    harness = r"""
let state = {A:[], B:[]};

function player(pos, value, name='P'){
  return {type:'player', pos, value, name};
}
function pick(value=1000){
  return {type:'pick', value, name:'Pick'};
}
function assess(a,b){
  state = {A:a, B:b};
  return packageAdjustmentAssessment();
}
function check(cond, msg){
  if(!cond) throw new Error(msg);
}
function close(a,b,msg){
  if(Math.abs(Number(a)-Number(b)) > 1e-9){
    throw new Error(`${msg}: ${a} != ${b}`);
  }
}

let r, base, padded, totals;

// Supported V3 size2 — offense.
r = assess(
  [player('QB',5000,'Target')],
  [player('RB',2550),player('WR',2450)]
);
check(r.status === 'applied', '51/49 offense size2 must apply');
check(r.packageAdjustment.meaningfulCount === 2, 'size2 meaningful count');
check(r.packageAdjustment.compositionSupported === true, 'size2 composition flag');

base = r.packageAdjustment;
totals = tradeVerdictTotals();
close(totals.A, 5000 + base.adjustment, 'target side must receive adjustment');
close(totals.B, 5000, 'package side must remain raw FV');

// Direction symmetry.
r = assess(
  [player('RB',2550),player('WR',2450)],
  [player('QB',5000,'Target')]
);
check(r.status === 'applied', 'reverse-side 51/49 must apply');
totals = tradeVerdictTotals();
close(totals.A, 5000, 'reverse package side raw FV');
close(totals.B, 5000 + r.packageAdjustment.adjustment, 'reverse target adjusted');

// IDP parity.
r = assess(
  [player('DL',5000,'IDP Target')],
  [player('LB',2550),player('DB',2450)]
);
check(r.status === 'applied', 'DL/LB/DB must use same size2 rules');

// Supported V4 size3.
r = assess(
  [player('QB',5000,'Target')],
  [player('RB',2250),player('LB',1650),player('DB',1100)]
);
check(r.status === 'applied', '45/33/22 size3 must apply');
check(r.packageAdjustment.meaningfulCount === 3, 'size3 meaningful count');
check(r.packageAdjustment.premiumTier === '3-player', 'size3 tier');

// Tiny padding on size2: full raw FV, no composition dilution.
r = assess(
  [player('QB',5000,'Target')],
  [player('RB',2550),player('WR',2450)]
);
base = r.packageAdjustment;
r = assess(
  [player('QB',5000,'Target')],
  [player('RB',2550),player('WR',2450),player('DB',200)]
);
check(r.status === 'applied', 'tiny-padded size2 must still apply');
padded = r.packageAdjustment;
check(padded.meaningfulCount === 2, 'tiny piece excluded from size');
close(padded.rawPackageFv, 5200, 'tiny piece retained in raw package FV');
close(padded.meaningfulPackageFv, 5000, 'meaningful FV unchanged');
close(padded.tinyPackageFv, 200, 'tiny FV tracked');
close(padded.adjustment, base.adjustment, 'tiny padding cannot change target premium');

// Tiny fourth on supported size3.
r = assess(
  [player('QB',5000,'Target')],
  [player('RB',2250),player('LB',1650),player('DB',1100)]
);
base = r.packageAdjustment;
r = assess(
  [player('QB',5000,'Target')],
  [player('RB',2250),player('LB',1650),player('DB',1100),player('TE',200)]
);
check(r.status === 'applied', 'tiny fourth must preserve size3 treatment');
check(r.packageAdjustment.meaningfulCount === 3, 'tiny fourth excluded from size3 classification');
close(r.packageAdjustment.adjustment, base.adjustment, 'tiny fourth cannot change size3 premium');

// Unsupported composition / size.
r = assess(
  [player('QB',5000,'Target')],
  [player('RB',3000),player('WR',2000)]
);
check(r.status === 'unsupported', '60/40 size2 must fail closed');
check(r.reason === 'size2_composition_outside_frozen_v3_envelope', '60/40 reason');

r = assess(
  [player('QB',5000,'Target')],
  [player('RB',2750),player('WR',1200),player('TE',1050)]
);
check(r.status === 'unsupported', '55/24/21 size3 must fail closed');
check(r.reason === 'size3_composition_outside_frozen_v4_envelope', '55/24/21 reason');

r = assess(
  [player('QB',5000,'Target')],
  [player('RB',1300),player('WR',1250),player('TE',1250),player('LB',1200)]
);
check(r.status === 'unsupported', '4 meaningful players must fail closed');
check(r.reason === 'more_than_three_meaningful_players', '4 meaningful reason');

// Scope guards.
r = assess(
  [player('K',5000,'K Target')],
  [player('RB',2550),player('WR',2450)]
);
check(r.status === 'unsupported', 'K target must fail closed');
check(r.reason === 'unsupported_position', 'K target reason');

r = assess(
  [player('QB',5000,'Target')],
  [player('K',2550),player('WR',2450)]
);
check(r.status === 'unsupported', 'K package player must fail closed');
check(r.reason === 'unsupported_position', 'K package reason');

r = assess(
  [player('QB',5000,'Target')],
  [player('RB',2550),pick(2450)]
);
check(r.status === 'unsupported', 'pick-containing package must be unsupported');
check(r.reason === 'player_only_scope', 'pick scope reason');

r = assess(
  [player('QB',2500),player('RB',2400)],
  [player('WR',2500),player('TE',2400)]
);
check(r.status === 'unsupported', 'multi-v-multi must be unsupported');
check(r.reason === 'multi_vs_multi', 'multi-v-multi reason');

r = assess(
  [player('QB',5000,'Target')],
  [player('RB',5000),player('WR',1000)]
);
check(r.status === 'unsupported', 'package asset >= target must fail closed');
check(r.reason === 'package_piece_at_or_above_target', 'target-equal reason');

// True/effective 1-for-1 are quiet, not warnings.
r = assess([player('QB',5000)], [player('RB',2500)]);
check(r.status === 'not_applicable', '1-for-1 must remain not applicable');
check(r.reason === 'one_for_one', '1-for-1 reason');

r = assess(
  [player('QB',5000)],
  [player('RB',2500),player('DB',200)]
);
check(r.status === 'not_applicable', 'effective 1-for-1 must remain not applicable');
check(r.reason === 'effective_one_for_one_after_tiny_filter', 'effective 1-for-1 reason');

process.stdout.write(JSON.stringify({status:'PASS', cases:15}));
"""

    js = "\n\n".join(parts) + "\n" + harness
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".js",
        delete=False,
        encoding="utf-8",
    ) as fh:
        fh.write(js)
        tmp = fh.name

    try:
        proc = subprocess.run(
            ["node", tmp],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(
                "Package Adjustment live-JS harness failed.\n"
                f"STDOUT:\n{proc.stdout}\n"
                f"STDERR:\n{proc.stderr}"
            )
        return json.loads(proc.stdout)
    finally:
        os.unlink(tmp)


def _validate_frozen_lineage(v1_5, prelaunch):
    assert v1_5.get("frozen") is True
    assert v1_5.get("status") == "exact_live_oos_release_manifest"
    assert v1_5.get("release_id") == (
        "package-adjustment-exact-live-v1.5-step6-realignment"
    )
    assert v1_5.get("production_revision_at_release") == (
        "v1.5-audit-step6-scope-ui-idp"
    )

    v1_4 = _read_json(V1_4_MANIFEST)
    assert v1_4.get("frozen") is True
    assert v1_4.get("release_id") == "package-adjustment-exact-live-v1.4-step4"
    assert _sha256(V1_4_MANIFEST) == v1_5.get("previous_release_manifest_sha256")
    assert v1_5.get("supersedes_for_active_monitoring") == v1_4["release_id"]

    hashes = v1_5["release_artifact_sha256"]
    assert _sha256(V3) == hashes["v3_frozen_catalog"]
    assert _sha256(V4) == hashes["v4_frozen_catalog"]
    assert _sha256(STEP6) == hashes["step6_hardening"]
    assert _sha256(MONITOR_WORKFLOW) == hashes["monitor_workflow"]

    assert prelaunch.get("frozen") is True
    assert prelaunch.get("status") == "package_adjustment_prelaunch_vote_evidence_freeze"

    for key, row in (prelaunch.get("frozen_files") or {}).items():
        snap = REPO_ROOT / row["snapshot_path"]
        assert snap.exists(), f"missing frozen prelaunch snapshot: {key}"
        assert _sha256(snap) == row["sha256"], (
            f"frozen prelaunch snapshot drift: {key}"
        )

    # Source challenge catalogs themselves remain frozen and match the
    # byte-for-byte snapshots that calibrated production.
    for key, source in (
        ("v3_challenges", V3),
        ("v4_challenges", V4),
    ):
        row = prelaunch["frozen_files"][key]
        assert _sha256(source) == row["sha256"], (
            f"frozen calibration catalog drift: {key}"
        )


def validate():
    required = (
        INDEX, LIVE, PLAN, STEP6, PRELAUNCH_FREEZE,
        V1_4_MANIFEST, V1_5_MANIFEST, OOS_VALIDATION,
        V3, V4, MONITOR_WORKFLOW,
    )
    for path in required:
        assert path.exists(), f"missing Package Adjustment regression artifact: {path}"

    index_text = INDEX.read_text(encoding="utf-8")
    live = _read_json(LIVE)
    step6 = _read_json(STEP6)
    prelaunch = _read_json(PRELAUNCH_FREEZE)
    v1_5 = _read_json(V1_5_MANIFEST)
    oos = _read_json(OOS_VALIDATION)

    assert live.get("status") == "controlled_live"
    assert live.get("production_formula_enabled") is True
    assert live.get("production_revision") == v1_5["production_revision_at_release"]
    assert live.get("exact_live_prospective_monitoring") is True
    assert live.get("monitoring_release_id") == v1_5["release_id"]

    # Only the trade verdict is allowed to consume Package Adjustment.
    assert live.get("fundamental_value_consumer_changed") is False
    assert live.get("market_value_consumer_changed") is False
    assert live.get("draft_pick_value_consumer_changed") is False
    assert live.get("team_utility_consumer_changed") is False
    assert live.get("trade_verdict_consumer_changed") is True

    hardening = live.get("audit_hardening") or {}
    required_true_flags = (
        "size2_tiny_padding_invariance",
        "tiny_fourth_padding_invariance",
        "fourth_meaningful_piece_still_unsupported",
        "size2_v3_composition_envelope",
        "size3_v4_composition_envelope",
        "unsupported_size2_shape_fail_closed",
        "unsupported_size3_shape_fail_closed",
        "evidence_bounded_position_scope_guard",
        "kicker_package_adjustment_excluded",
        "idp_uses_same_package_adjustment_rules_as_offense",
        "unsupported_scope_ui_reason",
        "one_for_one_remains_quiet_not_applicable",
        "exact_live_monitor_revision_aligned",
        "exact_live_prospective_monitoring",
        "step6_gate_complete",
        "permanent_package_adjustment_regression_suite",
        "step7_gate_complete",
    )
    missing_flags = [k for k in required_true_flags if hardening.get(k) is not True]
    assert not missing_flags, f"Package Adjustment hardening flag drift: {missing_flags}"
    assert hardening.get("step6_monitor_realign_required") is False

    exact = _extract_exact_formula(index_text)
    assert exact == v1_5["exact_live_formula"], (
        "live Package Adjustment formula/scope differs from frozen V1.5 release"
    )
    assert _canonical_hash(exact) == v1_5["exact_live_formula_sha256"], (
        "live Package Adjustment formula fingerprint drift"
    )

    lf = live["formula"]
    assert lf["supported_player_positions"] == EXPECTED_POSITIONS
    assert lf["position_scope_policy"] == exact["scope_contract"]["position_scope_policy"]
    assert abs(
        float(lf["meaningful_piece_min_target_share"])
        - exact["meaningful_piece_min_target_share"]
    ) <= EPS
    assert abs(float(lf["size3_multiplier"]) - exact["size3"]["multiplier"]) <= EPS

    assert step6.get("kicker_excluded") is True
    assert step6.get("idp_same_rules_as_offense") is True
    assert step6.get("supported_player_positions") == EXPECTED_POSITIONS

    _validate_frozen_lineage(v1_5, prelaunch)

    assert oos.get("status") == "controlled_live_exact_formula_prospective_oos_monitoring"
    assert oos.get("release", {}).get("release_id") == v1_5["release_id"]
    assert oos.get("release", {}).get("exact_live_formula_sha256") == (
        v1_5["exact_live_formula_sha256"]
    )
    assert oos.get("methodology", {}).get("supported_player_positions") == (
        EXPECTED_POSITIONS
    )
    assert oos.get("methodology", {}).get("unsupported_positions_fail_closed") is True
    assert oos.get("automatic_production_change_allowed") is False
    assert oos.get("consumer_changed") is False

    plan = PLAN.read_text(encoding="utf-8")
    assert "- [x] Step 6 — Unsupported-shape UI + scope guards + IDP consistency" in plan
    assert "- [x] Step 7 — Permanent Package Adjustment repo regression suite" in plan

    js_result = _run_live_js_behavior_tests(index_text)
    assert js_result["status"] == "PASS"
    assert js_result["cases"] == 15

    result = {
        "status": "PASS",
        "production_revision": live["production_revision"],
        "release_id": v1_5["release_id"],
        "exact_live_formula_sha256": v1_5["exact_live_formula_sha256"],
        "supported_positions": EXPECTED_POSITIONS,
        "synthetic_cases_checked": js_result["cases"],
        "frozen_prelaunch_files_checked": len(prelaunch["frozen_files"]),
        "v1_4_release_preserved": True,
        "v1_5_release_frozen": True,
        "oos_monitor_revision_aligned": True,
    }

    print(
        "PASS Package Adjustment permanent invariants: "
        f"{result['synthetic_cases_checked']} live-JS cases; "
        f"{len(EXPECTED_POSITIONS)} supported positions; "
        f"{result['frozen_prelaunch_files_checked']} frozen prelaunch files; "
        "V1.5 formula/monitor aligned"
    )
    return result


if __name__ == "__main__":
    validate()
