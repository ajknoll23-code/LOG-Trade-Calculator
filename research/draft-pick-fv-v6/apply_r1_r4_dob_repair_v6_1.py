#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, hashlib, importlib.util, json, math, re, time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
import requests

ROOT=Path.cwd(); V5=ROOT/"research/draft-pick-fv-v5"; V6=ROOT/"research/draft-pick-fv-v6"
PROTOCOL=V6/"r1_r4_dob_repair_protocol_v6_1.json"
PROTOCOL_MAN=V6/"r1_r4_dob_repair_protocol_manifest_v6_1.json"
IN_OUTCOMES=V6/"r1_r4_development_outcomes_v6_1.jsonl"
IN_SUMMARY=V6/"r1_r4_historical_outcome_summary_v6_1.json"
IN_MAN=V6/"r1_r4_historical_outcome_manifest_v6_1.json"
V5_PRE=V5/"r1_r2_bridge_preregistration_v5.json"
AGE_PATH=ROOT/"scripts/validation/snapshot_values.py"
OUT_SCRIPT=V6/"apply_r1_r4_dob_repair_v6_1.py"
OUT_SUPPLEMENT=V6/"r1_r4_dob_repair_supplement_v6_1.jsonl"
OUT_OUTCOMES=V6/"r1_r4_development_outcomes_dob_repaired_v6_1.jsonl"
OUT_SUMMARY=V6/"r1_r4_dob_repair_summary_v6_1.json"
OUT_MD=V6/"r1_r4_dob_repair_summary_v6_1.md"
OUT_MAN=V6/"r1_r4_dob_repair_manifest_v6_1.json"
SLEEPER_URL="https://api.sleeper.app/v1/players/nfl"
MIN_READY=.95
YEARS=(2018,2019,2020,2021,2022,2023)
CELLS=tuple(f"r{r}_{t}" for r in range(1,5) for t in ("early","mid","late"))
ROOT_ALLOWED={"birth_date","birth_date_source","status_flags","primary_o2_ready","H2","H3","H4","annual"}
ANNUAL_ALLOWED={"age_on_sep1","age_multiplier","annual_player_equivalent_fv"}

class GateError(RuntimeError): pass
def now(): return datetime.now(timezone.utc).isoformat()
def load(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def writej(p,o): Path(p).write_text(json.dumps(o,indent=2,sort_keys=True)+"\n")
def readjl(p):
    out=[]
    for n,line in enumerate(Path(p).read_text().splitlines(),1):
        if line.strip():
            try: x=json.loads(line)
            except json.JSONDecodeError as e: raise GateError(f"{p}:{n}: bad JSONL") from e
            if not isinstance(x,dict): raise GateError(f"{p}:{n}: row not object")
            out.append(x)
    return out
def writejl(p,rows):
    with Path(p).open("w") as f:
        for x in rows: f.write(json.dumps(x,sort_keys=True,separators=(",",":"))+"\n")
def import_file(p,name):
    s=importlib.util.spec_from_file_location(name,p)
    if s is None or s.loader is None: raise GateError(f"cannot import {p}")
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def stable(v):
    s=str(v or "").strip(); return s or None
def dob(v):
    s=str(v or "").strip()
    if not s: return None
    try: d=date.fromisoformat(s[:10])
    except ValueError: return None
    return d.isoformat() if 1940<=d.year<=2010 else None
def age(b,season):
    d=date.fromisoformat(b); a=date(season,9,1)
    x=a.year-d.year-((a.month,a.day)<(d.month,d.day))
    if not 18<=x<=50: raise GateError(f"implausible age {x}: {b} {season}")
    return x
def canon(o): return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def guard():
    p=load(PROTOCOL); pm=load(PROTOCOL_MAN); s=load(IN_SUMMARY); m=load(IN_MAN); v5=load(V5_PRE)
    assert p["status"]=="FROZEN_POSTHARVEST_PRE_FIT_METADATA_REPAIR"
    assert p["decision"]=="FREEZE_V6_1_PHASE3_1_DOB_REPAIR_PROTOCOL_EXECUTION_AUTHORIZED"
    assert pm["decision"]==p["decision"]
    r=p["repair_rule"]
    assert r["scope"]=="all_missing_DOB_targets_in_2018_2023_development_corpus"
    assert r["supplement_source"]==SLEEPER_URL
    assert r["join_key"]=="exact_frozen_sleeper_id_only"
    assert r["overwrite_existing_DOB"] is False
    assert r["manual_matching_allowed"] is False
    assert r["alternate_source_chasing_allowed"] is False
    assert r["failed_cell_specific_targeting_allowed"] is False
    assert r["candidate_fit_or_scoring_allowed"] is False
    assert float(r["same_readiness_threshold"])==MIN_READY
    assert s["decision"]=="STOP_V6_1_PHASE3_OUTCOME_AVAILABILITY_OR_COMPLETENESS_GATE"
    assert m["outcome_readiness_gate_pass"] is False
    assert m["development_selection_authorized_next_stage"] is False
    assert m["holdout_2024_pick_identity_file_read"] is False
    assert m["holdout_2024_rookie_outcomes_scored"] is False
    assert m["holdout_2024_pick_outcomes_remain_sealed"] is True
    bad=[(k,v) for k,v in s["outcome_readiness_gate"]["by_year_cell"].items() if not v["pass"]]
    assert len(bad)==1 and bad[0][0]=="2021:r4_late"
    f=bad[0][1]
    assert (f["retained_occurrence_n"],f["sleeper_identity_ready_n"],f["primary_o1_ready_n"],f["primary_o2_ready_n"])==(248,248,248,233)
    assert m["output_hashes"][IN_OUTCOMES.name]==sha(IN_OUTCOMES)
    assert v5["status"]=="FROZEN_PRE_OUTCOME"
    return {"p":p,"s":s,"m":m,"v5":v5}

def fetch_players():
    ses=requests.Session(); ses.headers["User-Agent"]="LOG-Draft-Pick-FV-V6-Phase3.1-DOB/1.0"
    waits=(2,4,8,15,30,45,60); last=None
    for i,w in enumerate(waits):
        try:
            r=ses.get(SLEEPER_URL,timeout=90)
            if r.status_code==429:
                last=GateError("429")
                if i+1<len(waits): time.sleep(w); continue
            r.raise_for_status(); raw=r.content; o=json.loads(raw.decode())
            if not isinstance(o,dict): raise GateError("player index not object")
            return o,{"url":SLEEPER_URL,"status":r.status_code,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"top_level_player_n":len(o),"fetched_at_utc":now()}
        except (requests.RequestException,UnicodeDecodeError,json.JSONDecodeError,GateError) as e:
            last=e
            if i+1<len(waits): time.sleep(w)
    raise GateError(f"Sleeper transport failed: {last}")

def key(row):
    sid=stable(row.get("sleeper_id"))
    return (int(row["draft_year"]),sid) if sid else None

def missing_targets(rows):
    out={}
    for r in rows:
        k=key(r)
        if not k or dob(r.get("birth_date")): continue
        c={"draft_year":k[0],"sleeper_id":k[1],"gsis_id":r.get("gsis_id"),"name":r.get("name"),"position":r.get("position")}
        if k in out:
            for f in ("gsis_id","position"):
                if out[k].get(f) and c.get(f) and out[k][f]!=c[f]: raise GateError(f"target conflict {k} {f}")
        else: out[k]=c
    return out

def supplement(targets,players):
    resolved={}; rows=[]
    for k,meta in sorted(targets.items()):
        y,sid=k; x=players.get(sid); raw=None
        if isinstance(x,dict): raw=x.get("birth_date") or x.get("birthdate")
        b=dob(raw)
        if b:
            for season in range(y,min(y+4,2026)): age(b,season)
            resolved[k]=b
        rows.append({**meta,"prior_birth_date":None,"supplement_birth_date":b,"supplement_source":"Sleeper /players/nfl exact frozen sleeper_id" if b else None,"status":"resolved_exact_sleeper_id_dob" if b else "unresolved"})
    return resolved,rows

def crosscheck(rows,players):
    seen={}; c=Counter()
    for r in rows:
        k=key(r)
        if not k or k in seen: continue
        b=dob(r.get("birth_date"))
        if not b: continue
        seen[k]=b; x=players.get(k[1])
        if not isinstance(x,dict): c["sleeper_record_missing"]+=1; continue
        sb=dob(x.get("birth_date") or x.get("birthdate"))
        if not sb: c["sleeper_dob_missing"]+=1
        elif sb==b: c["same_valid_dob"]+=1
        else: c["valid_dob_conflict_diagnostic_only"]+=1
    return dict(c)

def horizon(annual,y,n,orig):
    out=copy.deepcopy(orig)
    if not out.get("mature"): out["O2"]=None; return out
    req=set(range(y,y+n)); xs=[a for a in annual if int(a["season"]) in req]
    if len(xs)!=n: raise GateError(f"mature horizon missing rows {y}/{n}")
    vals=[a.get("annual_player_equivalent_fv") for a in xs]
    out["O2"]=round(sum(float(v) for v in vals)/n,8) if all(v is not None for v in vals) else None
    return out

def repair_row(r,b,age_mod,cfg,pw,base):
    if dob(r.get("birth_date")): raise GateError("overwrite attempt")
    pos=r.get("position")
    if pos not in pw: raise GateError("unsupported target position")
    o=copy.deepcopy(r); o["birth_date"]=b; o["birth_date_source"]="sleeper_exact_id_phase3_1_supplement"
    ann=o.get("annual")
    if not isinstance(ann,list): raise GateError("missing annual")
    for a in ann:
        season=int(a["season"]); rp=a.get("realized_prod_mult")
        if rp is None: raise GateError("missing realized_prod_mult")
        ag=age(b,season); am=float(age_mod.age_multiplier(pos,ag,"Starter",float(rp),float(rp),cfg))
        a["age_on_sep1"]=ag; a["age_multiplier"]=round(am,10); a["annual_player_equivalent_fv"]=round(base*pw[pos]*am*float(rp),8)
    y=int(o["draft_year"])
    for n,h in ((2,"H2"),(3,"H3"),(4,"H4")): o[h]=horizon(ann,y,n,r[h])
    o["status_flags"]=[x for x in list(o.get("status_flags") or []) if x!="missing_birth_date"]
    o["primary_o2_ready"]=bool(o["H3"].get("mature") and o["H3"].get("O2") is not None and not o["status_flags"])
    return o

def prove(before,after):
    roots={k for k in set(before)|set(after) if before.get(k)!=after.get(k)}
    if not roots<=ROOT_ALLOWED: raise GateError(f"forbidden root diff {sorted(roots-ROOT_ALLOWED)}")
    protected=("draft_year","league_id","league_idp","source_origin","overall_slot","round","within_round_pick","tier","cell","split","mfl_player_id","gsis_id","sleeper_id","stable_player_key","name","position","position_source","cell_weight_v6_1","source_weight_r1_r4_v6_1","primary_o1_ready")
    for k in protected:
        if before.get(k)!=after.get(k): raise GateError(f"protected field changed {k}")
    ba,aa=before["annual"],after["annual"]
    if len(ba)!=len(aa): raise GateError("annual length changed")
    for b,a in zip(ba,aa):
        d={k for k in set(b)|set(a) if b.get(k)!=a.get(k)}
        if not d<=ANNUAL_ALLOWED: raise GateError(f"forbidden annual diff {sorted(d-ANNUAL_ALLOWED)}")
    for h in ("H2","H3","H4"):
        d={k for k in set(before[h])|set(after[h]) if before[h].get(k)!=after[h].get(k)}
        if not d<={"O2"}: raise GateError(f"forbidden {h} diff {sorted(d-{'O2'})}")

def readiness(rows):
    by=defaultdict(lambda:{"n":0,"o1":0,"o2":0}); tot=0
    for r in rows:
        d=by[(int(r["draft_year"]),r["cell"])]; d["n"]+=1; d["o1"]+=int(bool(r.get("primary_o1_ready"))); d["o2"]+=int(bool(r.get("primary_o2_ready"))); tot+=int(bool(r.get("primary_o2_ready")))
    cells={}; ok=True
    for y in YEARS:
        for c in CELLS:
            d=by[(y,c)]; cov=d["o2"]/d["n"] if d["n"] else 0; p=cov>=MIN_READY; ok&=p
            cells[f"{y}:{c}"]={"retained_occurrence_n":d["n"],"primary_o1_ready_n":d["o1"],"primary_o2_ready_n":d["o2"],"primary_o2_ready_coverage":cov,"minimum_required":MIN_READY,"pass":p}
    overall=tot/len(rows) if rows else 0; ok&=overall>=MIN_READY
    return {"pass":bool(ok),"overall_primary_o2_ready_coverage":overall,"by_year_cell":cells}

def apply():
    st=guard(); rows=readjl(IN_OUTCOMES)
    if len(rows)!=17915: raise GateError("development denominator drift")
    mt=missing_targets(rows); before_occ=sum(1 for r in rows if key(r) in mt)
    players,meta=fetch_players(); resolved,supp=supplement(mt,players); diag=crosscheck(rows,players)
    age_mod=import_file(AGE_PATH,"v6dobage"); bridge=st["v5"]["frozen_scale_bridge"]
    cfg={"age_curve":bridge["age_curve"],"qb_post_peak_floor":float(bridge["qb_post_peak_floor"]),"lb_post_peak_decay_power":float(bridge["lb_post_peak_decay_power"])}
    pw={k:float(v) for k,v in bridge["position_weight"].items()}; base=float(bridge["base_scale"])
    out=[]; repaired=0; changed=set()
    for r in rows:
        k=key(r)
        if k in resolved and not dob(r.get("birth_date")):
            n=repair_row(r,resolved[k],age_mod,cfg,pw,base); prove(r,n); out.append(n); repaired+=1; changed.add(k)
        else: out.append(copy.deepcopy(r))
    if changed!=set(resolved): raise GateError("resolved target application mismatch")
    for b,a in zip(rows,out):
        if key(b) not in resolved and b!=a: raise GateError("non-repair row changed")
    before=readiness(rows); after=readiness(out)
    out.sort(key=lambda x:(int(x["draft_year"]),int(x["league_id"]),int(x["overall_slot"])))
    writejl(OUT_SUPPLEMENT,supp); writejl(OUT_OUTCOMES,out)
    unresolved=[x for x in supp if x["status"]=="unresolved"]
    decision="PASS_V6_1_PHASE3_1_DOB_REPAIR_DEVELOPMENT_SELECTION_AUTHORIZED_NEXT_STAGE" if after["pass"] else "STOP_V6_1_PHASE3_1_DOB_REPAIR_STILL_BELOW_READINESS_GATE"
    g=now()
    summary={"schema_version":1,"study_id":"draft-pick-fv-v6-r1-r4-structural-continuity","stage":"phase3_1_dob_lineage_repair","status":"DOB_REPAIR_PASS" if after["pass"] else "DOB_REPAIR_STOP","generated_at_utc":g,"decision":decision,"research_only":True,"postharvest_pre_fit_metadata_repair":True,"repair_protocol_frozen_before_sleeper_query":True,"repair_scope":"all missing-DOB unique targets in complete 2018-2023 development corpus","failed_cell_specific_targeting_used":False,"manual_matching_used":False,"alternate_source_chasing_used":False,"existing_dob_overwritten":False,"sleeper_position_used":False,"sleeper_name_used_for_matching":False,"join_key":"exact frozen sleeper_id only","candidate_fit_performed":False,"candidate_scores_computed":False,"candidate_selection_performed":False,"market_or_ktc_values_read":False,"package_vote_data_read":False,"holdout_2024_pick_identity_file_read":False,"holdout_2024_rookie_outcomes_scored":False,"production_change_authorized":False,"input_development_occurrence_n":len(rows),"missing_dob_unique_target_n_before":len(mt),"missing_dob_occurrence_n_before":before_occ,"resolved_unique_target_n":len(resolved),"repaired_occurrence_n":repaired,"unresolved_unique_target_n":len(unresolved),"existing_dob_crosscheck_diagnostic":diag,"sleeper_player_index_response":meta,"readiness_before":before,"readiness_after":after,"original_phase3_stop_preserved":True,"original_phase3_decision":st["s"]["decision"],"next_stage_authorized":after["pass"],"next_stage":"draft-pick-fv-v6-phase4-loyo-development-selection" if after["pass"] else None,"input_hashes":{PROTOCOL.name:sha(PROTOCOL),PROTOCOL_MAN.name:sha(PROTOCOL_MAN),IN_OUTCOMES.name:sha(IN_OUTCOMES),IN_SUMMARY.name:sha(IN_SUMMARY),IN_MAN.name:sha(IN_MAN),V5_PRE.name:sha(V5_PRE),AGE_PATH.name:sha(AGE_PATH)}}
    writej(OUT_SUMMARY,summary)
    fb=[k for k,v in before["by_year_cell"].items() if not v["pass"]]; fa=[k for k,v in after["by_year_cell"].items() if not v["pass"]]
    OUT_MD.write_text("\n".join(["# Draft Pick FV V6.1 — Phase 3.1 DOB Lineage Repair","",f"**Decision:** `{decision}`","",f"- Missing-DOB unique targets before: **{len(mt)}**",f"- Missing-DOB occurrences before: **{before_occ}**",f"- Exact-ID resolved targets: **{len(resolved)}**",f"- Repaired occurrences: **{repaired}**",f"- Still unresolved targets: **{len(unresolved)}**",f"- Overall H3 O2 readiness before: **{before['overall_primary_o2_ready_coverage']:.2%}**",f"- Overall H3 O2 readiness after: **{after['overall_primary_o2_ready_coverage']:.2%}**",f"- Failing cells before: **{', '.join(fb) or 'None'}**",f"- Failing cells after: **{', '.join(fa) or 'None'}**","","- Existing DOB overwrite: **No**","- Manual/name/position matching: **No**","- Candidate fitting/scoring/selection: **No**","- 2024 holdout pick-linked outcomes read/scored: **No**","- Production change authorized: **No**",""]),encoding="utf-8")
    man={"schema_version":1,"study_id":summary["study_id"],"stage":summary["stage"],"status":summary["status"],"generated_at_utc":g,"decision":decision,"repair_protocol_frozen_before_sleeper_query":True,"candidate_fit_performed":False,"candidate_scores_computed":False,"candidate_selection_performed":False,"holdout_2024_pick_identity_file_read":False,"holdout_2024_rookie_outcomes_scored":False,"production_change_authorized":False,"readiness_gate_pass":after["pass"],"development_selection_authorized_next_stage":after["pass"],"next_stage":summary["next_stage"],"input_hashes":summary["input_hashes"],"output_hashes":{OUT_SUPPLEMENT.name:sha(OUT_SUPPLEMENT),OUT_OUTCOMES.name:sha(OUT_OUTCOMES),OUT_SUMMARY.name:sha(OUT_SUMMARY),OUT_MD.name:sha(OUT_MD)},"canonical_summary_sha256":canon(summary)}
    writej(OUT_MAN,man)
    print(f"DECISION={decision}"); print(f"missing_targets={len(mt)} resolved={len(resolved)} repaired_occurrences={repaired}"); print(f"failing_cells_after={fa}")

def selftest():
    assert dob("2000-01-02")=="2000-01-02" and dob("") is None and age("2000-09-02",2021)==20
    rows=[]
    for y in YEARS:
        for c in CELLS:
            for _ in range(20): rows.append({"draft_year":y,"cell":c,"primary_o1_ready":True,"primary_o2_ready":True})
    rows[0]["primary_o2_ready"]=False
    d=readiness(rows); assert d["pass"] and math.isclose(d["by_year_cell"]["2018:r1_early"]["primary_o2_ready_coverage"],.95)
    targets={(2021,"111"):{"draft_year":2021,"sleeper_id":"111","gsis_id":"g1","name":"Frozen","position":"WR"},(2022,"222"):{"draft_year":2022,"sleeper_id":"222","gsis_id":"g2","name":"Other","position":"RB"}}
    players={"111":{"birth_date":"1999-03-04","position":"QB","full_name":"Different"},"222":{"birth_date":None,"position":"WR"}}
    r,s=supplement(targets,players); assert r=={(2021,"111"):"1999-03-04"} and s[1]["status"]=="unresolved"
    print("PASS: V6.1 Phase 3.1 DOB-repair self-test")

def check():
    s=load(OUT_SUMMARY); m=load(OUT_MAN)
    assert s["decision"] in {"PASS_V6_1_PHASE3_1_DOB_REPAIR_DEVELOPMENT_SELECTION_AUTHORIZED_NEXT_STAGE","STOP_V6_1_PHASE3_1_DOB_REPAIR_STILL_BELOW_READINESS_GATE"}
    assert m["decision"]==s["decision"]; assert s["input_development_occurrence_n"]==17915
    assert s["failed_cell_specific_targeting_used"] is False and s["existing_dob_overwritten"] is False and s["sleeper_position_used"] is False
    assert s["holdout_2024_pick_identity_file_read"] is False
    for o in (s,m):
        for k in ("candidate_fit_performed","candidate_scores_computed","candidate_selection_performed","production_change_authorized"): assert o[k] is False
    assert s["readiness_after"]["pass"]==m["readiness_gate_pass"]
    for n,h in m["output_hashes"].items(): assert sha(V6/n)==h
    print("PASS: V6.1 Phase 3.1 DOB-repair outputs validated")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--selftest",action="store_true"); ap.add_argument("--guard",action="store_true"); ap.add_argument("--apply",action="store_true"); ap.add_argument("--check",action="store_true"); a=ap.parse_args()
    if a.selftest: selftest()
    elif a.guard: guard(); print("PASS: frozen Phase 3 STOP + DOB repair protocol verified")
    elif a.apply: apply()
    elif a.check: check()
    else: raise SystemExit("choose --selftest/--guard/--apply/--check")
if __name__=="__main__": main()
