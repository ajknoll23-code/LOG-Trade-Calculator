/* QF11 V32: isolated KTC V2 browser submission contract. NOT wired to index.html.
 * Deliberately disabled without six explicit, independently verified launch gates.
 * No V1 collection, no local storage, no retry, no log/analytics, no PII fields.
 */
(function(root,factory){
  'use strict';
  const exported=factory();
  if(typeof module==='object' && module.exports) module.exports=exported;
  else root.QF11KtcV2ClientBridge=exported;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const SCHEMA='QF11_KTC_V2_PILOT_RESPONSE_V1';
  const KEYS=['schema','participant_token','display_order','consent','adult','sf_idp_experience','keep','trade','cut','mc'];
  const ALLOWED_ACK=new Set([
    'PENDING_HUMAN_Q4_REVIEW','CRITICAL_STOP_QUARANTINED',
    'DISABLED','HALTED','CLOSED','BUSY_NO_SUBMISSION',
    'REJECTED_SCHEMA','REJECTED_EXTRA_FIELDS','REJECTED_TOKEN_FORMAT',
    'REJECTED_CONSENT_OR_ELIGIBILITY','REJECTED_UNASSIGNED_TOKEN',
    'REJECTED_ORDER','REJECTED_RANKING','REJECTED_COMPREHENSION_FORMAT',
    'DUPLICATE_OR_SLOT_USED','REJECTED_PAYLOAD','REJECTED_JSON',
    'HALTED_CONFIGURATION_OR_STORAGE_ERROR'
  ]);
  function isGoogleScriptExec(url){
    if(typeof url!=='string' || !url || url.trim()!==url)return false;
    try{
      const parsed=new URL(url);
      return parsed.protocol==='https:' && parsed.hostname==='script.google.com' &&
        /^\/macros\/s\/[A-Za-z0-9_-]{16,}\/exec$/.test(parsed.pathname) &&
        !parsed.search && !parsed.hash && !parsed.username && !parsed.password;
    }catch(e){return false;}
  }
  function validPayload(payload,players){
    if(!payload || typeof payload!=='object' || Array.isArray(payload))return false;
    if(!Array.isArray(players) || players.length!==3 || new Set(players).size!==3 ||
       players.some(k=>typeof k!=='string' || !/^[A-Za-z0-9:_-]{2,80}$/.test(k)))return false;
    if(Object.keys(payload).length!==KEYS.length || KEYS.some(k=>!Object.prototype.hasOwnProperty.call(payload,k)))return false;
    if(payload.schema!==SCHEMA || typeof payload.participant_token!=='string' ||
       !/^[A-Za-z0-9_-]{32,128}$/.test(payload.participant_token))return false;
    if(!Number.isInteger(payload.display_order) || payload.display_order<0 || payload.display_order>5)return false;
    if(payload.consent!==true || payload.adult!==true || payload.sf_idp_experience!==true)return false;
    const ranks=[payload.keep,payload.trade,payload.cut];
    if(new Set(ranks).size!==3 || ranks.some(k=>!players.includes(k)))return false;
    if(!Array.isArray(payload.mc) || payload.mc.length!==3 ||
       payload.mc.some(n=>!Number.isInteger(n)||n<0||n>2))return false;
    return true;
  }
  function createBridge(options){
    const opts=options||{};
    let attempted=false;
    let inFlight=false;
    function ready(){
      return opts.independentInstrumentQcApproved===true &&
        opts.ownerRealPilotActivationApproved===true &&
        opts.dedicatedCollectorDeploymentVerified===true &&
        opts.privacyAndDeletionVerified===true &&
        opts.moderatorAndCriticalStopSopVerified===true &&
        opts.independentCollectorIsolationVerified===true &&
        isGoogleScriptExec(opts.endpoint) && isGoogleScriptExec(opts.legacyV1Endpoint) &&
        opts.endpoint!==opts.legacyV1Endpoint &&
        typeof opts.fetchImpl==='function';
    }
    async function submit(payload){
      if(!ready())return {state:'BLOCKED_NOT_AUTHORIZED_OR_CONFIGURED'};
      if(inFlight || attempted)return {state:'LOCKED_NO_RETRY'};
      if(!validPayload(payload,opts.approvedPlayerKeys))return {state:'REJECTED_CLIENT_VALIDATION'};
      attempted=true;inFlight=true;
      try{
        const res=await opts.fetchImpl(opts.endpoint,{
          method:'POST',mode:'cors',credentials:'omit',redirect:'follow',
          referrerPolicy:'no-referrer',cache:'no-store',
          headers:{'Content-Type':'text/plain;charset=utf-8'},
          body:JSON.stringify(payload)
        });
        if(!res || res.ok!==true || res.type==='opaque' || typeof res.json!=='function')
          return {state:'UNCERTAIN_DO_NOT_RETRY'};
        if(!res.headers || typeof res.headers.get!=='function' ||
           !/application\/json/i.test(String(res.headers.get('content-type')||'')))
          return {state:'UNCERTAIN_DO_NOT_RETRY'};
        const ack=await res.json();
        if(!ack || typeof ack!=='object' || Array.isArray(ack) ||
           ack.schema!==SCHEMA || typeof ack.status!=='string' || !ALLOWED_ACK.has(ack.status) ||
           Object.keys(ack).some(k=>k!=='schema'&&k!=='status'))
          return {state:'UNCERTAIN_DO_NOT_RETRY'};
        if(ack.status==='PENDING_HUMAN_Q4_REVIEW')return {state:'AWAITING_MODERATOR_Q4_REVIEW'};
        if(ack.status==='CRITICAL_STOP_QUARANTINED')return {state:'CRITICAL_STOP_QUARANTINED'};
        return {state:'STOPPED_OR_NOT_ACCEPTED'};
      }catch(_){return {state:'UNCERTAIN_DO_NOT_RETRY'};}
      finally{inFlight=false;}
    }
    return Object.freeze({ready,submit,hasAttempted:()=>attempted});
  }
  return Object.freeze({SCHEMA,KEYS:Object.freeze(KEYS.slice()),validPayload,isGoogleScriptExec,createBridge});
});
