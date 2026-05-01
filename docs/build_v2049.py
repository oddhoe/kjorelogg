#!/usr/bin/env python3
"""Bygg v2.0.49-ios fra v2.0.48-ios."""
import sys

if len(sys.argv) != 3:
    print(__doc__); sys.exit(1)

INPUT, OUTPUT = sys.argv[1], sys.argv[2]
with open(INPUT, 'r', encoding='utf-8') as f:
    html = f.read()
original_len = len(html)
print(f"Lest {original_len} tegn")

# 1. APP_VERSION
old = "const APP_VERSION='v2.0.48-ios';"
assert old in html
html = html.replace(old, "const APP_VERSION='v2.0.49-ios';")
html = html.replace("Vegmåling · v2.0.48-ios", "Vegmåling · v2.0.49-ios")
html = html.replace("kjorelogg-nvdb-fartsgrense/v2.0.48", "kjorelogg-nvdb-fartsgrense/v2.0.49")
html = html.replace("kjorelogg-nvdb-gps/v2.0.48", "kjorelogg-nvdb-gps/v2.0.49")
print("OK 1: APP_VERSION")

# 2. repair-funksjon header (tids-interleaving)
old_repair = """function intervalOverlapM(a,b){return Math.max(0,Math.min(a.end,b.end)-Math.max(a.start,b.start))}
function totalOverlap(intervalsA,intervalsB){
 let total=0;
 for(const a of intervalsA){for(const b of intervalsB){total+=intervalOverlapM(a,b)}}
 return total;
}
// v2.0.48: utvidet retningskorrigering. Fanger BAADE keys med rev-routeLog (overlap-test)
// OG keys med directionState.rev=true uten routeLog (60s tidsterskel).
function repairFalseRevTracks(){"""

new_repair = """// v2.0.49: KORREKT retningskorrigering. Tids-interleaving istedenfor geometri-overlap.
// Respekterer manualFull (brukeren har eksplisitt "Sett ferdig").
function nearestTimeBetweenSets(timesA,timesB){
 if(!timesA.length||!timesB.length)return Infinity;
 const a=[...timesA].sort((x,y)=>x-y),b=[...timesB].sort((x,y)=>x-y);
 let i=0,j=0,best=Infinity;
 while(i<a.length&&j<b.length){
  const diff=Math.abs(a[i]-b[j]);
  if(diff<best)best=diff;
  if(a[i]<b[j])i++;else j++;
 }
 return best;
}
function repairFalseRevTracks(){"""
assert old_repair in html, "Fant ikke v2.0.48 repair start"
html = html.replace(old_repair, new_repair)
print("OK 2: repair header")

# 3. Erstatt repair-funksjon body
old_body = """ const allRevKeys=new Set();
 for(const k of Object.keys(directionState||{})){
  if(directionState[k]?.rev)allRevKeys.add(k);
 }
 for(const k of Object.keys(routeLog||{})){
  if(Array.isArray(routeLog[k]?.rev)&&routeLog[k].rev.length>0)allRevKeys.add(k);
 }
 if(!allRevKeys.size){
  setMessage('Ingen rev-status funnet i historikken.','notice');
  return;
 }
 let cleanedOverlap=0,cleanedNoData=0,keptOverlap=0,keptNoData=0,keptTime=0,inspected=0;
 const TIME_THRESHOLD_MS=60000;
 for(const key of allRevKeys){
  inspected++;
  const log=routeLog[key]||{};
  const hasRevPoints=Array.isArray(log.rev)&&log.rev.length>0;
  const hasFwdPoints=Array.isArray(log.fwd)&&log.fwd.length>0;
  const ds=directionState[key]||{};
  if(hasRevPoints&&hasFwdPoints){
   const r=getRoadObjectForDisplay(key)||roadByKeyAny(key);
   if(!r||!r.parts){keptOverlap++;continue}
   const chains=makeChainsFromParts(r.parts,35);
   if(!chains.length){keptOverlap++;continue}
   let totalRevLen=0,overlapLen=0;
   for(const chain of chains){
    const measures=chainMeasures(chain);
    const fwdInts=buildIntervalsFromTrackPoints(log.fwd||[],chain,measures);
    const revInts=buildIntervalsFromTrackPoints(log.rev||[],chain,measures);
    if(!revInts.length)continue;
    totalRevLen+=intervalsKm(revInts)*1000;
    overlapLen+=totalOverlap(fwdInts,revInts);
   }
   if(totalRevLen<10){keptOverlap++;continue}
   const overlapRatio=overlapLen/totalRevLen;
   if(overlapRatio>=0.9){
    delete routeLog[key].rev;
    if(directionState[key]){
     directionState[key].rev=false;
     delete directionState[key].revFirstTs;
     delete directionState[key].revLastTs;
    }
    cleanedOverlap++;
   }else{
    keptOverlap++;
   }
  }else if(!hasRevPoints&&ds.rev){
   const firstTs=ds.revFirstTs,lastTs=ds.revLastTs;
   if(Number.isFinite(firstTs)&&Number.isFinite(lastTs)){
    const span=Math.abs(lastTs-firstTs);
    if(span<TIME_THRESHOLD_MS){
     directionState[key].rev=false;
     delete directionState[key].revFirstTs;
     delete directionState[key].revLastTs;
     cleanedNoData++;
    }else{
     keptTime++;
    }
   }else{
    keptNoData++;
   }
  }else{
   keptNoData++;
  }
 }
 const totalCleaned=cleanedOverlap+cleanedNoData;
 const totalKept=keptOverlap+keptNoData+keptTime;
 if(totalCleaned>0){
  saveRouteLog();
  saveDirectionState();
  rebuildStatusSetsFromDirections();
  saveState();
  renderAllViews();
  const parts=[];
  parts.push(`${totalCleaned} renset`);
  if(cleanedOverlap)parts.push(`${cleanedOverlap} med >=90% overlapp`);
  if(cleanedNoData)parts.push(`${cleanedNoData} uten GPS-data <60s`);
  parts.push(`${totalKept} beholdt`);
  if(keptOverlap)parts.push(`${keptOverlap} ekte motsatt-kjoring`);
  if(keptTime)parts.push(`${keptTime} >=60s rev uten GPS-data`);
  if(keptNoData)parts.push(`${keptNoData} uten tidsstempler`);
  setMessage(`Retningskorrigering ferdig (${inspected} sjekket): ${parts.join(', ')}.`,'success');
 }else{
  setMessage(`Sjekket ${inspected} strekninger med rev-status. Ingen falske rev-spor funnet (${keptOverlap} ekte motsatt-kjoring, ${keptTime} >=60s uten GPS-data, ${keptNoData} uten tidsstempler).`,'notice');
 }
}"""

new_body = """ const allRevKeys=new Set();
 for(const k of Object.keys(directionState||{})){
  if(directionState[k]?.rev)allRevKeys.add(k);
 }
 for(const k of Object.keys(routeLog||{})){
  if(Array.isArray(routeLog[k]?.rev)&&routeLog[k].rev.length>0)allRevKeys.add(k);
 }
 if(!allRevKeys.size){
  setMessage('Ingen rev-status funnet i historikken.','notice');
  return;
 }
 let cleanedInterleaved=0,cleanedShortNoData=0,keptManualFull=0,keptSeparate=0,keptOnlyRev=0,keptLongNoData=0,keptUnknownTs=0,inspected=0;
 const INTERLEAVE_MS=5*60*1000;
 const SHORT_NODATA_MS=60*1000;
 for(const key of allRevKeys){
  inspected++;
  const log=routeLog[key]||{};
  const hasRevPoints=Array.isArray(log.rev)&&log.rev.length>0;
  const hasFwdPoints=Array.isArray(log.fwd)&&log.fwd.length>0;
  const ds=directionState[key]||{};
  if(ds.manualFull){keptManualFull++;continue}
  if(hasRevPoints&&hasFwdPoints){
   const fwdTs=(log.fwd||[]).map(p=>p.ts).filter(Number.isFinite);
   const revTs=(log.rev||[]).map(p=>p.ts).filter(Number.isFinite);
   if(!fwdTs.length||!revTs.length){keptSeparate++;continue}
   const minGap=nearestTimeBetweenSets(fwdTs,revTs);
   if(minGap<INTERLEAVE_MS){
    delete routeLog[key].rev;
    if(directionState[key]){
     directionState[key].rev=false;
     delete directionState[key].revFirstTs;
     delete directionState[key].revLastTs;
    }
    cleanedInterleaved++;
   }else{keptSeparate++}
  }else if(hasRevPoints&&!hasFwdPoints){keptOnlyRev++}
  else if(!hasRevPoints&&ds.rev){
   const firstTs=ds.revFirstTs,lastTs=ds.revLastTs;
   if(Number.isFinite(firstTs)&&Number.isFinite(lastTs)){
    const span=Math.abs(lastTs-firstTs);
    if(span<SHORT_NODATA_MS){
     directionState[key].rev=false;
     delete directionState[key].revFirstTs;
     delete directionState[key].revLastTs;
     cleanedShortNoData++;
    }else{keptLongNoData++}
   }else{keptUnknownTs++}
  }else{keptUnknownTs++}
 }
 const totalCleaned=cleanedInterleaved+cleanedShortNoData;
 const totalKept=keptManualFull+keptSeparate+keptOnlyRev+keptLongNoData+keptUnknownTs;
 if(totalCleaned>0){
  saveRouteLog();saveDirectionState();rebuildStatusSetsFromDirections();saveState();renderAllViews();
  const parts=[];
  parts.push(`${totalCleaned} renset`);
  if(cleanedInterleaved)parts.push(`${cleanedInterleaved} interleaved <5min`);
  if(cleanedShortNoData)parts.push(`${cleanedShortNoData} uten GPS-data <60s`);
  parts.push(`${totalKept} beholdt`);
  if(keptManualFull)parts.push(`${keptManualFull} manuelt ferdig`);
  if(keptSeparate)parts.push(`${keptSeparate} ekte motsatt-kjoring`);
  if(keptOnlyRev)parts.push(`${keptOnlyRev} kun rev`);
  if(keptLongNoData)parts.push(`${keptLongNoData} >=60s uten data`);
  if(keptUnknownTs)parts.push(`${keptUnknownTs} uten tidsstempler`);
  setMessage(`Retningskorrigering ferdig (${inspected} sjekket): ${parts.join(', ')}.`,'success');
 }else{
  const parts=[];
  if(keptManualFull)parts.push(`${keptManualFull} manuelt ferdig`);
  if(keptSeparate)parts.push(`${keptSeparate} ekte motsatt-kjoring`);
  if(keptOnlyRev)parts.push(`${keptOnlyRev} kun rev`);
  if(keptLongNoData)parts.push(`${keptLongNoData} >=60s uten data`);
  if(keptUnknownTs)parts.push(`${keptUnknownTs} uten tidsstempler`);
  setMessage(`Sjekket ${inspected} strekninger. Ingen falske rev-spor (${parts.join(', ')||'alt ok'}).`,'notice');
 }
}"""
assert old_body in html, "Fant ikke v2.0.48 repair body"
html = html.replace(old_body, new_body)
print("OK 3: repair body")

# 4. Confirm-dialog
old_confirm = "if(!confirm('Korriger retning?\\n\\nFjerner falske rev-merker fra tidligere bug:\\n- Rev-spor med >=90% overlapp med fwd (samme strekning)\\n- Rev-flagg uten GPS-data der flagget var aktivt <60 sek\\n\\nReelle motsatt-kjoringer beholdes. Auto-backup tas av appen automatisk - kan rulles tilbake hvis noe gar galt.'))return;"
new_confirm = "if(!confirm('Korriger retning?\\n\\nFjerner falske rev-merker:\\n- Rev-spor logget innen 5 min av fwd (samme tur)\\n- Rev-flagg uten GPS-data <60 sek\\n\\nManuelt ferdig og ekte motsatt-kjoringer (separate turer) beholdes.\\n\\nIDB-snapshot tas automatisk for sikkerhet.'))return;"
assert old_confirm in html
html = html.replace(old_confirm, new_confirm)
print("OK 4: confirm")

# 5. Fylke: bruk fylkesnummer direkte
old_detect = """async function detectFylkeFromAPI(lat,lon){try{const resp=await fetch(`https://ws.geonorge.no/kommuneinfo/v1/punkt?nord=${lat}&ost=${lon}&koordsys=4326`,{headers:{Accept:'application/json'}});if(!resp.ok)return null;const d=await resp.json(),knr=d?.kommunenummer||d?.kommuneinfo?.kommunenummer;if(!knr)return null;const fid=String(knr).substring(0,2);return FYLKER.find(f=>f.id===fid)||null}catch(e){return null}}"""
new_detect = """async function detectFylkeFromAPI(lat,lon){try{const resp=await fetch(`https://ws.geonorge.no/kommuneinfo/v1/punkt?nord=${lat}&ost=${lon}&koordsys=4326`,{headers:{Accept:'application/json'}});if(!resp.ok)return null;const d=await resp.json();
 // v2.0.49: bruk fylkesnummer direkte fra Geonorge. Avledning fra kommunenummer.substring(0,2)
 // feilet i Heim/Halsa-omraadet der gamle MR-kommuner (1571) ble Troendelag-kommuner (5055).
 const fid=String(d?.fylkesnummer||d?.kommuneinfo?.fylkesnummer||d?.fylke?.fylkesnummer||String(d?.kommunenummer||d?.kommuneinfo?.kommunenummer||'').substring(0,2));
 if(!fid)return null;
 return FYLKER.find(f=>f.id===fid)||null;
}catch(e){return null}}"""
assert old_detect in html
html = html.replace(old_detect, new_detect)
html = html.replace("async function classifyFylkeIdFromPartsAPI(parts,maxSamples=5){",
                    "async function classifyFylkeIdFromPartsAPI(parts,maxSamples=12){\n // v2.0.49: 12 sample-punkter")
html = html.replace("classifyFylkeIdFromPartsAPI(getGeomParts(g),5)", "classifyFylkeIdFromPartsAPI(getGeomParts(g),12)")
print("OK 5: fylke")

# 6. IDB v3 + ny store
old_idb = "const IDB_NAME='nvdb_tiles',IDB_STORE='tiles',IDB_META_STORE='appdata',IDB_VER=2;let _idb=null;"
new_idb = "const IDB_NAME='nvdb_tiles',IDB_STORE='tiles',IDB_META_STORE='appdata',IDB_SNAPSHOT_STORE='progress_snapshots',IDB_VER=3;let _idb=null;"
assert old_idb in html
html = html.replace(old_idb, new_idb)
old_open = """req.onupgradeneeded=e=>{const db=e.target.result;if(!db.objectStoreNames.contains(IDB_STORE))db.createObjectStore(IDB_STORE);if(!db.objectStoreNames.contains(IDB_META_STORE))db.createObjectStore(IDB_META_STORE)};"""
new_open = """req.onupgradeneeded=e=>{const db=e.target.result;if(!db.objectStoreNames.contains(IDB_STORE))db.createObjectStore(IDB_STORE);if(!db.objectStoreNames.contains(IDB_META_STORE))db.createObjectStore(IDB_META_STORE);if(!db.objectStoreNames.contains(IDB_SNAPSHOT_STORE))db.createObjectStore(IDB_SNAPSHOT_STORE)};"""
assert old_open in html
html = html.replace(old_open, new_open)
print("OK 6: IDB v3")

# 7. Snapshot-funksjoner + eksport-paaminnelse (legges foer IMPORT/EXPORT-markor)
snapshot_code = """
/* ---------------- v2.0.49: IDB-SNAPSHOT-ROTASJON ---------------- */
const IDB_SNAPSHOT_KEEP=48;
const IDB_SNAPSHOT_MIN_INTERVAL_MS=15*60*1000;
let _lastIdbSnapshotTs=0;
let _idbSnapshotDirectionTimer=null;
let _idbSnapshotPeriodicTimer=null;
function makeIdbSnapshotKey(){
 const d=new Date(),pad=n=>String(n).padStart(2,'0');
 return `snap-${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}
async function saveIdbSnapshot(reason='periodic',force=false){
 if(!HAS_INDEXED_DB)return false;
 const now=Date.now();
 if(!force&&(now-_lastIdbSnapshotTs)<IDB_SNAPSHOT_MIN_INTERVAL_MS)return false;
 try{
  flushRouteWritesNow();
  const snap=progressSnapshot();
  snap.snapshotReason=reason;
  snap.snapshotVersion=APP_VERSION;
  const db=await openIDB();
  await new Promise((res,rej)=>{
   const tx=db.transaction(IDB_SNAPSHOT_STORE,'readwrite');
   const req=tx.objectStore(IDB_SNAPSHOT_STORE).put(snap,makeIdbSnapshotKey());
   req.onsuccess=()=>res(true);req.onerror=()=>rej(req.error);
  });
  _lastIdbSnapshotTs=now;
  pruneIdbSnapshots().catch(()=>{});
  return true;
 }catch(e){console.warn('IDB snapshot feilet ('+reason+'):',e);return false}
}
async function pruneIdbSnapshots(){
 if(!HAS_INDEXED_DB)return;
 try{
  const db=await openIDB();
  const keys=await new Promise(res=>{
   const req=db.transaction(IDB_SNAPSHOT_STORE,'readonly').objectStore(IDB_SNAPSHOT_STORE).getAllKeys();
   req.onsuccess=()=>res(req.result||[]);req.onerror=()=>res([]);
  });
  if(keys.length<=IDB_SNAPSHOT_KEEP)return;
  const sorted=keys.map(k=>String(k)).sort();
  const toDelete=sorted.slice(0,sorted.length-IDB_SNAPSHOT_KEEP);
  await new Promise((res,rej)=>{
   const tx=db.transaction(IDB_SNAPSHOT_STORE,'readwrite'),store=tx.objectStore(IDB_SNAPSHOT_STORE);
   for(const k of toDelete)store.delete(k);
   tx.oncomplete=()=>res(true);tx.onerror=()=>rej(tx.error);
  });
 }catch(e){console.warn('pruneIdbSnapshots feilet',e)}
}
async function listIdbSnapshots(){
 if(!HAS_INDEXED_DB)return [];
 try{
  const db=await openIDB();
  return await new Promise(res=>{
   const tx=db.transaction(IDB_SNAPSHOT_STORE,'readonly'),store=tx.objectStore(IDB_SNAPSHOT_STORE);
   const kr=store.getAllKeys(),vr=store.getAll();
   let keys=null,vals=null;
   const done=()=>{if(keys&&vals){const items=keys.map((k,i)=>({key:String(k),ts:vals[i]?.ts||0,reason:vals[i]?.snapshotReason||'',version:vals[i]?.snapshotVersion||''})).sort((a,b)=>String(b.key).localeCompare(String(a.key)));res(items)}};
   kr.onsuccess=()=>{keys=kr.result||[];done()};kr.onerror=()=>res([]);
   vr.onsuccess=()=>{vals=vr.result||[];done()};vr.onerror=()=>res([]);
  });
 }catch(e){return []}
}
async function loadIdbSnapshot(key){
 if(!HAS_INDEXED_DB)return null;
 try{
  const db=await openIDB();
  return await new Promise(res=>{
   const req=db.transaction(IDB_SNAPSHOT_STORE,'readonly').objectStore(IDB_SNAPSHOT_STORE).get(key);
   req.onsuccess=()=>res(req.result||null);req.onerror=()=>res(null);
  });
 }catch(e){return null}
}
async function restoreFromIdbSnapshot(key){
 const snap=await loadIdbSnapshot(key);
 if(!snap){setMessage('Snapshot ikke funnet: '+key,'error');return false}
 await saveIdbSnapshot('pre-restore',true);
 if(snap.state){applyStatusStateObject(snap.state)}
 if(snap.directionState&&typeof snap.directionState==='object')directionState=snap.directionState;
 if(snap.routeLog&&typeof snap.routeLog==='object')routeLog=snap.routeLog;
 if(snap.geomCache&&typeof snap.geomCache==='object')geomCache=normalizeLegacyGeomCache(snap.geomCache);
 rebuildStatusSetsFromDirections();
 saveState();saveDirectionState();saveRouteLog();saveGeomCache();
 await flushProgressPersistence();
 renderAllViews();
 const dt=new Date(snap.ts).toLocaleString('nb-NO');
 setMessage(`Gjenopprettet snapshot fra ${dt} (${snap.snapshotReason||'-'}). Sikkerhetskopi av forrige tilstand er tatt.`,'success');
 return true;
}
async function showSnapshotPicker(){
 const items=await listIdbSnapshots();
 if(!items.length){setMessage('Ingen IDB-snapshots enda. Lages ved GPS-start/stopp og hver time mens GPS gar.','notice');return}
 const lines=items.slice(0,20).map((it,idx)=>{
  const dt=new Date(it.ts).toLocaleString('nb-NO',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
  return `${idx+1}. ${dt} (${it.reason||'-'})`;
 }).join('\\n');
 const choice=prompt(`Velg snapshot (1-${Math.min(items.length,20)}):\\n\\n${lines}\\n\\nTom = avbryt.`);
 if(!choice)return;
 const idx=parseInt(choice,10)-1;
 if(!Number.isFinite(idx)||idx<0||idx>=items.length){setMessage('Ugyldig valg.','error');return}
 if(!confirm(`Gjenopprette snapshot fra ${new Date(items[idx].ts).toLocaleString('nb-NO')}?`))return;
 await restoreFromIdbSnapshot(items[idx].key);
}
function startIdbSnapshotPeriodic(){
 if(_idbSnapshotPeriodicTimer)return;
 _idbSnapshotPeriodicTimer=setInterval(()=>{if(gps.watching)saveIdbSnapshot('hourly').catch(()=>{})},60*60*1000);
}
function stopIdbSnapshotPeriodic(){if(_idbSnapshotPeriodicTimer){clearInterval(_idbSnapshotPeriodicTimer);_idbSnapshotPeriodicTimer=null}}
function triggerIdbSnapshotForDirection(){
 if(_idbSnapshotDirectionTimer)return;
 _idbSnapshotDirectionTimer=setTimeout(()=>{_idbSnapshotDirectionTimer=null;saveIdbSnapshot('direction-change').catch(()=>{})},5000);
}

/* ---------------- v2.0.49: EKSPORT-PAAMINNELSE ---------------- */
const EXPORT_REMINDER_MS=7*24*60*60*1000;
function checkExportReminder(){
 const last=Number(settings.lastManualExportTs||0);
 if(!last)return;
 const since=Date.now()-last;
 if(since>=EXPORT_REMINDER_MS){
  const days=Math.floor(since/(24*60*60*1000));
  setMessage(`Husk eksport! Siste manuelle eksport for ${days} dager siden. Apne meny -> Eksporter for ekstern backup.`,'notice');
 }
}
function noteManualExportDone(){settings.lastManualExportTs=Date.now();saveSettings();}

"""
old_marker = "/* \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 IMPORT / EXPORT \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 */"
assert old_marker in html, "Fant ikke IMPORT/EXPORT-markor"
html = html.replace(old_marker, snapshot_code + old_marker, 1)
print("OK 7: snapshot-funksjoner")

# 8. Hook IDB-snapshot inn i GPS-events
old = """ // v2.0.46: start auto-backup med en gang GPS er aktiv, og lag en startup-snapshot
 startPeriodicAutoBackup();
 autoBackupToFiles('gps-start',true).catch(e=>console.warn('Startup-backup feilet',e));"""
new = """ // v2.0.46: start auto-backup
 startPeriodicAutoBackup();
 autoBackupToFiles('gps-start',true).catch(e=>console.warn('Startup-backup feilet',e));
 // v2.0.49: IDB-snapshot
 startIdbSnapshotPeriodic();
 saveIdbSnapshot('gps-start',true).catch(()=>{});"""
assert old in html
html = html.replace(old, new)

old = """ // v2.0.46: tving en backup ved hver GPS-stopp.
 stopPeriodicAutoBackup();
 autoBackupToFiles('gps-stop',true).catch(e=>console.warn('Stop-backup feilet',e));
 renderGPS();renderAllViews()"""
new = """ // v2.0.46: tving en backup ved hver GPS-stopp.
 stopPeriodicAutoBackup();
 autoBackupToFiles('gps-stop',true).catch(e=>console.warn('Stop-backup feilet',e));
 // v2.0.49: IDB-snapshot + eksport-paaminnelse
 stopIdbSnapshotPeriodic();
 saveIdbSnapshot('gps-stop',true).catch(()=>{});
 setTimeout(()=>checkExportReminder(),1500);
 renderGPS();renderAllViews()"""
assert old in html
html = html.replace(old, new)

# visibilitychange (norsk versjon)
old = """  // v2.0.46: tving auto-backup når appen går i bakgrunn (samtaler, app-bytte, skjermlås).
  if(gps.watching){autoBackupToFiles('app-hidden',true).catch(e=>{})}"""
new = """  // v2.0.46: tving auto-backup når appen går i bakgrunn.
  if(gps.watching){autoBackupToFiles('app-hidden',true).catch(e=>{});saveIdbSnapshot('app-hidden',true).catch(e=>{})}"""
assert old in html, "Fant ikke visibilitychange-anchor"
html = html.replace(old, new)

# triggerDirectionAutoBackup
old = """function triggerDirectionAutoBackup(){
 if(_directionBackupTimer)return;
 _directionBackupTimer=setTimeout(()=>{
  _directionBackupTimer=null;
  autoBackupToFiles('direction-change').catch(e=>console.warn('Direction-backup feilet',e));
 },5000);
}"""
new = """function triggerDirectionAutoBackup(){
 if(_directionBackupTimer)return;
 _directionBackupTimer=setTimeout(()=>{
  _directionBackupTimer=null;
  autoBackupToFiles('direction-change').catch(e=>console.warn('Direction-backup feilet',e));
 },5000);
 triggerIdbSnapshotForDirection();
}"""
assert old in html
html = html.replace(old, new)
print("OK 8: GPS-event hooks")

# 9. btn-export oppdatert + ny meny-knapp + handler + bootApp-hook
old = """document.getElementById('btn-export').addEventListener('click',async()=>{try{closeMenu();setMessage('Eksporterer data \u2026','notice');const msg=await exportAppData();setMessage(msg||'Eksport ferdig.','success')}catch(e){setMessage('Eksport feilet: '+e.message,'error')}});"""
new = """document.getElementById('btn-export').addEventListener('click',async()=>{try{closeMenu();setMessage('Eksporterer data \u2026','notice');const msg=await exportAppData();noteManualExportDone();setMessage(msg||'Eksport ferdig.','success')}catch(e){setMessage('Eksport feilet: '+e.message,'error')}});"""
assert old in html
html = html.replace(old, new)

old = '<button class="menu-item" id="btn-export">\U0001f4e4 Eksporter</button>'
new = '<button class="menu-item" id="btn-export">\U0001f4e4 Eksporter</button> <button class="menu-item" id="btn-restoresnap">\u23ea Gjenopprett fra snapshot</button>'
assert old in html
html = html.replace(old, new)

old = "document.getElementById('btn-import').addEventListener('click',()=>{closeMenu();document.getElementById('import-file').click()});"
new = "document.getElementById('btn-import').addEventListener('click',()=>{closeMenu();document.getElementById('import-file').click()});\ndocument.getElementById('btn-restoresnap')?.addEventListener('click',()=>{closeMenu();showSnapshotPicker().catch(e=>setMessage('Snapshot-feil: '+(e?.message||e),'error'))});"
assert old in html
html = html.replace(old, new)

old = """ if(isNativeApp()){
  console.info('Auto-backup klar: '+AUTO_BACKUP_DIR+' (behold siste '+AUTO_BACKUP_KEEP+' filer)');
 }
}"""
new = """ if(isNativeApp()){
  console.info('Auto-backup klar: '+AUTO_BACKUP_DIR+' (behold siste '+AUTO_BACKUP_KEEP+' filer)');
 }
 setTimeout(()=>checkExportReminder(),3000);
}"""
assert old in html
html = html.replace(old, new)
print("OK 9: meny + bootApp")

# Validate
final_len = len(html)
print(f"\nDifferanse: +{final_len-original_len} tegn")
assert html.startswith('<!DOCTYPE html>')
assert html.rstrip().endswith('</html>')
assert 'v2.0.48-ios' not in html
assert 'v2.0.49-ios' in html
assert 'IDB_SNAPSHOT_STORE' in html
assert 'showSnapshotPicker' in html
assert 'manualFull' in html
assert 'nearestTimeBetweenSets' in html

with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"OK Skrevet til {OUTPUT}")
