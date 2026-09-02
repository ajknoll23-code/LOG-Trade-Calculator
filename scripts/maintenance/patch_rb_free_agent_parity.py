#!/usr/bin/env python3
# One-time integration patch for RB_CONTINUOUS_AGE_V1 free-agent parity.

from __future__ import annotations

import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNC = REPO_ROOT / "scripts" / "sync" / "sync_free_agent_valuation.py"
VALIDATOR = REPO_ROOT / "scripts" / "validation" / "validate_free_agent_valuation_parity.py"

MARKER = "RB_CONTINUOUS_AGE_FREE_AGENT_PARITY_V1"


def die(msg: str) -> None:
    raise RuntimeError(msg)


def replace_exact(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        die(f"{label}: expected {expected} matches, found {count}")
    return text.replace(old, new)


def patch_sync(text: str) -> str:
    if MARKER in text:
        return text

    old_render = """    _, _, canonical_db = _extract_const_object(index_text, "PLAYER_DB")
    s, e, _ = _extract_const_object(out, "PLAYER_DB")
    out = _replace_region(out, s, e, canonical_db)

    _, _, canonical_core = _extract_core(index_text)
"""
    new_render = f"""    _, _, canonical_db = _extract_const_object(index_text, "PLAYER_DB")
    s, e, _ = _extract_const_object(out, "PLAYER_DB")
    out = _replace_region(out, s, e, canonical_db)

    # {MARKER}
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
            + "\\n\\n"
            + canonical_rb_birth_dates
            + out[db_end:]
        )
    else:
        out = _replace_region(out, s, e, canonical_rb_birth_dates)

    _, _, canonical_core = _extract_core(index_text)
"""
    text = replace_exact(
        text, old_render, new_render, 1, "free-agent sync DOB render integration"
    )

    old_parity = """        "player_db": _extract_const_object(index_text, "PLAYER_DB")[2]
        == _extract_const_object(board_text, "PLAYER_DB")[2],
        "aliases": _extract_alias_region(index_text)[2] == _extract_alias_region(board_text)[2],
"""
    new_parity = """        "player_db": _extract_const_object(index_text, "PLAYER_DB")[2]
        == _extract_const_object(board_text, "PLAYER_DB")[2],
        "rb_birth_date_data": _extract_const_object(
            index_text, "RB_BIRTH_DATE_DATA"
        )[2]
        == _extract_const_object(board_text, "RB_BIRTH_DATE_DATA")[2],
        "aliases": _extract_alias_region(index_text)[2] == _extract_alias_region(board_text)[2],
"""
    text = replace_exact(
        text, old_parity, new_parity, 1, "free-agent sync DOB parity region"
    )
    return text


def patch_validator(text: str) -> str:
    if MARKER in text:
        return text

    old_extract = """    player_db = sync_free_agent_valuation._extract_const_object(board_text, "PLAYER_DB")[2]
    normalize = sync_free_agent_valuation._extract_function(board_text, "normalizeName")[2]
"""
    new_extract = f"""    player_db = sync_free_agent_valuation._extract_const_object(board_text, "PLAYER_DB")[2]
    rb_birth_dates = sync_free_agent_valuation._extract_const_object(
        board_text, "RB_BIRTH_DATE_DATA"
    )[2]
    normalize = sync_free_agent_valuation._extract_function(board_text, "normalizeName")[2]
    # {MARKER}
"""
    text = replace_exact(
        text, old_extract, new_extract, 2, "validator DOB constant extraction"
    )

    old_join = """            core,
            player_db,
            normalize,
"""
    new_join = """            core,
            player_db,
            rb_birth_dates,
            normalize,
"""
    text = replace_exact(
        text, old_join, new_join, 2, "validator DOB constant Node injection"
    )

    text = replace_exact(
        text,
        "  const am = ageMultiplier(info.pos, info.age, info.role, rm, rawRm);",
        "  const am = effectiveAgeMultiplier(info.pos, info.age, info.role, key, rm, rawRm);",
        1,
        "validator canonical effective age multiplier",
    )

    text = replace_exact(
        text,
        "  const am = ageMultiplier(pos, age, role, rm, rawRm);",
        "  const am = effectiveAgeMultiplier(pos, age, role, key, rm, rawRm);",
        1,
        "validator synthetic effective age multiplier",
    )

    old_py = """        am = snapshot_values.age_multiplier(pos, age, role, rm, raw, cfg)
"""
    new_py = """        am = snapshot_values.effective_age_multiplier(
            pos, age, role, key, rm, raw, cfg
        )
"""
    text = replace_exact(
        text,
        old_py,
        new_py,
        1,
        "validator Python effective age multiplier",
    )
    return text


def validate_sources(sync_text: str, validator_text: str) -> None:
    for token in (
        MARKER,
        '"RB_BIRTH_DATE_DATA"',
        '"rb_birth_date_data"',
        "canonical_rb_birth_dates",
    ):
        if token not in sync_text:
            die(f"patched sync missing token: {token}")

    for token in (
        MARKER,
        "rb_birth_dates =",
        "effectiveAgeMultiplier(",
        "snapshot_values.effective_age_multiplier(",
    ):
        if token not in validator_text:
            die(f"patched validator missing token: {token}")

    compile(sync_text, str(SYNC), "exec")
    compile(validator_text, str(VALIDATOR), "exec")


def dry_run() -> tuple[str, str]:
    sync_text = SYNC.read_text(encoding="utf-8")
    validator_text = VALIDATOR.read_text(encoding="utf-8")
    patched_sync = patch_sync(sync_text)
    patched_validator = patch_validator(validator_text)
    validate_sources(patched_sync, patched_validator)
    return patched_sync, patched_validator


def selftest() -> None:
    dry_run()
    print("patch_rb_free_agent_parity self-test passed.")


def apply() -> None:
    sync_text = SYNC.read_text(encoding="utf-8")
    validator_text = VALIDATOR.read_text(encoding="utf-8")
    patched_sync, patched_validator = dry_run()

    if patched_sync == sync_text and patched_validator == validator_text:
        print("RB free-agent parity integration already applied.")
        return

    SYNC.write_text(patched_sync, encoding="utf-8")
    VALIDATOR.write_text(patched_validator, encoding="utf-8")
    print("Applied RB continuous-age free-agent sync/parity integration.")


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--selftest", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        selftest()
    else:
        apply()


if __name__ == "__main__":
    main()
