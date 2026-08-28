#!/usr/bin/env python3
"""Prepare (but do not automatically apply) the preferred IDP V1 bake.

Default behavior is preview-only:
  * rebuild the preferred model-delta transport candidate from source inputs,
  * verify the current index.html PROD_MULT table still matches the immutable
    pre-V1 baseline for every canonical key,
  * create a machine-readable old/new patch manifest,
  * create a human-readable report,
  * create a unified index.html preview patch,
  * validate a temporary candidate HTML through Node syntax and the repaired
    snapshot_values.py parser/value engine.

Production modification requires the explicit ``--apply`` flag. Even then the
same immutable-baseline guard runs first. This script never commits or pushes.
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import re
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import snapshot_values
from idp_v1_model_delta_transport_candidate import build_candidate

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
INDEX_PATH = REPO_ROOT / "index.html"
BASELINE_PATH = SCRIPT_DIR / "prod_mult_pre_v1_baseline.json"
PATCH_JSON = SCRIPT_DIR / "idp_v1_prod_mult_patch.json"
PATCH_REPORT = SCRIPT_DIR / "idp_v1_prod_mult_patch_report.md"
PATCH_DIFF = SCRIPT_DIR / "idp_v1_index_preview.patch"


def extract_prod_block(text):
    marker = "const PROD_MULT_DATA = {"
    start = text.find(marker)
    if start < 0:
        raise RuntimeError("PROD_MULT_DATA block not found")
    open_idx = text.find("{", start)
    depth = 0
    quote = None
    escaped = False
    for i in range(open_idx, len(text)):
        ch = text[i]
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in ("'", '"', '`'):
            quote = ch
            continue
        if ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return open_idx, i + 1, text[open_idx:i + 1]
    raise RuntimeError("unterminated PROD_MULT_DATA block")


def parse_prod_values(block):
    return {k: float(v) for k, v in re.findall(r"'([^']+)'\s*:\s*([0-9.]+)", block)}


def fmt_value(v):
    s = f"{float(v):.4f}".rstrip("0").rstrip(".")
    return s if "." in s else s + ".0"


def apply_values_to_text(text, candidate):
    start, end, block = extract_prod_block(text)
    pattern = re.compile(r"('([^']+)'\s*:\s*)([0-9.]+)")
    changed = []

    def repl(m):
        key = m.group(2)
        if key not in candidate["players"]:
            return m.group(0)
        old = float(m.group(3))
        new = float(candidate["players"][key]["candidate_prod_mult"])
        if abs(old - new) < 1e-12:
            return m.group(0)
        changed.append((key, old, new))
        return m.group(1) + fmt_value(new)

    new_block = pattern.sub(repl, block)
    return text[:start] + new_block + text[end:], changed


def verify_true_live_baseline(current_values, baseline_values):
    missing = sorted(set(baseline_values) - set(current_values))
    mismatched = []
    for key in sorted(set(baseline_values) & set(current_values)):
        if abs(float(baseline_values[key]) - float(current_values[key])) > 1e-12:
            mismatched.append((key, baseline_values[key], current_values[key]))
    if missing or mismatched:
        msg = ["Current index PROD_MULT no longer matches immutable pre-V1 baseline; refusing preview/apply."]
        if missing: msg.append(f"Missing keys ({len(missing)}): {missing[:10]}")
        if mismatched: msg.append(f"Mismatches ({len(mismatched)}): {mismatched[:10]}")
        raise RuntimeError("\n".join(msg))


def validate_preview(candidate_text, candidate_doc):
    # JS syntax.
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", candidate_text, re.S | re.I)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write("\n".join(scripts)); js_path = f.name
    try:
        subprocess.run(["node", "--check", js_path], check=True, capture_output=True, text=True)
    finally:
        Path(js_path).unlink(missing_ok=True)

    # Actual value engine parse/evaluation.
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(candidate_text); html_path = f.name
    try:
        cfg = snapshot_values.load_from_html(html_path)
        vals = snapshot_values.compute_all_values(cfg)
    finally:
        Path(html_path).unlink(missing_ok=True)

    # Every preferred candidate key that exists in the live table must parse
    # back to exactly the candidate raw prod_mult after formatting.
    parsed = cfg["prod_mult"]
    mismatches = []
    for key, r in candidate_doc["players"].items():
        if key in parsed:
            expected = float(fmt_value(r["candidate_prod_mult"]))
            if abs(parsed[key] - expected) > 1e-12:
                mismatches.append((key, expected, parsed[key]))
    if mismatches:
        raise RuntimeError(f"preview parse mismatch: {mismatches[:10]}")
    return vals


def build_report(candidate, changes, patch_entries, preview_values):
    by_pos = Counter(e["pos"] for e in patch_entries)
    by_status = Counter(e["update_status"] for e in patch_entries)
    by_cohort = Counter(e["v1_source_cohort"] for e in patch_entries)
    largest = sorted(patch_entries, key=lambda e: abs(e["pct_change"]), reverse=True)[:25]
    anchors = ["bradley chubb", "aidan hutchinson", "myles garrett", "fred warner", "roquan smith", "ej speed", "isaiah mcduffie"]

    lines = [
        "# IDP V1 Preferred Bake Preview",
        "",
        "## Status",
        "",
        "**Preview only. Production `index.html` has not been modified.**",
        "",
        f"- Preferred candidate method: `{candidate['method']}`",
        f"- Live IDP keys in candidate: **{len(candidate['players'])}**",
        f"- Actual PROD_MULT entries that would change: **{len(changes)}**",
        f"- Exact holds / unchanged candidate entries: **{len(candidate['players']) - len(changes)}**",
        f"- Candidate HTML parsed/evaluated successfully: **{len(preview_values)} PLAYER_DB rows**",
        "",
        "## Changed entries by position",
        "",
    ]
    for pos in ("LB", "DL", "DB"):
        lines.append(f"- {pos}: **{by_pos[pos]}**")
    lines += ["", "## Changed entries by source cohort", ""]
    for k,v in sorted(by_cohort.items()): lines.append(f"- `{k}`: **{v}**")
    lines += ["", "## Changed entries by status", ""]
    for k,v in sorted(by_status.items()): lines.append(f"- `{k}`: **{v}**")

    lines += ["", "## Known anchors", "", "| Player | Pos | Old | Candidate | Change |", "|---|---|---:|---:|---:|"]
    entries = {e['key']: e for e in patch_entries}
    for key in anchors:
        r = candidate['players'].get(key)
        if not r: continue
        lines.append(f"| {key} | {r['pos']} | {r['old_live_prod_mult']:.4f} | {r['candidate_prod_mult']:.4f} | {r['pct_change']:+.1f}% |")

    lines += ["", "## Largest raw PROD_MULT changes", "", "| Player | Pos | Old | New | Change | Cohort |", "|---|---|---:|---:|---:|---|"]
    for e in largest:
        lines.append(f"| {e['key']} | {e['pos']} | {e['old']:.4f} | {e['new']:.4f} | {e['pct_change']:+.1f}% | {e['v1_source_cohort']} |")

    lines += [
        "",
        "## Safety gates passed",
        "",
        "- Current `index.html` canonical PROD_MULT entries exactly match the immutable pre-V1 baseline before preview generation.",
        "- Only the `PROD_MULT_DATA` object is changed in the preview patch.",
        "- Node JavaScript syntax check passes on the temporary candidate HTML.",
        "- `snapshot_values.py` parses and evaluates the temporary candidate HTML successfully.",
        "- No git commit or push is performed by this script.",
        "",
        "## Production note",
        "",
        "The large explanatory comment immediately above `PROD_MULT_DATA` still describes the retired manual FantasyPros/Sleeper final-points blend. When the final V1 bake is approved, update that comment in the same reviewed production commit so the code documentation matches the new model.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="explicitly write the validated candidate values into index.html")
    args = parser.parse_args()

    candidate = build_candidate()
    text = INDEX_PATH.read_text(encoding="utf-8")
    _, _, block = extract_prod_block(text)
    current = parse_prod_values(block)
    baseline_doc = json.load(open(BASELINE_PATH, encoding="utf-8"))
    verify_true_live_baseline(current, baseline_doc["values"])

    candidate_text, changes = apply_values_to_text(text, candidate)
    # Ensure preview differs nowhere outside the PROD_MULT object.
    s1,e1,_ = extract_prod_block(text); s2,e2,_ = extract_prod_block(candidate_text)
    if text[:s1] != candidate_text[:s2] or text[e1:] != candidate_text[e2:]:
        raise RuntimeError("preview changed content outside PROD_MULT_DATA")

    preview_values = validate_preview(candidate_text, candidate)

    patch_entries=[]
    for key,old,new in changes:
        r=candidate['players'][key]
        patch_entries.append({
            'key':key,'pos':r['pos'],'old':old,'new':new,
            'pct_change':(new/old-1)*100 if old else None,
            'v1_source_cohort':r['v1_source_cohort'],
            'update_status':r['update_status'],
            'delta_raw_prod_mult':r.get('delta_raw_prod_mult'),
        })
    patch_doc={
        'method':candidate['method'],
        'changed_entry_count':len(patch_entries),
        'candidate_player_count':len(candidate['players']),
        'unchanged_candidate_count':len(candidate['players'])-len(patch_entries),
        'entries':patch_entries,
    }
    PATCH_JSON.write_text(json.dumps(patch_doc,indent=2)+'\n',encoding='utf-8')
    PATCH_REPORT.write_text(build_report(candidate,changes,patch_entries,preview_values),encoding='utf-8')

    diff=''.join(difflib.unified_diff(
        text.splitlines(keepends=True), candidate_text.splitlines(keepends=True),
        fromfile='a/index.html', tofile='b/index.html',
    ))
    PATCH_DIFF.write_text(diff,encoding='utf-8')

    if args.apply:
        INDEX_PATH.write_text(candidate_text,encoding='utf-8')
        print(f"APPLIED: wrote {len(changes)} PROD_MULT changes to {INDEX_PATH}")
    else:
        print(f"PREVIEW ONLY: {len(changes)} PROD_MULT entries would change; index.html untouched")
    print(f"Wrote {PATCH_JSON}")
    print(f"Wrote {PATCH_REPORT}")
    print(f"Wrote {PATCH_DIFF}")


if __name__ == '__main__':
    main()
