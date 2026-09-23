#!/usr/bin/env python3
"""Permanent controlled-live regression checks for Package Adjustment V1.7."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import package_adjustment_exact_live_oos_v1_7 as oos

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent.parent
INDEX = ROOT / "index.html"
LIVE = ROOT / "research/package-adjustment-production-candidate-v1/live_deployment.json"
MANIFEST = ROOT / "research/package-adjustment-production-candidate-v1/prospective/release_manifest_v1_7.json"
OOS = ROOT / "research/package-adjustment-production-candidate-v1/prospective/exact_live_oos_validation.json"
CANDIDATE = ROOT / "research/package-adjustment-v6/production_candidate_v1.json"
EVAL = ROOT / "research/package-adjustment-v6/prospective_evaluation_v1.json"
REVIEW = ROOT / "research/package-adjustment-v6/production_review_v1.json"
FROZEN = ROOT / "research/package-adjustment-v6/prospective_exact_1800_frozen_v1.json"
CATALOG = ROOT / "research/package-adjustment-v6/package_vote_challenges_v6_prospective_v1.json"
WORKFLOW = ROOT / ".github/workflows/package-adjustment-audit-step4-exact-live-oos.yml"
DISPATCHER = SCRIPT_DIR / "package_adjustment_exact_live_oos.py"
V17_MONITOR = SCRIPT_DIR / "package_adjustment_exact_live_oos_v1_7.py"

REVISION = "v1.7-v6-size3-c2-overlay"
CANDIDATE_ID = "package-adjustment-v6-c2-size3-overlay-candidate-v1"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


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
    start = text.find("const PACKAGE_ADJUSTMENT_PRODUCTION_V1 = Object.freeze({")
    end = text.find("function packageAdjustmentSize2Multiplier(", start)
    assert start >= 0 and end > start
    return text[start:end].strip()


def _run_js_behavior(index_text):
    parts = [
        _extract_config(index_text),
        _extract_function(index_text, "packageAdjustmentSize2Multiplier"),
        _extract_function(index_text, "packageAdjustmentSize2CompositionFactor"),
        _extract_function(index_text, "packageAdjustmentSize3V6Assessment"),
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
function close(a,b,m,t=1e-8){ if(Math.abs(Number(a)-Number(b))>t) throw new Error(`${m}: ${a} != ${b}`); }

let r, base, totals, vals, S, P;
let checked = 0;

r=assess([player('QB',5000)],[player('RB',2500),player('WR',2500)]);
check(r.status==='unsupported','50/50 legacy gap'); checked++;

r=assess([player('QB',5000)],[player('RB',2550),player('WR',2450)]);
check(r.status==='applied','51/49 V3'); check(r.packageAdjustment.premiumTier==='2-player','V3 tier'); checked++;

r=assess([player('QB',5000)],[player('RB',2750),player('WR',2250)]);
check(r.status==='applied','55/45 V5'); check(r.packageAdjustment.premiumTier==='2-player-v5','V5 tier'); checked++;

r=assess([player('WR',5896)],[player('WR',4153),player('WR',3258)]);
check(r.status==='applied','56/44 motivating case');
close(r.packageAdjustment.multiplier,1.7349100401248068,'56/44 multiplier',2e-9); checked++;

r=assess([player('QB',5000)],[player('RB',3000),player('WR',2000)]);
check(r.status==='applied','60/40 ceiling'); checked++;

r=assess([player('QB',5000)],[player('RB',3001),player('WR',1999)]);
check(r.status==='unsupported','above 60/40'); checked++;

r=assess([player('QB',5000)],[player('RB',3250),player('WR',1750)]);
check(r.status==='unsupported','65/35'); checked++;

base=assess([player('QB',5000)],[player('RB',2750),player('WR',2250)]).packageAdjustment;
r=assess([player('QB',5000)],[player('RB',2750),player('WR',2250),player('DB',250)]);
check(r.status==='applied','V5 tiny third');
close(r.packageAdjustment.multiplier,base.multiplier,'tiny preserves size2 multiplier'); checked++;

r=assess([player('QB',5000)],[player('RB',2250),player('LB',1650),player('DB',1100)]);
check(r.status==='applied','legacy V4 fallback');
check(r.packageAdjustment.premiumTier==='3-player','legacy V4 tier');
check(r.packageAdjustment.size3Source==='V4','legacy V4 source');
close(r.packageAdjustment.multiplier,2.0512371846911357,'legacy V4 multiplier'); checked++;

vals=[4000,2181.818181818182,1090.909090909091];
r=assess([player('QB',5000)],[player('RB',vals[0]),player('WR',vals[1]),player('TE',vals[2])]);
check(r.status==='applied','V6 55/30/15');
check(r.packageAdjustment.premiumTier==='3-player-v6','V6 tier');
check(r.packageAdjustment.size3Source==='V6','V6 source');
check(r.packageAdjustment.v6CompositionProfile==='55/30/15','V6 profile');
close(r.packageAdjustment.v6ApexLevel,0.8,'V6 apex');
S=vals.reduce((a,b)=>a+b,0);
P=Math.pow(vals.reduce((a,x)=>a+Math.pow(x,PACKAGE_ADJUSTMENT_PRODUCTION_V1.size3V6Q),0),1/PACKAGE_ADJUSTMENT_PRODUCTION_V1.size3V6Q);
close(r.packageAdjustment.multiplier,S/P,'V6 exact C2 translation',1e-9); checked++;

vals=[4000,2933.3333333333335,1955.5555555555557];
r=assess([player('QB',5000)],[player('RB',vals[0]),player('WR',vals[1]),player('TE',vals[2])]);
check(r.status==='applied','V6/V4 overlap');
check(r.packageAdjustment.premiumTier==='3-player-v6','V6 precedence'); checked++;

vals=[4500,2700,1800];
r=assess([player('QB',5000)],[player('RB',vals[0]),player('WR',vals[1]),player('TE',vals[2])]);
check(r.status==='applied','V6 50/30/20 apex .90');
check(r.packageAdjustment.v6CompositionProfile==='50/30/20','V6 profile 50/30/20');
close(r.packageAdjustment.v6ApexLevel,0.9,'V6 apex .90'); checked++;

vals=[3000,1636.3636363636363,818.1818181818181];
r=assess([player('QB',5000)],[player('RB',vals[0]),player('WR',vals[1]),player('TE',vals[2])]);
check(r.status==='unsupported','V6 bad apex fails closed'); checked++;

vals=[4000,1230.7692307692307,923.0769230769231];
r=assess([player('QB',5000)],[player('RB',vals[0]),player('WR',vals[1]),player('TE',vals[2])]);
check(r.status==='unsupported','V6 bad composition fails closed'); checked++;

vals=[4000,2181.818181818182,1090.909090909091];
r=assess([player('QB',5000)],[player('RB',vals[0]),player('WR',vals[1]),player('TE',vals[2]),player('DB',100)]);
check(r.status==='unsupported','V6 exact raw size3 guard'); checked++;

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

vals=[4000,2181.818181818182,1090.909090909091];
r=assess([player('RB',vals[0]),player('WR',vals[1]),player('TE',vals[2])],[player('QB',5000)]);
check(r.status==='applied','reverse V6');
check(r.packageAdjustment.premiumTier==='3-player-v6','reverse V6 tier'); checked++;

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
        INDEX, LIVE, MANIFEST, OOS, CANDIDATE, EVAL, REVIEW, FROZEN, CATALOG,
        WORKFLOW, DISPATCHER, V17_MONITOR,
    )
    missing = [str(p) for p in required if not p.exists()]
    assert not missing, f"Package Adjustment V1.7 required files missing: {missing}"

    live = _read(LIVE)
    manifest = _read(MANIFEST)
    oos_result = _read(OOS)
    candidate = _read(CANDIDATE)
    evaluation = _read(EVAL)
    review = _read(REVIEW)

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

    assert evaluation["primary_confirmation"]["primary_pass"] is True
    assert review["review_conclusion"]["primary_confirmation_passed"] is True
    assert review["review_conclusion"]["deployment_status"] == (
        "eligible_for_explicit_human_approval_under_strict_scope"
    )
    assert candidate["human_approval"]["confirmed"] is True
    assert candidate["frozen_c2"]["q"] == 2.9897594788655337

    formula = oos.extract_formula(INDEX.read_text(encoding="utf-8"))
    oos.verify_live_metadata(live, formula, candidate)
    oos.verify_release_manifest(manifest, live, formula, candidate)

    assert formula["size3"]["v6_c2_overlay"]["q"] == 2.9897594788655337
    assert formula["size3"]["v6_c2_overlay"]["max_abs_composition_share_error"] == 0.04
    assert formula["size3"]["v6_c2_overlay"]["max_abs_apex_ratio_error"] == 0.035
    assert formula["size3"]["v6_c2_overlay"]["apex_levels"] == [0.7, 0.8, 0.9, 0.97]
    assert len(formula["size3"]["v6_c2_overlay"]["composition_profiles"]) == 6

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
    assert "PACKAGE_ADJUSTMENT_V1_7_V6_C2_SIZE3" in text
    assert "pkg.premiumTier === '3-player-v6' ? 'V6' : 'V4'" in text
    assert "return `3-player package - ${version} - ${ratio}`;" in text
    assert "2-player consolidation - V3 + V5" in text

    behavior = _run_js_behavior(text)
    assert behavior["status"] == "PASS"
    assert behavior["checked"] >= 24

    print(
        "PASS controlled-live Package Adjustment V1.7: "
        f"{behavior['checked']} JS behavior cases; V3/V5 size2 preserved; "
        "V6 C2 size3 overlay evidence-bounded; V4 fallback preserved; "
        "exact-live OOS aligned"
    )
    return {
        "status": "PASS",
        "production_revision": REVISION,
        "candidate_spec_sha256": candidate["candidate_spec_sha256"],
        "exact_live_formula_sha256": manifest["exact_live_formula_sha256"],
        "js_behavior_cases_checked": behavior["checked"],
        "trade_verdict_only": True,
    }


if __name__ == "__main__":
    validate()
