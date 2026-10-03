#!/usr/bin/env python3
"""
Player Role V2 B41C2 exact-key scorer.

Frozen before B41C2 recalculates the already-seen 2026 Weeks 1-3.

Design:
- frozen Sleeper league scoring_settings are the source of truth;
- exact raw-stat keys are scored exactly once;
- no generic<->IDP fallback substitution;
- kicker range scoring is therefore naturally included;
- derived bonuses are used only when Sleeper did not expose the
  exact bonus key in the raw player stat object.
"""

from __future__ import annotations
import math

SCORER_VERSION = "player-role-v2-b41c2-v1"

DERIVED_BONUS_KEYS = {
    "bonus_pass_yd_300",
    "bonus_pass_yd_400",
    "bonus_rush_yd_100",
    "bonus_rush_yd_200",
    "bonus_rec_yd_100",
    "bonus_rec_yd_200",
    "bonus_sack_2p",
    "bonus_tkl_10p",
    "idp_pass_def_3p",
}

def num(value):
    try:
        x = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return x if math.isfinite(x) else 0.0

def direct_score(raw, settings):
    pts = 0.0
    scored_keys = set()

    for key, weight in settings.items():
        if key in DERIVED_BONUS_KEYS:
            continue
        if key not in raw:
            continue
        pts += num(raw.get(key)) * num(weight)
        scored_keys.add(key)

    return pts, scored_keys

def _score_exact_bonus_if_present(raw, settings, key):
    if key in raw:
        return num(raw.get(key)) * num(settings.get(key)), True
    return 0.0, False

def _yardage_bonus(raw, settings, base_key, low_key, high_key, low_cut, high_cut):
    pts = 0.0

    # Prefer provider-supplied exact bonus counters whenever present.
    high_pts, high_present = _score_exact_bonus_if_present(
        raw, settings, high_key
    )
    low_pts, low_present = _score_exact_bonus_if_present(
        raw, settings, low_key
    )

    if high_present or low_present:
        # Exact provider counters govern; do not derive a second copy.
        return high_pts + low_pts

    yards = num(raw.get(base_key))
    if yards >= high_cut:
        return num(settings.get(high_key))
    if yards >= low_cut:
        return num(settings.get(low_key))
    return 0.0

def _threshold_bonus(raw, settings, stat_key, bonus_key, threshold):
    exact, present = _score_exact_bonus_if_present(
        raw, settings, bonus_key
    )
    if present:
        return exact
    return num(settings.get(bonus_key)) if num(raw.get(stat_key)) >= threshold else 0.0

def score_week(raw, settings):
    pts, _ = direct_score(raw, settings)

    pts += _yardage_bonus(
        raw, settings,
        "pass_yd", "bonus_pass_yd_300", "bonus_pass_yd_400",
        300, 400,
    )
    pts += _yardage_bonus(
        raw, settings,
        "rush_yd", "bonus_rush_yd_100", "bonus_rush_yd_200",
        100, 200,
    )
    pts += _yardage_bonus(
        raw, settings,
        "rec_yd", "bonus_rec_yd_100", "bonus_rec_yd_200",
        100, 200,
    )

    pts += _threshold_bonus(
        raw, settings, "idp_sack", "bonus_sack_2p", 2
    )

    # Sleeper's 10-tackle bonus is based on total credited tackles.
    exact, present = _score_exact_bonus_if_present(
        raw, settings, "bonus_tkl_10p"
    )
    if present:
        pts += exact
    else:
        total_tackles = (
            num(raw.get("idp_tkl_solo"))
            + num(raw.get("idp_tkl_ast"))
        )
        if total_tackles >= 10:
            pts += num(settings.get("bonus_tkl_10p"))

    pts += _threshold_bonus(
        raw, settings, "idp_pass_def", "idp_pass_def_3p", 3
    )

    return round(pts, 6)

def selftest():
    settings = {
        "pass_yd": 0.04,
        "bonus_pass_yd_300": 2.0,
        "bonus_pass_yd_400": 3.0,
        "fgm_0_19": 3.0,
        "fgm_40_49": 4.0,
        "fgm_50p": 5.0,
        "xpm": 1.0,
        "xpmiss": -1.0,
        "idp_blk_kick": 6.0,
        "blk_kick": 2.0,
        "idp_safe": 3.0,
        "safe": 2.0,
        "idp_tkl_solo": 1.5,
        "idp_tkl_ast": 0.75,
        "bonus_tkl_10p": 2.0,
    }

    assert score_week({"fgm_50p": 2, "xpm": 3}, settings) == 13.0
    assert score_week({"fgm_40_49": 1, "xpmiss": 1}, settings) == 3.0
    assert score_week({"idp_blk_kick": 1}, settings) == 6.0
    assert score_week({"blk_kick": 1}, settings) == 2.0
    assert score_week({"idp_safe": 1}, settings) == 3.0
    assert score_week({"safe": 1}, settings) == 2.0
    assert score_week({"pass_yd": 300}, settings) == 14.0
    assert score_week({"pass_yd": 400}, settings) == 19.0
    assert score_week({
        "idp_tkl_solo": 8,
        "idp_tkl_ast": 2,
    }, settings) == 15.5

    print("SELFTEST PASS")

if __name__ == "__main__":
    selftest()
