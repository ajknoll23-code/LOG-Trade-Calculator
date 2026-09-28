from __future__ import annotations
import argparse, hashlib, json, math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

YEARS=tuple(range(2018,2024))
TIERS=("early","mid","late")
CELLS=tuple(f"r{r}_{t}" for r in range(1,7) for t in TIERS)
K_TOL_REL=0.10
MIN_IMPROVEMENT=0.05
BOUND_REL_TOL=1e-6
EPS=1e-12

class GateError(RuntimeError): pass

def now(): return datetime.now(timezone.utc).isoformat()
def sha(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p:Path): return json.loads(p.read_text())
def write_json(p:Path,o:Any): p.write_text(json.dumps(clean(o),indent=2,sort_keys=True)+"\n")
def clean(o:Any)->Any:
    if isinstance(o,float):
        if not math.isfinite(o): raise GateError('nonfinite')
        return round(o,10)
    if isinstance(o,np.floating): return clean(float(o))
    if isinstance(o,np.integer): return int(o)
    if isinstance(o,dict): return {str(k):clean(v) for k,v in o.items()}
    if isinstance(o,(list,tuple)): return [clean(v) for v in o]
    return o

def read_jsonl(p:Path):
    out=[]
    for n,line in enumerate(p.open(),1):
        if not line.strip(): continue
        x=json.loads(line)
        if not isinstance(x,dict): raise GateError(f'{p}:{n} row not object')
        out.append(x)
    return out

def outcome(r,h='H3',field='O2'):
    x=r.get(h)
    if not isinstance(x,dict): return None
    v=x.get(field)
    return float(v) if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(float(v)) else None

def cell_round(c): return int(c[1])

def baseline(pre):
    b=pre['frozen_primary_candidate']['deployed_pick_base_2027']
    return {f'r{r}_{t}':float(b[str(r)][t]) for r in range(1,7) for t in TIERS}

def structural(values):
    seq=[float(values[c]) for c in CELLS]
    return {
      'all_18_positive':all(v>0 for v in seq),
      'all_18_monotone_nonincreasing':all(seq[i]>=seq[i+1]-1e-10 for i in range(17)),
      'structural_gate_pass':all(v>0 for v in seq) and all(seq[i]>=seq[i+1]-1e-10 for i in range(17)),
    }

def at_bound(k,bounds):
    lo,hi=map(float,bounds); scale=max(1.0,abs(lo),abs(hi),abs(hi-lo)); tol=BOUND_REL_TOL*scale
    return {'value':k,'lower':lo,'upper':hi,'absolute_tolerance':tol,'at_lower':abs(k-lo)<=tol,'at_upper':abs(k-hi)<=tol,'at_hard_bound':abs(k-lo)<=tol or abs(k-hi)<=tol}

def validate_rows(rows):
    if len(rows)!=24970: raise GateError(f'expected 24970 rows got {len(rows)}')
    sparse=[r for r in rows if int(r['draft_year'])==2018 and int(r['round'])==6]
    if len(sparse)!=72: raise GateError(f'2018 R6 row drift {len(sparse)}')
    for c in ('r6_early','r6_mid','r6_late'):
        xs=[r for r in sparse if r['cell']==c]
        if len(xs)!=24: raise GateError(f'{c} occurrence drift')
        if sorted(set(int(r['source_membership_index']) for r in xs))!=list(range(1,7)):
            raise GateError(f'{c} source index drift')
        if any(r.get('source_sparse_2018_r6') is not True for r in xs): raise GateError('sparse label drift')
    ready=sum(1 for r in rows if r.get('primary_o2_ready') is True and outcome(r) is not None)
    if ready < int(math.ceil(24970*0.95)): raise GateError('H3 O2 readiness below frozen gate')

def build_variant(rows,kind,index=None):
    kept=[]
    for r0 in rows:
        if r0.get('primary_o2_ready') is not True or outcome(r0) is None: continue
        y=int(r0['draft_year']); rnd=int(r0['round'])
        if kind=='exclude_2018_r6' and y==2018 and rnd==6: continue
        if kind=='leave_one_source_index_out' and y==2018 and rnd==6 and int(r0['source_membership_index'])==int(index): continue
        kept.append(dict(r0))
    by=defaultdict(list)
    for r in kept: by[(int(r['draft_year']),str(r['cell']))].append(r)
    for y in YEARS:
        available=[c for c in CELLS if by[(y,c)]]
        expected=15 if kind=='exclude_2018_r6' and y==2018 else 18
        if len(available)!=expected: raise GateError(f'{kind}/{index}: {y} available cells {len(available)} != {expected}')
        share=(1.0/len(YEARS))/len(available)
        for c in available:
            xs=by[(y,c)]
            sw=sum(float(x['development_fit_weight_v8']) for x in xs)
            if sw<=0: raise GateError('nonpositive inherited cell weight')
            for x in xs: x['_variant_w']=share*float(x['development_fit_weight_v8'])/sw
            if not math.isclose(sum(x['_variant_w'] for x in xs),share,rel_tol=0,abs_tol=1e-12): raise GateError('cell renormalization drift')
    if not math.isclose(sum(r['_variant_w'] for r in kept),1.0,rel_tol=0,abs_tol=1e-12): raise GateError('variant weights do not sum to one')
    return kept

def fit_c1(rows,base,bounds):
    grouped=defaultdict(float)
    for r in rows: grouped[(str(r['cell']),float(outcome(r)))]+=float(r['_variant_w'])
    obs=[(c,y,w) for (c,y),w in sorted(grouped.items())]
    n=len(obs); cv=np.zeros(1+n,dtype=float); rr=[];cc=[];dd=[];b=[];rn=0
    for i,(cell,y,w) in enumerate(obs):
        cv[1+i]=w; a=float(base[cell])
        rr.extend((rn,rn));cc.extend((0,1+i));dd.extend((a,-1.0));b.append(y);rn+=1
        rr.extend((rn,rn));cc.extend((0,1+i));dd.extend((-a,-1.0));b.append(-y);rn+=1
    A=coo_matrix((np.asarray(dd),(rr,cc)),shape=(rn,1+n)).tocsr()
    res=linprog(cv,A_ub=A,b_ub=np.asarray(b),bounds=[tuple(map(float,bounds))]+[(0,None)]*n,method='highs')
    if not res.success: raise GateError(f'C1 LAD failed: {res.message}')
    k=float(res.x[0]); vals={c:base[c]*k for c in CELLS}
    return {'k':k,'training_weighted_mae':float(res.fun),'values':vals,'boundary':at_bound(k,bounds),'structural':structural(vals)}

def mae(rows,values,tail=False):
    xs=[r for r in rows if not tail or cell_round(str(r['cell']))>=5]
    if not xs: raise GateError('empty evaluation slice')
    denom=sum(float(r['_variant_w']) for r in xs)
    if denom<=0: raise GateError('zero eval weight')
    return sum(float(r['_variant_w'])*abs(float(values[str(r['cell'])])-float(outcome(r))) for r in xs)/denom

def evaluate(rows,base,k):
    c0=dict(base); cand={c:base[c]*float(k) for c in CELLS}
    c0_all=mae(rows,c0); ca_all=mae(rows,cand)
    c0_tail=mae(rows,c0,True); ca_tail=mae(rows,cand,True)
    return {
      'k':float(k),'h3_o2_macro_mae':ca_all,'c0_h3_o2_macro_mae':c0_all,
      'h3_o2_improvement_vs_C0':(c0_all-ca_all)/c0_all,
      'r5_r6_h3_o2_macro_mae':ca_tail,'c0_r5_r6_h3_o2_macro_mae':c0_tail,
      'r5_r6_h3_o2_improvement_vs_C0':(c0_tail-ca_tail)/c0_tail,
      'structural':structural(cand),
    }

def run(args):
    pre=load(Path(args.prereg)); rows=read_jsonl(Path(args.phase2_dir)/'v8_phase2_development_outcomes.jsonl'); out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True)
    validate_rows(rows)
    assert pre['decision']=='FREEZE_V8_1_C1_CARRYFORWARD_SPARSE_SENSITIVITY_NEXT'
    assert pre['evidence_status']['2024_rookie_holdout_outcomes_read'] is False
    assert pre['phase1_sparse_tail_sensitivity']['must_run_before_2024_holdout'] is True
    assert pre['phase1_sparse_tail_sensitivity']['selection_or_tuning_allowed_from_sensitivity'] is False
    k0=float(pre['frozen_primary_candidate']['k']); bounds=tuple(pre['frozen_primary_candidate']['k_hard_bounds_from_v8']); base=baseline(pre)
    frozen_values={c:base[c]*k0 for c in CELLS}
    for c in CELLS:
        rr=str(cell_round(c)); t=c.split('_',1)[1]
        if not math.isclose(float(pre['frozen_primary_candidate']['frozen_candidate_pick_base_2027'][rr][t]),frozen_values[c],rel_tol=0,abs_tol=1e-7): raise GateError('frozen candidate value drift')

    primary_rows=build_variant(rows,'primary')
    primary_refit=fit_c1(primary_rows,base,bounds)
    if not math.isclose(primary_refit['k'],k0,rel_tol=0,abs_tol=1e-7): raise GateError(f'full-corpus C1 reproduction drift {primary_refit["k"]} vs {k0}')
    primary_fixed=evaluate(primary_rows,base,k0)

    variants=[]
    specs=[('exclude_2018_r6',None)]+[('leave_one_source_index_out',i) for i in range(1,7)]
    for kind,index in specs:
        vr=build_variant(rows,kind,index)
        fit=fit_c1(vr,base,bounds)
        fixed=evaluate(vr,base,k0); refit=evaluate(vr,base,fit['k'])
        rel=(fit['k']/k0)-1.0
        gates={
          'diagnostic_k_within_10pct_of_frozen_primary':abs(rel)<=K_TOL_REL+EPS,
          'frozen_primary_h3_o2_improvement_ge_5pct':fixed['h3_o2_improvement_vs_C0']>=MIN_IMPROVEMENT-EPS,
          'diagnostic_refit_h3_o2_improvement_ge_5pct':refit['h3_o2_improvement_vs_C0']>=MIN_IMPROVEMENT-EPS,
          'frozen_primary_r5_r6_h3_o2_improvement_ge_5pct':fixed['r5_r6_h3_o2_improvement_vs_C0']>=MIN_IMPROVEMENT-EPS,
          'diagnostic_refit_r5_r6_h3_o2_improvement_ge_5pct':refit['r5_r6_h3_o2_improvement_vs_C0']>=MIN_IMPROVEMENT-EPS,
          'diagnostic_refit_not_at_hard_bound':fit['boundary']['at_hard_bound'] is False,
          'frozen_primary_curve_structurally_valid':fixed['structural']['structural_gate_pass'] is True,
          'diagnostic_refit_curve_structurally_valid':fit['structural']['structural_gate_pass'] is True,
        }
        variants.append({
          'variant_id':'exclude_all_2018_r6' if kind=='exclude_2018_r6' else f'leave_2018_r6_source_index_{index}_out',
          'kind':kind,'source_membership_index_omitted':index,'retained_ready_occurrence_n':len(vr),
          'diagnostic_refit_k':fit['k'],'diagnostic_refit_k_relative_to_frozen_primary':rel,
          'diagnostic_refit_boundary':fit['boundary'],'fixed_primary_evaluation':fixed,'diagnostic_refit_evaluation':refit,
          'gates':gates,'pass':all(gates.values()),
        })

    all_pass=all(v['pass'] for v in variants)
    decision=pre['phase1_sparse_tail_sensitivity']['pass_decision'] if all_pass else pre['phase1_sparse_tail_sensitivity']['failure_decision']
    result={
      'schema_version':1,'study_id':pre['study_id'],'stage':'phase1_sparse_tail_sensitivity','status':'SPARSE_TAIL_SENSITIVITY_PASS' if all_pass else 'SPARSE_TAIL_SENSITIVITY_STOP','generated_at_utc':now(),'decision':decision,'research_only':True,
      'implementation_resolution':{
        'seven_diagnostic_refits':'one exclude-all-2018-R6 refit plus six leave-one-source-membership-index refits; the full-corpus run only reproduces the already-frozen primary k',
        'variant_evaluation_gate':'both the unchanged frozen-primary curve and the diagnostic-refit curve must retain >=5% overall H3 O2 and combined available R5-R6 H3 O2 improvement vs C0; diagnostic refits remain non-selectable',
        'tail_metric':'variant-weighted H3 O2 MAE over available R5-R6 observations with variant weights renormalized over that tail slice',
        'fit_method':'same one-parameter weighted LAD/HiGHS objective as V8 C1, using the variant weighting contract',
      },
      'frozen_primary':{'candidate_id':pre['frozen_primary_candidate']['candidate_id'],'k':k0,'full_corpus_reproduction_refit_k':primary_refit['k'],'full_corpus_reproduction_abs_difference':abs(primary_refit['k']-k0),'fixed_primary_evaluation':primary_fixed,'candidate_parameter_changed':False},
      'variant_n':len(variants),'variants':variants,
      'aggregate_gates':{
        'all_7_diagnostic_k_within_10pct':all(v['gates']['diagnostic_k_within_10pct_of_frozen_primary'] for v in variants),
        'all_7_overall_improvement_gates_pass':all(v['gates']['frozen_primary_h3_o2_improvement_ge_5pct'] and v['gates']['diagnostic_refit_h3_o2_improvement_ge_5pct'] for v in variants),
        'all_7_r5_r6_improvement_gates_pass':all(v['gates']['frozen_primary_r5_r6_h3_o2_improvement_ge_5pct'] and v['gates']['diagnostic_refit_r5_r6_h3_o2_improvement_ge_5pct'] for v in variants),
        'all_7_refits_off_hard_bounds':all(v['gates']['diagnostic_refit_not_at_hard_bound'] for v in variants),
        'all_generated_curves_structurally_valid':all(v['gates']['frozen_primary_curve_structurally_valid'] and v['gates']['diagnostic_refit_curve_structurally_valid'] for v in variants),
      },
      'sparse_sensitivity_gate_pass':all_pass,
      'selection_or_tuning_performed':False,'primary_candidate_refit_or_changed':False,'2024_holdout_pick_identity_file_read':False,'2024_holdout_rookie_outcomes_read':False,'2024_holdout_outcomes_remain_sealed':True,'market_or_ktc_values_read':False,'package_vote_data_read':False,'production_change_authorized':False,
      '2024_H2_outcome_open_authorized_next_stage':all_pass,
      'next_stage':'draft-pick-fv-v8-1-phase2-2024-h2-independent-confirmation' if all_pass else None,
      'input_hashes':{'preregistration':sha(Path(args.prereg)),'v8_phase2_development_outcomes.jsonl':sha(Path(args.phase2_dir)/'v8_phase2_development_outcomes.jsonl')},
    }
    rp=out/'v8_1_phase1_sparse_tail_sensitivity.json';write_json(rp,result)
    manifest={'schema_version':1,'study_id':pre['study_id'],'stage':'phase1_sparse_tail_sensitivity_manifest','status':result['status'],'decision':decision,'sparse_sensitivity_gate_pass':all_pass,'primary_candidate_k':k0,'primary_candidate_changed':False,'variant_n':7,'2024_holdout_outcomes_read':False,'2024_H2_outcome_open_authorized_next_stage':all_pass,'production_change_authorized':False,'result_sha256':sha(rp),'next_stage':result['next_stage']}
    mp=out/'v8_1_phase1_sparse_tail_sensitivity_manifest.json';write_json(mp,manifest)
    lines=['# Draft Pick FV V8.1 — Phase 1 Sparse Tail Sensitivity','',f'**Decision:** `{decision}`','',f'- Frozen primary k: **{k0:.10f}**',f'- Full-corpus reproduction k: **{primary_refit["k"]:.10f}**',f'- Diagnostic variants passing: **{sum(v["pass"] for v in variants)} / 7**','', '| Variant | refit k | Δk vs frozen | fixed H3 imp | refit H3 imp | fixed R5-R6 imp | refit R5-R6 imp | Pass |','|---|---:|---:|---:|---:|---:|---:|---|']
    for v in variants:
        lines.append(f'| {v["variant_id"]} | {v["diagnostic_refit_k"]:.10f} | {v["diagnostic_refit_k_relative_to_frozen_primary"]:.3%} | {v["fixed_primary_evaluation"]["h3_o2_improvement_vs_C0"]:.2%} | {v["diagnostic_refit_evaluation"]["h3_o2_improvement_vs_C0"]:.2%} | {v["fixed_primary_evaluation"]["r5_r6_h3_o2_improvement_vs_C0"]:.2%} | {v["diagnostic_refit_evaluation"]["r5_r6_h3_o2_improvement_vs_C0"]:.2%} | {"PASS" if v["pass"] else "FAIL"} |')
    lines += ['', '- 2024 rookie holdout outcomes read: **No**', '- Primary candidate changed/refit for selection: **No**', '- Production change authorized: **No**']
    (out/'v8_1_phase1_sparse_tail_sensitivity.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines));print('NEXT_STAGE=',result['next_stage'])

def check(args):
    out=Path(args.out_dir);r=load(out/'v8_1_phase1_sparse_tail_sensitivity.json');m=load(out/'v8_1_phase1_sparse_tail_sensitivity_manifest.json')
    allowed={'PASS_V8_1_SPARSE_TAIL_SENSITIVITY_AUTHORIZE_2024_H2_ONCE','STOP_V8_1_SPARSE_TAIL_SENSITIVITY'}
    assert r['decision'] in allowed and m['decision']==r['decision']; assert r['variant_n']==7 and len(r['variants'])==7
    assert r['primary_candidate_refit_or_changed'] is False and r['selection_or_tuning_performed'] is False
    assert r['2024_holdout_rookie_outcomes_read'] is False and r['2024_holdout_outcomes_remain_sealed'] is True
    assert r['production_change_authorized'] is False
    assert bool(r['sparse_sensitivity_gate_pass'])==bool(r['2024_H2_outcome_open_authorized_next_stage'])
    assert sha(out/'v8_1_phase1_sparse_tail_sensitivity.json')==m['result_sha256']
    print('PASS: Phase 1 output validation')

def selftest():
    vals={'r1_early':10,'r1_mid':9,'r1_late':8,'r2_early':7,'r2_mid':6,'r2_late':5,'r3_early':4.5,'r3_mid':4,'r3_late':3.5,'r4_early':3,'r4_mid':2.8,'r4_late':2.6,'r5_early':2.4,'r5_mid':2.2,'r5_late':2,'r6_early':1.8,'r6_mid':1.5,'r6_late':1.2}
    assert structural(vals)['structural_gate_pass']; assert at_bound(0.1,(0.1,1.25))['at_hard_bound']; assert not at_bound(.35,(.1,1.25))['at_hard_bound']; print('PASS: selftest')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--fit',action='store_true');ap.add_argument('--check',action='store_true');ap.add_argument('--selftest',action='store_true');ap.add_argument('--prereg');ap.add_argument('--phase2-dir');ap.add_argument('--out-dir');a=ap.parse_args()
    if a.selftest:selftest()
    elif a.fit:run(a)
    elif a.check:check(a)
    else:raise SystemExit('choose --fit/--check/--selftest')
if __name__=='__main__':main()
