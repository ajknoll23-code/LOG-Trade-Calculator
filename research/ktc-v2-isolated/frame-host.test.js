/* QF11 V33: research-only server HtmlService integration tests. No network. */
'use strict';
const fs=require('fs'),assert=require('assert'),vm=require('vm'),crypto=require('crypto');
const dir=__dirname,gs=fs.readFileSync(dir+'/frame-host.gs','utf8'),html=fs.readFileSync(dir+'/pilot-frame.html','utf8');
const collector=fs.readFileSync(dir+'/collector.gs','utf8');
const schema='QF11_KTC_V2_PILOT_RESPONSE_V1',secret='TEST_ONLY_SECRET_123456789012345678901234567890';
const token='QF11_V33_SYNTHETIC_SAMPLE_INVITATION_TOKEN_001';
const digest=crypto.createHmac('sha256',secret).update(token).digest('base64url');
const head=['received_utc','delete_due_utc','schema','slot','display_order','token_hmac','keep','trade','cut','q1','q2','q3','review_status'];
let rows=[head],locked=false,tests=0;
const props={
 QF11_V2_ENABLED:'false',QF11_V2_HALTED:'false',QF11_V2_CLOSED:'false',
 QF11_V2_HMAC_SECRET:secret,QF11_V2_SHEET_ID:'NEW_V2_TEST_SHEET',QF11_V1_SHEET_ID:'V1_SEPARATE_TEST_SHEET',QF11_V2_SEPARATE_SHEET_VERIFIED:'YES',
 QF11_V2_INVITES_JSON:JSON.stringify({[digest]:{slot:1,display_order:0}}),
 QF11_V2_PLAYER_KEYS_JSON:JSON.stringify(['sample_a','sample_b','sample_c']),
 QF11_V2_PLAYER_LABELS_JSON:JSON.stringify(['Sample A','Sample B','Sample C'])
};
const pp={getProperty:k=>props[k]??null,setProperty:(k,v)=>props[k]=String(v)};
const sh={getRange:(r,c,n)=>({getValues:()=>rows.slice(r-1,r-1+n).map(x=>x.slice(c-1,c+head.length-1))}),getDataRange:()=>({getValues:()=>rows.map(x=>x.slice())}),appendRow:x=>rows.push(x),deleteRow:n=>rows.splice(n-1,1)};
const env={PropertiesService:{getScriptProperties:()=>pp},LockService:{getScriptLock:()=>({tryLock(){if(locked)return false;locked=true;return true},releaseLock(){locked=false}})},SpreadsheetApp:{openById:id=>({getSheetByName:n=>id==='NEW_V2_TEST_SHEET'&&n==='Responses'?sh:null})},
 Utilities:{computeHmacSha256Signature:(t,s)=>Array.from(crypto.createHmac('sha256',s).update(t).digest()),base64EncodeWebSafe:x=>Buffer.from(x).toString('base64url')},
 HtmlService:{XFrameOptionsMode:{ALLOWALL:'ALLOWALL'},createHtmlOutput:s=>({content:s}),createHtmlOutputFromFile:name=>({name,setXFrameOptionsMode(v){this.mode=v;return this}})},
 Date,JSON,Object,Array,String,Number,Set,Error,Math};
vm.createContext(env);vm.runInContext(collector+'\n'+gs,env,{timeout:2000});
function T(label,fun){fun();tests++;console.log('PASS '+label)}
const guards=['QF11_V2_ENABLED','QF11_V2_IFRAME_TRANSPORT_VERIFIED','QF11_V2_OWNER_PILOT_AUTHORIZED','QF11_V2_INDEPENDENT_WORDING_QC','QF11_V2_PRIVACY_DELETION_VERIFIED','QF11_V2_MODERATOR_SOP_VERIFIED','QF11_V2_COLLECTOR_ISOLATION_VERIFIED'];
T('disabled is default and does not expose ballot',()=>{assert(/not accepting/.test(env.doGet().content));assert.equal(env.qf11v33Bootstrap(token).status,'DISABLED');assert.equal(rows.length,1)});
guards.forEach(k=>props[k]='true');
T('all seven explicit gates needed',()=>{for(const k of guards){props[k]='false';assert(/not accepting/.test(env.doGet().content),k);props[k]='true'}});
T('enabled source exposes iframe template only',()=>{const res=env.doGet();assert.equal(res.name,'pilot-frame');assert.equal(res.mode,'ALLOWALL')});
T('reject missing or malformed code',()=>{assert.equal(env.qf11v33Bootstrap('bad').status,'REJECTED_TOKEN_FORMAT')});
T('reject unknown code',()=>{assert.equal(env.qf11v33Bootstrap(token.slice(0,-1)+'2').status,'REJECTED_INVITATION')});
T('valid code returns correct assigned three labels',()=>{const res=env.qf11v33Bootstrap(token);assert.equal(res.status,'READY');assert.equal(res.display_order,0);assert.deepEqual(JSON.parse(JSON.stringify(res.players)),[{key:'sample_a',label:'Sample A'},{key:'sample_b',label:'Sample B'},{key:'sample_c',label:'Sample C'}])});
T('reject V1 and V2 sheet equality before bootstrap',()=>{const old=props.QF11_V1_SHEET_ID;props.QF11_V1_SHEET_ID=props.QF11_V2_SHEET_ID;assert.throws(()=>env.qf11v33Bootstrap(token));props.QF11_V1_SHEET_ID=old});
T('reject missing player labels config',()=>{const old=props.QF11_V2_PLAYER_LABELS_JSON;props.QF11_V2_PLAYER_LABELS_JSON='[]';assert.equal(env.qf11v33Bootstrap(token).status,'INVALID_CONFIG');props.QF11_V2_PLAYER_LABELS_JSON=old});
const good={schema,participant_token:token,display_order:0,consent:true,adult:true,sf_idp_experience:true,keep:'sample_a',trade:'sample_b',cut:'sample_c',mc:[1,1,0]};
T('handler stores one acknowledged moderated response',()=>{assert.equal(env.qf11v33Submit(good).status,'PENDING_HUMAN_Q4_REVIEW');assert.equal(rows.length,2)});
T('duplicate is rejected with no second row',()=>{assert.equal(env.qf11v33Submit(good).status,'DUPLICATE_OR_SLOT_USED');assert.equal(rows.length,2)});
T('used invitation bootstrap is rejected',()=>{assert.equal(env.qf11v33Bootstrap(token).status,'ALREADY_USED_OR_CLOSED')});
T('halt means disabled no further votes',()=>{props.QF11_V2_HALTED='true';assert.equal(env.qf11v33Submit(good).status,'DISABLED');assert.equal(env.qf11v33Bootstrap(token).status,'DISABLED');props.QF11_V2_HALTED='false'});
T('missing gate disables RPC',()=>{props.QF11_V2_OWNER_PILOT_AUTHORIZED='false';assert.equal(env.qf11v33Submit(good).status,'DISABLED');props.QF11_V2_OWNER_PILOT_AUTHORIZED='true'});
T('HTML avoids cross origin fetch, postMessage, browser storage',()=>{for(const x of ['fetch(', 'postMessage(', 'localStorage', 'sessionStorage', 'XMLHttpRequest','innerHTML'])assert(!html.includes(x),x)});
T('HTML uses Apps Script google.script.run handlers',()=>{assert(html.includes('google.script.run.withSuccessHandler'));assert(html.includes('withFailureHandler(error)'));assert(html.includes('qf11v33Submit(payload)'))});
T('HTML enforces hosting origin and one attempt',()=>{assert(html.includes('document.referrer'));assert(html.includes('EXPECTED_ORIGIN'));assert(html.includes('attempted=true'))});
T('HTML user labels rendered as textContent',()=>{assert(html.includes('head.textContent=p.label'))});
T('q4 is not sent to collector',()=>{assert(!html.includes('id="q4"'));assert(!gs.includes('q4'))});
T('source neither includes V1 endpoint nor pilot player names',()=>{assert(!gs.includes('script.google.com/macros/s/'));assert(!html.includes('Brock Bowers'));assert(!html.includes('Tyler Warren'))});
console.log('QF11_V33_IFRAME_HOST_SOURCE_GREEN '+JSON.stringify({tests,participants:0,networkCalls:0}));
