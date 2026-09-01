#!/usr/bin/env python3
"""
apply_value_uncertainty_ui.py

Idempotently integrate the generated player-value sensitivity envelope into
the Trade Desk UI without changing valuation math, side totals, trade verdicts,
Team Utility, or any production coefficients.

The live page fetches:
  scripts/artifacts/generated/value_uncertainty.json

UI behavior:
- Player center value remains the primary number.
- A second line shows "Range low–high · tier".
- Range is shown only when the artifact's center_value exactly matches the
  currently computed player value, preventing stale ranges from being paired
  with a changed calculator value.
- Tooltips expose the three V1 components.
- Draft picks have no V1 uncertainty range.
- Trade totals/verdicts remain center-value-only.
- Fetch failure is silent/graceful: calculator behavior remains unchanged.

Usage:
  python3 scripts/maintenance/apply_value_uncertainty_ui.py --check
  python3 scripts/maintenance/apply_value_uncertainty_ui.py --write
  python3 scripts/maintenance/apply_value_uncertainty_ui.py --selftest
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = REPO_ROOT / "index.html"

MARKER = "VALUE_UNCERTAINTY_UI_V1"
EXPECTED_SEMANTICS = "sensitivity_envelope_v1_not_probability_interval"

CSS_ANCHOR = """  .asset-value{
    font-family:'IBM Plex Mono',monospace;
    font-size:14px;
    color:var(--text);
  }
"""

CSS_INSERT = CSS_ANCHOR + r"""  /* VALUE_UNCERTAINTY_UI_V1
     The range is deliberately visually subordinate to the deployed center
     value. It is a sensitivity envelope, not a calibrated probability
     interval. */
  .asset-value-stack{
    display:flex;
    flex-direction:column;
    align-items:flex-end;
    gap:2px;
  }
  .asset-range{
    font-family:'IBM Plex Mono',monospace;
    font-size:9.5px;
    line-height:1.15;
    color:var(--text-dim);
    white-space:nowrap;
    cursor:help;
  }
  .asset-range.tier-low{ color:var(--green); }
  .asset-range.tier-moderate{ color:var(--text-muted); }
  .asset-range.tier-high{ color:var(--amber); }
  .asset-range.tier-very-high{ color:var(--red); }
"""

JS_ANCHOR = """function addPlayerAsset(side, name, pos, age, role){
"""

JS_INSERT = r"""/* ---------- Player Value Sensitivity Envelope ----------
   VALUE_UNCERTAINTY_UI_V1

   This is intentionally separate from playerValue(). The generated artifact
   cannot change the point estimate, side totals, verdict, or Team Utility.
   It only supplies a display range around the already-computed center value.

   Critical guard: a range is displayed only when its stored center_value
   EXACTLY matches the live computed value. If index.html changes before the
   next data refresh, stale uncertainty is hidden rather than attached to the
   wrong center value.

   V1 semantics are NOT a probability confidence interval. */
const VALUE_UNCERTAINTY_URL =
  'https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/refs/heads/main/scripts/artifacts/generated/value_uncertainty.json';

let VALUE_UNCERTAINTY = null;

function valueUncertaintyForPlayer(name, centerValue){
  if(!VALUE_UNCERTAINTY || VALUE_UNCERTAINTY.range_semantics !== 'sensitivity_envelope_v1_not_probability_interval'){
    return null;
  }
  const key = normalizeName(name || '');
  const row = VALUE_UNCERTAINTY.players && VALUE_UNCERTAINTY.players[key];
  if(!row) return null;

  const artifactCenter = Number(row.center_value);
  if(!Number.isFinite(artifactCenter) || artifactCenter !== Number(centerValue)){
    return null; // stale/mismatched artifact: fail closed
  }

  const low = Number(row.range_low);
  const high = Number(row.range_high);
  const width = Number(row.relative_half_width);
  if(!Number.isFinite(low) || !Number.isFinite(high) || !Number.isFinite(width)) return null;
  if(low > artifactCenter || high < artifactCenter || width < 0) return null;

  return row;
}

function valueUncertaintyRangeHTML(name, centerValue){
  const row = valueUncertaintyForPlayer(name, centerValue);
  if(!row) return '';

  const signals = row.signals || {};
  const pct = v => Number.isFinite(Number(v)) ? `${(Number(v)*100).toFixed(1)}%` : 'n/a';
  const tier = String(row.uncertainty_tier || 'unknown').replace(/_/g, ' ');
  const tierClass = String(row.uncertainty_tier || '').replace(/_/g, '-');

  const tooltip = [
    'Sensitivity envelope — NOT a probability interval',
    `Tier: ${tier}`,
    `Relative half-width: ${pct(row.relative_half_width)}`,
    `Projection disagreement: ${pct(signals.provider_disagreement_component)}`,
    `History sampling: ${pct(signals.history_sampling_component)}`,
    `Availability history: ${pct(signals.availability_component)}`,
  ].join('\n');

  return `<div class="asset-range tier-${escapeHtml(tierClass)}" title="${escapeHtml(tooltip)}">Range ${Number(row.range_low).toLocaleString()}–${Number(row.range_high).toLocaleString()} · ${escapeHtml(tier)}</div>`;
}

function syncValueUncertaintyFromGitHub(){
  fetch(VALUE_UNCERTAINTY_URL)
    .then(r => {
      if(!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(data => {
      const players = data && data.players;
      const playerCount = players && typeof players === 'object' ? Object.keys(players).length : 0;
      if(data.range_semantics !== 'sensitivity_envelope_v1_not_probability_interval' || playerCount < 500){
        throw new Error('unexpected uncertainty artifact schema/coverage');
      }
      VALUE_UNCERTAINTY = data;
      render(); // redraw any currently-selected players with their range
    })
    .catch(() => {
      // Uncertainty is optional display metadata. Never block the calculator.
      VALUE_UNCERTAINTY = null;
    });
}

""" + JS_ANCHOR

ASSET_OLD = """      <div class="asset-right">
        <div class="asset-value">${a.value.toLocaleString()}</div>
        <button class="remove-btn" onclick="removeAsset('${side}','${a.id}')">×</button>
      </div>
"""

ASSET_NEW = """      <div class="asset-right">
        <div class="asset-value-stack">
          <div class="asset-value">${a.value.toLocaleString()}</div>
          ${a.type === 'player' ? valueUncertaintyRangeHTML(a.name, a.value) : ''}
        </div>
        <button class="remove-btn" onclick="removeAsset('${side}','${a.id}')">×</button>
      </div>
"""

IMPACT_OLD = """      <div style="font-family:'IBM Plex Mono',monospace;font-size:13px;margin-bottom:8px;">
        Team Utility: <span style="color:${tuColor};font-weight:600;">${tuSign}${teamUtil.teamUtility.toLocaleString()}</span>
        <span style="color:var(--text-dim);"> — does this actually help your lineup</span>
      </div>
      ${packageNote}
"""

IMPACT_NEW = """      <div style="font-family:'IBM Plex Mono',monospace;font-size:13px;margin-bottom:8px;">
        Team Utility: <span style="color:${tuColor};font-weight:600;">${tuSign}${teamUtil.teamUtility.toLocaleString()}</span>
        <span style="color:var(--text-dim);"> — does this actually help your lineup</span>
      </div>
      ${[...outgoing, ...incoming].some(a => valueUncertaintyForPlayer(a.name, a.value)) ? `
        <div style="font-family:'IBM Plex Mono',monospace;font-size:10.5px;color:var(--text-dim);margin-bottom:8px;">
          Player ranges are sensitivity envelopes, not probability intervals. Totals and verdict still use center values.
        </div>` : ''}
      ${packageNote}
"""

INIT_OLD = """render();
renderIntegritySummary();
syncRosterFromGitHub();
syncLeagueFromGitHub();
"""

INIT_NEW = """render();
renderIntegritySummary();
syncValueUncertaintyFromGitHub();
syncRosterFromGitHub();
syncLeagueFromGitHub();
"""


def validate_integrated(text: str) -> list[str]:
    problems = []
    required = [
        MARKER,
        "const VALUE_UNCERTAINTY_URL",
        "function valueUncertaintyForPlayer",
        "function valueUncertaintyRangeHTML",
        "function syncValueUncertaintyFromGitHub",
        EXPECTED_SEMANTICS,
        "asset-value-stack",
        "Player ranges are sensitivity envelopes, not probability intervals.",
        "syncValueUncertaintyFromGitHub();",
    ]
    for token in required:
        if token not in text:
            problems.append(f"missing required UI token: {token}")

    if text.count("const VALUE_UNCERTAINTY_URL") != 1:
        problems.append("VALUE_UNCERTAINTY_URL must appear exactly once")
    if text.count("function syncValueUncertaintyFromGitHub") != 1:
        problems.append("syncValueUncertaintyFromGitHub must appear exactly once")
    if text.count("syncValueUncertaintyFromGitHub();") != 1:
        problems.append("uncertainty startup call must appear exactly once")

    # The deployed trade math must remain unchanged by this integration.
    if "function playerValue(pos, age, role, name){" not in text:
        problems.append("playerValue function missing")
    if "function sideTotal(side){" not in text:
        problems.append("sideTotal function missing")
    if "const outValue = outgoing.reduce((s,a) => s + a.value, 0);" not in text:
        problems.append("center-value trade-impact math missing")
    return problems


def integrate(text: str) -> str:
    if MARKER in text:
        problems = validate_integrated(text)
        if problems:
            raise RuntimeError("Existing uncertainty UI marker is incomplete: " + "; ".join(problems))
        return text

    replacements = [
        (CSS_ANCHOR, CSS_INSERT, "asset-value CSS"),
        (JS_ANCHOR, JS_INSERT, "player uncertainty JS"),
        (ASSET_OLD, ASSET_NEW, "selected-player row"),
        (IMPACT_OLD, IMPACT_NEW, "trade-impact interpretation note"),
        (INIT_OLD, INIT_NEW, "startup fetch"),
    ]

    out = text
    for old, new, label in replacements:
        count = out.count(old)
        if count != 1:
            raise RuntimeError(f"Expected exactly one {label} anchor, found {count}")
        out = out.replace(old, new, 1)

    problems = validate_integrated(out)
    if problems:
        raise RuntimeError("Integrated UI validation failed: " + "; ".join(problems))
    return out


def run_selftest() -> None:
    fixture = f"""<!doctype html>
<style>
{CSS_ANCHOR}</style>
<script>
function normalizeName(s){{ return s.trim().toLowerCase(); }}
function escapeHtml(s){{ return String(s); }}
function render(){{}}
function playerValue(pos, age, role, name){{ return 1000; }}
function sideTotal(side){{ return 0; }}
{JS_ANCHOR}
  return;
}}
function assetRowHTML(side, a){{
  return `
    <div class="asset-row">
      <div class="asset-right">
        <div class="asset-value">${{a.value.toLocaleString()}}</div>
        <button class="remove-btn" onclick="removeAsset('${{side}}','${{a.id}}')">×</button>
      </div>
    </div>`;
}}
function renderTradeImpact(){{
  const outgoing = [], incoming = [];
  const tuColor='', tuSign='', teamUtil={{teamUtility:0}}, packageNote='';
  const outValue = outgoing.reduce((s,a) => s + a.value, 0);
  const inValue = incoming.reduce((s,a) => s + a.value, 0);
  const netValue = inValue - outValue;
  const x = `
      <div style="font-family:'IBM Plex Mono',monospace;font-size:13px;margin-bottom:8px;">
        Team Utility: <span style="color:${{tuColor}};font-weight:600;">${{tuSign}}${{teamUtil.teamUtility.toLocaleString()}}</span>
        <span style="color:var(--text-dim);"> — does this actually help your lineup</span>
      </div>
      ${{packageNote}}
  `;
}}
render();
renderIntegritySummary();
syncRosterFromGitHub();
syncLeagueFromGitHub();
</script>
"""
    once = integrate(fixture)
    twice = integrate(once)
    assert once == twice, "integration must be idempotent"
    assert once.count(MARKER) >= 1
    assert once.count("const VALUE_UNCERTAINTY_URL") == 1
    assert "artifactCenter !== Number(centerValue)" in once
    assert "Totals and verdict still use center values." in once

    print(
        "apply_value_uncertainty_ui self-test passed: anchored integration, "
        "idempotence, stale-center fail-closed guard, and center-value trade math preservation."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    if not INDEX_PATH.exists():
        raise RuntimeError(f"Missing {INDEX_PATH}")

    original = INDEX_PATH.read_text(encoding="utf-8")

    if args.check:
        problems = validate_integrated(original)
        if problems:
            raise RuntimeError("Value uncertainty UI check failed: " + "; ".join(problems))
        print("Value uncertainty UI check passed.")
        return

    if not args.write:
        raise RuntimeError("Use --write, --check, or --selftest")

    updated = integrate(original)
    if updated == original:
        print("Value uncertainty UI already integrated; no change.")
        return

    INDEX_PATH.write_text(updated, encoding="utf-8")
    print("Integrated value uncertainty UI into index.html.")


if __name__ == "__main__":
    main()
