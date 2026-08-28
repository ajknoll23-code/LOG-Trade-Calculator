#!/usr/bin/env python3
"""Extract the baked PROD_MULT_DATA table from index.html into an auditable JSON snapshot.

Purpose: keep before/after production validation tied to what the web app
actually served, not to a generated lineage file that may have drifted.

Usage:
  python3 scripts/extract_prod_mult_snapshot.py
  python3 scripts/extract_prod_mult_snapshot.py --input index.html --output scripts/prod_mult_pre_v1_baseline.json
  python3 scripts/extract_prod_mult_snapshot.py --force
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_INPUT = os.path.join(REPO_ROOT, "index.html")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "prod_mult_pre_v1_baseline.json")

BLOCK_RE = re.compile(r"const\s+PROD_MULT_DATA\s*=\s*\{(.*?)\n\};", re.S)
ENTRY_RE = re.compile(r"'([^']+)'\s*:\s*(-?\d+(?:\.\d+)?)")


def extract(path):
    raw = open(path, "rb").read()
    text = raw.decode("utf-8")
    match = BLOCK_RE.search(text)
    if not match:
        raise RuntimeError("Could not find PROD_MULT_DATA in index.html")
    pairs = ENTRY_RE.findall(match.group(1))
    values = {}
    duplicates = []
    for key, value in pairs:
        if key in values:
            duplicates.append(key)
        values[key] = float(value)
    if duplicates:
        raise RuntimeError(f"Duplicate literal PROD_MULT_DATA keys found: {sorted(set(duplicates))}")
    return raw, values


def run_selftest():
    sample = "const PROD_MULT_DATA = {\n 'alpha':0.5,\n 'beta':1.25,\n};"
    m = BLOCK_RE.search(sample)
    assert m
    values = {k: float(v) for k, v in ENTRY_RE.findall(m.group(1))}
    assert values == {"alpha": 0.5, "beta": 1.25}
    print("extract_prod_mult_snapshot self-test passed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    if os.path.exists(args.output) and not args.force:
        print(f"ERROR: {args.output} already exists. Use --force only if intentionally replacing the baseline.")
        sys.exit(1)

    raw, values = extract(args.input)
    payload = {
        "snapshot_type": "baked_prod_mult_data",
        "source_file": os.path.relpath(args.input, REPO_ROOT),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "entry_count": len(values),
        "values": dict(sorted(values.items())),
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=False)
        f.write("\n")
    print(f"Captured {len(values)} PROD_MULT_DATA entries -> {args.output}")
    print(f"Source SHA256: {payload['source_sha256']}")


if __name__ == "__main__":
    main()
