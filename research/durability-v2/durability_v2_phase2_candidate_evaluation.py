#!/usr/bin/env python3
"""
Durability / Availability V2 — Phase 2 candidate evaluation.

RESEARCH ONLY. No deployed durability, history component, production multiplier,
age curve, market value, or player value is changed.

Phase 2 keeps survivor-only and unconditional availability targets separate and
evaluates candidate predictors with leave-one-base-season-out cross-validation.
All multi-year variants are evaluated on matched cohorts.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
PHASE1_JSON = REPO_ROOT / "research" / "durability-v2" / "durability_v2_phase1_availability_audit.json"
OUTPUT_JSON = REPO_ROOT / "research" / "durability-v2" / "durability_v2_phase2_candidate_evaluation.json"
OUTPUT_MD = REPO_ROOT / "research" / "durability-v2" / "durability_v2_phase2_candidate_evaluation.md"
METHOD_VERSION = "durability-v2-phase2-candidate-evaluation-v1"
PHASE1_METHOD = "durability-v2-phase1-availability-audit-v1"
TRACKED_POSITIONS = ("QB", "RB", "WR", "TE", "DL", "LB", "DB")
TARGETS = ("survivor_only", "unconditional")
FAMILIES = ("one_year", "two_year", "three_year")
BASE_SEASONS = tuple(range(2015, 2025))
BLEND_GRID = tuple(i / 20.0 for i in range(21))
EPS = 1e-12
FAMILY_VARIANTS = {
    "one_year": ("position_median", "deployed_r2_blend", "own_raw", "trained_blend", "ols_current"),
    "two_year": ("position_median", "deployed_r2_blend", "own_raw", "trained_blend", "ols_current", "mean_2year", "recency_2year", "ols_current_prior1"),
    "three_year": ("position_median", "deployed_r2_blend", "own_raw", "trained_blend", "ols_current", "mean_3year", "recency_3year", "ols_current_prior1_prior2"),
}
SCREEN = {
    "mae_must_beat_deployed_r2_blend": True,
    "spearman_delta_min": -0.005,
    "positions_with_mae_improvement_min": 4,
    "fold_improvement_share_min": 0.70,
}

def now_utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def read_json(path: Path):
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))

def rankdata(values):
    indexed = sorted(enumerate(values), key=lambda x: (x[1], x[0]))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg = ((i + 1) + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg
        i = j
    return ranks

def pearson(xs, ys):
    if len(xs) != len(ys) or len(xs) < 5:
        return None
    mx = statistics.fmean(xs); my = statistics.fmean(ys)
    dx = [x-mx for x in xs]; dy = [y-my for y in ys]
    den = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    return None if den <= 0 else sum(a*b for a,b in zip(dx,dy)) / den

def spearman(xs, ys):
    return None if len(xs) < 5 else pearson(rankdata(xs), rankdata(ys))

def metric_bundle(rows, field):
    if not rows:
        return {"n":0,"mae":None,"rmse":None,"spearman":None,"pearson":None,"bias":None}
    actual=[float(r["target"]) for r in rows]; pred=[float(r[field]) for r in rows]
    return {
        "n":len(rows),
        "mae":statistics.fmean(abs(a-p) for a,p in zip(actual,pred)),
        "rmse":math.sqrt(statistics.fmean((a-p)**2 for a,p in zip(actual,pred))),
        "spearman":spearman(pred,actual),
        "pearson":pearson(pred,actual),
        "bias":statistics.fmean(p-a for a,p in zip(actual,pred)),
    }

def validate_phase1(phase1):
    if phase1.get("method_version") != PHASE1_METHOD:
        raise RuntimeError("Unexpected Durability V2 Phase-1 method")
    if phase1.get("deployment_authorized") is not False:
        raise RuntimeError("Phase 1 unexpectedly authorizes deployment")
    if int((phase1.get("coverage") or {}).get("player_seasons") or 0) < 10000:
        raise RuntimeError("Phase-1 historical sample unexpectedly sparse")

def phase1_rows_by_key(phase1):
    rows=phase1.get("player_seasons")
    if not isinstance(rows,list):
        raise RuntimeError("Phase 1 missing player_seasons")
    out={}
    for row in rows:
        key=(str(row["sleeper_id"]),int(row["season"]))
        if key in out: raise RuntimeError(f"Duplicate Phase-1 player-season: {key}")
        out[key]=row
    return out

def build_model_rows(phase1,target_name):
    source=phase1.get("survivor_only_transition_rows" if target_name=="survivor_only" else "unconditional_transition_rows")
    if not isinstance(source,list):
        raise RuntimeError(f"Phase 1 missing {target_name} transition rows")
    lookup=phase1_rows_by_key(phase1); out=[]
    for row in source:
        pid=str(row["sleeper_id"]); season=int(row["season"]); pos=str(row["pos"])
        if pos not in TRACKED_POSITIONS: continue
        prior1=lookup.get((pid,season-1)); prior2=lookup.get((pid,season-2))
        cur=float(row["current_availability"]); target=float(row["next_availability"])
        p1=float(prior1["availability"]) if prior1 is not None else None
        p2=float(prior2["availability"]) if prior2 is not None else None
        out.append({
            "sleeper_id":pid,"pos":pos,"season":season,"target":target,"current":cur,
            "prior1":p1,"prior2":p2,
            "mean_2year":((cur+p1)/2.0 if p1 is not None else None),
            "recency_2year":(0.67*cur+0.33*p1 if p1 is not None else None),
            "mean_3year":((cur+p1+p2)/3.0 if p1 is not None and p2 is not None else None),
            "recency_3year":(0.57*cur+0.29*p1+0.14*p2 if p1 is not None and p2 is not None else None),
        })
    return out

def family_cohort(rows,family):
    if family=="one_year": return list(rows)
    if family=="two_year": return [r for r in rows if r["prior1"] is not None]
    if family=="three_year": return [r for r in rows if r["prior1"] is not None and r["prior2"] is not None]
    raise ValueError(family)

def fit_ols(rows,features):
    if len(rows)<max(20,3*(len(features)+1)):
        raise RuntimeError(f"Too few OLS rows: {len(rows)}")
    x=np.asarray([[1.0]+[float(r[n]) for n in features] for r in rows],dtype=float)
    y=np.asarray([float(r["target"]) for r in rows],dtype=float)
    beta,*_=np.linalg.lstsq(x,y,rcond=None)
    return beta

def predict_ols(beta,row,features):
    x=np.asarray([1.0]+[float(row[n]) for n in features],dtype=float)
    return clamp01(float(np.dot(x,beta)))

def deployed_r2_by_position(phase1):
    dep=((phase1.get("legacy_methodology") or {}).get("deployed_durability_results") or {})
    return {p:clamp01(float((dep.get(p) or {}).get("r_squared") or 0.0)) for p in TRACKED_POSITIONS}

def select_blend_weight(train_pos,median):
    best_w=None; best_mae=None
    for w in BLEND_GRID:
        score=statistics.fmean(abs(float(r["target"])-(w*float(r["current"])+(1-w)*median)) for r in train_pos)
        if best_mae is None or score<best_mae-EPS or (abs(score-best_mae)<=EPS and abs(w-.5)<abs(float(best_w)-.5)):
            best_w=w; best_mae=score
    return float(best_w),float(best_mae)

def run_family_oof(phase1,target_name,family,all_rows):
    cohort=family_cohort(all_rows,family)
    years=sorted({int(r["season"]) for r in cohort if int(r["season"]) in BASE_SEASONS})
    deployed=deployed_r2_by_position(phase1)
    out=[]; fold_params={}
    for held in years:
        train=[r for r in cohort if int(r["season"])!=held]; test=[r for r in cohort if int(r["season"])==held]
        params={}
        for pos in TRACKED_POSITIONS:
            train_pos=[r for r in train if r["pos"]==pos]; test_pos=[r for r in test if r["pos"]==pos]
            if not test_pos: continue
            if len(train_pos)<20: raise RuntimeError(f"Too few training rows {target_name}/{family}/{held}/{pos}")
            med=float(statistics.median(float(r["current"]) for r in train_pos))
            w,wmae=select_blend_weight(train_pos,med)
            beta1=fit_ols(train_pos,("current",))
            beta2=fit_ols(train_pos,("current","prior1")) if family=="two_year" else None
            beta3=fit_ols(train_pos,("current","prior1","prior2")) if family=="three_year" else None
            params[pos]={"training_n":len(train_pos),"test_n":len(test_pos),"position_median":med,"deployed_r2_weight":deployed[pos],"trained_blend_weight":w,"trained_blend_training_mae":wmae,"ols_current_coefficients":[float(x) for x in beta1],"ols_multiyear_coefficients":([float(x) for x in beta2] if beta2 is not None else [float(x) for x in beta3] if beta3 is not None else None)}
            for row in test_pos:
                rec=dict(row); cur=float(row["current"]); r2w=deployed[pos]
                rec.update({"target_name":target_name,"family":family,"held_out_season":held,
                    "pred__position_median":med,
                    "pred__deployed_r2_blend":clamp01(r2w*cur+(1-r2w)*med),
                    "pred__own_raw":cur,
                    "pred__trained_blend":clamp01(w*cur+(1-w)*med),
                    "pred__ols_current":predict_ols(beta1,row,("current",))})
                if family=="two_year":
                    rec["pred__mean_2year"]=clamp01(float(row["mean_2year"])); rec["pred__recency_2year"]=clamp01(float(row["recency_2year"])); rec["pred__ols_current_prior1"]=predict_ols(beta2,row,("current","prior1"))
                if family=="three_year":
                    rec["pred__mean_3year"]=clamp01(float(row["mean_3year"])); rec["pred__recency_3year"]=clamp01(float(row["recency_3year"])); rec["pred__ols_current_prior1_prior2"]=predict_ols(beta3,row,("current","prior1","prior2"))
                out.append(rec)
        fold_params[str(held)]=params
    expected={f"pred__{v}" for v in FAMILY_VARIANTS[family]}
    for row in out:
        missing=expected.difference(row)
        if missing: raise RuntimeError(f"Missing predictions: {sorted(missing)}")
    return out,{"held_out_seasons":years,"fold_parameters":fold_params,"cohort_n":len(cohort)}

def evaluate_oof(rows,family):
    variants=FAMILY_VARIANTS[family]
    overall={v:metric_bundle(rows,f"pred__{v}") for v in variants}
    by_position={p:{v:metric_bundle([r for r in rows if r["pos"]==p],f"pred__{v}") for v in variants} for p in TRACKED_POSITIONS}
    years=sorted({int(r["season"]) for r in rows})
    by_fold={str(y):{v:metric_bundle([r for r in rows if int(r["season"])==y],f"pred__{v}") for v in variants} for y in years}
    return {"overall":overall,"by_position":by_position,"by_fold":by_fold}

def compare_to_deployed(ev,family):
    control="deployed_r2_blend"; base=ev["overall"][control]; out={}
    for v in FAMILY_VARIANTS[family]:
        if v==control: continue
        cur=ev["overall"][v]; pos_imp=0; pos_delta={}
        for p in TRACKED_POSITIONS:
            a=ev["by_position"][p][v]["mae"]; b=ev["by_position"][p][control]["mae"]; d=(float(a)-float(b) if a is not None and b is not None else None); pos_delta[p]=d; pos_imp+=int(d is not None and d<0)
        fold_imp=0; fold_total=0; fold_delta={}
        for y,data in ev["by_fold"].items():
            a=data[v]["mae"]; b=data[control]["mae"]; d=(float(a)-float(b) if a is not None and b is not None else None); fold_delta[y]=d
            if d is not None: fold_total+=1; fold_imp+=int(d<0)
        out[v]={
            "mae_delta_vs_deployed":float(cur["mae"])-float(base["mae"]),
            "rmse_delta_vs_deployed":float(cur["rmse"])-float(base["rmse"]),
            "spearman_delta_vs_deployed":(float(cur["spearman"])-float(base["spearman"]) if cur["spearman"] is not None and base["spearman"] is not None else None),
            "pearson_delta_vs_deployed":(float(cur["pearson"])-float(base["pearson"]) if cur["pearson"] is not None and base["pearson"] is not None else None),
            "positions_with_mae_improvement":pos_imp,"folds_with_mae_improvement":fold_imp,"folds_compared":fold_total,"fold_improvement_share":(fold_imp/fold_total if fold_total else None),"by_position_mae_delta":pos_delta,"by_fold_mae_delta":fold_delta}
    return out

def screen_family(ev,comp,family):
    base=ev["overall"]["deployed_r2_blend"]; screens={}; survivors=[]
    for v in FAMILY_VARIANTS[family]:
        if v=="deployed_r2_blend": screens[v]={"control":True,"passes":True,"checks":{}}; continue
        c=comp[v]; cur=ev["overall"][v]
        checks={
            "mae_beats_deployed":float(cur["mae"])<float(base["mae"]),
            "spearman_delta":c["spearman_delta_vs_deployed"] is not None and float(c["spearman_delta_vs_deployed"])>=SCREEN["spearman_delta_min"],
            "positions_with_mae_improvement":c["positions_with_mae_improvement"]>=SCREEN["positions_with_mae_improvement_min"],
            "fold_improvement_share":c["fold_improvement_share"] is not None and float(c["fold_improvement_share"])>=SCREEN["fold_improvement_share_min"],}
        passed=all(checks.values()); screens[v]={"control":False,"passes":passed,"checks":checks}
        if passed: survivors.append(v)
    leader=None
    if survivors:
        survivors.sort(key=lambda v:(ev["overall"][v]["mae"],-(ev["overall"][v]["spearman"] or -999),v)); leader=survivors[0]
    return screens,survivors,leader

def summarize_weights(meta):
    out={}
    for p in TRACKED_POSITIONS:
        vals=[float(f[p]["trained_blend_weight"]) for f in meta["fold_parameters"].values() if p in f]
        out[p]={"n_folds":len(vals),"mean_weight":statistics.fmean(vals) if vals else None,"median_weight":statistics.median(vals) if vals else None,"min_weight":min(vals) if vals else None,"max_weight":max(vals) if vals else None}
    return out

def build_result():
    phase1=read_json(PHASE1_JSON); validate_phase1(phase1)
    result={"schema_version":1,"method_version":METHOD_VERSION,"generated_at_utc":now_utc(),"status":"RESEARCH_ONLY_DURABILITY_CANDIDATE_EVALUATION","production_files_mutated":0,"deployment_authorized":False,"durability_change_authorized":False,"history_component_change_authorized":False,"primary_metric":"next-season availability MAE","targets":{},"screen":SCREEN}
    for target in TARGETS:
        all_rows=build_model_rows(phase1,target); t={"base_row_n":len(all_rows),"families":{}}
        for family in FAMILIES:
            print(f"Evaluating {target} / {family}...")
            oof,meta=run_family_oof(phase1,target,family,all_rows); ev=evaluate_oof(oof,family); comp=compare_to_deployed(ev,family); screening,survivors,leader=screen_family(ev,comp,family)
            t["families"][family]={"metadata":meta,"trained_blend_weight_summary":summarize_weights(meta),"evaluation":ev,"comparison_vs_deployed_r2_blend":comp,"screening":screening,"screened_survivors":survivors,"monitoring_leader":leader,"oof_predictions":oof}
        result["targets"][target]=t
    s=result["targets"]["survivor_only"]["families"]["one_year"]; u=result["targets"]["unconditional"]["families"]["one_year"]
    result["phase3_handoff"]={"survivor_one_year_leader":s["monitoring_leader"],"unconditional_one_year_leader":u["monitoring_leader"],"recommendation":"Phase 3 should shadow current projected-games behavior only if the survivor-only track produces a stable non-control winner. Treat the unconditional track as a separate broader availability/survival diagnostic because it overlaps conceptually with Age V2, Production V2, and Opportunity V2. If longer-history variants win only on matched veteran cohorts, test them position-specifically rather than applying them to every player."}
    return result

def fmt(v,d=4): return "—" if v is None else f"{float(v):.{d}f}"
def signed(v,d=4): return "—" if v is None else f"{float(v):+.{d}f}"

def render_family(target,family,fr):
    ev=fr["evaluation"]; comp=fr["comparison_vs_deployed_r2_blend"]; screening=fr["screening"]
    lines=[f"### `{target}` — `{family}`","","| Variant | N | MAE | Δ MAE | RMSE | Spearman | Δ Spearman | Pos improved | Folds improved | Pass |","|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for v in FAMILY_VARIANTS[family]:
        row=ev["overall"][v]
        if v=="deployed_r2_blend": dmae=dsp=None; pos="—"; folds="—"
        else:
            c=comp[v]; dmae=c["mae_delta_vs_deployed"]; dsp=c["spearman_delta_vs_deployed"]; pos=f"{c['positions_with_mae_improvement']}/7"; folds=f"{c['folds_with_mae_improvement']}/{c['folds_compared']}"
        lines.append(f"| `{v}` | {row['n']} | {fmt(row['mae'])} | {signed(dmae)} | {fmt(row['rmse'])} | {fmt(row['spearman'])} | {signed(dsp)} | {pos} | {folds} | {'PASS' if screening[v]['passes'] else 'FAIL'} |")
    lines += ["",f"Monitoring leader: **`{fr['monitoring_leader'] or 'none'}`**",""]
    return lines

def render_markdown(result):
    lines=["# Durability / Availability V2 — Phase 2 Candidate Evaluation","",f"Method: `{result['method_version']}`  ",f"Status: **`{result['status']}`**","","## Guardrail","","**Research only. No deployed durability or player value is changed.**","","Primary metric: **next-season availability MAE**.","","The survivor-only and unconditional targets are intentionally kept separate. The former is the cleaner durability target; the latter also contains role loss, retirement, and league exit.",""]
    for target in TARGETS:
        lines += [f"## {target.replace('_',' ').title()} target",""]
        for family in FAMILIES: lines += render_family(target,family,result["targets"][target]["families"][family])
    lines += ["## Training-fold optimized own-history weights","","One-year family, median optimized weight across held-out folds:","","| Target | QB | RB | WR | TE | DL | LB | DB |","|---|---:|---:|---:|---:|---:|---:|---:|"]
    for target in TARGETS:
        weights=result["targets"][target]["families"]["one_year"]["trained_blend_weight_summary"]
        lines.append(f"| {target} | " + " | ".join(fmt(weights[p]["median_weight"],2) for p in TRACKED_POSITIONS) + " |")
    h=result["phase3_handoff"]
    lines += ["","## Phase 3","",f"- Survivor one-year leader: **`{h['survivor_one_year_leader'] or 'none'}`**",f"- Unconditional one-year leader: **`{h['unconditional_one_year_leader'] or 'none'}`**","",h["recommendation"],""]
    return "\n".join(lines)

def write_outputs(result):
    OUTPUT_JSON.parent.mkdir(parents=True,exist_ok=True); OUTPUT_JSON.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8"); OUTPUT_MD.write_text(render_markdown(result),encoding="utf-8"); print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}"); print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")

def check_outputs():
    result=read_json(OUTPUT_JSON)
    if result.get("method_version")!=METHOD_VERSION: raise RuntimeError("Durability V2 Phase-2 method mismatch")
    if result.get("production_files_mutated")!=0: raise RuntimeError("Durability Phase-2 mutation guardrail failed")
    for key in ("deployment_authorized","durability_change_authorized","history_component_change_authorized"):
        if result.get(key) is not False: raise RuntimeError(f"Durability Phase 2 unexpectedly authorizes {key}")
    if set(result.get("targets") or {})!=set(TARGETS): raise RuntimeError("Durability Phase-2 target family mismatch")
    for target in TARGETS:
        families=result["targets"][target].get("families") or {}
        if set(families)!=set(FAMILIES): raise RuntimeError(f"{target}: family mismatch")
        for family in FAMILIES:
            oof=families[family].get("oof_predictions")
            if not isinstance(oof,list) or len(oof)<500: raise RuntimeError(f"{target}/{family}: OOF sample unexpectedly small")
    if not OUTPUT_MD.exists(): raise RuntimeError("Durability Phase-2 markdown missing")
    text=OUTPUT_MD.read_text(encoding="utf-8")
    for marker in ("Research only","Survivor Only target","Unconditional target","Training-fold optimized own-history weights","Phase 3"):
        if marker not in text: raise RuntimeError(f"Durability Phase-2 report missing marker: {marker}")
    print("Durability / Availability V2 Phase-2 outputs passed guardrails.")

def run_selftest():
    assert clamp01(-1)==0 and clamp01(2)==1
    assert abs(spearman([1,2,3,4,5],[10,20,30,40,50])-1.0)<1e-12
    rows=[]
    for i in range(50):
        cur=i/49.0; rows.append({"current":cur,"prior1":cur*.8,"prior2":cur*.6,"target":.2+.6*cur,"pos":"RB"})
    beta=fit_ols(rows,("current",)); pred=predict_ols(beta,rows[10],("current",)); assert 0<=pred<=1
    w,m=select_blend_weight(rows,.7); assert 0<=w<=1 and m>=0
    print("Durability / Availability V2 Phase-2 self-test passed: metrics, OLS, clamping, and training-only blend selection.")

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--selftest",action="store_true"); parser.add_argument("--write",action="store_true"); parser.add_argument("--check",action="store_true"); args=parser.parse_args()
    if args.selftest: run_selftest(); return
    if args.check: check_outputs(); return
    result=build_result(); write_outputs(result) if args.write else print(render_markdown(result))

if __name__=="__main__": main()
