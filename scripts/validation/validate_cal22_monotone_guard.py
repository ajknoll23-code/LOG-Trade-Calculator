#!/usr/bin/env python3
"""CAL22 frozen-source continuity guard: deployed-price parity and prior lineage.
This validator proves the 48-key repair without masking old IDP/CAL15 safeguards.
"""
from __future__ import annotations
import csv,hashlib,json,re,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve()
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'scripts/validation'))
sys.path.insert(0,str(ROOT/'scripts/sync'))
import snapshot_values as sv
import sync_free_agent_valuation as sync_fa
REL='model/releases/cal22-legacy-048-raw-floor-continuity-v1/release.json'
BEGIN='/* CAL22_LEGACY_MONOTONE_GUARD_BEGIN — frozen 48-key identity cohort; never change current FV */\n'
END='/* CAL22_LEGACY_MONOTONE_GUARD_END */\n'
ADDITIONAL=("    if(role === 'Speculative' && CAL22_LEGACY_MONOTONE_KEYS.hasOwnProperty(key) && "
            "real >= 0.15 && real < roleEstimate && NO_REAL_PRODUCTION_HISTORY.hasOwnProperty(key)) return roleEstimate;\n")

def sha(b):return hashlib.sha256(b).hexdigest()
def original_html(s):
 assert s.count(BEGIN)==1 and s.count(END)==1 and s.count(ADDITIONAL)==1
 begin=s.index(BEGIN);end=s.index(END,begin)+len(END)
 # Extra newline inserted after block.
 assert s[end:end+1]=='\n'
 return (s[:begin]+s[end+1:]).replace(ADDITIONAL,'',1)

def validate_deployment_successor():
 release=json.loads((ROOT/REL).read_text())
 assert release['release_id']=='cal22-legacy-048-raw-floor-continuity-v1'
 assert release['no_current_price_changes'] and release['market_value_untouched']
 assert release['guard_key_count']==48
 index=(ROOT/'index.html').read_text();board=(ROOT/'free-agent-board.html').read_text()
 assert sha(index.encode())==release['candidate_index_sha256']
 assert sha(board.encode())==release['candidate_board_sha256']
 assert sync_fa.render_synced(index,board)==board
 assert all(sync_fa.parity_regions(index,board).values())
 original=original_html(index)
 original_board=sync_fa.render_synced(original,board)
 assert sha(original.encode())==release['base_index_sha256']
 assert sha(original_board.encode())==release['base_board_sha256']
 cfg=sv.load_from_html(ROOT/'index.html');after=sv.compute_all_values(cfg)
 assert len(after)==565 and len(cfg['cal22_keys'])==48
 assert sorted(cfg['cal22_keys'])==release['frozen_keys']
 with tempfile.TemporaryDirectory() as td:
  p=Path(td)/'old.html';p.write_text(original)
  q=Path(td)/'oldboard.html';q.write_text(original_board)
  old=sv.compute_all_values(sv.load_from_html(p))
  assert {k:r['value'] for k,r in old.items()}=={k:r['value'] for k,r in after.items()}
  cal20_deployed=(ROOT/'model/releases/cal20-offense-core173-2026-10-20-v1/release.json').exists()
  if cal20_deployed:
   import validate_cal20_successor as prior
   # CAL20 validation operates on the reconstructed directly preceding
   # exact release. If later background jobs changed the CAL20 file,
   # the predecessor's release hash appropriately FAILS CLOSED.
   predecessor_index=p
   predecessor_board=q
  else:
   import validate_cal15_successor as prior
   # Current index.html contains unrelated scheduled-refresh metadata
   # changes since CAL15. The CAL15 validator intentionally requires
   # EXACT released HTML SHA256 bytes, so replay its immutable release
   # instead of mistakenly claiming the current (pre-CAL22) index is CAL15.
   # This commit is a GREEN CAL16 run that contains the deployed CAL15
   # index/board exactly, not a regenerated approximation.
   import subprocess
   frozen_commit='2789271e94e80674d2f183ab726ec7407041b111'
   manifest15=json.loads((ROOT/'model/releases/cal15-idp-2026-horizon-bounded-v1/release.json').read_text())
   frozen_index=subprocess.check_output(['git','show',f'{frozen_commit}:index.html'],cwd=ROOT)
   frozen_board=subprocess.check_output(['git','show',f'{frozen_commit}:free-agent-board.html'],cwd=ROOT)
   assert sha(frozen_index)==manifest15['candidate_index_sha256'], 'Immutable CAL15 source index drift'
   assert sha(frozen_board)==manifest15['candidate_free_agent_board_sha256'], 'Immutable CAL15 source board drift'
   predecessor_index=Path(td)/'immutable-cal15-index.html'
   predecessor_board=Path(td)/'immutable-cal15-board.html'
   predecessor_index.write_bytes(frozen_index)
   predecessor_board.write_bytes(frozen_board)
   # Independently retain the current predecessor reconstruction check
   # above: sha(original)==release['base_index_sha256'] remains mandatory.
  from datetime import date
  pi,pb=prior.INDEX,prior.BOARD
  live_birth_age=sv.fractional_age_from_birth_date
  def cal15_historical_birth_age(birth_date,fallback_age,as_of=None):
   return live_birth_age(birth_date,fallback_age,
      as_of=date(2026,10,19) if as_of is None else as_of)
  try:
   prior.INDEX=predecessor_index;prior.BOARD=predecessor_board
   if not cal20_deployed:
    sv.fractional_age_from_birth_date=cal15_historical_birth_age
   previous=prior.validate_deployment_successor()
  finally:
   sv.fractional_age_from_birth_date=live_birth_age
   prior.INDEX=pi;prior.BOARD=pb
  assert sv.fractional_age_from_birth_date is live_birth_age
  assert previous['status']=='PASS'
  print('CAL22 historical validator PASS:', 'CAL20 frozen price date' if cal20_deployed else 'CAL15 2026-10-19 release date pinned; live clock restored')
 role_floor=cfg['role_mult']['Speculative'];assert role_floor==0.22
 oldprod=dict(cfg['prod_mult']);suspects=[]
 for k in sorted(cfg['cal22_keys']):
  assert k in cfg['no_real_history'] and cfg['player_db'][k]['role']=='Speculative'
  assert oldprod[k]==0.15,(k,oldprod[k])
  last=0
  for raw in (.15,.150001,.151,.1575,.165,.18,.219999,.22,.220001,.24,.3):
   eff,_=sv.production_multiplier(k,'Speculative',{k:raw},cfg['no_real_history'],cfg['role_mult'],cfg['cal22_keys'])
   assert eff>=last,(k,raw,eff,last)
   last=eff
   probe=dict(cfg);probe['prod_mult']=dict(oldprod);probe['prod_mult'][k]=raw
   val=sv.compute_all_values(probe)[k]['value']
   suspects.append((k,raw,val))
  per=[v for name,r,v in suspects if name==k]
  assert per==sorted(per),(k,per)
 assert len(suspects)==48*11
 print('PASS CAL22: 48 guard keys, no current FV change 565/565, prior IDP/CAL15 lineage, 528 raw monotonicity probes')
 return {'status':'PASS','guard_keys':48,'current_fv_changes':0,'prior':previous['status']}

if __name__=='__main__':validate_deployment_successor()
