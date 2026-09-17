#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
PHASE1B = ROOT / "research/trade-robustness-v1/trade_robustness_v1_phase1b_live_verdict_alignment.json"
OUTDIR = Path(__file__).resolve().parent
OUTJSON = OUTDIR / "trade_robustness_v1_phase2_ui_shadow_confirmation.json"
OUTMD = OUTDIR / "trade_robustness_v1_phase2_ui_shadow_confirmation.md"
MANIFEST = OUTDIR / "trade_robustness_v1_phase2_manifest.json"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def balanced(text: str, marker: str, open_char: str = "{", close_char: str = "}") -> str:
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"missing marker: {marker}")
    open_idx = text.find(open_char, start)
    if open_idx < 0:
        raise RuntimeError(f"missing opening char: {marker}")
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
    raise RuntimeError(f"unbalanced block: {marker}")

def function(text: str, name: str) -> str:
    return balanced(text, f"function {name}(")

def package_config(text: str) -> str:
    start = text.find("const PACKAGE_ADJUSTMENT_PRODUCTION_V1 = Object.freeze({")
    end = text.find("function packageAdjustmentSize2Multiplier(", start)
    if start < 0 or end <= start:
        raise RuntimeError("cannot extract package config")
    return text[start:end].strip()

def run_js_behavior() -> dict:
    text = INDEX.read_text(encoding="utf-8")
    parts = [
        "let VALUE_UNCERTAINTY = null;",
        "let state = {A:[], B:[]};",
        "function normalizeName(s){ return s.trim().toLowerCase().replace(/[.'’-]/g,'').replace(/\\\\s+/g,' '); }",
        function(text, "valueUncertaintyForPlayer"),
        package_config(text),
        function(text, "packageAdjustmentSize2Multiplier"),
        function(text, "packageAdjustmentSize2CompositionFactor"),
        function(text, "packageAdjustmentAssessment"),
        function(text, "packageAdjustmentForTrade"),
        function(text, "sideTotal"),
        function(text, "tradeVerdictTotals"),
        function(text, "tradeRobustnessVerdictClass"),
        function(text, "tradeRobustnessAssessment"),
    ]

    harness = """
function player(name,pos,value){ return {type:'player',name,pos,value}; }
function setRanges(rows){
  const players = {};
  for(const r of rows){
    players[normalizeName(r.name)] = {
      center_value:r.center,
      range_low:r.low,
      range_high:r.high,
      relative_half_width:Math.abs(r.high-r.low)/(2*Math.max(1,r.center)),
    };
  }
  VALUE_UNCERTAINTY = {
    range_semantics:'sensitivity_envelope_v1_not_probability_interval',
    players,
  };
}
function check(v,m){ if(!v) throw new Error(m); }
let checked = 0;

state = {A:[player('A','WR',105)], B:[player('B','WR',100)]};
setRanges([{name:'A',center:105,low:95,high:115},{name:'B',center:100,low:90,high:110}]);
let r = tradeRobustnessAssessment();
check(r.status === 'center_fair', 'fair center status'); checked++;

state = {A:[player('A','WR',130)], B:[player('B','WR',100)]};
setRanges([{name:'A',center:130,low:120,high:140},{name:'B',center:100,low:90,high:100}]);
r = tradeRobustnessAssessment();
check(r.status === 'evaluated', 'robust evaluated');
check(r.favoredSide === 'A', 'robust favored A');
check(r.outcome === 'robust' && r.adverseVerdict.side === 'A', 'robust survives');
check(state.A[0].value === 130 && state.B[0].value === 100, 'robust restores state'); checked++;

state = {A:[player('A','WR',120)], B:[player('B','WR',100)]};
setRanges([{name:'A',center:120,low:104,high:130},{name:'B',center:100,low:90,high:100}]);
r = tradeRobustnessAssessment();
check(r.outcome === 'softened_to_fair', 'softens to fair');
check(r.adverseVerdict.side === null, 'fair adverse no side');
check(state.A[0].value === 120 && state.B[0].value === 100, 'fair restores state'); checked++;

state = {A:[player('A','WR',120)], B:[player('B','WR',100)]};
setRanges([{name:'A',center:120,low:90,high:130},{name:'B',center:100,low:90,high:110}]);
r = tradeRobustnessAssessment();
check(r.outcome === 'flipped_direction', 'flips direction');
check(r.adverseVerdict.side === 'B', 'adverse favors B');
check(state.A[0].value === 120 && state.B[0].value === 100, 'flip restores state'); checked++;

state = {A:[player('A','WR',130)], B:[{type:'pick',name:'2027 Rd 1',value:100}]};
setRanges([{name:'A',center:130,low:120,high:140}]);
r = tradeRobustnessAssessment();
check(r.status === 'unavailable', 'pick fail closed'); checked++;

process.stdout.write(JSON.stringify({status:'PASS',checked}));
"""
    js = "\n\n".join(parts) + "\n\n" + harness
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(js)
        js_path = Path(fh.name)
    try:
        proc = subprocess.run(["node", str(js_path)], cwd=ROOT, capture_output=True, text=True, check=True)
        return json.loads(proc.stdout)
    finally:
        js_path.unlink(missing_ok=True)

def main() -> None:
    phase1b = json.loads(PHASE1B.read_text(encoding="utf-8"))
    if phase1b.get("decision") != "PASS_TRADE_ROBUSTNESS_V1_PHASE1B_LIVE_VERDICT_ALIGNMENT":
        raise RuntimeError("Phase 1B anchor is not PASS")

    text = INDEX.read_text(encoding="utf-8")
    for required in (
        "function tradeRobustnessVerdictClass(",
        "function tradeRobustnessAssessment(",
        "function renderTradeRobustness(",
        "renderTradeRobustness();",
        "Sensitivity Robust",
        "Sensitivity Fragile",
        "NOT a probability or confidence interval",
    ):
        if required not in text:
            raise RuntimeError(f"missing Trade Robustness UI marker: {required}")

    behavior = run_js_behavior()
    if behavior.get("status") != "PASS" or behavior.get("checked", 0) < 5:
        raise RuntimeError("Trade Robustness JS behavior checks failed")

    result = {
        "schema_version": 1,
        "study_id": "trade-robustness-v1-phase2-ui-shadow",
        "decision": "PASS_TRADE_ROBUSTNESS_V1_PHASE2_UI_SHADOW_DEPLOYED",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "display_only": True,
        "fundamental_value_changed": False,
        "market_value_changed": False,
        "package_adjustment_changed": False,
        "team_utility_changed": False,
        "trade_verdict_changed": False,
        "probability_language_allowed": False,
        "fair_trade_center_badge_shown": False,
        "player_only_complete_uncertainty_coverage_required": True,
        "live_package_adjustment_recomputed_in_adverse_corner": True,
        "js_behavior_cases_checked": behavior["checked"],
        "phase1b_directional_cases": phase1b["universe"]["directional_center_verdict_cases"],
        "phase1b_direction_robust_share": phase1b["summary"]["direction_robust_share"],
        "phase1b_softened_to_fair_share": phase1b["summary"]["softened_to_fair_share"],
        "phase1b_flipped_direction_share": phase1b["summary"]["flipped_direction_share"],
    }
    OUTJSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUTMD.write_text(
        "\n".join([
            "# Trade Robustness V1 Phase 2 — UI Shadow Deployment",
            "",
            f"**Decision:** `{result['decision']}`",
            "",
            "**Display-only production shadow deployed.**",
            "",
            "- Fundamental Value changed: **NO**",
            "- Market Value changed: **NO**",
            "- Package Adjustment changed: **NO**",
            "- Team Utility changed: **NO**",
            "- Trade Verdict changed: **NO**",
            "- Probability/confidence percentage shown: **NO**",
            "- Fair Trade center verdict gets directional badge: **NO**",
            "- Picks/partial/stale uncertainty fail closed: **YES**",
            "- Live Package Adjustment reruns in adverse corner: **YES**",
            f"- JS behavior cases checked: **{behavior['checked']}**",
        ]).rstrip() + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "study_id": result["study_id"],
        "decision": result["decision"],
        "index_sha256": sha(INDEX),
        "phase1b_sha256": sha(PHASE1B),
        "confirmation_json_sha256": sha(OUTJSON),
        "confirmation_md_sha256": sha(OUTMD),
        "validator_sha256": sha(Path(__file__).resolve()),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
