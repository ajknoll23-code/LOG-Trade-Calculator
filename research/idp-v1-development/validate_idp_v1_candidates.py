#!/usr/bin/env python3
"""Compare V1 candidate strategies through the actual Trade Desk value engine.

This validator does not edit production files. It compares four diagnostic
paths against the true pre-V1 index.html values:

1. full history+V1 recompute (with the legacy production-position grouping)
2. isolated projection delta with rank-32 re-normalization
3. strict projection-only bridge with no baseline re-normalization
4. model-delta transport onto the true pre-V1 live PROD_MULT table

The goal is release attribution: identify which path changes only the approved
V1 projection architecture versus silently absorbing historical lineage drift.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import snapshot_values

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
INDEX = REPO_ROOT / "index.html"
PRE_V1_BASELINE = SCRIPT_DIR / "prod_mult_pre_v1_baseline.json"
REPORT = SCRIPT_DIR / "idp_v1_candidate_comparison_report.md"
JSON_OUT = SCRIPT_DIR / "idp_v1_candidate_comparison.json"

CANDIDATES = {
    "full_canonical": SCRIPT_DIR / "idp_v1_production_candidate.json",
    "isolated_normalized": SCRIPT_DIR / "idp_v1_isolated_projection_candidate.json",
    "strict_projection_only": SCRIPT_DIR / "idp_v1_projection_only_candidate.json",
    "model_delta_transport": SCRIPT_DIR / "idp_v1_model_delta_transport_candidate.json",
}
IDP_POSITIONS = ("LB", "DL", "DB")
ANCHORS = (
    "bradley chubb", "aidan hutchinson", "myles garrett", "fred warner",
    "roquan smith", "ej speed", "isaiah mcduffie",
)


def percentile(values, q):
    vals=sorted(values)
    if not vals: return None
    if len(vals)==1: return vals[0]
    x=(len(vals)-1)*q; lo=math.floor(x); hi=math.ceil(x)
    if lo==hi:return vals[lo]
    return vals[lo]+(vals[hi]-vals[lo])*(x-lo)


def summary(values):
    if not values:return {"n":0,"median":None,"p90":None,"p95":None,"min":None,"max":None}
    return {"n":len(values),"median":statistics.median(values),"p90":percentile(values,.9),"p95":percentile(values,.95),"min":min(values),"max":max(values)}


def rank_map(values):
    by_pos=defaultdict(list)
    for key,r in values.items():
        if r['pos'] in IDP_POSITIONS:
            by_pos[r['pos']].append((r['value'],key))
    ranks={}
    for pos,arr in by_pos.items():
        arr.sort(key=lambda x:(-x[0],x[1]))
        for i,(v,k) in enumerate(arr,1): ranks[k]=i
    return ranks


def candidate_values(base_cfg, candidate_doc):
    cfg=dict(base_cfg)
    cfg['prod_mult']=dict(base_cfg['prod_mult'])
    for key,r in candidate_doc['players'].items():
        if key in cfg['prod_mult']:
            cfg['prod_mult'][key]=float(r['candidate_prod_mult'])
    return snapshot_values.compute_all_values(cfg)


def analyze_candidate(name, doc, old_values, old_ranks, cfg):
    new_values=candidate_values(cfg,doc); new_ranks=rank_map(new_values)
    changes_by_pos=defaultdict(list); rows=[]
    for key,old in old_values.items():
        if old['pos'] not in IDP_POSITIONS or key not in new_values: continue
        new=new_values[key]
        pct=(new['value']/old['value']-1)*100 if old['value'] else None
        changes_by_pos[old['pos']].append(pct)
        rows.append({
            'key':key,'pos':old['pos'],'old_value':old['value'],'new_value':new['value'],
            'value_pct_change':pct,'old_rank':old_ranks.get(key),'new_rank':new_ranks.get(key),
            'rank_change':(new_ranks.get(key)-old_ranks.get(key)) if key in old_ranks and key in new_ranks else None,
            'old_effective_prod_mult':old['prod_mult'],'new_effective_prod_mult':new['prod_mult'],
            'candidate_raw_prod_mult':doc['players'].get(key,{}).get('candidate_prod_mult'),
            'source_cohort':doc['players'].get(key,{}).get('v1_source_cohort'),
            'update_status':doc['players'].get(key,{}).get('update_status') or doc['players'].get(key,{}).get('status'),
        })

    top_movement={}
    for pos in IDP_POSITIONS:
        rel=[r for r in rows if r['pos']==pos and (r['old_rank']<=36 or r['new_rank']<=36)]
        top_movement[pos]={
            'top24_movers_ge5':sum(1 for r in rel if (r['old_rank']<=24 or r['new_rank']<=24) and abs(r['rank_change'])>=5),
            'top36_movers_ge5':sum(1 for r in rel if abs(r['rank_change'])>=5),
            'max_abs_rank_move_top36':max([abs(r['rank_change']) for r in rel],default=0),
        }

    return {
        'final_value_change_by_position':{p:summary(changes_by_pos[p]) for p in IDP_POSITIONS},
        'top_rank_movement':top_movement,
        'largest_final_value_movers':sorted(rows,key=lambda r:abs(r['value_pct_change']),reverse=True)[:30],
        'anchors':{k:next((r for r in rows if r['key']==k),None) for k in ANCHORS},
        'rows':rows,
    }


def main():
    # The comparison baseline is the immutable PRE-V1 live PROD_MULT table,
    # not whatever happens to be deployed in index.html today. This keeps the
    # candidate-comparison artifact reproducible after V1 itself is deployed.
    cfg=snapshot_values.load_from_html(INDEX)
    baseline_doc=json.load(open(PRE_V1_BASELINE,encoding='utf-8'))
    old_cfg=dict(cfg)
    old_cfg['prod_mult']=dict(cfg['prod_mult'])
    old_cfg['prod_mult'].update({k:float(v) for k,v in baseline_doc['values'].items()})
    old_values=snapshot_values.compute_all_values(old_cfg); old_ranks=rank_map(old_values)
    docs={name:json.load(open(path,encoding='utf-8')) for name,path in CANDIDATES.items()}
    results={name:analyze_candidate(name,doc,old_values,old_ranks,cfg) for name,doc in docs.items()}

    out={'old_player_count':len(old_values),'candidates':results}
    JSON_OUT.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')

    lines=[
        '# IDP V1 Candidate Comparison Through Final Trade Desk Values','',
        '## Purpose','',
        'All candidates are passed through the **actual current `snapshot_values.py` port of `index.html`** for valuation logic, while the OLD side is anchored to the immutable pre-V1 `PROD_MULT_DATA` snapshot. This keeps the comparison reproducible even after V1 is deployed.','',
        '## Final value movement by position','',
    ]
    for name,res in results.items():
        lines += [f'### {name}','', '| Pos | N | Median | P90 | P95 | Min | Max |','|---|---:|---:|---:|---:|---:|---:|']
        for pos in IDP_POSITIONS:
            s=res['final_value_change_by_position'][pos]
            lines.append(f"| {pos} | {s['n']} | {s['median']:+.1f}% | {s['p90']:+.1f}% | {s['p95']:+.1f}% | {s['min']:+.1f}% | {s['max']:+.1f}% |")
        lines.append('')

    lines += ['## Top-rank stability','', '| Candidate | Pos | Top-24 movers >=5 ranks | Top-36 movers >=5 ranks | Max abs move among top-36 |','|---|---|---:|---:|---:|']
    for name,res in results.items():
        for pos in IDP_POSITIONS:
            m=res['top_rank_movement'][pos]
            lines.append(f"| {name} | {pos} | {m['top24_movers_ge5']} | {m['top36_movers_ge5']} | {m['max_abs_rank_move_top36']} |")

    lines += ['', '## Known anchors — final Trade Desk value','', '| Candidate | Player | Pos | Old | New | Change | Old rank | New rank |','|---|---|---|---:|---:|---:|---:|---:|']
    for name,res in results.items():
        for k in ANCHORS:
            r=res['anchors'].get(k)
            if r:
                lines.append(f"| {name} | {k} | {r['pos']} | {r['old_value']} | {r['new_value']} | {r['value_pct_change']:+.1f}% | {r['old_rank']} | {r['new_rank']} |")

    lines += ['', '## Largest final-value movers by candidate','']
    for name,res in results.items():
        lines += [f'### {name}','', '| Player | Pos | Old value | New value | Change | Rank move | Cohort/status |','|---|---|---:|---:|---:|---:|---|']
        for r in res['largest_final_value_movers'][:15]:
            label='/'.join(x for x in (r.get('source_cohort'),r.get('update_status')) if x)
            lines.append(f"| {r['key']} | {r['pos']} | {r['old_value']} | {r['new_value']} | {r['value_pct_change']:+.1f}% | {r['rank_change']:+d} | {label} |")
        lines.append('')

    lines += [
        '## Engineering conclusion','',
        '- **Full canonical** answers: “What would the model say if we regenerated the entire current history + projection lineage today?” It is the clean long-term architecture but mixes historical lineage cleanup into V1.',
        '- **Isolated normalized** answers: “What if we anchor to live values, apply V1 projection deltas, then immediately force the table back through rank-32 normalization?” This still moves no-change players because the old baked table is not internally rank-32 normalized.',
        '- **Strict projection-only** answers: “What does the direct projection-point delta do if baseline movement is deferred entirely?”',
        '- **Model-delta transport** computes old and V1 models on one reproducible comparable cohort, includes the V1 model’s legitimate rank-32 baseline movement there, and transports only that model delta onto the actual live table. This is the cleanest bridge between reproducibility and release attribution.',
        '',
        '**Recommendation:** use `model_delta_transport` as the production-oriented V1 candidate. It nearly reproduces the shape of the earlier validated sensitivity study without importing the stale old model’s absolute level or silently re-normalizing the historical live table.',
    ]
    REPORT.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'Wrote {REPORT}'); print(f'Wrote {JSON_OUT}')

if __name__=='__main__': main()
