#!/usr/bin/env python3
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
LIVE = ROOT / "research/package-adjustment-production-candidate-v1/live_deployment.json"
V15_MANIFEST = ROOT / "research/package-adjustment-production-candidate-v1/prospective/release_manifest_v1_5.json"
MONITOR = ROOT / ".github/workflows/package-adjustment-audit-step4-exact-live-oos.yml"
LIVE_CHECK = ROOT / "scripts/validation/check_package_adjustment_live.py"
CANDIDATE = ROOT / "research/package-adjustment-v5/production_candidate_design.json"
SHADOW = ROOT / "research/package-adjustment-v5/shadow_regression_hardening.json"
HARDENING = ROOT / "research/package-adjustment-v5/evidence_hardening.json"

OUT_JSON = ROOT / "research/package-adjustment-v5/promotion_readiness.json"
OUT_MD = ROOT / "research/package-adjustment-v5/promotion_readiness.md"
OUT_DIFF = ROOT / "research/package-adjustment-v5/proposed_index_v1_6.patch"
OUT_MANIFEST = ROOT / "research/package-adjustment-v5/release_manifest_v1_6_draft.json"
OUT_ROLLBACK = ROOT / "research/package-adjustment-v5/rollback_plan_v1_6.json"

PROPOSED_REVISION = "v1.6-v5-size2-composition-overlay"
PROPOSED_RELEASE_ID = "package-adjustment-controlled-live-v1.6-v5-composition"
EPS = 1e-12

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha256_bytes(data: bytes):
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path):
    return sha256_bytes(path.read_bytes())

def extract_balanced(text: str, marker: str, open_char="{", close_char="}"):
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"Missing marker: {marker}")
    open_idx = text.find(open_char, start)
    if open_idx < 0:
        raise RuntimeError(f"Missing opening {open_char}: {marker}")

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
                return start, i + 1
        i += 1

    raise RuntimeError(f"Unbalanced block: {marker}")

def extract_function(text: str, name: str):
    start, end = extract_balanced(text, f"function {name}(")
    return text[start:end]

def extract_config(text: str):
    marker = "const PACKAGE_ADJUSTMENT_PRODUCTION_V1 = Object.freeze({"
    start = text.find(marker)
    if start < 0:
        raise RuntimeError("Missing Package Adjustment config")
    func = text.find("function packageAdjustmentSize2Multiplier(", start)
    if func < 0:
        raise RuntimeError("Missing size2 multiplier function")
    return text[start:func].strip()

def replace_balanced_if(text: str, marker: str, replacement: str):
    start, end = extract_balanced(text, marker)
    return text[:start] + replacement + text[end:]

def patch_index(index_text: str, candidate: dict):
    f55 = float(candidate["multiplier_policy"]["candidate_factor_55_45"])
    f60 = float(candidate["multiplier_policy"]["candidate_factor_60_40"])
    v3_max = float(
        candidate["composition_policy"]["existing_v3_core_unchanged"]["largest_max"]
    )
    v5_max = float(
        candidate["composition_policy"]["v5_expansion_largest_share_max_inclusive"]
    )

    if "size2V5CompositionOverlay:" in index_text:
        raise RuntimeError("V5 overlay already present in production index")

    config_marker = "  size2ReferencePoints: Object.freeze(["
    if index_text.count(config_marker) != 1:
        raise RuntimeError("Unexpected size2ReferencePoints marker count")

    overlay_config = f"""  size2V5CompositionOverlay: Object.freeze({{
        policy: 'hardened-v5-composition-overlay-through-60-40-fail-closed',
        largestShareMinExclusive: {v3_max!r},
        largestShareMaxInclusive: {v5_max!r},
        factor55: {f55!r},
        factor60: {f60!r},
      }}),
    """

    patched = index_text.replace(
        config_marker,
        overlay_config + config_marker,
        1,
    )

    assess_marker = "function packageAdjustmentAssessment(){"
    if patched.count(assess_marker) != 1:
        raise RuntimeError("Unexpected packageAdjustmentAssessment marker count")

    helper = f"""
    function packageAdjustmentSize2CompositionFactor(largestShare, smallestShare){{
      const v3 = PACKAGE_ADJUSTMENT_PRODUCTION_V1.size2CompositionEnvelope;
      const v5 = PACKAGE_ADJUSTMENT_PRODUCTION_V1.size2V5CompositionOverlay;
      const compositionEpsilon = 1e-12;

      const inFrozenV3 =
        largestShare >= v3.largestMin - compositionEpsilon &&
        largestShare <= v3.largestMax + compositionEpsilon &&
        smallestShare >= v3.smallestMin - compositionEpsilon &&
        smallestShare <= v3.smallestMax + compositionEpsilon;

      if(inFrozenV3){{
        return {{supported:true, factor:1, source:'V3'}};
      }}

      if(
        !(largestShare > v5.largestShareMinExclusive + compositionEpsilon) ||
        largestShare > v5.largestShareMaxInclusive + compositionEpsilon
      ){{
        return {{supported:false, factor:null, source:null}};
      }}

      let factor = 1;
      if(largestShare <= 0.55){{
        const span = 0.55 - v5.largestShareMinExclusive;
        const w = span <= 0 ? 0 : (largestShare - v5.largestShareMinExclusive) / span;
        factor = 1 + w * (v5.factor55 - 1);
      }} else {{
        const span = 0.60 - 0.55;
        const w = span <= 0 ? 0 : (largestShare - 0.55) / span;
        factor = v5.factor55 + w * (v5.factor60 - v5.factor55);
      }}

      factor = Math.max(1, factor);
      return {{supported:true, factor, source:'V5'}};
    }}

    """

    patched = patched.replace(
        assess_marker,
        helper + assess_marker,
        1,
    )

    new_size2 = """if(meaningful.length === 2){
      const orderedMeaningful = [...meaningful].sort((a,b) => b - a);
      largestMeaningfulPackageShare = orderedMeaningful[0] / meaningfulPackageFv;
      smallestMeaningfulPackageShare = orderedMeaningful[1] / meaningfulPackageFv;

      const composition = packageAdjustmentSize2CompositionFactor(
        largestMeaningfulPackageShare,
        smallestMeaningfulPackageShare
      );
      compositionSupported = composition.supported;

      if(!compositionSupported){
        return {
          status:'unsupported',
          reason:'size2_composition_outside_evidence_supported_envelope',
          meaningfulCount: 2,
          largestMeaningfulPackageShare,
          smallestMeaningfulPackageShare,
          message:'This two-player package is outside the evidence-supported V3/V5 composition envelope.',
        };
      }

      multiplier = size2Multiplier * composition.factor;
      if(composition.source === 'V5'){
        premiumTier = '2-player-v5';
      }
    }"""

    patched = replace_balanced_if(
        patched,
        "if(meaningful.length === 2){",
        new_size2,
    )

    # Make the existing user-facing tier label distinguish the V5
    # expansion while leaving all other labels untouched.
    tier_pattern = (
        r"(pkg\.premiumTier === '3-player'\s*"
        r"\?\s*'3-player consolidation · V4'\s*"
        r":\s*)"
        r"(pkg\.premiumTier === '2-player \+ small third')"
    )
    tier_replacement = (
        r"\1pkg.premiumTier === '2-player-v5'\n"
        r"        ? '2-player consolidation · V3 + V5'\n"
        r"        : \2"
    )
    patched, count = re.subn(
        tier_pattern,
        tier_replacement,
        patched,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError("Could not inject V5 Package Adjustment tier label")

    return patched

def run_inline_syntax(index_text: str):
    scripts = re.findall(
        r"<script(?:\s[^>]*)?>(.*?)</script>",
        index_text,
        re.S | re.I,
    )
    js = "\n".join(scripts)
    fd, path = tempfile.mkstemp(suffix=".js")
    os.close(fd)
    try:
        Path(path).write_text(js, encoding="utf-8")
        subprocess.run(["node", "--check", path], check=True)
    finally:
        Path(path).unlink(missing_ok=True)

def run_behavior_harness(index_text: str):
    parts = [
        extract_config(index_text),
        extract_function(index_text, "packageAdjustmentSize2Multiplier"),
        extract_function(index_text, "packageAdjustmentSize2CompositionFactor"),
        extract_function(index_text, "packageAdjustmentAssessment"),
        extract_function(index_text, "packageAdjustmentForTrade"),
        extract_function(index_text, "sideTotal"),
        extract_function(index_text, "tradeVerdictTotals"),
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
    function close(a,b,msg,tol=1e-9){
      if(Math.abs(Number(a)-Number(b)) > tol){
        throw new Error(`${msg}: ${a} != ${b}`);
      }
    }

    let r, base, padded, totals;

    // Frozen V3 core remains exactly active.
    r = assess(
      [player('QB',5000,'Target')],
      [player('RB',2550),player('WR',2450)]
    );
    check(r.status === 'applied', '51/49 V3 core must apply');
    check(r.packageAdjustment.premiumTier === '2-player', 'V3 tier unchanged');

    // Existing lower gap remains fail closed.
    r = assess(
      [player('QB',5000,'Target')],
      [player('RB',2500),player('WR',2500)]
    );
    check(r.status === 'unsupported', '50/50 lower V3 gap must remain unsupported');

    // V5 55/45.
    r = assess(
      [player('QB',5000,'Target')],
      [player('RB',2750),player('WR',2250)]
    );
    check(r.status === 'applied', '55/45 V5 must apply');
    check(r.packageAdjustment.premiumTier === '2-player-v5', '55/45 must identify V5 tier');
    check(r.packageAdjustment.multiplier > packageAdjustmentSize2Multiplier(5000), '55/45 factor must add premium');

    // Motivating 56/44 case.
    r = assess(
      [player('WR',5896,'George Pickens')],
      [player('WR',4153,'Parker Washington'),player('WR',3258,'Jauan Jennings')]
    );
    check(r.status === 'applied', 'motivating 56/44 case must apply');
    check(r.packageAdjustment.premiumTier === '2-player-v5', 'motivating case must use V5 tier');
    close(r.packageAdjustment.multiplier, 1.73491004, 'motivating candidate multiplier', 2e-8);
    close(r.packageAdjustment.tradeEquivalentTargetFv, 10229.03, 'motivating trade-equivalent target FV', 0.02);

    // Exact 60/40 ceiling remains supported at live baseline factor.
    r = assess(
      [player('QB',5000,'Target')],
      [player('RB',3000),player('WR',2000)]
    );
    check(r.status === 'applied', '60/40 ceiling must apply');
    close(
      r.packageAdjustment.multiplier,
      packageAdjustmentSize2Multiplier(5000),
      '60/40 must return to live V1.5 baseline'
    );

    // Beyond 60/40 fails closed.
    r = assess(
      [player('QB',5000,'Target')],
      [player('RB',3001),player('WR',1999)]
    );
    check(r.status === 'unsupported', 'above 60/40 must fail closed');

    r = assess(
      [player('QB',5000,'Target')],
      [player('RB',3250),player('WR',1750)]
    );
    check(r.status === 'unsupported', '65/35 must fail closed');

    // Tiny throw-in: excluded from composition, retained in raw FV.
    base = assess(
      [player('QB',5000,'Target')],
      [player('RB',2800),player('WR',2200)]
    ).packageAdjustment;
    r = assess(
      [player('QB',5000,'Target')],
      [player('RB',2800),player('WR',2200),player('DB',250)]
    );
    check(r.status === 'applied', 'V5 + tiny third must apply');
    padded = r.packageAdjustment;
    close(padded.multiplier, base.multiplier, 'tiny third cannot alter V5 multiplier');
    close(padded.rawPackageFv, 5250, 'tiny third retained in raw FV');
    close(padded.meaningfulPackageFv, 5000, 'tiny third excluded from meaningful FV');
    close(padded.tinyPackageFv, 250, 'tiny third tracked');

    // Frozen V4 exact behavior remains active.
    r = assess(
      [player('QB',5000,'Target')],
      [player('RB',2250),player('LB',1650),player('DB',1100)]
    );
    check(r.status === 'applied', '45/33/22 V4 must apply');
    check(r.packageAdjustment.premiumTier === '3-player', 'V4 tier unchanged');
    close(r.packageAdjustment.multiplier, 2.0512371846911357, 'V4 multiplier unchanged');

    // Fail-closed scope remains.
    r = assess(
      [player('QB',5000,'Target')],
      [player('RB',2750),player('K',2250)]
    );
    check(r.status === 'unsupported', 'K must remain unsupported');

    r = assess(
      [player('QB',5000,'Target')],
      [player('RB',5000),player('WR',1000)]
    );
    check(r.status === 'unsupported', 'package piece >= target must remain unsupported');

    r = assess(
      [player('QB',5000,'Target')],
      [player('RB',2000),player('WR',1500),player('LB',1000),player('DB',500)]
    );
    check(r.status === 'unsupported', '4 meaningful players must remain unsupported');

    r = assess(
      [player('QB',5000,'Target')],
      [player('RB',2750),pick(2250)]
    );
    check(r.status === 'unsupported', 'picks must remain unsupported');

    // Direction symmetry for V5.
    r = assess(
      [player('RB',2750),player('WR',2250)],
      [player('QB',5000,'Target')]
    );
    check(r.status === 'applied', 'reverse-side 55/45 must apply');
    totals = tradeVerdictTotals();
    close(totals.A, 5000, 'V5 package side stays raw FV');
    check(totals.B > 5000, 'V5 target side receives adjustment');

    process.stdout.write(JSON.stringify({
      status:'PASS',
      motivatingMultiplier: assess(
        [player('WR',5896,'George Pickens')],
        [player('WR',4153),player('WR',3258)]
      ).packageAdjustment.multiplier
    }));
    """

    js = "\n\n".join(parts) + "\n" + harness
    proc = subprocess.run(
        ["node", "-e", js],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)

def main():
    candidate = read_json(CANDIDATE)
    shadow = read_json(SHADOW)
    hard = read_json(HARDENING)
    live = read_json(LIVE)

    if candidate.get("status") != "shadow_candidate_design_complete":
        raise RuntimeError("Unexpected candidate status")
    if shadow.get("status") != "shadow_regression_hardening_complete":
        raise RuntimeError("Shadow hardening is not complete")
    if shadow["conclusion"].get("shadow_regression_passed") is not True:
        raise RuntimeError("Shadow regression did not pass")
    if shadow["conclusion"].get("candidate_ready_for_human_promotion_review") is not True:
        raise RuntimeError("Shadow artifact does not permit human promotion review")
    if candidate["candidate_spec_sha256"] != shadow["candidate_spec_sha256"]:
        raise RuntimeError("Candidate/shadow spec hash mismatch")
    if (
        candidate["source_evidence_fingerprint_sha256"]
        != hard["evidence_freeze"]["evidence_fingerprint_sha256"]
    ):
        raise RuntimeError("Evidence fingerprint mismatch")
    if live.get("production_revision") != "v1.5-audit-step6-scope-ui-idp":
        raise RuntimeError("Current live revision drifted before readiness review")

    current = INDEX.read_text(encoding="utf-8")
    proposed = patch_index(current, candidate)

    if current == proposed:
        raise RuntimeError("Candidate patch produced no index change")
    if "size2V5CompositionOverlay:" not in proposed:
        raise RuntimeError("Proposed index missing V5 overlay config")
    if "function packageAdjustmentSize2CompositionFactor(" not in proposed:
        raise RuntimeError("Proposed index missing V5 composition helper")
    if "premiumTier = '2-player-v5';" not in proposed:
        raise RuntimeError("Proposed index missing V5 UI tier state")

    run_inline_syntax(proposed)
    behavior = run_behavior_harness(proposed)
    if behavior.get("status") != "PASS":
        raise RuntimeError(f"Proposed candidate behavior harness failed: {behavior}")

    patch = "".join(
        difflib.unified_diff(
            current.splitlines(keepends=True),
            proposed.splitlines(keepends=True),
            fromfile="a/index.html",
            tofile="b/index.html",
        )
    )
    if not patch:
        raise RuntimeError("Proposed index patch is empty")
    OUT_DIFF.write_text(patch, encoding="utf-8")

    current_sha = sha256_bytes(current.encode("utf-8"))
    proposed_sha = sha256_bytes(proposed.encode("utf-8"))

    required_promotion_changes = [
        "index.html",
        "scripts/validation/check_package_adjustment_live.py",
        "research/package-adjustment-production-candidate-v1/live_deployment.json",
        "research/package-adjustment-production-candidate-v1/prospective/release_manifest_v1_6.json",
    ]
    manual_monitor = ".github/workflows/package-adjustment-audit-step4-exact-live-oos.yml"

    rollback = {
        "schema_version": 1,
        "status": "draft_pre_promotion_rollback_plan",
        "current_production_revision": live["production_revision"],
        "proposed_production_revision": PROPOSED_REVISION,
        "pre_promotion_file_sha256": {
            "index.html": current_sha,
            "scripts/validation/check_package_adjustment_live.py": sha256_file(LIVE_CHECK),
            "research/package-adjustment-production-candidate-v1/live_deployment.json": sha256_file(LIVE),
            "research/package-adjustment-production-candidate-v1/prospective/release_manifest_v1_5.json": sha256_file(V15_MANIFEST),
            manual_monitor: sha256_file(MONITOR),
        },
        "rollback_method": (
            "revert_the_single_live_promotion_commit_then_restore_the_exact_pre_promotion_"
            "OOS_workflow_copy_if_the_monitor_was_replaced"
        ),
        "rollback_trigger_examples": [
            "permanent_package_adjustment_regression_failure",
            "exact_live_OOS_monitor_alignment_failure",
            "unexpected_consumer_change",
            "unexpected_support_above_60_40",
            "existing_V1_5_supported_case_semantics_drift",
        ],
        "automatic_rollback_allowed": False,
        "human_review_required": True,
    }
    OUT_ROLLBACK.write_text(
        json.dumps(rollback, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": 1,
        "status": "draft_not_deployed",
        "release_id": PROPOSED_RELEASE_ID,
        "production_revision": PROPOSED_REVISION,
        "candidate_id": candidate["candidate_id"],
        "candidate_spec_sha256": candidate["candidate_spec_sha256"],
        "source_evidence_fingerprint_sha256": candidate[
            "source_evidence_fingerprint_sha256"
        ],
        "source_counted_votes": candidate["source_counted_votes"],
        "pre_promotion_index_sha256": current_sha,
        "proposed_index_sha256": proposed_sha,
        "production_formula_enabled": False,
        "production_promotion_allowed": False,
        "automatic_production_change_allowed": False,
        "human_approval_required": True,
        "proposed_formula": {
            "baseline": "exact_v1_5_target_sensitive_size2_curve",
            "frozen_v3_core_unchanged": True,
            "v5_expansion_largest_share_min_exclusive": candidate[
                "composition_policy"
            ]["v5_expansion_largest_share_min_exclusive"],
            "v5_expansion_largest_share_max_inclusive": candidate[
                "composition_policy"
            ]["v5_expansion_largest_share_max_inclusive"],
            "factor_55_45": candidate["multiplier_policy"][
                "candidate_factor_55_45"
            ],
            "factor_60_40": candidate["multiplier_policy"][
                "candidate_factor_60_40"
            ],
            "factor_floor": 1.0,
            "interpolation": "piecewise_linear",
            "size3_v4_unchanged": True,
            "unsupported_above_60_40": True,
        },
        "consumer_scope": {
            "fundamental_value_changed": False,
            "market_value_changed": False,
            "draft_pick_value_changed": False,
            "team_utility_changed": False,
            "trade_verdict_only_if_promoted": True,
        },
        "required_live_commit_files": required_promotion_changes,
        "manual_workflow_alignment_required": True,
        "manual_workflow_alignment_path": manual_monitor,
        "post_promotion_required_checks": [
            "candidate_spec_hash_exact",
            "evidence_fingerprint_exact",
            "inline_javascript_syntax",
            "permanent_repo_regression_suite",
            "updated_package_adjustment_live_validator",
            "frozen_v3_core_behavior_parity",
            "frozen_v4_behavior_parity",
            "v5_55_45_60_40_boundaries",
            "tiny_throw_in_invariance",
            "unsupported_scope_fail_closed",
            "exact_live_OOS_monitor_alignment",
        ],
    }
    OUT_MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    review = {
        "schema_version": 1,
        "status": "promotion_readiness_review_complete",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_id": candidate["candidate_id"],
        "candidate_spec_sha256": candidate["candidate_spec_sha256"],
        "source_evidence_fingerprint_sha256": candidate[
            "source_evidence_fingerprint_sha256"
        ],
        "source_counted_votes": candidate["source_counted_votes"],
        "current_production_revision": live["production_revision"],
        "proposed_production_revision": PROPOSED_REVISION,
        "production_formula_changed": False,
        "live_change_performed": False,
        "production_promotion_allowed": False,
        "automatic_production_change_allowed": False,
        "fundamental_value_consumer_changed": False,
        "market_value_consumer_changed": False,
        "draft_pick_value_consumer_changed": False,
        "team_utility_consumer_changed": False,
        "trade_verdict_consumer_changed": False,
        "proposed_index_patch": {
            "current_index_sha256": current_sha,
            "proposed_index_sha256": proposed_sha,
            "patch_path": str(OUT_DIFF.relative_to(ROOT)),
            "inline_javascript_syntax_passed": True,
            "exact_candidate_behavior_harness_passed": True,
            "motivating_56_44_multiplier": behavior["motivatingMultiplier"],
        },
        "shadow_evidence": {
            "adversarial_cases_passed": shadow["validation"][
                "adversarial_cases_passed"
            ],
            "dense_sweep_cases": shadow["validation"]["dense_sweep"]["cases"],
            "existing_v1_5_applied_cases_changed": shadow["validation"][
                "dense_sweep"
            ]["existing_v1_5_applied_cases_changed"],
            "illegal_new_support_cases": shadow["validation"]["dense_sweep"][
                "illegal_new_support_cases"
            ],
            "new_support_above_60_40_cases": shadow["validation"][
                "dense_sweep"
            ]["new_support_above_60_40_cases"],
        },
        "release_choreography": {
            "live_promotion_must_be_explicitly_human_approved": True,
            "automatic_promotion": False,
            "workflow_permission_constraint": (
                "GitHub App cannot create/update workflow files from workflow-run commits"
            ),
            "monitor_alignment_required": True,
            "monitor_alignment_path": manual_monitor,
            "recommended_sequence": [
                "prepare_and_manually_upload_monitor_transition_or_final_v1_6_workflow",
                "verify_monitor_alignment_strategy_before_live_commit",
                "run_single controlled-live promotion workflow",
                "run repo regression and exact-live OOS validation immediately",
                "rollback if any production gate fails",
            ],
        },
        "decision": {
            "candidate_ready_for_explicit_human_promotion_decision": True,
            "candidate_automatically_approved": False,
            "remaining_non_formula_blocker": (
                "exact_live_OOS_monitor_workflow_must_be_realignable_despite_workflow_file_permission_constraint"
            ),
            "next_step": "prepare_monitor_realign_then_request_explicit_live_promotion_approval",
        },
    }
    OUT_JSON.write_text(
        json.dumps(review, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Package Adjustment V5 — Promotion Readiness Review",
        "",
        "**NO LIVE CHANGE PERFORMED.**",
        "",
        f"- Candidate: `{candidate['candidate_id']}`",
        f"- Candidate spec: `{candidate['candidate_spec_sha256']}`",
        f"- Frozen evidence: `{candidate['source_counted_votes']}` votes",
        f"- Current revision: `{live['production_revision']}`",
        f"- Proposed revision: `{PROPOSED_REVISION}`",
        "",
        "## Formula readiness",
        "",
        f"- Shadow adversarial cases: **{shadow['validation']['adversarial_cases_passed']} passed**",
        f"- Dense regression cases: **{shadow['validation']['dense_sweep']['cases']:,}**",
        "- Existing V1.5 applied cases changed: **0**",
        "- Illegal new support: **0**",
        "- Support above 60/40: **0**",
        "- Proposed patched-index JavaScript syntax: **PASS**",
        "- Proposed patched-index exact behavior harness: **PASS**",
        "",
        "## Proposed live behavior",
        "",
        "- Frozen V3 core stays unchanged.",
        "- V5 composition overlay applies only above the V3 core through 60/40.",
        f"- 55/45 factor: **{candidate['multiplier_policy']['candidate_factor_55_45']:.6f}x**",
        f"- 60/40 factor: **{candidate['multiplier_policy']['candidate_factor_60_40']:.6f}x**",
        "- 65/35+ remains unsupported.",
        "- V4 3-player logic remains unchanged.",
        "- FV, MV, draft-pick values, and Team Utility remain unchanged.",
        "",
        "## Remaining release blocker",
        "",
        "The formula itself is promotion-ready, but the exact-live OOS monitor is still an inline GitHub workflow. "
        "Because GitHub App commits cannot update workflow files, monitor realignment must be staged manually before/around promotion.",
        "",
        "This review therefore does **not** approve or perform a production change.",
        "",
        "## Generated release materials",
        "",
        "- Exact proposed `index.html` unified patch.",
        "- Draft V1.6 release manifest.",
        "- Pre-promotion rollback plan with exact current file hashes.",
        "",
        "## Next step",
        "",
        "Prepare the monitor-realignment workflow, verify it, then request explicit human approval for the controlled-live promotion.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print("Package Adjustment V5 promotion-readiness review complete.")
    print("Current index SHA:", current_sha)
    print("Proposed index SHA:", proposed_sha)
    print("Temporary patched-index syntax: PASS")
    print("Temporary patched-index behavior harness: PASS")
    print("Live production changed: False")
    print("Next: monitor realignment before explicit promotion decision.")

if __name__ == "__main__":
    main()
