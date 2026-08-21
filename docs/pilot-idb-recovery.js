(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;root.KjoreloggPilotIDB=api})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const CORE_STORES=['tiles','appdata','progress_snapshots'],SYNC_OUTBOX='sync_outbox',SYNC_META='sync_meta';
 const request=req=>new Promise((resolve,reject)=>{req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error)});
 function error(code,message,details={}){const value=new Error(message);value.code=code;value.details=details;return value}
 function openExisting(idb,name){return new Promise((resolve,reject)=>{const req=idb.open(name);let created=false;req.onupgradeneeded=()=>{created=true;req.transaction.abort()};req.onsuccess=()=>{if(created){req.result.close();reject(error('IDB_NOT_FOUND',`IndexedDB ${name} finnes ikke`))}else resolve(req.result)};req.onerror=()=>reject(error('IDB_OPEN_ERROR',req.error?.message||'Kunne ikke åpne IndexedDB',{name:req.error?.name}))})}
 async function databaseInfo(idb,name){if(typeof idb.databases==='function'){const entry=(await idb.databases()).find(item=>item.name===name);if(!entry)throw error('IDB_NOT_FOUND',`IndexedDB ${name} finnes ikke`);return entry}const db=await openExisting(idb,name);try{return{name,version:db.version}}finally{db.close()}}
 function openForUpgrade(options={}){
  const idb=options.indexedDB||globalThis.indexedDB,name=options.name||'nvdb_tiles',version=options.version||4,timeoutMs=Number(options.timeoutMs)||12000,onEvent=typeof options.onEvent==='function'?options.onEvent:()=>{};
  if(!idb)return Promise.reject(error('IDB_UNAVAILABLE','IndexedDB er ikke tilgjengelig'));
  return new Promise((resolve,reject)=>{
   let settled=false,blocked=false,upgradeStarted=false,req;
   const finish=(fn,value)=>{if(settled)return;settled=true;clearTimeout(timer);fn(value)};
   const timer=setTimeout(()=>finish(reject,error(blocked?'IDB_UPGRADE_BLOCKED':'IDB_OPEN_TIMEOUT',blocked?'Databaseoppgradering blokkert. Lukk alle andre Kjørelogg-faner og prøv igjen.':'Tidsavbrudd ved åpning av Kjørelogg-databasen.',{name,version,timeout_ms:timeoutMs})),timeoutMs);
   try{req=idb.open(name,version)}catch(cause){finish(reject,error('IDB_OPEN_ERROR',cause.message,{name:cause.name}));return}
   req.onblocked=()=>{blocked=true;onEvent({step:'open',status:'BLOCKED',version});finish(reject,error('IDB_UPGRADE_BLOCKED','Databaseoppgradering blokkert. En annen Kjørelogg-fane bruker fortsatt den gamle databasen. Lukk alle andre Kjørelogg-faner og prøv igjen.',{name,version}))};
   req.onupgradeneeded=event=>{
    upgradeStarted=true;const db=req.result,from=event.oldVersion,to=event.newVersion;
    onEvent({step:'upgrade',status:'STARTED',from,to});
    try{
     for(const store of CORE_STORES)if(!db.objectStoreNames.contains(store))throw error('IDB_CORE_STORE_MISSING',`Kan ikke oppgradere: eksisterende store ${store} mangler`,{store,from,to});
     if(!db.objectStoreNames.contains(SYNC_OUTBOX)){const outbox=db.createObjectStore(SYNC_OUTBOX,{keyPath:'id'});outbox.createIndex('entity',['entity_type','entity_key'],{unique:false});outbox.createIndex('state_created',['state','created_at'],{unique:false})}
     if(!db.objectStoreNames.contains(SYNC_META))db.createObjectStore(SYNC_META,{keyPath:'key'});
    }catch(cause){try{req.transaction.abort()}catch(_){};finish(reject,cause.code?cause:error('IDB_UPGRADE_ERROR',cause.message,{name:cause.name}))}
   };
   req.onerror=()=>finish(reject,error('IDB_OPEN_ERROR',req.error?.message||'IndexedDB-open feilet',{name:req.error?.name,upgrade_started:upgradeStarted}));
   req.onsuccess=()=>{const db=req.result;if(settled){db.close();return}db.onversionchange=()=>{onEvent({step:'connection',status:'VERSION_CHANGE_CLOSE',from:db.version});db.close()};onEvent({step:'open',status:'PASS',version:db.version,stores:[...db.objectStoreNames]});finish(resolve,db)};
  })
 }
 async function sha256(bytes){const digest=await globalThis.crypto.subtle.digest('SHA-256',bytes);return[...new Uint8Array(digest)].map(v=>v.toString(16).padStart(2,'0')).join('')}
 function typeSummary(value){if(value===null)return'null';if(Array.isArray(value))return`array(${value.length})`;if(value instanceof Blob)return`Blob(${value.size})`;if(value instanceof ArrayBuffer)return`ArrayBuffer(${value.byteLength})`;if(ArrayBuffer.isView(value))return`${value.constructor.name}(${value.byteLength})`;if(value&&typeof value==='object')return`object(${Object.keys(value).length})`;return typeof value}
 function elementCount(value){if(Array.isArray(value))return value.length;if(value&&typeof value==='object'&&!(value instanceof Blob)&&!(value instanceof ArrayBuffer)&&!ArrayBuffer.isView(value))return Object.keys(value).length;return value==null?0:1}
 async function inspect(db,canonicalBytes){
  const stores=[...db.objectStoreNames],counts={},appdata_keys=[],critical_records={};
  for(const storeName of stores){const tx=db.transaction(storeName,'readonly'),store=tx.objectStore(storeName);counts[storeName]=await request(store.count())}
  if(stores.includes('appdata')){
   const tx=db.transaction('appdata','readonly'),store=tx.objectStore('appdata'),keysRequest=store.getAllKeys(),valuesRequest=store.getAll(),keys=await request(keysRequest),values=await request(valuesRequest);
   for(let index=0;index<keys.length;index++){const key=keys[index],value=values[index],bytes=await canonicalBytes(value),logical=value&&typeof value==='object'&&Object.hasOwn(value,'value')?value.value:value;appdata_keys.push(String(key));critical_records[String(key)]={sha256:await sha256(bytes),bytes:bytes.length,type:typeSummary(logical),elements:elementCount(logical)}}
   appdata_keys.sort();
  }
  return{version:db.version,stores:stores.sort(),counts,appdata_keys,critical_records}
 }
 function compare(before,after){
  const mismatches=[];
  for(const store of['appdata','progress_snapshots'])if(Number(before?.counts?.[store]||0)!==Number(after?.counts?.[store]||0))mismatches.push(`${store} count ${before?.counts?.[store]} != ${after?.counts?.[store]}`);
  if(JSON.stringify(before?.appdata_keys||[])!==JSON.stringify(after?.appdata_keys||[]))mismatches.push('appdata keys changed');
  for(const key of before?.appdata_keys||[])if(before.critical_records?.[key]?.sha256!==after.critical_records?.[key]?.sha256)mismatches.push(`appdata fingerprint changed: ${key}`);
  return{valid:mismatches.length===0,mismatches}
 }
 async function runReadOnlyBoot(steps={}){const state=await steps.hydrate();const validated=await steps.validate(state);await steps.render(validated);return validated}
 return{CORE_STORES,SYNC_OUTBOX,SYNC_META,error,databaseInfo,openExisting,openForUpgrade,inspect,compare,runReadOnlyBoot};
});
