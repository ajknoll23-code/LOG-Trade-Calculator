"""
prod_mult_pipeline.py -- reconstructs PROD_MULT_DATA from real source inputs.

WHY THIS EXISTS: PROD_MULT_DATA (baked into index.html, 847 static entries)
has never had a callable script that produces it from raw inputs. Four
independent AI reviews (DeepSeek, Gemini, Grok, ChatGPT) and this project's
own technical spec all flagged this as the single highest-leverage gap: the
model's most load-bearing number (prod_mult, a ~10x range from 0.15-1.55,
the only component of playerValue() that distinguishes players at the same
position) has only ever existed as a hand-transcribed table plus a prose
description of the formula in code comments.

This script reconstructs that formula from real, already-collected data:
  - ppg_results.json          (real 2025 true PPG + weekly scores, this
                                league's exact scoring rules)
  - sleeper_2026_projections.json (real Sleeper season-total projections)
  - fantasypros_2026_projections.json (real FantasyPros season-total
                                projections, manually transcribed from this
                                league's roster screenshots)
  - durability_results.json   (real year-over-year games-played R^2 per
                                position, from durability_pipeline.py)

FORMULA (as documented in code comments across ppg_pipeline.py,
durability_pipeline.py, and index.html's productionMultiplier() function):

  shrunk_ppg    = (n * true_ppg + k[pos] * pos_mean_ppg) / (n + k[pos])
                  -- empirical-Bayes shrinkage of a player's real 2025 PPG
                  toward their position's mean PPG. n = games actually
                  played in 2025 (so n=0 -> full shrinkage to position
                  mean, which is the correct behavior for a rookie with no
                  2025 data at all). k[pos] was previously a single
                  inspection-chosen placeholder (k=3, see ppg_pipeline.py's
                  own comment); this script derives it for real, per
                  position, as sigma^2_within / sigma^2_between using the
                  real weekly_points arrays already collected for exactly
                  this purpose.

  durability_projected_games =
      (own_weight * own_avail_2025 + (1 - own_weight) * pos_median_avail_2025) * 17
                  -- own_weight was previously a flat, un-derived 65/35
                  split applied identically to every position (see
                  durability_pipeline.py's own docstring, which explicitly
                  built the real per-position R^2 to replace this and was
                  never wired back in). This script sets own_weight = the
                  real position R^2 from durability_results.json, per that
                  script's own stated interpretation ("if DL comes back at
                  R^2=0.30, that suggests roughly 30% own-history / 70%
                  position-median for DL").
                  A player entirely absent from ppg_results.json (true
                  rookie, zero 2025 snaps) has no meaningful "own
                  availability" signal -- own_weight is forced to 0 for
                  those players specifically (full reliance on position
                  median), rather than misreading "no data" as "0%
                  available."

  proj_2026     = 0.5 * fantasypros_2026_proj + 0.5 * sleeper_2026_proj_total
                  -- falls back to whichever single source exists if only
                  one of the two is available for a player (documented
                  explicitly per player in the audit output, not silent).

  combined      = 0.45 * (shrunk_ppg * durability_projected_games)
                  + 0.55 * proj_2026

  baseline[pos] = the `combined` value of the player at that position's
                  real roster-construction-matched replacement rank
                  (QB18, RB32, WR36, TE15, DL32, LB32, DB32 -- same ranks
                  already used elsewhere in this project for
                  POSITION_WEIGHT derivation), computed over the SAME
                  combined-value universe this script produces (not a
                  separately snapshotted number).

  ratio         = combined / baseline[pos]

  prod_mult     = clamp(-0.10 + 0.75 * ratio, 0.15, 1.55)
                  -- these exact constants reproduce two independently
                  documented facts already in the codebase: a player
                  exactly AT replacement level (ratio=1.0) gets 0.65,
                  matching the Elite-tier floor-rescue constant in
                  index.html's productionMultiplier() comment, and the
                  observed baked-data range is exactly [0.15, 1.55].

OUTPUT: writes prod_mult_pipeline_output.json with, for every player, the
full intermediate lineage (not just the final scalar) per ChatGPT's review
recommendation -- so a future "why is this player's number X" question is
answerable from this file directly, not by re-deriving it from scratch.

USAGE: python3 prod_mult_pipeline.py
Reads the four JSON inputs from the same directory as this script.
"""

import json
import os
import re
import statistics

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

REPLACEMENT_RANK = {"QB": 18, "RB": 32, "WR": 36, "TE": 15, "DL": 32, "LB": 32, "DB": 32}

SEASON_LENGTH_2025 = 17  # matches ppg_pipeline.py's real range(1,19) week span
SEASON_LENGTH_2026 = 17  # same real NFL schedule length assumed for the projection year

# Same bucket collapse used by durability_pipeline.py and sync_sleeper.py --
# kept identical on purpose so groupings here match what the live tool uses.
POS_BUCKET = {
    "DE": "DL", "DT": "DL", "DL": "DL", "OLB": "LB", "ILB": "LB", "LB": "LB",
    "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB", "DB": "DB",
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE",
}

TRACKED_POSITIONS = {"QB", "RB", "WR", "TE", "DL", "LB", "DB"}


def normalize_name(s):
    """Identical logic to index.html's normalizeName() -- kept in lockstep
    on purpose so this script's keys match the live tool's lookup keys."""
    return re.sub(r"\s+", " ", re.sub(r"[.'\u2019-]", "", s.strip().lower()))


def load_aliases():
    """Reuses ppg_pipeline.py's real ALIASES map by executing that file's
    module-level dict definition directly, rather than hand-copying it a
    third time into yet another script -- the exact anti-pattern flagged in
    ppg_pipeline.py's own header comment about ALIASES needing to be reused,
    not re-implemented, everywhere name matching happens."""
    ppg_path = os.path.join(SCRIPT_DIR, "ppg_pipeline.py")
    if not os.path.exists(ppg_path):
        return {}
    namespace = {}
    with open(ppg_path) as f:
        src = f.read()
    m = re.search(r"ALIASES\s*=\s*\{.*?\n\}", src, re.S)
    if not m:
        return {}
    exec(m.group(0), namespace)
    return namespace.get("ALIASES", {})


def resolve_key(name, aliases):
    key = normalize_name(name)
    return aliases.get(key, key)


def load_json(fname):
    path = os.path.join(SCRIPT_DIR, fname)
    with open(path) as f:
        return json.load(f)


def compute_shrinkage_k(ppg_rows):
    """k[pos] = sigma^2_within / sigma^2_between, computed per position from
    real weekly_points. This is the exact derivation DeepSeek's and Gemini's
    reviews both specified, and the one ppg_pipeline.py's own 2026-08-19
    comment says was the whole reason weekly_points was added to that
    file's output in the first place.

    sigma^2_within: pooled within-player variance of weekly scores (only
    players with >=2 scored weeks contribute -- a single-week player gives
    no within-player variance estimate).
    sigma^2_between: variance of players' own true_ppg (season means)
    within the position, using all players at that position regardless of
    weeks played.
    """
    by_pos = {}
    for r in ppg_rows:
        by_pos.setdefault(r["pos"], []).append(r)

    k_by_pos = {}
    for pos, rows in by_pos.items():
        # sigma^2_between: sample variance of true_ppg across all players
        # at this position.
        means = [r["true_ppg"] for r in rows]
        if len(means) < 2:
            k_by_pos[pos] = None
            continue
        var_between = statistics.variance(means)

        # sigma^2_within: pooled sample variance of weekly_points within
        # each player, pooled across players (sum of squared deviations
        # from each player's own mean, divided by total degrees of freedom).
        ss_within = 0.0
        df_within = 0
        for r in rows:
            weeks = r.get("weekly_points") or []
            if len(weeks) < 2:
                continue
            player_mean = sum(weeks) / len(weeks)
            ss_within += sum((w - player_mean) ** 2 for w in weeks)
            df_within += len(weeks) - 1

        if df_within == 0 or var_between == 0:
            k_by_pos[pos] = None
            continue
        var_within = ss_within / df_within
        k_by_pos[pos] = var_within / var_between

    return k_by_pos


def compute_position_mean_ppg(ppg_rows):
    by_pos = {}
    for r in ppg_rows:
        by_pos.setdefault(r["pos"], []).append(r["true_ppg"])
    return {pos: sum(vals) / len(vals) for pos, vals in by_pos.items()}


def compute_position_median_availability(ppg_rows):
    """Real 2025 games-played fraction, median per position -- matches
    durability_pipeline.py's own availability definition
    (games_played / SEASON_MAX_GAMES)."""
    by_pos = {}
    for r in ppg_rows:
        avail = min(1.0, r["games_played"] / SEASON_LENGTH_2025)
        by_pos.setdefault(r["pos"], []).append(avail)
    return {pos: statistics.median(vals) for pos, vals in by_pos.items()}


def main():
    ppg_rows = load_json("ppg_results.json")
    sleeper_2026 = load_json("sleeper_2026_projections.json")
    fantasypros_2026 = load_json("fantasypros_2026_projections.json")
    durability = load_json("durability_results.json")
    aliases = load_aliases()

    # ---- Step 1: real per-position constants derived from real data ----
    k_by_pos = compute_shrinkage_k(ppg_rows)
    pos_mean_ppg = compute_position_mean_ppg(ppg_rows)
    pos_median_avail = compute_position_median_availability(ppg_rows)

    own_weight_by_pos = {}
    for pos in TRACKED_POSITIONS:
        r2 = durability.get(pos, {}).get("r_squared")
        own_weight_by_pos[pos] = max(0.0, min(1.0, r2)) if r2 is not None else 0.0

    # ---- Step 2: build a unified player universe, keyed by resolved name
    # (falls back to sleeper_id as a secondary check where both exist, to
    # catch cases where two different real people share a resolved name
    # key -- see this project's own documented Devin Neal RB/DB collision). ----
    players = {}  # key -> record

    def get_or_create(key, pos, sleeper_id=None, display_name=None):
        bucket_pos = POS_BUCKET.get(pos, pos)
        rec = players.get(key)
        if rec is None:
            rec = {
                "key": key,
                "display_name": display_name,
                "pos": bucket_pos,
                "sleeper_id": sleeper_id,
                "true_ppg": None,
                "games_played_2025": 0,
                "sleeper_2026_proj_total": None,
                "fantasypros_2026_proj": None,
            }
            players[key] = rec
        if sleeper_id and not rec.get("sleeper_id"):
            rec["sleeper_id"] = sleeper_id
        if display_name and not rec.get("display_name"):
            rec["display_name"] = display_name
        return rec

    for r in ppg_rows:
        pos = POS_BUCKET.get(r["pos"], r["pos"])
        if pos not in TRACKED_POSITIONS:
            continue
        key = resolve_key(r["player"], aliases)
        rec = get_or_create(key, r["pos"], r.get("sleeper_id"), r["player"])
        rec["true_ppg"] = r["true_ppg"]
        rec["games_played_2025"] = r["games_played"]

    for r in sleeper_2026:
        pos = POS_BUCKET.get(r["pos"], r["pos"])
        if pos not in TRACKED_POSITIONS:
            continue
        key = resolve_key(r["player"], aliases)
        rec = get_or_create(key, r["pos"], r.get("sleeper_id"), r["player"])
        rec["sleeper_2026_proj_total"] = r.get("sleeper_2026_proj_total")

    fp_unmatched = []
    for r in fantasypros_2026:
        pos = POS_BUCKET.get(r["pos"], r["pos"])
        if pos not in TRACKED_POSITIONS:
            continue
        key = resolve_key(r["player"], aliases)
        if key not in players:
            fp_unmatched.append(r["player"])
        rec = get_or_create(key, r["pos"], None, r["player"])
        rec["fantasypros_2026_proj"] = r.get("fantasypros_2026_proj")

    # ---- Step 3: per-player lineage computation ----
    audit = {}
    for key, rec in players.items():
        pos = rec["pos"]
        if pos not in TRACKED_POSITIONS:
            continue

        n = rec["games_played_2025"] or 0
        true_ppg = rec["true_ppg"]
        k = k_by_pos.get(pos)
        posmean = pos_mean_ppg.get(pos)

        if true_ppg is not None and k is not None and posmean is not None:
            shrunk_ppg = (n * true_ppg + k * posmean) / (n + k)
            shrinkage_note = "real"
        elif posmean is not None:
            # No real 2025 data at all (true rookie / zero-snap player) --
            # full shrinkage to position mean, which the shrinkage formula
            # produces automatically at n=0 but is made explicit here for
            # players who never appear in ppg_results.json in the first
            # place (n implicitly 0, true_ppg unknown rather than literally
            # zero).
            shrunk_ppg = posmean
            shrinkage_note = "no_2025_data_full_shrink_to_position_mean"
        else:
            shrunk_ppg = None
            shrinkage_note = "no_position_mean_available"

        has_own_history = rec["true_ppg"] is not None
        own_weight = own_weight_by_pos.get(pos, 0.0) if has_own_history else 0.0
        own_avail = min(1.0, n / SEASON_LENGTH_2025) if has_own_history else None
        med_avail = pos_median_avail.get(pos)

        if med_avail is not None:
            if has_own_history and own_avail is not None:
                durability_avail = own_weight * own_avail + (1 - own_weight) * med_avail
            else:
                durability_avail = med_avail
            durability_games = durability_avail * SEASON_LENGTH_2026
        else:
            durability_avail = None
            durability_games = None

        sleeper_proj = rec["sleeper_2026_proj_total"]
        fp_proj = rec["fantasypros_2026_proj"]
        if sleeper_proj is not None and fp_proj is not None:
            proj_2026 = 0.5 * fp_proj + 0.5 * sleeper_proj
            proj_source = "blend_50_50"
        elif fp_proj is not None:
            proj_2026 = fp_proj
            proj_source = "fantasypros_only"
        elif sleeper_proj is not None:
            proj_2026 = sleeper_proj
            proj_source = "sleeper_only"
        else:
            proj_2026 = None
            proj_source = "no_projection_available"

        if shrunk_ppg is not None and durability_games is not None and proj_2026 is not None:
            history_component = shrunk_ppg * durability_games
            combined = 0.45 * history_component + 0.55 * proj_2026
        else:
            combined = None
            history_component = None

        audit[key] = {
            "player": rec["display_name"],
            "pos": pos,
            "sleeper_id": rec["sleeper_id"],
            "games_played_2025": n,
            "true_ppg_2025": true_ppg,
            "shrinkage_k_used": k,
            "position_mean_ppg": posmean,
            "shrunk_ppg": shrunk_ppg,
            "shrinkage_note": shrinkage_note,
            "own_weight_durability": own_weight,
            "own_avail_2025": own_avail,
            "position_median_avail_2025": med_avail,
            "durability_projected_avail_2026": durability_avail,
            "durability_projected_games_2026": durability_games,
            "sleeper_2026_proj_total": sleeper_proj,
            "fantasypros_2026_proj": fp_proj,
            "proj_2026_blended": proj_2026,
            "proj_source": proj_source,
            "history_component": history_component,
            "combined": combined,
        }

    # ---- Step 4: baseline[pos] = combined value at real replacement rank ----
    baseline_by_pos = {}
    for pos, rank in REPLACEMENT_RANK.items():
        vals = sorted(
            (a["combined"] for a in audit.values() if a["pos"] == pos and a["combined"] is not None),
            reverse=True,
        )
        if len(vals) >= rank:
            baseline_by_pos[pos] = vals[rank - 1]
        elif vals:
            baseline_by_pos[pos] = vals[-1]
            print(f"WARNING: {pos} has only {len(vals)} players with combined values, "
                  f"fewer than replacement rank {rank}. Using lowest available instead.")
        else:
            baseline_by_pos[pos] = None
            print(f"WARNING: {pos} has no players with combined values at all.")

    # ---- Step 5: ratio + prod_mult ----
    for key, a in audit.items():
        baseline = baseline_by_pos.get(a["pos"])
        if a["combined"] is not None and baseline:
            ratio = a["combined"] / baseline
            prod_mult = max(0.15, min(1.55, -0.10 + 0.75 * ratio))
        else:
            ratio = None
            prod_mult = None
        a["baseline_used"] = baseline
        a["ratio"] = ratio
        a["prod_mult_reconstructed"] = round(prod_mult, 4) if prod_mult is not None else None

    output = {
        "shrinkage_k_by_position": k_by_pos,
        "position_mean_ppg": pos_mean_ppg,
        "position_median_availability_2025": pos_median_avail,
        "own_weight_durability_by_position": own_weight_by_pos,
        "replacement_rank_used": REPLACEMENT_RANK,
        "baseline_combined_by_position": baseline_by_pos,
        "fantasypros_names_unmatched_to_existing_record": fp_unmatched,
        "players": audit,
    }

    out_path = os.path.join(SCRIPT_DIR, "prod_mult_pipeline_output.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, sort_keys=False)

    print("=== Real per-position shrinkage k (sigma^2_within / sigma^2_between) ===")
    for pos, k in sorted(k_by_pos.items()):
        print(f"  {pos:3s}: k = {k:.3f}" if k is not None else f"  {pos:3s}: k = n/a")
    print()
    print("=== Real durability own-weight (= position R^2, replacing flat 65/35) ===")
    for pos in sorted(TRACKED_POSITIONS):
        r2 = durability.get(pos, {}).get("r_squared")
        print(f"  {pos:3s}: R^2 = {r2}  ->  own_weight = {own_weight_by_pos.get(pos):.3f}")
    print()
    print("=== Real baseline[pos] (combined value at replacement rank) ===")
    for pos, rank in REPLACEMENT_RANK.items():
        print(f"  {pos:3s} (rank {rank}): {baseline_by_pos.get(pos)}")
    print()
    print(f"Total players with a reconstructed prod_mult: "
          f"{sum(1 for a in audit.values() if a['prod_mult_reconstructed'] is not None)}")
    print(f"FantasyPros names that never matched an existing player record: "
          f"{len(fp_unmatched)}")
    print(f"Full per-player lineage written to {out_path}")


if __name__ == "__main__":
    main()
