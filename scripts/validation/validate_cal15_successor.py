"""Versioned CAL15 successor validator: live FV/quote plus preserved original IDP V1/CAL02 release.
The original IDP V1 validator is retained unchanged and run against an exact
byte-reconstruction of the pre-CAL15 index from the published CAL15 release.
"""
from __future__ import annotations
import hashlib,json,re,tempfile,sys
from pathlib import Path
import snapshot_values
import validate_idp_v1_final_deployment as prior

ROOT=Path(__file__).resolve().parent.parent.parent
INDEX=ROOT/'index.html'
RELEASE=ROOT/'model/releases/cal15-idp-2026-horizon-bounded-v1/release.json'
QUOTE=ROOT/'scripts/artifacts/generated/fv_informed_estimate_cal15.json'
BOARD=ROOT/'free-agent-board.html'
sys.path.insert(0,str(ROOT/'scripts/sync'))
import sync_free_agent_valuation as sync_fa

def sha(b):return hashlib.sha256(b).hexdigest()

def validate_deployment_successor():
    release=json.loads(RELEASE.read_text())
    assert release['release_id']=='cal15-idp-2026-horizon-bounded-v1'
    assert release['base_index_sha256']=='3bdeb2c0f44dfe28b9f5390b53a3512a24a7e6a3ec01d0733928eb13609243c2'
    assert sha(INDEX.read_bytes())==release['candidate_index_sha256']
    assert sha(QUOTE.read_bytes())==release['new_quote_sha256']
    assert sha(BOARD.read_bytes())==release['candidate_free_agent_board_sha256'], 'Free Agent Board bytes not deployed'
    assert all(sync_fa.parity_regions(INDEX.read_text(),BOARD.read_text()).values()), 'Free Agent Board canonical source drift'
    assert sync_fa.render_synced(INDEX.read_text(),BOARD.read_text())==BOARD.read_text(), 'Free Agent Board sync not idempotent'
    assert release['changed_players']==len(release['changed_rows'])>=100
    current=INDEX.read_text()
    cfg=snapshot_values.load_from_html(INDEX);now=snapshot_values.compute_all_values(cfg)
    assert len(now)==565
    original=current
    start=original.index('const PROD_MULT_DATA = {')
    end=original.index('};',start)
    block=original[start:end]
    changed=set()
    for entry in release['changed_rows']:
        k=entry['player'];changed.add(k)
        assert now[k]['value']==entry['new_fv'],('CAL15 successor FV',k)
        assert abs(cfg['prod_mult'][k]-entry['new_raw'])<1e-11,('CAL15 successor raw',k)
        pat=re.compile(r"(?m)^([ ]*'"+re.escape(k)+r"':)([-+0-9.eE]+)(,?)$")
        block,n=pat.subn(lambda m:m.group(1)+entry['old_literal']+m.group(3),block)
        assert n==1,('CAL15 successor missing live raw entry',k,n)
    original=original[:start]+block+original[end:]
    assert original.count('fv_informed_estimate_cal15.json')==1
    original=original.replace('fv_informed_estimate_cal15.json','fv_informed_estimate_cal05.json',1)
    assert sha(original.encode())==release['base_index_sha256'],'Pre-CAL15 IDP lineage cannot be exactly reproduced'
    # Run old hard-frozen V1 + CAL02 + 4for4 regression on the exact prior bytes.
    with tempfile.NamedTemporaryFile('w',suffix='.html',delete=False) as h:
        h.write(original);path=Path(h.name)
    prior_index=prior.INDEX
    try:
        prior.INDEX=path
        legacy=prior.validate_deployment()
    finally:
        prior.INDEX=prior_index
        path.unlink(missing_ok=True)
    assert legacy['status']=='PASS'
    # Independently reconstruct prior FV once more through a temporary file.
    with tempfile.NamedTemporaryFile('w',suffix='.html',delete=False) as h:
        h.write(original);path=Path(h.name)
    try:
        baseline=snapshot_values.compute_all_values(snapshot_values.load_from_html(path))
    finally:path.unlink(missing_ok=True)
    assert len(changed)==release['changed_players']
    assert {k for k in now if now[k]['value']!=baseline[k]['value']}==changed
    assert all(now[k]['value']-baseline[k]['value']==next(e['new_fv']-e['old_fv'] for e in release['changed_rows'] if e['player']==k) for k in changed)
    assert all(now[k]['value']==baseline[k]['value'] for k in now if k not in changed)
    assert all(abs(now[k]['value']-baseline[k]['value'])<=max(1,int(baseline[k]['value']*release['max_relative_FV_shift'])) for k in changed)
    q=json.loads(QUOTE.read_text())
    assert q['display_only'] and q['no_trading_math_changes'] and len(q['players'])==565
    assert all(q['players'][k]['fundamental_value']==now[k]['value'] for k in now)
    assert 'fv_informed_estimate_cal15.json' in INDEX.read_text()
    print(f'PASS CAL15 successor: {len(changed)} bounded IDP changes; 565 quote parity; exact historical V1+CAL02 lineage preserved')
    return {'status':'PASS','changed_players':len(changed),'historical_idp_v1':legacy['status']}

if __name__=='__main__':validate_deployment_successor()
