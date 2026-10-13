/* QF11 V31 local synthetic-only collector tests. NO REAL PARTICIPANT DATA. */
'use strict';
const fs=require('fs'),vm=require('vm'),crypto=require('crypto'),assert=require('assert');
const src=fs.readFileSync(__dirname+'/collector.gs','utf8');
const HEADERS=['received_utc','delete_due_utc','schema','slot','display_order','token_hmac','keep','trade','cut','q1','q2','q3','review_status'];
const schema='QF11_KTC_V2_PILOT_RESPONSE_V1';
const secret='TEST_ONLY_SECRET_123456789012345678901234567890';
const token=i=>'QF11_V31_SYNTHETIC_PARTICIPANT_TOKEN_'+String(i).padStart(3,'0');
const hmac=t=>crypto.createHmac('sha256',secret).update(t).digest('base64url');
const invite=Object.fromEntries(Array.from({length:12},(_,i)=>[hmac(token(i+1)),{slot:i+1,display_order:i%6}]));
let testCount=0;
function test(name,run){run();testCount++;console.log('PASS '+name)}
function fresh(){
  let rows=[HEADERS.slice()];let activeLock=false;
  const conf={QF11_V2_ENABLED:'false',QF11_V2_HALTED:'false',QF11_V2_CLOSED:'false',QF11_V2_SHEET_ID:'V2-TEST-ONLY',QF11_V1_SHEET_ID:'V1-TEST-ONLY',QF11_V2_SEPARATE_SHEET_VERIFIED:'YES',QF11_V2_HMAC_SECRET:secret,QF11_V2_INVITES_JSON:JSON.stringify(invite),QF11_V2_PLAYER_KEYS_JSON:JSON.stringify(['sample_a','sample_b','sample_c'])};
  const props={getProperty:k=>conf[k]??null,setProperty:(k,v)=>{conf[k]=String(v)}};
  const sheet={getRange:(r,c,n)=>({getValues:()=>rows.slice(r-1,r-1+n).map(v=>v.slice(c-1,c+HEADERS.length-1))}),
    getDataRange:()=>({getValues:()=>rows.map(x=>x.slice())}),appendRow:v=>{rows.push(v)},deleteRow:r=>{rows.splice(r-1,1)}};
  const globals={
    ContentService:{MimeType:{JSON:'application/json'},createTextOutput(s){return {s,setMimeType(m){return this},getContent(){return this.s}}}},
    PropertiesService:{getScriptProperties:()=>props},
    LockService:{getScriptLock(){return {tryLock(){if(activeLock)return false;activeLock=true;return true},releaseLock(){activeLock=false}}}},
    SpreadsheetApp:{openById(id){if(id!=='V2-TEST-ONLY')throw Error('UNKNOWN_SHEET');return {getSheetByName:n=>n==='Responses'?sheet:null}}},
    Utilities:{computeHmacSha256Signature:(t,key)=>Array.from(crypto.createHmac('sha256',key).update(t).digest()),base64EncodeWebSafe:bytes=>Buffer.from(bytes).toString('base64url')},
    Date,JSON,Object,Array,String,Number,Set,Error,Math
  };
  vm.createContext(globals);vm.runInContext(src,globals,{timeout:1000});
  const payload=(slot=1,over={})=>Object.assign({schema,participant_token:token(slot),display_order:(slot-1)%6,consent:true,adult:true,sf_idp_experience:true,keep:'sample_a',trade:'sample_b',cut:'sample_c',mc:[1,1,0]},over);
  const post=p=>JSON.parse(globals.doPost({postData:{contents:JSON.stringify(p)}}).getContent()).status;
  return {conf,rows,props,globals,payload,post};
}
const REQUIRED_GATE_KEYS=[
 'QF11_V2_ENABLED','QF11_V2_IFRAME_TRANSPORT_VERIFIED',
 'QF11_V2_OWNER_PILOT_AUTHORIZED','QF11_V2_INDEPENDENT_WORDING_QC',
 'QF11_V2_PRIVACY_DELETION_VERIFIED','QF11_V2_MODERATOR_SOP_VERIFIED',
 'QF11_V2_COLLECTOR_ISOLATION_VERIFIED'
];
const ready=()=>{let e=fresh();REQUIRED_GATE_KEYS.forEach(k=>e.conf[k]='true');return e};

test('disabled is default and writes nothing',()=>{let e=fresh();assert.equal(e.post(e.payload()),'DISABLED');assert.equal(e.rows.length,1)});
test('V35 each of seven missing approvals blocks direct doPost and handler',()=>{
  for(const key of REQUIRED_GATE_KEYS){
    let e=ready();e.conf[key]='false';
    assert.equal(e.post(e.payload()),'DISABLED',key);
    assert.equal(e.globals.qf11v2Handle_(e.payload(),e.props,Date.now()),'DISABLED',key);
    assert.equal(e.rows.length,1,key);
  }
});
test('V35 missing and incorrectly typed approval properties fail closed',()=>{
  for(const value of [undefined,'FALSE','True',true,0,'yes']){
    let e=ready();e.conf.QF11_V2_PRIVACY_DELETION_VERIFIED=value;
    assert.equal(e.post(e.payload()),'DISABLED');
    assert.equal(e.rows.length,1);
  }
});
test('V35 ENABLED alone must not accept even well-formed invite',()=>{
  let e=fresh();e.conf.QF11_V2_ENABLED='true';
  assert.equal(e.post(e.payload()),'DISABLED');
  assert.equal(e.rows.length,1);
});
test('happy path stored only in separate sheet and Q4 waits human',()=>{let e=ready();assert.equal(e.post(e.payload()),'PENDING_HUMAN_Q4_REVIEW');assert.equal(e.rows.length,2);assert.equal(e.rows[1][3],1);assert.equal(e.rows[1][5],hmac(token(1)));assert(!JSON.stringify(e.rows).includes(token(1)))});
test('duplicate same token rejected',()=>{let e=ready();e.post(e.payload());assert.equal(e.post(e.payload()),'DUPLICATE_OR_SLOT_USED');assert.equal(e.rows.length,2)});
test('reject unassigned',()=>{let e=ready();assert.equal(e.post(e.payload(1,{participant_token:token(15)})),'REJECTED_UNASSIGNED_TOKEN');assert.equal(e.rows.length,1)});
test('reject wrong display order',()=>{let e=ready();assert.equal(e.post(e.payload(2,{display_order:4})),'REJECTED_ORDER');assert.equal(e.rows.length,1)});
test('reject missing consent',()=>{let e=ready();assert.equal(e.post(e.payload(1,{consent:false})),'REJECTED_CONSENT_OR_ELIGIBILITY')});
test('reject nonadult',()=>{let e=ready();assert.equal(e.post(e.payload(1,{adult:false})),'REJECTED_CONSENT_OR_ELIGIBILITY')});
test('reject nonexpert',()=>{let e=ready();assert.equal(e.post(e.payload(1,{sf_idp_experience:false})),'REJECTED_CONSENT_OR_ELIGIBILITY')});
test('reject invalid ranking duplicate',()=>{let e=ready();assert.equal(e.post(e.payload(1,{trade:'sample_a'})),'REJECTED_RANKING')});
test('reject unknown player',()=>{let e=ready();assert.equal(e.post(e.payload(1,{cut:'malicious_person'})),'REJECTED_RANKING')});
test('reject invalid MC response',()=>{let e=ready();assert.equal(e.post(e.payload(1,{mc:[1,1,9]})),'REJECTED_COMPREHENSION_FORMAT')});
test('reject unsolicited PII/freeform Q4',()=>{let e=ready();assert.equal(e.post(e.payload(1,{q4:'some private name'})),'REJECTED_EXTRA_FIELDS')});
test('critical Q1 stops all future intake',()=>{let e=ready();assert.equal(e.post(e.payload(1,{mc:[0,1,0]})),'CRITICAL_STOP_QUARANTINED');assert.equal(e.conf.QF11_V2_HALTED,'true');assert.equal(e.post(e.payload(2)),'HALTED');assert.equal(e.rows.length,2)});
test('critical Q2 stops all future intake',()=>{let e=ready();assert.equal(e.post(e.payload(1,{mc:[1,0,0]})),'CRITICAL_STOP_QUARANTINED')});
test('critical Q3 stops all future intake',()=>{let e=ready();assert.equal(e.post(e.payload(1,{mc:[1,1,1]})),'CRITICAL_STOP_QUARANTINED')});
test('12 cap and balanced two per order enforced',()=>{let e=ready();for(let i=1;i<=12;i++)assert.equal(e.post(e.payload(i)),'PENDING_HUMAN_Q4_REVIEW');assert.equal(e.conf.QF11_V2_CLOSED,'true');assert.equal(e.rows.length,13);let counts=Object.fromEntries(Array.from({length:6},(_,i)=>[i,e.rows.slice(1).filter(v=>v[4]===i).length]));assert.deepEqual(Object.values(counts),[2,2,2,2,2,2]);assert.equal(e.post(e.payload(1)),'CLOSED')});
test('V1/V2 sheet ID equality halts before write',()=>{let e=ready();e.conf.QF11_V1_SHEET_ID=e.conf.QF11_V2_SHEET_ID;assert.equal(e.post(e.payload()),'HALTED_CONFIGURATION_OR_STORAGE_ERROR');assert.equal(e.rows.length,1);assert.equal(e.conf.QF11_V2_HALTED,'true')});
test('separation attestation absent halts',()=>{let e=ready();e.conf.QF11_V2_SEPARATE_SHEET_VERIFIED='NO';assert.equal(e.post(e.payload()),'HALTED_CONFIGURATION_OR_STORAGE_ERROR');assert.equal(e.rows.length,1)});
test('weak HMAC configuration halts',()=>{let e=ready();e.conf.QF11_V2_HMAC_SECRET='short';assert.equal(e.post(e.payload()),'HALTED_CONFIGURATION_OR_STORAGE_ERROR');assert.equal(e.rows.length,1)});
test('invalid JSON rejected without halting',()=>{let e=ready();assert.equal(JSON.parse(e.globals.doPost({postData:{contents:'{'}}).getContent()).status,'REJECTED_JSON')});
test('oversized payload rejected before parse',()=>{let e=ready();assert.equal(JSON.parse(e.globals.doPost({postData:{contents:'x'.repeat(4097)}}).getContent()).status,'REJECTED_PAYLOAD')});
test('retention: expiry deletes rows and halts intake',()=>{let e=ready();e.post(e.payload());e.rows[1][1]='2000-01-01T00:00:00.000Z';assert.equal(e.globals.purgeExpiredQF11V2Rows(),1);assert.equal(e.rows.length,1);assert.equal(e.conf.QF11_V2_HALTED,'true')});
test('retention: unexpired row untouched',()=>{let e=ready();e.post(e.payload());assert.equal(e.globals.purgeExpiredQF11V2Rows(),0);assert.equal(e.rows.length,2)});
test('unknown sheet name halts',()=>{let e=ready();e.conf.QF11_V2_SHEET_ID='BOGUS';assert.equal(e.post(e.payload()),'HALTED_CONFIGURATION_OR_STORAGE_ERROR')});
console.log('QF11_V31_ISOLATED_COLLECTOR_TESTS_GREEN '+JSON.stringify({tests:testCount,real_participants:0,live_submissions:0}));
