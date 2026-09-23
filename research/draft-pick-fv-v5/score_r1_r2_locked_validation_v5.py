#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path.cwd()
D = ROOT / "research" / "draft-pick-fv-v5"
PREREG = D / "r1_r2_bridge_preregistration_v5.json"
ID_SUMMARY = D / "r1_r2_source_identity_summary_v5_1.json"
ID_MANIFEST = D / "r1_r2_source_identity_manifest_v5_1.json"
P3_MANIFEST = D / "r1_r2_historical_outcome_manifest_v5_1.json"
P3_SUMMARY = D / "r1_r2_historical_outcome_summary_v5_1.json"
FIT = D / "r1_r2_development_candidate_fit_v5.json"
FIT_MANIFEST = D / "r1_r2_development_candidate_fit_manifest_v5.json"
METRIC = D / "r1_r2_validation_metric_contract_v5.json"
VALIDATION = D / "r1_r2_locked_validation_outcomes_v5_1.jsonl"
OUT = D / "r1_r2_locked_validation_results_v5.json"
OUT_MD = D / "r1_r2_locked_validation_results_v5.md"
OUT_MANIFEST = D / "r1_r2_locked_validation_manifest_v5.json"

YEARS = (2022, 2023)
CELLS = ("r1_early", "r1_mid", "r1_late", "r2_early", "r2_mid", "r2_late")
CANDIDATES = ("C0_DEPLOYED", "C1_R1_GLOBAL_RESCALE", "C2_R1_R2_ROUND_RESCALE", "C3_R1_R2_LOW_PARAMETER_TIER_CURVE")
WINNER_POOL = CANDIDATES[1:]

class GateError(RuntimeError): pass
def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def finite(x): return isinstance(x, (int,float)) and not isinstance(x,bool) and math.isfinite(float(x))
def get_outcome(row, horizon, field):
    h = row.get(horizon)
    if not isinstance(h, dict): return None
    v = h.get(field)
    return float(v) if finite(v) else None
def read_jsonl(path):
    rows=[]
    with Path(path).open(encoding="utf-8") as f:
        for n,line in enumerate(f,1):
            if not line.strip(): continue
            x=json.loads(line)
            if not isinstance(x,dict): raise GateError(f"{path}:{n}: non-object")
            rows.append(x)
    return rows
def base_rows(rows, non_idp=False):
    out=[]; seen=set()
    for r in rows:
        y=int(r["draft_year"]); cell=str(r["cell"])
        if y not in YEARS or cell not in CELLS or r.get("split") != "locked_validation":
            raise GateError("locked-validation corpus contract violated")
        key=(y,str(r["league_id"]),int(r["overall_slot"]))
        if key in seen: raise GateError(f"duplicate validation occurrence {key}")
        seen.add(key)
        if non_idp and bool(r.get("league_idp",False)): continue
        out.append(r)
    return out
def weighted_rows(rows, horizon, field, years=YEARS, mature=False, require_h3=False):
    chosen=[]; raw=defaultdict(float); counts=defaultdict(int)
    for r in rows:
        y=int(r["draft_year"])
        if y not in years: continue
        h=r.get(horizon)
        if not isinstance(h,dict): continue
        if mature and h.get("mature") is not True: continue
        if get_outcome(r,horizon,field) is None: continue
        if require_h3 and get_outcome(r,"H3",field) is None: continue
        w=r.get("cell_weight_v5_1")
        if not finite(w) or float(w)<=0: raise GateError("invalid cell weight")
        key=(y,str(r["cell"])); raw[key]+=float(w); counts[key]+=1; chosen.append(r)
    present=tuple(y for y in years if any(counts[(y,c)] for c in CELLS))
    if not present: raise GateError(f"no rows for {horizon}/{field}")
    for y in present:
        for c in CELLS:
            if counts[(y,c)]==0 or raw[(y,c)]<=0: raise GateError(f"zero support {horizon} {y}:{c}")
    share=1/len(present); out=[]; check=defaultdict(float)
    for r in chosen:
        y=int(r["draft_year"])
        if y not in present: continue
        key=(y,str(r["cell"])); x=dict(r)
        x["_w"]=share*float(r["cell_weight_v5_1"])/raw[key]
        out.append(x); check[key]+=x["_w"]
    for y in present:
        for c in CELLS:
            if not math.isclose(check[(y,c)],share,abs_tol=1e-12,rel_tol=0): raise GateError("weight normalization failure")
    return out,{"years_used":list(present),"row_n":len(out),"by_year_cell":{f"{y}:{c}":{"row_n":counts[(y,c)],"weight_total":check[(y,c)]} for y in present for c in CELLS}}
def cell_mae(rows, values, horizon, field):
    d=defaultdict(float)
    for r in rows:
        y=get_outcome(r,horizon,field)
        if y is None: raise GateError("missing scored outcome")
        d[str(r["cell"])]+=float(r["_w"])*abs(float(values[str(r["cell"])])-y)
    return {c:d[c] for c in CELLS}
def macro(cm): return sum(float(cm[c]) for c in CELLS)/6
def year_mae(base, values, year):
    rows,_=weighted_rows(base,"H3","O2",years=(year,))
    return macro(cell_mae(rows,values,"H3","O2"))
def normalized_shape(d):
    m=sum(float(d[c]) for c in CELLS)/6
    if m<=0: raise GateError("nonpositive shape mean")
    return {c:float(d[c])/m for c in CELLS}
def o1_targets(rows):
    d=defaultdict(float)
    for r in rows:
        v=get_outcome(r,"H3","O1")
        if v is None: raise GateError("missing H3 O1")
        d[str(r["cell"])]+=float(r["_w"])*v
    return {c:d[c] for c in CELLS}
def shape_error(targets,values):
    a=normalized_shape(targets); b=normalized_shape(values)
    return sum(abs(a[c]-b[c]) for c in CELLS)/6
def score_set(base,candidates):
    h3,h3diag=weighted_rows(base,"H3","O2")
    o1,o1diag=weighted_rows(base,"H3","O1")
    h2,h2diag=weighted_rows(base,"H2","O2",require_h3=True)
    h4,h4diag=weighted_rows(base,"H4","O2",mature=True,require_h3=True)
    targets=o1_targets(o1); scores={}
    for cid in CANDIDATES:
        rec=candidates[cid]; values={c:float(rec["r1_r2_values"][c]) for c in CELLS}
        h3m=macro(cell_mae(h3,values,"H3","O2"))
        h2m=macro(cell_mae(h2,values,"H2","O2")); h2h3=macro(cell_mae(h2,values,"H3","O2"))
        h4m=macro(cell_mae(h4,values,"H4","O2")); h4h3=macro(cell_mae(h4,values,"H3","O2"))
        scores[cid]={
          "effective_parameters":int(rec["effective_parameters"]),
          "frozen_parameters":rec["parameters"],
          "frozen_r1_r2_values":values,
          "primary_h3_o2":{"macro_mae":h3m,"macro_mae_by_year":{"2022":year_mae(base,values,2022),"2023":year_mae(base,values,2023)}},
          "o1_shape":{"normalized_shape_error":shape_error(targets,values)},
          "H2_o2":{"macro_mae":h2m,"matched_H3_macro_mae":h2h3,"relative_regression_vs_matched_H3":(h2m-h2h3)/h2h3},
          "mature_H4_o2":{"macro_mae":h4m,"matched_H3_macro_mae":h4h3,"relative_regression_vs_matched_H3":(h4m-h4h3)/h4h3,"years_used":h4diag["years_used"]},
          "structural_diagnostics_from_frozen_fit":rec["structural_diagnostics"]
        }
    return scores,{"H3_O2":h3diag,"H3_O1":o1diag,"H2_matched":h2diag,"H4_mature_matched":h4diag,"empirical_H3_O1_cell_targets":targets}
def clean(obj):
    if isinstance(obj,float):
        if not math.isfinite(obj): raise GateError("nonfinite result")
        return round(obj,10)
    if isinstance(obj,dict): return {k:clean(v) for k,v in obj.items()}
    if isinstance(obj,list): return [clean(v) for v in obj]
    return obj

def main():
    pre=load(PREREG); ident=load(ID_SUMMARY); identm=load(ID_MANIFEST); p3=load(P3_MANIFEST); p3s=load(P3_SUMMARY); fit=load(FIT); fitm=load(FIT_MANIFEST); metric=load(METRIC)
    if metric["status"]!="FROZEN_BEFORE_VALIDATION_PARSE": raise GateError("metric contract not frozen")
    if fitm["development_fit_frozen"] is not True or fit["validation_outcomes_read"] is not False or fit["validation_scored"] is not False: raise GateError("fit firewall drift")
    if p3["output_hashes"][VALIDATION.name] != sha(VALIDATION): raise GateError("validation hash drift")
    if p3s["locked_validation_occurrence_n"] != 4164: raise GateError("validation count drift")
    coverage=float(ident["identity_gate"]["pick_occurrence_coverage"])
    if identm["identity_gate_pass"] is not True or coverage<0.95: raise GateError("identity gate drift")
    candidates=fit["primary"]["candidates"]
    if set(candidates)!=set(CANDIDATES): raise GateError("candidate set drift")
    for cid in CANDIDATES:
        if candidates[cid]["selected_winner"] is not False: raise GateError("prevalidation winner found")

    raw=read_jsonl(VALIDATION)
    if len(raw)!=4164: raise GateError(f"expected 4164 validation rows, got {len(raw)}")
    primary=base_rows(raw); nonidp=base_rows(raw,non_idp=True)
    scores,diag=score_set(primary,candidates); nscores,ndiag=score_set(nonidp,candidates)

    c0=scores["C0_DEPLOYED"]; c0mae=float(c0["primary_h3_o2"]["macro_mae"]); c0shape=float(c0["o1_shape"]["normalized_shape_error"])
    gates={}; eligible=[]
    for cid in WINNER_POOL:
        s=scores[cid]; mae=float(s["primary_h3_o2"]["macro_mae"]); by=s["primary_h3_o2"]["macro_mae_by_year"]; cby=c0["primary_h3_o2"]["macro_mae_by_year"]
        structural=s["structural_diagnostics_from_frozen_fit"]
        g={
          "validation_macro_mae_improvement_ge_5pct":(c0mae-mae)/c0mae >= 0.05-1e-12,
          "improves_2022_vs_C0":float(by["2022"])<float(cby["2022"]),
          "improves_2023_vs_C0":float(by["2023"])<float(cby["2023"]),
          "o1_shape_regression_le_2pct":float(s["o1_shape"]["normalized_shape_error"])/c0shape-1 <= 0.02+1e-12,
          "H2_regression_vs_matched_H3_le_2pct":float(s["H2_o2"]["relative_regression_vs_matched_H3"]) <= 0.02+1e-12,
          "mature_H4_regression_vs_matched_H3_le_2pct":float(s["mature_H4_o2"]["relative_regression_vs_matched_H3"]) <= 0.02+1e-12,
          "all_six_r1_r2_positive":all(float(s["frozen_r1_r2_values"][c])>0 for c in CELLS),
          "all_18_monotone_nonincreasing":structural["all_18_monotone_nonincreasing"] is True,
          "r3_r6_unchanged":structural["r3_r6_unchanged"] is True,
          "identity_resolution_ge_95pct":coverage>=0.95,
          "no_forbidden_prevalidation_data_read":fit["market_or_ktc_values_read"] is False and fit["package_vote_data_read"] is False and fit["validation_outcomes_read"] is False and fit["validation_scored"] is False and fit["candidate_selection_performed"] is False
        }
        passed=all(g.values())
        gates[cid]={"eligible":passed,"validation_macro_mae_improvement_vs_C0":(c0mae-mae)/c0mae,"o1_shape_relative_regression_vs_C0":float(s["o1_shape"]["normalized_shape_error"])/c0shape-1,"gates":g}
        if passed: eligible.append(cid)

    selected=None
    if eligible:
        minmae=min(float(scores[c]["primary_h3_o2"]["macro_mae"]) for c in eligible)
        near=[c for c in eligible if float(scores[c]["primary_h3_o2"]["macro_mae"])<=minmae*1.01+1e-12]
        order={"C1_R1_GLOBAL_RESCALE":1,"C2_R1_R2_ROUND_RESCALE":2,"C3_R1_R2_LOW_PARAMETER_TIER_CURVE":3}
        near.sort(key=lambda c:(int(scores[c]["effective_parameters"]),order[c])); selected=near[0]
    decision="PASS_V5_LOCKED_VALIDATION_WINNER_FROZEN_HUMAN_REVIEW_REQUIRED" if selected else pre["selection"]["none_eligible"]
    for cid in CANDIDATES:
        scores[cid]["validation_eligibility"]=gates.get(cid,{"eligible":False,"baseline_not_in_winner_pool":True})
        scores[cid]["selected_winner"]=(cid==selected)

    result={
      "schema_version":1,"study_id":fit["study_id"],"stage":"phase5_locked_validation_scoring","status":"LOCKED_VALIDATION_SCORED_AND_FROZEN","generated_at_utc":datetime.now(timezone.utc).isoformat(),"decision":decision,"research_only":True,
      "validation_outcomes_read":True,"validation_scored":True,"candidate_fit_performed_in_phase5":False,"candidate_refit_performed":False,"candidate_parameters_changed":False,"candidate_selection_performed":True,
      "market_or_ktc_values_read":False,"package_vote_data_read":False,"year_discount_fit_or_changed":False,"r3_r6_fit_or_changed":False,"production_change_authorized":False,"automatic_production_promotion_allowed":False,
      "identity_resolution_coverage":coverage,"metric_contract_file":METRIC.name,"metric_contract_sha256":sha(METRIC),"locked_validation_occurrence_n":len(raw),"primary_scores":scores,"primary_sample_diagnostics":diag,"eligibility_gate_results":gates,"eligible_candidates":eligible,"selected_candidate":selected,"winner_does_not_authorize_production":True,
      "non_idp_validation_sensitivity":{"diagnostic_only":True,"used_for_selection":False,"scores":nscores,"sample_diagnostics":ndiag},
      "next_stage_authorized":True,"next_stage":"draft-pick-fv-v5-phase6-postselection-external-trade-replay-and-human-review" if selected else "draft-pick-fv-v5-phase6-closeout-no-candidate",
      "input_hashes":{PREREG.name:sha(PREREG),ID_SUMMARY.name:sha(ID_SUMMARY),ID_MANIFEST.name:sha(ID_MANIFEST),P3_MANIFEST.name:sha(P3_MANIFEST),P3_SUMMARY.name:sha(P3_SUMMARY),FIT.name:sha(FIT),FIT_MANIFEST.name:sha(FIT_MANIFEST),METRIC.name:sha(METRIC),VALIDATION.name:sha(VALIDATION)}
    }
    result=clean(result); OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")

    lines=["# Draft Pick FV V5 — Phase 5 Locked Validation","",f"**Decision:** `{decision}`","","| Candidate | H3 O2 macro MAE | Improvement vs C0 | 2022 better? | 2023 better? | 18-cell monotone? | Eligible |","|---|---:|---:|---|---|---|---|"]
    for cid in CANDIDATES:
        s=result["primary_scores"][cid]
        if cid=="C0_DEPLOYED": imp=0; g=None
        else: g=result["eligibility_gate_results"][cid]; imp=g["validation_macro_mae_improvement_vs_C0"]
        lines.append(f"| {cid} | {s['primary_h3_o2']['macro_mae']:.2f} | {imp:.2%} | {'—' if g is None else ('YES' if g['gates']['improves_2022_vs_C0'] else 'NO')} | {'—' if g is None else ('YES' if g['gates']['improves_2023_vs_C0'] else 'NO')} | {'YES' if s['structural_diagnostics_from_frozen_fit']['all_18_monotone_nonincreasing'] else 'NO'} | {'BASELINE' if g is None else ('YES' if g['eligible'] else 'NO')} |")
    lines += ["","## Selection","",f"Frozen candidate: **{selected}**." if selected else "No C1/C2/C3 candidate passed every preregistered gate. V5 stops with no R1/R2 production candidate.","","## Firewalls","","- Candidate refit after validation: **No**","- KTC/market evidence used: **No**","- Package-vote evidence used: **No**","- YEAR_DISCOUNT changed: **No**","- R3–R6 changed: **No**","- Production change authorized: **No**","","## Next step","",("Run the frozen external pick-trade replay audit and explicit human review before any separate production workflow." if selected else "Freeze the no-candidate closeout. Any new candidate family or structural constraint requires a new preregistered study; V5 cannot be refit after validation."),""]
    OUT_MD.write_text("\n".join(lines),encoding="utf-8")
    manifest={"schema_version":1,"study_id":result["study_id"],"stage":result["stage"],"status":result["status"],"generated_at_utc":result["generated_at_utc"],"decision":decision,"validation_outcomes_read":True,"validation_scored":True,"candidate_refit_performed":False,"candidate_parameters_changed":False,"candidate_selection_performed":True,"selected_candidate":selected,"eligible_candidate_n":len(eligible),"winner_does_not_authorize_production":True,"production_change_authorized":False,"next_stage":result["next_stage"],"input_hashes":result["input_hashes"],"output_hashes":{OUT.name:sha(OUT),OUT_MD.name:sha(OUT_MD)}}
    OUT_MANIFEST.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"DECISION={decision}"); print(f"ELIGIBLE={eligible}"); print(f"SELECTED={selected}")
    for cid in CANDIDATES: print(cid,f"H3_MAE={result['primary_scores'][cid]['primary_h3_o2']['macro_mae']:.4f}")

if __name__ == "__main__": main()
