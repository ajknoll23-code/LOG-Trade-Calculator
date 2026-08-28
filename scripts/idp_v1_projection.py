#!/usr/bin/env python3
"""Canonical projection math for the validated Trade Desk IDP V1 ensemble.

This module intentionally contains ONLY source-signal detection and the V1
category-level projection formula. It has no file I/O and no production bake
side effects, so every consumer (experiments, bake scripts, validation tools)
can use the exact same implementation.

Validated V1 assumptions:
  - Stage 1 total tackles: 50% FantasyPros / 50% Sleeper when both providers
    have tackle projections.
  - Stage 2 solo share: 40% FantasyPros / 60% Sleeper when both providers
    have tackle projections.
  - TFL and QB hits: Sleeper-only.
  - sacks / INT / PD / FF / FR / defensive TD: 50/50 when both providers have
    a meaningful V1 IDP projection; otherwise use the one active source.
  - no meaningful source signal: preserve the caller-provided old projection
    rather than inventing a zero.

Important distinction:
  source presence != source activity != tackle activity.

A provider can have a real row containing all zeroes (E.J. Speed's FantasyPros
row was the real regression case), and a provider could theoretically project
zero tackles but a non-zero sack/PD. Source activity therefore uses every V1
category, while tackle blending separately checks whether a positive tackle
projection exists.
"""

STAGE1_FP_WEIGHT = 0.50
STAGE2_FP_WEIGHT = 0.40

FP_SIGNAL_KEYS = (
    "def_tackle",
    "def_assist",
    "def_sack",
    "def_int",
    "def_pd",
    "def_ff",
    "def_fr",
    "def_td",
)

SLEEPER_SIGNAL_KEYS = (
    "idp_tkl_solo",
    "idp_tkl_ast",
    "idp_tkl_loss",
    "idp_qb_hit",
    "sack",
    "int",
    "idp_pass_def",
    "idp_ff",
    "idp_fum_rec",
    "idp_td",
)


def _positive(value):
    try:
        return float(value or 0) > 0
    except (TypeError, ValueError):
        return False


def has_meaningful_fp_signal(stats):
    """True only when FantasyPros has at least one non-zero V1 category."""
    return bool(stats) and any(_positive(stats.get(k)) for k in FP_SIGNAL_KEYS)


def has_meaningful_sleeper_signal(stats):
    """True only when Sleeper has at least one non-zero V1 category."""
    return bool(stats) and any(_positive(stats.get(k)) for k in SLEEPER_SIGNAL_KEYS)


def _value(stats, key):
    if not stats:
        return 0.0
    return float(stats.get(key, 0) or 0)


def _shared_category_value(fp_value, sleeper_value, fp_active, sleeper_active):
    if fp_active and sleeper_active:
        return 0.5 * fp_value + 0.5 * sleeper_value
    if fp_active:
        return fp_value
    if sleeper_active:
        return sleeper_value
    return 0.0


def compute_v1_projection(fp_stats, sleeper_stats, old_proj=None):
    """Return the complete V1 projected points plus audit metadata.

    ``old_proj`` is used only when neither provider has any meaningful V1
    signal. This preserves the already-established missing-data rule.
    """
    fp_active = has_meaningful_fp_signal(fp_stats)
    sleeper_active = has_meaningful_sleeper_signal(sleeper_stats)

    if not fp_active and not sleeper_active:
        return {
            "projection": old_proj,
            "source_cohort": "no_new_data",
            "fp_active": False,
            "sleeper_active": False,
            "fp_tackle_active": False,
            "sleeper_tackle_active": False,
            "tackle_points": None,
            "other_points": None,
        }

    fp_solo = _value(fp_stats, "def_tackle")
    fp_ast = _value(fp_stats, "def_assist")
    sleeper_solo = _value(sleeper_stats, "idp_tkl_solo")
    sleeper_ast = _value(sleeper_stats, "idp_tkl_ast")

    fp_total = fp_solo + fp_ast
    sleeper_total = sleeper_solo + sleeper_ast
    fp_tackle_active = fp_total > 0
    sleeper_tackle_active = sleeper_total > 0

    if fp_tackle_active and sleeper_tackle_active:
        consensus_total = STAGE1_FP_WEIGHT * fp_total + (1 - STAGE1_FP_WEIGHT) * sleeper_total
        fp_share = fp_solo / fp_total
        sleeper_share = sleeper_solo / sleeper_total
        consensus_share = STAGE2_FP_WEIGHT * fp_share + (1 - STAGE2_FP_WEIGHT) * sleeper_share
        consensus_solo = consensus_total * consensus_share
        consensus_ast = consensus_total - consensus_solo
        tackle_points = consensus_solo * 1.5 + consensus_ast * 0.75
    elif fp_tackle_active:
        tackle_points = fp_solo * 1.5 + fp_ast * 0.75
    elif sleeper_tackle_active:
        tackle_points = sleeper_solo * 1.5 + sleeper_ast * 0.75
    else:
        # A source can theoretically project a sack/PD while projecting zero
        # tackles. Do not divide by zero or pretend the source is absent.
        tackle_points = 0.0

    other_points = 0.0
    shared = (
        ("def_sack", "sack", 3.0),
        ("def_int", "int", 6.0),
        ("def_pd", "idp_pass_def", 3.0),
        ("def_ff", "idp_ff", 3.0),
        ("def_fr", "idp_fum_rec", 4.0),
        ("def_td", "idp_td", 6.0),
    )
    for fp_key, sleeper_key, points_per in shared:
        category = _shared_category_value(
            _value(fp_stats, fp_key),
            _value(sleeper_stats, sleeper_key),
            fp_active,
            sleeper_active,
        )
        other_points += category * points_per

    # Categories absent from FantasyPros are genuinely Sleeper-only in V1.
    if sleeper_active:
        other_points += _value(sleeper_stats, "idp_tkl_loss") * 2.0
        other_points += _value(sleeper_stats, "idp_qb_hit") * 2.0

    if fp_active and sleeper_active:
        cohort = "both"
    elif fp_active:
        cohort = "fp_only"
    else:
        cohort = "sleeper_only"

    return {
        "projection": tackle_points + other_points,
        "source_cohort": cohort,
        "fp_active": fp_active,
        "sleeper_active": sleeper_active,
        "fp_tackle_active": fp_tackle_active,
        "sleeper_tackle_active": sleeper_tackle_active,
        "tackle_points": tackle_points,
        "other_points": other_points,
    }


def run_selftest():
    # E.J. Speed: FP row present but all-zero; Sleeper is the one active source.
    fp_speed = {
        "def_sack": 0, "def_int": 0, "def_td": 0, "def_tackle": 0,
        "def_assist": 0, "def_ff": 0, "def_fr": 0, "def_pd": 0,
    }
    sleeper_speed = {
        "idp_tkl_solo": 33.45, "idp_tkl_ast": 31.58,
        "idp_tkl_loss": 3.9, "idp_qb_hit": 1.02, "sack": 1.02,
        "int": 0.0, "idp_pass_def": 2.89, "idp_ff": 0.0,
        "idp_fum_rec": 0.0, "idp_td": 0.0,
    }
    result = compute_v1_projection(fp_speed, sleeper_speed, old_proj=999.0)
    assert abs(result["projection"] - 95.43) < 0.1, result
    assert result["source_cohort"] == "sleeper_only"

    # Missing data keeps the old projection exactly.
    result = compute_v1_projection(None, None, old_proj=123.4)
    assert result["projection"] == 123.4
    assert result["source_cohort"] == "no_new_data"

    # Future-proof edge: FP can be active on sacks with zero tackles. Sleeper
    # has tackles. No divide-by-zero and FP's sack participates in consensus.
    fp_sack_only = {"def_tackle": 0, "def_assist": 0, "def_sack": 4.0}
    sleeper = {
        "idp_tkl_solo": 40, "idp_tkl_ast": 20, "sack": 2.0,
        "idp_tkl_loss": 0, "idp_qb_hit": 0, "idp_pass_def": 0,
        "int": 0, "idp_ff": 0, "idp_fum_rec": 0, "idp_td": 0,
    }
    result = compute_v1_projection(fp_sack_only, sleeper)
    expected_tackles = 40 * 1.5 + 20 * 0.75
    expected_sacks = ((4.0 + 2.0) / 2) * 3.0
    assert abs(result["projection"] - (expected_tackles + expected_sacks)) < 1e-9
    assert result["fp_active"] and not result["fp_tackle_active"]

    # Mirror edge: Sleeper can be active on PD only while FP supplies tackles.
    fp = {"def_tackle": 30, "def_assist": 10, "def_pd": 2.0}
    sleeper_pd_only = {
        "idp_tkl_solo": 0, "idp_tkl_ast": 0, "idp_pass_def": 4.0,
        "idp_tkl_loss": 0, "idp_qb_hit": 0, "sack": 0, "int": 0,
        "idp_ff": 0, "idp_fum_rec": 0, "idp_td": 0,
    }
    result = compute_v1_projection(fp, sleeper_pd_only)
    expected_tackles = 30 * 1.5 + 10 * 0.75
    expected_pd = ((2.0 + 4.0) / 2) * 3.0
    assert abs(result["projection"] - (expected_tackles + expected_pd)) < 1e-9
    assert result["sleeper_active"] and not result["sleeper_tackle_active"]

    print("idp_v1_projection self-test passed (4 cases).")


if __name__ == "__main__":
    run_selftest()
