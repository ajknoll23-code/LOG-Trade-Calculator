/** QF11 V33 — experimental HtmlService RPC alternative, SOURCE ONLY. No deployment. */
var QF11_V33_TRUSTED_PARENT_ORIGIN='https://ajknoll23-code.github.io';
var QF11_V33_SCHEMA='QF11_KTC_V2_PILOT_RESPONSE_V1';
var QF11_V33_REQUIRED_GATES=[
 'QF11_V2_ENABLED', 'QF11_V2_IFRAME_TRANSPORT_VERIFIED',
 'QF11_V2_OWNER_PILOT_AUTHORIZED','QF11_V2_INDEPENDENT_WORDING_QC',
 'QF11_V2_PRIVACY_DELETION_VERIFIED','QF11_V2_MODERATOR_SOP_VERIFIED',
 'QF11_V2_COLLECTOR_ISOLATION_VERIFIED'
];
function qf11v33Ready_(props){
 return QF11_V33_REQUIRED_GATES.every(function(k){return props.getProperty(k)==='true';}) &&
   props.getProperty('QF11_V2_HALTED')!=='true' && props.getProperty('QF11_V2_CLOSED')!=='true';
}
function doGet(e){
 var props=PropertiesService.getScriptProperties();
 if(!qf11v33Ready_(props))return HtmlService.createHtmlOutput('<p>KTC V2 is not accepting pilot responses.</p>');
 // ALLOWALL is needed for embedding; clickjacking/origin controls require separate human privacy review.
 return HtmlService.createHtmlOutputFromFile('pilot-frame')
   .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}
function qf11v33Bootstrap(token){
 var props=PropertiesService.getScriptProperties();
 if(!qf11v33Ready_(props))return {status:'DISABLED'};
 if(!qf11v2ValidToken_(token))return {status:'REJECTED_TOKEN_FORMAT'};
 var secret=qf11v2Required_(props,'QF11_V2_HMAC_SECRET');
 qf11v2Assert_(secret.length>=32,'WEAK_HMAC_SECRET');
 var digest=qf11v2Hash_(token,secret);
 var invites=qf11v2Json_(props,'QF11_V2_INVITES_JSON');
 var entry=Object.prototype.hasOwnProperty.call(invites,digest)?invites[digest]:null;
 if(!entry||!Number.isInteger(entry.slot)||entry.slot<1||entry.slot>12||entry.display_order!==(entry.slot-1)%6)return {status:'REJECTED_INVITATION'};
 var sheet=qf11v2Sheet_(props);
 var rows=sheet.getDataRange().getValues().slice(1);
 if(rows.length>=12 || rows.some(function(row){return row[5]===digest || Number(row[3])===entry.slot;}))return {status:'ALREADY_USED_OR_CLOSED'};
 var players=qf11v2Json_(props,'QF11_V2_PLAYER_KEYS_JSON');
 var labels=qf11v2Json_(props,'QF11_V2_PLAYER_LABELS_JSON');
 if(!Array.isArray(players)||players.length!==3||new Set(players).size!==3)return {status:'INVALID_CONFIG'};
 if(!Array.isArray(labels)||labels.length!==3||labels.some(function(v){return typeof v!=='string'||v.length>70;}))return {status:'INVALID_CONFIG'};
 var orders=[[0,1,2],[0,2,1],[1,0,2],[1,2,0],[2,0,1],[2,1,0]];
 return {status:'READY',display_order:entry.display_order,players:orders[entry.display_order].map(function(i){return {key:players[i],label:labels[i]};})};
}
function qf11v33Submit(payload){
 var props=PropertiesService.getScriptProperties();
 if(!qf11v33Ready_(props))return {schema:QF11_V33_SCHEMA,status:'DISABLED'};
 var lock=LockService.getScriptLock();
 if(!lock.tryLock(15000))return {schema:QF11_V33_SCHEMA,status:'BUSY_NO_SUBMISSION'};
 try{return {schema:QF11_V33_SCHEMA,status:qf11v2Handle_(payload,props,Date.now())};}
 catch(err){props.setProperty('QF11_V2_HALTED','true');return {schema:QF11_V33_SCHEMA,status:'HALTED_CONFIGURATION_OR_STORAGE_ERROR'};}
 finally{lock.releaseLock();}
}
