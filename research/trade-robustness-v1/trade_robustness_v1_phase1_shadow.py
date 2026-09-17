#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = Path(__file__).resolve().parent

INDEX = ROOT / "index.html"
ROSTERS = ROOT / "data/league_rosters.json"
UNCERTAINTY = (
    ROOT / "scripts/artifacts/generated/value_uncertainty.json"
)

OUTJSON = OUTDIR / "trade_robustness_v1_phase1_shadow.json"
OUTMD = OUTDIR / "trade_robustness_v1_phase1_shadow.md"
MANIFEST = OUTDIR / "trade_robustness_v1_phase1_manifest.json"

METHOD = "trade-robustness-v1-live-verdict-sensitivity-shadow"
RANGE_SEMANTICS = "sensitivity_envelope_v1_not_probability_interval"
TOP_PLAYERS_1V1 = 10
TOP_SINGLE_1V2 = 6
TOP_PACKAGE_1V2 = 8
POSITIONS = {"QB", "RB", "WR", "TE", "DL", "LB", "DB"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_name(value: str) -> str:
    return " ".join((value or "").lower().strip().split())


def extract_balanced(
    text: str,
    marker: str,
    open_char: str = "{",
    close_char: str = "}",
) -> str:
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"missing JS marker: {marker}")
    open_idx = text.find(open_char, start)
    if open_idx < 0:
        raise RuntimeError(
            f"missing opening {open_char}: {marker}"
        )

    depth = 0
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    i = open_idx

    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if line_comment:
            if ch == "\n":
                line_comment = False
            i += 1
            continue

        if block_comment:
            if ch == "*" and nxt == "/":
                block_comment = False
                i += 2
                continue
            i += 1
            continue

        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            i += 1
            continue

        if ch == "/" and nxt == "/":
            line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            block_comment = True
            i += 2
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            continue

        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1

    raise RuntimeError(f"unbalanced JS block: {marker}")


def extract_function(text: str, name: str) -> str:
    return extract_balanced(text, f"function {name}(")


def extract_package_config(text: str) -> str:
    start = text.find(
        "const PACKAGE_ADJUSTMENT_PRODUCTION_V1 = Object.freeze({"
    )
    end = text.find(
        "function packageAdjustmentSize2Multiplier(",
        start,
    )
    if start < 0 or end <= start:
        raise RuntimeError(
            "Cannot extract production package-adjustment config"
        )
    return text[start:end].strip()


def build_roster_pools() -> tuple[dict[int, list[dict]], dict]:
    uncertainty = read(UNCERTAINTY)
    players = uncertainty.get("players") or {}
    if (
        uncertainty.get("range_semantics")
        != RANGE_SEMANTICS
    ):
        raise RuntimeError("uncertainty semantics drift")

    by_sid = {}
    for key, row in players.items():
        sid = str(row.get("sleeper_id") or "").strip()
        pos = str(row.get("pos") or "")
        if not sid or pos not in POSITIONS:
            continue

        center = float(row["center_value"])
        low = float(row["range_low"])
        high = float(row["range_high"])

        if not (
            0 <= low <= center <= high
            and math.isfinite(center)
            and math.isfinite(low)
            and math.isfinite(high)
        ):
            raise RuntimeError(
                f"invalid uncertainty envelope for {key}"
            )

        by_sid[sid] = {
            "key": key,
            "pos": pos,
            "center": center,
            "low": low,
            "high": high,
            "half_width": float(
                row["relative_half_width"]
            ),
            "tier": row.get("uncertainty_tier"),
        }

    roster_doc = read(ROSTERS)
    pools = {}
    unmatched = []
    slot_counts = Counter()

    for roster in roster_doc.get("rosters") or []:
        rid = int(roster["roster_id"])
        seen = set()
        rows = []

        for slot in (
            "starters",
            "bench",
            "taxi",
            "reserve_ir",
        ):
            for item in roster.get(slot) or []:
                sid = str(
                    item.get("player_id") or ""
                ).strip()
                if not sid or sid in seen:
                    continue
                seen.add(sid)

                u = by_sid.get(sid)
                if not u:
                    unmatched.append({
                        "roster_id": rid,
                        "slot": slot,
                        "sleeper_id": sid,
                        "name": item.get("name"),
                    })
                    continue

                rows.append({
                    **u,
                    "name": item.get("name") or u["key"],
                    "sleeper_id": sid,
                    "slot": slot,
                })
                slot_counts[slot] += 1

        rows.sort(
            key=lambda r: (
                -r["center"],
                r["key"],
            )
        )
        pools[rid] = rows

    audit = {
        "roster_count": len(pools),
        "matched_unique_rostered_players":
            sum(len(v) for v in pools.values()),
        "unmatched_roster_entries": unmatched,
        "slot_counts": dict(sorted(slot_counts.items())),
    }
    return pools, audit


def combinations2(rows: list[dict]):
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            yield [rows[i], rows[j]]


def build_cases(pools: dict[int, list[dict]]) -> list[dict]:
    roster_ids = sorted(pools)
    cases = []

    for i, a_id in enumerate(roster_ids):
        for b_id in roster_ids[i + 1:]:
            a_pool = pools[a_id]
            b_pool = pools[b_id]

            for a in a_pool[:TOP_PLAYERS_1V1]:
                for b in b_pool[:TOP_PLAYERS_1V1]:
                    cases.append({
                        "case_id":
                            f"1v1:{a_id}:{b_id}:{a['sleeper_id']}:{b['sleeper_id']}",
                        "structure": "1v1",
                        "roster_a": a_id,
                        "roster_b": b_id,
                        "A": [a],
                        "B": [b],
                    })

            a_singles = a_pool[:TOP_SINGLE_1V2]
            b_singles = b_pool[:TOP_SINGLE_1V2]
            a_pair_pool = a_pool[:TOP_PACKAGE_1V2]
            b_pair_pool = b_pool[:TOP_PACKAGE_1V2]

            for a in a_singles:
                for pair in combinations2(b_pair_pool):
                    cases.append({
                        "case_id":
                            f"1v2:{a_id}:{b_id}:{a['sleeper_id']}:"
                            + "-".join(
                                x["sleeper_id"] for x in pair
                            ),
                        "structure": "1v2",
                        "roster_a": a_id,
                        "roster_b": b_id,
                        "A": [a],
                        "B": pair,
                    })

            for b in b_singles:
                for pair in combinations2(a_pair_pool):
                    cases.append({
                        "case_id":
                            f"2v1:{a_id}:{b_id}:"
                            + "-".join(
                                x["sleeper_id"] for x in pair
                            )
                            + f":{b['sleeper_id']}",
                        "structure": "2v1",
                        "roster_a": a_id,
                        "roster_b": b_id,
                        "A": pair,
                        "B": [b],
                    })

    return cases


def compact_case(case: dict) -> dict:
    keep = (
        "key",
        "pos",
        "center",
        "low",
        "high",
        "half_width",
        "tier",
        "sleeper_id",
    )
    return {
        "case_id": case["case_id"],
        "structure": case["structure"],
        "roster_a": case["roster_a"],
        "roster_b": case["roster_b"],
        "A": [
            {k: row[k] for k in keep}
            for row in case["A"]
        ],
        "B": [
            {k: row[k] for k in keep}
            for row in case["B"]
        ],
    }


def run_live_js(cases: list[dict]) -> list[dict]:
    text = INDEX.read_text(encoding="utf-8")
    parts = [
        extract_package_config(text),
        extract_function(
            text,
            "packageAdjustmentSize2Multiplier",
        ),
        extract_function(
            text,
            "packageAdjustmentSize2CompositionFactor",
        ),
        extract_function(
            text,
            "packageAdjustmentAssessment",
        ),
        extract_function(
            text,
            "packageAdjustmentForTrade",
        ),
        extract_function(text, "sideTotal"),
        extract_function(text, "tradeVerdictTotals"),
    ]

    harness = r"""
const fs = require('fs');
const cases = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
let state = {A:[], B:[]};

function item(x, field) {
  return {
    type: 'player',
    pos: x.pos,
    value: Number(x[field]),
    name: x.key,
  };
}

function evalScenario(c, aField, bField) {
  state = {
    A: c.A.map(x => item(x, aField)),
    B: c.B.map(x => item(x, bField)),
  };
  const totals = tradeVerdictTotals();
  return {
    A: Number(totals.A),
    B: Number(totals.B),
    delta: Number(totals.A) - Number(totals.B),
  };
}

const out = [];
for (const c of cases) {
  state = {
    A: c.A.map(x => item(x, 'center')),
    B: c.B.map(x => item(x, 'center')),
  };
  const assessment = packageAdjustmentAssessment();

  out.push({
    case_id: c.case_id,
    package_status: assessment.status,
    package_tier:
      assessment.packageAdjustment
        ? assessment.packageAdjustment.premiumTier
        : null,
    center: evalScenario(c, 'center', 'center'),
    a_low_b_high: evalScenario(c, 'low', 'high'),
    a_high_b_low: evalScenario(c, 'high', 'low'),
  });
}

process.stdout.write(JSON.stringify(out));
"""

    js = "\n\n".join(parts) + "\n\n" + harness

    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".js",
        delete=False,
        encoding="utf-8",
    ) as jf, tempfile.NamedTemporaryFile(
        "w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as cf:
        jf.write(js)
        js_path = Path(jf.name)
        json.dump(
            [compact_case(c) for c in cases],
            cf,
            separators=(",", ":"),
        )
        case_path = Path(cf.name)

    try:
        proc = subprocess.run(
            ["node", str(js_path), str(case_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(proc.stdout)
    finally:
        js_path.unlink(missing_ok=True)
        case_path.unlink(missing_ok=True)


def pct_margin(delta: float, a: float, b: float):
    denom = max(1.0, (abs(a) + abs(b)) / 2.0)
    return abs(delta) / denom


def margin_bucket(value: float) -> str:
    if value < 0.05:
        return "under_5pct"
    if value < 0.10:
        return "5_to_10pct"
    if value < 0.20:
        return "10_to_20pct"
    return "20pct_plus"


def analyze() -> dict:
    pools, roster_audit = build_roster_pools()
    cases = build_cases(pools)
    by_id = {c["case_id"]: c for c in cases}
    js_results = run_live_js(cases)

    rows = []
    structure = defaultdict(
        lambda: {
            "cases": 0,
            "robust": 0,
            "fragile": 0,
            "ties": 0,
        }
    )
    margins = defaultdict(
        lambda: {
            "cases": 0,
            "robust": 0,
            "fragile": 0,
        }
    )
    package_status = Counter()
    tier_counts = Counter()

    for result in js_results:
        case = by_id[result["case_id"]]
        center = result["center"]
        delta = float(center["delta"])
        base_margin_pct = pct_margin(
            delta,
            float(center["A"]),
            float(center["B"]),
        )

        if abs(delta) <= 1e-9:
            base_winner = "tie"
            robust = False
            adverse_delta = 0.0
        elif delta > 0:
            base_winner = "A"
            adverse_delta = float(
                result["a_low_b_high"]["delta"]
            )
            robust = adverse_delta > 1e-9
        else:
            base_winner = "B"
            adverse_delta = float(
                result["a_high_b_low"]["delta"]
            )
            robust = adverse_delta < -1e-9

        classification = (
            "tie"
            if base_winner == "tie"
            else ("robust" if robust else "fragile")
        )

        s = structure[case["structure"]]
        s["cases"] += 1
        if classification == "robust":
            s["robust"] += 1
        elif classification == "fragile":
            s["fragile"] += 1
        else:
            s["ties"] += 1

        mb = margin_bucket(base_margin_pct)
        margins[mb]["cases"] += 1
        if classification in {"robust", "fragile"}:
            margins[mb][classification] += 1

        package_status[result["package_status"]] += 1
        if result.get("package_tier"):
            tier_counts[result["package_tier"]] += 1

        widths = [
            float(x["half_width"])
            for x in case["A"] + case["B"]
        ]
        max_width = max(widths)
        mean_width = sum(widths) / len(widths)

        rows.append({
            "case_id": case["case_id"],
            "structure": case["structure"],
            "roster_a": case["roster_a"],
            "roster_b": case["roster_b"],
            "A": [
                {
                    "player": x["key"],
                    "pos": x["pos"],
                    "center": x["center"],
                    "low": x["low"],
                    "high": x["high"],
                    "tier": x["tier"],
                }
                for x in case["A"]
            ],
            "B": [
                {
                    "player": x["key"],
                    "pos": x["pos"],
                    "center": x["center"],
                    "low": x["low"],
                    "high": x["high"],
                    "tier": x["tier"],
                }
                for x in case["B"]
            ],
            "package_status":
                result["package_status"],
            "package_tier":
                result.get("package_tier"),
            "center_totals": center,
            "base_winner": base_winner,
            "base_margin_pct":
                round(base_margin_pct, 6),
            "adverse_delta":
                round(adverse_delta, 6),
            "classification": classification,
            "mean_player_relative_half_width":
                round(mean_width, 6),
            "max_player_relative_half_width":
                round(max_width, 6),
        })

    non_ties = [
        r for r in rows
        if r["classification"] != "tie"
    ]
    robust_rows = [
        r for r in non_ties
        if r["classification"] == "robust"
    ]
    fragile_rows = [
        r for r in non_ties
        if r["classification"] == "fragile"
    ]

    def sort_fragile(row):
        return (
            row["base_margin_pct"],
            -row["max_player_relative_half_width"],
            row["case_id"],
        )

    fragile_examples = sorted(
        fragile_rows,
        key=sort_fragile,
    )[:50]

    robust_examples = sorted(
        robust_rows,
        key=lambda r: (
            -r["base_margin_pct"],
            r["max_player_relative_half_width"],
            r["case_id"],
        ),
    )[:25]

    return {
        "schema_version": 1,
        "study_id": "trade-robustness-v1-phase1-shadow",
        "method_version": METHOD,
        "status": "SHADOW_COMPLETE",
        "decision":
            "PASS_TRADE_ROBUSTNESS_V1_PHASE1_SHADOW",
        "generated_at_utc":
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        "research_only": True,
        "production_change_authorized": False,
        "semantics": {
            "uncertainty_range":
                RANGE_SEMANTICS,
            "robust": (
                "The center-value winner remains ahead when "
                "every player on that winning side is moved to "
                "its sensitivity low and every player on the "
                "other side is moved to its sensitivity high, "
                "with the actual live trade-verdict/package "
                "adjustment functions rerun."
            ),
            "fragile": (
                "The center-value verdict ties or flips under "
                "that deterministic adverse sensitivity corner."
            ),
            "not_probability": (
                "Robust/fragile is a sensitivity classification, "
                "not a probability or calibrated confidence level."
            ),
        },
        "universe": {
            "roster_audit": roster_audit,
            "top_players_per_team_1v1":
                TOP_PLAYERS_1V1,
            "top_single_players_per_team_1v2":
                TOP_SINGLE_1V2,
            "top_package_players_per_team_1v2":
                TOP_PACKAGE_1V2,
            "total_cases": len(rows),
            "non_tie_cases": len(non_ties),
        },
        "summary": {
            "robust_cases": len(robust_rows),
            "fragile_cases": len(fragile_rows),
            "tie_cases":
                len(rows) - len(non_ties),
            "robust_share_of_non_ties": round(
                len(robust_rows)
                / max(1, len(non_ties)),
                6,
            ),
            "fragile_share_of_non_ties": round(
                len(fragile_rows)
                / max(1, len(non_ties)),
                6,
            ),
            "median_base_margin_pct":
                round(
                    median(
                        r["base_margin_pct"]
                        for r in non_ties
                    ),
                    6,
                )
                if non_ties else None,
            "median_max_player_half_width":
                round(
                    median(
                        r[
                            "max_player_relative_half_width"
                        ]
                        for r in non_ties
                    ),
                    6,
                )
                if non_ties else None,
        },
        "by_structure": {
            key: value
            for key, value in sorted(
                structure.items()
            )
        },
        "by_base_margin_bucket": {
            key: value
            for key, value in sorted(
                margins.items()
            )
        },
        "package_adjustment_status_counts":
            dict(sorted(package_status.items())),
        "package_adjustment_tier_counts":
            dict(sorted(tier_counts.items())),
        "fragile_examples": fragile_examples,
        "robust_examples": robust_examples,
        "implementation_rule": (
            "A future UI shadow may display only "
            "Sensitivity Robust / Sensitivity Fragile plus "
            "the deterministic low/high trade totals. It may "
            "not display probability language until the "
            "uncertainty envelopes are empirically calibrated."
        ),
    }


def render(result: dict) -> str:
    s = result["summary"]
    lines = [
        "# Trade Robustness V1 Phase 1 — Shadow",
        "",
        f"**Decision:** `{result['decision']}`",
        "",
        "**RESEARCH ONLY. No calculator behavior changed.**",
        "",
        "## What this tests",
        "",
        "The shadow reruns the actual production trade-verdict "
        "and package-adjustment functions under the existing "
        "player sensitivity envelopes.",
        "",
        "- `robust`: the center-value winner still wins in the "
        "deterministic adverse corner.",
        "- `fragile`: the center-value winner ties or loses in "
        "the adverse corner.",
        "- These are **not probability/confidence labels**.",
        "",
        "## Universe",
        "",
        f"- Real league rosters: "
        f"**{result['universe']['roster_audit']['roster_count']}**",
        f"- Matched rostered players: "
        f"**{result['universe']['roster_audit']['matched_unique_rostered_players']}**",
        f"- Synthetic realistic cross-team trade cases: "
        f"**{result['universe']['total_cases']}**",
        "",
        "## Results",
        "",
        f"- Robust non-ties: **{s['robust_cases']}** "
        f"({100*s['robust_share_of_non_ties']:.1f}%)",
        f"- Fragile non-ties: **{s['fragile_cases']}** "
        f"({100*s['fragile_share_of_non_ties']:.1f}%)",
        f"- Center-value ties: **{s['tie_cases']}**",
        f"- Median base margin: "
        f"**{100*s['median_base_margin_pct']:.1f}%**",
        f"- Median maximum player envelope half-width: "
        f"**{100*s['median_max_player_half_width']:.1f}%**",
        "",
        "## By trade structure",
        "",
        "| Structure | Cases | Robust | Fragile | Ties |",
        "|---|---:|---:|---:|---:|",
    ]

    for key, row in result["by_structure"].items():
        lines.append(
            f"| {key} | {row['cases']} | "
            f"{row['robust']} | {row['fragile']} | "
            f"{row['ties']} |"
        )

    lines += [
        "",
        "## Example fragile trades",
        "",
        "| Structure | Side A | Side B | Base margin | Package status |",
        "|---|---|---|---:|---|",
    ]

    for row in result["fragile_examples"][:25]:
        a = " + ".join(
            x["player"] for x in row["A"]
        )
        b = " + ".join(
            x["player"] for x in row["B"]
        )
        lines.append(
            f"| {row['structure']} | {a} | {b} | "
            f"{100*row['base_margin_pct']:.1f}% | "
            f"{row['package_status']} |"
        )

    lines += [
        "",
        "## Guardrails",
        "",
        "- Fundamental Value centers are unchanged.",
        "- Sensitivity envelopes are unchanged.",
        "- Market Value V2 is unchanged.",
        "- Team Utility is unchanged.",
        "- Package Adjustment is unchanged.",
        "- Trade Verdict is unchanged.",
        "- No probability label is permitted from this phase.",
        "",
    ]
    return "\n".join(lines)


def write() -> None:
    result = analyze()
    OUTJSON.write_text(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    OUTMD.write_text(
        render(result),
        encoding="utf-8",
    )

    manifest = {
        "schema_version": 1,
        "study_id": result["study_id"],
        "decision": result["decision"],
        "production_change_authorized": False,
        "index_sha256": sha(INDEX),
        "rosters_sha256": sha(ROSTERS),
        "uncertainty_sha256": sha(UNCERTAINTY),
        "output_json_sha256": sha(OUTJSON),
        "output_md_sha256": sha(OUTMD),
        "evaluator_sha256":
            sha(Path(__file__).resolve()),
    }
    MANIFEST.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "decision": result["decision"],
        "total_cases":
            result["universe"]["total_cases"],
        "robust_cases":
            result["summary"]["robust_cases"],
        "fragile_cases":
            result["summary"]["fragile_cases"],
        "robust_share":
            result["summary"][
                "robust_share_of_non_ties"
            ],
    }, indent=2))


def check() -> None:
    result = read(OUTJSON)

    assert (
        result["decision"]
        == "PASS_TRADE_ROBUSTNESS_V1_PHASE1_SHADOW"
    )
    assert result["production_change_authorized"] is False
    assert (
        result["semantics"]["uncertainty_range"]
        == RANGE_SEMANTICS
    )
    assert result["universe"]["roster_audit"]["roster_count"] == 12
    assert result["universe"]["total_cases"] >= 10000
    assert (
        result["summary"]["robust_cases"]
        + result["summary"]["fragile_cases"]
        + result["summary"]["tie_cases"]
        == result["universe"]["total_cases"]
    )

    print("Trade Robustness V1 Phase 1 checks PASS")


def selftest() -> None:
    assert margin_bucket(0.01) == "under_5pct"
    assert margin_bucket(0.07) == "5_to_10pct"
    assert margin_bucket(0.15) == "10_to_20pct"
    assert margin_bucket(0.30) == "20pct_plus"
    assert pct_margin(10, 100, 100) == 0.1
    print("Trade Robustness V1 self-test PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(
        required=True
    )
    group.add_argument("--selftest", action="store_true")
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        selftest()
    elif args.write:
        write()
    else:
        check()


if __name__ == "__main__":
    main()
