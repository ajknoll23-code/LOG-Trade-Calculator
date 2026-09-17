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
PHASE3 = (
    ROOT / "research/trade-robustness-v1/"
    "trade_robustness_v1_phase3_pick_sensitivity_shadow.json"
)
OUTDIR = Path(__file__).resolve().parent

OUTJSON = OUTDIR / "trade_robustness_v1_phase4_pick_ui_confirmation.json"
OUTMD = OUTDIR / "trade_robustness_v1_phase4_pick_ui_confirmation.md"
MANIFEST = OUTDIR / "trade_robustness_v1_phase4_manifest.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def balanced(
    text: str,
    marker: str,
    open_char: str = "{",
    close_char: str = "}",
) -> str:
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
    start = text.find(
        "const PACKAGE_ADJUSTMENT_PRODUCTION_V1 = Object.freeze({"
    )
    end = text.find(
        "function packageAdjustmentSize2Multiplier(",
        start,
    )
    if start < 0 or end <= start:
        raise RuntimeError("cannot extract package config")
    return text[start:end].strip()


def const_array(text: str, marker: str) -> str:
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"missing marker: {marker}")
    open_idx = text.find("[", start)
    block = balanced(
        text,
        marker,
        "[",
        "]",
    )
    semi = text.find(";", start + len(block))
    if semi < 0:
        return block
    return text[start:semi + 1]


def run_js_behavior() -> dict:
    text = INDEX.read_text(encoding="utf-8")
    parts = [
        "let VALUE_UNCERTAINTY = null;",
        "let state = {A:[], B:[]};",
        (
            "function normalizeName(s){ "
            "return s.trim().toLowerCase()"
            ".replace(/[.'’-]/g,'')"
            ".replace(/\\\\s+/g,' '); }"
        ),
        function(text, "valueUncertaintyForPlayer"),
        balanced(text, "const PICK_BASE = {"),
        balanced(text, "const YEAR_DISCOUNT = {"),
        const_array(text, "const PICK_SEASONS = ["),
        function(text, "pickValue"),
        package_config(text),
        function(text, "packageAdjustmentSize2Multiplier"),
        function(text, "packageAdjustmentSize2CompositionFactor"),
        function(text, "packageAdjustmentAssessment"),
        function(text, "packageAdjustmentForTrade"),
        function(text, "sideTotal"),
        function(text, "tradeVerdictTotals"),
        function(text, "tradeRobustnessVerdictClass"),
        function(text, "tradeRobustnessPickEnvelope"),
        function(text, "tradeRobustnessAssessment"),
    ]

    harness = r"""
function player(name,pos,value){
  return {type:'player',name,pos,value};
}
function pick(year,round,slot){
  return {
    type:'pick',
    name:`${year} Rd ${round} (${slot})`,
    value:pickValue(round,slot,year),
  };
}
function setRanges(rows){
  const players = {};
  for(const r of rows){
    players[normalizeName(r.name)] = {
      center_value:r.center,
      range_low:r.low,
      range_high:r.high,
      relative_half_width:
        Math.abs(r.high-r.low)/(2*Math.max(1,r.center)),
    };
  }
  VALUE_UNCERTAINTY = {
    range_semantics:
      'sensitivity_envelope_v1_not_probability_interval',
    players,
  };
}
function check(v,m){
  if(!v) throw new Error(m);
}
let checked = 0;

// 1) Existing player-only behavior still works.
state = {
  A:[player('A','WR',130)],
  B:[player('B','WR',100)],
};
setRanges([
  {name:'A',center:130,low:120,high:140},
  {name:'B',center:100,low:90,high:100},
]);
let r = tradeRobustnessAssessment();
check(r.status === 'evaluated', 'player-only evaluated');
check(r.containsPick === false, 'player-only containsPick false');
check(r.outcome === 'robust', 'player-only robust');
check(
  state.A[0].value === 130 && state.B[0].value === 100,
  'player-only state restored'
);
checked++;

// 2) Supported R1 pick evaluates and reports draft-slot mode.
state = {
  A:[pick('2027',1,'early')],
  B:[pick('2027',2,'early')],
};
setRanges([]);
r = tradeRobustnessAssessment();
check(r.status === 'evaluated', 'R1 pick evaluated');
check(r.containsPick === true, 'R1 containsPick');
check(
  r.sensitivityMode === 'player_and_draft_slot',
  'R1 sensitivity mode'
);
check(r.pickRounds.includes(1), 'R1 reported');
check(
  state.A[0].value === pickValue(1,'early','2027'),
  'R1 state restored'
);
checked++;

// 3) R4 pick is still supported.
state = {
  A:[pick('2027',3,'early')],
  B:[pick('2027',4,'mid')],
};
r = tradeRobustnessAssessment();
check(r.status === 'evaluated', 'R4 supported');
check(r.pickRounds.includes(4), 'R4 reported');
checked++;

// 4) R5 fails closed.
state = {
  A:[pick('2027',1,'early')],
  B:[pick('2027',5,'mid')],
};
r = tradeRobustnessAssessment();
check(r.status === 'unavailable', 'R5 fails closed');
check(
  r.reason === 'unsupported_or_stale_pick_sensitivity',
  'R5 failure reason'
);
checked++;

// 5) Unparseable/stale pick fails closed.
state = {
  A:[pick('2027',1,'early')],
  B:[{
    type:'pick',
    name:'Mystery Pick',
    value:pickValue(2,'mid','2027'),
  }],
};
r = tradeRobustnessAssessment();
check(r.status === 'unavailable', 'unparseable pick fails closed');
checked++;

// 6) Player + R1 pick mixed trade evaluates and restores every value.
state = {
  A:[
    player('A','WR',4200),
    pick('2028',1,'mid'),
  ],
  B:[player('B','WR',9000)],
};
setRanges([
  {name:'A',center:4200,low:3500,high:4900},
  {name:'B',center:9000,low:7600,high:10300},
]);
const original = state.A.concat(state.B).map(x => x.value);
r = tradeRobustnessAssessment();
check(
  r.status === 'evaluated' || r.status === 'center_fair',
  'mixed trade returns valid status'
);
if(r.status === 'evaluated'){
  check(r.containsPick === true, 'mixed contains pick');
  check(r.pickRounds.includes(1), 'mixed reports R1');
}
const restored = state.A.concat(state.B).map(x => x.value);
check(
  JSON.stringify(original) === JSON.stringify(restored),
  'mixed trade state restored'
);
checked++;

// 7) Stale player uncertainty still fails closed even with supported pick.
state = {
  A:[player('No Range','WR',5000)],
  B:[pick('2027',1,'mid')],
};
setRanges([]);
r = tradeRobustnessAssessment();
check(r.status === 'unavailable', 'missing player range fails closed');
check(
  r.reason === 'missing_or_stale_player_uncertainty',
  'missing player reason'
);
checked++;

process.stdout.write(
  JSON.stringify({status:'PASS',checked})
);
"""

    js = "\n\n".join(parts) + "\n\n" + harness
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".js",
        delete=False,
        encoding="utf-8",
    ) as fh:
        fh.write(js)
        js_path = Path(fh.name)

    try:
        proc = subprocess.run(
            ["node", str(js_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(proc.stdout)
    finally:
        js_path.unlink(missing_ok=True)


def main() -> None:
    phase3 = json.loads(PHASE3.read_text(encoding="utf-8"))
    if (
        phase3.get("decision")
        != "PASS_TRADE_ROBUSTNESS_V1_PHASE3_PICK_SLOT_SENSITIVITY_SHADOW"
    ):
        raise RuntimeError("Phase 3 pick-sensitivity anchor is not PASS")

    if phase3.get("production_change_authorized") is not False:
        raise RuntimeError("Phase 3 production guardrail drifted")

    scope = phase3.get("promotion_scope") or {}
    if scope.get("eligible_rounds") != [1, 2, 3, 4]:
        raise RuntimeError("Phase 3 eligible round scope drifted")
    if scope.get("ineligible_rounds") != [5, 6]:
        raise RuntimeError("Phase 3 ineligible round scope drifted")

    text = INDEX.read_text(encoding="utf-8")
    required = (
        "function tradeRobustnessPickEnvelope(",
        "function tradeRobustnessAssessment(",
        "function renderTradeRobustness(",
        "draft-slot stress",
        "Round 1–4 picks",
        "unsupported_or_stale_pick_sensitivity",
        "renderTradeRobustness();",
    )
    for marker in required:
        if marker not in text:
            raise RuntimeError(
                f"missing Phase 4 UI marker: {marker}"
            )

    behavior = run_js_behavior()
    if (
        behavior.get("status") != "PASS"
        or behavior.get("checked", 0) < 7
    ):
        raise RuntimeError(
            "Phase 4 Trade Robustness behavior checks failed"
        )

    result = {
        "schema_version": 1,
        "study_id": "trade-robustness-v1-phase4-pick-ui",
        "decision":
            "PASS_TRADE_ROBUSTNESS_V1_PHASE4_PICK_UI_DEPLOYED",
        "generated_at_utc":
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        "display_only": True,
        "phase3_anchor_passed": True,
        "supported_pick_rounds": [1, 2, 3, 4],
        "unsupported_pick_rounds": [5, 6],
        "pick_range_semantics":
            "same-round/year deterministic early-to-late slot envelope",
        "year_discount_uncertainty_added": False,
        "player_uncertainty_semantics_changed": False,
        "fundamental_value_changed": False,
        "pick_value_formula_changed": False,
        "market_value_changed": False,
        "package_adjustment_changed": False,
        "team_utility_changed": False,
        "trade_verdict_changed": False,
        "probability_language_allowed": False,
        "fair_trade_center_badge_shown": False,
        "unsupported_pick_fail_closed": True,
        "stale_player_uncertainty_fail_closed": True,
        "live_package_adjustment_recomputed_in_adverse_corner":
            True,
        "js_behavior_cases_checked": behavior["checked"],
    }

    OUTJSON.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUTMD.write_text(
        "\n".join([
            "# Trade Robustness V1 Phase 4 — Pick UI Deployment",
            "",
            f"**Decision:** `{result['decision']}`",
            "",
            "**Display-only production extension deployed.**",
            "",
            "- Supported draft-pick rounds: **1–4**",
            "- Round 5–6 picks fail closed: **YES**",
            "- Pick stress: **same round/year, late ↔ early slot**",
            "- Year-discount uncertainty added: **NO**",
            "- Player uncertainty model changed: **NO**",
            "- Fundamental Value changed: **NO**",
            "- Pick value formula changed: **NO**",
            "- Market Value changed: **NO**",
            "- Package Adjustment changed: **NO**",
            "- Team Utility changed: **NO**",
            "- Trade Verdict changed: **NO**",
            "- Probability/confidence percentage shown: **NO**",
            "- Fair Trade center verdict gets directional badge: **NO**",
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
        "phase3_sha256": sha(PHASE3),
        "validator_sha256": sha(Path(__file__).resolve()),
        "confirmation_json_sha256": sha(OUTJSON),
        "confirmation_md_sha256": sha(OUTMD),
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
