#!/usr/bin/env node
'use strict';
/** LOG R1 read-only Role V2 display checks. Pass candidate index.html as arg 1.
 * No network, no vote/market/holdout access, and no repository writes.
 */
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const path=require('node:path');
const main=process.argv[2] || 'index.html';
const code=fs.readFileSync(main,'utf8');
const start='/* LOG_R1_ROLE_BAND_INLINE_DISPLAY_ONLY_BEGIN';
const end='/* LOG_R1_ROLE_BAND_INLINE_DISPLAY_ONLY_END */';
assert.equal(code.split(start).length,2,'unique candidate helper opening marker');
assert.equal(code.split(end).length,2,'unique candidate helper closing marker');
const segment=code.slice(code.indexOf(start),code.indexOf(end)+end.length);
new vm.Script(segment,{filename:'inline_role_band_candidate.js'});

const norm=s=>String(s||'').toLowerCase().replace(/[.'’-]/g,'').replace(/\s+/g,' ').trim();
const htmlEscape=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
const lookup={
  'justin herbert':'6797',
  'bijan robinson':'9509',
  'joshua metellus':'6901',
  'name with html <tag>':'999999',
};
let renderCount=0;
const ctx={
  PACKAGE_UI_SLEEPER_IDS: Object.freeze(lookup), normalizeName:norm,escapeHtml:htmlEscape,
  render:()=>renderCount++,console:{warn:()=>{}},
};
vm.createContext(ctx);vm.runInContext(segment,ctx);
const tiers=['Speculative','Depth','Understudy','Rotational','Starter','Every-Down','Elite'];
const labels=['Bottom Band','Low Band','Lower-Middle Band','Middle Band','Upper-Middle Band','High Band','Top Band'];
function makeFixture(){
  const players=Array.from({length:1450},(_,i)=>({
    sleeper_id:String(30000+i),position:'QB',role_tier:tiers[i%7],name:'Synthetic '+i
  }));
  players[0]={sleeper_id:'6797',position:'QB',role_tier:'Rotational',name:'Justin Herbert'};
  players[1]={sleeper_id:'9509',position:'RB',role_tier:'Elite',name:'Bijan Robinson'};
  players[2]={sleeper_id:'6901',position:'LB',role_tier:'Starter',name:'Joshua Metellus'};
  players[3]={sleeper_id:'999999',position:'WR',role_tier:'Depth',name:'Name with HTML'};
  return {schema_version:1,season:2026,week:5,valuation_adjustments_authorized:false,players};
}
function expectThrow(payload,phrase){assert.throws(()=>ctx.logR1ParseFrozenBands(payload),new RegExp(phrase));}
const valid=makeFixture();
const baseline=JSON.stringify(valid);
assert.equal(ctx.logR1SetFrozenBands(valid),1450);
assert.equal(JSON.stringify(valid),baseline,'frozen fixture remains unchanged');
assert.match(ctx.logR1RoleBandInlineHTML('Justin Herbert','QB'),/W5 projection band: Middle Band \(Week 5 snapshot\)/);
assert.match(ctx.logR1RoleBandInlineHTML('Bijan Robinson','RB'),/Top Band/);
assert.equal(ctx.logR1RoleBandInlineHTML('Justin Herbert','RB'),'','wrong position fails closed');
assert.equal(ctx.logR1RoleBandInlineHTML('Joshua Metellus','DL'),'','LB vs DL mismatch fails closed');
assert.equal(ctx.logR1RoleBandInlineHTML('Unknown player','QB'),'','missing stable ID fails closed');
assert.equal(ctx.logR1RoleBandInlineHTML('Bijan Robinson','WR'),'','a player must not cross position');
assert.match(ctx.logR1RoleBandInlineHTML('Name with HTML <tag>','WR'),/Low Band/);
assert.ok(!ctx.logR1RoleBandInlineHTML('Justin Herbert','QB').includes('confidence='));
for(let i=0;i<7;i++){
  const d=makeFixture();d.players[0].role_tier=tiers[i];
  ctx.logR1SetFrozenBands(d);
  assert.ok(ctx.logR1RoleBandInlineHTML('Justin Herbert','QB').includes(labels[i]),tiers[i]);
}
const clash=makeFixture();clash.players[1].sleeper_id='6797';
ctx.logR1SetFrozenBands(clash);
assert.equal(ctx.logR1RoleBandInlineHTML('Justin Herbert','QB'),'','duplicate Sleeper ID fails closed');
let bad=makeFixture();bad.week=6;expectThrow(bad,'schema');
bad=makeFixture();bad.valuation_adjustments_authorized=true;expectThrow(bad,'contract');
bad=makeFixture();bad.players.pop();expectThrow(bad,'size');
bad=makeFixture();bad.players[0].role_tier='UncalibratedHero';expectThrow(bad,'tier');
bad=makeFixture();bad.players[0].sleeper_id='unknown';expectThrow(bad,'identity');
// Missing or failed data must never mutate FV or invent tier metadata.
const fvState=Object.freeze({indexPrice:4141,marketPrice:4200,packageAdjustment:320,tradeVerdict:'Slightly Favors A'});
assert.equal(Object.keys(fvState).length,4);
assert.equal(ctx.logR1RoleBandInlineHTML('Justin Herbert','QB'),'');
const prices=['PICK_BASE','YEAR_DISCOUNT','PROD_MULT_DATA','ROLE_MULT','PLAYER_DB','playerValue('];
assert.ok(prices.every(p=>!segment.includes(p)), 'Role integration helper must not reference core pricing tables/functions');
assert.match(code,/logR1RoleBandInlineHTML\(a\.name, a\.pos\)/);
assert.match(code,/logR1RoleBandInlineHTML\(r\.key, r\.info\.pos\)/);
assert.match(code,/logR1SyncFrozenBands\(\);/);
(async () => {
  // Real fetch errors fail closed, leaving baseline pricing and FV role intact.
  ctx.fetch=async () => { throw new Error('offline'); };
  const before=renderCount;
  ctx.logR1SyncFrozenBands();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(renderCount,before+1,'a failed fetch rerenders without a band');
  assert.equal(ctx.logR1RoleBandInlineHTML('Justin Herbert','QB'),'');
  ctx.fetch=async () => ({ok:true,json:async () => makeFixture()});
  ctx.logR1SyncFrozenBands();
  await new Promise(resolve => setImmediate(resolve));
  assert.match(ctx.logR1RoleBandInlineHTML('Justin Herbert','QB'),/Middle Band/);
  console.log('PASS: LOG R1 display-only helper: 7 bands, stable IDs, position mismatches, collisions, malformed source, fetch success/failure and HTML integration markers.');
})().catch(e => { console.error(e); process.exitCode=1; });
