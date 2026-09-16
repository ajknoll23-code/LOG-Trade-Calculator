#!/usr/bin/env python3
"""Apply/check the approved IDP Position Lineage V1 PROD_MULT release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
INDEX = ROOT / "index.html"
RELEASE = (
    ROOT / "model" / "releases" / "idp-position-lineage-v1" / "release.json"
)

sys.path.insert(0, str(ROOT / "scripts" / "validation"))
import snapshot_values

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def locate_prod_object(text):
    marker = "PROD_MULT_DATA"
    idx = text.find(marker)
    if idx < 0:
        raise RuntimeError("PROD_MULT_DATA marker not found")
    brace = text.find("{", idx)
    if brace < 0:
        raise RuntimeError("PROD_MULT_DATA opening brace not found")

    depth = 0
    quote = None
    escape = False
    for i in range(brace, len(text)):
        ch = text[i]
        if quote is not None:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = None
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return brace, i + 1
    raise RuntimeError("Unclosed PROD_MULT_DATA object")

def parse_prod(text):
    cfg = snapshot_values.load_from_html(INDEX)
    return dict(cfg["prod_mult"])

def render(text, release):
    start, end = locate_prod_object(text)
    body = text[start:end]

    before_cfg = snapshot_values.load_from_html(INDEX)
    before_prod = dict(before_cfg["prod_mult"])

    for row in release["candidate_overrides"]:
        key = row["key"]
        expected_old = float(row["deployed_raw_prod_mult"])
        candidate = float(row["candidate_raw_prod_mult"])

        actual_old = before_prod.get(key)
        if actual_old is None or abs(actual_old - expected_old) > 1e-9:
            raise RuntimeError(
                f"Current deployed raw mismatch for {key}: "
                f"{actual_old} != {expected_old}"
            )

        pattern = re.compile(
            r"('" + re.escape(key) + r"'\s*:\s*)(-?(?:\d+(?:\.\d*)?|\.\d+))"
        )
        matches = list(pattern.finditer(body))
        if len(matches) != 1:
            raise RuntimeError(
                f"Expected exactly one PROD_MULT_DATA literal for {key}; "
                f"found {len(matches)}"
            )

        body = pattern.sub(
            lambda m: m.group(1) + format(candidate, ".4f").rstrip("0").rstrip("."),
            body,
            count=1,
        )

    return text[:start] + body + text[end:]

def validate_exact(before_text, after_text, release):
    tmp_before = INDEX.read_text(encoding="utf-8")
    try:
        INDEX.write_text(before_text, encoding="utf-8")
        before = snapshot_values.load_from_html(INDEX)["prod_mult"]
        INDEX.write_text(after_text, encoding="utf-8")
        after = snapshot_values.load_from_html(INDEX)["prod_mult"]
    finally:
        INDEX.write_text(tmp_before, encoding="utf-8")

    expected_keys = {
        row["key"] for row in release["candidate_overrides"]
    }
    actual_changed = {
        key
        for key in before
        if float(before[key]) != float(after[key])
    }

    if actual_changed != expected_keys:
        raise RuntimeError(
            f"Changed PROD_MULT keys mismatch. "
            f"Expected {sorted(expected_keys)}; actual {sorted(actual_changed)}"
        )

    for row in release["held_rows"]:
        key = row["key"]
        if float(before[key]) != float(after[key]):
            raise RuntimeError(f"Held row changed: {key}")

    if set(before) != set(after):
        raise RuntimeError("PROD_MULT_DATA key set changed")

def main():
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    group.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sample = "const PROD_MULT_DATA = {'alpha':0.5,'beta':0.7};"
        release = {
            "candidate_overrides": [{
                "key": "alpha",
                "deployed_raw_prod_mult": 0.5,
                "candidate_raw_prod_mult": 0.8
            }],
            "held_rows": []
        }
        # Pure substitution smoke test.
        start, end = locate_prod_object(sample)
        assert start < end
        pat = re.compile(r"('alpha'\s*:\s*)(-?(?:\d+(?:\.\d*)?|\.\d+))")
        changed = sample[:start] + pat.sub(r"\g<1>0.8", sample[start:end], count=1) + sample[end:]
        assert "'alpha':0.8" in changed
        print("IDP Position Lineage V1 applicator self-test PASS")
        return

    release = read_json(RELEASE)
    before = INDEX.read_text(encoding="utf-8")

    if args.check:
        cfg = snapshot_values.load_from_html(INDEX)
        prod = cfg["prod_mult"]
        for row in release["candidate_overrides"]:
            actual = float(prod[row["key"]])
            expected = float(row["candidate_raw_prod_mult"])
            if abs(actual - expected) > 1e-9:
                raise SystemExit(
                    f"Stale deployment for {row['key']}: "
                    f"{actual} != {expected}"
                )
        print("PASS: IDP Position Lineage V1 release is deployed")
        return

    after = render(before, release)
    validate_exact(before, after, release)
    INDEX.write_text(after, encoding="utf-8")
    print(
        "Wrote index.html with",
        len(release["candidate_overrides"]),
        "approved Position Lineage V1 PROD_MULT changes.",
    )

if __name__ == "__main__":
    main()
