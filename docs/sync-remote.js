(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;root.KjoreloggRemote=api})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const ENTITY={road_progress:{table:'road_progress',owner:'user_id',key:'road_key'},asphalt_plan:{table:'asphalt_plans',owner:'owner_user_id',key:'plan_key'},asphalt_progress:{table:'asphalt_progress',owner:'user_id',key:'plan_id'},app_setting:{table:'app_settings',owner:'user_id',key:'setting_key'},day_plan:{table:'day_plans',owner:'user_id',key:'plan_date'},measurement_track:{table:'measurement_tracks',owner:'user_id',key:'id'}};
 function normalizeError(error){const databaseCode=error?.code||null,e=new Error(error?.message||'Remote operation failed');e.databaseCode=databaseCode;e.details=error?.details||null;e.hint=error?.hint||null;if(databaseCode==='PT409'){e.code='REVISION_CONFLICT';e.httpStatus=409;e.conflict=true}else e.code=databaseCode;return e}
 function create(options={}){
  const auth=options.auth,planIdByKey=new Map(),planKeyById=new Map();
  async function context(){const client=auth?.getClient?.(),session=await auth?.getSession?.();if(!client||!session?.user)throw Object.assign(new Error('Ingen gyldig Supabase-session'),{code:'AUTH_REQUIRED'});return{client,user:session.user}}
  function rememberPlan(row){if(row?.id&&row?.plan_key){planIdByKey.set(row.plan_key,row.id);planKeyById.set(row.id,row.plan_key)}return row}
  async function resolveAsphaltPlanId(planKey,knownPlanId=null){
   if(!planKey)throw Object.assign(new Error('Logical asphalt plan_key mangler'),{code:'ASPHALT_PLAN_KEY_REQUIRED'});
   const{client,user}=await context(),result=await client.from('asphalt_plans').select('id,plan_key').eq('owner_user_id',user.id).eq('plan_key',String(planKey)).limit(2);
   if(result.error)throw normalizeError(result.error);
   if(!result.data?.length)throw Object.assign(new Error(`Fant ikke asfaltplan for plan_key ${planKey}`),{code:'ASPHALT_PLAN_NOT_FOUND'});
   if(result.data.length!==1)throw Object.assign(new Error(`Flere asfaltplaner har plan_key ${planKey}`),{code:'ASPHALT_PLAN_KEY_AMBIGUOUS'});
   const row=rememberPlan(result.data[0]);
   if(knownPlanId&&knownPlanId!==row.id)throw Object.assign(new Error('Cached plan_id tilhører ikke oppgitt plan_key'),{code:'ASPHALT_PLAN_ID_MISMATCH'});
   return row.id;
  }
  async function registerDevice(device){const{client,user}=await context(),payload={user_id:user.id,...device,last_seen_at:new Date().toISOString()};const result=await client.from('devices').upsert(payload,{onConflict:'user_id,device_id'}).select().single();if(result.error)throw normalizeError(result.error);return result.data}
  async function push(mutation,deviceId){
   const meta=ENTITY[mutation.entity_type];if(!meta)throw new Error(`Unsupported entity ${mutation.entity_type}`);
   const{client,user}=await context();let source={...mutation.payload};
   if(mutation.entity_type==='asphalt_progress'){
    source.plan_id=await resolveAsphaltPlanId(source.plan_key||mutation.entity_key,source.plan_id||null);delete source.plan_key;
   }
   const payload={...source,[meta.owner]:user.id,device_id:deviceId,last_mutation_id:mutation.mutation_id,revision:mutation.base_revision||1};
   let result;
   if(Number(mutation.base_revision)>0){result=await client.from(meta.table).update(payload).eq(meta.owner,user.id).eq(meta.key,payload[meta.key]).select().single()}
   else result=await client.from(meta.table).insert(payload).select().single();
   if(result.error){
    const error=normalizeError(result.error);
    if(error.code==='23505'){
     const existing=await fetchEntity(mutation.entity_type,mutation.entity_key);
     if(existing?.last_mutation_id===mutation.mutation_id)return existing;
    }
    throw error;
   }
   if(mutation.entity_type==='asphalt_plan')rememberPlan(result.data);
   return result.data;
  }
  async function fetchEntity(entityType,entityKey){
   const meta=ENTITY[entityType],{client,user}=await context();if(!meta)return null;let key=entityKey;
   if(entityType==='asphalt_progress')key=await resolveAsphaltPlanId(entityKey);
   const result=await client.from(meta.table).select('*').eq(meta.owner,user.id).eq(meta.key,key).maybeSingle();if(result.error)throw normalizeError(result.error);if(entityType==='asphalt_plan')rememberPlan(result.data);if(entityType==='asphalt_progress'&&result.data)result.data.plan_key=planKeyById.get(result.data.plan_id)||String(entityKey);return result.data
  }
  async function pullTable(entityType,cursor,limit=500){
   const meta=ENTITY[entityType],{client,user}=await context();if(!meta)return{rows:[],cursor};let query=client.from(meta.table).select('*').eq(meta.owner,user.id).order('server_updated_at',{ascending:true}).order('id',{ascending:true}).limit(limit);
   if(cursor?.server_updated_at){const timestamp=String(cursor.server_updated_at).replaceAll('"',''),id=String(cursor.id||'00000000-0000-0000-0000-000000000000').replaceAll('"','');query=query.or(`server_updated_at.gt.${timestamp},and(server_updated_at.eq.${timestamp},id.gt.${id})`)}
   const result=await query;if(result.error)throw normalizeError(result.error);const rows=result.data||[];
   if(entityType==='asphalt_plan')rows.forEach(rememberPlan);
   if(entityType==='asphalt_progress'&&rows.length){const unknown=[...new Set(rows.map(row=>row.plan_id).filter(id=>!planKeyById.has(id)))];if(unknown.length){const plans=await client.from('asphalt_plans').select('id,plan_key').eq('owner_user_id',user.id).in('id',unknown);if(plans.error)throw normalizeError(plans.error);plans.data.forEach(rememberPlan)}for(const row of rows){row.plan_key=planKeyById.get(row.plan_id)||null;if(!row.plan_key)throw Object.assign(new Error(`Fant ikke stabil plan_key for plan_id ${row.plan_id}`),{code:'ASPHALT_PLAN_NOT_FOUND'})}}
   const last=rows.at(-1);return{rows,cursor:last?{server_updated_at:last.server_updated_at,id:last.id}:cursor||null};
  }
  async function countUserMigrationData(){
   const{client,user}=await context(),spec=[['road_progress','user_id'],['asphalt_plans','owner_user_id'],['asphalt_progress','user_id'],['measurement_tracks','user_id'],['app_settings','user_id'],['day_plans','user_id']],counts={};
   for(const[table,owner]of spec){const result=await client.from(table).select('id',{count:'exact',head:true}).eq(owner,user.id);if(result.error)throw normalizeError(result.error);counts[table]=result.count||0}
   return counts;
  }
  return{registerDevice,resolveAsphaltPlanId,push,fetchEntity,pullTable,countUserMigrationData};
 }
 return{ENTITY,normalizeError,create};
});
