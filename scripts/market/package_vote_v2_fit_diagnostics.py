#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import package_vote_fit_diagnostics as v1d
import package_vote_v2_pipeline as v2p

CHALLENGES = ROOT / "research" / "package-adjustment-v2" / "package_vote_challenges_v2.json"
OUT_JSON = ROOT / "research" / "package-adjustment-v2" / "package_vote_v2_fit_diagnostics.json"
OUT_MD = ROOT / "research" / "package-adjustment-v2" / "package_vote_v2_fit_diagnostics.md"

BOOTSTRAP_REPS = 400
BOOTSTRAP_SEED = 20260908


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_records(rows, catalog, voter_weights):
    out = []
    for row in rows:
        c = catalog.get(row["challenge_id"])
        if c is None:
            continue
        voter = row["voter_roster_id"]
        out.append({
            "challenge_id": c["id"],
            "pair_id": c["matched_pair_id"],
            "voter": voter,
            "choice": row["choice"],
            "y": 1.0 if row["choice"] == "P" else 0.0,
            "weight": float(voter_weights[voter]["ballot_weight"]),
            "ratio": float(c["raw_package_to_target_ratio"]),
            "log_ratio": math.log(max(float(c["raw_package_to_target_ratio"]), 1e-12)),
            "fg": float(c["fg"]),
            "fragmentation": float(c["fragmentation"]),
            "best_asset_gap": float(c["best_asset_gap"]),
            "package_size": int(c["package_size"]),
            "size3": 1.0 if int(c["package_size"]) == 3 else 0.0,
            "target_key": c["target"]["key"],
            "target_name": c["target"]["name"],
            "target_pos": c["target"]["pos"],
            "ratio_target": float(c["ratio_target"]),
        })
    return out


def fit_additive_custom(records, names):
    cols = [np.ones(len(records))]
    col_names = ["intercept"]
    for name in names:
        cols.append(np.asarray([float(r[name]) for r in records], dtype=float))
        col_names.append(name)
    X = np.column_stack(cols)
    y = np.asarray([r["y"] for r in records], dtype=float)
    w = np.asarray([r["weight"] for r in records], dtype=float)
    theta, ll, pred = v1d.logistic_irls(X, y, w)
    return {
        "coefficients": {n: float(v) for n, v in zip(col_names, theta)},
        "weighted_log_likelihood": float(ll),
        "aic": float(2 * len(theta) - 2 * ll),
        "predictions": [float(x) for x in pred],
        "parameter_count": len(theta),
    }


def lr(full, reduced, df=1):
    stat = max(0.0, 2.0 * (full["weighted_log_likelihood"] - reduced["weighted_log_likelihood"]))
    if df == 1:
        p = math.erfc(math.sqrt(stat / 2.0))
    else:
        p = None
    return {"lr_stat": stat, "df": df, "p_value_heuristic": p}


def matched_pair_fixed_effects(records):
    # Only use matched pairs where both package sizes received at least one vote.
    by_pair = defaultdict(list)
    for r in records:
        by_pair[r["pair_id"]].append(r)

    eligible_pairs = sorted(
        pair_id for pair_id, rows in by_pair.items()
        if {int(r["package_size"]) for r in rows} == {2, 3}
    )
    sub = [r for r in records if r["pair_id"] in set(eligible_pairs)]
    if len(eligible_pairs) < 3 or not sub:
        return {
            "eligible_pairs": len(eligible_pairs),
            "votes": len(sub),
            "coefficients": None,
            "note": "insufficient matched-pair coverage",
        }

    pair_ref = eligible_pairs[0]
    cols = [np.ones(len(sub))]
    names = ["intercept"]

    # Pair fixed effects absorb target + ratio + shared-asset baseline within pair.
    for pair_id in eligible_pairs[1:]:
        cols.append(np.asarray([1.0 if r["pair_id"] == pair_id else 0.0 for r in sub]))
        names.append(f"pair:{pair_id}")

    cols.append(np.asarray([r["size3"] for r in sub], dtype=float))
    names.append("size3")
    cols.append(np.asarray([r["fg"] for r in sub], dtype=float))
    names.append("fg")

    X = np.column_stack(cols)
    y = np.asarray([r["y"] for r in sub], dtype=float)
    w = np.asarray([r["weight"] for r in sub], dtype=float)
    theta, ll, _pred = v1d.logistic_irls(X, y, w, ridge=1e-5)
    coef = {n: float(v) for n, v in zip(names, theta)}

    return {
        "eligible_pairs": len(eligible_pairs),
        "votes": len(sub),
        "reference_pair": pair_ref,
        "size3_coefficient": coef["size3"],
        "fg_coefficient": coef["fg"],
        "weighted_log_likelihood": float(ll),
        "note": "research diagnostic; pair fixed effects absorb target/ratio/shared-asset baseline",
    }


def matched_pair_descriptives(records):
    by_pair = defaultdict(list)
    for r in records:
        by_pair[r["pair_id"]].append(r)

    rows = []
    for pair_id, vals in sorted(by_pair.items()):
        size2 = [r for r in vals if r["package_size"] == 2]
        size3 = [r for r in vals if r["package_size"] == 3]
        if not size2 or not size3:
            continue
        obs2 = v1d.weighted_mean(
            [r["y"] for r in size2], [r["weight"] for r in size2]
        )
        obs3 = v1d.weighted_mean(
            [r["y"] for r in size3], [r["weight"] for r in size3]
        )
        fg2 = sum(r["fg"] for r in size2) / len(size2)
        fg3 = sum(r["fg"] for r in size3) / len(size3)
        rows.append({
            "pair_id": pair_id,
            "votes_2": len(size2),
            "votes_3": len(size3),
            "package_choice_pct_2": 100.0 * obs2,
            "package_choice_pct_3": 100.0 * obs3,
            "size3_minus_size2_pp": 100.0 * (obs3 - obs2),
            "fg_2": fg2,
            "fg_3": fg3,
            "delta_fg": fg3 - fg2,
        })
    diffs = [r["size3_minus_size2_pp"] for r in rows]
    return {
        "matched_pairs": len(rows),
        "pair_rows": rows,
        "size3_minus_size2_pp_distribution": v1d.summarize_distribution(diffs),
        "pairs_where_3player_package_chosen_less_often": sum(r["size3_minus_size2_pp"] < 0 for r in rows),
        "pairs_where_3player_package_chosen_more_often": sum(r["size3_minus_size2_pp"] > 0 for r in rows),
        "pairs_tied": sum(abs(r["size3_minus_size2_pp"]) < 1e-12 for r in rows),
    }


def resample_voters(records, rng):
    by_voter = defaultdict(list)
    for r in records:
        by_voter[r["voter"]].append(r)
    voters = sorted(by_voter)
    sampled = [rng.choice(voters) for _ in voters]
    out = []
    for draw_idx, voter in enumerate(sampled):
        for r in by_voter[voter]:
            rr = dict(r)
            rr["voter"] = f"boot_{draw_idx}_{voter}"
            out.append(rr)
    return out


def bootstrap(records):
    rng = random.Random(BOOTSTRAP_SEED)
    size_coefs, fg_coefs, ratio_coefs = [], [], []
    for _ in range(BOOTSTRAP_REPS):
        sample = resample_voters(records, rng)
        model = fit_additive_custom(sample, ["log_ratio", "size3", "fg"])
        size_coefs.append(model["coefficients"]["size3"])
        fg_coefs.append(model["coefficients"]["fg"])
        ratio_coefs.append(model["coefficients"]["log_ratio"])

    return {
        "reps": BOOTSTRAP_REPS,
        "seed": BOOTSTRAP_SEED,
        "size3_coefficient": v1d.summarize_distribution(size_coefs),
        "fg_coefficient": v1d.summarize_distribution(fg_coefs),
        "log_ratio_coefficient": v1d.summarize_distribution(ratio_coefs),
        "size3_negative_rate_pct": 100.0 * sum(x < 0 for x in size_coefs) / len(size_coefs),
        "fg_negative_rate_pct": 100.0 * sum(x < 0 for x in fg_coefs) / len(fg_coefs),
        "ratio_positive_rate_pct": 100.0 * sum(x > 0 for x in ratio_coefs) / len(ratio_coefs),
    }


def conclusion(models, boot, pair_fe, gates):
    warnings = []
    if not gates["all_passed"]:
        warnings.append("V2 diagnostic collection gates are not all passed")
    if boot["size3_negative_rate_pct"] < 80.0:
        warnings.append("3-player package-size effect is not yet stable across voter clusters")
    if boot["fg_negative_rate_pct"] < 80.0:
        warnings.append("FG penalty sign is not yet stable across voter clusters")
    if boot["ratio_positive_rate_pct"] < 80.0:
        warnings.append("raw FV ratio response is not yet stable across voter clusters")

    best_aic = min(
        (m["aic"], name)
        for name, m in models.items()
        if isinstance(m, dict) and "aic" in m
    )
    return {
        "status": "hold_research" if warnings else "diagnostically_promising_not_production_ready",
        "production_promotion_allowed": False,
        "warnings": warnings,
        "lowest_aic_model": best_aic[1],
        "matched_pair_fixed_effects_available": bool(pair_fe.get("coefficients") or "size3_coefficient" in pair_fe),
        "note": (
            "No automatic promotion. Production requires separate prospective/OOS evidence "
            "after V2 establishes a stable structural signal."
        ),
    }


def write_report(result):
    d = result["diagnostics"]
    s = result["data"]
    models = d["models"]
    boot = d["voter_cluster_bootstrap"]
    pair = d["matched_pair_descriptives"]
    pair_fe = d["matched_pair_fixed_effects"]
    c = d["conclusion"]

    lines = [
        "# Package Vote V2 Fit Diagnostics",
        "",
        "**Status: RESEARCH ONLY — no production consumer changed.**",
        "",
        "V2 uses matched secondary splits: `[A,B]` versus `[A,C,D]` around the same target and raw FV ratio.",
        "",
        f"- Counted votes: `{s['counted_votes']}`",
        f"- Unique voters: `{s['unique_voters']}`",
        f"- Distinct challenges: `{s['distinct_challenges']}`",
        f"- Matched pairs with both sizes observed: `{s['matched_pairs_with_both_sizes']}`",
        "",
        "## Diagnostic conclusion",
        "",
        f"- Status: `{c['status']}`",
        f"- Lowest-AIC candidate: `{c['lowest_aic_model']}`",
        "- Production promotion allowed: `False`",
    ]
    if c["warnings"]:
        lines += ["", "Warnings:"]
        lines += [f"- {w}" for w in c["warnings"]]

    lines += [
        "",
        "## Candidate model comparison",
        "",
        "| Model | AIC | coefficients |",
        "|---|---:|---|",
    ]
    for name in ("ratio_only", "ratio_plus_size", "ratio_plus_fg", "ratio_plus_size_plus_fg"):
        m = models[name]
        lines.append(f"| {name} | {m['aic']:.2f} | `{m['coefficients']}` |")

    lines += [
        "",
        "## Incremental tests",
        "",
        f"- Add size to ratio-only: LR `{d['tests']['size_over_ratio']['lr_stat']:.3f}`, "
        f"p `{d['tests']['size_over_ratio']['p_value_heuristic']}`",
        f"- Add FG to ratio-only: LR `{d['tests']['fg_over_ratio']['lr_stat']:.3f}`, "
        f"p `{d['tests']['fg_over_ratio']['p_value_heuristic']}`",
        "",
        "## Voter-cluster bootstrap",
        "",
        f"- Reps: `{boot['reps']}`",
        f"- size3 negative: `{boot['size3_negative_rate_pct']:.1f}%`",
        f"- FG negative: `{boot['fg_negative_rate_pct']:.1f}%`",
        f"- raw-ratio coefficient positive: `{boot['ratio_positive_rate_pct']:.1f}%`",
        f"- size3 median: `{boot['size3_coefficient']['median']}` "
        f"(5–95% `{boot['size3_coefficient']['p05']}`–`{boot['size3_coefficient']['p95']}`)",
        f"- FG median: `{boot['fg_coefficient']['median']}` "
        f"(5–95% `{boot['fg_coefficient']['p05']}`–`{boot['fg_coefficient']['p95']}`)",
        "",
        "## Matched-pair design check",
        "",
        f"- Pairs with both sizes observed: `{pair['matched_pairs']}`",
        f"- 3-player package chosen less often: `{pair['pairs_where_3player_package_chosen_less_often']}` pairs",
        f"- 3-player package chosen more often: `{pair['pairs_where_3player_package_chosen_more_often']}` pairs",
        f"- ties: `{pair['pairs_tied']}` pairs",
        f"- median 3-player minus 2-player package-choice difference: "
        f"`{pair['size3_minus_size2_pp_distribution']['median']}` pp",
        "",
        "## Matched-pair fixed effects",
        "",
        f"- Eligible pairs: `{pair_fe.get('eligible_pairs')}`",
        f"- Votes: `{pair_fe.get('votes')}`",
        f"- size3 coefficient: `{pair_fe.get('size3_coefficient')}`",
        f"- FG coefficient: `{pair_fe.get('fg_coefficient')}`",
        "",
        "## Guardrails",
        "",
        "- V1 remains frozen and is never refit as V2.",
        "- V2 challenge values and matched metadata remain hidden from voters.",
        "- Bootstrap resamples whole voters.",
        "- No model in this report changes the live calculator.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def selftest():
    fake = []
    for i in range(80):
        size3 = 1.0 if i % 2 else 0.0
        ratio = [0.95, 1.05, 1.15, 1.30][i % 4]
        fg = 0.12 + 0.08 * size3 + 0.01 * (i % 5)
        eta = -0.7 + 1.5 * math.log(ratio) - 0.6 * size3 - 1.0 * fg
        p = 1.0 / (1.0 + math.exp(-eta))
        y = 1.0 if ((i * 29) % 100) / 100.0 < p else 0.0
        fake.append({
            "challenge_id": f"x{i}",
            "pair_id": f"p{i//2}",
            "voter": f"v{i%10}",
            "choice": "P" if y else "T",
            "y": y,
            "weight": 1.0,
            "ratio": ratio,
            "log_ratio": math.log(ratio),
            "fg": fg,
            "fragmentation": 0.3,
            "best_asset_gap": 0.2,
            "package_size": 3 if size3 else 2,
            "size3": size3,
            "target_key": "t",
            "target_name": "T",
            "target_pos": "WR",
            "ratio_target": ratio,
        })
    m = fit_additive_custom(fake, ["log_ratio", "size3", "fg"])
    assert set(m["coefficients"]) == {"intercept", "log_ratio", "size3", "fg"}
    pf = matched_pair_fixed_effects(fake)
    assert pf["eligible_pairs"] > 10
    print("Package Preference V2 diagnostics self-test passed.")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return

    doc = read_json(CHALLENGES)
    if doc.get("status") != "frozen_package_preference_v2" or doc.get("frozen") is not True:
        raise RuntimeError("unexpected/unfrozen V2 challenge catalog")
    catalog = {c["id"]: c for c in doc["challenges"]}

    raw = [v2p.parse_row(r) for r in v2p.fetch_rows() if v2p.is_package_v2_row(r)]
    raw = [r for r in raw if r is not None]
    capped, dropped = v2p.apply_daily_cap(raw)
    valid = [r for r in capped if r["challenge_id"] in catalog]
    weights = v2p.voter_weights(valid)
    records = build_records(valid, catalog, weights)

    summary = v2p.summarize(capped, doc)
    gates = summary["diagnostic_data_gates"]

    ratio_only = fit_additive_custom(records, ["log_ratio"])
    ratio_size = fit_additive_custom(records, ["log_ratio", "size3"])
    ratio_fg = fit_additive_custom(records, ["log_ratio", "fg"])
    ratio_both = fit_additive_custom(records, ["log_ratio", "size3", "fg"])

    models = {
        "ratio_only": ratio_only,
        "ratio_plus_size": ratio_size,
        "ratio_plus_fg": ratio_fg,
        "ratio_plus_size_plus_fg": ratio_both,
    }

    pair_desc = matched_pair_descriptives(records)
    pair_fe = matched_pair_fixed_effects(records)
    boot = bootstrap(records)

    diagnostics = {
        "models": models,
        "tests": {
            "size_over_ratio": lr(ratio_size, ratio_only),
            "fg_over_ratio": lr(ratio_fg, ratio_only),
        },
        "voter_cluster_bootstrap": boot,
        "matched_pair_descriptives": pair_desc,
        "matched_pair_fixed_effects": pair_fe,
    }
    diagnostics["conclusion"] = conclusion(models, boot, pair_fe, gates)

    for model in diagnostics["models"].values():
        model.pop("predictions", None)

    result = {
        "schema_version": 2,
        "status": "research_only",
        "production_consumer_changed": False,
        "market_value_consumer_changed": False,
        "fundamental_value_consumer_changed": False,
        "team_utility_consumer_changed": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "challenge_catalog": str(CHALLENGES.relative_to(ROOT)),
            "challenge_catalog_status": doc.get("status"),
            "challenge_catalog_frozen": doc.get("frozen"),
            "daily_cap_dropped": dropped,
        },
        "data": {
            "counted_votes": len(valid),
            "unique_voters": len(weights),
            "distinct_challenges": len({r["challenge_id"] for r in valid}),
            "matched_pairs_with_both_sizes": pair_desc["matched_pairs"],
        },
        "diagnostic_gates": gates,
        "diagnostics": diagnostics,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(result)
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")
    print(f"Conclusion: {diagnostics['conclusion']['status']}")


if __name__ == "__main__":
    main()
