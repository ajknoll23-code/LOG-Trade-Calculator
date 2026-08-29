"""
check_no_duplicate_prod_mult_keys.py -- regression guard.

WHY THIS EXISTS: PROD_MULT_DATA was found to contain 24 duplicate entries --
an abbreviated key (e.g. 'j greenard') and its full-name resolution (e.g.
'jonathan greenard') both present, with different values. The abbreviated
form is dead at runtime (productionMultiplier() always normalizes a real
player's full name), but it silently sat in the table as conflicting data
until this check was written. This script exists so that class of bug
cannot silently reappear -- e.g. if a future name/alias correction is added
to PROD_MULT_DATA without removing the old key first.

USAGE: python3 scripts/check_no_duplicate_prod_mult_keys.py
Run from anywhere -- paths are resolved relative to this script's own
location, not the current working directory. Lives in scripts/ alongside
ppg_pipeline.py (same folder -- ALIASES is loaded from there directly).
index.html lives one level up, at the repo root, and is located the same
way -- relative to this script, not to wherever it's invoked from.

Exits non-zero (and prints every offending pair) if any abbreviated key in
ppg_pipeline.py's ALIASES table AND its resolved full-name key are BOTH
present in PROD_MULT_DATA at the same time. Run this before merging any
change to PROD_MULT_DATA, or wire into CI.
"""

import re
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # scripts/ -> repo root, one level up


def load_prod_mult_keys(index_html_path):
    with open(index_html_path) as f:
        content = f.read()
    m = re.search(r'const PROD_MULT_DATA = \{(.*?)\n\};', content, re.S)
    if not m:
        raise RuntimeError("Could not find PROD_MULT_DATA in index.html")
    entries = re.findall(r"'([^']+)':\s*([\d.]+)", m.group(1))
    return {k: float(v) for k, v in entries}


def load_aliases(ppg_pipeline_path):
    with open(ppg_pipeline_path) as f:
        src = f.read()
    m = re.search(r"ALIASES\s*=\s*\{.*?\n\}", src, re.S)
    namespace = {}
    exec(m.group(0), namespace)
    return namespace['ALIASES']


def main():
    index_html = os.path.join(REPO_ROOT, "index.html")     # repo root
    ppg_pipeline = os.path.join(os.path.dirname(SCRIPT_DIR), "ppg_pipeline.py")  # same folder (scripts/)

    baked = load_prod_mult_keys(index_html)
    aliases = load_aliases(ppg_pipeline)

    offenders = [(abbrev, full) for abbrev, full in aliases.items()
                 if abbrev in baked and full in baked]

    if offenders:
        print(f"FAIL: {len(offenders)} duplicate/stale key pair(s) found in PROD_MULT_DATA:")
        for abbrev, full in offenders:
            print(f"  '{abbrev}' = {baked[abbrev]}   (dead duplicate of)   '{full}' = {baked[full]}")
        print()
        print("Delete the abbreviated-key entry (left column) -- the full-name entry")
        print("(right column) is the one productionMultiplier() actually reaches at runtime.")
        sys.exit(1)
    else:
        print(f"PASS: no duplicate/stale keys found. {len(baked)} entries checked "
              f"against {len(aliases)} known aliases.")
        sys.exit(0)


if __name__ == "__main__":
    main()
