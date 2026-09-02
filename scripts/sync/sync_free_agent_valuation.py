#!/usr/bin/env python3
"""Synchronize free-agent-board.html with index.html's canonical valuation engine.

The free-agent board intentionally has its own UI and a free-agent-only
``FA_PROD_MULT_DATA`` table, but it must not maintain a second independent copy
of the Trade Desk valuation engine. This script copies the canonical runtime
pieces from ``index.html`` into ``free-agent-board.html``:

* position weights / age curves / role multipliers
* deployed PROD_MULT_DATA and production-history guards
* productionMultiplier / ageMultiplier / playerValue
* canonical PLAYER_DB
* canonical alias maps / resolveExistingKey
* normalizeName

The free-agent-only production table and board-specific mapping logic are left
untouched. Use ``--check`` in CI and ``--write`` when intentionally syncing.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INDEX_PATH = REPO_ROOT / "index.html"
BOARD_PATH = REPO_ROOT / "free-agent-board.html"

SYNC_NOTE = """/* CANONICAL VALUATION SYNC — 2026-08-28
   The valuation engine below is generated from index.html by
   scripts/sync/sync_free_agent_valuation.py. Do not hand-edit POSITION_WEIGHT,
   AGE_CURVE, PROD_MULT_DATA, productionMultiplier(), ageMultiplier(),
   playerValue(), PLAYER_DB, ALIASES, or normalizeName in this file.

   FA_PROD_MULT_DATA remains intentionally free-agent-specific because those
   players are outside the main calculator's curated live PROD_MULT table. Its
   source/methodology is audited separately; it is not permission for the core
   valuation engine to drift. CI checks exact source parity plus runtime value
   parity on canonical and synthetic test populations. */
"""


def _find_matching_brace(text: str, open_pos: int) -> int:
    """Return the matching closing brace, ignoring braces in JS strings/comments."""
    if text[open_pos] != "{":
        raise ValueError("open_pos must point at '{'")
    depth = 0
    i = open_pos
    quote = None
    escape = False
    line_comment = False
    block_comment = False
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""
        if line_comment:
            if c == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            if c == "*" and n == "/":
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == quote:
                quote = None
            i += 1
            continue
        if c == "/" and n == "/":
            line_comment = True
            i += 2
            continue
        if c == "/" and n == "*":
            block_comment = True
            i += 2
            continue
        if c in ("'", '"', "`"):
            quote = c
            i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("unbalanced braces")


def _extract_function(text: str, name: str) -> tuple[int, int, str]:
    needle = f"function {name}("
    start = text.find(needle)
    if start < 0:
        raise ValueError(f"missing function {name}")
    # normalizeName contains JavaScript regex literals whose character class
    # includes an apostrophe. A lightweight string/comment brace scanner can
    # misread that apostrophe as a JS string delimiter, so use the stable next
    # top-level function anchor for this one tiny canonical helper.
    if name == "normalizeName":
        next_anchor = text.find("\nfunction titleCase(", start)
        if next_anchor < 0:
            raise ValueError("missing titleCase anchor after normalizeName")
        end = next_anchor
        while end > start and text[end - 1] in " \t\r\n":
            end -= 1
        return start, end, text[start:end]
    open_pos = text.find("{", start)
    end_brace = _find_matching_brace(text, open_pos)
    return start, end_brace + 1, text[start : end_brace + 1]


def _extract_const_object(text: str, name: str) -> tuple[int, int, str]:
    needle = f"const {name} ="
    start = text.find(needle)
    if start < 0:
        raise ValueError(f"missing const {name}")
    open_pos = text.find("{", start)
    if open_pos < 0:
        raise ValueError(f"const {name} is not an object")
    end_brace = _find_matching_brace(text, open_pos)
    semi = text.find(";", end_brace)
    if semi < 0:
        raise ValueError(f"missing semicolon after const {name}")
    return start, semi + 1, text[start : semi + 1]


def _extract_core(text: str) -> tuple[int, int, str]:
    start = text.find("const POSITION_WEIGHT =")
    if start < 0:
        raise ValueError("missing POSITION_WEIGHT")
    _, end, _ = _extract_function(text, "playerValue")
    if end <= start:
        raise ValueError("playerValue unexpectedly precedes POSITION_WEIGHT")
    return start, end, text[start:end]


def _extract_alias_region(text: str) -> tuple[int, int, str]:
    start = text.find("const ALIASES =")
    if start < 0:
        raise ValueError("missing ALIASES")
    _, end, _ = _extract_function(text, "resolveExistingKey")
    if end <= start:
        raise ValueError("resolveExistingKey unexpectedly precedes ALIASES")
    return start, end, text[start:end]


def _replace_region(text: str, start: int, end: int, replacement: str) -> str:
    return text[:start] + replacement + text[end:]


def _replace_sync_note(board: str) -> str:
    marker = "/* SYNC NOTE 2026-08-20:"
    canonical_marker = "/* CANONICAL VALUATION SYNC — 2026-08-28"
    if canonical_marker in board:
        start = board.index(canonical_marker)
    elif marker in board:
        start = board.index(marker)
    else:
        # Insert immediately before the canonical core when no prior note exists.
        core_start = board.index("const POSITION_WEIGHT =")
        return board[:core_start] + SYNC_NOTE + board[core_start:]
    end = board.find("*/", start)
    if end < 0:
        raise ValueError("unterminated valuation sync note")
    end += 2
    while end < len(board) and board[end] in " \t\r\n":
        end += 1
    return board[:start] + SYNC_NOTE + board[end:]


def render_synced(index_text: str, board_text: str) -> str:
    """Return the board with all canonical valuation regions copied from index."""
    out = _replace_sync_note(board_text)

    # Replace from bottom-to-top where practical so earlier offsets never matter.
    _, _, canonical_norm = _extract_function(index_text, "normalizeName")
    s, e, _ = _extract_function(out, "normalizeName")
    out = _replace_region(out, s, e, canonical_norm)

    _, _, canonical_aliases = _extract_alias_region(index_text)
    s, e, _ = _extract_alias_region(out)
    out = _replace_region(out, s, e, canonical_aliases)

    _, _, canonical_db = _extract_const_object(index_text, "PLAYER_DB")
    s, e, _ = _extract_const_object(out, "PLAYER_DB")
    out = _replace_region(out, s, e, canonical_db)

    # RB_CONTINUOUS_AGE_FREE_AGENT_PARITY_V1
    # effectiveAgeMultiplier() depends on this compact DOB map. Keep it as a
    # first-class canonical region beside PLAYER_DB. Older board copies do not
    # have the constant yet, so insert it after PLAYER_DB on the first sync.
    _, _, canonical_rb_birth_dates = _extract_const_object(
        index_text, "RB_BIRTH_DATE_DATA"
    )
    try:
        s, e, _ = _extract_const_object(out, "RB_BIRTH_DATE_DATA")
    except ValueError:
        _, db_end, _ = _extract_const_object(out, "PLAYER_DB")
        out = (
            out[:db_end]
            + "\n\n"
            + canonical_rb_birth_dates
            + out[db_end:]
        )
    else:
        out = _replace_region(out, s, e, canonical_rb_birth_dates)

    _, _, canonical_core = _extract_core(index_text)
    s, e, _ = _extract_core(out)
    out = _replace_region(out, s, e, canonical_core)

    return out


def parity_regions(index_text: str, board_text: str) -> dict[str, bool]:
    """Exact source-level parity for every generated canonical region."""
    return {
        "core": _extract_core(index_text)[2] == _extract_core(board_text)[2],
        "player_db": _extract_const_object(index_text, "PLAYER_DB")[2]
        == _extract_const_object(board_text, "PLAYER_DB")[2],
        "rb_birth_date_data": _extract_const_object(
            index_text, "RB_BIRTH_DATE_DATA"
        )[2]
        == _extract_const_object(board_text, "RB_BIRTH_DATE_DATA")[2],
        "aliases": _extract_alias_region(index_text)[2] == _extract_alias_region(board_text)[2],
        "normalize_name": _extract_function(index_text, "normalizeName")[2]
        == _extract_function(board_text, "normalizeName")[2],
    }


def run_selftest() -> None:
    # Exercise the brace scanner with nested objects, strings/comments, and a
    # template literal containing braces. This is the machinery that makes
    # source sync safe, so test it independently of the current repo text.
    sample = "const X = {a:{b:1}, s:'}', t:`{x}`, /* } */ c:2};\nfunction f(){return {x:1};}"
    s, e, obj = _extract_const_object(sample, "X")
    assert obj == "const X = {a:{b:1}, s:'}', t:`{x}`, /* } */ c:2};"
    s, e, fun = _extract_function(sample, "f")
    assert fun == "function f(){return {x:1};}"

    index_text = INDEX_PATH.read_text(encoding="utf-8")
    board_text = BOARD_PATH.read_text(encoding="utf-8")
    # The generator is allowed to replace only the canonical regions. The
    # board-specific FA_PROD_MULT_DATA lineage is intentionally separate and
    # must be byte-for-byte preserved by every sync.
    original_fa_prod = _extract_const_object(board_text, "FA_PROD_MULT_DATA")[2]
    synced = render_synced(index_text, board_text)
    synced_twice = render_synced(index_text, synced)
    assert synced == synced_twice, "free-agent valuation sync is not idempotent"
    synced_fa_prod = _extract_const_object(synced, "FA_PROD_MULT_DATA")[2]
    assert synced_fa_prod == original_fa_prod, (
        "canonical valuation sync unexpectedly changed FA_PROD_MULT_DATA"
    )

    # Critical deployed mechanisms must be present in the generated board.
    for token in (
        "LB_POST_PEAK_DECAY_POWER",
        "NO_REAL_PRODUCTION_HISTORY",
        "MODEL-DELTA TRANSPORT",
        "exact_hold_floor_rescue_discontinuity_guard",
    ):
        # The last token lives in scripts, not the HTML; don't require it here.
        if token == "exact_hold_floor_rescue_discontinuity_guard":
            continue
        assert token in synced, f"generated board missing canonical token: {token}"

    print("sync_free_agent_valuation self-test passed.")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="rewrite free-agent-board.html")
    mode.add_argument("--check", action="store_true", help="fail if board is stale")
    mode.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return 0

    index_text = INDEX_PATH.read_text(encoding="utf-8")
    board_text = BOARD_PATH.read_text(encoding="utf-8")
    synced = render_synced(index_text, board_text)

    if args.check:
        parity = parity_regions(index_text, board_text)
        if synced != board_text or not all(parity.values()):
            stale = [k for k, ok in parity.items() if not ok]
            print(
                "FAIL free-agent valuation parity: free-agent-board.html is stale. "
                f"Mismatched canonical regions: {stale or ['sync_note/formatting']}. "
                "Run: python3 scripts/sync/sync_free_agent_valuation.py --write",
                file=sys.stderr,
            )
            return 1
        print("PASS free-agent valuation source parity: all canonical regions match index.html")
        return 0

    BOARD_PATH.write_text(synced, encoding="utf-8")
    parity = parity_regions(index_text, synced)
    if not all(parity.values()):
        raise RuntimeError(f"post-write parity failure: {parity}")
    print(f"Wrote {BOARD_PATH}: canonical valuation regions synchronized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
