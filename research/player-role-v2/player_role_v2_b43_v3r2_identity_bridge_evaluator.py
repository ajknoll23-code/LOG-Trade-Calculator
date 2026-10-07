#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import requests

SUPPORTED_MODEL_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DL", "LB", "DB"}
MISSING = {"", "na", "nan", "none", "null", "n/a"}
SUFFIX_TOKENS = {"jr", "sr", "ii", "iii", "iv", "v"}
REFERENCE_MIN_COMPARISONS = 500
MIN_COMBINED_CURRENT_ELIGIBLE_COVERAGE = 0.995
EXPECTED_STABLE_CROSSWALK_SHA256 = "de241875e4ae91d43bbc7fbff682521da2abc9535028f952a35cb3305106c0a5"
EXPECTED_B41I_SHA256 = "d531dcff2d3ff681f02210d314f6e9f16c671c0beefa85fd311a55363675d4cc"
EXPECTED_B42_ELIGIBILITY_SHA256 = "fb1e12405eec27cf8d512f1abcbba58232d8957b84e6c515ac4025382c218f34"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def clean(value) -> str:
    x = str(value if value is not None else "").strip()
    return "" if x.casefold() in MISSING else x


def parse_numeric_id(value) -> str | None:
    x = clean(value)
    if not x:
        return None
    if re.fullmatch(r"\d+\.0+", x):
        x = x.split(".", 1)[0]
    return x if re.fullmatch(r"\d+", x) else None


def canonical_name(value) -> str:
    x = clean(value)
    if not x:
        return ""
    x = unicodedata.normalize("NFKD", x)
    x = "".join(ch for ch in x if not unicodedata.combining(ch))
    x = x.casefold()
    x = re.sub(r"[^a-z0-9]+", " ", x)
    tokens = [t for t in x.split() if t]
    while tokens and tokens[-1] in SUFFIX_TOKENS:
        tokens.pop()
    # Join consecutive single-letter initials so A. J. and AJ normalize alike.
    out=[]
    i=0
    while i < len(tokens):
        if len(tokens[i]) == 1:
            j=i
            initials=[]
            while j < len(tokens) and len(tokens[j]) == 1:
                initials.append(tokens[j]); j += 1
            if len(initials) >= 2:
                out.append("".join(initials)); i=j; continue
        out.append(tokens[i]); i += 1
    return " ".join(out)


def position_family(value) -> str:
    p = clean(value).upper()
    if p == "QB":
        return "QB"
    if p in {"RB", "HB", "FB"}:
        return "RB"
    if p == "WR":
        return "WR"
    if p == "TE":
        return "TE"
    if p in {"K", "PK"}:
        return "K"
    if p in {"DL", "DE", "DT", "NT", "ED", "EDGE", "LB", "ILB", "OLB"}:
        return "FRONT7"
    if p in {"DB", "CB", "S", "FS", "SS"}:
        return "DB"
    return ""


def row_name(row: dict) -> str:
    return clean(row.get("display_name")) or clean(row.get("full_name")) or clean(row.get("football_name"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def source_get(session: requests.Session, url: str) -> bytes:
    last=None
    for attempt in range(4):
        try:
            r=session.get(url, timeout=45)
            r.raise_for_status()
            return r.content
        except Exception as e:
            last=e
            if attempt < 3:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"B43_V3R2_SOURCE_FETCH_FAILED url={url} error={last}")


def load_csv_bytes(data: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


def load_crosswalk_bytes(data: bytes):
    rows=load_csv_bytes(data)
    if not rows or not {"gsis_id","sleeper_id"}.issubset(rows[0]):
        raise RuntimeError("B43_V3R2_CROSSWALK_SCHEMA")
    exact={}
    inverse={}
    missing_gsis=0
    for row in rows:
        sid=parse_numeric_id(row.get("sleeper_id"))
        g=clean(row.get("gsis_id"))
        if sid and not g:
            missing_gsis += 1
        if not sid or not g:
            continue
        if g in exact and exact[g] != sid:
            raise RuntimeError(f"B43_V3R2_AMBIGUOUS_GSIS_CROSSWALK gsis={g}")
        if sid in inverse and inverse[sid] != g:
            raise RuntimeError(f"B43_V3R2_AMBIGUOUS_SLEEPER_CROSSWALK sleeper={sid}")
        exact[g]=sid
        inverse[sid]=g
    return exact,inverse,{"exact_pair_count":len(exact),"rows_with_sleeper_id_but_missing_gsis":missing_gsis}


def load_b41i(path: Path):
    if sha256_file(path) != EXPECTED_B41I_SHA256:
        raise RuntimeError("B43_V3R2_B41I_SHA_DRIFT")
    rows=list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    if not rows:
        raise RuntimeError("B43_V3R2_B41I_EMPTY")
    required={"gsis_id","espn_id","position","birth_date"}
    missing=required-set(rows[0])
    if missing:
        raise RuntimeError(f"B43_V3R2_B41I_REQUIRED_COLUMNS_MISSING {sorted(missing)}")
    by_gsis={}
    for r in rows:
        g=clean(r.get("gsis_id"))
        if not g:
            continue
        if g in by_gsis:
            raise RuntimeError(f"B43_V3R2_DUPLICATE_B41I_GSIS {g}")
        by_gsis[g]={
            "gsis_id":g,
            "espn_id":parse_numeric_id(r.get("espn_id")),
            "name":row_name(r),
            "name_key":canonical_name(row_name(r)),
            "position_family":position_family(r.get("position") or r.get("position_group")),
            "birth_date":clean(r.get("birth_date")),
        }
    return by_gsis, rows[0].keys()


def load_current(base: Path, b41i_by_gsis: dict):
    p=base/"player_role_v2_b42_v4_role_eligibility.csv"
    if sha256_file(p) != EXPECTED_B42_ELIGIBILITY_SHA256:
        raise RuntimeError("B43_V3R2_B42_ELIGIBILITY_SHA_DRIFT")
    rows=list(csv.DictReader(p.open(encoding="utf-8-sig", newline="")))
    current=[]
    for r in rows:
        g=clean(r.get("gsis_id"))
        model_pos=clean(r.get("position"))
        if not g or model_pos not in SUPPORTED_MODEL_POSITIONS:
            continue
        meta=b41i_by_gsis.get(g,{})
        name=clean(r.get("player_name")) or clean(meta.get("name"))
        current.append({
            "gsis_id":g,
            "player_name":name,
            "name_key":canonical_name(name),
            "model_position":model_pos,
            "position_family":position_family(model_pos),
            "espn_id":meta.get("espn_id"),
            "birth_date":clean(meta.get("birth_date")),
        })
    if len({x["gsis_id"] for x in current}) != len(current):
        raise RuntimeError("B43_V3R2_DUPLICATE_CURRENT_GSIS")
    return current


def sleeper_records_from_payload(data: bytes):
    raw=json.loads(data.decode("utf-8"))
    if not isinstance(raw,dict):
        raise RuntimeError("B43_V3R2_SLEEPER_PAYLOAD_NOT_OBJECT")
    records=[]
    for key,obj in raw.items():
        if not isinstance(obj,dict):
            continue
        sid=parse_numeric_id(obj.get("player_id")) or parse_numeric_id(key)
        espn=parse_numeric_id(obj.get("espn_id"))
        pos=position_family(obj.get("position"))
        full=clean(obj.get("full_name"))
        if not full:
            full=" ".join(x for x in [clean(obj.get("first_name")),clean(obj.get("last_name"))] if x).strip()
        if not sid or not pos:
            continue
        records.append({
            "sleeper_id":sid,
            "espn_id":espn,
            "full_name":full,
            "name_key":canonical_name(full),
            "position":clean(obj.get("position")),
            "position_family":pos,
            "birth_date":clean(obj.get("birth_date")),
            "nfl_team":clean(obj.get("team")).upper(),
            "status":clean(obj.get("status")),
        })
    return raw,records


def candidate_by_espn(row: dict, sleeper_by_espn: dict[str,list[dict]]):
    eid=row.get("espn_id")
    if not eid:
        return None
    # External-ID ambiguity fails closed before any name/position filtering.
    raw=sleeper_by_espn.get(eid,[])
    if len(raw) != 1:
        return None
    x=raw[0]
    # Exact external ID is necessary but not sufficient: require identity-shape agreement.
    if x["position_family"] != row["position_family"] or x["name_key"] != row["name_key"]:
        return None
    # Frozen B43-lineage safeguard: a positive DOB contradiction is a hard veto.
    row_bd=clean(row.get("birth_date"))
    sleeper_bd=clean(x.get("birth_date"))
    if row_bd and sleeper_bd and row_bd != sleeper_bd:
        return None
    return x


def stale_alias_supersession_safe(current_row: dict, old_gsis: str, current_gsis_set: set[str], b41i_by_gsis: dict) -> bool:
    # General, prospective stale-alias rule: old claimant cannot itself be in the
    # frozen current eligible population, and both GSIS rows must independently
    # point to the same exact ESPN ID, canonical name, and position family.
    if old_gsis in current_gsis_set:
        return False
    old=b41i_by_gsis.get(old_gsis)
    new=b41i_by_gsis.get(current_row["gsis_id"])
    if not old or not new:
        return False
    if not old.get("espn_id") or not new.get("espn_id"):
        return False
    old_bd=clean(old.get("birth_date"))
    new_bd=clean(new.get("birth_date"))
    if old_bd and new_bd and old_bd != new_bd:
        return False
    return bool(
        old["espn_id"] == new["espn_id"] == current_row.get("espn_id")
        and old["name_key"]
        and old["name_key"] == new["name_key"] == current_row["name_key"]
        and old["position_family"]
        and old["position_family"] == new["position_family"] == current_row["position_family"]
    )


def protocol_payload() -> dict:
    return {
        "schema_version":1,
        "study_id":"player-role-v2",
        "phase":"B43-v3-exact-espn-id-source-extension-and-stale-alias-adjudication",
        "status":"FROZEN_BEFORE_B43_V3R2_IDENTITY_RESULTS",
        "motivation":(
            "B43 V2R1 reached a valid scientific STOP after two target-population stable-pair collisions disqualified DOB_POSITION. "
            "The next study uses an exact cross-platform identifier exposed by both frozen nflverse identity data and a newly frozen Sleeper map, rather than another fuzzy name/DOB rule."
        ),
        "scientific_boundary":{
            "B42_and_B43_V1_and_B43_V2R1_results_are_prior_observed_evidence":True,
            "B43_V3R2_is_post_stop_remediation_not_independent_confirmation":True,
            "B43_may_not_parse_or_use_league_rosters":True,
            "B43_may_not_use_owner_identity_or_fantasy_roster_partition":True,
            "player_specific_exceptions_allowed":False,
            "role_model_or_tier_changes_allowed":False,
            "B42_or_B43_miss_lists_may_not_be_hard_coded":True,
        },
        "sources":{
            "current_population":"exact frozen B42 V4 owner-blind role-eligibility artifact",
            "nflverse_identity":"exact frozen B41I players.csv snapshot; espn_id is the external identifier",
            "reference_pairs":"B41G-pinned DynastyProcess GSIS<->Sleeper crosswalk, used only as known-pair truth and inverse-conflict evidence",
            "candidate_sleeper_identity_source":"newly frozen https://api.sleeper.app/v1/players/nfl bytes; espn_id is the external identifier",
        },
        "matching_rule":(
            "ESPN_ID_EXACT: exact nonmissing normalized espn_id between frozen nflverse row and Sleeper row, exactly one Sleeper candidate, "
            "plus exact canonical-name agreement and compatible position family; duplicated Sleeper ESPN IDs fail closed before filtering; conflicting nonmissing birth dates veto the match"
        ),
        "dob_contradiction_veto":True,
        "duplicate_sleeper_espn_id_policy":"Any ESPN ID represented by more than one Sleeper record is ambiguous and cannot produce a candidate, even if filtering would leave one name/position match.",
        "position_compatibility":"QB exact; RB/HB/FB -> RB; WR exact; TE exact; K/PK -> K; DL/DE/DT/NT/ED/EDGE/LB/ILB/OLB -> FRONT7; DB/CB/S/FS/SS -> DB",
        "stale_alias_adjudication":{
            "specified_after_B43_V2R1_observed_two_collision_conflicts":True,
            "may_override_historical_stable_inverse_claim":True,
            "requirements":[
                "old stable claimant is not in frozen B42 current-eligible population",
                "old and current GSIS rows both exist in frozen B41I snapshot",
                "old and current GSIS rows share the same exact nonmissing ESPN ID",
                "old and current GSIS rows share the same canonical name",
                "old and current GSIS rows share the same compatible position family",
                "Sleeper ESPN ID has exactly one raw record before any name/position filtering",
                "Sleeper candidate matches canonical name and compatible position family",
                "no conflicting nonmissing birth date exists between current nflverse and Sleeper records",
                "no conflicting nonmissing birth date exists between old and current B41I GSIS records",
            ],
            "historical_stable_crosswalk_is_not_mutated":True,
            "supersession_applies_only_to_current_bridge_overlay":True,
        },
        "validation_design":{
            "reference_pairs_are_not_used_to_generate_candidate_features":True,
            "exact_espn_rule_must_have_at_least_500_known_pair_comparisons":True,
            "exact_espn_rule_must_have_zero_known_pair_conflicts":True,
            "current_current_sleeper_collisions_are_never_adjudicated_as_aliases":True,
            "unadjudicated_stable_inverse_collisions_fail_the_study":True,
            "dob_contradiction_veto_is_preserved_from_B43_V1R1":True,
            "known_pair_birth_date_agreement_is_descriptive_not_a_gate":True,
        },
        "primary_gates":{
            "minimum_exact_espn_reference_comparisons":REFERENCE_MIN_COMPARISONS,
            "exact_espn_reference_conflicts_allowed":0,
            "unadjudicated_identity_conflicts_allowed":0,
            "minimum_base_plus_supplemental_current_eligible_coverage":MIN_COMBINED_CURRENT_ELIGIBLE_COVERAGE,
            "minimum_supplemental_mapping_count":1,
        },
        "production_firewall":{
            "B43_authorizes_production_change":False,
            "B43_deploys_model":False,
            "B44_owner_blind_reaudit_required_after_B43_pass":True,
            "B44_must_preserve_original_98pct_min_team_coverage_and_2pp_range_gates":True,
        },
    }


def run_selftest():
    assert canonical_name("Generic Player Jr.") == "generic player"
    assert canonical_name("A. J. Example") == canonical_name("AJ Example")
    assert parse_numeric_id("1234.0") == "1234"
    assert parse_numeric_id("NA") is None
    sleepers={"42":[{"sleeper_id":"7","espn_id":"42","full_name":"A.J. Example","name_key":"aj example","position":"CB","position_family":"DB","birth_date":"2001-02-03","nfl_team":"ARI","status":"Active"}]}
    row={"gsis_id":"GNEW","player_name":"AJ Example","name_key":"aj example","model_position":"DB","position_family":"DB","espn_id":"42","birth_date":"2001-02-03"}
    assert candidate_by_espn(row,sleepers)["sleeper_id"]=="7"
    duplicate_espn={"42":[
        {"sleeper_id":"7","espn_id":"42","full_name":"A.J. Example","name_key":"aj example","position":"CB","position_family":"DB","birth_date":"2001-02-03","nfl_team":"ARI","status":"Active"},
        {"sleeper_id":"8","espn_id":"42","full_name":"Different Person","name_key":"different person","position":"WR","position_family":"WR","birth_date":"1999-01-01","nfl_team":"ARI","status":"Inactive"},
    ]}
    assert candidate_by_espn(row,duplicate_espn) is None, "Duplicate raw Sleeper ESPN ID must fail closed before filtering"
    dob_conflict={"42":[{"sleeper_id":"7","espn_id":"42","full_name":"A.J. Example","name_key":"aj example","position":"CB","position_family":"DB","birth_date":"1998-09-09","nfl_team":"ARI","status":"Active"}]}
    assert candidate_by_espn(row,dob_conflict) is None, "Conflicting known DOB must veto ESPN-ID candidate"
    dup={
        "GNEW":{"gsis_id":"GNEW","espn_id":"42","name":"AJ Example","name_key":"aj example","position_family":"DB","birth_date":"2001-02-03"},
        "GOLD":{"gsis_id":"GOLD","espn_id":"42","name":"A. J. Example Jr.","name_key":"aj example","position_family":"DB","birth_date":"2001-02-03"},
        "GBAD":{"gsis_id":"GBAD","espn_id":"99","name":"AJ Example","name_key":"aj example","position_family":"DB","birth_date":"2001-02-03"},
        "GDOB":{"gsis_id":"GDOB","espn_id":"42","name":"AJ Example","name_key":"aj example","position_family":"DB","birth_date":"1990-01-01"},
    }
    assert stale_alias_supersession_safe(row,"GOLD",{"GNEW"},dup) is True
    assert stale_alias_supersession_safe(row,"GOLD",{"GNEW","GOLD"},dup) is False
    assert stale_alias_supersession_safe(row,"GBAD",{"GNEW"},dup) is False
    assert stale_alias_supersession_safe(row,"GDOB",{"GNEW"},dup) is False, "Conflicting old/current B41I DOB must veto stale-alias supersession"
    sample=b"gsis_id,sleeper_id\nNA,100\n,101\nG1,102\n"
    exact,inv,audit=load_crosswalk_bytes(sample)
    assert exact=={"G1":"102"} and inv=={"102":"G1"} and audit["rows_with_sleeper_id_but_missing_gsis"]==2
    print("PASS B43 V3R2 evaluator self-test")


def source_preflight(repo: Path, out: Path, session: requests.Session):
    base=repo/"research/player-role-v2"
    # Frozen local source integrity only; no target association is computed here.
    b41i=base/"frozen_inputs/players_b41i_snapshot.csv"
    if sha256_file(b41i)!=EXPECTED_B41I_SHA256:
        raise RuntimeError("B43_V3R2_B41I_SHA_DRIFT")
    with b41i.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.reader(f)
        header=next(reader,None)
    if not header or not {"gsis_id","espn_id","position","birth_date"}.issubset(set(header)):
        raise RuntimeError("B43_V3R2_B41I_ESPN_SCHEMA_MISSING")

    prereg=json.loads((base/"player_role_v2_b41g_holdout_validation_preregistration.json").read_text())
    commit=prereg["frozen_inputs"]["stable_id_crosswalk_commit"]
    cross_url=f"https://raw.githubusercontent.com/dynastyprocess/data/{commit}/files/db_playerids.csv"
    cross_bytes=source_get(session,cross_url)
    if sha256_bytes(cross_bytes)!=EXPECTED_STABLE_CROSSWALK_SHA256:
        raise RuntimeError("B43_V3R2_STABLE_CROSSWALK_SHA_DRIFT")
    rows=load_csv_bytes(cross_bytes)
    if not rows or not {"gsis_id","sleeper_id"}.issubset(rows[0]):
        raise RuntimeError("B43_V3R2_CROSSWALK_SCHEMA")

    sleeper_bytes=source_get(session,"https://api.sleeper.app/v1/players/nfl")
    raw,records=sleeper_records_from_payload(sleeper_bytes)
    if len(raw)<5000 or len(records)<1000:
        raise RuntimeError(f"B43_V3R2_SLEEPER_MAP_TOO_SMALL raw={len(raw)} supported={len(records)}")
    # Schema-only availability check; no join to the B42 population here.
    espn_field_rows=sum(1 for v in raw.values() if isinstance(v,dict) and "espn_id" in v)
    if espn_field_rows<1000:
        raise RuntimeError(f"B43_V3R2_SLEEPER_ESPN_SCHEMA_TOO_SPARSE field_rows={espn_field_rows}")
    espn_counts=Counter(x["espn_id"] for x in records if x["espn_id"])
    duplicate_espn_id_count=sum(1 for _,count in espn_counts.items() if count>1)
    duplicate_espn_record_count=sum(count for _,count in espn_counts.items() if count>1)

    out.mkdir(parents=True,exist_ok=True)
    (out/"stable_crosswalk.csv").write_bytes(cross_bytes)
    (out/"sleeper_players.json").write_bytes(sleeper_bytes)
    write_json(out/"source_preflight.json",{
        "status":"PASS_SOURCE_SCHEMA_ONLY_NO_B43_V3R2_IDENTITY_RESULT_COMPUTED",
        "B43_V3R2_identity_mapping_metric_computed":False,
        "league_roster_source_used":False,
        "stable_crosswalk_sha256":sha256_bytes(cross_bytes),
        "sleeper_player_map_sha256":sha256_bytes(sleeper_bytes),
        "sleeper_raw_object_count":len(raw),
        "sleeper_supported_identity_row_count":len(records),
        "sleeper_rows_exposing_espn_id_field":espn_field_rows,
        "sleeper_duplicate_espn_id_count":duplicate_espn_id_count,
        "sleeper_records_on_duplicate_espn_ids":duplicate_espn_record_count,
        "b41i_snapshot_sha256":sha256_file(b41i),
    })


def run_evaluation(repo: Path, out: Path, source_cache: Path):
    base=repo/"research/player-role-v2"
    v2r1d=json.loads((base/"player_role_v2_b43_v2r1_scientific_decision.json").read_text())
    if v2r1d["result"]!="SCIENTIFIC_STOP_B43_V2R1_OWNER_BLIND_IDENTITY_BRIDGE_FEASIBILITY_FAILED":
        raise RuntimeError("B43_V3R2_PARENT_V2R1_DECISION_NOT_EXPECTED_STOP")
    if v2r1d["eligible_for_B44_owner_blind_reaudit"] is not False:
        raise RuntimeError("B43_V3R2_PARENT_V2R1_B44_STATE_UNEXPECTED")

    b41i_by_gsis,_=load_b41i(base/"frozen_inputs/players_b41i_snapshot.csv")
    current=load_current(base,b41i_by_gsis)
    if len(current)!=1398:
        raise RuntimeError(f"B43_V3R2_CURRENT_POPULATION_DRIFT count={len(current)}")
    current_set={x["gsis_id"] for x in current}

    cross_bytes=(source_cache/"stable_crosswalk.csv").read_bytes()
    sleeper_bytes=(source_cache/"sleeper_players.json").read_bytes()
    source_preflight_meta=json.loads((source_cache/"source_preflight.json").read_text())
    if sha256_bytes(cross_bytes)!=EXPECTED_STABLE_CROSSWALK_SHA256:
        raise RuntimeError("B43_V3R2_CACHED_CROSSWALK_SHA_DRIFT")
    if sha256_bytes(cross_bytes)!=source_preflight_meta.get("stable_crosswalk_sha256"):
        raise RuntimeError("B43_V3R2_CACHED_CROSSWALK_DIFFERS_FROM_PREFLIGHT")
    if sha256_bytes(sleeper_bytes)!=source_preflight_meta.get("sleeper_player_map_sha256"):
        raise RuntimeError("B43_V3R2_CACHED_SLEEPER_DIFFERS_FROM_PREFLIGHT")
    stable,stable_inverse,cross_audit=load_crosswalk_bytes(cross_bytes)
    raw_sleeper,sleeper_records=sleeper_records_from_payload(sleeper_bytes)
    sleeper_by_id={x["sleeper_id"]:x for x in sleeper_records}
    sleeper_by_espn=defaultdict(list)
    for x in sleeper_records:
        if x["espn_id"]:
            sleeper_by_espn[x["espn_id"]].append(x)
    duplicate_sleeper_espn_ids={e:v for e,v in sleeper_by_espn.items() if len(v)>1}

    # Rule validation on known current stable pairs. The stable pair is truth only;
    # it never contributes an ESPN feature or candidate.
    comparisons=conflicts=correct=0
    conflict_details=[]
    birth_date_comparable=birth_date_agree=birth_date_disagree=0
    for row in current:
        ref_sid=stable.get(row["gsis_id"])
        if not ref_sid or ref_sid not in sleeper_by_id:
            continue
        ref_record=sleeper_by_id[ref_sid]
        nfl_bd=clean(row.get("birth_date"))
        sleeper_bd=clean(ref_record.get("birth_date"))
        if nfl_bd and sleeper_bd:
            birth_date_comparable += 1
            if nfl_bd == sleeper_bd:
                birth_date_agree += 1
            else:
                birth_date_disagree += 1
        pred=candidate_by_espn(row,sleeper_by_espn)
        if not pred:
            continue
        comparisons += 1
        if pred["sleeper_id"]==ref_sid:
            correct += 1
        else:
            conflicts += 1
            conflict_details.append({"gsis_id":row["gsis_id"],"predicted_sleeper_id":pred["sleeper_id"],"reference_sleeper_id":ref_sid})

    rule_eligible=bool(comparisons>=REFERENCE_MIN_COMPARISONS and conflicts==0)

    provisional=[]
    unadjudicated=[]
    for row in current:
        g=row["gsis_id"]
        if g in stable:
            continue
        pred=candidate_by_espn(row,sleeper_by_espn)
        if not pred:
            continue
        provisional.append({
            "gsis_id":g,
            "sleeper_id":pred["sleeper_id"],
            "espn_id":row["espn_id"],
            "rule":"ESPN_ID_EXACT",
            "name_key":row["name_key"],
            "model_position":row["model_position"],
            "position_family":row["position_family"],
            "stable_conflict_gsis":"",
            "stale_alias_supersession":False,
        })

    # Any two current eligible GSIS rows trying to claim one Sleeper ID are ambiguous.
    sid_counts=Counter(x["sleeper_id"] for x in provisional)
    accepted=[]
    adjudicated_aliases=[]
    for x in provisional:
        if sid_counts[x["sleeper_id"]] != 1:
            unadjudicated.append({**x,"reason":"current_current_sleeper_collision"})
            continue
        old=stable_inverse.get(x["sleeper_id"])
        if old and old!=x["gsis_id"]:
            current_row=next(r for r in current if r["gsis_id"]==x["gsis_id"])
            if stale_alias_supersession_safe(current_row,old,current_set,b41i_by_gsis):
                y=dict(x)
                y["stable_conflict_gsis"]=old
                y["stale_alias_supersession"]=True
                accepted.append(y)
                adjudicated_aliases.append({"gsis_id":x["gsis_id"],"sleeper_id":x["sleeper_id"],"old_stable_gsis":old,"espn_id":x["espn_id"]})
            else:
                unadjudicated.append({**x,"reason":"stable_inverse_collision_not_safe_to_supersede","old_stable_gsis":old})
            continue
        accepted.append(x)

    # Fail closed if the rule itself did not validate. We still report the prospective
    # proposal set, but no mapping may count toward the bridge if the rule is ineligible.
    if not rule_eligible:
        accepted=[]
        adjudicated_aliases=[]

    # Structural current-bridge invariants.
    if len({x["gsis_id"] for x in accepted}) != len(accepted):
        raise RuntimeError("B43_V3R2_ACCEPTED_GSIS_NOT_ONE_TO_ONE")
    if len({x["sleeper_id"] for x in accepted}) != len(accepted):
        raise RuntimeError("B43_V3R2_ACCEPTED_SLEEPER_NOT_ONE_TO_ONE")
    for x in accepted:
        old=stable_inverse.get(x["sleeper_id"])
        if old and old!=x["gsis_id"] and not x["stale_alias_supersession"]:
            raise RuntimeError("B43_V3R2_UNADJUDICATED_STABLE_CONFLICT_ENTERED_BRIDGE")

    base_mapped=sum(1 for x in current if x["gsis_id"] in stable)
    accepted_gsis={x["gsis_id"] for x in accepted}
    combined=sum(1 for x in current if x["gsis_id"] in stable or x["gsis_id"] in accepted_gsis)
    coverage=combined/len(current)

    gates={
        "no_roster_or_owner_context":True,
        "minimum_exact_espn_reference_comparisons":comparisons>=REFERENCE_MIN_COMPARISONS,
        "zero_exact_espn_reference_conflicts":conflicts==0,
        "exact_espn_rule_independently_validated":rule_eligible,
        "zero_unadjudicated_identity_conflicts":len(unadjudicated)==0,
        "minimum_base_plus_supplemental_current_eligible_coverage":coverage>=MIN_COMBINED_CURRENT_ELIGIBLE_COVERAGE,
        "minimum_supplemental_mapping_count":len(accepted)>=1,
    }
    all_pass=all(gates.values())

    out.mkdir(parents=True,exist_ok=True)
    snap=out/"player_role_v2_b43_v3r2_sleeper_espn_identity_snapshot.csv"
    with snap.open("w",newline="",encoding="utf-8") as f:
        fields=["sleeper_id","espn_id","full_name","name_key","position","position_family","birth_date","nfl_team","status"]
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for x in sorted(sleeper_records,key=lambda z:(int(z["sleeper_id"]),z["name_key"])):
            w.writerow({k:x.get(k,"") or "" for k in fields})

    bridge=out/"player_role_v2_b43_v3r2_identity_bridge.csv"
    with bridge.open("w",newline="",encoding="utf-8") as f:
        fields=["gsis_id","sleeper_id","espn_id","rule","name_key","model_position","position_family","stable_conflict_gsis","stale_alias_supersession"]
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for x in sorted(accepted,key=lambda z:z["gsis_id"]):
            w.writerow({k:x.get(k,"") for k in fields})

    evidence={
        "schema_version":1,
        "study_id":"player-role-v2",
        "phase":"B43-v3-exact-espn-id-source-extension-and-stale-alias-adjudication",
        "result":"PASS_B43_V3R2_EXACT_ESPN_ID_BRIDGE_FROZEN_FOR_B44_REAUDIT" if all_pass else "SCIENTIFIC_STOP_B43_V3R2_EXACT_ESPN_ID_BRIDGE_FAILED",
        "all_primary_gates_pass":all_pass,
        "primary_gates":gates,
        "thresholds":{
            "minimum_exact_espn_reference_comparisons":REFERENCE_MIN_COMPARISONS,
            "exact_espn_reference_conflicts_allowed":0,
            "unadjudicated_identity_conflicts_allowed":0,
            "minimum_base_plus_supplemental_current_eligible_coverage":MIN_COMBINED_CURRENT_ELIGIBLE_COVERAGE,
        },
        "reference_validation":{
            "rule":"ESPN_ID_EXACT",
            "comparisons":comparisons,
            "correct":correct,
            "conflicts":conflicts,
            "precision":correct/comparisons if comparisons else None,
            "eligible_for_supplemental_application":rule_eligible,
            "conflict_details":conflict_details,
            "birth_date_agreement_descriptive":{
                "comparable_known_pairs":birth_date_comparable,
                "agree":birth_date_agree,
                "disagree":birth_date_disagree,
                "agreement_rate":birth_date_agree/birth_date_comparable if birth_date_comparable else None,
                "used_as_primary_gate":False,
            },
        },
        "current_owner_blind_population":{
            "eligible_gsis_rows":len(current),
            "base_stable_mapping_count":base_mapped,
            "base_stable_mapping_coverage":base_mapped/len(current),
            "provisional_exact_espn_proposal_count":len(provisional),
            "supplemental_accepted_count":len(accepted),
            "stale_alias_supersession_count":len(adjudicated_aliases),
            "combined_mapped_count":combined,
            "combined_mapping_coverage":coverage,
            "unresolved_count":len(current)-combined,
        },
        "identity_conflict_adjudication":{
            "specified_after_B43_V2R1_observed_collision_conflicts":True,
            "adjudicated_stale_alias_count":len(adjudicated_aliases),
            "adjudicated_stale_aliases":adjudicated_aliases,
            "unadjudicated_conflict_count":len(unadjudicated),
            "unadjudicated_conflicts":unadjudicated,
        },
        "source_integrity":{
            "b41i_nfl_identity_snapshot_sha256":sha256_file(base/"frozen_inputs/players_b41i_snapshot.csv"),
            "b42_role_eligibility_sha256":sha256_file(base/"player_role_v2_b42_v4_role_eligibility.csv"),
            "stable_crosswalk_sha256":sha256_bytes(cross_bytes),
            "stable_crosswalk_audit":cross_audit,
            "sleeper_player_map_sha256":sha256_bytes(sleeper_bytes),
            "sleeper_raw_object_count":len(raw_sleeper),
            "sleeper_supported_identity_row_count":len(sleeper_records),
            "sleeper_duplicate_espn_id_count":len(duplicate_sleeper_espn_ids),
            "sleeper_records_on_duplicate_espn_ids":sum(len(v) for v in duplicate_sleeper_espn_ids.values()),
            "cached_sleeper_sha_matches_preflight":True,
            "sleeper_espn_snapshot_sha256":sha256_file(snap),
        },
        "accepted_bridge_structural_invariant":{
            "one_to_one_current_gsis_and_sleeper":True,
            "all_historical_stable_inverse_conflicts_explicitly_adjudicated":True,
        },
        "league_roster_source_used":False,
        "owner_identity_used":False,
        "fantasy_roster_partition_used":False,
        "player_specific_exception_count":0,
        "model_or_tier_retuning_performed":False,
        "production_change_authorized":False,
        "production_model_deployed":False,
        "B43_V3R2_is_post_stop_remediation_not_independent_confirmation":True,
        "dob_contradiction_veto":True,
        "duplicate_sleeper_espn_ids_fail_closed_before_filtering":True,
        "B44_owner_blind_reaudit_required_after_pass":True,
        "identity_bridge_sha256":sha256_file(bridge),
    }
    write_json(out/"player_role_v2_b43_v3r2_evidence.json",evidence)

    decision={
        "schema_version":1,
        "study_id":"player-role-v2",
        "phase":"B43-v3-scientific-decision",
        "result":evidence["result"],
        "all_primary_gates_pass":all_pass,
        "eligible_for_B44_owner_blind_reaudit":bool(all_pass),
        "combined_mapping_coverage":coverage,
        "supplemental_accepted_count":len(accepted),
        "stale_alias_supersession_count":len(adjudicated_aliases),
        "unadjudicated_identity_conflict_count":len(unadjudicated),
        "production_change_authorized":False,
        "production_model_deployed":False,
        "next_stage":(
            "If PASS, B44 must use this exact frozen V3R2 bridge and Sleeper ESPN snapshot as a current-identity overlay, preserve the original B42 98% minimum-team coverage / 2pp range gates, and remain a post-remediation acceptance re-audit. "
            "If STOP, preserve evidence and preregister a different identity-source study before any further team audit."
        ),
    }
    write_json(out/"player_role_v2_b43_v3r2_scientific_decision.json",decision)

    report=[
        "# Player Role V2 — B43 V3R2 Exact ESPN-ID Source Extension and Stale-Alias Adjudication",
        "",
        f"- Decision: **{evidence['result']}**",
        f"- Current owner-blind active eligible GSIS rows: **{len(current)}**",
        f"- Base stable mappings: **{base_mapped} ({base_mapped/len(current):.4f})**",
        f"- Exact ESPN known-pair comparisons: **{comparisons}**",
        f"- Exact ESPN known-pair conflicts: **{conflicts}**",
        f"- Known-pair DOB agreement (descriptive): **{birth_date_agree}/{birth_date_comparable}**; disagreements **{birth_date_disagree}**",
        f"- Sleeper ESPN IDs duplicated across raw supported records: **{len(duplicate_sleeper_espn_ids)}** (all fail closed)",
        f"- Exact ESPN proposals for previously unmapped current GSIS IDs: **{len(provisional)}**",
        f"- Accepted supplements: **{len(accepted)}**",
        f"- Adjudicated stale-alias supersessions: **{len(adjudicated_aliases)}**",
        f"- Unadjudicated identity conflicts: **{len(unadjudicated)}**",
        f"- Combined mapping coverage: **{coverage:.4f}**",
        f"- Minimum required combined coverage: **{MIN_COMBINED_CURRENT_ELIGIBLE_COVERAGE:.4f}**",
        "- League roster source used: **No**",
        "- Owner/fantasy-team context used: **No**",
        "- Player-specific exceptions: **0**",
        "- Model/tier retuning: **No**",
        "- Production authorized: **No**",
        "",
        "## Gate results",
        "",
    ]
    report += [f"- {k}: **{'PASS' if v else 'FAIL'}**" for k,v in gates.items()]
    report += [
        "",
        "## Interpretation",
        "",
        "B43 V3R2 is a disclosed post-stop identity-source extension. The sole mapping rule requires an exact ESPN ID exposed by both the frozen nflverse identity snapshot and the newly frozen Sleeper map, plus canonical-name and position-family agreement. Any duplicated Sleeper ESPN ID fails closed before filtering, and the frozen birth-date contradiction veto remains a hard safeguard.",
        "",
        "A historical stable inverse claim may be superseded only for the current bridge overlay when the old stable GSIS claimant is outside the frozen current-eligible population and the frozen nflverse snapshot shows the old and current GSIS IDs share the same exact nonmissing ESPN ID, canonical name, and position family, with no conflicting nonmissing birth date. The historical crosswalk itself is never rewritten.",
        "",
        "No B42/B43 missed-player names, GSIS IDs, Sleeper IDs, or per-player exceptions are encoded in the evaluator. B44 remains the actual post-remediation owner-blind acceptance re-audit under the unchanged 98% minimum-team-coverage and 2-percentage-point range gates.",
    ]
    (out/"player_role_v2_b43_v3r2_report.md").write_text("\n".join(report)+"\n",encoding="utf-8")
    return evidence


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",choices=["selftest","protocol","source-preflight","evaluate"],required=True)
    ap.add_argument("--repo",default=".")
    ap.add_argument("--out")
    ap.add_argument("--source-cache")
    args=ap.parse_args()
    if args.mode=="selftest":
        run_selftest(); return
    repo=Path(args.repo).resolve()
    if args.mode=="protocol":
        if not args.out: raise RuntimeError("--out required")
        write_json(Path(args.out),protocol_payload()); return
    if not args.out: raise RuntimeError("--out required")
    session=requests.Session(); session.headers.update({"User-Agent":"LOG-Trade-Calculator-player-role-v2-b43-v3r2"})
    if args.mode=="source-preflight":
        source_preflight(repo,Path(args.out),session); return
    if args.mode=="evaluate":
        if not args.source_cache: raise RuntimeError("--source-cache required")
        run_evaluation(repo,Path(args.out),Path(args.source_cache)); return

if __name__=="__main__":
    main()
