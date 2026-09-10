#!/usr/bin/env python3
"""Permanent regression checks for controlled-live Package Adjustment V1.6.

Protects:
- frozen V1.5 target-sensitive size2 curve and V3 core;
- hardened V5 composition overlay only through 60/40;
- frozen V4 size3 behavior;
- fail-closed scope and tiny-piece semantics;
- candidate/evidence/release lineage;
- exact-live OOS dispatcher/monitor alignment;
- Trade Verdict-only consumer scope.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import package_adjustment_exact_live_oos_v1_6 as oos

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent.parent
INDEX = ROOT / "index.html"
LIVE = ROOT / "research/package-adjustment-production-candidate-v1/live_deployment.json"
MANIFEST = ROOT / "research/package-adjustment-production-candidate-v1/prospective/release_manifest_v1_6.json"
OOS = ROOT / "research/package-adjustment-production-candidate-v1/prospective/exact_live_oos_validation.json"
CANDIDATE = ROOT / "research/package-adjustment-v5/production_candidate_design.json"
SHADOW = ROOT / "research/package-adjustment-v5/shadow_regression_hardening.json"
READINESS = ROOT / "research/package-adjustment-v5/promotion_readiness.json"
OOS_READINESS = ROOT / "research/package-adjustment-v5/oos_monitor_v1_6_readiness.json"
HARDENING = ROOT / "research/package-adjustment-v5/evidence_hardening.json"
WORKFLOW = ROOT / ".github/workflows/package-adjustment-audit-step4-exact-live-oos.yml"
DISPATCHER = SCRIPT_DIR / "package_adjustment_exact_live_oos.py"
V16_MONITOR = SCRIPT_DIR / "package_adjustment_exact_live_oos_v1_6.py"

REVISION = "v1.6-v5-size2-composition-overlay"
CANDIDATE_ID = "package-adjustment-v5-size2-composition-overlay-candidate-v1"
EXPECTED_POSITIONS = ["QB", "RB", "WR", "TE", "DL", "LB", "DB"]

def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _extract_balanced(text, marker, open_char="{", close_char="}"):
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
                return text[start:i + 1]
        i += 1
    raise AssertionError(f"unbalanced JS block: {marker}")

def _extract_function(text, name):
    return _extract_balanced(text, f"function {name}(")

def _extract_config(text):
    start = text.find(
        "const PACKAGE_ADJUSTMENT_PRODUCTION_V1 = Object.freeze({"
    )
    end = text.find("function packageAdjustmentSize2Multiplier(", start)
    assert start >= 0 and end > start
    return text[start:end].strip()

def _run_js_behavior(index_text):
    parts = [
        _extract_config(index_text),
        _extract_function(index_text, "packageAdjustmentSize2Multiplier"),
        _extract_function(index_text, "packageAdjustmentSize2CompositionFactor"),
        _extract_function(index_text, "packageAdjustmentAssessment"),
        _extract_function(index_text, "packageAdjustmentForTrade"),
        _extract_function(index_text, "sideTotal"),
        _extract_function(index_text, "tradeVerdictTotals"),
    ]
    harness = r"""
let state = {A:[], B:[]};
function player(pos, value, name='P'){ return {type:'player',pos,value,name}; }
function pick(value=1000){ return {type:'pick',value,name:'Pick'}; }
function assess(a,b){ state={A:a,B:b}; return packageAdjustmentAssessment(); }
function check(v,m){ if(!v) throw new Error(m); }
function close(a,b,m,t=1e-9){ if(Math.abs(Number(a)-Number(b))>t) throw new Error(`${m}: ${a} != ${b}`); }

let r, base, padded, totals;
let checked = 0;

r=assess([player('QB',5000)],[player('RB',2500),player('WR',2500)]);
check(r.status==='unsupported','50/50 legacy gap'); checked++;

r=assess([player('QB',5000)],[player('RB',2550),player('WR',2450)]);
check(r.status==='applied','51/49 V3'); check(r.packageAdjustment.premiumTier==='2-player','V3 tier');
base=r.packageAdjustment; checked++;

r=assess([player('QB',5000)],[player('RB',2750),player('WR',2250)]);
check(r.status==='applied','55/45 V5'); check(r.packageAdjustment.premiumTier==='2-player-v5','V5 tier');
check(r.packageAdjustment.multiplier>packageAdjustmentSize2Multiplier(5000),'55/45 premium'); checked++;

r=assess([player('WR',5896)],[player('WR',4153),player('WR',3258)]);
check(r.status==='applied','56/44 motivating case');
close(r.packageAdjustment.multiplier,1.7349100401248068,'56/44 multiplier',2e-10); checked++;

r=assess([player('QB',5000)],[player('RB',3000),player('WR',2000)]);
check(r.status==='applied','60/40 ceiling');
close(r.packageAdjustment.multiplier,packageAdjustmentSize2Multiplier(5000),'60/40 baseline'); checked++;

r=assess([player('QB',5000)],[player('RB',3001),player('WR',1999)]);
check(r.status==='unsupported','above 60/40'); checked++;

r=assess([player('QB',5000)],[player('RB',3250),player('WR',1750)]);
check(r.status==='unsupported','65/35'); checked++;

base=assess([player('QB',5000)],[player('RB',2750),player('WR',2250)]).packageAdjustment;
r=assess([player('QB',5000)],[player('RB',2750),player('WR',2250),player('DB',250)]);
check(r.status==='applied','V5 tiny third');
close(r.packageAdjustment.multiplier,base.multiplier,'tiny does not alter multiplier');
close(r.packageAdjustment.rawPackageFv,5250,'tiny retained raw');
close(r.packageAdjustment.meaningfulPackageFv,5000,'tiny excluded meaningful');
close(r.packageAdjustment.tinyPackageFv,250,'tiny tracked'); checked++;

r=assess([player('QB',5000)],[player('RB',2250),player('LB',1650),player('DB',1100)]);
check(r.status==='applied','V4 45/33/22');
close(r.packageAdjustment.multiplier,2.0512371846911357,'V4 multiplier'); checked++;

r=assess([player('DL',5000)],[player('LB',2750),player('DB',2250)]);
check(r.status==='applied','IDP V5 parity'); checked++;

r=assess([player('QB',5000)],[player('RB',2750),player('K',2250)]);
check(r.status==='unsupported','K fail closed'); checked++;

r=assess([player('QB',5000)],[player('RB',5000),player('WR',1000)]);
check(r.status==='unsupported','piece >= target'); checked++;

r=assess([player('QB',5000)],[player('RB',2000),player('WR',1500),player('LB',1000),player('DB',500)]);
check(r.status==='unsupported','4 meaningful'); checked++;

r=assess([player('QB',5000)],[player('RB',2750),pick(2250)]);
check(r.status==='unsupported','pick fail closed'); checked++;

r=assess([player('QB',2500),player('WR',2500)],[player('RB',2750),player('WR',2250)]);
check(r.status==='unsupported','multi-v-multi'); checked++;

r=assess([player('QB',5000)],[player('WR',5000)]);
check(r.status==='not_applicable','1-for-1 quiet'); checked++;

r=assess([player('RB',2750),player('WR',2250)],[player('QB',5000)]);
check(r.status==='applied','reverse V5');
totals=tradeVerdictTotals();
close(totals.A,5000,'reverse package raw');
check(totals.B>5000,'reverse target adjusted'); checked++;

r=assess([player('QB',5000)],[player('RB',2750),player('WR',2250)]);
totals=tradeVerdictTotals();
check(totals.A>5000,'target adjusted');
close(totals.B,5000,'package remains raw'); checked++;

process.stdout.write(JSON.stringify({status:'PASS',checked}));
"""
    js = "\n\n".join(parts) + "\n" + harness
    proc = subprocess.run(
        ["node", "-e", js],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)

def validate():
    required = (
        INDEX, LIVE, MANIFEST, OOS, CANDIDATE, SHADOW, READINESS,
        OOS_READINESS, HARDENING, WORKFLOW, DISPATCHER, V16_MONITOR,
    )
    missing = [str(p) for p in required if not p.exists()]
    assert not missing, f"Package Adjustment V1.6 required files missing: {missing}"

    live = _read(LIVE)
    manifest = _read(MANIFEST)
    oos_result = _read(OOS)
    candidate = _read(CANDIDATE)
    shadow = _read(SHADOW)
    readiness = _read(READINESS)
    oos_ready = _read(OOS_READINESS)

    assert live["status"] == "controlled_live"
    assert live["production_formula_enabled"] is True
    assert live["production_revision"] == REVISION
    assert live["package_adjustment_candidate_id"] == CANDIDATE_ID
    assert live["package_adjustment_candidate_spec_sha256"] == candidate["candidate_spec_sha256"]
    assert live["package_adjustment_evidence_fingerprint_sha256"] == candidate["source_evidence_fingerprint_sha256"]
    assert live["fundamental_value_consumer_changed"] is False
    assert live["market_value_consumer_changed"] is False
    assert live["draft_pick_value_consumer_changed"] is False
    assert live["team_utility_consumer_changed"] is False
    assert live["trade_verdict_consumer_changed"] is True

    assert candidate["candidate_spec_sha256"] == shadow["candidate_spec_sha256"]
    assert shadow["conclusion"]["shadow_regression_passed"] is True
    assert readiness["decision"]["candidate_ready_for_explicit_human_promotion_decision"] is True
    assert oos_ready["status"] == "v1_6_exact_live_oos_monitor_ready"
    assert _sha(V16_MONITOR) == oos_ready["v1_6_monitor_sha256"]

    formula = oos.extract_formula(INDEX.read_text(encoding="utf-8"))
    oos.verify_live_metadata(live, formula, candidate)
    oos.verify_release_manifest(manifest, live, formula, candidate, shadow)

    assert manifest["exact_live_formula_sha256"] == oos.canonical_hash(formula)
    assert manifest["release_artifact_sha256"]["permanent_live_validator"] == _sha(Path(__file__))
    assert manifest["release_artifact_sha256"]["hardening_evidence"] == _sha(HARDENING)
    assert manifest["release_artifact_sha256"]["promotion_readiness"] == _sha(READINESS)
    assert manifest["release_artifact_sha256"]["oos_monitor_readiness"] == _sha(OOS_READINESS)

    assert oos_result["status"] == "controlled_live_exact_formula_prospective_oos_monitoring"
    assert oos_result["release"]["production_revision_at_release"] == REVISION
    assert oos_result["release"]["release_id"] == manifest["release_id"]
    assert oos_result["release"]["exact_live_formula_sha256"] == manifest["exact_live_formula_sha256"]
    assert oos_result["automatic_production_change_allowed"] is False
    for key in (
        "consumer_changed",
        "fundamental_value_consumer_changed",
        "market_value_consumer_changed",
        "draft_pick_value_consumer_changed",
        "team_utility_consumer_changed",
        "trade_verdict_consumer_changed",
    ):
        assert oos_result[key] is False, f"OOS monitor unexpectedly changed {key}"

    text = INDEX.read_text(encoding="utf-8")
    assert "2-player consolidation · V3 + V5" in text
    behavior = _run_js_behavior(text)
    assert behavior["status"] == "PASS"
    assert behavior["checked"] >= 18

    result = {
        "status": "PASS",
        "production_revision": REVISION,
        "candidate_spec_sha256": candidate["candidate_spec_sha256"],
        "exact_live_formula_sha256": manifest["exact_live_formula_sha256"],
        "js_behavior_cases_checked": behavior["checked"],
        "trade_verdict_only": True,
        "support_ceiling": "60/40",
    }
    print(
        "PASS controlled-live Package Adjustment V1.6: "
        f"{behavior['checked']} JS behavior cases; V3/V4 preserved; "
        "V5 through 60/40; exact-live OOS aligned"
    )
    return result

if __name__ == "__main__":
    validate()
