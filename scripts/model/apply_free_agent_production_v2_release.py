#!/usr/bin/env python3
"""Apply/check the approved Free-Agent Production V2 release.

The historical FA_PROD_MULT_DATA object is intentionally preserved.
A generated release block immediately after it overrides `prod` for
exactly the approved V2 candidate cohort. Held/unresolved rows and
kickers remain on the historical table.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
BOARD = ROOT / "free-agent-board.html"
RELEASE = ROOT / "model" / "releases" / "free-agent-production-v2" / "release.json"

START = "/* FREE_AGENT_PRODUCTION_V2_RELEASE_START */"
END = "/* FREE_AGENT_PRODUCTION_V2_RELEASE_END */"

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def load_sync():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from sync import sync_free_agent_valuation
    return sync_free_agent_valuation

def eval_base_table(board_text, sync_mod):
    const_source = sync_mod._extract_const_object(
        board_text, "FA_PROD_MULT_DATA"
    )[2]
    js = const_source + "\nprocess.stdout.write(JSON.stringify(FA_PROD_MULT_DATA));\n"
    proc = subprocess.run(
        ["node", "-e", js],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())
    return json.loads(proc.stdout)

def exact_entry(table, key, pos):
    raw = table.get(key)
    vals = raw if isinstance(raw, list) else [raw]
    matches = [
        v for v in vals
        if isinstance(v, dict) and str(v.get("pos") or "") == pos
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one FA table entry for {key!r} {pos}; "
            f"found {len(matches)}"
        )
    return matches[0]

def validate_release_against_base(board_text, release, sync_mod):
    table = eval_base_table(board_text, sync_mod)
    seen = set()
    for group_name in ("candidate_overrides", "held_active_legacy"):
        for row in release[group_name]:
            ident = (row["key"], row["pos"], row["sleeper_id"])
            if ident in seen:
                raise RuntimeError(f"Duplicate release identity: {ident}")
            seen.add(ident)
            entry = exact_entry(table, row["key"], row["pos"])
            actual = float(entry["prod"])
            expected = float(row["deployed_prod"])
            if abs(actual - expected) > 1e-12:
                raise RuntimeError(
                    f"Historical FA base drift for {ident}: "
                    f"{actual} != {expected}"
                )
    if len(release["candidate_overrides"]) != 333:
        raise RuntimeError("Release candidate count is not 333")
    if len(release["held_active_legacy"]) != 31:
        raise RuntimeError("Release held count is not 31")

def release_block(release):
    rows = [
        {
            "key": r["key"],
            "pos": r["pos"],
            "prod": float(r["candidate_prod"]),
            "sleeper_id": r["sleeper_id"],
        }
        for r in release["candidate_overrides"]
    ]
    payload = json.dumps(rows, separators=(",", ":"))
    return (
        START + "\n"
        "const FA_PROD_MULT_V2_RELEASE = " + payload + ";\n"
        "for (const __v2 of FA_PROD_MULT_V2_RELEASE) {\n"
        "  const __raw = FA_PROD_MULT_DATA[__v2.key];\n"
        "  const __vals = Array.isArray(__raw) ? __raw : [__raw];\n"
        "  let __matched = 0;\n"
        "  for (const __entry of __vals) {\n"
        "    if (__entry && __entry.pos === __v2.pos) {\n"
        "      __entry.prod = __v2.prod;\n"
        "      __matched += 1;\n"
        "    }\n"
        "  }\n"
        "  if (__matched !== 1) {\n"
        "    throw new Error('FA Production V2 release match failure for ' + "
        "__v2.sleeper_id + ' ' + __v2.key + ' ' + __v2.pos + ': ' + __matched);\n"
        "  }\n"
        "}\n"
        + END
    )

def render(board_text, release, sync_mod):
    validate_release_against_base(board_text, release, sync_mod)
    block = release_block(release)
    if START in board_text or END in board_text:
        if START not in board_text or END not in board_text:
            raise RuntimeError("Partial FA Production V2 release markers found")
        s = board_text.index(START)
        e = board_text.index(END, s) + len(END)
        return board_text[:s] + block + board_text[e:]

    _, const_end, _ = sync_mod._extract_const_object(
        board_text, "FA_PROD_MULT_DATA"
    )
    return board_text[:const_end] + "\n\n" + block + board_text[const_end:]

def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    sync_mod = load_sync()

    if args.selftest:
        sample = "const FA_PROD_MULT_DATA = {'x':{pos:'WR',prod:0.15}};\n"
        release = {
            "candidate_overrides": [{
                "key": "x",
                "pos": "WR",
                "sleeper_id": "1",
                "deployed_prod": 0.15,
                "candidate_prod": 0.25,
            }],
            "held_active_legacy": [],
        }
        # Test block construction separately; production count guards
        # intentionally require the real 333/31 release.
        block = release_block(release)
        assert START in block and END in block
        assert '"prod":0.25' in block
        print("Free-Agent Production V2 release applicator self-test PASS")
        return

    board = BOARD.read_text(encoding="utf-8")
    release = read_json(RELEASE)
    expected = render(board, release, sync_mod)

    if args.check:
        if START not in board:
            raise SystemExit("FA Production V2 release block is absent")
        # render() replaces an existing block deterministically.
        if expected != board:
            raise SystemExit("FA Production V2 release block is stale")
        print("PASS: Free-Agent Production V2 release block is current")
        return

    BOARD.write_text(expected, encoding="utf-8")
    print("Wrote", BOARD, "with approved Free-Agent Production V2 release")

if __name__ == "__main__":
    main()
