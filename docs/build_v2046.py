
#!/usr/bin/env python3
“””
Bygg v2.0.46-ios fra v2.0.45-ios.

Bruk:
python3 build_v2046.py path/til/index.html path/til/index_v2046.html

Endringer (alle dokumentert i build_notes.md):

1. APP_VERSION: v2.0.45-ios -> v2.0.46-ios
1. settings.settingsVersion: bump til 7
1. persistJsonStore: IDB-first, localStorage kun for små settings
1. loadProgressSnapshotFromIDB: alltid foretrekk IDB
1. scheduleProgressIDBSave: 250ms -> 50ms debounce
1. markDirectionDriven: synkron skriving hver gang
1. Persistent storage i bootApp
1. autoBackupToFiles + integrasjon
1. Auto-backup retention (siste 48 filer)
   “””
   import sys
   import re
   import os

if len(sys.argv) != 3:
print(**doc**)
sys.exit(1)

INPUT, OUTPUT = sys.argv[1], sys.argv[2]

with open(INPUT, ‘r’, encoding=‘utf-8’) as f:
html = f.read()

original_len = len(html)
print(f”Lest {original_len} tegn fra {INPUT}”)

# ––––– ENDRING 1: APP_VERSION –––––

old = “const APP_VERSION=‘v2.0.45-ios’;”
new = “const APP_VERSION=‘v2.0.46-ios’;”
assert old in html, f”Fant ikke APP_VERSION-konstanten”
html = html.replace(old, new)
print(“✓ APP_VERSION bumpet til v2.0.46-ios”)

# Også i title/header-label hvis de finnes

html = html.replace(“Vegmåling · v2.0.45-ios”, “Vegmåling · v2.0.46-ios”)

# Også i fetch-headers

html = html.replace(“kjorelogg-nvdb-fartsgrense/v2.0.35”, “kjorelogg-nvdb-fartsgrense/v2.0.46”)
html = html.replace(“kjorelogg-nvdb-gps/v2.0.35”, “kjorelogg-nvdb-gps/v2.0.46”)

# ––––– ENDRING 2: persistJsonStore IDB-first –––––

old = “”“function persistJsonStore(key,obj,opt={}){
let json=’’;
try{json=JSON.stringify(obj??{})}catch(e){console.warn(‘Kunne ikke serialisere’,key,e);return false}
const limit=Number(opt.localLimit)||300000;
if(json.length<=limit){
if(!safeLocalSet(key,json))safeLocalRemove(key);
}else{
// Viktig på Safari/iOS: store fremdrifts-/geometridata skal ikke ligge i localStorage når de vokser.
safeLocalRemove(key);
}
if(HAS_INDEXED_DB)idbSetAppData(key,obj).catch(e=>console.warn(‘IndexedDB-lagring feilet for’,key,e));
return true;
}”””

new = “”“function persistJsonStore(key,obj,opt={}){
// v2.0.46: IDB er sannhetskilden for alle store data. localStorage brukes kun for små settings
// (opt.smallSetting=true). Dette eliminerer race condition der iOS jetsam-kill mellom localStorage
// og IDB skriving kunne etterlate localStorage med delvis/foreldet data som overskrev god IDB-data
// ved oppstart. Brukeren mistet 2 uker med Trøndelag-data i v2.0.45 på grunn av dette.
if(HAS_INDEXED_DB){
// Store data: kun IDB. Fjern eventuell gammel localStorage-rest fra tidligere versjon.
if(!opt.smallSetting)safeLocalRemove(key);
idbSetAppData(key,obj).catch(e=>console.warn(‘IndexedDB-lagring feilet for’,key,e));
return true;
}
// Fallback for nettlesere uten IDB: bruk localStorage med stringify
let json=’’;
try{json=JSON.stringify(obj??{})}catch(e){console.warn(‘Kunne ikke serialisere’,key,e);return false}
const limit=Number(opt.localLimit)||300000;
if(json.length<=limit){if(!safeLocalSet(key,json))safeLocalRemove(key)}
else safeLocalRemove(key);
return true;
}”””

assert old in html, “Fant ikke persistJsonStore”
html = html.replace(old, new)
print(“✓ persistJsonStore: IDB-first”)

# ––––– ENDRING 3: loadProgressSnapshotFromIDB - alltid foretrekk IDB –––––

old = “”“async function loadProgressSnapshotFromIDB(){
if(!HAS_INDEXED_DB)return false;
try{
const snap=await idbGetAppData(PROGRESS_IDB_KEY);
if(!snap||typeof snap!==‘object’)return false;
const localTs=Number(localStorage.getItem(PROGRESS_META_STORE)||0);
if(localTs&&Number.isFinite(snap.ts)&&snap.ts<localTs)return false;”””

new = “”“async function loadProgressSnapshotFromIDB(){
if(!HAS_INDEXED_DB)return false;
try{
const snap=await idbGetAppData(PROGRESS_IDB_KEY);
if(!snap||typeof snap!==‘object’)return false;
// v2.0.46: IDB er alltid foretrukket kilde. Tidligere sammenlignet vi med localStorage-timestamp,
// men det åpnet for at en korrupt/delvis localStorage kunne overstyre god IDB-data ved oppstart.
// Nå leser vi alltid IDB-snapshotet hvis det finnes.”””

assert old in html, “Fant ikke loadProgressSnapshotFromIDB”
html = html.replace(old, new)
print(“✓ loadProgressSnapshotFromIDB: alltid IDB-prefer”)

# ––––– ENDRING 4: scheduleProgressIDBSave debounce 250 -> 50 ms –––––

old = “”“function scheduleProgressIDBSave(){
if(!HAS_INDEXED_DB)return;
clearTimeout(_progressSaveTimer);
_progressSaveTimer=setTimeout(()=>saveProgressSnapshotToIDB(),250);
}”””

new = “”“function scheduleProgressIDBSave(){
if(!HAS_INDEXED_DB)return;
clearTimeout(_progressSaveTimer);
// v2.0.46: redusert fra 250ms til 50ms. Med IDB som sannhetskilde må vi flushe raskt slik at
// krasj/jetsam-kill ikke etterlater nylig endret status uskrevet.
_progressSaveTimer=setTimeout(()=>saveProgressSnapshotToIDB(),50);
}”””

assert old in html, “Fant ikke scheduleProgressIDBSave”
html = html.replace(old, new)
print(“✓ scheduleProgressIDBSave: 50ms debounce”)

# ––––– ENDRING 5: markDirectionDriven - skriv synkront alltid –––––

old = “”“function markDirectionDriven(key,dir){
if(!key||(dir!==‘fwd’&&dir!==‘rev’))return false;
if(!directionState[key])directionState[key]={fwd:false,rev:false};
const now=Date.now(),st=directionState[key],wasNew=!st[dir];
st[dir]=true;st[dir+‘LastTs’]=now;
if(!st[dir+‘FirstTs’])st[dir+‘FirstTs’]=now;
// v2.0.30: hot path - debounce skriving. Skriv umiddelbart kun første gang en retning logges,
// slik at fwd/rev-status er sikret hvis appen krasjer rett etter første treff. Ellers utsett.
if(wasNew){saveDirectionState();rebuildStatusSetsFromDirections();saveState()}
else{markDirectionDirty();rebuildStatusSetsFromDirections()}
return true;
}”””

new = “”“function markDirectionDriven(key,dir){
if(!key||(dir!==‘fwd’&&dir!==‘rev’))return false;
if(!directionState[key])directionState[key]={fwd:false,rev:false};
const now=Date.now(),st=directionState[key],wasNew=!st[dir];
st[dir]=true;st[dir+‘LastTs’]=now;
if(!st[dir+‘FirstTs’])st[dir+‘FirstTs’]=now;
// v2.0.46: alltid synkron skriving. directionState er kjernen av det brukeren har målt og må
// overleve enhver krasj/jetsam-kill. routeLog kan fortsatt debouncest fordi punktene gjenskapes
// fra GPS-strømmen, men retningsstatus mistes for godt hvis den ikke skrives.
saveDirectionState();
rebuildStatusSetsFromDirections();
saveState();
if(wasNew)triggerDirectionAutoBackup();
return true;
}”””

assert old in html, “Fant ikke markDirectionDriven”
html = html.replace(old, new)
print(“✓ markDirectionDriven: synkron skriving alltid”)

# ––––– ENDRING 6: legg til auto-backup-funksjoner –––––

# Sett dem inn rett før “/* ───────────────────── IMPORT / EXPORT ───────────────────── */”

backup_funcs = “””
/* ───────────────────── v2.0.46: AUTO-BACKUP TIL FILER ───────────────────── */
// Skriver snapshot til Documents/Kjorelogg/auto/snapshot-YYYYMMDD-HHMM.json
// Sortbart filnavn. Behold de siste 48 filene (≈48 timer ved hver-time-backup).
// Brukeren kan importere en hvilken som helst snapshot via standard import-flow.
const AUTO_BACKUP_DIR=‘Kjorelogg/auto’;
const AUTO_BACKUP_KEEP=48;
const AUTO_BACKUP_MIN_INTERVAL_MS=15*60*1000; // minimum 15 min mellom auto-backups
let _lastAutoBackupTs=0;
let _directionBackupTimer=null;

function makeAutoBackupName(){
const d=new Date(),pad=n=>String(n).padStart(2,‘0’);
return `snapshot-${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}.json`;
}

async function autoBackupToFiles(reason=‘periodic’,force=false){
if(!isNativeApp())return false;
const fs=getCapFilesystem();
if(!fs?.writeFile)return false;
const now=Date.now();
if(!force&&(now-_lastAutoBackupTs)<AUTO_BACKUP_MIN_INTERVAL_MS)return false;
try{
// Sørg for at både hovedmappen og auto-undermappen finnes
if(fs.mkdir){
await fs.mkdir({path:‘Kjorelogg’,directory:‘DOCUMENTS’,recursive:true}).catch(()=>{});
await fs.mkdir({path:AUTO_BACKUP_DIR,directory:‘DOCUMENTS’,recursive:true}).catch(()=>{});
}
// Flush ventende skrivinger først, så snapshotet er ferskt
flushRouteWritesNow();
const snap=progressSnapshot();
snap.autoBackupReason=reason;
snap.autoBackupVersion=APP_VERSION;
const json=JSON.stringify(snap);
const name=makeAutoBackupName();
const path=`${AUTO_BACKUP_DIR}/${name}`;
await fs.writeFile({path,directory:‘DOCUMENTS’,data:json,encoding:‘utf8’,recursive:true});
_lastAutoBackupTs=now;
// Rydd gamle filer i bakgrunn — ikke await, vi vil ikke blokkere GPS-callbacken
pruneAutoBackups().catch(e=>console.warn(‘Auto-backup pruning feilet’,e));
return true;
}catch(e){
console.warn(‘Auto-backup feilet (’+reason+’):’,e);
return false;
}
}

async function pruneAutoBackups(){
const fs=getCapFilesystem();
if(!fs?.readdir)return;
try{
const list=await fs.readdir({path:AUTO_BACKUP_DIR,directory:‘DOCUMENTS’});
const files=(list?.files||list?.entries||[])
.filter(f=>{const name=f.name||f;return typeof name===‘string’&&name.startsWith(‘snapshot-’)&&name.endsWith(’.json’)})
.map(f=>f.name||f)
.sort(); // alfabetisk = kronologisk pga ISO-aktig timestamp
if(files.length<=AUTO_BACKUP_KEEP)return;
const toDelete=files.slice(0,files.length-AUTO_BACKUP_KEEP);
for(const name of toDelete){
try{await fs.deleteFile({path:`${AUTO_BACKUP_DIR}/${name}`,directory:‘DOCUMENTS’})}
catch(e){console.warn(‘Kunne ikke slette gammel backup’,name,e)}
}
}catch(e){
// readdir kan kaste hvis mappen ikke finnes ennå — det er greit
if(!String(e?.message||e).toLowerCase().includes(‘does not exist’))console.warn(‘pruneAutoBackups feilet’,e);
}
}

// Trigges fra markDirectionDriven (når en NY retning logges) og holder backups oppdatert
// uten å spamme filsystemet. Debounced til min. 15 min via _lastAutoBackupTs.
function triggerDirectionAutoBackup(){
if(_directionBackupTimer)return;
_directionBackupTimer=setTimeout(()=>{
_directionBackupTimer=null;
autoBackupToFiles(‘direction-change’).catch(e=>console.warn(‘Direction-backup feilet’,e));
},5000);
}

// Periodisk backup hver time mens GPS er aktiv
let _periodicBackupTimer=null;
function startPeriodicAutoBackup(){
if(_periodicBackupTimer)return;
_periodicBackupTimer=setInterval(()=>{
if(gps.watching)autoBackupToFiles(‘hourly’).catch(e=>console.warn(‘Hourly-backup feilet’,e));
},60*60*1000);
}
function stopPeriodicAutoBackup(){
if(_periodicBackupTimer){clearInterval(_periodicBackupTimer);_periodicBackupTimer=null}
}

“””

old_marker = “/* ───────────────────── IMPORT / EXPORT ───────────────────── */”
assert old_marker in html, “Fant ikke IMPORT/EXPORT-markør”
html = html.replace(old_marker, backup_funcs + old_marker, 1)
print(“✓ Auto-backup-funksjoner lagt til”)

# ––––– ENDRING 7: Trigge backup fra startGPS, stopGPS, visibilitychange –––––

# I startGPS: legg til startPeriodicAutoBackup() og en initial backup

old = “”” ensureWakeLock();
startGpsHealthWatchdog();”””
new = “”” ensureWakeLock();
startGpsHealthWatchdog();
// v2.0.46: start auto-backup med en gang GPS er aktiv, og lag en startup-snapshot
startPeriodicAutoBackup();
autoBackupToFiles(‘gps-start’,true).catch(e=>console.warn(‘Startup-backup feilet’,e));”””
assert old in html, “Fant ikke startGPS-anchor for backup”
html = html.replace(old, new)
print(“✓ startGPS: auto-backup aktivert”)

# I stopGPS: gjør en final backup og stopp periodisk

old = “”” stopGpsHealthWatchdog();
releaseWakeLock();
flushRouteWritesNow();
renderGPS();renderAllViews()”””
new = “”” stopGpsHealthWatchdog();
releaseWakeLock();
flushRouteWritesNow();
// v2.0.46: tving en backup ved hver GPS-stopp. Dette er det viktigste sikkerhetsnettet
// mot iOS jetsam-kill — hvis appen drepes etter at brukeren stopper en målerunde,
// har vi en fersk snapshot på disk uansett.
stopPeriodicAutoBackup();
autoBackupToFiles(‘gps-stop’,true).catch(e=>console.warn(‘Stop-backup feilet’,e));
renderGPS();renderAllViews()”””
assert old in html, “Fant ikke stopGPS-anchor for backup”
html = html.replace(old, new)
print(“✓ stopGPS: final backup”)

# I visibilitychange→hidden: legg til backup

old = “”” if(document.hidden){
if(gps.watching&&isNativeApp()&&!settings.backgroundGps){
stopGPS();
setMessage(‘GPS stoppet automatisk fordi appen gikk i bakgrunnen. Slå på Bakgrunns-GPS i menyen for å unngå dette.’,‘notice’);
}
return;
}”””
new = “”” if(document.hidden){
// v2.0.46: tving auto-backup når appen går i bakgrunn. Dette fanger samtaler, app-bytter,
// og skjermlås — alle situasjoner der iOS kan velge å drepe WebView-en før vi får skrevet ferdig.
if(gps.watching){autoBackupToFiles(‘app-hidden’,true).catch(e=>{})}
if(gps.watching&&isNativeApp()&&!settings.backgroundGps){
stopGPS();
setMessage(‘GPS stoppet automatisk fordi appen gikk i bakgrunnen. Slå på Bakgrunns-GPS i menyen for å unngå dette.’,‘notice’);
}
return;
}”””
assert old in html, “Fant ikke visibilitychange-anchor”
html = html.replace(old, new)
print(“✓ visibilitychange: backup ved bakgrunn”)

# ––––– ENDRING 8: Persistent storage i bootApp –––––

old = “”“async function bootApp(){
loadSettings();
await loadPersistentAppState();
loadPlanKeys();
loadSelectedTableKeys();
repairGeomCacheFromRoads();
applySettingsToUI();updateProgressReportUi();renderGPS();showSecureWarning();renderStats();renderRoads();renderTable();updateOfflineCacheInfo();
}”””

new = “”“async function bootApp(){
loadSettings();
// v2.0.46: be iOS/nettleser om persistent storage. Dette reduserer (men eliminerer ikke)
// risikoen for at lagringen vår evictes ved minnepress. Capacitor-apper får dette typisk
// automatisk, men kall det eksplisitt for å være sikker — og logg resultatet.
if(navigator.storage?.persist){
navigator.storage.persist().then(granted=>{
console.info(‘Persistent storage:’,granted?‘GRANTED’:‘DENIED’);
}).catch(e=>console.warn(‘persist() feilet’,e));
}
await loadPersistentAppState();
loadPlanKeys();
loadSelectedTableKeys();
repairGeomCacheFromRoads();
applySettingsToUI();updateProgressReportUi();renderGPS();showSecureWarning();renderStats();renderRoads();renderTable();updateOfflineCacheInfo();
// v2.0.46: meld i konsoll at auto-backup er klart hvis vi er i native app
if(isNativeApp()){
console.info(‘Auto-backup klar: ‘+AUTO_BACKUP_DIR+’ (behold siste ‘+AUTO_BACKUP_KEEP+’ filer)’);
}
}”””

assert old in html, “Fant ikke bootApp”
html = html.replace(old, new)
print(“✓ bootApp: persistent storage + auto-backup info”)

# ––––– ENDRING 9: settings versjon-bump til 7 –––––

# Legg til en migrering som rydder bort store localStorage-nøkler ved oppstart fra v2.0.45

# (de skal nå kun ligge i IDB)

old = “””   // v2.0.32: ny default — sideanlegg filtreres bort. Eksisterende brukere får filteret slått PÅ
// (dvs. settings.includeSideanlegg=false), men bevarer historikken sin. Bruk “Rens sideanlegg”
// i menyen for å fjerne registrerte sideanlegg fra fremdrift.
if(!settings.settingsVersion||settings.settingsVersion<6){
if(typeof settings.includeSideanlegg!==‘boolean’)settings.includeSideanlegg=false;
settings.settingsVersion=6;
saveSettings();
}”””

new = “””   // v2.0.32: ny default — sideanlegg filtreres bort. Eksisterende brukere får filteret slått PÅ
// (dvs. settings.includeSideanlegg=false), men bevarer historikken sin. Bruk “Rens sideanlegg”
// i menyen for å fjerne registrerte sideanlegg fra fremdrift.
if(!settings.settingsVersion||settings.settingsVersion<6){
if(typeof settings.includeSideanlegg!==‘boolean’)settings.includeSideanlegg=false;
settings.settingsVersion=6;
saveSettings();
}
// v2.0.46: migrer bort store localStorage-nøkler. IDB er nå sannhetskilden, og store
// nøkler i localStorage kan være delvis/foreldet etter et iOS jetsam-kill. Vi trygger
// ved oppstart ved å tømme dem — IDB-snapshotet leses uansett først av bootApp.
if(!settings.settingsVersion||settings.settingsVersion<7){
[STORE,GEOM_STORE,LEGACY_GEOM,DIR_STORE,ROUTE_STORE,PLAN_STORE,PROGRESS_META_STORE].forEach(safeLocalRemove);
settings.settingsVersion=7;
saveSettings();
console.info(‘v2.0.46: store data flyttet helt til IndexedDB’);
}”””

assert old in html, “Fant ikke settings-migrasjons-anchor”
html = html.replace(old, new)
print(“✓ Settings v7 migrering: rydd opp i localStorage”)

# ––––– VALIDER OUTPUT –––––

final_len = len(html)
diff_pct = abs(final_len - original_len) / original_len * 100
print(f”\nOriginalt: {original_len} tegn”)
print(f”Ny:        {final_len} tegn”)
print(f”Differanse: +{final_len-original_len} tegn ({diff_pct:.1f}%)”)

# Sanity: HTML-en må fortsatt åpne med <!DOCTYPE og slutte med </html>

assert html.startswith(’<!DOCTYPE html>’), “HTML startet ikke med doctype”
assert html.rstrip().endswith(’</html>’), “HTML slutter ikke med </html>”
assert ‘v2.0.45-ios’ not in html, “Restspor av v2.0.45 i output”
assert ‘v2.0.46-ios’ in html, “v2.0.46 ikke til stede”

with open(OUTPUT, ‘w’, encoding=‘utf-8’) as f:
f.write(html)

print(f”\n✅ Skrevet til {OUTPUT}”)
print(f”   Versjon: v2.0.46-ios”)
print(f”   Endringer: 9 (alle dokumentert i kommentarer)”)
