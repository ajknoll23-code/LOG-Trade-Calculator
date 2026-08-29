#!/usr/bin/env python3
"""Strict projection-only V1 bridge candidate.

The immutable pre-V1 PROD_MULT table is internally inconsistent with the
current replacement-normalized formula: the actual live rank-32 player is not
at prod_mult 0.65 for LB/DL/DB. Therefore any candidate that recomputes a rank-
32 baseline necessarily mixes a baseline-normalization migration into the V1
projection-source change.

This diagnostic isolates V1 *strictly*:

    live_ratio = inverse(actual live prod_mult)
    ratio_delta = 0.55 * (V1 projection - legacy projection)
                  / reproducible old-model point baseline
    candidate_ratio = live_ratio + ratio_delta
    candidate_prod_mult = clamp(-0.10 + 0.75 * candidate_ratio)

No replacement baseline is recomputed. Players with no comparable projection
delta remain exactly at their old live prod_mult. This is not proposed as the
forever architecture; it answers the narrower release-engineering question:
"What does the V1 projection source change itself do, without silently fixing
historical baseline drift at the same time?"

Never reads prod_mult_pipeline_output.json. Never edits index.html.
"""

from __future__ import annotations

import json
import math
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from idp_v1_isolated_projection_candidate import (
    IDP_POSITIONS, PROJECTION_WEIGHT, FLOOR, CEILING,
    build_canonical_candidate, live_ratio_from_prod,
)

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_DIR / "idp_v1_projection_only_candidate.json"
REPORT_PATH = SCRIPT_DIR / "idp_v1_projection_only_candidate_report.md"
REPLACEMENT_RANK = 32


def clamp_prod(ratio):
    return max(FLOOR, min(CEILING, -0.10 + 0.75 * ratio))


def pct(values, q):
    vals=sorted(values)
    if not vals: return None
    if len(vals)==1: return vals[0]
    x=(len(vals)-1)*q; lo=math.floor(x); hi=math.ceil(x)
    if lo==hi: return vals[lo]
    return vals[lo]+(vals[hi]-vals[lo])*(x-lo)


def summarize(values):
    if not values:
        return {"n":0,"median":None,"p90":None,"p95":None,"min":None,"max":None}
    return {"n":len(values),"median":statistics.median(values),"p90":pct(values,.90),"p95":pct(values,.95),"min":min(values),"max":max(values)}


def build_candidate():
    canonical=build_canonical_candidate()
    src=canonical['players']

    old_combined={}
    old_baselines={}
    old_baseline_players={}
    for key,r in src.items():
        lp=r.get('legacy_projection_fallback'); hc=r.get('history_component')
        if lp is not None and hc is not None:
            old_combined[key]=.45*float(hc)+.55*float(lp)
    for pos in IDP_POSITIONS:
        arr=sorted([(v,k) for k,v in old_combined.items() if src[k]['pos']==pos],reverse=True)
        val,key=arr[REPLACEMENT_RANK-1]
        old_baselines[pos]=val; old_baseline_players[pos]=key

    records={}; holds=Counter(); anchors=Counter()
    for key,r in src.items():
        pos=r['pos']; live=float(r['old_live_prod_mult'])
        canonical_old_ratio=old_combined.get(key)
        if canonical_old_ratio is not None:
            canonical_old_ratio/=old_baselines[pos]
        live_ratio,anchor_method=live_ratio_from_prod(live,canonical_old_ratio)
        anchors[anchor_method]+=1

        oldp=r.get('legacy_projection_fallback'); newp=r.get('v1_projection'); cohort=r.get('v1_source_cohort')
        if cohort=='no_new_data':
            delta=0.0; status='no_new_data_exact_hold'
        elif oldp is None:
            delta=0.0; status='hold_new_source_without_legacy_projection'; holds[status]+=1
        elif newp is None:
            delta=0.0; status='hold_no_comparable_projection'; holds[status]+=1
        else:
            delta=float(newp)-float(oldp); status='projection_delta_applied'

        # Exact no-delta holds stay byte-for-byte at the observed old prod_mult.
        # This matters for clamped rows where the precise pre-clamp ratio is
        # unknowable and prevents a diagnostic bridge from inventing movement.
        if abs(delta) < 1e-12:
            candidate_pm=live
            candidate_ratio=live_ratio
        else:
            ratio_delta=PROJECTION_WEIGHT*delta/old_baselines[pos]
            candidate_ratio=live_ratio+ratio_delta
            candidate_pm=round(clamp_prod(candidate_ratio),4)

        records[key]={**r,
            'canonical_old_point_baseline':old_baselines[pos],
            'canonical_old_ratio':canonical_old_ratio,
            'anchor_method':anchor_method,
            'live_ratio_anchor':live_ratio,
            'projection_delta':delta,
            'ratio_delta':PROJECTION_WEIGHT*delta/old_baselines[pos] if abs(delta)>1e-12 else 0.0,
            'candidate_ratio':candidate_ratio,
            'candidate_prod_mult':candidate_pm,
            'pct_change':(candidate_pm/live-1)*100 if live else None,
            'update_status':status,
        }

    return {
        'method':'strict_projection_only_v1_bridge_no_baseline_renormalization',
        'projection_weight':PROJECTION_WEIGHT,
        'canonical_old_point_baseline_by_position':old_baselines,
        'canonical_old_replacement_player':old_baseline_players,
        'source_cohort_counts':canonical['source_cohort_counts'],
        'identity_method_counts':canonical['identity_method_counts'],
        'anchor_method_counts':dict(anchors),
        'hold_counts':dict(holds),
        'players':records,
    }


def build_report(c):
    rows=list(c['players'].values()); by_pos=defaultdict(list); by_source=defaultdict(list); by_status=defaultdict(list)
    clamp_old=Counter(); clamp_new=Counter()
    for r in rows:
        by_pos[r['pos']].append(r['pct_change']); by_source[r['v1_source_cohort']].append(r['pct_change']); by_status[r['update_status']].append(r['pct_change'])
        if r['old_live_prod_mult']<=FLOOR+1e-9: clamp_old[(r['pos'],'floor')]+=1
        if r['old_live_prod_mult']>=CEILING-1e-9: clamp_old[(r['pos'],'ceiling')]+=1
        if r['candidate_prod_mult']<=FLOOR+1e-9: clamp_new[(r['pos'],'floor')]+=1
        if r['candidate_prod_mult']>=CEILING-1e-9: clamp_new[(r['pos'],'ceiling')]+=1

    # Show the live rank-32 inconsistency that motivates this diagnostic.
    live_rank32={}
    for pos in IDP_POSITIONS:
        arr=sorted([r for r in rows if r['pos']==pos],key=lambda r:r['old_live_prod_mult'],reverse=True)
        live_rank32[pos]=arr[REPLACEMENT_RANK-1]

    anchors=['bradley chubb','aidan hutchinson','myles garrett','fred warner','roquan smith','ej speed','isaiah mcduffie']
    risers=sorted(rows,key=lambda r:r['pct_change'],reverse=True)[:20]; fallers=sorted(rows,key=lambda r:r['pct_change'])[:20]
    lines=[
        '# IDP V1 Strict Projection-Only Bridge Report','',
        '## Status','',
        '**Diagnostic release candidate; `index.html` was not modified.**','',
        'This is the only candidate that guarantees a player with no projection delta stays exactly unchanged. It intentionally defers replacement-baseline normalization because the actual pre-V1 baked table is already inconsistent with the current rank-32=0.65 formula.','',
        '## Why baseline normalization must be a separate migration','',
        '| Pos | Actual old live rank-32 player | Old prod_mult | Implied ratio | Expected normalized prod_mult |','|---|---|---:|---:|---:|'
    ]
    for pos in IDP_POSITIONS:
        r=live_rank32[pos]; implied=(r['old_live_prod_mult']+.10)/.75
        lines.append(f"| {pos} | {r['key']} | {r['old_live_prod_mult']:.4f} | {implied:.4f} | 0.6500 |")
    lines += ['', 'A rank-32 re-normalization would therefore move players even when their projection is unchanged. That is a separate historical-lineage correction, not part of the V1 source change.','',
        '## Point scales used only for projection-delta conversion','',
        '| Pos | Reproducible old-model baseline | Rank-32 player |','|---|---:|---|']
    for pos in IDP_POSITIONS:
        lines.append(f"| {pos} | {c['canonical_old_point_baseline_by_position'][pos]:.2f} | {c['canonical_old_replacement_player'][pos]} |")
    lines += ['', '## True pre-V1 live -> strict projection-only change','', '| Pos | N | Median | P90 | P95 | Min | Max |','|---|---:|---:|---:|---:|---:|---:|']
    for pos in IDP_POSITIONS:
        s=summarize(by_pos[pos]); lines.append(f"| {pos} | {s['n']} | {s['median']:+.1f}% | {s['p90']:+.1f}% | {s['p95']:+.1f}% | {s['min']:+.1f}% | {s['max']:+.1f}% |")
    lines += ['', '## Source cohorts','', '| Cohort | N | Median | P90 | P95 |','|---|---:|---:|---:|---:|']
    for cohort in ('both','fp_only','sleeper_only','no_new_data'):
        s=summarize(by_source.get(cohort,[]))
        if s['n']: lines.append(f"| {cohort} | {s['n']} | {s['median']:+.1f}% | {s['p90']:+.1f}% | {s['p95']:+.1f}% |")
    lines += ['', '## Exact-hold verification','']
    for status in ('no_new_data_exact_hold','hold_new_source_without_legacy_projection','hold_no_comparable_projection'):
        vals=by_status.get(status,[])
        if vals: lines.append(f"- `{status}`: **{len(vals)}** players, maximum absolute change **{max(abs(v) for v in vals):.6f}%**")
    lines += ['', '## Clamp occupancy','', '| Pos | Old floor | New floor | Old ceiling | New ceiling |','|---|---:|---:|---:|---:|']
    for pos in IDP_POSITIONS:
        lines.append(f"| {pos} | {clamp_old[(pos,'floor')]} | {clamp_new[(pos,'floor')]} | {clamp_old[(pos,'ceiling')]} | {clamp_new[(pos,'ceiling')]} |")
    lines += ['', '## Known anchors','', '| Player | Pos | Old | Candidate | Change | Cohort | Status |','|---|---|---:|---:|---:|---|---|']
    for k in anchors:
        r=c['players'].get(k)
        if r: lines.append(f"| {k} | {r['pos']} | {r['old_live_prod_mult']:.4f} | {r['candidate_prod_mult']:.4f} | {r['pct_change']:+.1f}% | {r['v1_source_cohort']} | {r['update_status']} |")
    def mv(title,arr):
        lines.extend(['',title,'','| Player | Pos | Old | Candidate | Change | Cohort |','|---|---|---:|---:|---:|---|'])
        for r in arr: lines.append(f"| {r['key']} | {r['pos']} | {r['old_live_prod_mult']:.4f} | {r['candidate_prod_mult']:.4f} | {r['pct_change']:+.1f}% | {r['v1_source_cohort']} |")
    mv('## Top 20 risers',risers); mv('## Top 20 fallers',fallers)
    lines += ['', '## Interpretation','', 'This report should be compared with both the full canonical recompute and the normalized isolated candidate. If this strict bridge is selected for the first V1 release, replacement-baseline normalization becomes an explicit later migration with its own validation rather than a hidden side effect of the projection-source change.']
    return '\n'.join(lines)+'\n'


def run_selftest():
    c=build_candidate()
    for r in c['players'].values():
        if r['update_status']!='projection_delta_applied':
            assert r['candidate_prod_mult']==r['old_live_prod_mult'], r['key']
    print('idp_v1_projection_only_candidate self-test passed; all hold rows exact.')


def main():
    if '--selftest' in os.sys.argv:
        run_selftest(); return
    c=build_candidate()
    with open(OUTPUT_PATH,'w',encoding='utf-8') as f: json.dump(c,f,indent=2); f.write('\n')
    REPORT_PATH.write_text(build_report(c),encoding='utf-8')
    print(f'Wrote {OUTPUT_PATH}'); print(f'Wrote {REPORT_PATH}')

if __name__=='__main__': main()
