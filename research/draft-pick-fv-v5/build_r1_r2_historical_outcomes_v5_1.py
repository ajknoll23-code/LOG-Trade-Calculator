#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import time
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path.cwd()
D = ROOT / "research" / "draft-pick-fv-v5"

PREREG = D / "r1_r2_bridge_preregistration_v5.json"
PICKS = D / "r1_r2_pick_identity_v5_1.jsonl"
CAT = D / "r1_r2_source_catalog_v5_1.json"
P21_SUM = D / "r1_r2_source_identity_summary_v5_1.json"
P21_MAN = D / "r1_r2_source_identity_manifest_v5_1.json"

SCORE_PATH = ROOT / "research/roster-economics/historical_weekly_points_pipeline.py"
AGE_PATH = ROOT / "scripts/validation/snapshot_values.py"

OUT_SOURCE = D / "r1_r2_historical_source_manifest_v5_1.json"
OUT_UNIVERSE = D / "r1_r2_historical_scored_universe_v5_1.jsonl"
OUT_DEV = D / "r1_r2_development_outcomes_v5_1.jsonl"
OUT_VAL = D / "r1_r2_locked_validation_outcomes_v5_1.jsonl"
OUT_SUM = D / "r1_r2_historical_outcome_summary_v5_1.json"
OUT_MD = D / "r1_r2_historical_outcome_summary_v5_1.md"
OUT_MAN = D / "r1_r2_historical_outcome_manifest_v5_1.json"

BASE = "https://api.sleeper.app/v1"
DRAFT_YEARS = (2018, 2019, 2020, 2021, 2022, 2023)
DEV = {2018, 2019, 2020, 2021}
VAL = {2022, 2023}
SEASONS = tuple(range(2018, 2026))
WEEKS = tuple(range(1, 19))
CELLS = ("r1_early", "r1_mid", "r1_late", "r2_early", "r2_mid", "r2_late")
POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
MIN_READY = 0.95

POS = {
    "QB":"QB","RB":"RB","FB":"RB","WR":"WR","TE":"TE",
    "DE":"DL","DT":"DL","NT":"DL","DL":"DL","EDGE":"DL",
    "OLB":"LB","ILB":"LB","MLB":"LB","LB":"LB",
    "CB":"DB","S":"DB","SS":"DB","FS":"DB","DB":"DB",
}

class GateError(RuntimeError):
    pass

def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def bsha(b):
    return hashlib.sha256(b).hexdigest()

def now():
    return datetime.now(timezone.utc).isoformat()

def import_file(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise GateError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

scoring = import_file(SCORE_PATH, "v5_scoring")
age_mod = import_file(AGE_PATH, "v5_age")

def norm_pos(v):
    return POS.get(str(v or "").strip().upper())

def read_jsonl(path):
    out = []
    with Path(path).open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            x = json.loads(line)
            if not isinstance(x, dict):
                raise GateError(f"{path}:{n}: non-object row")
            out.append(x)
    return out

def request_json(session, url, allow_old_week18=False):
    waits = (2,4,8,15,30,45,60)
    last = None
    for attempt in range(len(waits)):
        try:
            r = session.get(url, timeout=60)
            if allow_old_week18 and r.status_code == 404:
                raw = b"{}"
                return {}, {
                    "url":url, "status":404, "sha256":bsha(raw),
                    "bytes":len(raw), "top_level_n":0,
                }
            if r.status_code == 429:
                ra = r.headers.get("Retry-After")
                try:
                    ra = float(ra) if ra else 0.0
                except ValueError:
                    ra = 0.0
                wait = max(ra, waits[attempt])
                last = RuntimeError("HTTP 429")
                if attempt + 1 == len(waits):
                    break
                time.sleep(wait)
                continue
            r.raise_for_status()
            raw = r.content
            obj = json.loads(raw.decode("utf-8"))
            return obj, {
                "url":url, "status":r.status_code, "sha256":bsha(raw),
                "bytes":len(raw),
                "top_level_n":len(obj) if isinstance(obj,(dict,list)) else None,
            }
        except (requests.RequestException, UnicodeDecodeError, json.JSONDecodeError) as e:
            last = e
            if attempt + 1 < len(waits):
                time.sleep(waits[attempt])
    raise GateError(f"transport failure for {url}: {type(last).__name__}: {last}")

def dob(v):
    s = str(v or "").strip()
    if not s:
        return None
    try:
        d = date.fromisoformat(s[:10])
    except ValueError:
        return None
    return d.isoformat() if 1940 <= d.year <= 2010 else None

def age_sep1(birth, season):
    d = date.fromisoformat(birth)
    a = date(season,9,1)
    age = a.year-d.year-(((a.month,a.day)<(d.month,d.day)))
    if not 18 <= age <= 50:
        raise GateError(f"implausible age {age}: {birth} in {season}")
    return age

def sched_games(season):
    return 17 if season >= 2021 else 16

def required_weeks(season):
    return set(range(1,19 if season >= 2021 else 18))

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def main():
    pre = load(PREREG)
    cat = load(CAT)
    p21s = load(P21_SUM)
    p21m = load(P21_MAN)
    picks = read_jsonl(PICKS)

    if p21m["outcome_ingestion_authorized_next_stage"] is not True:
        raise GateError("V5.1 did not authorize outcomes")
    if p21m["candidate_fit_performed"] or p21m["validation_scored"]:
        raise GateError("upstream firewall already violated")
    if len(picks) != 9008 or cat["league_n"] != 378:
        raise GateError("V5.1 frozen corpus drift")
    if p21s["development_validation_split"]["split_changed"]:
        raise GateError("split drift")
    for p in (PICKS,CAT,P21_SUM):
        if p21m["output_hashes"][p.name] != sha(p):
            raise GateError(f"input hash drift: {p.name}")

    bridge = pre["frozen_scale_bridge"]
    ranks = {k:int(v) for k,v in pre["frozen_replacement_ranks"].items()}
    pos_weight = {k:float(v) for k,v in bridge["position_weight"].items()}
    prod = bridge["production_transform"]
    age_cfg = {
        "age_curve":bridge["age_curve"],
        "qb_post_peak_floor":float(bridge["qb_post_peak_floor"]),
        "lb_post_peak_decay_power":float(bridge["lb_post_peak_decay_power"]),
    }
    if set(ranks) != set(POSITIONS):
        raise GateError("replacement-rank position drift")
    if float(bridge["base_scale"]) != 5500.0:
        raise GateError("base-scale drift")

    session = requests.Session()
    session.headers["User-Agent"] = "LOG-Trade-Calculator-Draft-Pick-FV-V5-Phase3/1.0"

    player_obj, player_meta = request_json(session, f"{BASE}/players/nfl")
    if not isinstance(player_obj, dict):
        raise GateError("Sleeper player index is not object")

    player_index = {}
    for pid, x in player_obj.items():
        if not isinstance(x, dict):
            continue
        raw_pos = x.get("position")
        if not raw_pos and isinstance(x.get("fantasy_positions"), list) and x["fantasy_positions"]:
            raw_pos = x["fantasy_positions"][0]
        player_index[str(pid)] = {
            "position":norm_pos(raw_pos),
            "birth_date":dob(x.get("birth_date") or x.get("birthdate")),
            "name":x.get("full_name") or " ".join(
                y for y in (
                    str(x.get("first_name") or "").strip(),
                    str(x.get("last_name") or "").strip()
                ) if y
            ) or None,
        }

    target_pos = {}
    target_rows = {}
    for row in picks:
        sid = str(row.get("sleeper_id") or "").strip()
        if not sid:
            continue
        y = int(row["draft_year"])
        key = (y,sid)
        pos = norm_pos(row.get("position")) or player_index.get(sid,{}).get("position")
        if key not in target_rows:
            target_rows[key] = {
                "sleeper_id":sid,
                "gsis_id":row.get("gsis_id"),
                "name":row.get("name") or player_index.get(sid,{}).get("name"),
                "position":pos,
                "birth_date":player_index.get(sid,{}).get("birth_date"),
            }
        elif pos and target_rows[key].get("position") and pos != target_rows[key]["position"]:
            raise GateError(f"target position conflict {key}")
        if pos:
            target_pos.setdefault(sid,pos)

    seasons = {s:{} for s in SEASONS}
    nonempty_weeks = {s:set() for s in SEASONS}
    endpoint_meta = []

    for season in SEASONS:
        for week in WEEKS:
            obj, meta = request_json(
                session,
                f"{BASE}/stats/nfl/regular/{season}/{week}",
                allow_old_week18=(season <= 2020 and week == 18),
            )
            if not isinstance(obj, dict):
                raise GateError(f"{season} week {week}: non-object stats")
            meta.update({"season":season,"week":week,"nonempty":bool(obj)})
            endpoint_meta.append(meta)
            if obj:
                nonempty_weeks[season].add(week)

            active_n = 0
            for pid, stats in obj.items():
                if not isinstance(stats, dict):
                    continue
                try:
                    active = float(stats.get("gp") or 0) >= 1
                except (TypeError,ValueError):
                    active = False
                if not active:
                    continue
                sid = str(pid)
                pos = player_index.get(sid,{}).get("position") or target_pos.get(sid)
                if pos not in POSITIONS:
                    continue
                pts = float(scoring.score_week(stats))
                rec = seasons[season].setdefault(
                    sid, {"position":pos,"games":0,"total":0.0}
                )
                if rec["position"] != pos:
                    raise GateError(f"position drift {sid} {season}")
                rec["games"] += 1
                rec["total"] += pts
                active_n += 1
            meta["scored_active_player_n"] = active_n
            print(f"{season} week {week}: raw={len(obj)} scored={active_n}", flush=True)
            time.sleep(0.10)

    season_avail = {}
    for season in SEASONS:
        missing = sorted(required_weeks(season)-nonempty_weeks[season])
        season_avail[str(season)] = {
            "missing_required_weeks":missing,
            "scored_player_n":len(seasons[season]),
            "pass":not missing and bool(seasons[season]),
        }

    class_avail = {}
    for y in DRAFT_YEARS:
        req = [y,y+1,y+2]
        class_avail[str(y)] = {
            "required_seasons":req,
            "pass":all(season_avail[str(s)]["pass"] for s in req),
        }

    all_classes = all(class_avail[str(y)]["pass"] for y in DRAFT_YEARS)

    replacements = {}
    universe = []
    for season in SEASONS:
        by_pos = defaultdict(list)
        for sid, rec in seasons[season].items():
            g = int(rec["games"])
            total = float(rec["total"])
            ppg = total/g if g else 0.0
            row = {
                "season":season,"sleeper_id":sid,
                "name":player_index.get(sid,{}).get("name"),
                "position":rec["position"],"games":g,
                "season_total":round(total,8),"ppg":round(ppg,8),
            }
            universe.append(row)
            if g >= 3:
                by_pos[rec["position"]].append(row)

        replacements[season] = {}
        for pos in POSITIONS:
            eligible = sorted(by_pos[pos], key=lambda x:(-x["ppg"],x["sleeper_id"]))
            rank = ranks[pos]
            if len(eligible) < rank:
                raise GateError(f"{season} {pos}: replacement rank unsupported")
            a = eligible[rank-1]
            replacements[season][pos] = {
                "rank":rank,
                "replacement_ppg":float(a["ppg"]),
                "anchor_sleeper_id":a["sleeper_id"],
                "anchor_name":a["name"],
                "eligible_player_n":len(eligible),
            }

    with OUT_UNIVERSE.open("w",encoding="utf-8") as f:
        for row in sorted(universe,key=lambda x:(x["season"],x["position"],-x["ppg"],x["sleeper_id"])):
            f.write(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n")

    targets = {}
    for (draft_year,sid), meta in sorted(target_rows.items()):
        pos = meta.get("position")
        birth = meta.get("birth_date")
        flags = []
        if pos not in POSITIONS:
            flags.append("missing_supported_position")
        if not birth:
            flags.append("missing_birth_date")
        if not class_avail[str(draft_year)]["pass"]:
            flags.append("class_required_season_unavailable")

        annual = []
        for season in range(draft_year, min(draft_year+4, 2026)):
            if pos not in POSITIONS:
                annual.append({"season":season,"status":"position_unavailable"})
                continue
            repl = replacements[season][pos]
            rec = seasons[season].get(sid)
            games = int(rec["games"]) if rec else 0
            total = float(rec["total"]) if rec else 0.0
            denom = float(repl["replacement_ppg"])*sched_games(season)
            if denom <= 0:
                raise GateError(f"{season} {pos}: nonpositive replacement denominator")
            realized = (
                float(prod["zero_games_override"])
                if games == 0
                else clamp(
                    float(prod["intercept"]) + float(prod["slope"])*(total/denom),
                    float(prod["floor"]), float(prod["ceiling"])
                )
            )
            age = age_mult = annual_fv = None
            if birth:
                age = age_sep1(birth,season)
                age_mult = float(age_mod.age_multiplier(
                    pos,age,"Starter",realized,realized,age_cfg
                ))
                annual_fv = 5500.0*pos_weight[pos]*age_mult*realized
            annual.append({
                "season":season,"games":games,"season_total":round(total,8),
                "replacement_rank":repl["rank"],
                "replacement_ppg":round(float(repl["replacement_ppg"]),8),
                "scheduled_games":sched_games(season),
                "annual_surplus_o1":round(max(0.0,total-denom),8),
                "realized_prod_mult":round(realized,10),
                "age_on_sep1":age,
                "age_multiplier":round(age_mult,10) if age_mult is not None else None,
                "annual_player_equivalent_fv":round(annual_fv,8) if annual_fv is not None else None,
            })

        def horizon(n):
            rows = [x for x in annual if draft_year <= x["season"] < draft_year+n]
            if len(rows) != n:
                return {"horizon_years":n,"mature":False,"O1":None,"O2":None}
            o1 = all(x.get("annual_surplus_o1") is not None for x in rows)
            o2 = all(x.get("annual_player_equivalent_fv") is not None for x in rows)
            return {
                "horizon_years":n,"mature":True,
                "O1":round(sum(x["annual_surplus_o1"] for x in rows),8) if o1 else None,
                "O2":round(sum(x["annual_player_equivalent_fv"] for x in rows)/n,8) if o2 else None,
            }

        h2,h3,h4 = horizon(2),horizon(3),horizon(4)
        targets[(draft_year,sid)] = {
            **meta,"draft_year":draft_year,"status_flags":flags,
            "annual":annual,"H2":h2,"H3":h3,"H4":h4,
            "primary_o1_ready":class_avail[str(draft_year)]["pass"] and h3["O1"] is not None,
            "primary_o2_ready":class_avail[str(draft_year)]["pass"] and not flags and h3["O2"] is not None,
        }

    dev_rows,val_rows = [],[]
    cy = defaultdict(lambda:{"n":0,"sid":0,"o1":0,"o2":0})
    sp = defaultdict(lambda:{"n":0,"sid":0,"o1":0,"o2":0})

    for row in picks:
        y = int(row["draft_year"])
        sid = str(row.get("sleeper_id") or "").strip()
        out = targets.get((y,sid)) if sid else None
        split = row["split"]
        cell = row["cell"]
        o1 = bool(out and out["primary_o1_ready"])
        o2 = bool(out and out["primary_o2_ready"])
        cy[(y,cell)]["n"] += 1
        sp[split]["n"] += 1
        if sid:
            cy[(y,cell)]["sid"] += 1
            sp[split]["sid"] += 1
        if o1:
            cy[(y,cell)]["o1"] += 1
            sp[split]["o1"] += 1
        if o2:
            cy[(y,cell)]["o2"] += 1
            sp[split]["o2"] += 1

        rec = {
            "draft_year":y,"league_id":str(row["league_id"]),
            "league_idp":bool(row.get("league_idp",False)),
            "overall_slot":int(row["overall_slot"]),
            "round":int(row["round"]),
            "within_round_pick":int(row["within_round_pick"]),
            "tier":row["tier"],"cell":cell,"split":split,
            "mfl_player_id":row.get("mfl_player_id"),
            "gsis_id":row.get("gsis_id"),"sleeper_id":sid or None,
            "stable_player_key":row.get("stable_player_key"),
            "name":row.get("name"),
            "position":out.get("position") if out else norm_pos(row.get("position")),
            "cell_weight_v5_1":row["cell_weight_v5_1"],
            "source_weight_r1_r2_v5_1":row["source_weight_r1_r2_v5_1"],
            "primary_o1_ready":o1,"primary_o2_ready":o2,
            "birth_date":out.get("birth_date") if out else None,
            "status_flags":out.get("status_flags") if out else ["missing_sleeper_identity"],
            "H2":out.get("H2") if out else None,
            "H3":out.get("H3") if out else None,
            "H4":out.get("H4") if out else None,
            "annual":out.get("annual") if out else None,
        }
        (dev_rows if split=="development" else val_rows).append(rec)

    def write(path, rows):
        rows.sort(key=lambda x:(x["draft_year"],int(x["league_id"]),x["overall_slot"]))
        with Path(path).open("w",encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n")

    write(OUT_DEV,dev_rows)
    write(OUT_VAL,val_rows)

    by_cell = {}
    gate = all_classes
    for y in DRAFT_YEARS:
        for cell in CELLS:
            d = cy[(y,cell)]
            o2c = d["o2"]/d["n"] if d["n"] else 0
            g = o2c >= MIN_READY
            gate = gate and g
            by_cell[f"{y}:{cell}"] = {
                "retained_occurrence_n":d["n"],
                "sleeper_identity_ready_n":d["sid"],
                "primary_o1_ready_n":d["o1"],
                "primary_o2_ready_n":d["o2"],
                "primary_o2_ready_coverage":o2c,
                "minimum_required":MIN_READY,"pass":g,
            }

    by_split = {}
    for split in ("development","locked_validation"):
        d = sp[split]
        by_split[split] = {
            "retained_occurrence_n":d["n"],
            "sleeper_identity_coverage":d["sid"]/d["n"],
            "primary_o1_ready_coverage":d["o1"]/d["n"],
            "primary_o2_ready_coverage":d["o2"]/d["n"],
        }
        gate = gate and by_split[split]["primary_o2_ready_coverage"] >= MIN_READY

    decision = (
        "PASS_V5_PHASE3_HISTORICAL_OUTCOME_HARVEST_DEVELOPMENT_FIT_AUTHORIZED_NEXT_STAGE"
        if gate else
        "STOP_V5_PHASE3_OUTCOME_AVAILABILITY_OR_COMPLETENESS_GATE"
    )
    generated = now()

    source = {
        "schema_version":1,"stage":"phase3_historical_outcome_harvest",
        "generated_at_utc":generated,
        "provider":"Sleeper historical weekly NFL stats",
        "player_index":{**player_meta,"parsed_player_n":len(player_index)},
        "weekly_endpoints":endpoint_meta,
        "season_availability":season_avail,
        "class_availability":class_avail,
        "replacement_baselines":{str(s):replacements[s] for s in SEASONS},
        "scoring_source":str(SCORE_PATH.relative_to(ROOT)),
        "scoring_source_sha256":sha(SCORE_PATH),
        "age_multiplier_source":str(AGE_PATH.relative_to(ROOT)),
        "age_multiplier_source_sha256":sha(AGE_PATH),
        "candidate_fit_performed":False,"validation_scored":False,
        "production_change_authorized":False,
    }
    OUT_SOURCE.write_text(json.dumps(source,indent=2,sort_keys=True)+"\n")

    summary = {
        "schema_version":1,"stage":"phase3_historical_outcome_harvest",
        "status":"HISTORICAL_OUTCOME_HARVEST_PASS" if gate else "HISTORICAL_OUTCOME_HARVEST_STOP",
        "generated_at_utc":generated,"decision":decision,
        "research_only":True,
        "historical_player_outcomes_read":True,
        "historical_outcomes_harvested":True,
        "candidate_fit_performed":False,
        "candidate_scores_computed":False,
        "validation_scored":False,
        "validation_cell_outcome_aggregates_computed":False,
        "candidate_selection_performed":False,
        "market_or_ktc_values_read":False,
        "package_vote_data_read":False,
        "production_change_authorized":False,
        "source_population_changed":False,
        "source_search_performed":False,
        "retained_pick_occurrence_n":len(picks),
        "development_occurrence_n":len(dev_rows),
        "locked_validation_occurrence_n":len(val_rows),
        "unique_outcome_identity_n":len(targets),
        "all_six_primary_classes_available":all_classes,
        "season_availability":season_avail,
        "class_availability":class_avail,
        "outcome_readiness_gate":{
            "pass":gate,"minimum_primary_o2_occurrence_coverage":MIN_READY,
            "by_year_cell":by_cell,"by_split":by_split,
        },
        "locked_validation_firewall":{
            "development_outcomes_file":OUT_DEV.name,
            "validation_outcomes_file":OUT_VAL.name,
            "files_physically_separate":True,
            "validation_scored":False,
            "validation_aggregates_reported":False,
            "next_development_fit_workflow_must_not_read":OUT_VAL.name,
        },
        "next_stage_authorized":gate,
        "next_stage":"draft-pick-fv-v5-phase4-development-candidate-fit" if gate else None,
        "input_hashes":{
            PREREG.name:sha(PREREG),PICKS.name:sha(PICKS),CAT.name:sha(CAT),
            P21_SUM.name:sha(P21_SUM),P21_MAN.name:sha(P21_MAN),
            SCORE_PATH.name:sha(SCORE_PATH),AGE_PATH.name:sha(AGE_PATH),
        },
        "source_manifest_sha256":sha(OUT_SOURCE),
    }
    OUT_SUM.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")

    md = [
        "# Draft Pick FV V5 — Phase 3 Historical Outcome Harvest","",
        f"**Decision:** `{decision}`","",
        f"- Retained occurrences: **{len(picks)}**",
        f"- Development occurrences: **{len(dev_rows)}**",
        f"- Locked-validation occurrences: **{len(val_rows)}**",
        f"- Unique outcome identities: **{len(targets)}**",
        f"- Development O2-ready coverage: **{by_split['development']['primary_o2_ready_coverage']:.2%}**",
        f"- Locked-validation O2-ready coverage: **{by_split['locked_validation']['primary_o2_ready_coverage']:.2%}**","",
        "## Firewall","",
        "- Historical outcomes harvested: **Yes**",
        "- Candidate fitting performed: **No**",
        "- Validation scoring performed: **No**",
        "- Validation aggregates reported: **No**",
        "- Development and validation files separated: **Yes**",
        "- KTC/market values read: **No**",
        "- Package-vote evidence read: **No**",
        "- Production change authorized: **No**","",
        "## Next step","",
        (
            "Fit C1/C2/C3 using only the development outcome file. "
            "The Phase-4 fit workflow must be mechanically forbidden "
            "from reading the locked-validation file."
            if gate else
            "Stop before candidate fitting and diagnose outcome availability."
        ),""
    ]
    OUT_MD.write_text("\n".join(md),encoding="utf-8")

    man = {
        "schema_version":1,"stage":"phase3_historical_outcome_harvest",
        "status":summary["status"],"generated_at_utc":generated,
        "decision":decision,"historical_player_outcomes_read":True,
        "candidate_fit_performed":False,"validation_scored":False,
        "candidate_selection_performed":False,
        "production_change_authorized":False,
        "outcome_readiness_gate_pass":gate,
        "development_fit_authorized_next_stage":gate,
        "input_hashes":summary["input_hashes"],
        "output_hashes":{
            OUT_SOURCE.name:sha(OUT_SOURCE),OUT_UNIVERSE.name:sha(OUT_UNIVERSE),
            OUT_DEV.name:sha(OUT_DEV),OUT_VAL.name:sha(OUT_VAL),
            OUT_SUM.name:sha(OUT_SUM),OUT_MD.name:sha(OUT_MD),
        },
    }
    OUT_MAN.write_text(json.dumps(man,indent=2,sort_keys=True)+"\n")

    print(f"DECISION={decision}")
    print(f"development={len(dev_rows)} validation={len(val_rows)}")
    print(
        "O2 ready: dev="
        f"{by_split['development']['primary_o2_ready_coverage']:.2%} "
        "val="
        f"{by_split['locked_validation']['primary_o2_ready_coverage']:.2%}"
    )

if __name__ == "__main__":
    main()
