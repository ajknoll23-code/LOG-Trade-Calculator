#!/usr/bin/env python3
"""
Player Role V2 target scorer.

Frozen before B41C reads 2026 Sleeper matchup points.
"""

from __future__ import annotations
import math

SCORER_VERSION = "player-role-v2-b41c-v1"

def n(stats, key):
    value = stats.get(key, 0)
    try:
        x = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return x if math.isfinite(x) else 0.0

def score_week(stats):
    pts = 0.0

    pass_yd = n(stats, "pass_yd")
    pts += pass_yd * 0.04
    pts += n(stats, "pass_td") * 4.0
    pts += n(stats, "pass_2pt") * 2.0
    pts += n(stats, "pass_int") * -2.0
    if pass_yd >= 400:
        pts += 3.0
    elif pass_yd >= 300:
        pts += 2.0

    rush_yd = n(stats, "rush_yd")
    pts += n(stats, "rush_att") * 0.2
    pts += rush_yd * 0.1
    pts += n(stats, "rush_td") * 6.0
    pts += n(stats, "rush_2pt") * 2.0
    if rush_yd >= 200:
        pts += 3.0
    elif rush_yd >= 100:
        pts += 2.0

    rec_yd = n(stats, "rec_yd")
    pts += n(stats, "rec") * 0.5
    pts += rec_yd * 0.1
    pts += n(stats, "rec_td") * 6.0
    pts += n(stats, "rec_2pt") * 2.0
    if rec_yd >= 200:
        pts += 3.0
    elif rec_yd >= 100:
        pts += 2.0

    pts += n(stats, "fum_lost") * -2.0
    pts += n(stats, "fum_rec_td") * 6.0

    solo = n(stats, "idp_tkl_solo")
    ast = n(stats, "idp_tkl_ast")
    pts += solo * 1.5
    pts += ast * 0.75
    pts += n(stats, "idp_tkl_loss") * 2.0

    sacks = n(stats, "idp_sack")
    if sacks == 0:
        sacks = n(stats, "sack")
    pts += sacks * 3.0
    pts += n(stats, "idp_qb_hit") * 2.0

    ints = n(stats, "idp_int")
    if ints == 0:
        ints = n(stats, "int")
    pts += ints * 6.0
    pts += n(stats, "idp_fum_rec") * 4.0
    pts += n(stats, "idp_ff") * 3.0
    pts += n(stats, "idp_safety") * 3.0
    pts += n(stats, "blk_kick") * 6.0
    pts += n(stats, "idp_td") * 6.0

    pd = n(stats, "idp_pass_def")
    pts += pd * 3.0

    if (solo + ast) >= 10:
        pts += 2.0
    if sacks >= 2:
        pts += 2.0
    if pd >= 3:
        pts += 2.0

    pts += n(stats, "st_td") * 6.0
    pts += n(stats, "st_ff") * 3.0
    pts += n(stats, "st_fum_rec") * 3.0

    return round(pts, 6)

def selftest():
    assert score_week({}) == 0.0
    assert score_week({"pass_yd": 299}) == round(299 * 0.04, 6)
    assert score_week({"pass_yd": 300}) == 14.0
    assert score_week({"pass_yd": 400}) == 19.0
    assert score_week({"rush_yd": 100}) == 12.0
    assert score_week({"rush_yd": 200}) == 23.0
    assert score_week({"rec_yd": 100}) == 12.0
    assert score_week({"rec_yd": 200}) == 23.0
    assert score_week({"idp_tkl_solo": 10}) == 17.0
    assert score_week({"idp_sack": 2}) == 8.0
    assert score_week({"idp_pass_def": 3}) == 11.0
    assert score_week({"st_td": 1, "st_ff": 1, "st_fum_rec": 1}) == 12.0
    print("SELFTEST PASS")

if __name__ == "__main__":
    selftest()
