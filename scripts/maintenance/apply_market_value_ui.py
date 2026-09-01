#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = REPO_ROOT / "index.html"

MARKER = "MARKET_VALUE_UI_V1"
EXPECTED_SCALE = "league_rank_quantile_mapped_to_trade_desk_points_v1"

CSS_ANCHOR = "  .asset-range.tier-very-high{ color:var(--red); }\n"
CSS_INSERT = CSS_ANCHOR + r"""  /* MARKET_VALUE_UI_V1 — separate league-opinion lens */
  .asset-market{
    font-family:'IBM Plex Mono',monospace;
    font-size:9.5px;
    line-height:1.15;
    color:var(--text-muted);
    white-space:nowrap;
    cursor:help;
  }
  .side-total-stack{
    display:flex;
    flex-direction:column;
    align-items:flex-end;
    gap:1px;
  }
  .side-total-label{
    font-family:'IBM Plex Mono',monospace;
    font-size:8.5px;
    letter-spacing:0.06em;
    text-transform:uppercase;
    color:var(--text-dim);
  }
"""

JS_ANCHOR = "function addPlayerAsset(side, name, pos, age, role){\n"
JS_INSERT = r"""/* ---------- Separate League Market Value ----------
   MARKET_VALUE_UI_V1

   Fundamental Value remains the deployed playerValue() result stored in
   each asset's `.value`. Market Value is display-only league opinion.

   Stale-center guard: a Market row is accepted only when its stored
   fundamental_value exactly equals the live Fundamental Value.

   Package guard: trade-level Market Value is shown only with COMPLETE
   coverage. Partial market sums are never presented as the whole trade. */
const MARKET_VALUE_URL =
  'https://raw.githubusercontent.com/ajknoll23-code/LOG-Trade-Calculator/refs/heads/main/scripts/artifacts/generated/market_values.json';

let MARKET_VALUE = null;
let MARKET_VALUE_STATUS = 'loading';

function marketValueForPlayer(name, fundamentalValue){
  if(!MARKET_VALUE || MARKET_VALUE.scale_semantics !== 'league_rank_quantile_mapped_to_trade_desk_points_v1'){
    return null;
  }
  const key = normalizeName(name || '');
  const row = MARKET_VALUE.players && MARKET_VALUE.players[key];
  if(!row) return null;

  const storedFundamental = Number(row.fundamental_value);
  const market = Number(row.market_value);
  if(!Number.isFinite(storedFundamental) || storedFundamental !== Number(fundamentalValue)) return null;
  if(!Number.isFinite(market) || market < 0) return null;
  return row;
}

function marketValueHTML(name, fundamentalValue){
  const row = marketValueForPlayer(name, fundamentalValue);
  if(!row) return '';

  const market = Number(row.market_value);
  const delta = market - Number(fundamentalValue);
  const deltaSign = delta >= 0 ? '+' : '';
  const deltaColor = delta > 0 ? 'var(--green)' : (delta < 0 ? 'var(--red)' : 'var(--text-dim)');
  const evidence = row.evidence || {};
  const pairs = Number(evidence.same_position_pairwise_observations || 0);
  const enough = Boolean(evidence.same_position_enough_data);
  const dominant = Number(evidence.dominant_voter_share_pct);
  const rank = Number(row.market_rank);

  const tooltip = [
    'Market Value — separate league-opinion lens',
    `Market rank: ${Number.isFinite(rank) ? rank : 'n/a'}`,
    `Direct ${row.pos || ''} pairwise observations: ${pairs}${enough ? ' (threshold met)' : ' (below 30-pair threshold)'}`,
    `Dominant voter share: ${Number.isFinite(dominant) ? dominant.toFixed(1) + '%' : 'n/a'}`,
    'Not blended into Fundamental Value or Team Utility',
  ].join('\n');

  return `<div class="asset-market" title="${escapeHtml(tooltip)}">Market ${market.toLocaleString()} · <span style="color:${deltaColor}">${deltaSign}${delta.toLocaleString()}</span></div>`;
}

function packageMarketValueSummary(outgoing, incoming){
  const all = [...outgoing, ...incoming];

  if(MARKET_VALUE_STATUS === 'loading'){
    return {status:'loading', total:all.length, rated:0};
  }
  if(MARKET_VALUE_STATUS !== 'ready' || !MARKET_VALUE){
    return {status:'failed', total:all.length, rated:0};
  }

  const outRows = outgoing.map(a => ({asset:a, row:marketValueForPlayer(a.name, a.value)}));
  const inRows = incoming.map(a => ({asset:a, row:marketValueForPlayer(a.name, a.value)}));
  const combined = [...outRows, ...inRows];
  const rated = combined.filter(x => x.row).length;

  if(rated !== combined.length){
    return {
      status:'partial',
      total:combined.length,
      rated,
      missing:combined.filter(x => !x.row).map(x => x.asset.name),
    };
  }

  const outMarket = outRows.reduce((s,x) => s + Number(x.row.market_value), 0);
  const inMarket = inRows.reduce((s,x) => s + Number(x.row.market_value), 0);
  const net = inMarket - outMarket;

  const lowSample = {};
  for(const item of combined){
    const row = item.row;
    const evidence = row.evidence || {};
    if(!evidence.same_position_enough_data){
      const pos = row.pos || item.asset.pos || '?';
      lowSample[pos] = Number(evidence.same_position_pairwise_observations || 0);
    }
  }

  const quality = MARKET_VALUE.market_quality || {};
  return {
    status:'complete',
    total:combined.length,
    rated,
    net,
    dominantVoterShare:Number(quality.dominant_voter_share_pct),
    dominantVoterMajority:Boolean(quality.dominant_voter_majority_flag),
    lowSample,
  };
}

function marketPackageLineHTML(summary){
  if(!summary) return '';

  if(summary.status === 'loading'){
    return `<div style="font-family:'IBM Plex Mono',monospace;font-size:13px;margin-bottom:4px;">
      Market Value: <span style="color:var(--text-dim);">loading league market…</span>
    </div>`;
  }

  if(summary.status === 'failed'){
    return `<div style="font-family:'IBM Plex Mono',monospace;font-size:13px;margin-bottom:4px;">
      Market Value: <span style="color:var(--text-dim);">unavailable</span>
      <span style="color:var(--text-dim);"> — Fundamental Value and Team Utility are unaffected</span>
    </div>`;
  }

  if(summary.status === 'partial'){
    const missing = (summary.missing || []).map(escapeHtml).join(', ');
    return `<div style="font-family:'IBM Plex Mono',monospace;font-size:13px;margin-bottom:4px;">
      Market Value: <span style="color:var(--amber);">${summary.rated}/${summary.total} players rated</span>
      <span style="color:var(--text-dim);"> — no partial package total shown</span>
      ${missing ? `<div style="font-size:10px;color:var(--text-dim);margin-top:2px;">Missing/stale: ${missing}</div>` : ''}
    </div>`;
  }

  const sign = summary.net >= 0 ? '+' : '';
  const color = summary.net >= 0 ? 'var(--green)' : 'var(--red)';
  const lowSampleParts = Object.entries(summary.lowSample || {}).map(([pos,n]) => `${pos} ${n}`);
  const warnings = [];
  if(summary.dominantVoterMajority && Number.isFinite(summary.dominantVoterShare)){
    warnings.push(`voter concentration ${summary.dominantVoterShare.toFixed(1)}% dominant`);
  }
  if(lowSampleParts.length){
    warnings.push(`direct sample below threshold: ${lowSampleParts.join(', ')}`);
  }

  return `<div style="font-family:'IBM Plex Mono',monospace;font-size:13px;margin-bottom:4px;">
    Market Value: <span style="color:${color};font-weight:600;">${sign}${summary.net.toLocaleString()}</span>
    <span style="color:var(--text-dim);"> — what this league's current votes imply</span>
    ${warnings.length ? `<div style="font-size:10px;color:var(--amber);margin-top:2px;">⚠ ${escapeHtml(warnings.join(' · '))}</div>` : ''}
  </div>`;
}

function syncMarketValueFromGitHub(){
  MARKET_VALUE_STATUS = 'loading';
  fetch(MARKET_VALUE_URL)
    .then(r => {
      if(!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(data => {
      const players = data && data.players;
      const playerCount = players && typeof players === 'object' ? Object.keys(players).length : 0;
      if(data.scale_semantics !== 'league_rank_quantile_mapped_to_trade_desk_points_v1' || playerCount < 100){
        throw new Error('unexpected Market Value artifact schema/coverage');
      }
      MARKET_VALUE = data;
      MARKET_VALUE_STATUS = 'ready';
      render();
    })
    .catch(() => {
      MARKET_VALUE = null;
      MARKET_VALUE_STATUS = 'failed';
      render();
    });
}

""" + JS_ANCHOR

ASSET_OLD = """        <div class="asset-value-stack">
          <div class="asset-value">${a.value.toLocaleString()}</div>
          ${a.type === 'player' ? valueUncertaintyRangeHTML(a.name, a.value) : ''}
        </div>
"""
ASSET_NEW = """        <div class="asset-value-stack">
          <div class="asset-value" title="${a.type === 'player' ? 'Fundamental Value — deployed model point estimate' : 'Draft-pick value'}">${a.type === 'player' ? 'Fund. ' : ''}${a.value.toLocaleString()}</div>
          ${a.type === 'player' ? valueUncertaintyRangeHTML(a.name, a.value) : ''}
          ${a.type === 'player' ? marketValueHTML(a.name, a.value) : ''}
        </div>
"""

RANGE_OLD = """  return `<div class="asset-range tier-${escapeHtml(tierClass)}" title="${escapeHtml(tooltip)}">Range ${Number(row.range_low).toLocaleString()}–${Number(row.range_high).toLocaleString()} · ${escapeHtml(tier)}</div>`;
"""
RANGE_NEW = """  return `<div class="asset-range tier-${escapeHtml(tierClass)}" title="${escapeHtml(tooltip)}">Fund. range ${Number(row.range_low).toLocaleString()}–${Number(row.range_high).toLocaleString()} · ${escapeHtml(tier)}</div>`;
"""

SIDE_TOTAL_OLD = """        <div class="side-name">${label}</div>
        <div class="side-total">${total.toLocaleString()}</div>
"""
SIDE_TOTAL_NEW = """        <div class="side-name">${label}</div>
        <div class="side-total-stack">
          <div class="side-total">${total.toLocaleString()}</div>
          <div class="side-total-label">Fundamental</div>
        </div>
"""

TEAM_UTIL_OLD = """  const teamUtil = calculateTeamUtility(MY_ROSTER, afterRoster);
  const tuColor = teamUtil.teamUtility >= 0 ? 'var(--green)' : 'var(--red)';
  const tuSign = teamUtil.teamUtility >= 0 ? '+' : '';

  let packageNote = '';
"""
TEAM_UTIL_NEW = """  const teamUtil = calculateTeamUtility(MY_ROSTER, afterRoster);
  const tuColor = teamUtil.teamUtility >= 0 ? 'var(--green)' : 'var(--red)';
  const tuSign = teamUtil.teamUtility >= 0 ? '+' : '';

  const marketSummary = packageMarketValueSummary(outgoing, incoming);
  const marketLine = marketPackageLineHTML(marketSummary);

  let packageNote = '';
"""

TRADE_OLD = """      <div style="font-family:'IBM Plex Mono',monospace;font-size:13px;margin-bottom:4px;">
        Net value: <span style="color:${netColor};font-weight:600;">${netSign}${netValue.toLocaleString()}</span>
        <span style="color:var(--text-dim);"> — is this fair by market value</span>
      </div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:13px;margin-bottom:8px;">
        Team Utility: <span style="color:${tuColor};font-weight:600;">${tuSign}${teamUtil.teamUtility.toLocaleString()}</span>
        <span style="color:var(--text-dim);"> — does this actually help your lineup</span>
      </div>
"""
TRADE_NEW = """      <div style="font-family:'IBM Plex Mono',monospace;font-size:13px;margin-bottom:4px;">
        Fundamental Value: <span style="color:${netColor};font-weight:600;">${netSign}${netValue.toLocaleString()}</span>
        <span style="color:var(--text-dim);"> — what the deployed model says the player-value balance is</span>
      </div>
      ${marketLine}
      <div style="font-family:'IBM Plex Mono',monospace;font-size:13px;margin-bottom:8px;">
        Team Utility: <span style="color:${tuColor};font-weight:600;">${tuSign}${teamUtil.teamUtility.toLocaleString()}</span>
        <span style="color:var(--text-dim);"> — does this actually help your lineup</span>
      </div>
"""

NOTE_OLD = "          Player ranges are sensitivity envelopes, not probability intervals. Totals and verdict still use center values.\n"
NOTE_NEW = "          Fundamental ranges are sensitivity envelopes, not probability intervals. Trade totals and verdict still use Fundamental center values.\n"

STARTUP_OLD = """render();
renderIntegritySummary();
syncValueUncertaintyFromGitHub();
syncRosterFromGitHub();
syncLeagueFromGitHub();
"""
STARTUP_NEW = """render();
renderIntegritySummary();
syncValueUncertaintyFromGitHub();
syncMarketValueFromGitHub();
syncRosterFromGitHub();
syncLeagueFromGitHub();
"""


def validate_integrated(text: str) -> list[str]:
    required = [
        MARKER,
        "const MARKET_VALUE_URL",
        "function marketValueForPlayer",
        "function packageMarketValueSummary",
        "function marketPackageLineHTML",
        "function syncMarketValueFromGitHub",
        EXPECTED_SCALE,
        "Fundamental Value:",
        "Market Value:",
        "Team Utility:",
        "no partial package total shown",
        "side-total-label",
        "syncMarketValueFromGitHub();",
        "Fund. range",
        "function playerValue(pos, age, role, name){",
        "function sideTotal(side){",
        "const outValue = outgoing.reduce((s,a) => s + a.value, 0);",
        "const inValue = incoming.reduce((s,a) => s + a.value, 0);",
        "const teamUtil = calculateTeamUtility(MY_ROSTER, afterRoster);",
    ]
    problems = [f"missing token: {token}" for token in required if token not in text]
    if text.count("const MARKET_VALUE_URL") != 1:
        problems.append("MARKET_VALUE_URL must appear exactly once")
    if text.count("syncMarketValueFromGitHub();") != 1:
        problems.append("market startup call must appear exactly once")
    return problems


def integrate(text: str) -> str:
    if MARKER in text:
        problems = validate_integrated(text)
        if problems:
            raise RuntimeError("Existing Market UI marker is incomplete: " + "; ".join(problems))
        return text

    replacements = [
        (CSS_ANCHOR, CSS_INSERT, "Market CSS"),
        (JS_ANCHOR, JS_INSERT, "Market JS"),
        (ASSET_OLD, ASSET_NEW, "asset stack"),
        (RANGE_OLD, RANGE_NEW, "range label"),
        (SIDE_TOTAL_OLD, SIDE_TOTAL_NEW, "side total label"),
        (TEAM_UTIL_OLD, TEAM_UTIL_NEW, "market summary calculation"),
        (TRADE_OLD, TRADE_NEW, "three-lens trade impact"),
        (NOTE_OLD, NOTE_NEW, "uncertainty note"),
        (STARTUP_OLD, STARTUP_NEW, "startup fetch"),
    ]
    out = text
    for old, new, label in replacements:
        count = out.count(old)
        if count != 1:
            raise RuntimeError(f"Expected exactly one {label} anchor, found {count}")
        out = out.replace(old, new, 1)

    problems = validate_integrated(out)
    if problems:
        raise RuntimeError("Market UI validation failed: " + "; ".join(problems))
    return out


def run_selftest() -> None:
    # Build a synthetic page from the exact anchors instead of duplicating
    # the whole production page in the test fixture.
    fixture = "\n".join([
        "<style>",
        CSS_ANCHOR,
        "</style><script>",
        "function normalizeName(s){return s;}",
        "function escapeHtml(s){return String(s);}",
        "function render(){}",
        "function playerValue(pos, age, role, name){return 1000;}",
        "function sideTotal(side){return 0;}",
        "function calculateTeamUtility(a,b){return {teamUtility:0};}",
        "function valueUncertaintyRangeHTML(name, centerValue){",
        "  const tierClass='low', tooltip='', tier='low', row={range_low:800,range_high:1200};",
        RANGE_OLD,
        "}",
        JS_ANCHOR,
        "}",
        "function assetRowHTML(side,a){return `",
        ASSET_OLD,
        "`;}",
        "function sidePanelHTML(side,label){const total=0;return `",
        SIDE_TOTAL_OLD,
        "`;}",
        "function renderTradeImpact(){",
        "  const MY_ROSTER=[], afterRoster=[], outgoing=[], incoming=[];",
        "  const outValue = outgoing.reduce((s,a) => s + a.value, 0);",
        "  const inValue = incoming.reduce((s,a) => s + a.value, 0);",
        "  const netValue = inValue - outValue;",
        "  const netColor='', netSign='';",
        TEAM_UTIL_OLD,
        "  const wrap={}; wrap.innerHTML=`",
        TRADE_OLD,
        "<div>",
        NOTE_OLD,
        "</div>`;",
        "}",
        STARTUP_OLD,
        "</script>",
    ])
    once = integrate(fixture)
    twice = integrate(once)
    assert once == twice
    assert "storedFundamental !== Number(fundamentalValue)" in once
    assert "rated !== combined.length" in once
    assert "no partial package total shown" in once
    assert "Fundamental Value:" in once and "Market Value:" in once and "Team Utility:" in once
    print("apply_market_value_ui self-test passed: separation, stale-center guard, complete-package guard, and idempotence.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    original = INDEX_PATH.read_text(encoding="utf-8")
    if args.check:
        problems = validate_integrated(original)
        if problems:
            raise RuntimeError("Market Value UI check failed: " + "; ".join(problems))
        print("Market Value UI check passed.")
        return

    if not args.write:
        raise RuntimeError("Use --write, --check, or --selftest")

    updated = integrate(original)
    if updated == original:
        print("Market Value UI already integrated; no change.")
        return
    INDEX_PATH.write_text(updated, encoding="utf-8")
    print("Integrated Fundamental / Market / Team Utility UI into index.html.")


if __name__ == "__main__":
    main()
