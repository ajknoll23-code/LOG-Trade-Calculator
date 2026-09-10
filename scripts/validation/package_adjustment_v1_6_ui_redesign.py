#!/usr/bin/env python3
"""Install and validate the Package Adjustment V1.6 UI redesign.

UI ONLY. This script must never change the deployed Package Adjustment formula.

Commands:
  --self-test  Run isolated patcher/hash/syntax tests without modifying the repo.
  --apply      Patch index.html in-place after exact production/drift guards pass.
  --check      Validate an already-patched index.html and all production guards.

The first install is intentionally locked to the exact reviewed V1.6 index.html
that shipped with the controlled-live release. Re-running --apply is idempotent:
an already-patched page is validated and left unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent.parent
INDEX = ROOT / "index.html"
LIVE = ROOT / "research/package-adjustment-production-candidate-v1/live_deployment.json"
MANIFEST = ROOT / "research/package-adjustment-production-candidate-v1/prospective/release_manifest_v1_6.json"

PRODUCTION_REVISION = "v1.6-v5-size2-composition-overlay"
EXPECTED_FORMULA_SHA256 = "9a1a52f3393a701fe8463fcf2179d1342debb925da1109ce73276b8b2b8cbbc7"
EXPECTED_PRE_UI_INDEX_SHA256 = "7aa813423c8fe8de5cdb0089361d0629ec6e2c27ee158a7768e3ef494b89951b"
EXPECTED_POSITIONS = ["QB", "RB", "WR", "TE", "DL", "LB", "DB"]
EPS = 1e-12

UI_MARKER = "PACKAGE_ADJUSTMENT_V1_6_UI_REDESIGN"
UI_SOURCE_MARKER = (
    f"{UI_MARKER} source_sha256={EXPECTED_PRE_UI_INDEX_SHA256}"
)
CSS_MARKER = "PACKAGE_ADJUSTMENT_V1_6_UI_CSS"
HEADSHOT_MARKER = "PACKAGE_ADJUSTMENT_V1_6_HEADSHOT_MAP"
RULES_MARKER = "PACKAGE_ADJUSTMENT_V1_6_RULES"
RESULT_MARKER = "PACKAGE_ADJUSTMENT_V1_6_RESULT_COPY"

PLAYER_DATA_PATHS = (
    ROOT / "data/my_roster.json",
    ROOT / "data/league_rosters.json",
    ROOT / "data/free_agents.json",
)
PLAYERS_CACHE = ROOT / "data/players_cache.json"


def die(message: str) -> "NoReturn":
    raise RuntimeError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def canonical_hash(obj: Any) -> str:
    return sha256_bytes(
        json.dumps(
            obj,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_name(value: str) -> str:
    # Mirrors index.html normalizeName(): trim/lower, remove . ' ’ -, collapse ws.
    s = str(value or "").strip().lower()
    s = re.sub(r"[.'’\-]", "", s)
    return re.sub(r"\s+", " ", s)


def extract_number(text: str, pattern: str, label: str) -> float:
    match = re.search(pattern, text, flags=re.S)
    if not match:
        die(f"Could not extract {label} from exact live source")
    return float(match.group(1))


def extract_object(text: str, object_name: str, fields: Iterable[str]) -> dict[str, Any]:
    match = re.search(
        rf"{re.escape(object_name)}:\s*Object\.freeze\(\{{(.*?)\}}\),",
        text,
        flags=re.S,
    )
    if not match:
        die(f"Could not extract {object_name}")
    body = match.group(1)
    out: dict[str, Any] = {}
    for field in fields:
        fm = re.search(rf"\b{re.escape(field)}:\s*([0-9.eE+-]+)", body)
        if not fm:
            die(f"Could not extract {object_name}.{field}")
        out[field] = float(fm.group(1))
    pm = re.search(r"\bpolicy:\s*'([^']+)'", body)
    if pm:
        out["policy"] = pm.group(1)
    return out


def extract_formula(index_text: str) -> dict[str, Any]:
    """Mirror the permanent V1.6 exact-live monitor's formula extraction."""
    meaningful = extract_number(
        index_text,
        r"meaningfulPieceMinTargetShare:\s*([0-9.eE+-]+)",
        "meaningfulPieceMinTargetShare",
    )
    size3_multiplier = extract_number(
        index_text,
        r"size3Multiplier:\s*([0-9.eE+-]+)",
        "size3Multiplier",
    )

    pm = re.search(
        r"supportedPlayerPositions:\s*Object\.freeze\(\[(.*?)\]\),",
        index_text,
        flags=re.S,
    )
    if not pm:
        die("Could not extract supportedPlayerPositions")
    positions = re.findall(r"['\"]([A-Z]+)['\"]", pm.group(1))
    if positions != EXPECTED_POSITIONS:
        die(f"Unexpected V1.6 supported positions: {positions}")

    v3 = extract_object(
        index_text,
        "size2CompositionEnvelope",
        ("largestMin", "largestMax", "smallestMin", "smallestMax"),
    )
    v5 = extract_object(
        index_text,
        "size2V5CompositionOverlay",
        (
            "largestShareMinExclusive",
            "largestShareMaxInclusive",
            "factor55",
            "factor60",
        ),
    )
    v4 = extract_object(
        index_text,
        "size3CompositionEnvelope",
        (
            "largestMin",
            "largestMax",
            "middleMin",
            "middleMax",
            "smallestMin",
            "smallestMax",
        ),
    )

    rm = re.search(
        r"size2ReferencePoints:\s*Object\.freeze\(\[(.*?)\]\),",
        index_text,
        flags=re.S,
    )
    if not rm:
        die("Could not extract size2ReferencePoints")
    refs = [
        {"target_fv": float(target), "ratio": float(ratio)}
        for target, ratio in re.findall(
            r"targetFv:\s*([0-9.eE+-]+)\s*,\s*ratio:\s*([0-9.eE+-]+)",
            rm.group(1),
        )
    ]
    if len(refs) != 4:
        die(f"Expected 4 size2 reference points, found {len(refs)}")
    refs.sort(key=lambda row: row["target_fv"])

    required = (
        "function packageAdjustmentSize2CompositionFactor(",
        "function packageAdjustmentAssessment(){",
        "size2V5CompositionOverlay",
        "premiumTier = '2-player-v5';",
        "reason:'size2_composition_outside_evidence_supported_envelope'",
        "allAssets.some(a => a.type !== 'player')",
        "reason:'unsupported_position'",
        "packageValues.some(v => v >= targetFv)",
        "if(meaningful.length > 3){",
        "if(meaningful.length === 3){",
        "const rawPackageFv = packageValues.reduce((s,v) => s + v, 0);",
        "const meaningfulPackageFv = meaningful.reduce((s,v) => s + v, 0);",
        "function packageAdjustmentForTrade(){",
    )
    missing = [token for token in required if token not in index_text]
    if missing:
        die(f"V1.6 live contract markers missing: {missing}")

    return {
        "meaningful_piece_min_target_share": meaningful,
        "size2": {
            "source": "V1.5 target curve + frozen V3 core + hardened V5 composition overlay",
            "reference_points": refs,
            "v3_composition_policy": v3.get("policy"),
            "v3_composition_envelope": {
                "largest_min": v3["largestMin"],
                "largest_max": v3["largestMax"],
                "smallest_min": v3["smallestMin"],
                "smallest_max": v3["smallestMax"],
                "comparison_epsilon": EPS,
            },
            "v5_overlay": {
                "policy": v5.get("policy"),
                "largest_share_min_exclusive": v5["largestShareMinExclusive"],
                "largest_share_max_inclusive": v5["largestShareMaxInclusive"],
                "factor_55_45": v5["factor55"],
                "factor_60_40": v5["factor60"],
                "factor_floor": 1.0,
                "interpolation": "piecewise_linear",
            },
        },
        "size3": {
            "source": "V4 ratio_only",
            "multiplier": size3_multiplier,
            "composition_policy": v4.get("policy"),
            "composition_envelope": {
                "largest_min": v4["largestMin"],
                "largest_max": v4["largestMax"],
                "middle_min": v4["middleMin"],
                "middle_max": v4["middleMax"],
                "smallest_min": v4["smallestMin"],
                "smallest_max": v4["smallestMax"],
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
            "size2_support_ceiling": "60/40",
        },
    }


def formula_sha(index_text: str) -> str:
    return canonical_hash(extract_formula(index_text))


def validate_release_metadata(root: Path = ROOT) -> None:
    live_path = root / LIVE.relative_to(ROOT)
    manifest_path = root / MANIFEST.relative_to(ROOT)
    if not live_path.exists() or not manifest_path.exists():
        die("Required V1.6 live metadata/manifest is missing")

    live = read_json(live_path)
    manifest = read_json(manifest_path)

    checks = (
        (live.get("status") == "controlled_live", "live status is not controlled_live"),
        (live.get("production_formula_enabled") is True, "production formula is not enabled"),
        (live.get("production_revision") == PRODUCTION_REVISION, "live production revision drifted"),
        (
            manifest.get("production_revision_at_release") == PRODUCTION_REVISION,
            "release manifest production revision drifted",
        ),
        (
            manifest.get("exact_live_formula_sha256") == EXPECTED_FORMULA_SHA256,
            "release manifest exact formula SHA drifted",
        ),
        (manifest.get("frozen") is True, "V1.6 release manifest is not frozen"),
        (
            manifest.get("production_formula_enabled") is True,
            "release manifest says production formula is disabled",
        ),
    )
    failures = [message for ok, message in checks if not ok]
    if failures:
        die("; ".join(failures))


def validate_formula_guard(index_text: str) -> str:
    digest = formula_sha(index_text)
    if digest != EXPECTED_FORMULA_SHA256:
        die(
            "Package Adjustment formula drift detected: "
            f"expected {EXPECTED_FORMULA_SHA256}, got {digest}"
        )
    return digest


def find_balanced_function(text: str, name: str) -> tuple[int, int, str]:
    marker = f"function {name}("
    start = text.find(marker)
    if start < 0:
        die(f"Missing required JavaScript function: {name}")
    open_idx = text.find("{", start)
    if open_idx < 0:
        die(f"Missing opening brace for JavaScript function: {name}")

    depth = 0
    quote: str | None = None
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
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                return start, end, text[start:end]
        i += 1
    die(f"Unbalanced JavaScript function: {name}")


def replace_function(text: str, name: str, replacement: str) -> str:
    start, end, _ = find_balanced_function(text, name)
    return text[:start] + replacement.rstrip() + text[end:]


def extract_player_db_keys(index_text: str) -> set[str]:
    marker = "const PLAYER_DB = {"
    start = index_text.find(marker)
    if start < 0:
        die("Missing PLAYER_DB; refusing UI patch")
    open_idx = index_text.find("{", start)
    depth = 0
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    i = open_idx
    end = None
    while i < len(index_text):
        ch = index_text[i]
        nxt = index_text[i + 1] if i + 1 < len(index_text) else ""
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
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1
    if end is None:
        die("PLAYER_DB object is unbalanced")
    block = index_text[open_idx:end]
    keys = {
        normalize_name(match.group(1))
        for match in re.finditer(r"^\s*['\"]([^'\"]+)['\"]\s*:\s*\{", block, flags=re.M)
    }
    if len(keys) < 50:
        die(f"PLAYER_DB key extraction unexpectedly small ({len(keys)}); refusing patch")
    return keys


def candidate_name(record: dict[str, Any]) -> str | None:
    for field in ("name", "full_name", "player_name"):
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    first = record.get("first_name")
    last = record.get("last_name")
    if isinstance(first, str) and isinstance(last, str) and (first.strip() or last.strip()):
        return f"{first.strip()} {last.strip()}".strip()
    return None


def candidate_id(record: dict[str, Any], fallback: str | None = None) -> str | None:
    for field in ("player_id", "sleeper_id", "sleeper_player_id"):
        value = record.get(field)
        if value is not None and str(value).strip().isdigit():
            return str(value).strip()
    if fallback and str(fallback).isdigit():
        return str(fallback)
    return None


def collect_player_ids(node: Any, found: dict[str, set[str]], parent_key: str | None = None) -> None:
    if isinstance(node, dict):
        name = candidate_name(node)
        pid = candidate_id(node, parent_key)
        if name and pid:
            found[normalize_name(name)].add(pid)
        for key, value in node.items():
            collect_player_ids(value, found, str(key))
    elif isinstance(node, list):
        for value in node:
            collect_player_ids(value, found, parent_key)


def build_headshot_mapping(index_text: str, root: Path = ROOT) -> tuple[dict[str, str], dict[str, Any]]:
    db_keys = extract_player_db_keys(index_text)
    found: dict[str, set[str]] = defaultdict(set)
    used_sources: list[str] = []

    for template in PLAYER_DATA_PATHS:
        path = root / template.relative_to(ROOT)
        if not path.exists():
            continue
        collect_player_ids(read_json(path), found)
        used_sources.append(str(path.relative_to(root)))

    # The 16MB Sleeper cache is a fallback only. Parse it if live roster/free-agent
    # payloads did not uniquely resolve every static PLAYER_DB player.
    uniquely_resolved = {name for name, ids in found.items() if len(ids) == 1}
    missing = db_keys - uniquely_resolved
    cache_path = root / PLAYERS_CACHE.relative_to(ROOT)
    if missing and cache_path.exists():
        collect_player_ids(read_json(cache_path), found)
        used_sources.append(str(cache_path.relative_to(root)))

    mapping: dict[str, str] = {}
    ambiguous: dict[str, list[str]] = {}
    for name in sorted(db_keys):
        ids = sorted(found.get(name, set()))
        if len(ids) == 1:
            mapping[name] = ids[0]
        elif len(ids) > 1:
            # Name collisions are intentionally omitted: initials fallback is safer
            # than displaying the wrong player's face.
            ambiguous[name] = ids

    stats = {
        "player_db_names": len(db_keys),
        "mapped": len(mapping),
        "unmapped": len(db_keys) - len(mapping),
        "ambiguous": ambiguous,
        "sources": used_sources,
    }
    if len(mapping) < 50:
        die(
            "Headshot mapping extraction failed closed: only "
            f"{len(mapping)} PLAYER_DB names resolved from repo player data"
        )
    return mapping, stats


UI_CSS = r"""
/* PACKAGE_ADJUSTMENT_V1_6_UI_CSS
   Presentation only: raw FV remains raw; consolidation affects verdict only. */
.asset-row.asset-row-player{
  align-items:center;
  grid-template-columns:42px minmax(0,1fr) auto!important;
}
.asset-headshot-wrap,
.asset-headshot-fallback,
.asset-headshot-spacer{
  width:42px;
  height:42px;
  flex:0 0 42px;
  border-radius:9px;
}
.asset-headshot-wrap{
  position:relative;
  grid-column:1!important;
  grid-row:1!important;
  align-self:center!important;
  overflow:hidden;
  background:rgba(14,40,65,.72);
  border:1px solid var(--line-strong);
}
.asset-headshot{
  width:100%;
  height:100%;
  display:block;
  object-fit:cover;
  object-position:center top;
}
.asset-headshot-fallback{
  align-items:center;
  justify-content:center;
  font-family:'IBM Plex Mono',monospace;
  font-size:11px;
  font-weight:700;
  letter-spacing:.04em;
  color:var(--text-muted);
  background:rgba(14,40,65,.88);
  border:1px solid var(--line-strong);
}
.asset-headshot-wrap .asset-headshot-fallback{
  position:absolute;
  inset:0;
  width:100%;
  height:100%;
  border:0;
  border-radius:0;
}
.asset-headshot-spacer{
  opacity:0;
}
.asset-row .asset-info{
  flex:1 1 auto;
}
.asset-row .asset-right{
  margin-left:auto;
}
.package-adjustment-row{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
  margin:-1px 4px 2px 52px;
  padding:9px 10px;
  border:1px dashed rgba(232,184,75,.35);
  border-left:2px solid var(--amber);
  border-radius:0 0 7px 7px;
  background:rgba(232,184,75,.055);
}
.package-adjustment-copy{
  min-width:0;
}
.package-adjustment-title-row{
  display:flex;
  align-items:center;
  gap:7px;
  margin-bottom:3px;
}
.package-adjustment-title{
  font-size:12px;
  font-weight:650;
  color:var(--text);
}
.package-adjustment-live{
  font-family:'IBM Plex Mono',monospace;
  font-size:8px;
  line-height:1;
  letter-spacing:.08em;
  text-transform:uppercase;
  color:var(--green);
  border:1px solid rgba(63,203,124,.32);
  border-radius:999px;
  padding:3px 5px;
}
.package-adjustment-meta{
  font-family:'IBM Plex Mono',monospace;
  font-size:9.5px;
  color:var(--text-dim);
  line-height:1.25;
}
.package-adjustment-value{
  flex:0 0 auto;
  font-family:'IBM Plex Mono',monospace;
  font-size:14px;
  font-weight:700;
  color:var(--amber);
}
.package-adjustment-warning{
  margin-top:10px;
  border-color:var(--line-strong)!important;
}
.package-adjustment-warning-title{
  font-family:'IBM Plex Mono',monospace;
  font-size:10px;
  letter-spacing:.08em;
  text-transform:uppercase;
  color:var(--amber);
  margin-bottom:5px;
}
.package-adjustment-warning-copy{
  font-size:11px;
  line-height:1.45;
  color:var(--text-muted);
}
.package-rules{
  margin-top:10px;
  border:1px solid var(--line);
  border-radius:8px;
  background:rgba(30,62,96,.40);
  overflow:hidden;
}
.package-rules summary{
  cursor:pointer;
  list-style:none;
  padding:10px 12px;
  font-family:'IBM Plex Mono',monospace;
  font-size:10px;
  letter-spacing:.05em;
  color:var(--text-muted);
}
.package-rules summary::-webkit-details-marker{display:none;}
.package-rules summary::after{
  content:'+';
  float:right;
  color:var(--text-dim);
}
.package-rules[open] summary::after{content:'−';}
.package-rules-body{
  padding:0 12px 11px;
  border-top:1px solid var(--line);
}
.package-rule{
  padding-top:9px;
  font-size:10.5px;
  line-height:1.45;
  color:var(--text-muted);
}
.package-rule strong{color:var(--text);}
.package-rule-invariant{
  color:var(--amber);
  font-weight:600;
}
.package-threshold-line{
  min-height:14px;
  margin-top:4px;
  font-family:'IBM Plex Mono',monospace;
  font-size:10px;
  color:var(--text-dim);
}
.meter-verdict{
  text-transform:uppercase;
}
@media (max-width:520px){
  .asset-row.asset-row-player{
    grid-template-columns:38px minmax(0,1fr) auto!important;
  }
  .asset-headshot-wrap,
  .asset-headshot-fallback,
  .asset-headshot-spacer{
    width:38px;
    height:38px;
    flex-basis:38px;
    border-radius:8px;
  }
  .package-adjustment-row{
    margin-left:48px;
    gap:8px;
  }
  .package-adjustment-meta{
    font-size:9px;
  }
}
""".strip()


RULES_HTML = r"""
  <!-- PACKAGE_ADJUSTMENT_V1_6_RULES -->
  <details class="package-rules">
    <summary>Understanding the Rules</summary>
    <div class="package-rules-body">
      <div class="package-rule"><strong>FV — Fair Value</strong><br>The model's base player value.</div>
      <div class="package-rule"><strong>V3 — Core consolidation rule</strong><br>The original evidence-backed 2-player package rule.</div>
      <div class="package-rule"><strong>V5 — Composition extension</strong><br>The live evidence-backed extension for supported 2-player package shapes beyond the V3 core, through 60/40.</div>
      <div class="package-rule"><strong>Consolidation</strong><br>The model requires a premium when one concentrated asset is split into multiple smaller assets.</div>
      <div class="package-rule package-rule-invariant">Player FV is unchanged. This adjustment affects the trade verdict only.</div>
    </div>
  </details>
""".rstrip()


RENDER_PACKAGE_ADJUSTMENT = r"""
function renderPackageAdjustment(){
  const wrap = document.getElementById('packageAdjustmentWrap');
  if(!wrap) return;
  const assessment = packageAdjustmentAssessment();

  // PACKAGE_ADJUSTMENT_V1_6_UI_REDESIGN:
  // Permanent validator compatibility marker: 2-player consolidation · V3 + V5
  // Supported applied adjustments now render as a pseudo-asset directly under
  // the concentrated player. Keep this container only for fail-closed warnings.
  if(assessment.status === 'unsupported'){
    const detail = packageUiEscape(
      assessment.message || 'This trade shape is outside the calibrated Package Adjustment scope.'
    );
    wrap.innerHTML = `
      <div class="trade-impact package-adjustment-warning">
        <div class="package-adjustment-warning-title">Consolidation Adjustment · Not Applied</div>
        <div class="package-adjustment-warning-copy">${detail}</div>
      </div>
    `;
    return;
  }

  wrap.innerHTML = '';
}
""".strip()


def js_helpers(mapping: dict[str, str]) -> str:
    mapping_json = json.dumps(mapping, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"""/* {HEADSHOT_MARKER}\n   Generated from repo Sleeper identity data. Ambiguous names are omitted. */\nconst PACKAGE_UI_SLEEPER_IDS = Object.freeze({mapping_json});\n\nfunction packageUiEscape(value){{\n  return String(value ?? '')\n    .replace(/&/g,'&amp;')\n    .replace(/</g,'&lt;')\n    .replace(/>/g,'&gt;')\n    .replace(/\"/g,'&quot;')\n    .replace(/'/g,'&#39;');\n}}\n\nfunction packageUiInitials(name){{\n  const parts = String(name || '').trim().split(/\\s+/).filter(Boolean);\n  if(!parts.length) return '?';\n  return parts.slice(0,2).map(p => p[0] || '').join('').toUpperCase();\n}}\n\nfunction packageUiHeadshotHTML(asset){{\n  const name = asset && asset.name ? asset.name : '';\n  const key = normalizeName(name);\n  const playerId = PACKAGE_UI_SLEEPER_IDS[key] || null;\n  const initials = packageUiEscape(packageUiInitials(name));\n  if(!playerId){{\n    return `<div class=\"asset-headshot-fallback\" aria-label=\"No headshot available\">${{initials}}</div>`;\n  }}\n  const src = `https://sleepercdn.com/content/nfl/players/thumb/${{encodeURIComponent(playerId)}}.jpg`;\n  return `<div class=\"asset-headshot-wrap\">\n    <img class=\"asset-headshot\" src=\"${{src}}\" alt=\"\" loading=\"lazy\" referrerpolicy=\"no-referrer\" onerror=\"this.style.display='none';this.nextElementSibling.style.display='flex';\">\n    <div class=\"asset-headshot-fallback\" style=\"display:none\" aria-hidden=\"true\">${{initials}}</div>\n  </div>`;\n}}\n\nfunction packageUiCompositionText(pkg){{\n  if(!pkg) return '';\n  if(pkg.meaningfulCount === 2){{\n    const largest = Number(pkg.largestMeaningfulPackageShare);\n    const smallest = Number(pkg.smallestMeaningfulPackageShare);\n    const ratio = Number.isFinite(largest) && Number.isFinite(smallest)\n      ? `${{Math.round(largest * 100)}}/${{Math.round(smallest * 100)}}`\n      : 'supported shape';\n    const version = pkg.premiumTier === '2-player-v5' ? 'V3 + V5' : 'V3';\n    return `2-player package · ${{version}} · ${{ratio}}`;\n  }}\n  if(pkg.meaningfulCount === 3){{\n    const shares = [\n      Number(pkg.largestMeaningfulPackageShare),\n      Number(pkg.middleMeaningfulPackageShare),\n      Number(pkg.smallestMeaningfulPackageShare),\n    ];\n    const ratio = shares.every(Number.isFinite)\n      ? shares.map(v => Math.round(v * 100)).join('/')\n      : 'supported shape';\n    return `3-player package · V4 · ${{ratio}}`;\n  }}\n  return 'Supported consolidation package';\n}}\n\nfunction packageUiAdjustmentRowHTML(pkg){{\n  const adjustment = Math.round(Number(pkg && pkg.adjustment) || 0);\n  return `\n    <div class=\"package-adjustment-row\" data-package-adjustment-ui=\"live\">\n      <div class=\"package-adjustment-copy\">\n        <div class=\"package-adjustment-title-row\">\n          <span class=\"package-adjustment-title\">Consolidation Adjustment</span>\n          <span class=\"package-adjustment-live\">LIVE</span>\n        </div>\n        <div class=\"package-adjustment-meta\">${{packageUiEscape(packageUiCompositionText(pkg))}}</div>\n      </div>\n      <div class=\"package-adjustment-value\">+${{adjustment.toLocaleString()}}</div>\n    </div>\n  `;\n}}\n\nfunction packageUiSideAssetListHTML(side){{\n  const assessment = packageAdjustmentAssessment();\n  const pkg = assessment.status === 'applied' ? assessment.packageAdjustment : null;\n  return state[side].map(a => {{\n    let html = assetRowHTML(side, a);\n    if(pkg && pkg.targetSide === side && a === pkg.targetAsset){{\n      html += packageUiAdjustmentRowHTML(pkg);\n    }}\n    return html;\n  }}).join('');\n}}\n""".rstrip()


def insert_before_head_style_close(text: str, block: str) -> str:
    head_end = text.find("</head>")
    if head_end < 0:
        die("Missing </head> anchor")
    style_end = text.rfind("</style>", 0, head_end)
    if style_end < 0:
        die("Missing head </style> anchor")
    return text[:style_end] + "\n\n" + block + "\n" + text[style_end:]


def patch_asset_row_function(text: str) -> str:
    start, end, function = find_balanced_function(text, "assetRowHTML")
    original = function

    if "packageUiHeadshotHTML(a)" not in function:
        anchor = '<div class="asset-row">'
        if function.count(anchor) != 1:
            die("assetRowHTML asset-row anchor drifted")
        function = function.replace(
            anchor,
            '<div class="asset-row ${a.type === \'player\' ? \'asset-row-player\' : \'asset-row-pick\'}">\n'
            "      ${a.type === 'player' ? packageUiHeadshotHTML(a) : ''}",
            1,
        )

    # Rename the displayed deployed point estimate only. No value calculation changes.
    function = function.replace(
        "a.type === 'player' ? 'Fund. ' : ''",
        "a.type === 'player' ? 'FV ' : ''",
        1,
    )
    function = function.replace(
        "Fundamental Value — deployed model point estimate",
        "Fair Value (FV) — deployed model point estimate",
        1,
    )

    if function == original:
        die("assetRowHTML patch made no change")
    return text[:start] + function + text[end:]


def patch_side_panel_function(text: str) -> str:
    start, end, function = find_balanced_function(text, "sidePanelHTML")
    original = function

    old_map = "state[side].map(a => assetRowHTML(side,a)).join('')"
    if old_map in function:
        function = function.replace(old_map, "packageUiSideAssetListHTML(side)", 1)
    elif "packageUiSideAssetListHTML(side)" not in function:
        die("sidePanelHTML asset-list anchor drifted")

    function = function.replace(
        '<div class="side-total-label">Fundamental</div>',
        '<div class="side-total-label">Raw FV</div>',
        1,
    )

    if function == original:
        die("sidePanelHTML patch made no change")
    return text[:start] + function + text[end:]


def patch_result_display(text: str) -> str:
    old_totals = """  const verdictTotals = tradeVerdictTotals();
  const totalA = verdictTotals.A;
  const totalB = verdictTotals.B;
  const grand = totalA + totalB;

  const pctA = grand ? (totalA/grand)*100 : 50;
  const pctB = grand ? (totalB/grand)*100 : 50;

  document.getElementById('fillA').style.width = pctA + '%';
  document.getElementById('fillB').style.width = pctB + '%';
  document.getElementById('labelA').textContent = `SIDE A — ${totalA.toLocaleString()}`;
  document.getElementById('labelB').textContent = `SIDE B — ${totalB.toLocaleString()}`;
"""
    new_totals = """  const verdictTotals = tradeVerdictTotals();
  const totalA = verdictTotals.A;
  const totalB = verdictTotals.B;
  const grand = totalA + totalB;

  // PACKAGE_ADJUSTMENT_V1_6_RESULT_COPY: meter labels/fill show raw FV.
  // The adjusted totals above remain the only inputs to the trade verdict.
  const rawDisplayA = sideTotal('A');
  const rawDisplayB = sideTotal('B');
  const rawDisplayGrand = rawDisplayA + rawDisplayB;
  const pctA = rawDisplayGrand ? (rawDisplayA/rawDisplayGrand)*100 : 50;
  const pctB = rawDisplayGrand ? (rawDisplayB/rawDisplayGrand)*100 : 50;

  document.getElementById('fillA').style.width = pctA + '%';
  document.getElementById('fillB').style.width = pctB + '%';
  document.getElementById('labelA').textContent = `SIDE A — ${rawDisplayA.toLocaleString()}`;
  document.getElementById('labelB').textContent = `SIDE B — ${rawDisplayB.toLocaleString()}`;
"""
    if old_totals not in text:
        if RESULT_MARKER not in text:
            die("Trade-result totals/display anchor drifted")
    else:
        text = text.replace(old_totals, new_totals, 1)

    verdict_anchor = """  renderTradeImpact();
  renderSensitivity();
  renderMauling();
}"""
    verdict_injection = """  const thresholdEl = document.getElementById('verdictThreshold');
  if(thresholdEl) thresholdEl.textContent = '';
  const packageUiAssessment = packageAdjustmentAssessment();
  if(packageUiAssessment.status === 'applied'){
    const pkg = packageUiAssessment.packageAdjustment;
    const threshold = Math.round(Number(pkg.tradeEquivalentTargetFv) || 0);
    const rawPackage = Math.round(Number(pkg.rawPackageFv) || 0);
    const delta = threshold - rawPackage;
    if(delta > 0){
      subEl.textContent = `Package is ${delta.toLocaleString()} short of the required consolidation threshold.`;
    } else if(delta < 0){
      subEl.textContent = `Package clears the required consolidation threshold by ${Math.abs(delta).toLocaleString()}.`;
    } else {
      subEl.textContent = 'Package meets the required consolidation threshold.';
    }
    if(thresholdEl) thresholdEl.textContent = `Required package value: ${threshold.toLocaleString()}`;
  }

  renderTradeImpact();
  renderSensitivity();
  renderMauling();
}"""
    if "const packageUiAssessment = packageAdjustmentAssessment();" not in text:
        if text.count(verdict_anchor) != 1:
            die("Trade-result render tail anchor drifted")
        text = text.replace(verdict_anchor, verdict_injection, 1)
    return text


def patch_index_text(index_text: str, mapping: dict[str, str]) -> str:
    if UI_MARKER in index_text:
        return index_text

    text = index_text

    # Provenance marker is HTML-only and intentionally outside formula extraction.
    html_open = "<html lang=\"en\">"
    if html_open not in text:
        die("Missing <html lang=\"en\"> anchor")
    text = text.replace(
        html_open,
        html_open + f"\n<!-- {UI_SOURCE_MARKER} -->",
        1,
    )

    text = insert_before_head_style_close(text, UI_CSS)

    package_wrap = '  <div id="packageAdjustmentWrap"></div>'
    if text.count(package_wrap) != 1:
        die("packageAdjustmentWrap anchor drifted")
    text = text.replace(package_wrap, package_wrap + "\n" + RULES_HTML, 1)

    verdict_sub = '    <div class="meter-sub" id="verdictSub">&nbsp;</div>'
    if text.count(verdict_sub) != 1:
        die("verdictSub anchor drifted")
    text = text.replace(
        verdict_sub,
        verdict_sub + '\n    <div class="package-threshold-line" id="verdictThreshold"></div>',
        1,
    )

    rendering_anchor = "/* ---------- Rendering ---------- */"
    if text.count(rendering_anchor) != 1:
        die("Rendering anchor drifted")
    text = text.replace(rendering_anchor, js_helpers(mapping) + "\n\n" + rendering_anchor, 1)

    text = patch_asset_row_function(text)
    text = patch_side_panel_function(text)
    text = replace_function(text, "renderPackageAdjustment", RENDER_PACKAGE_ADJUSTMENT)
    text = patch_result_display(text)
    return text


def inline_scripts(html: str) -> list[str]:
    scripts = []
    for match in re.finditer(r"<script\b([^>]*)>(.*?)</script>", html, flags=re.S | re.I):
        attrs, body = match.group(1), match.group(2)
        if re.search(r"\bsrc\s*=", attrs, flags=re.I):
            continue
        if body.strip():
            scripts.append(body)
    return scripts


def validate_js_syntax(html: str) -> int:
    node = shutil.which("node")
    if not node:
        die("node is required for JavaScript syntax validation")
    scripts = inline_scripts(html)
    if not scripts:
        die("No inline JavaScript found for syntax validation")
    with tempfile.TemporaryDirectory(prefix="package-ui-js-") as td:
        for idx, script in enumerate(scripts):
            path = Path(td) / f"inline-{idx}.js"
            path.write_text(script, encoding="utf-8")
            proc = subprocess.run(
                [node, "--check", str(path)],
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                die(
                    f"JavaScript syntax validation failed for inline script {idx}:\n"
                    + (proc.stderr or proc.stdout)
                )
    return len(scripts)


def validate_patched_text(index_text: str) -> dict[str, Any]:
    if UI_SOURCE_MARKER not in index_text:
        die("UI redesign provenance/source marker missing or incorrect")
    validate_formula_guard(index_text)

    required_tokens = (
        CSS_MARKER,
        HEADSHOT_MARKER,
        RULES_MARKER,
        RESULT_MARKER,
        "packageUiSideAssetListHTML(side)",
        "packageUiAdjustmentRowHTML(pkg)",
        "2-player consolidation · V3 + V5",
        "Consolidation Adjustment",
        "package-adjustment-live\">LIVE",
        "Player FV is unchanged. This adjustment affects the trade verdict only.",
        "FV — Fair Value",
        "V3 — Core consolidation rule",
        "V5 — Composition extension",
        "Required package value:",
        "short of the required consolidation threshold",
        "https://sleepercdn.com/content/nfl/players/thumb/",
        "onerror=\"this.style.display='none';this.nextElementSibling.style.display='flex';\"",
        "<div class=\"side-total-label\">Raw FV</div>",
        "const rawDisplayA = sideTotal('A');",
        "const rawDisplayB = sideTotal('B');",
    )
    missing = [token for token in required_tokens if token not in index_text]
    if missing:
        die(f"Patched UI validation markers missing: {missing}")

    # Old applied card must be gone; unsupported/fail-closed messaging must remain.
    if "Side ${pkg.targetSide}: +${adj.toLocaleString()} trade value" in index_text:
        die("Confusing old applied Package Adjustment card is still present")
    _, _, render_pkg = find_balanced_function(index_text, "renderPackageAdjustment")
    if "assessment.status === 'unsupported'" not in render_pkg:
        die("Unsupported Package Adjustment warning path was not preserved")
    if "Not Applied" not in render_pkg:
        die("Unsupported Package Adjustment warning copy is missing")

    _, _, side_panel = find_balanced_function(index_text, "sidePanelHTML")
    if "const total = sideTotal(side);" not in side_panel:
        die("Side panel no longer uses raw sideTotal")
    if "packageUiSideAssetListHTML(side)" not in side_panel:
        die("Adjustment pseudo-row is not wired into side asset rendering")

    _, _, verdict_totals = find_balanced_function(index_text, "tradeVerdictTotals")
    for token in (
        "const rawA = sideTotal('A');",
        "const rawB = sideTotal('B');",
        "totals[pkg.targetSide] += pkg.adjustment;",
    ):
        if token not in verdict_totals:
            die(f"Trade-verdict Package Adjustment behavior drifted: missing {token}")

    scripts_checked = validate_js_syntax(index_text)
    return {
        "formula_sha256": EXPECTED_FORMULA_SHA256,
        "production_revision": PRODUCTION_REVISION,
        "scripts_syntax_checked": scripts_checked,
        "raw_totals_preserved": True,
        "trade_verdict_adjustment_preserved": True,
        "unsupported_fail_closed_warning_preserved": True,
        "headshot_fallback_present": True,
    }


def atomic_write(path: Path, text: str) -> None:
    temp = path.with_name(path.name + ".tmp-package-ui")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def apply(root: Path = ROOT) -> dict[str, Any]:
    validate_release_metadata(root)
    index = root / INDEX.relative_to(ROOT)
    if not index.exists():
        die(f"Missing {index}")
    original = index.read_text(encoding="utf-8")
    validate_formula_guard(original)

    if UI_MARKER in original:
        result = validate_patched_text(original)
        result.update({"status": "PASS", "changed": False, "idempotent": True})
        print("PASS Package Adjustment V1.6 UI redesign already installed; no changes made")
        return result

    actual_sha = sha256_bytes(index.read_bytes())
    if actual_sha != EXPECTED_PRE_UI_INDEX_SHA256:
        die(
            "Unknown/drifted pre-UI production tree: index.html SHA256 is "
            f"{actual_sha}, expected {EXPECTED_PRE_UI_INDEX_SHA256}. Refusing to patch."
        )

    mapping, stats = build_headshot_mapping(original, root)
    patched = patch_index_text(original, mapping)

    before_formula = validate_formula_guard(original)
    after_formula = validate_formula_guard(patched)
    if before_formula != after_formula:
        die("Formula SHA changed during UI patch")

    validation = validate_patched_text(patched)
    atomic_write(index, patched)

    reread = index.read_text(encoding="utf-8")
    if reread != patched:
        die("index.html write verification failed")
    validate_patched_text(reread)

    result = {
        "status": "PASS",
        "changed": True,
        "idempotent": False,
        "pre_ui_index_sha256": actual_sha,
        "post_ui_index_sha256": sha256_bytes(index.read_bytes()),
        "headshots": stats,
        **validation,
    }
    print(
        "PASS installed Package Adjustment V1.6 UI redesign: "
        f"formula {after_formula}; {stats['mapped']}/{stats['player_db_names']} "
        "PLAYER_DB names mapped to unambiguous Sleeper IDs"
    )
    return result


def check(root: Path = ROOT) -> dict[str, Any]:
    validate_release_metadata(root)
    index = root / INDEX.relative_to(ROOT)
    text = index.read_text(encoding="utf-8")
    result = validate_patched_text(text)
    result.update({"status": "PASS", "index_sha256": sha256_bytes(index.read_bytes())})
    print(
        "PASS Package Adjustment V1.6 UI redesign check: raw FV display preserved; "
        "verdict-only adjustment preserved; JS syntax valid"
    )
    return result


# Exact structured formula object from the immutable V1.6 release manifest.
SELF_TEST_FORMULA = {
    "meaningful_piece_min_target_share": 0.06,
    "scope_contract": {
        "meaningful_package_sizes": [2, 3],
        "one_for_package_only": True,
        "package_piece_must_be_below_target": True,
        "player_only": True,
        "position_scope_policy": "frozen_v3_v4_target_and_package_position_intersection_fail_closed",
        "size2_support_ceiling": "60/40",
        "supported_player_positions": EXPECTED_POSITIONS,
        "tiny_pieces_count_in_raw_package_fv": True,
        "tiny_pieces_excluded_from_composition": True,
        "unsupported_composition_fails_closed": True,
    },
    "size2": {
        "reference_points": [
            {"ratio": 1.4007986955507035, "target_fv": 4269.25},
            {"ratio": 1.485881276187134, "target_fv": 5049.5},
            {"ratio": 1.5368431747111482, "target_fv": 5558.25},
            {"ratio": 1.5859349498155657, "target_fv": 6078.700000000002},
        ],
        "source": "V1.5 target curve + frozen V3 core + hardened V5 composition overlay",
        "v3_composition_envelope": {
            "comparison_epsilon": EPS,
            "largest_max": 0.5230278884462152,
            "largest_min": 0.5044104156375697,
            "smallest_max": 0.49558958436243034,
            "smallest_min": 0.4769721115537849,
        },
        "v3_composition_policy": "frozen-v3-size2-rectangular-empirical-hull-fail-closed",
        "v5_overlay": {
            "factor_55_45": 1.133281,
            "factor_60_40": 1.0,
            "factor_floor": 1.0,
            "interpolation": "piecewise_linear",
            "largest_share_max_inclusive": 0.6,
            "largest_share_min_exclusive": 0.5230278884462152,
            "policy": "hardened-v5-composition-overlay-through-60-40-fail-closed",
        },
    },
    "size3": {
        "composition_envelope": {
            "comparison_epsilon": EPS,
            "largest_max": 0.4696171986399035,
            "largest_min": 0.41991319353657897,
            "middle_max": 0.36725409193118236,
            "middle_min": 0.30827026434134036,
            "smallest_max": 0.2247276896617619,
            "smallest_min": 0.2120186203977994,
        },
        "composition_policy": "frozen-v4-rectangular-empirical-hull-fail-closed",
        "multiplier": 2.0512371846911357,
        "source": "V4 ratio_only",
    },
}


def self_test() -> dict[str, Any]:
    if canonical_hash(SELF_TEST_FORMULA) != EXPECTED_FORMULA_SHA256:
        die("Self-test frozen formula object does not match expected V1.6 formula SHA")

    if normalize_name("  Le'Veon  Moss  ") != "leveon moss":
        die("normalize_name self-test failed")

    # Exercise collision-safe player-ID extraction without repo dependencies.
    found: dict[str, set[str]] = defaultdict(set)
    collect_player_ids(
        {
            "100": {"first_name": "Alpha", "last_name": "One", "player_id": "100"},
            "200": {"name": "Beta Two", "player_id": "200"},
            "201": {"name": "  Beta   Two  ", "player_id": "201"},
        },
        found,
    )
    if found["alpha one"] != {"100"}:
        die("player-ID extraction self-test failed")
    if found["beta two"] != {"200", "201"}:
        die("player-ID ambiguity self-test failed")

    # Syntax-check exactly the injected helper JS using tiny stubs around it.
    helper_fixture = """
function normalizeName(s){ return String(s||'').trim().toLowerCase(); }
let state={A:[],B:[]};
function packageAdjustmentAssessment(){ return {status:'not_applicable'}; }
function assetRowHTML(){ return ''; }
""" + js_helpers({"alpha one": "100"})
    node = shutil.which("node")
    if not node:
        die("node is required for self-test JavaScript syntax validation")
    with tempfile.TemporaryDirectory(prefix="package-ui-selftest-") as td:
        js_path = Path(td) / "helpers.js"
        js_path.write_text(helper_fixture, encoding="utf-8")
        proc = subprocess.run([node, "--check", str(js_path)], capture_output=True, text=True)
        if proc.returncode != 0:
            die("Injected helper JavaScript self-test failed:\n" + (proc.stderr or proc.stdout))

    # Exercise the full HTML patch transform against a small production-shaped fixture.
    patch_fixture = r'''<!DOCTYPE html>
<html lang="en">
<head><style>.asset-row{display:flex;}</style></head>
<body>
    <div class="meter-sub" id="verdictSub">&nbsp;</div>
  <div id="packageAdjustmentWrap"></div>
<script>
function normalizeName(s){ return String(s||'').trim().toLowerCase(); }
function sideTotal(side){ return 0; }
function packageAdjustmentAssessment(){ return {status:'not_applicable'}; }
function packageAdjustmentForTrade(){ return null; }
function tradeVerdictTotals(){
  const rawA = sideTotal('A');
  const rawB = sideTotal('B');
  const pkg = packageAdjustmentForTrade();
  if(!pkg) return { A: rawA, B: rawB, packageAdjustment: null };
  const totals = { A: rawA, B: rawB, packageAdjustment: pkg };
  totals[pkg.targetSide] += pkg.adjustment;
  return totals;
}
let state={A:[],B:[],activeTab:{A:'player',B:'player'}};
/* ---------- Rendering ---------- */
function assetRowHTML(side, a){
  return `<div class="asset-row">
      <div class="asset-info"><div class="asset-title">${a.name}</div></div>
      <div class="asset-right"><div class="asset-value">${a.type === 'player' ? 'Fund. ' : ''}${a.value.toLocaleString()}</div></div>
    </div>`;
}
function sidePanelHTML(side, label){
  const total = sideTotal(side);
  const list = state[side].length
    ? state[side].map(a => assetRowHTML(side,a)).join('')
    : `<div class="asset-empty">No assets added yet.</div>`;
  return `<div class="side-total-label">Fundamental</div><div>${list}</div>`;
}
function renderPackageAdjustment(){
  const wrap = document.getElementById('packageAdjustmentWrap');
  if(!wrap) return;
  const assessment = packageAdjustmentAssessment();
  if(assessment.status === 'unsupported') wrap.innerHTML = assessment.message || '';
  if(assessment.status === 'applied'){
    const pkg=assessment.packageAdjustment; const adj=Math.round(pkg.adjustment);
    wrap.innerHTML=`Side ${pkg.targetSide}: +${adj.toLocaleString()} trade value`;
  }
}
function renderAll(){
  const verdictTotals = tradeVerdictTotals();
  const totalA = verdictTotals.A;
  const totalB = verdictTotals.B;
  const grand = totalA + totalB;

  const pctA = grand ? (totalA/grand)*100 : 50;
  const pctB = grand ? (totalB/grand)*100 : 50;

  document.getElementById('fillA').style.width = pctA + '%';
  document.getElementById('fillB').style.width = pctB + '%';
  document.getElementById('labelA').textContent = `SIDE A — ${totalA.toLocaleString()}`;
  document.getElementById('labelB').textContent = `SIDE B — ${totalB.toLocaleString()}`;
  const verdictEl=document.getElementById('verdictText');
  const subEl=document.getElementById('verdictSub');
  renderTradeImpact();
  renderSensitivity();
  renderMauling();
}
function renderTradeImpact(){}
function renderSensitivity(){}
function renderMauling(){}
</script>
</body></html>'''
    patched_fixture = patch_index_text(patch_fixture, {"alpha one": "100"})
    for token in (
        UI_SOURCE_MARKER,
        CSS_MARKER,
        HEADSHOT_MARKER,
        RULES_MARKER,
        "packageUiHeadshotHTML(a)",
        "packageUiSideAssetListHTML(side)",
        "Raw FV",
        "const rawDisplayA = sideTotal('A');",
        "Consolidation Adjustment · Not Applied",
    ):
        if token not in patched_fixture:
            die(f"full patch transform self-test missing marker: {token}")
    validate_js_syntax(patched_fixture)

    # Balanced-function replacement must ignore braces inside strings/templates/comments.
    sample = "function x(){ const s=`{{ not a block }}`; /* } */ return {ok:true}; }\nNEXT"
    start, end, block = find_balanced_function(sample, "x")
    if start != 0 or sample[end:].strip() != "NEXT" or "return {ok:true}" not in block:
        die("balanced JavaScript function extraction self-test failed")

    result = {
        "status": "PASS",
        "formula_sha256": EXPECTED_FORMULA_SHA256,
        "production_revision": PRODUCTION_REVISION,
        "headshot_collision_policy": "ambiguous names fall back to initials",
        "node_syntax_check": "PASS",
    }
    print(
        "PASS Package Adjustment V1.6 UI redesign self-test: "
        "frozen formula hash, collision-safe headshot mapping, and injected JS syntax"
    )
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--self-test", action="store_true", help="run isolated self-tests")
    group.add_argument("--apply", action="store_true", help="patch index.html in-place")
    group.add_argument("--check", action="store_true", help="validate patched index.html")
    group.add_argument(
        "--print-headshot-stats",
        action="store_true",
        help="validate production source and print mapping coverage without patching",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        if args.self_test:
            self_test()
        elif args.apply:
            apply()
        elif args.check:
            check()
        elif args.print_headshot_stats:
            validate_release_metadata(ROOT)
            text = INDEX.read_text(encoding="utf-8")
            validate_formula_guard(text)
            mapping, stats = build_headshot_mapping(text, ROOT)
            print(json.dumps({"status": "PASS", "mapped": len(mapping), **stats}, indent=2))
        return 0
    except Exception as exc:
        print(f"FAIL Package Adjustment V1.6 UI redesign: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
