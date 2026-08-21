(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;root.KjoreloggSync=api})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const PULL_ENTITIES=['road_progress','asphalt_plan','asphalt_progress'];
 function sameComment(a,b){return String(a?.comment||'')===String(b?.comment||'')}
 function mergeProgress(local,remote){
  if(!local)return{action:'remote',payload:remote};
  if(local.status===remote.status&&!!local.direction_fwd===!!remote.direction_fwd&&!!local.direction_rev===!!remote.direction_rev&&sameComment(local,remote))return{action:'remote',payload:remote};
  if(!sameComment(local,remote)&&String(local.comment||'')&&String(remote.comment||''))return{action:'conflict',reason:'COMMENT_DIVERGED'};
  if(new Set([local.status,remote.status]).has('SKIPPED')&&local.status!==remote.status)return{action:'conflict',reason:'SKIPPED_VS_PROGRESS'};
  if(local.status==='ONE_DIRECTION'&&remote.status==='COMPLETED')return{action:'remote',payload:{...remote,comment:local.comment||remote.comment||null}};
  if(local.status==='COMPLETED'&&remote.status==='ONE_DIRECTION')return{action:'merged',payload:{...local,comment:local.comment||remote.comment||null}};
  if(local.status==='ONE_DIRECTION'&&remote.status==='ONE_DIRECTION'&&!local.single_direction&&!remote.single_direction&&((local.direction_fwd&&!local.direction_rev&&remote.direction_rev&&!remote.direction_fwd)||(local.direction_rev&&!local.direction_fwd&&remote.direction_fwd&&!remote.direction_rev)))return{action:'merged',payload:{...remote,status:'COMPLETED',direction_fwd:true,direction_rev:true,comment:local.comment||remote.comment||null}};
  return{action:'conflict',reason:'UNSAFE_CONCURRENT_CHANGE'};
 }
 function create(options={}){
  const local=options.local,remote=options.remote,auth=options.auth,adapter=options.adapter||{},online=options.online||(()=>globalThis.navigator?.onLine!==false),listeners=new Set();let running=false,state={phase:'idle',pending:0,error:null,last_sync:null};
  function emit(patch={}){state={...state,...patch};for(const listener of listeners)try{listener({...state})}catch(error){console.warn('Sync listener failed',error)}}
  async function refreshStatus(){const pending=await local.countPending();emit({pending});return pending}
  function backoff(attempts){return Math.min(15*60*1000,Math.max(2000,2**Math.min(attempts,8)*1000))}
  async function pushPendingChanges(){
   const rows=await local.listPending(100);let pushed=0;
   for(const row of rows){
    try{const ack=await remote.push(row,await local.getDeviceId());await adapter.onPushAck?.(row,ack);await local.remove(row.id);pushed++}
    catch(error){
     const attempts=(row.attempts||0)+1,server=error.conflict?await remote.fetchEntity(row.entity_type,row.entity_key).catch(()=>null):null;
     if(error.conflict){await local.update(row.id,{attempts,last_attempt_at:new Date().toISOString(),last_error:error.message,state:'conflict',conflict:{reason:'STALE_REVISION',entity:row.entity_type,entity_key:row.entity_key,local_revision:row.base_revision,server_revision:server?.revision??null,local_payload:row.payload,server_payload:server}});continue}
     await local.update(row.id,{attempts,last_attempt_at:new Date().toISOString(),last_error:error.message,state:'retry',next_attempt_at:new Date(Date.now()+backoff(attempts)).toISOString()});
     if(['AUTH_REQUIRED','401','403'].includes(String(error.code)))break;
    }
   }
   await refreshStatus();return pushed;
  }
  async function pullRemoteChanges(){
   let pulled=0;
   for(const entityType of PULL_ENTITIES){
    let cursor=await local.getMeta(`pull_cursor:${entityType}`),more=true;
    while(more){
     const page=await remote.pullTable(entityType,cursor,500);
     for(const row of page.rows){
      const entityKey=adapter.remoteEntityKey?.(entityType,row);if(!entityKey)continue;
      const pending=await local.findPending(entityType,entityKey);
      if(!pending){await adapter.applyRemote?.(entityType,row);pulled++;continue}
      const decision=(entityType==='road_progress'||entityType==='asphalt_progress')?mergeProgress(pending.payload,row):{action:'conflict',reason:'PENDING_LOCAL_CHANGE'};
      if(decision.action==='remote'){await adapter.applyRemote?.(entityType,row);await local.remove(pending.id);pulled++}
      else if(decision.action==='merged'){await adapter.applyRemote?.(entityType,decision.payload);await local.enqueue({entity_type:entityType,entity_key:entityKey,payload:decision.payload,base_revision:row.revision});pulled++}
      else await local.update(pending.id,{state:'conflict',last_error:decision.reason,conflict:{reason:decision.reason,entity:entityType,entity_key:entityKey,local_revision:pending.base_revision,server_revision:row.revision,local_payload:pending.payload,server_payload:row}});
     }
     cursor=page.cursor;if(cursor)await local.setMeta(`pull_cursor:${entityType}`,cursor);more=page.rows.length===500;
    }
   }
   return pulled;
  }
  async function syncNow(){
   if(running)return{skipped:'already_running'};if(!online()){await refreshStatus();emit({phase:'offline',error:null});return{skipped:'offline'}};if(!await auth.getSession()){await refreshStatus();emit({phase:'signed_out',error:null});return{skipped:'signed_out'}};
   running=true;emit({phase:'syncing',error:null});
   try{await remote.registerDevice({device_id:await local.getDeviceId(),device_name:adapter.deviceName?.()||null,platform:adapter.platform?.()||null,app_version:adapter.appVersion?.()||null});const pushed=await pushPendingChanges(),pulled=await pullRemoteChanges(),last_sync=new Date().toISOString();await local.setMeta('last_successful_sync',last_sync);emit({phase:'synced',last_sync,error:null});return{pushed,pulled}}
   catch(error){emit({phase:'error',error:error.message});return{error}}
   finally{running=false;await refreshStatus()}
  }
  function onStatus(listener){listeners.add(listener);listener({...state});return()=>listeners.delete(listener)}
  return{syncNow,pushPendingChanges,pullRemoteChanges,refreshStatus,onStatus,getState:()=>({...state})};
 }
 return{mergeProgress,create};
});
