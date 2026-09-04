#!/usr/bin/env python3
"""Durability / Availability V2 Phase 1 historical audit. RESEARCH ONLY."""
from __future__ import annotations
import argparse, json, math, statistics, time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import requests

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
DEPLOYED = REPO_ROOT / 'scripts' / 'durability_results.json'
PPG = REPO_ROOT / 'scripts' / 'ppg_results.json'
OUT_JSON = REPO_ROOT / 'research' / 'durability-v2' / 'durability_v2_phase1_availability_audit.json'
OUT_MD = REPO_ROOT / 'research' / 'durability-v2' / 'durability_v2_phase1_availability_audit.md'
METHOD = 'durability-v2-phase1-availability-audit-v1'
POSITIONS = ('QB','RB','WR','TE','DL','LB','DB')
SEASONS = tuple(range(2015, 2026))
BASE_SEASONS = tuple(range(2015, 2025))
POS_BUCKET = {'QB':'QB','RB':'RB','WR':'WR','TE':'TE','DE':'DL','DT':'DL','NT':'DL','DL':'DL','EDGE':'DL','OLB':'LB','ILB':'LB','LB':'LB','CB':'DB','S':'DB','SS':'DB','FS':'DB','DB':'DB'}
NEAR_FULL = 0.88
SEVERE_LOW = 0.65
TIMEOUT = 60
SLEEP = 0.08

def read_json(path: Path):
    if not path.exists(): raise RuntimeError(f'Missing required input: {path.relative_to(REPO_ROOT)}')
    return json.loads(path.read_text(encoding='utf-8'))

def now_utc(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def scheduled_games(season): return 16 if season <= 2020 else 17
def regular_weeks(season): return 17 if season <= 2020 else 18
def clamp01(x): return max(0.0, min(1.0, float(x)))

def percentile(vals, q):
    if not vals: return None
    vals = sorted(float(v) for v in vals)
    if len(vals)==1: return vals[0]
    idx=(len(vals)-1)*max(0,min(1,q)); lo=math.floor(idx); hi=math.ceil(idx)
    if lo==hi: return vals[lo]
    t=idx-lo; return vals[lo]*(1-t)+vals[hi]*t

def rankdata(vals):
    indexed=sorted(enumerate(vals), key=lambda x:(x[1],x[0])); ranks=[0.0]*len(vals); i=0
    while i<len(indexed):
        j=i+1
        while j<len(indexed) and indexed[j][1]==indexed[i][1]: j+=1
        avg=((i+1)+j)/2.0
        for k in range(i,j): ranks[indexed[k][0]]=avg
        i=j
    return ranks

def pearson(xs, ys):
    if len(xs)!=len(ys) or len(xs)<5: return None
    mx=statistics.fmean(xs); my=statistics.fmean(ys); dx=[x-mx for x in xs]; dy=[y-my for y in ys]
    den=math.sqrt(sum(x*x for x in dx)*sum(y*y for y in dy))
    return None if den<=0 else sum(a*b for a,b in zip(dx,dy))/den

def spearman(xs, ys): return pearson(rankdata(xs), rankdata(ys)) if len(xs)>=5 else None

def bundle(xs, ys):
    r=pearson(xs,ys); s=spearman(xs,ys)
    return {'n':len(xs),'pearson_r':r,'pearson_r_squared':r*r if r is not None else None,'spearman':s,'mae_using_current_as_prediction':statistics.fmean(abs(a-b) for a,b in zip(xs,ys)) if xs else None,'mean_current_availability':statistics.fmean(xs) if xs else None,'mean_next_availability':statistics.fmean(ys) if ys else None}

def fetch_player_index(session):
    print('Fetching Sleeper NFL player index...')
    r=session.get('https://api.sleeper.app/v1/players/nfl',timeout=TIMEOUT); r.raise_for_status(); p=r.json()
    if not isinstance(p,dict) or len(p)<1000: raise RuntimeError('Sleeper player index malformed/sparse')
    return {str(k):v for k,v in p.items() if isinstance(v,dict)}

def build_pos_map(index):
    out={}
    for pid,row in index.items():
        p=POS_BUCKET.get(str(row.get('position') or '').upper().strip())
        if p in POSITIONS: out[pid]=p
    return out

def fetch_season(session, season):
    games=defaultdict(int); weekly_ids=set(); gp_ids=set(); malformed=0
    for week in range(1, regular_weeks(season)+1):
        print(f'  Sleeper {season} week {week}...')
        r=session.get(f'https://api.sleeper.app/v1/stats/nfl/regular/{season}/{week}',timeout=TIMEOUT); r.raise_for_status(); payload=r.json()
        if not isinstance(payload,dict): raise RuntimeError(f'{season} week {week} response not object')
        for pid,stats in payload.items():
            pid=str(pid); weekly_ids.add(pid)
            if not isinstance(stats,dict): malformed+=1; continue
            try: gp=float(stats.get('gp') or 0)
            except (TypeError,ValueError): malformed+=1; continue
            if gp>=1: games[pid]+=1; gp_ids.add(pid)
        time.sleep(SLEEP)
    maxg=scheduled_games(season)
    clipped={pid:min(int(g),maxg) for pid,g in games.items()}
    return clipped, {'season':season,'weekly_record_player_ids':len(weekly_ids),'gp_positive_player_ids':len(gp_ids),'malformed_rows':malformed,'players_clipped_above_schedule':sum(1 for g in games.values() if g>maxg)}

def build_player_seasons(season_games,posmap):
    rows=[]; unresolved=Counter()
    for season in SEASONS:
        maxg=scheduled_games(season)
        for pid,games in season_games[season].items():
            pos=posmap.get(pid)
            if pos not in POSITIONS: unresolved[str(season)]+=1; continue
            rows.append({'sleeper_id':pid,'season':season,'pos':pos,'games_played':int(games),'scheduled_games':maxg,'availability':clamp01(games/maxg)})
    rows.sort(key=lambda r:(r['season'],r['pos'],r['sleeper_id']))
    return rows, {'player_seasons':len(rows),'unresolved_gp_positive_player_seasons_by_season':dict(unresolved),'unresolved_gp_positive_player_seasons':sum(unresolved.values())}

def lookup(rows):
    out={}
    for r in rows:
        k=(r['sleeper_id'],int(r['season']))
        if k in out: raise RuntimeError(f'Duplicate player-season: {k}')
        out[k]=r
    return out

def transition_rows(rows):
    lu=lookup(rows); survivor=[]; unconditional=[]
    for r in rows:
        s=int(r['season'])
        if s not in BASE_SEASONS: continue
        nxt=lu.get((r['sleeper_id'],s+1))
        rec={'sleeper_id':r['sleeper_id'],'pos':r['pos'],'season':s,'current_availability':float(r['availability']),'next_availability':float(nxt['availability']) if nxt else 0.0,'next_season_observed':nxt is not None}
        unconditional.append(rec)
        if nxt is not None: survivor.append(dict(rec))
    return survivor,unconditional

def summarize_transitions(rows):
    def one(cohort): return bundle([float(r['current_availability']) for r in cohort],[float(r['next_availability']) for r in cohort])
    return {'overall':one(rows),'by_position':{p:one([r for r in rows if r['pos']==p]) for p in POSITIONS}}

def multiyear_rows(rows):
    lu=lookup(rows); out=[]
    for r in rows:
        s=int(r['season'])
        if s not in BASE_SEASONS: continue
        pid=r['sleeper_id']; cur=float(r['availability']); nxt=lu.get((pid,s+1)); target=float(nxt['availability']) if nxt else 0.0
        p1=lu.get((pid,s-1)); p2=lu.get((pid,s-2)); a1=float(p1['availability']) if p1 else None; a2=float(p2['availability']) if p2 else None
        out.append({'sleeper_id':pid,'pos':r['pos'],'season':s,'target_next_availability_unconditional':target,'current_availability':cur,'prior1_availability':a1,'prior2_availability':a2,'has_2year_history':a1 is not None,'has_3year_history':a1 is not None and a2 is not None,'mean_2year_availability':(cur+a1)/2 if a1 is not None else None,'recency_2year_availability':0.67*cur+0.33*a1 if a1 is not None else None,'mean_3year_availability':(cur+a1+a2)/3 if a1 is not None and a2 is not None else None,'recency_3year_availability':0.57*cur+0.29*a1+0.14*a2 if a1 is not None and a2 is not None else None})
    return out

def summarize_multiyear(rows):
    features=('current_availability','mean_2year_availability','recency_2year_availability','mean_3year_availability','recency_3year_availability')
    def one(cohort):
        out={}
        for f in features:
            pairs=[(float(r[f]),float(r['target_next_availability_unconditional'])) for r in cohort if r.get(f) is not None]
            out[f]=bundle([x for x,_ in pairs],[y for _,y in pairs])
        return out
    return {'overall':one(rows),'by_position':{p:one([r for r in rows if r['pos']==p]) for p in POSITIONS}}

def low_patterns(rows):
    groups={'one_year_low_after_near_full':[],'repeated_low_two_years':[],'current_near_full':[]}
    for r in rows:
        cur=float(r['current_availability']); prior=r.get('prior1_availability'); target=float(r['target_next_availability_unconditional'])
        if cur>=NEAR_FULL: groups['current_near_full'].append(target)
        if prior is None: continue
        prior=float(prior)
        if cur<SEVERE_LOW and prior>=NEAR_FULL: groups['one_year_low_after_near_full'].append(target)
        if cur<SEVERE_LOW and prior<SEVERE_LOW: groups['repeated_low_two_years'].append(target)
    return {k:{'n':len(v),'mean_next_availability':statistics.fmean(v) if v else None,'median_next_availability':statistics.median(v) if v else None,'p25_next_availability':percentile(v,0.25),'p75_next_availability':percentile(v,0.75)} for k,v in groups.items()}

def deployed_compare(deployed,surv,uncond):
    out={}
    for p in POSITIONS:
        d=(deployed.get(p) or {}).get('r_squared'); d=float(d) if d is not None else None; sr=surv['by_position'][p]['pearson_r_squared']; ur=uncond['by_position'][p]['pearson_r_squared']
        out[p]={'deployed_own_weight_r_squared':d,'phase1_survivor_only_r_squared':sr,'phase1_unconditional_r_squared':ur,'survivor_minus_deployed':sr-d if sr is not None and d is not None else None,'unconditional_minus_deployed':ur-d if ur is not None and d is not None else None}
    return out

def current_2025(ppg,deployed):
    grouped=defaultdict(list)
    for r in ppg:
        p=str(r.get('pos') or '')
        if p in POSITIONS: grouped[p].append(clamp01(int(r.get('games_played') or 0)/17.0))
    out={}
    for p in POSITIONS:
        vals=grouped[p]; med=statistics.median(vals) if vals else None; w=float((deployed.get(p) or {}).get('r_squared') or 0.0)
        preds=[w*a+(1-w)*med for a in vals] if med is not None else []
        out[p]={'tracked_ppg_rows':len(vals),'deployed_own_weight':w,'position_median_2025_availability':med,'median_deployed_projected_2026_availability':statistics.median(preds) if preds else None,'min_deployed_projected_2026_availability':min(preds) if preds else None,'max_deployed_projected_2026_availability':max(preds) if preds else None}
    return out

def build_result():
    deployed=read_json(DEPLOYED); ppg=read_json(PPG)
    if not isinstance(ppg,list): raise RuntimeError('scripts/ppg_results.json must be list')
    sess=requests.Session(); index=fetch_player_index(sess); posmap=build_pos_map(index); season_games={}; fetch_summary={}
    for s in SEASONS:
        print(f'=== Fetching durability season {s} ==='); games,summary=fetch_season(sess,s); season_games[s]=games; fetch_summary[str(s)]=summary
    players,coverage=build_player_seasons(season_games,posmap); survivor,unconditional=transition_rows(players); multi=multiyear_rows(players)
    survsum=summarize_transitions(survivor); uncsum=summarize_transitions(unconditional)
    return {'schema_version':1,'method_version':METHOD,'generated_at_utc':now_utc(),'status':'RESEARCH_ONLY_DURABILITY_AVAILABILITY_AUDIT','production_files_mutated':0,'deployment_authorized':False,'durability_change_authorized':False,'history_component_change_authorized':False,'scope':{'seasons':list(SEASONS),'base_seasons':list(BASE_SEASONS),'tracked_positions':list(POSITIONS),'games_played_source':'Sleeper weekly stats gp field','survivor_only_definition':'base-season >=1 GP and next-season >=1 GP','unconditional_definition':'base-season >=1 GP; next-season missing => zero availability','schedule_normalization':{'2015_2020':'16 games / 17 regular-season weeks','2021_2025':'17 games / 18 regular-season weeks'}},'legacy_methodology':{'deployed_formula':'r2_position * own_availability + (1-r2_position) * position_median_availability','deployed_durability_results':deployed,'legacy_known_survivor_bias':'legacy pipeline intersects player IDs observed in both seasons'},'fetch_summary':fetch_summary,'coverage':coverage,'player_seasons':players,'survivor_only_transition_rows':survivor,'unconditional_transition_rows':unconditional,'multiyear_rows':multi,'survivor_only_summary':survsum,'unconditional_summary':uncsum,'multiyear_summary':summarize_multiyear(multi),'low_availability_patterns':low_patterns(multi),'deployed_vs_phase1_r_squared':deployed_compare(deployed,survsum,uncsum),'current_2025_deployed_availability_audit':current_2025(ppg,deployed),'phase2_handoff':'Cross-validate next-season availability by held-out base season. Compare position median only, deployed R2 blend, prior-year availability, 2-year mean, 2-year recency, 3-year mean, 3-year recency, and simple position-specific OLS variants. Keep survivor-only and unconditional targets separate so role/league-exit risk is not silently conflated with within-career injury persistence.'}

def fmt(v,d=4): return '—' if v is None else f'{float(v):.{d}f}'
def pct(v,d=1): return '—' if v is None else f'{100*float(v):.{d}f}%'

def render_md(r):
    surv=r['survivor_only_summary']['by_position']; unc=r['unconditional_summary']['by_position']; comp=r['deployed_vs_phase1_r_squared']; multi=r['multiyear_summary']['by_position']; pat=r['low_availability_patterns']
    lines=['# Durability / Availability V2 — Phase 1 Historical Audit','',f"Method: `{r['method_version']}`  ",f"Status: **`{r['status']}`**",'','## Guardrail','','**Research only. No deployed durability or player value is changed.**','','## Why this audit matters','','The live history component uses each position\'s year-over-year games-played **R² directly as the player-specific availability weight**. Phase 1 tests survivor-only persistence, an unconditional next-season view where missing future seasons are zero, and whether 2–3 years of history adds signal.','',f"- Historical seasons: **{r['scope']['seasons'][0]}–{r['scope']['seasons'][-1]}**",f"- Player-seasons with mapped tracked position: **{r['coverage']['player_seasons']}**",f"- Unresolved GP-positive player-seasons: **{r['coverage']['unresolved_gp_positive_player_seasons']}**",'','## Year-over-year persistence','','| Pos | Deployed R² | Survivor R² | Unconditional R² | Survivor ρ | Unconditional ρ | Survivor N | Unconditional N |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for p in POSITIONS: lines.append(f"| {p} | {fmt(comp[p]['deployed_own_weight_r_squared'])} | {fmt(surv[p]['pearson_r_squared'])} | {fmt(unc[p]['pearson_r_squared'])} | {fmt(surv[p]['spearman'])} | {fmt(unc[p]['spearman'])} | {surv[p]['n']} | {unc[p]['n']} |")
    lines += ['','## Multi-year history vs unconditional next-season availability','','| Pos | Current ρ | 2Y mean ρ | 2Y recency ρ | 3Y mean ρ | 3Y recency ρ |','|---|---:|---:|---:|---:|---:|']
    for p in POSITIONS:
        x=multi[p]; lines.append(f"| {p} | {fmt(x['current_availability']['spearman'])} | {fmt(x['mean_2year_availability']['spearman'])} | {fmt(x['recency_2year_availability']['spearman'])} | {fmt(x['mean_3year_availability']['spearman'])} | {fmt(x['recency_3year_availability']['spearman'])} |")
    lines += ['','## Low-availability pattern check','','These are descriptive participation patterns, not injury diagnoses.','','| Pattern | N | Mean next availability | Median next availability |','|---|---:|---:|---:|']
    for k in ('one_year_low_after_near_full','repeated_low_two_years','current_near_full'):
        x=pat[k]; lines.append(f"| `{k}` | {x['n']} | {pct(x['mean_next_availability'])} | {pct(x['median_next_availability'])} |")
    lines += ['','## Phase 2','',r['phase2_handoff'],'']
    return '\n'.join(lines)

def write_outputs(r):
    OUT_JSON.parent.mkdir(parents=True,exist_ok=True); OUT_JSON.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n',encoding='utf-8'); OUT_MD.write_text(render_md(r),encoding='utf-8'); print(f'Wrote {OUT_JSON.relative_to(REPO_ROOT)}'); print(f'Wrote {OUT_MD.relative_to(REPO_ROOT)}')

def check_outputs():
    r=read_json(OUT_JSON)
    if r.get('method_version')!=METHOD: raise RuntimeError('Phase-1 method mismatch')
    if r.get('production_files_mutated')!=0: raise RuntimeError('Mutation guardrail failed')
    for k in ('deployment_authorized','durability_change_authorized','history_component_change_authorized'):
        if r.get(k) is not False: raise RuntimeError(f'Unexpected authorization: {k}')
    if int((r.get('coverage') or {}).get('player_seasons') or 0)<10000: raise RuntimeError('Historical sample unexpectedly small')
    if set((r['survivor_only_summary']['by_position']))!=set(POSITIONS) or set((r['unconditional_summary']['by_position']))!=set(POSITIONS): raise RuntimeError('Position family mismatch')
    if not OUT_MD.exists(): raise RuntimeError('Markdown missing')
    text=OUT_MD.read_text(encoding='utf-8')
    for marker in ('Research only','Year-over-year persistence','Multi-year history','Low-availability pattern check','Phase 2'):
        if marker not in text: raise RuntimeError(f'Missing report marker: {marker}')
    print('Durability / Availability V2 Phase-1 outputs passed guardrails.')

def selftest():
    assert scheduled_games(2020)==16 and scheduled_games(2021)==17 and regular_weeks(2020)==17 and regular_weeks(2021)==18
    xs=[.2,.4,.6,.8,1.0]; ys=[.1,.3,.5,.7,.9]; assert abs(float(pearson(xs,ys))-1)<1e-12 and abs(float(spearman(xs,ys))-1)<1e-12
    fake=[{'sleeper_id':'a','season':2023,'pos':'RB','availability':1.0},{'sleeper_id':'a','season':2024,'pos':'RB','availability':.5},{'sleeper_id':'b','season':2023,'pos':'RB','availability':.8}]
    s,u=transition_rows(fake); assert len(s)==1 and len(u)==3 and next(r for r in u if r['sleeper_id']=='b')['next_availability']==0.0
    print('Durability / Availability V2 Phase-1 self-test passed.')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--selftest',action='store_true'); ap.add_argument('--write',action='store_true'); ap.add_argument('--check',action='store_true'); a=ap.parse_args()
    if a.selftest: selftest(); return
    if a.check: check_outputs(); return
    r=build_result(); write_outputs(r) if a.write else print(render_md(r))

if __name__=='__main__': main()
