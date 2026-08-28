#!/usr/bin/env python3
"""Transport the internally consistent V1 model delta onto true live values.

This bridge resolves the core lineage problem without pretending the stale
historical generator is the old production table.

1. On one reproducible, comparable player cohort, compute an OLD model using
   canonical history + directly reconstructed legacy 2026 projection inputs.
2. On that exact same cohort, compute the NEW model using canonical history +
   validated V1 category projections.
3. Recompute rank-32 baselines in each model.
4. Measure the model change in *unclamped production-multiplier units*:

       delta_pm = 0.75 * (new_ratio - old_ratio)

5. Apply only that delta to the actual pre-V1 live PROD_MULT value and clamp.

This transports the V1 model change -- including its internally consistent
replacement-baseline effect -- without importing the old model's absolute
historical level into production. Players lacking a comparable old projection
are held exactly unchanged rather than inventing a zero baseline.

A deployment guard also preserves the live role-floor rescue for current
PLAYER_DB players with zero real 2025 history whose pre-V1 raw multiplier was
exactly 0.15. If a tiny transported delta would move raw PROD_MULT just above
0.15 but still below the role estimate, the raw value is held at 0.15 so the
existing live rescue is not accidentally disabled. This prevents an unvalidated
threshold artifact from turning a positive raw delta into a large final-value
drop.

Never reads prod_mult_pipeline_output.json. Never edits index.html.
"""

from __future__ import annotations

import json
import math
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from idp_v1_production_candidate import build_candidate as build_source_candidate
import snapshot_values

SCRIPT_DIR = Path(__file__).resolve().parent
INDEX_PATH = SCRIPT_DIR.parent / "index.html"
OUTPUT_PATH = SCRIPT_DIR / "idp_v1_model_delta_transport_candidate.json"
REPORT_PATH = SCRIPT_DIR / "idp_v1_model_delta_transport_candidate_report.md"

IDP_POSITIONS=("LB","DL","DB")
REPLACEMENT_RANK=32
FLOOR=.15
CEILING=1.55
HISTORY_WEIGHT=.45
PROJECTION_WEIGHT=.55


def clamp(x): return max(FLOOR,min(CEILING,x))

def pct(vals,q):
    vals=sorted(vals)
    if not vals:return None
    if len(vals)==1:return vals[0]
    x=(len(vals)-1)*q; lo=math.floor(x); hi=math.ceil(x)
    if lo==hi:return vals[lo]
    return vals[lo]+(vals[hi]-vals[lo])*(x-lo)

def summarize(vals):
    if not vals:return {'n':0,'median':None,'p90':None,'p95':None,'min':None,'max':None}
    return {'n':len(vals),'median':statistics.median(vals),'p90':pct(vals,.9),'p95':pct(vals,.95),'min':min(vals),'max':max(vals)}


def build_candidate():
    source=build_source_candidate(); src=source['players']
    # Migration-specific safety guard: the live value engine rescues a player
    # with zero real 2025 history from the literal 0.15 raw floor to the
    # player's role estimate. A tiny transported delta such as 0.150 -> 0.151
    # would otherwise TURN THAT RESCUE OFF and create a large final-value drop
    # even though the raw model delta was positive. That discontinuity was not
    # part of the V1 validation cohort (no-history rows were excluded there).
    # Preserve the pre-V1 floor rescue unless V1's transported raw multiplier
    # actually clears the role estimate. This is release attribution, not a
    # recalibration of productionMultiplier() itself.
    valuation_cfg = snapshot_values.load_from_html(INDEX_PATH)
    comparable={}
    holds=Counter()
    for key,r in src.items():
        oldp=r.get('legacy_projection_fallback'); newp=r.get('v1_projection'); hc=r.get('history_component')
        if hc is None or oldp is None:
            holds['hold_without_comparable_old_projection']+=1
            continue
        # compute_v1_projection returns oldp for no_new_data, so newp should be
        # comparable whenever oldp exists. Guard anyway.
        if newp is None:
            holds['hold_without_comparable_new_projection']+=1
            continue
        comparable[key]={
            'old_combined':HISTORY_WEIGHT*float(hc)+PROJECTION_WEIGHT*float(oldp),
            'new_combined':HISTORY_WEIGHT*float(hc)+PROJECTION_WEIGHT*float(newp),
        }

    old_baselines={}; new_baselines={}; old_players={}; new_players={}
    for pos in IDP_POSITIONS:
        oldarr=sorted([(v['old_combined'],k) for k,v in comparable.items() if src[k]['pos']==pos],reverse=True)
        newarr=sorted([(v['new_combined'],k) for k,v in comparable.items() if src[k]['pos']==pos],reverse=True)
        if len(oldarr)<REPLACEMENT_RANK or len(newarr)<REPLACEMENT_RANK:
            raise RuntimeError(f'{pos}: insufficient comparable cohort')
        old_baselines[pos],old_players[pos]=oldarr[REPLACEMENT_RANK-1]
        new_baselines[pos],new_players[pos]=newarr[REPLACEMENT_RANK-1]

    records={}; status_counts=Counter()
    for key,r in src.items():
        live=float(r['old_live_prod_mult']); pos=r['pos']
        if key not in comparable:
            candidate=live; unguarded_candidate=candidate; delta_raw_pm=0.0; status='exact_hold_no_comparable_old_projection'
        else:
            old_ratio=comparable[key]['old_combined']/old_baselines[pos]
            new_ratio=comparable[key]['new_combined']/new_baselines[pos]
            delta_raw_pm=.75*(new_ratio-old_ratio)
            candidate=round(clamp(live+delta_raw_pm),4)
            status='model_delta_transported'

            info = valuation_cfg['player_db'].get(key)
            role_estimate = valuation_cfg['role_mult'].get(info['role'], 1.0) if info else None
            if (
                live <= FLOOR
                and r.get('games_played_2025') == 0
                and role_estimate is not None
                and FLOOR < candidate <= role_estimate
            ):
                unguarded_candidate = candidate
                candidate = live
                status = 'exact_hold_floor_rescue_discontinuity_guard'
            else:
                unguarded_candidate = candidate
        status_counts[status]+=1
        rec={**r,
            'old_model_combined':comparable.get(key,{}).get('old_combined'),
            'new_model_combined':comparable.get(key,{}).get('new_combined'),
            'old_model_baseline':old_baselines[pos],
            'new_model_baseline':new_baselines[pos],
            'old_model_ratio':(comparable[key]['old_combined']/old_baselines[pos]) if key in comparable else None,
            'new_model_ratio':(comparable[key]['new_combined']/new_baselines[pos]) if key in comparable else None,
            'delta_raw_prod_mult':delta_raw_pm,
            'unguarded_candidate_prod_mult':unguarded_candidate,
            'candidate_prod_mult':candidate,
            'pct_change':(candidate/live-1)*100 if live else None,
            'update_status':status,
        }
        records[key]=rec

    return {
        'method':'reproducible_old_vs_v1_model_delta_transported_to_true_live_prod_mult',
        'replacement_rank':REPLACEMENT_RANK,
        'history_weight':HISTORY_WEIGHT,
        'projection_weight':PROJECTION_WEIGHT,
        'comparable_player_count':len(comparable),
        'old_model_baseline_by_position':old_baselines,
        'new_model_baseline_by_position':new_baselines,
        'old_model_replacement_player':old_players,
        'new_model_replacement_player':new_players,
        'source_cohort_counts':source['source_cohort_counts'],
        'identity_method_counts':source['identity_method_counts'],
        'hold_counts':dict(holds),
        'status_counts':dict(status_counts),
        'players':records,
    }


def build_report(c):
    rows=list(c['players'].values()); by_pos=defaultdict(list); by_source=defaultdict(list); by_status=defaultdict(list)
    for r in rows:
        by_pos[r['pos']].append(r['pct_change']); by_source[r['v1_source_cohort']].append(r['pct_change']); by_status[r['update_status']].append(r['pct_change'])
    anchors=['bradley chubb','aidan hutchinson','myles garrett','fred warner','roquan smith','ej speed','isaiah mcduffie']
    risers=sorted(rows,key=lambda r:r['pct_change'],reverse=True)[:20]; fallers=sorted(rows,key=lambda r:r['pct_change'])[:20]
    lines=['# IDP V1 Model-Delta Transport Candidate Report','',
        '## Status','',
        '**Preferred engineering candidate to evaluate for the first V1 production bake. `index.html` is unchanged.**','',
        'This candidate computes the old->V1 change inside one reproducible model, including rank-32 baseline movement, then transports only that change onto the actual pre-V1 live PROD_MULT table. It neither replaces live values with the regenerated old model nor forces the historically drifted live table through a fresh baseline normalization.','',
        f"Comparable old/new model cohort: **{c['comparable_player_count']}** of **{len(rows)}** live IDP keys.",'']
    lines += ['## Internally consistent model baseline movement','', '| Pos | Old model baseline | Old rank-32 | V1 baseline | V1 rank-32 | Shift |','|---|---:|---|---:|---|---:|']
    for pos in IDP_POSITIONS:
        o=c['old_model_baseline_by_position'][pos]; n=c['new_model_baseline_by_position'][pos]
        lines.append(f"| {pos} | {o:.2f} | {c['old_model_replacement_player'][pos]} | {n:.2f} | {c['new_model_replacement_player'][pos]} | {(n/o-1)*100:+.1f}% |")
    lines += ['', '## True pre-V1 live -> transported V1 change','', '| Pos | N | Median | P90 | P95 | Min | Max |','|---|---:|---:|---:|---:|---:|---:|']
    for pos in IDP_POSITIONS:
        s=summarize(by_pos[pos]); lines.append(f"| {pos} | {s['n']} | {s['median']:+.1f}% | {s['p90']:+.1f}% | {s['p95']:+.1f}% | {s['min']:+.1f}% | {s['max']:+.1f}% |")
    lines += ['', '## Source cohorts','', '| Cohort | N | Median | P90 | P95 |','|---|---:|---:|---:|---:|']
    for cohort in ('both','fp_only','sleeper_only','no_new_data'):
        s=summarize(by_source.get(cohort,[]))
        if s['n']: lines.append(f"| {cohort} | {s['n']} | {s['median']:+.1f}% | {s['p90']:+.1f}% | {s['p95']:+.1f}% |")
    lines += ['', '## Exact holds / release guards','']
    vals=by_status.get('exact_hold_no_comparable_old_projection',[])
    lines.append(f"- No comparable old projection: **{len(vals)}** players; maximum absolute change **{max([abs(x) for x in vals],default=0):.6f}%**")
    guarded=[r['key'] for r in rows if r['update_status']=='exact_hold_floor_rescue_discontinuity_guard']
    lines.append(f"- Floor-rescue discontinuity guard: **{len(guarded)}** current PLAYER_DB players held exactly at the pre-V1 raw floor: {', '.join(guarded) if guarded else 'none'}.")
    lines.append("  This prevents a tiny positive raw transport delta from disabling the existing no-history role-floor rescue and causing an unvalidated large final-value drop.")
    lines += ['', '## Known anchors','', '| Player | Pos | Old | Candidate | Change | Cohort | Status |','|---|---|---:|---:|---:|---|---|']
    for k in anchors:
        r=c['players'].get(k)
        if r: lines.append(f"| {k} | {r['pos']} | {r['old_live_prod_mult']:.4f} | {r['candidate_prod_mult']:.4f} | {r['pct_change']:+.1f}% | {r['v1_source_cohort']} | {r['update_status']} |")
    def mv(title,arr):
        lines.extend(['',title,'','| Player | Pos | Old | Candidate | Change | Cohort |','|---|---|---:|---:|---:|---|'])
        for r in arr: lines.append(f"| {r['key']} | {r['pos']} | {r['old_live_prod_mult']:.4f} | {r['candidate_prod_mult']:.4f} | {r['pct_change']:+.1f}% | {r['v1_source_cohort']} |")
    mv('## Top 20 risers',risers); mv('## Top 20 fallers',fallers)
    lines += ['', '## Why this bridge is different','',
        '- It **does** preserve the V1 model’s legitimate replacement-baseline effect, because old and V1 baselines are recomputed inside the same reproducible comparable model.',
        '- It **does not** import the regenerated old model’s absolute player values into production, because only the old->new model delta is transported.',
        '- It **does not** re-normalize the historically drifted live table just because V1 is being deployed.',
        '- It holds players with no comparable old projection exactly unchanged instead of inventing a zero or an unverifiable delta.','']
    return '\n'.join(lines)+'\n'


def run_selftest():
    c=build_candidate()
    floor_guarded=[]
    for r in c['players'].values():
        if r['update_status']=='exact_hold_no_comparable_old_projection':
            assert r['candidate_prod_mult']==r['old_live_prod_mult'],r['key']
        if r['update_status']=='exact_hold_floor_rescue_discontinuity_guard':
            floor_guarded.append(r['key'])
            assert r['old_live_prod_mult'] == FLOOR, r['key']
            assert r['candidate_prod_mult'] == FLOOR, r['key']
            assert r['unguarded_candidate_prod_mult'] > FLOOR, r['key']
    expected={'jaishawn barham','jake golday','kaleb elarmsorr','kyle louis'}
    assert set(floor_guarded)==expected, (floor_guarded, expected)
    print('idp_v1_model_delta_transport_candidate self-test passed.')


def main():
    if '--selftest' in os.sys.argv:
        run_selftest();return
    c=build_candidate(); OUTPUT_PATH.write_text(json.dumps(c,indent=2)+'\n',encoding='utf-8'); REPORT_PATH.write_text(build_report(c),encoding='utf-8')
    print(f'Wrote {OUTPUT_PATH}');print(f'Wrote {REPORT_PATH}')

if __name__=='__main__':main()
