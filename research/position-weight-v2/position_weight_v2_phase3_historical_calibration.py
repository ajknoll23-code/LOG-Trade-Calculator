#!/usr/bin/env python3
"""Position Weight V2 Phase 3 — research-only historical calibration.

Uses Phase-2 current-2026-rules structural lineup utility as the future target.
Every candidate is evaluated across all four frozen Replacement Level V2 rank
families. Global multiplicative scale is re-fit on training data per fold so it
cannot select the winning POSITION_WEIGHT family.
"""
from __future__ import annotations
import argparse, hashlib, json, math, statistics
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve(); REPO_ROOT = SCRIPT_PATH.parents[2]
PW1 = REPO_ROOT/'research'/'position-weight-v2'/'position_weight_v2_phase1_architecture_audit.json'
PW2 = REPO_ROOT/'research'/'position-weight-v2'/'position_weight_v2_phase2_ruleset_simulation.json'
POINTS = REPO_ROOT/'research'/'roster-economics'/'weekly_points_by_season.json'
REPL = REPO_ROOT/'research'/'replacement-level-v2'/'replacement_level_v2_phase5_frozen_candidates.json'
OUTJ = REPO_ROOT/'research'/'position-weight-v2'/'position_weight_v2_phase3_historical_calibration.json'
OUTM = REPO_ROOT/'research'/'position-weight-v2'/'position_weight_v2_phase3_historical_calibration.md'
METHOD='position-weight-v2-phase3-historical-calibration-v1'
POS=('QB','RB','WR','TE','DL','LB','DB')
FAMILIES=('legacy_control','prior_limited_evidence','stable_positions_only','full_phase2_leaders')
ALPHAS=(0.0,0.25,0.5,0.75,1.0); WINDOWS=(2,4,6); PRIMARY=4
MIN_GAMES=3

def load(p):
    if not p.exists(): raise RuntimeError(f'missing input: {p.relative_to(REPO_ROOT)}')
    return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def clamp(x,a,b): return max(a,min(b,x))
def pm(ppg,base): return clamp(-0.10+0.75*(ppg/base),0.15,1.55) if base and base>0 else None
def akey(a): return f'shrink_{int(round(a*100)):03d}'
def med(xs):
    x=[float(v) for v in xs if v is not None and math.isfinite(float(v))]; return statistics.median(x) if x else None
def avg(xs):
    x=[float(v) for v in xs if v is not None and math.isfinite(float(v))]; return statistics.fmean(x) if x else None
def pct(v,c): return ((v-c)/c) if v is not None and c not in (None,0) else None
def rnd(o,d=6):
    if isinstance(o,dict): return {k:rnd(v,d) for k,v in o.items()}
    if isinstance(o,list): return [rnd(v,d) for v in o]
    if isinstance(o,float): return round(o,d) if math.isfinite(o) else None
    return o

def validate(p1,p2,repl):
    if p1.get('method_version')!='position-weight-v2-phase1-architecture-audit-v1': raise RuntimeError('bad Phase1 method')
    if p2.get('method_version')!='position-weight-v2-phase2-ruleset-simulation-v1': raise RuntimeError('bad Phase2 method')
    if repl.get('method_version')!='replacement-level-v2-phase5-prospective-v1': raise RuntimeError('bad replacement method')
    for name,p in [('Phase1',p1),('Phase2',p2)]:
        for f in ('deployment_authorized','position_weight_change_authorized','replacement_rank_change_authorized','production_v2_change_authorized','transform_change_authorized','scale_change_authorized'):
            if p.get(f) is not False: raise RuntimeError(f'{name} guardrail changed: {f}')
        if p.get('frozen_prospective_experiments_touched') is not False: raise RuntimeError(f'{name} frozen guardrail changed')
    if repl.get('variant_manifest')!=list(FAMILIES): raise RuntimeError('replacement family manifest changed')
    mae=((p2.get('historical_validation') or {}).get('mean_of_season_mae_starters_per_team_week'))
    if mae is None or float(mae)>0.25: raise RuntimeError(f'allocator validation too weak: {mae}')

def season_players(points,season):
    p=(points.get('seasons') or {}).get(season)
    if not isinstance(p,dict): raise RuntimeError(f'missing season {season}')
    return p

def wval(rec,w):
    wk=rec.get('weekly_points') or {}; v=wk.get(str(w),wk.get(w))
    if v is None: return None
    try: v=float(v)
    except: return None
    return v if math.isfinite(v) else None

def start_counts(p2,season):
    rows=(((p2.get('current_rules_on_historical_scoring_samples') or {}).get(season) or {}).get('weekly') or [])
    if not rows: raise RuntimeError(f'missing Phase2 weekly rows {season}')
    return {int(r['week']):{p:int(((r.get('positions') or {}).get(p) or {}).get('simulated_starts') or 0) for p in POS} for r in rows}

def selected_ids(points,p2,season):
    players=season_players(points,season); counts=start_counts(p2,season); out={}
    for w,cnt in sorted(counts.items()):
        by={p:[] for p in POS}
        for pid,r in players.items():
            p=str(r.get('pos_bucket') or '').upper(); v=wval(r,w)
            if p in by and v is not None: by[p].append((str(pid),v))
        out[w]={}
        for p in POS:
            rows=sorted(by[p],key=lambda z:(-z[1],z[0])); n=cnt[p]
            if len(rows)<n: raise RuntimeError(f'{season} w{w} {p}: only {len(rows)} for {n} starts')
            out[w][p]=set(pid for pid,_ in rows[:n])
    return out

def maps(points,selected,season,weeks,min_games=0):
    players=season_players(points,season); out={}; W=sorted(set(weeks))
    for pid,r in players.items():
        p=str(r.get('pos_bucket') or '').upper()
        if p not in POS: continue
        pts=[]; util=[]
        for w in W:
            v=wval(r,w)
            if v is None: continue
            pts.append(v); util.append(v if str(pid) in selected.get(w,{}).get(p,set()) else 0.0)
        if len(pts)<min_games or not pts: continue
        out[str(pid)]={'pos':p,'name':r.get('name') or str(pid),'ppg':statistics.fmean(pts),'utility':statistics.fmean(util),'games':len(pts)}
    return out

def baseline(training,ranks):
    out={}
    for p in POS:
        vals=sorted([r['ppg'] for r in training.values() if r['pos']==p],reverse=True); rank=int(ranks[p])
        if len(vals)<rank or vals[rank-1]<=0: return None
        out[p]=float(vals[rank-1])
    return out

def with_pm(training,bases):
    return {pid:{**r,'pm':pm(r['ppg'],bases[r['pos']])} for pid,r in training.items()}

def fitted_weights(rows,deployed):
    slopes={}
    for p in POS:
        rr=[r for r in rows.values() if r['pos']==p]; den=sum(r['pm']**2 for r in rr); num=sum(r['pm']*r['utility'] for r in rr)
        if den<=0:return None
        slopes[p]=num/den
    if slopes['WR']<=0:return None
    fitted={p:slopes[p]/slopes['WR'] for p in POS}; fitted['WR']=1.0
    return fitted

def shrink(deployed,fitted,a):
    w={p:deployed[p]+a*(fitted[p]-deployed[p]) for p in POS}; w['WR']=1.0
    if any(v<=0 for v in w.values()): raise RuntimeError('nonpositive candidate weight')
    return w

def gscale(rows,w):
    xy=[]
    for r in rows.values(): xy.append((w[r['pos']]*r['pm'],r['utility']))
    den=sum(x*x for x,_ in xy)
    return sum(x*y for x,y in xy)/den if den>0 else None

def pairacc(rows):
    correct=0.0; total=0
    for i in range(len(rows)):
        pi,xi,yi=rows[i]
        for j in range(i+1,len(rows)):
            pj,xj,yj=rows[j]
            if pi==pj or yi==yj: continue
            total+=1; dp=xi-xj; da=yi-yj
            if dp==0: correct+=0.5
            elif (dp>0)==(da>0): correct+=1
    return correct/total if total else None

def eval_future(future,train,w,g):
    errs={p:[] for p in POS}; pairs=[]
    for pid,t in future.items():
        r=train.get(pid)
        if not r: continue
        pred=g*w[t['pos']]*r['pm']; actual=t['utility']; e=pred-actual
        errs[t['pos']].append(e); pairs.append((t['pos'],pred,actual))
    maes={p:(statistics.fmean(abs(e) for e in es) if es else None) for p,es in errs.items()}
    rms={p:(math.sqrt(statistics.fmean(e*e for e in es)) if es else None) for p,es in errs.items()}
    vm=[x for x in maes.values() if x is not None]; vr=[x for x in rms.values() if x is not None]
    allerr=[e for es in errs.values() for e in es]
    return {'n':len(allerr),'positions_available':len(vm),'position_balanced_mae':avg(vm),'position_balanced_rmse':avg(vr),'pooled_mae':avg([abs(e) for e in allerr]),'cross_position_pairwise_accuracy':pairacc(pairs),'by_position_mae':maes}

def folds(points,p2,window):
    out=[]
    for season in ('2024','2025'):
        sel=selected_ids(points,p2,season); weeks=sorted(sel); mx=max(weeks)
        for predw in range(9,16):
            tw=list(range(predw,predw+window))
            if tw[-1]>mx: continue
            tr=[w for w in weeks if w<predw]
            out.append({'name':f'{season}_wk{predw}','training':maps(points,sel,season,tr,MIN_GAMES),'future':maps(points,sel,season,tw,0)})
    # same cross-season robustness fold for each window sweep
    s24=selected_ids(points,p2,'2024'); s25=selected_ids(points,p2,'2025')
    out.append({'name':'2024_full_to_2025_full','training':maps(points,s24,'2024',sorted(s24),MIN_GAMES),'future':maps(points,s25,'2025',sorted(s25),0)})
    return out

def eval_fold(fold,ranks,deployed):
    bases=baseline(fold['training'],ranks)
    if bases is None:return None
    tr=with_pm(fold['training'],bases); fit=fitted_weights(tr,deployed)
    if fit is None:return None
    variants={}
    for a in ALPHAS:
        w=shrink(deployed,fit,a); g=gscale(tr,w)
        if not g or g<=0: continue
        variants[akey(a)]={'alpha':a,'weights':w,'training_global_scale':g,'future_metrics':eval_future(fold['future'],tr,w,g)}
    return {'fold_name':fold['name'],'fitted_weights':fit,'baselines':bases,'variants':variants}

def summarize(evals):
    out={}
    for a in ALPHAS:
        k=akey(a); rows=[]
        for e in evals:
            if e and k in e['variants']:
                m=e['variants'][k]['future_metrics']
                if m['position_balanced_mae'] is not None: rows.append(m)
        out[k]={'alpha':a,'n_folds':len(rows),'median_position_balanced_mae':med([r['position_balanced_mae'] for r in rows]),'mean_position_balanced_mae':avg([r['position_balanced_mae'] for r in rows]),'median_position_balanced_rmse':med([r['position_balanced_rmse'] for r in rows]),'median_cross_position_pairwise_accuracy':med([r['cross_position_pairwise_accuracy'] for r in rows])}
    ctl=out[akey(0.0)]['median_position_balanced_mae']
    for r in out.values(): r['mae_pct_vs_deployed_control']=pct(r['median_position_balanced_mae'],ctl)
    return out

def select_alpha(summaries):
    cand=[]
    for a in ALPHAS:
        k=akey(a); prim=[]; beats=0; nw=0; total=0
        for fam in FAMILIES:
            r=summaries[str(PRIMARY)][fam][k]; c=summaries[str(PRIMARY)][fam][akey(0.0)]
            if r['median_position_balanced_mae'] is not None and c['median_position_balanced_mae'] is not None:
                prim.append(r['median_position_balanced_mae']); beats+=int(r['median_position_balanced_mae']<c['median_position_balanced_mae'])
        for win in WINDOWS:
            for fam in FAMILIES:
                r=summaries[str(win)][fam][k]; c=summaries[str(win)][fam][akey(0.0)]
                if r['median_position_balanced_mae'] is not None and c['median_position_balanced_mae'] is not None:
                    total+=1; nw+=int(r['median_position_balanced_mae']<=c['median_position_balanced_mae'])
        cand.append({'alpha':a,'key':k,'mean_primary_mae_across_rank_families':avg(prim),'rank_families_beating_control_primary':beats,'window_family_comparisons_nonworse':nw,'window_family_comparisons_total':total})
    valid=[c for c in cand if c['mean_primary_mae_across_rank_families'] is not None]; valid.sort(key=lambda c:(c['mean_primary_mae_across_rank_families'],abs(c['alpha']-.5),c['alpha']))
    leader=valid[0]; share=leader['window_family_comparisons_nonworse']/leader['window_family_comparisons_total'] if leader['window_family_comparisons_total'] else 0
    leader['window_family_nonworse_share']=share; leader['historical_screen_pass']=bool(leader['alpha']>0 and leader['rank_families_beating_control_primary']>=3 and share>=.75)
    return {'candidates':cand,'selected':leader}

def full_history(points,p2):
    merged={}
    for season in ('2024','2025'):
        sel=selected_ids(points,p2,season); m=maps(points,sel,season,sorted(sel),0)
        players=season_players(points,season)
        for pid,r in players.items():
            p=str(r.get('pos_bucket') or '').upper()
            if p not in POS: continue
            row=merged.setdefault(str(pid),{'pos':p,'name':r.get('name') or str(pid),'pts':[],'util':[]})
            if row['pos']!=p: continue
            for w in sorted(sel):
                v=wval(r,w)
                if v is None: continue
                row['pts'].append(v); row['util'].append(v if str(pid) in sel[w][p] else 0.0)
    out={}
    for pid,r in merged.items():
        if len(r['pts'])>=MIN_GAMES: out[pid]={'pos':r['pos'],'name':r['name'],'ppg':statistics.fmean(r['pts']),'utility':statistics.fmean(r['util']),'games':len(r['pts'])}
    return out

def candidate_weights(points,p2,repl,deployed,a):
    tr=full_history(points,p2); by={}
    for fam in FAMILIES:
        ranks=repl['variants'][fam]['replacement_ranks']; bases=baseline(tr,ranks)
        rows=with_pm(tr,bases); fit=fitted_weights(rows,deployed); w=shrink(deployed,fit,a)
        by[fam]={'candidate_weights':w,'unshrunk_empirical_weights':fit,'baselines':bases}
    robust={p:med([by[f]['candidate_weights'][p] for f in FAMILIES]) for p in POS}; robust['WR']=1.0
    ranges={p:{'min':min(by[f]['candidate_weights'][p] for f in FAMILIES),'max':max(by[f]['candidate_weights'][p] for f in FAMILIES)} for p in POS}
    for p in POS:ranges[p]['range']=ranges[p]['max']-ranges[p]['min']
    return {'selected_alpha':a,'by_rank_family':by,'robust_median_candidate_weights':robust,'rank_family_weight_range':ranges}

def build():
    p1,p2,points,repl=load(PW1),load(PW2),load(POINTS),load(REPL); validate(p1,p2,repl)
    deployed={p:float(p1['current_position_weights'][p]) for p in POS}
    summaries={}; details={}
    for win in WINDOWS:
        fs=folds(points,p2,win); summaries[str(win)]={}; details[str(win)]={}
        for fam in FAMILIES:
            ranks=repl['variants'][fam]['replacement_ranks']; ev=[eval_fold(f,ranks,deployed) for f in fs]
            summaries[str(win)][fam]=summarize(ev); details[str(win)][fam]=ev
    selection=select_alpha(summaries); a=float(selection['selected']['alpha']); full=candidate_weights(points,p2,repl,deployed,a)
    phase4={'deployed_control':deployed}
    if selection['selected']['historical_screen_pass']: phase4['robust_empirical_candidate']=full['robust_median_candidate_weights']
    return rnd({'method_version':METHOD,'status':'RESEARCH_ONLY_POSITION_WEIGHT_HISTORICAL_CALIBRATION','deployment_authorized':False,'position_weight_change_authorized':False,'replacement_rank_change_authorized':False,'production_v2_change_authorized':False,'transform_change_authorized':False,'scale_change_authorized':False,'frozen_prospective_experiments_touched':False,'target_definition':{'future_target':'active-game structural lineup utility under 2026 roster slots','starter_utility':'league fantasy points scored that week','nonstarter_utility':0.0,'availability':'active-game conditional; missing-score weeks omitted to avoid re-testing Durability V2','individual_team_ownership_constraints':False},'prediction_definition':{'training_input':'trailing PPG before each fold','replacement_rank_families':list(FAMILIES),'pm_transform':{'intercept':-.1,'slope':.75,'floor':.15,'ceiling':1.55},'empirical_weight_fit':'utility ~= slope_pos * PM; slopes normalized to WR','shrink_alphas':list(ALPHAS),'global_scale_handling':'training-only multiplicative scale refit per candidate/fold'},'primary_metric':{'name':'median position-balanced MAE','forward_window_weeks':PRIMARY,'lower_is_better':True},'deployed_position_weights':deployed,'summary_by_window_and_rank_family':summaries,'alpha_selection':selection,'full_history_candidate_weights':full,'phase4_candidate_weights':phase4,'phase4_handoff':{'candidate_authorized_for_shadow_only':bool(selection['selected']['historical_screen_pass']),'selected_alpha':a,'current_board_shadow_required':True,'deployment_authorized':False,'replacement_rank_families_remain_frozen':True},'input_sha256':{str(PW1.relative_to(REPO_ROOT)):sha(PW1),str(PW2.relative_to(REPO_ROOT)):sha(PW2),str(POINTS.relative_to(REPO_ROOT)):sha(POINTS),str(REPL.relative_to(REPO_ROOT)):sha(REPL)}})

def fmt(v,d=4): return '—' if v is None else f'{float(v):.{d}f}'
def fpct(v): return '—' if v is None else f'{100*float(v):+.1f}%'
def md(r):
    sel=r['alpha_selection']['selected']; lines=['# Position Weight / Cross-Position Economics V2 — Phase 3 Historical Calibration','','**Research only. No POSITION_WEIGHT change is authorized.**','',f"Method: `{r['method_version']}`",'', '## Target','', 'Future target = **active-game structural lineup utility under the 2026 roster slots**. A structurally started player gets his league-scored points; an active nonstarter gets 0. Missing-score weeks are omitted so durability is not re-tested.','', 'Every candidate receives its own training-only global rescale, so only relative POSITION_WEIGHT differences can win.','', '## Alpha selection across all frozen replacement families','', '| Alpha | Mean primary MAE | Rank families beating control | Window×family non-worse |','|---:|---:|---:|---:|']
    for x in r['alpha_selection']['candidates']:
        share=x['window_family_comparisons_nonworse']/x['window_family_comparisons_total'] if x['window_family_comparisons_total'] else None
        lines.append(f"| {x['alpha']:.2f} | {fmt(x['mean_primary_mae_across_rank_families'])} | {x['rank_families_beating_control_primary']}/4 | {x['window_family_comparisons_nonworse']}/{x['window_family_comparisons_total']} ({fpct(share)}) |")
    lines += ['',f"Selected historical alpha: **{sel['alpha']:.2f}**",f"Historical screen: **{'PASS' if sel['historical_screen_pass'] else 'NO'}**",'', '## Primary 4-week results by replacement-rank family','', '| Rank family | Deployed MAE | Selected MAE | Δ vs deployed | Selected pairwise |','|---|---:|---:|---:|---:|']
    sk=akey(float(sel['alpha'])); ss=r['summary_by_window_and_rank_family']['4']
    for fam in FAMILIES:
        c=ss[fam][akey(0.0)]; x=ss[fam][sk]; lines.append(f"| `{fam}` | {fmt(c['median_position_balanced_mae'])} | {fmt(x['median_position_balanced_mae'])} | {fpct(x['mae_pct_vs_deployed_control'])} | {fmt(x['median_cross_position_pairwise_accuracy'])} |")
    lines += ['','## Full-history candidate weights','','These are **shadow candidates only**.','', '| Pos | Deployed | Robust median candidate | Family min | Family max |','|---|---:|---:|---:|---:|']
    full=r['full_history_candidate_weights']; dep=r['deployed_position_weights']; rob=full['robust_median_candidate_weights']; rr=full['rank_family_weight_range']
    for p in POS: lines.append(f"| {p} | {fmt(dep[p],3)} | {fmt(rob[p],3)} | {fmt(rr[p]['min'],3)} | {fmt(rr[p]['max'],3)} |")
    lines += ['','## Interpretation','','If the historical screen passes, Phase 4 may shadow the robust median candidate on the current board. Large rank-family spread is a warning that weight and replacement normalization are not cleanly separable for that position.','','## Guardrails','','- deployment_authorized: **false**','- position_weight_change_authorized: **false**','- replacement_rank_change_authorized: **false**','- production_v2_change_authorized: **false**','- transform_change_authorized: **false**','- scale_change_authorized: **false**','- frozen prospective experiments touched: **false**','']
    return '\n'.join(lines)

def selftest():
    assert abs(pm(10,10)-.65)<1e-12 and pm(0,10)==.15
    dep={'QB':1.3,'RB':.89,'WR':1,'TE':.82,'DL':.93,'LB':1.12,'DB':.87}; fit={**dep,'QB':1.5,'WR':1}
    assert abs(shrink(dep,fit,.5)['QB']-1.4)<1e-12
    rows={'a':{'pos':'WR','pm':1,'utility':10},'b':{'pos':'WR','pm':.5,'utility':5}}
    assert abs(gscale(rows,{'WR':1})-10)<1e-12
    print('PASS Position Weight V2 Phase 3 self-test.')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--selftest',action='store_true'); ap.add_argument('--write',action='store_true'); ap.add_argument('--check',action='store_true'); a=ap.parse_args()
    if a.selftest:
        selftest()
        if not a.write and not a.check:return
    r=build(); j=json.dumps(r,indent=2,sort_keys=True)+'\n'; m=md(r).rstrip()+'\n'
    if a.write:
        OUTJ.parent.mkdir(parents=True,exist_ok=True); OUTJ.write_text(j); OUTM.write_text(m); print(f'Wrote {OUTJ.relative_to(REPO_ROOT)}'); print(f'Wrote {OUTM.relative_to(REPO_ROOT)}')
    if a.check:
        if not OUTJ.exists() or not OUTM.exists(): raise RuntimeError('Phase3 outputs missing')
        if OUTJ.read_text()!=j: raise RuntimeError('Phase3 JSON stale/non-deterministic')
        if OUTM.read_text()!=m: raise RuntimeError('Phase3 markdown stale/non-deterministic')
        for f in ('deployment_authorized','position_weight_change_authorized','replacement_rank_change_authorized','production_v2_change_authorized','transform_change_authorized','scale_change_authorized'):
            if r.get(f) is not False: raise RuntimeError(f'guardrail failed: {f}')
        print('PASS Position Weight V2 Phase 3 checks.')
    if not a.write and not a.check and not a.selftest: print(m)
if __name__=='__main__': main()
