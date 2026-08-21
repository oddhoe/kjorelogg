(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;root.KjoreloggSyncLocal=api})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const DB_NAME='nvdb_tiles',DB_VERSION=4,OUTBOX='sync_outbox',META='sync_meta',SCHEMA_VERSION=1;
 function uuid(){return globalThis.crypto?.randomUUID?.()||'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,c=>{const r=Math.random()*16|0,v=c==='x'?r:r&3|8;return v.toString(16)})}
 function stable(value){if(Array.isArray(value))return value.map(stable);if(value&&typeof value==='object'){const out={};for(const key of Object.keys(value).sort())out[key]=stable(value[key]);return out}return value}
 function stableJson(value){return JSON.stringify(stable(value))}
 function request(req){return new Promise((resolve,reject)=>{req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error)})}
 function transactionDone(tx){return new Promise((resolve,reject)=>{tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error||new Error('IndexedDB transaction aborted'))})}
 function create(options={}){
  const idb=options.indexedDB||globalThis.indexedDB,name=options.dbName||DB_NAME,version=options.version||DB_VERSION;let dbPromise=null;
  function open(){
   if(!idb)return Promise.reject(new Error('IndexedDB is unavailable'));
   if(dbPromise)return dbPromise;
   dbPromise=new Promise((resolve,reject)=>{
    const req=idb.open(name,version);
    req.onupgradeneeded=()=>{
     const db=req.result;
     if(!db.objectStoreNames.contains('tiles'))db.createObjectStore('tiles');
     if(!db.objectStoreNames.contains('appdata'))db.createObjectStore('appdata');
     if(!db.objectStoreNames.contains('progress_snapshots'))db.createObjectStore('progress_snapshots');
     if(!db.objectStoreNames.contains(OUTBOX)){
      const store=db.createObjectStore(OUTBOX,{keyPath:'id'});
      store.createIndex('entity',['entity_type','entity_key'],{unique:false});
      store.createIndex('state_created',['state','created_at'],{unique:false});
     }
     if(!db.objectStoreNames.contains(META))db.createObjectStore(META,{keyPath:'key'});
    };
    req.onsuccess=()=>{const db=req.result;db.onversionchange=()=>{db.close();dbPromise=null};resolve(db)};
    req.onerror=()=>{dbPromise=null;reject(req.error)};
    req.onblocked=()=>reject(new Error('IndexedDB upgrade blocked; close other Kjørelogg tabs'));
   });
   return dbPromise;
  }
  async function enqueue(input){
   if(!input?.entity_type||!input?.entity_key||!input?.payload)throw new Error('Invalid outbox mutation');
   const db=await open(),tx=db.transaction(OUTBOX,'readwrite'),done=transactionDone(tx),store=tx.objectStore(OUTBOX),index=store.index('entity');
   const matches=await request(index.getAll([String(input.entity_type),String(input.entity_key)]));
   const reusable=matches.find(row=>row.state==='pending'||row.state==='retry');
   const payload=stable(input.payload),payloadHash=stableJson(payload);
   if(reusable&&reusable.payload_hash===payloadHash&&reusable.operation===(input.operation||'upsert')){await done;return{record:reusable,created:false,deduplicated:true}}
   const now=new Date().toISOString(),record=reusable?{...reusable}:{id:uuid(),created_at:now,attempts:0};
   Object.assign(record,{entity_type:String(input.entity_type),entity_key:String(input.entity_key),operation:input.operation||'upsert',payload,base_revision:Number(input.base_revision)||0,mutation_id:uuid(),payload_hash:payloadHash,state:'pending',last_attempt_at:null,last_error:null,conflict:null,updated_at:now,next_attempt_at:null});
   store.put(record);await done;return{record,created:!reusable,deduplicated:false};
  }
  async function listPending(limit=100){const db=await open(),rows=await request(db.transaction(OUTBOX,'readonly').objectStore(OUTBOX).getAll());return rows.filter(row=>['pending','retry'].includes(row.state)&&(!row.next_attempt_at||Date.parse(row.next_attempt_at)<=Date.now())).sort((a,b)=>a.created_at.localeCompare(b.created_at)).slice(0,limit)}
  async function listAll(){const db=await open();return request(db.transaction(OUTBOX,'readonly').objectStore(OUTBOX).getAll())}
  async function get(id){const db=await open();return request(db.transaction(OUTBOX,'readonly').objectStore(OUTBOX).get(id))}
  async function remove(id){const db=await open(),tx=db.transaction(OUTBOX,'readwrite');tx.objectStore(OUTBOX).delete(id);await transactionDone(tx)}
  async function update(id,patch){const db=await open(),tx=db.transaction(OUTBOX,'readwrite'),done=transactionDone(tx),store=tx.objectStore(OUTBOX),row=await request(store.get(id));if(!row){await done;return null}const next={...row,...patch,updated_at:new Date().toISOString()};store.put(next);await done;return next}
  async function findPending(entityType,entityKey){const db=await open(),rows=await request(db.transaction(OUTBOX,'readonly').objectStore(OUTBOX).index('entity').getAll([entityType,entityKey]));return rows.find(row=>row.state!=='done')||null}
  async function countPending(){const rows=await listAll();return rows.filter(row=>row.state!=='done').length}
  async function getMeta(key){const db=await open(),row=await request(db.transaction(META,'readonly').objectStore(META).get(String(key)));return row?.value??null}
  async function setMeta(key,value){const db=await open(),tx=db.transaction(META,'readwrite');tx.objectStore(META).put({key:String(key),value,updated_at:new Date().toISOString()});await transactionDone(tx);return value}
  async function getDeviceId(){let value=await getMeta('device_id');if(!value){value=uuid();await setMeta('device_id',value)}return value}
  async function initialize(){await open();await setMeta('schema_version',SCHEMA_VERSION);const device_id=await getDeviceId();return{device_id,schema_version:SCHEMA_VERSION}}
  return{open,initialize,enqueue,listPending,listAll,get,remove,update,findPending,countPending,getMeta,setMeta,getDeviceId};
 }
 return{DB_NAME,DB_VERSION,OUTBOX,META,SCHEMA_VERSION,stableJson,create};
});
