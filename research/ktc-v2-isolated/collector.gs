/**
 * QF11 V31 — KTC V2 isolated, fail-closed pilot collector SOURCE CODE ONLY.
 * Not deployed, not configured, not authorized for real participants.
 * Uses a new Google Apps Script project and separate Google Spreadsheet.
 * Do not put the V1 collector URL or V1 sheet ID here.
 * Only QF11 version-1 protocol JSON is accepted (not regular KTC votes).
 */
var QF11_V2_SCHEMA = 'QF11_KTC_V2_PILOT_RESPONSE_V1';
var QF11_V2_HEADERS = [
  'received_utc','delete_due_utc','schema','slot','display_order','token_hmac',
  'keep','trade','cut','q1','q2','q3','review_status'
];
var QF11_V2_EXPECTED = [1,1,0]; // proposed V25 MC answers; pending independent human wording QC.

function qf11v2Reply_(status) {
  // Intentionally reveal no participant-specific information or record fields.
  return ContentService.createTextOutput(JSON.stringify({schema:QF11_V2_SCHEMA,status:status}))
    .setMimeType(ContentService.MimeType.JSON);
}
function qf11v2Assert_(condition, message) { if(!condition) throw new Error(message); }
function qf11v2Required_(props, key) {
  var x=props.getProperty(key);
  qf11v2Assert_(typeof x==='string' && x.length>0,'MISSING_CONFIG_'+key);
  return x;
}
function qf11v2Sheet_(props) {
  var own=qf11v2Required_(props,'QF11_V2_SHEET_ID');
  var legacy=qf11v2Required_(props,'QF11_V1_SHEET_ID');
  qf11v2Assert_(own!==legacy,'SAME_AS_PRODUCTION_KTC_V1_SHEET');
  qf11v2Assert_(props.getProperty('QF11_V2_SEPARATE_SHEET_VERIFIED')==='YES', 'SEPARATION_NOT_ATTESTED');
  var sheet=SpreadsheetApp.openById(own).getSheetByName('Responses');
  qf11v2Assert_(!!sheet,'MISSING_RESPONSES_SHEET');
  var headers=sheet.getRange(1,1,1,QF11_V2_HEADERS.length).getValues()[0];
  qf11v2Assert_(JSON.stringify(headers)===JSON.stringify(QF11_V2_HEADERS),'SHEET_SCHEMA_MISMATCH');
  return sheet;
}
function qf11v2Hash_(token,secret) {
  var bytes=Utilities.computeHmacSha256Signature(token,secret);
  return Utilities.base64EncodeWebSafe(bytes).replace(/=+$/,'');
}
function qf11v2ValidToken_(v) { return typeof v==='string' && /^[A-Za-z0-9_-]{32,128}$/.test(v); }
function qf11v2Json_(props,key){
  var x=JSON.parse(qf11v2Required_(props,key));
  qf11v2Assert_(x && typeof x==='object','BAD_CONFIG_'+key);
  return x;
}
/**
 * V35: ALL direct intake paths require the same seven authorizations as the
 * iframe RPC host. Never mistake a single ENABLED switch for full approval.
 * This helper is intentionally self-contained (collector also has doPost).
 */
function qf11v2IntakeAuthorized_(props) {
  var required=[
    'QF11_V2_ENABLED','QF11_V2_IFRAME_TRANSPORT_VERIFIED',
    'QF11_V2_OWNER_PILOT_AUTHORIZED','QF11_V2_INDEPENDENT_WORDING_QC',
    'QF11_V2_PRIVACY_DELETION_VERIFIED','QF11_V2_MODERATOR_SOP_VERIFIED',
    'QF11_V2_COLLECTOR_ISOLATION_VERIFIED'
  ];
  return required.every(function(k){return props.getProperty(k)==='true';});
}
function qf11v2Handle_(payload,props,now) {
  // This routine must only run inside the Apps Script lock.
  if(!qf11v2IntakeAuthorized_(props)) return 'DISABLED';
  if(props.getProperty('QF11_V2_HALTED')==='true') return 'HALTED';
  if(props.getProperty('QF11_V2_CLOSED')==='true') return 'CLOSED';
  if(!payload || typeof payload!=='object' || Array.isArray(payload)) return 'REJECTED_SCHEMA';
  // Reject incidental PII and non-contract keys; Q4 is moderated separately, never sent to this endpoint.
  var allowed=['schema','participant_token','display_order','consent','adult','sf_idp_experience','keep','trade','cut','mc'];
  if(Object.keys(payload).some(function(k){return allowed.indexOf(k)<0;})) return 'REJECTED_EXTRA_FIELDS';
  if(payload.schema!==QF11_V2_SCHEMA) return 'REJECTED_SCHEMA';
  if(!qf11v2ValidToken_(payload.participant_token)) return 'REJECTED_TOKEN_FORMAT';
  if(payload.consent!==true || payload.adult!==true || payload.sf_idp_experience!==true) return 'REJECTED_CONSENT_OR_ELIGIBILITY';
  var secret=qf11v2Required_(props,'QF11_V2_HMAC_SECRET');
  qf11v2Assert_(secret.length>=32,'WEAK_HMAC_SECRET');
  var invites=qf11v2Json_(props,'QF11_V2_INVITES_JSON');
  var digest=qf11v2Hash_(payload.participant_token,secret);
  var assignment=Object.prototype.hasOwnProperty.call(invites,digest) ? invites[digest] : null;
  if(!assignment || !Number.isInteger(assignment.slot) || assignment.slot<1 || assignment.slot>12) return 'REJECTED_UNASSIGNED_TOKEN';
  var expectedOrder=(assignment.slot-1)%6;
  if(assignment.display_order!==expectedOrder || payload.display_order!==expectedOrder) return 'REJECTED_ORDER';
  var players=qf11v2Json_(props,'QF11_V2_PLAYER_KEYS_JSON');
  if(!Array.isArray(players) || players.length!==3 || new Set(players).size!==3 || players.some(function(x){return typeof x!=='string' || !/^[A-Za-z0-9:_-]{2,80}$/.test(x);})) throw new Error('BAD_PILOT_PLAYER_CONFIG');
  var choices=[payload.keep,payload.trade,payload.cut];
  if(choices.length!==3 || new Set(choices).size!==3 || !choices.every(function(x){return players.indexOf(x)!==-1;})) return 'REJECTED_RANKING';
  if(!Array.isArray(payload.mc) || payload.mc.length!==3 || !payload.mc.every(function(x){return Number.isInteger(x) && x>=0 && x<=2;})) return 'REJECTED_COMPREHENSION_FORMAT';
  var sheet=qf11v2Sheet_(props);
  var rows=sheet.getDataRange().getValues().slice(1);
  // V39: fail closed if the purge trigger failed or a deadline is corrupt.
  // Do not accept a fresh response while stale participant data remain.
  if(!Number.isFinite(now) || rows.some(function(row){
    var due=Date.parse(String(row[1]));
    return !Number.isFinite(due) || due<=now;
  })) {
    props.setProperty('QF11_V2_HALTED','true');
    return 'HALTED';
  }
  if(rows.some(function(row){return String(row[5])===digest || Number(row[3])===assignment.slot;})) return 'DUPLICATE_OR_SLOT_USED';
  if(rows.length>=12) {props.setProperty('QF11_V2_CLOSED','true');return 'CLOSED';}
  var critical=payload.mc.some(function(x,i){return x!==QF11_V2_EXPECTED[i];});
  var status=critical?'CRITICAL_STOP_QUARANTINED':'PENDING_HUMAN_Q4_REVIEW';
  var start=new Date(now);var expires=new Date(now+30*24*3600*1000);
  sheet.appendRow([start.toISOString(),expires.toISOString(),QF11_V2_SCHEMA,assignment.slot,
    expectedOrder,digest,payload.keep,payload.trade,payload.cut,
    payload.mc[0],payload.mc[1],payload.mc[2],status]);
  if(critical) props.setProperty('QF11_V2_HALTED','true');
  else if(rows.length+1>=12)props.setProperty('QF11_V2_CLOSED','true');
  return status;
}
function doPost(e) {
  // Never log request bodies, invite tokens, or response values.
  var props=PropertiesService.getScriptProperties();
  if(!qf11v2IntakeAuthorized_(props)) return qf11v2Reply_('DISABLED');
  if(props.getProperty('QF11_V2_HALTED')==='true') return qf11v2Reply_('HALTED');
  var lock=LockService.getScriptLock();
  if(!lock.tryLock(15000)) return qf11v2Reply_('BUSY_NO_SUBMISSION');
  try {
    var raw=e&&e.postData&&e.postData.contents;
    if(typeof raw!=='string' || raw.length>4096) return qf11v2Reply_('REJECTED_PAYLOAD');
    var payload;
    try {payload=JSON.parse(raw);}catch(err){return qf11v2Reply_('REJECTED_JSON');}
    return qf11v2Reply_(qf11v2Handle_(payload,props,Date.now()));
  } catch(error) {
    // Fails closed and does not disclose error/participant details to public clients.
    props.setProperty('QF11_V2_HALTED','true');
    return qf11v2Reply_('HALTED_CONFIGURATION_OR_STORAGE_ERROR');
  } finally {lock.releaseLock();}
}
/**
 * Install a daily trigger manually after independent review and before activation.
 * Deletion is NOT operational until the trigger is installed and verified.
 * This routine deletes complete expired rows; pause intake on any expiry.
 */
function purgeExpiredQF11V2Rows() {
  var props=PropertiesService.getScriptProperties();
  var lock=LockService.getScriptLock();
  var acquired=false;
  try {
    qf11v2Assert_(lock.tryLock(15000),'LOCK_UNAVAILABLE');
    acquired=true;
    var sheet=qf11v2Sheet_(props),values=sheet.getDataRange().getValues();
    var now=Date.now(),expired=[];
    for(var i=values.length-1;i>=1;i--){
      var due=Date.parse(String(values[i][1]));
      if(!Number.isFinite(due) || due<=now)expired.push(i+1);
    }
    // V39: halt BEFORE attempting any deletion, including partial failures.
    if(expired.length>0)props.setProperty('QF11_V2_HALTED','true');
    expired.forEach(function(row){sheet.deleteRow(row);});
    // Only return a count (no respondent identifiers or raw data).
    return expired.length;
  } catch(error) {
    // A failed scheduled purge must not leave intake authorized.
    props.setProperty('QF11_V2_HALTED','true');
    throw error;
  } finally {if(acquired)lock.releaseLock();}
}
