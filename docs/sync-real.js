/* FASE 6.2C: isolated real-sync adapter.
 * This module is intentionally not imported by pilot-index.html yet.
 * It never writes through PostgREST tables; road mutations use only the
 * server-side apply_road_progress_mutation RPC.
 */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;root.KjoreloggRealSync=api})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const WRITE_ROLES=new Set(['owner','admin','driver']);
 const VERSION_RE=/^v\d+\.\d+\.\d+$/;
 function semver(v){const m=String(v||'').match(/^v(\d+)\.(\d+)\.(\d+)$/);return m?Number(m[1])*1e12+Number(m[2])*1e6+Number(m[3]):-1}
 function classify(error){
  const code=String(error?.code||error?.databaseCode||'');
  if(['PT401','42501','401'].includes(code))return'AUTH';
  if(['PT403','403'].includes(code))return'FORBIDDEN_READ_ONLY';
  if(['PT409','REVISION_CONFLICT'].includes(code))return'REVISION_CONFLICT';
  if(['PT412'].includes(code))return'LEASE_OR_FENCE_STALE';
  if(['PT426'].includes(code))return'CLIENT_TOO_OLD';
  if(['22023'].includes(code))return'INVALID_MUTATION_IDEMPOTENCY_CONFLICT';
  if(error?.name==='TypeError'||/network|fetch|offline|failed to fetch/i.test(String(error?.message||'')))return'OFFLINE_RETRYABLE';
  return'REMOTE_ERROR';
 }
 function normalizedError(error){const e=error instanceof Error?error:new Error(error?.message||'Real sync failed');e.realSyncClass=classify(error);e.databaseCode=error?.code||error?.databaseCode||null;return e}
 function canRealSyncWrite(state={}){
  const session=state.session||state.authSession;
  const membership=state.membership||{};
  const lease=state.lease||{};
  const version=String(state.clientVersion||'');
  return !!(session?.user?.id&&state.dataset?.id&&!String(state.dataset.dataset_key||'').startsWith('TEST_PHASE61_')&&
    WRITE_ROLES.has(String(membership.role||''))&&state.bootstrap_status==='COMPLETE'&&
    lease.id&&lease.dataset_id===state.dataset.id&&lease.session_id&&lease.device_id&&
    Number.isFinite(Number(lease.fencing_generation))&&Number(lease.fencing_generation)>0&&
    VERSION_RE.test(version)&&state.clientVersionApproved===true&&!state.frozen&&!state.conflict);
 }
 function resultValue(data){return Array.isArray(data)?data[0]:data}
 function normalizeResult(data){const r=resultValue(data)||{};return{ok:r.ok===true,dataset_id:r.dataset_id||null,road_key:r.road_key||null,revision:Number(r.revision),mutation_id:r.mutation_id||null,server_updated_at:r.server_updated_at||null,idempotent:r.idempotent===true,status:r.status||null}}
 function create(options={}){
  const client=options.client,auth=options.auth||client?.auth,clientVersion=String(options.clientVersion||'v2.0.105'),featureEnabled=options.featureEnabled!==false;
  if(!client?.rpc)throw new Error('RealSyncRemote krever Supabase-klient med rpc()');
  async function session(){const r=await auth?.getSession?.();if(r?.error)throw normalizedError(r.error);return r?.data?.session||r?.session||null}
  async function preflight(datasetId){
   const s=await session();if(!s?.user)throw Object.assign(new Error('Auth-session mangler'),{code:'PT401'});
   if(!datasetId)throw Object.assign(new Error('dataset_id mangler'),{code:'PT400'});
   const [d,m,c,l,roads]=await Promise.all([
    client.from('datasets').select('id,dataset_key,name,county,vehicle').eq('id',datasetId).maybeSingle(),
    client.from('dataset_members').select('dataset_id,user_id,role,active').eq('dataset_id',datasetId).eq('user_id',s.user.id).maybeSingle(),
    client.from('sync_runtime_config').select('minimum_write_client_version').single(),
    client.from('work_leases').select('id,dataset_id,user_id,device_id,session_id,fencing_generation,expires_at,released_at').eq('dataset_id',datasetId).is('released_at',null).maybeSingle(),
    client.from('road_progress').select('id',{count:'exact',head:true}).eq('dataset_id',datasetId)
   ]);
   for(const r of [d,m,c,l,roads])if(r.error)throw normalizedError(r.error);
   return{session:s,user:s.user,dataset:d.data||null,membership:m.data||null,minimum_client_version:c.data?.minimum_write_client_version||null,lease:l.data||null,road_progress_count:rCount(roads)};
  }
  async function pushRoadProgress(mutation,state={}){
   const s=await session();
   const gate=canRealSyncWrite({...state,session:s,clientVersion:clientVersion});
   if(!featureEnabled||!gate){const e=new Error('Real sync write gate er ikke oppfylt');e.code='REAL_SYNC_GATE_CLOSED';e.realSyncClass='GATE_CLOSED';throw e}
   const p=mutation||{};
   if(!p.dataset_id||!p.road_key||!p.mutation_id)throw Object.assign(new Error('dataset_id, road_key og mutation_id kreves'),{code:'22023'});
   try{
    const response=await client.rpc('apply_road_progress_mutation',{
     p_dataset_id:p.dataset_id,p_road_key:p.road_key,p_mutation_id:p.mutation_id,
     p_base_revision:Number(p.base_revision),p_fencing_generation:Number(state.lease.fencing_generation),
     p_lease_id:state.lease.id,p_session_id:state.lease.session_id,p_device_id:state.lease.device_id,
     p_client_version:clientVersion,p_status:p.status,p_payload:p.payload
    });
    if(response.error)throw response.error;
    return normalizeResult(response.data);
   }catch(error){throw normalizedError(error)}
  }
  return{clientVersion,canRealSyncWrite,preflight,pushRoadProgress,classifyError:classify,normalizeResult};
 }
 function rCount(r){return Number(r?.count||0)}
 return{create,canRealSyncWrite,classifyError:classify,normalizeResult,semver};
});
