#!/usr/bin/env python3
Bygger v2.0.52-ios fra v2.0.49.1-ios baseline.

Inkluderer ALT:
v2.0.50: Fremdrift-fanen redigeringsliste (under kart, dragbar splitter)
v2.0.51: Meny-rydding (fjerner ubrukte knapper, seksjonsoverskrifter)
v2.0.52: Error-logg + synlig lagrings-status + synkron skriv ved fylke-bytte

NYE FUNKSJONER I v2.0.52:

- IDB error_log store, 500 oppføringer FIFO
- logError(level, source, msg, ctx) wrapper
- Try/catch rundt alle IDB-skriv med error-logging
- Synlig “💾 Sist lagret: HH:MM:SS” i GPS-header
  Rød hvis >2 min siden, gul 30s-2min, grønn <30s
- Synkron flush ved fylke-bytte (forhindrer datatap ved kryssing av fylkesgrenser)
- Ny menyknapp: “📋 Eksporter feillogg” under “Backup og data”
- Strategisk error-logging: IDB-skriv, fylke-bytte, NVDB-lasting, GPS-events

ENDRER IKKE:

- GPS-deteksjons-logikk
- routeLog-format
- Eksisterende IDB-stores

Brukes via GitHub Actions workflow build-v2052.yml.
Genererer ny docs/index.html basert på docs/index.html.v2049_1.bak.
‘’’

import re
import sys
from pathlib import Path

REPO_ROOT = Path(**file**).resolve().parent.parent
DOCS_DIR = REPO_ROOT / ‘docs’
SOURCE_FILE = DOCS_DIR / ‘index.html.v2049_1.bak’
TARGET_FILE = DOCS_DIR / ‘index.html’
BACKUP_FILE = DOCS_DIR / ‘index.html.v2051.bak’

NEW_VERSION = ‘v2.0.52-ios’

def read_source():
if not SOURCE_FILE.exists():
# Fall tilbake til gjeldende index.html hvis baseline ikke finnes
candidates = [
DOCS_DIR / ‘index.html.v2049_1.bak’,
DOCS_DIR / ‘index.html.v2049.bak’,
DOCS_DIR / ‘index.html’,
]
for c in candidates:
if c.exists():
print(f”[INFO] Bruker {c.name} som baseline”)
return c.read_text(encoding=‘utf-8’), c
raise FileNotFoundError(
f”Fant ingen baseline-fil. Sjekket: {[str(c) for c in candidates]}”
)
return SOURCE_FILE.read_text(encoding=‘utf-8’), SOURCE_FILE

def patch_version(html):
‘’‘Bytt APP_VERSION og synlig versjons-tag.’’’
html = re.sub(
r”const APP_VERSION=‘v2.0.\d+(?:.\d+)?-ios’;”,
f”const APP_VERSION=’{NEW_VERSION}’;”,
html, count=1
)
html = re.sub(
r’Vegmåling · v2.0.\d+(?:.\d+)?-ios’,
f’Vegmåling · {NEW_VERSION}’,
html
)
return html

def patch_idb_version(html):
‘’‘Øk IDB_VER fra 3 til 4 for å legge til error_log store.’’’
html = re.sub(
r”const IDB_NAME=‘nvdb_tiles’,IDB_STORE=‘tiles’,IDB_META_STORE=‘appdata’,IDB_PROGRESS_SNAPSHOT_STORE=‘progress_snapshots’,IDB_VER=3;”,
“const IDB_NAME=‘nvdb_tiles’,IDB_STORE=‘tiles’,IDB_META_STORE=‘appdata’,IDB_PROGRESS_SNAPSHOT_STORE=‘progress_snapshots’,IDB_ERROR_LOG_STORE=‘error_log’,IDB_VER=4;”,
html, count=1
)
# Hvis v2.0.49 ikke har snapshot-store-konstanten, fall tilbake til v2 → v4
if “IDB_ERROR_LOG_STORE” not in html:
html = re.sub(
r”const IDB_NAME=‘nvdb_tiles’,IDB_STORE=‘tiles’,IDB_META_STORE=‘appdata’,IDB_VER=\d+;”,
“const IDB_NAME=‘nvdb_tiles’,IDB_STORE=‘tiles’,IDB_META_STORE=‘appdata’,IDB_PROGRESS_SNAPSHOT_STORE=‘progress_snapshots’,IDB_ERROR_LOG_STORE=‘error_log’,IDB_VER=4;”,
html, count=1
)
return html

def patch_open_idb(html):
‘’‘Utvid openIDB() til å opprette error_log store ved upgrade.’’’
old = (
“function openIDB(){if(!HAS_INDEXED_DB)return Promise.reject(new Error(‘IndexedDB er ikke tilgjengelig’));”
“if(_idb)return Promise.resolve(_idb);”
“return new Promise((res,rej)=>{const req=indexedDB.open(IDB_NAME,IDB_VER);”
“req.onupgradeneeded=e=>{const db=e.target.result;”
“if(!db.objectStoreNames.contains(IDB_STORE))db.createObjectStore(IDB_STORE);”
“if(!db.objectStoreNames.contains(IDB_META_STORE))db.createObjectStore(IDB_META_STORE);”
“if(!db.objectStoreNames.contains(IDB_PROGRESS_SNAPSHOT_STORE))db.createObjectStore(IDB_PROGRESS_SNAPSHOT_STORE,{keyPath:‘ts’});”
“};”
“req.onsuccess=e=>{_idb=e.target.result;res(_idb)};”
“req.onerror=()=>rej(req.error)})}”
)
new = (
“function openIDB(){if(!HAS_INDEXED_DB)return Promise.reject(new Error(‘IndexedDB er ikke tilgjengelig’));”
“if(_idb)return Promise.resolve(_idb);”
“return new Promise((res,rej)=>{const req=indexedDB.open(IDB_NAME,IDB_VER);”
“req.onupgradeneeded=e=>{const db=e.target.result;”
“if(!db.objectStoreNames.contains(IDB_STORE))db.createObjectStore(IDB_STORE);”
“if(!db.objectStoreNames.contains(IDB_META_STORE))db.createObjectStore(IDB_META_STORE);”
“if(!db.objectStoreNames.contains(IDB_PROGRESS_SNAPSHOT_STORE))db.createObjectStore(IDB_PROGRESS_SNAPSHOT_STORE,{keyPath:‘ts’});”
“if(!db.objectStoreNames.contains(IDB_ERROR_LOG_STORE))db.createObjectStore(IDB_ERROR_LOG_STORE,{keyPath:‘id’,autoIncrement:true});”
“};”
“req.onsuccess=e=>{_idb=e.target.result;res(_idb)};”
“req.onerror=()=>rej(req.error)})}”
)
if old in html:
html = html.replace(old, new)
else:
# Sjekk for v2.0.49-variant uten progress_snapshots
old2 = (
“function openIDB(){if(!HAS_INDEXED_DB)return Promise.reject(new Error(‘IndexedDB er ikke tilgjengelig’));”
“if(_idb)return Promise.resolve(_idb);”
“return new Promise((res,rej)=>{const req=indexedDB.open(IDB_NAME,IDB_VER);”
“req.onupgradeneeded=e=>{const db=e.target.result;”
“if(!db.objectStoreNames.contains(IDB_STORE))db.createObjectStore(IDB_STORE);”
“if(!db.objectStoreNames.contains(IDB_META_STORE))db.createObjectStore(IDB_META_STORE)};”
“req.onsuccess=e=>{_idb=e.target.result;res(_idb)};”
“req.onerror=()=>rej(req.error)})}”
)
if old2 in html:
html = html.replace(old2, new)
else:
print(”[WARN] openIDB() ble ikke patchet — sjekk source manuelt”)
return html

def inject_error_log_module(html):
‘’‘Sett inn error-log-modul rett etter openIDB().’’’
error_log_module = r’’’
/* ─────────────── v2.0.52: ERROR LOG SYSTEM ─────────────── */
// Error-log lagres i IDB_ERROR_LOG_STORE. Buffer på 500 oppføringer, FIFO-rotasjon.
// Hver oppføring: {id, ts, level, source, message, context}
// Levels: ‘error’, ‘warn’, ‘info’
const ERROR_LOG_KEEP=500;
let _errorLogBuffer=[]; // In-memory buffer som flushes til IDB periodisk
let _errorLogFlushTimer=null;
let _errorLogFlushing=false;

function logError(level,source,message,context){
const entry={ts:Date.now(),level:String(level||‘info’),source:String(source||‘unknown’),message:String(message||’’),context:context==null?null:(()=>{try{return JSON.parse(JSON.stringify(context))}catch(e){return String(context)}})()};
_errorLogBuffer.push(entry);
// Speil til console for utviklerverktøy
const consoleFn=level===‘error’?console.error:(level===‘warn’?console.warn:console.log);
try{consoleFn(`[${source}] ${message}`,context||’’)}catch(e){}
scheduleErrorLogFlush();
}
function scheduleErrorLogFlush(){
if(_errorLogFlushTimer)return;
_errorLogFlushTimer=setTimeout(()=>{_errorLogFlushTimer=null;flushErrorLogToIDB()},2000);
}
async function flushErrorLogToIDB(){
if(_errorLogFlushing||!HAS_INDEXED_DB||!_errorLogBuffer.length)return;
_errorLogFlushing=true;
const toWrite=_errorLogBuffer.splice(0,_errorLogBuffer.length);
try{
const db=await openIDB();
await new Promise((res,rej)=>{
const tx=db.transaction(IDB_ERROR_LOG_STORE,‘readwrite’);
const store=tx.objectStore(IDB_ERROR_LOG_STORE);
for(const entry of toWrite)store.add(entry);
tx.oncomplete=()=>res();
tx.onerror=()=>rej(tx.error);
tx.onabort=()=>rej(tx.error||new Error(‘error-log abort’));
});
// Rotasjon: behold bare siste ERROR_LOG_KEEP oppføringer
await new Promise(res=>{
const tx=db.transaction(IDB_ERROR_LOG_STORE,‘readwrite’);
const store=tx.objectStore(IDB_ERROR_LOG_STORE);
const countReq=store.count();
countReq.onsuccess=()=>{
const total=countReq.result;
if(total<=ERROR_LOG_KEEP){res();return}
const toDelete=total-ERROR_LOG_KEEP;
const cursorReq=store.openCursor();
let deleted=0;
cursorReq.onsuccess=e=>{
const cursor=e.target.result;
if(cursor&&deleted<toDelete){store.delete(cursor.primaryKey);deleted++;cursor.continue()}
else res();
};
cursorReq.onerror=()=>res();
};
countReq.onerror=()=>res();
});
}catch(e){
console.warn(‘Error-log flush feilet’,e);
// Returner oppføringene til bufferet for retry
_errorLogBuffer.unshift(…toWrite);
}finally{_errorLogFlushing=false}
}
async function exportErrorLogTxt(){
try{
await flushErrorLogToIDB();
if(!HAS_INDEXED_DB){setMessage(‘IndexedDB er ikke tilgjengelig.’,‘error’);return}
const db=await openIDB();
const entries=await new Promise((res,rej)=>{
const tx=db.transaction(IDB_ERROR_LOG_STORE,‘readonly’);
const req=tx.objectStore(IDB_ERROR_LOG_STORE).getAll();
req.onsuccess=()=>res(req.result||[]);
req.onerror=()=>rej(req.error);
});
if(!entries.length){setMessage(‘Ingen feilloggoppføringer å eksportere.’,‘notice’);return}
entries.sort((a,b)=>(a.ts||0)-(b.ts||0));
const lines=[`Kjørelogg feillogg ${APP_VERSION}`,`Eksportert: ${new Date().toISOString()}`,`Antall oppføringer: ${entries.length}`,’’];
for(const e of entries){
const ts=new Date(e.ts).toISOString();
const ctx=e.context?’ ‘+JSON.stringify(e.context):’’;
lines.push(`${ts} [${e.level.toUpperCase()}] [${e.source}] ${e.message}${ctx}`);
}
const text=lines.join(’\n’);
const stamp=new Date().toISOString().slice(0,16).replace(/[-:]/g,’’).replace(‘T’,’-’);
const fileName=`kjorelogg-feillogg-${stamp}.txt`;
if(isNativeApp()){
try{const saved=await saveTextNativeIfPossible(text,fileName);setMessage(`Feillogg lagret som ${saved.relPath}. Plassering: ${saved.label}. ${entries.length} oppføringer.`,‘success’);return}
catch(e){logError(‘error’,‘export-log’,‘Native lagring feilet’,{err:String(e)})}
}
const blob=new Blob([text],{type:‘text/plain;charset=utf-8’});
const url=URL.createObjectURL(blob),a=document.createElement(‘a’);
a.href=url;a.download=fileName;document.body.appendChild(a);a.click();a.remove();
setTimeout(()=>URL.revokeObjectURL(url),1000);
setMessage(`Feillogg eksportert: ${entries.length} oppføringer i ${fileName}.`,‘success’);
}catch(e){setMessage(’Eksport av feillogg feilet: ’+(e?.message||e),‘error’);logError(‘error’,‘export-log’,‘Eksport feilet’,{err:String(e)})}
}
async function clearErrorLog(){
if(!confirm(‘Slette hele feilloggen?\n\nDette kan ikke angres.’))return;
try{
_errorLogBuffer=[];
if(HAS_INDEXED_DB){
const db=await openIDB();
await new Promise((res,rej)=>{
const tx=db.transaction(IDB_ERROR_LOG_STORE,‘readwrite’);
const req=tx.objectStore(IDB_ERROR_LOG_STORE).clear();
req.onsuccess=()=>res();
req.onerror=()=>rej(req.error);
});
}
setMessage(‘Feillogg tømt.’,‘success’);
}catch(e){setMessage(’Kunne ikke tømme feillogg: ’+(e?.message||e),‘error’)}
}
// Flush ved app-bytte slik at vi ikke mister oppføringer
window.addEventListener(‘pagehide’,()=>{try{flushErrorLogToIDB()}catch(e){}});

/* ─────────────── v2.0.52: SAVE STATUS TRACKING ─────────────── */
// Holder rede på siste vellykkede IDB-skriv av fremdriftsdata. Vises i GPS-header.
let _lastSaveTs=null;
let _lastSaveError=null;
function markSaveSuccess(source){
_lastSaveTs=Date.now();
_lastSaveError=null;
// Trigger GPS-header re-render hvis GPS er aktiv
if(gps.watching)try{updateSaveStatusBadge()}catch(e){}
}
function markSaveError(source,err){
_lastSaveError={ts:Date.now(),source,msg:String(err?.message||err)};
logError(‘error’,source,‘IDB-skriv feilet’,{err:String(err?.message||err)});
if(gps.watching)try{updateSaveStatusBadge()}catch(e){}
}
function formatSaveStatusText(){
if(!_lastSaveTs)return ‘💾 Ikke lagret enda’;
const ageSec=Math.round((Date.now()-_lastSaveTs)/1000);
const t=new Date(_lastSaveTs);
const hhmmss=`${String(t.getHours()).padStart(2,'0')}:${String(t.getMinutes()).padStart(2,'0')}:${String(t.getSeconds()).padStart(2,'0')}`;
if(ageSec<60)return `💾 ${hhmmss} (${ageSec}s)`;
if(ageSec<3600)return `💾 ${hhmmss} (${Math.floor(ageSec/60)}m)`;
return `💾 ${hhmmss} (>1t)`;
}
function getSaveStatusColor(){
if(_lastSaveError&&Date.now()-_lastSaveError.ts<10000)return ‘#ff4444’;
if(!_lastSaveTs)return ‘#999’;
const ageSec=(Date.now()-_lastSaveTs)/1000;
if(ageSec<30)return ‘#7cb342’;
if(ageSec<120)return ‘#f9a825’;
return ‘#ff4444’;
}
function updateSaveStatusBadge(){
const el=document.getElementById(‘gps-save-status’);
if(!el)return;
el.textContent=formatSaveStatusText();
el.style.color=getSaveStatusColor();
if(_lastSaveError&&Date.now()-_lastSaveError.ts<10000)el.title=’Siste lagrings-feil: ’+_lastSaveError.msg;
else el.title=‘Siste vellykkede lagring av fremdriftsdata’;
}
// Tikk hvert 5. sek for å oppdatere alder-fargen
setInterval(()=>{if(gps.watching)try{updateSaveStatusBadge()}catch(e){}},5000);

‘’’
# Sett inn rett etter openIDB-funksjonen, før tileKey
marker = “function tileKey(lat,lon,r,f){”
if marker in html:
html = html.replace(marker, error_log_module + marker, 1)
else:
print(”[WARN] Fant ikke tileKey-marker for error-log-injeksjon”)
return html

def patch_save_progress_snapshot(html):
‘’‘Wrapp saveProgressSnapshotToIDB med try/catch + markSaveSuccess/Error.’’’
old = (
“async function saveProgressSnapshotToIDB(){\n”
“ if(!HAS_INDEXED_DB)return false;\n”
“ try{await idbSetAppData(PROGRESS_IDB_KEY,progressSnapshot());return true}\n”
“ catch(e){console.warn(‘Kunne ikke lagre samlet fremdrift i IndexedDB’,e);return false}\n”
“}”
)
new = (
“async function saveProgressSnapshotToIDB(){\n”
“ if(!HAS_INDEXED_DB)return false;\n”
“ try{\n”
“  await idbSetAppData(PROGRESS_IDB_KEY,progressSnapshot());\n”
“  markSaveSuccess(‘progress-snapshot’);\n”
“  return true;\n”
“ }catch(e){\n”
“  markSaveError(‘progress-snapshot’,e);\n”
“  return false;\n”
“ }\n”
“}”
)
if old in html:
html = html.replace(old, new)
else:
# v2.0.49-variant kan ha annen formatering
old2 = (
“async function saveProgressSnapshotToIDB(){if(!HAS_INDEXED_DB)return false;”
“try{await idbSetAppData(PROGRESS_IDB_KEY,progressSnapshot());return true}”
“catch(e){console.warn(‘Kunne ikke lagre samlet fremdrift i IndexedDB’,e);return false}}”
)
new2 = (
“async function saveProgressSnapshotToIDB(){if(!HAS_INDEXED_DB)return false;”
“try{await idbSetAppData(PROGRESS_IDB_KEY,progressSnapshot());markSaveSuccess(‘progress-snapshot’);return true}”
“catch(e){markSaveError(‘progress-snapshot’,e);return false}}”
)
if old2 in html:
html = html.replace(old2, new2)
else:
print(”[WARN] saveProgressSnapshotToIDB ble ikke patchet”)
return html

def patch_update_fylke(html):
‘’‘Synkron flush ved fylke-bytte for å unngå datatap ved fylkesgrenser.’’’
old = (
“async function updateFylkeFromPosition(lat,lon){”
“const sel=document.getElementById(‘fylke’);”
“if(lastFylkeCheckPos&&dM(lastFylkeCheckPos[0],lastFylkeCheckPos[1],lat,lon)<10000)return;”
“lastFylkeCheckPos=[lat,lon];”
“const f=await detectFylkeFromAPI(lat,lon);”
“if(!f)return;”
“gps.detectedFylke=f.id;”
“if(sel&&sel.dataset.manual!==‘1’&&sel.value)sel.value=’’;”
“updateHeaderTitle()}”
)
new = (
“async function updateFylkeFromPosition(lat,lon){”
“const sel=document.getElementById(‘fylke’);”
“if(lastFylkeCheckPos&&dM(lastFylkeCheckPos[0],lastFylkeCheckPos[1],lat,lon)<10000)return;”
“lastFylkeCheckPos=[lat,lon];”
“let f;try{f=await detectFylkeFromAPI(lat,lon)}catch(e){logError(‘warn’,‘fylke-detect’,‘Geonorge feilet’,{err:String(e)});return}”
“if(!f)return;”
“const prevFylke=gps.detectedFylke;”
“gps.detectedFylke=f.id;”
“if(sel&&sel.dataset.manual!==‘1’&&sel.value)sel.value=’’;”
“updateHeaderTitle();”
“// v2.0.52: synkron flush ved fylke-bytte. Forhindrer datatap ved kryssing av fylkesgrenser.\n”
“if(prevFylke&&prevFylke!==f.id){”
“logError(‘info’,‘fylke-bytte’,‘Krysset fylkesgrense, tving synkron lagring’,{fra:prevFylke,til:f.id,lat,lon});”
“try{await flushAllPendingWritesNow();await saveProgressSnapshotToIDB()}”
“catch(e){logError(‘error’,‘fylke-bytte’,‘Synkron lagring feilet’,{err:String(e)})}”
“}}”
)
if old in html:
html = html.replace(old, new)
else:
print(”[WARN] updateFylkeFromPosition ble ikke patchet — sjekk syntax”)
return html

def patch_gps_ui_save_status(html):
‘’‘Legg til save-status-badge i GPS-UI.’’’
old = (
“   <span class="gps-heading" id="gps-heading" style="display:none">\n”
“     <span class="compass-arrow" id="gps-arrow">↑</span>\n”
“     <span class="heading-val" id="gps-heading-val"></span>\n”
“     <span class="heading-dir" id="gps-heading-dir"></span>\n”
“    </span>”
)
new = (
“   <span class="gps-heading" id="gps-heading" style="display:none">\n”
“     <span class="compass-arrow" id="gps-arrow">↑</span>\n”
“     <span class="heading-val" id="gps-heading-val"></span>\n”
“     <span class="heading-dir" id="gps-heading-dir"></span>\n”
“    </span>\n”
“    <span class="gps-save-status" id="gps-save-status" style="font-size:10px;font-weight:900;margin-left:6px;font-variant-numeric:tabular-nums"></span>”
)
if old in html:
html = html.replace(old, new)
else:
print(”[WARN] GPS-UI save-status badge ble ikke injisert — sjekk template-string”)
return html

def patch_render_gps_save_status(html):
‘’‘Sørg for at save-status oppdateres ved hver renderGPS().’’’
# Finn slutten av renderGPS-funksjonen og legg til kall
marker = “ if(headWrap){\n  if(on&&Number.isFinite(gps.heading)&&gps.heading!=null){”
if marker in html:
# Etter headWrap-blokken kommer slutten av renderGPS. Legg til updateSaveStatusBadge() der.
# Søk etter avsluttende } av renderGPS
old_end = “  }else{\n   headWrap.style.display=‘none’;\n  }\n }\n}”
new_end = “  }else{\n   headWrap.style.display=‘none’;\n  }\n }\n updateSaveStatusBadge();\n}”
if old_end in html:
# Bare første forekomst etter renderGPS
idx = html.find(“function renderGPS(){”)
if idx >= 0:
tail = html[idx:]
first_match = tail.find(old_end)
if first_match >= 0:
abs_pos = idx + first_match
html = html[:abs_pos] + new_end + html[abs_pos + len(old_end):]
else:
print(”[WARN] renderGPS-slutt ikke funnet for save-status-injeksjon”)
return html

def patch_menu_v2051(html):
‘’‘v2.0.51 meny-rydding: fjern ubrukte knapper og legg til seksjoner.
Også legg til ny “📋 Eksporter feillogg”-knapp i v2.0.52.’’’
old_menu = (
“<div id="top-menu">”
“<button class="menu-item" id="btn-refreshcenter">🔄 Oppdater området</button>”
“<div class="menu-sep"></div>”
“<button class="menu-item" id="btn-export">📤 Eksporter</button> “
“<button class="menu-item" id="btn-exportgpx">🛰 Eksporter GPX-spor</button> “
“<button class="menu-item" id="btn-import">📥 Importer</button>”
“<div class="menu-sep"></div>”
“<button class="menu-item" id="btn-offline">💾 Offline-cache</button> “
“<button class="menu-item" id="btn-offlinemode">✈️ Offline-modus AV</button> “
“<button class="menu-item" id="btn-datasaver">💾 Datasparing PÅ</button> “
“<button class="menu-item" id="btn-backgroundgps">📍 Bakgrunns-GPS PÅ</button> “
“<button class="menu-item" id="btn-sideanlegg">🆿️ Sideanlegg AV</button> “
“<button class="menu-item" id="btn-cleansideanlegg">🧹 Rens sideanlegg fra historikk</button> “
“<button class="menu-item" id="btn-repairgeom">🔧 Reparer geometri</button> “
“<button class="menu-item" id="btn-manualcenter">📍 Sett manuell kartmarkør</button> “
“<button class="menu-item" id="btn-clearmanual">🧹 Fjern manuell markør</button> “
“<button class="menu-item" id="btn-planmode">🗺 Planmodus AV</button> “
“<button class="menu-item" id="btn-clear-plan-menu">🧹 Nullstill dagsrute</button>”
)
# Det nye menyoppsettet bruker seksjonsoverskrifter og fjerner ubrukte knapper.
# Vi beholder de underliggende DOM-id-ene for skjulte knapper slik at JS-event-listenere
# ikke krasjer ved oppstart, men flytter dem til en skjult container.
new_menu = (
“<div id="top-menu">”
# Daglig bruk
“<div class="menu-section-title">Daglig bruk</div>”
“<button class="menu-item" id="btn-refreshcenter">🔄 Oppdater området</button>”
“<button class="menu-item" id="btn-manualcenter">📍 Sett manuell kartmarkør</button>”
“<button class="menu-item" id="btn-clearmanual">🧹 Fjern manuell markør</button>”
“<div class="menu-sep"></div>”
# Backup og data
“<div class="menu-section-title">Backup og data</div>”
“<button class="menu-item" id="btn-export">📤 Eksporter fremdrift</button>”
“<button class="menu-item" id="btn-exportgpx">🛰 Eksporter GPX-spor</button>”
“<button class="menu-item" id="btn-import">📥 Importer</button>”
“<button class="menu-item" id="btn-restoresnap">⏪ Gjenopprett fra snapshot</button>”
“<button class="menu-item" id="btn-export-errorlog">📋 Eksporter feillogg</button>”
“<button class="menu-item" id="btn-clear-errorlog">🧹 Tøm feillogg</button>”
“<div class="menu-sep"></div>”
# Verktøy
“<div class="menu-section-title">Verktøy</div>”
“<button class="menu-item" id="btn-repairdir">🔧 Reparer falske R2-spor</button>”
“<div class="menu-sep"></div>”
# Innstillinger
“<div class="menu-section-title">Innstillinger</div>”
“<button class="menu-item" id="btn-backgroundgps">📍 Bakgrunns-GPS PÅ</button>”
# Skjulte knapper for kompatibilitet med eksisterende event-listenere
“<div style="display:none">”
“<button id="btn-offline"></button>”
“<button id="btn-offlinemode"></button>”
“<button id="btn-datasaver"></button>”
“<button id="btn-sideanlegg"></button>”
“<button id="btn-cleansideanlegg"></button>”
“<button id="btn-repairgeom"></button>”
“<button id="btn-planmode"></button>”
“<button id="btn-clear-plan-menu"></button>”
“</div>”
)
if old_menu in html:
html = html.replace(old_menu, new_menu)
else:
print(”[WARN] Menyen ble ikke funnet eksakt — prøver mer fleksibel match”)
# Fallback: bytt ut hele <div id="top-menu">…</div> blokken, men behold Vegkategorier-delen som kommer etter
m = re.search(
r’<div id="top-menu">.*?(?=<div class="menu-sep"></div><div class="menu-section-title">Vegkategorier</div>)’,
html, re.DOTALL
)
if m:
html = html[:m.start()] + new_menu + ‘<div class="menu-sep"></div>’ + html[m.end():]
else:
print(”[ERROR] Fallback-menyfjerning lyktes heller ikke”)
return html

def patch_event_listeners(html):
‘’‘Legg til event-listenere for nye knapper.’’’
# Finn et trygt sted å legge til, f.eks. etter btn-export-listener
marker = (
“document.getElementById(‘btn-export’).addEventListener(‘click’,async()=>”
“{try{closeMenu();setMessage(‘Eksporterer data …’,‘notice’);”
“const msg=await exportAppData();setMessage(msg||‘Eksport ferdig.’,‘success’)}”
“catch(e){setMessage(’Eksport feilet: ’+e.message,‘error’)}});”
)
addition = (
“\ndocument.getElementById(‘btn-export-errorlog’)?.addEventListener(‘click’,async()=>{closeMenu();setMessage(‘Eksporterer feillogg …’,‘notice’);await exportErrorLogTxt()});”
“\ndocument.getElementById(‘btn-clear-errorlog’)?.addEventListener(‘click’,async()=>{closeMenu();await clearErrorLog()});”
)
if marker in html:
html = html.replace(marker, marker + addition)
else:
print(”[WARN] Fant ikke btn-export-listener for å legge til feillogg-listenere”)
return html

def patch_progress_split_view(html):
‘’‘v2.0.50: Fremdrift-fanen redigeringsliste under kart med dragbar splitter.’’’
# Bytt ut Fremdrift-tab innholdet for å støtte split-view
old_progress_tab = (
“<div class="content" id="tab-progress">”
)
# Vi injiserer ekstra struktur INNI tab-progress, etter eksisterende innhold
# Strategi: Etter “<div id="progress-map-container"></div>” injiser splitter + redigeringsliste

```
# Finn map-container-blokken og legg til splitter/redigeringsliste etter
map_container_marker = (
    "<div id=\"progress-map-container\"></div>"
    "<div class=\"map-tools\"><button class=\"map-tool-btn\" id=\"fit-progress-btn\">🎯 Tilpass kart</button></div>"
)
# NB: progress-map-container-strukturen kan være litt forskjellig. Vi gjør en enkel injisering.

if "progress-edit-list" in html:
    print("[INFO] progress-edit-list finnes allerede, hopper over")
    return html

# Vi setter inn ny seksjon før </div> som lukker tab-progress.
# Enklere: finn slutten av tab-progress-elementet og injiser før det.
# Tab-progress lukkes av </div> rett før <div id="offline-modal".
offline_modal_idx = html.find('<div id="offline-modal"')
if offline_modal_idx < 0:
    print("[WARN] offline-modal ikke funnet — kan ikke injisere progress-edit-list")
    return html

# Finn </div> som lukker tab-progress (siste </div> før offline-modal)
# Trygt: finn siste forekomst av </div></div> før offline-modal og injiser før den siste </div>
# Enklere: legg inn HTML rett før <div id="offline-modal">
edit_list_html = (
    '<div id="progress-edit-section" style="display:none;border-top:2px solid #2a2a31;background:#16161b;flex-shrink:0">'
    '<div id="progress-splitter" style="height:6px;background:#2a3a5a;cursor:ns-resize;display:flex;align-items:center;justify-content:center" title="Dra for å justere størrelse"><div style="width:40px;height:3px;background:#7bc1ff;border-radius:2px"></div></div>'
    '<div id="progress-edit-controls" style="padding:6px 10px;display:flex;gap:6px;flex-wrap:wrap;align-items:center;border-bottom:1px solid rgba(255,255,255,.08)">'
    '<input id="progress-edit-search" placeholder="🔍 Søk veg/segment..." style="flex:1;min-width:120px;padding:8px;border:none;border-radius:10px;font-size:13px;background:#323237;color:#fff">'
    '<select id="progress-edit-sort" style="padding:8px;border:none;border-radius:10px;font-size:13px;background:#323237;color:#fff">'
    '<option value="recent">Sist endret</option>'
    '<option value="veg">Veg A–Å</option>'
    '<option value="km-desc">Lengde (lengst)</option>'
    '<option value="km-asc">Lengde (kortest)</option>'
    '</select>'
    '<button class="pf-btn" id="progress-edit-select-all">☑️ Velg alle</button>'
    '<button class="pf-btn" id="progress-edit-clear-sel">↩ Tøm valg</button>'
    '</div>'
    '<div id="progress-edit-batch-actions" style="padding:6px 10px;display:none;gap:6px;flex-wrap:wrap;border-bottom:1px solid rgba(255,255,255,.08);background:#1a1a2e">'
    '<span id="progress-edit-sel-count" style="font-size:11px;font-weight:900;color:#7bc1ff;align-self:center"></span>'
    '<button class="pf-btn" id="progress-edit-set-done" style="background:#1a3a1a;color:#8fca8f;border-color:#2a5a2a">✅ Ferdig</button>'
    '<button class="pf-btn" id="progress-edit-set-oneway" style="background:#3a3000;color:#f9a825;border-color:#7a6500">🟡 1 retning</button>'
    '<button class="pf-btn" id="progress-edit-set-skip" style="background:#1a1a1a;color:#aaa;border-color:#444">⛔ Kjøres ikke</button>'
    '<button class="pf-btn" id="progress-edit-reset" style="background:#2a1a1a;color:#ffb8b8;border-color:#5a2a2a">↩ Nullstill</button>'
    '<button class="pf-btn" id="progress-edit-delete" style="background:#3a1a1a;color:#ffb8b8;border-color:#5a2a2a">🗑 Slett valgte</button>'
    '</div>'
    '<div id="progress-edit-list" style="overflow-y:auto;padding:4px 8px"></div>'
    '<div id="progress-edit-load-more" style="padding:8px;text-align:center;display:none"><button class="pf-btn" id="progress-edit-show-more">Vis flere…</button></div>'
    '</div>'
)
html = html[:offline_modal_idx] + edit_list_html + html[offline_modal_idx:]

# Legg til JS-modulen for redigeringslisten
progress_edit_js = r'''
```

/* ─────────────── v2.0.50: PROGRESS EDIT LIST ─────────────── */
let _progressEditSelected=new Set();
let _progressEditRenderLimit=200;
let _progressEditVisible=false;

function getProgressEditEntries(){
const search=(document.getElementById(‘progress-edit-search’)?.value||’’).toLowerCase().trim();
const sort=document.getElementById(‘progress-edit-sort’)?.value||‘recent’;
const fylkeId=getProgressFylkeId();
const rangeInfo=getProgressRangeInfo();
const allKeys=new Set([…drivenKeys,…oneWayKeys,…skipKeys]);
const rows=[];
for(const key of allKeys){
if(!keyPassesCategoryFilter(key))continue;
if(!keyPassesProgressFylke(key,fylkeId))continue;
if(!keyHasTimeInRange(key,rangeInfo))continue;
const meta=getReportRoadMeta(key);
const status=drivenKeys.has(key)?‘done’:oneWayKeys.has(key)?‘oneway’:‘skip’;
if(search){const hay=(meta.veg+’ ‘+meta.seg).toLowerCase();if(!hay.includes(search))continue}
const times=getKeyEventTimes(key);
rows.push({key,veg:meta.veg,seg:meta.seg,km:meta.lenKm||0,status,fylke:meta.fylkeName||’–’,lastTs:times[times.length-1]||0,firstTs:times[0]||0});
}
if(sort===‘recent’)rows.sort((a,b)=>(b.lastTs||0)-(a.lastTs||0));
else if(sort===‘veg’)rows.sort((a,b)=>a.veg.localeCompare(b.veg,‘no’));
else if(sort===‘km-desc’)rows.sort((a,b)=>b.km-a.km);
else if(sort===‘km-asc’)rows.sort((a,b)=>a.km-b.km);
return rows;
}
function renderProgressEditList(){
const listEl=document.getElementById(‘progress-edit-list’);
if(!listEl)return;
const allRows=getProgressEditEntries();
const visible=allRows.slice(0,_progressEditRenderLimit);
const loadMore=document.getElementById(‘progress-edit-load-more’);
if(loadMore)loadMore.style.display=allRows.length>visible.length?‘block’:‘none’;
if(!visible.length){listEl.innerHTML=’<div style="padding:12px;text-align:center;color:#888;font-size:12px">Ingen strekninger matcher filteret.</div>’;return}
listEl.innerHTML=visible.map(r=>{
const sel=_progressEditSelected.has(r.key);
const statusIcon=r.status===‘done’?‘🟢’:r.status===‘oneway’?‘🟡’:‘⛔’;
const statusColor=r.status===‘done’?’#8fca8f’:r.status===‘oneway’?’#f9a825’:’#aaa’;
const lastTxt=r.lastTs?formatDateTime(r.lastTs):’–’;
return `<div class="pe-row" data-pekey="${esc(r.key)}" style="display:flex;align-items:center;gap:8px;padding:7px 8px;border-bottom:1px solid rgba(255,255,255,.05);cursor:pointer;${sel?'background:#24364a':''}">
<input type=“checkbox” data-pecb=”${esc(r.key)}” ${sel?‘checked’:’’} style=“flex-shrink:0”>

   <div style="flex:1;min-width:0">
    <div style="font-size:13px;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${statusIcon} ${esc(r.veg)} <span style="color:#b6b6bd;font-weight:400">${esc(r.seg||'')}</span></div>
    <div style="font-size:10px;color:#888;margin-top:2px">${r.km.toFixed(2)} km · ${esc(r.fylke)} · ${lastTxt}</div>
   </div>
   <span style="font-size:11px;font-weight:900;color:${statusColor};flex-shrink:0">${r.status==='done'?'Ferdig':r.status==='oneway'?'1 rtn':'Skip'}</span>
  </div>`;
 }).join('');
 listEl.querySelectorAll('[data-pecb]').forEach(cb=>cb.addEventListener('change',e=>{
  e.stopPropagation();
  const k=cb.getAttribute('data-pecb');
  if(cb.checked)_progressEditSelected.add(k);else _progressEditSelected.delete(k);
  updateProgressEditBatchUI();
  cb.closest('.pe-row').style.background=cb.checked?'#24364a':'';
 }));
 listEl.querySelectorAll('.pe-row').forEach(row=>row.addEventListener('click',e=>{
  if(e.target.closest('input,button'))return;
  const key=row.getAttribute('data-pekey');
  if(_progressEditSelected.has(key))_progressEditSelected.delete(key);else _progressEditSelected.add(key);
  renderProgressEditList();updateProgressEditBatchUI();
  // Highlight på kart
  highlightProgressListKey(key);
 }));
 updateProgressEditBatchUI();
}
function updateProgressEditBatchUI(){
 const ba=document.getElementById('progress-edit-batch-actions');
 const cnt=document.getElementById('progress-edit-sel-count');
 if(!ba)return;
 const n=_progressEditSelected.size;
 ba.style.display=n>0?'flex':'none';
 if(cnt)cnt.textContent=n+' valgt';
}
function highlightProgressListKey(key){
 if(!progressMap)return;
 const r=geomCache[key]||roadByKeyAny(key);
 if(!r)return;
 const parts=getGeomParts(r);
 if(!parts.length)return;
 // Fjern eksisterende highlight
 progressMap.eachLayer(l=>{if(l._isProgressHighlight)progressMap.removeLayer(l)});
 const bounds=[];
 for(const part of parts){
  const lls=part.filter(isVLL).map(c=>[c[1],c[0]]);
  if(lls.length<2)continue;
  const pl=L.polyline(lls,{color:'#00d4ff',weight:10,opacity:0.7}).addTo(progressMap);
  pl._isProgressHighlight=true;
  bounds.push(...lls);
 }
 if(bounds.length)progressMap.fitBounds(L.latLngBounds(bounds),{padding:[40,40],maxZoom:15});
 // Auto-fjern highlight etter 5 sek
 setTimeout(()=>{if(progressMap)progressMap.eachLayer(l=>{if(l._isProgressHighlight)progressMap.removeLayer(l)})},5000);
}
function showProgressEditSection(){
 const sec=document.getElementById('progress-edit-section');
 if(!sec)return;
 _progressEditVisible=true;
 sec.style.display='flex';
 sec.style.flexDirection='column';
 // Default-høyde: 40% av tab-progress-høyde
 const tab=document.getElementById('tab-progress');
 const tabH=tab?tab.clientHeight:600;
 sec.style.height=Math.round(tabH*0.40)+'px';
 renderProgressEditList();
 setupProgressSplitter();
}
function setupProgressSplitter(){
 const splitter=document.getElementById('progress-splitter');
 const sec=document.getElementById('progress-edit-section');
 const tab=document.getElementById('tab-progress');
 if(!splitter||!sec||!tab||splitter._wired)return;
 splitter._wired=true;
 let dragging=false,startY=0,startH=0;
 const onMove=e=>{
  if(!dragging)return;
  const y=(e.touches?e.touches[0].clientY:e.clientY);
  const dy=startY-y; // dra opp = høyere edit-section
  const tabH=tab.clientHeight;
  const newH=Math.max(80,Math.min(tabH-200,startH+dy));
  sec.style.height=newH+'px';
  if(progressMap)setTimeout(()=>safeInvalidate(progressMap),50);
 };
 const onUp=()=>{dragging=false;document.removeEventListener('mousemove',onMove);document.removeEventListener('touchmove',onMove);document.removeEventListener('mouseup',onUp);document.removeEventListener('touchend',onUp)};
 const onDown=e=>{dragging=true;startY=(e.touches?e.touches[0].clientY:e.clientY);startH=sec.clientHeight;document.addEventListener('mousemove',onMove);document.addEventListener('touchmove',onMove,{passive:false});document.addEventListener('mouseup',onUp);document.addEventListener('touchend',onUp)};
 splitter.addEventListener('mousedown',onDown);
 splitter.addEventListener('touchstart',onDown,{passive:false});
}
async function applyProgressEditBatch(action){
 const keys=[..._progressEditSelected];
 if(!keys.length)return;
 if(action==='delete'&&!confirm(`Slette ${keys.length} strekninger fra historikken?\n\nDette kan ikke angres.`))return;
 for(const key of keys){
  if(action==='done')setRoadDoneFull(key);
  else if(action==='oneway'){if(!directionState[key])directionState[key]={fwd:false,rev:false};markDirectionDriven(key,'fwd')}
  else if(action==='skip')setRoadSkipFromTable(key);
  else if(action==='reset')clearRoadProgressForKey(key,{clearSkip:true});
  else if(action==='delete'){clearRoadProgressForKey(key,{clearSkip:true});delete geomCache[key]}
 }
 await flushProgressPersistence();
 saveGeomCache();
 _progressEditSelected.clear();
 renderAllViews();
 renderProgressEditList();
 setMessage(`${keys.length} strekninger oppdatert.`,'success');
}

‘’’
# Sett inn JS-modulen før </script>
script_close = “</script></body></html>”
if script_close in html:
html = html.replace(script_close, progress_edit_js + script_close, 1)
else:
print(”[WARN] Fant ikke </script> for progress-edit-JS-injeksjon”)

```
# Legg til event-listenere — finn et trygt sted (etter progress-show-all-btn)
listener_marker = "document.getElementById('progress-show-all-btn')?.addEventListener('click',setProgressFilterAll);"
listener_addition = (
    "\n// v2.0.50: progress edit list listeners\n"
    "document.getElementById('progress-edit-search')?.addEventListener('input',renderProgressEditList);\n"
    "document.getElementById('progress-edit-sort')?.addEventListener('change',renderProgressEditList);\n"
    "document.getElementById('progress-edit-select-all')?.addEventListener('click',()=>{const rows=getProgressEditEntries().slice(0,_progressEditRenderLimit);rows.forEach(r=>_progressEditSelected.add(r.key));renderProgressEditList()});\n"
    "document.getElementById('progress-edit-clear-sel')?.addEventListener('click',()=>{_progressEditSelected.clear();renderProgressEditList()});\n"
    "document.getElementById('progress-edit-set-done')?.addEventListener('click',()=>applyProgressEditBatch('done'));\n"
    "document.getElementById('progress-edit-set-oneway')?.addEventListener('click',()=>applyProgressEditBatch('oneway'));\n"
    "document.getElementById('progress-edit-set-skip')?.addEventListener('click',()=>applyProgressEditBatch('skip'));\n"
    "document.getElementById('progress-edit-reset')?.addEventListener('click',()=>applyProgressEditBatch('reset'));\n"
    "document.getElementById('progress-edit-delete')?.addEventListener('click',()=>applyProgressEditBatch('delete'));\n"
    "document.getElementById('progress-edit-show-more')?.addEventListener('click',()=>{_progressEditRenderLimit+=200;renderProgressEditList()});\n"
)
if listener_marker in html:
    html = html.replace(listener_marker, listener_marker + listener_addition)
else:
    print("[WARN] Fant ikke progress-show-all-btn-listener-marker")

# Trigger visning av edit-section når man bytter til progress-fanen
show_tab_marker = "if(t==='progress'){"
show_tab_addition_old = (
    "if(t==='progress'){\n  const ok=await ensureLeafletReady();"
)
show_tab_addition_new = (
    "if(t==='progress'){\n  showProgressEditSection();\n  const ok=await ensureLeafletReady();"
)
if show_tab_addition_old in html:
    html = html.replace(show_tab_addition_old, show_tab_addition_new)

return html
```

def patch_restoresnap_button(html):
‘’‘Legg til handler for restoresnap-knapp hvis den ikke finnes.’’’
# I v2.0.49 finnes showSnapshotPicker. Bare wire opp btn-restoresnap til den.
if “btn-restoresnap” in html and “showSnapshotPicker” in html:
marker = “document.getElementById(‘btn-export-errorlog’)?.addEventListener”
addition = (
“document.getElementById(‘btn-restoresnap’)?.addEventListener(‘click’,async()=>{closeMenu();if(typeof showSnapshotPicker===‘function’)await showSnapshotPicker();else setMessage(‘Snapshot-funksjonen er ikke tilgjengelig i denne versjonen.’,‘notice’)});\n”
)
if marker in html:
html = html.replace(marker, addition + marker)
return html

def patch_repairdir_button(html):
‘’‘Legg til handler for repairdir-knapp.’’’
if “btn-repairdir” in html and “repairFalseRevTracks” in html:
marker = “document.getElementById(‘btn-export-errorlog’)?.addEventListener”
addition = (
“document.getElementById(‘btn-repairdir’)?.addEventListener(‘click’,async()=>{closeMenu();if(typeof repairFalseRevTracks===‘function’)await repairFalseRevTracks();else setMessage(‘Reparasjonsfunksjonen er ikke tilgjengelig i denne versjonen.’,‘notice’)});\n”
)
if marker in html:
html = html.replace(marker, addition + marker)
return html

def write_target(html, source_path):
# Lag backup hvis ikke finnes
if not BACKUP_FILE.exists() and TARGET_FILE.exists():
BACKUP_FILE.write_text(TARGET_FILE.read_text(encoding=‘utf-8’), encoding=‘utf-8’)
print(f”[INFO] Backup lagret: {BACKUP_FILE.name}”)
TARGET_FILE.write_text(html, encoding=‘utf-8’)
print(f”[INFO] Skrev {TARGET_FILE.name} ({len(html)} bytes) basert på {source_path.name}”)

def main():
print(f”=== Bygger {NEW_VERSION} ===”)
html, source_path = read_source()
print(f”[INFO] Source: {source_path.name} ({len(html)} bytes)”)

```
html = patch_version(html)
print("[OK] Versjon oppdatert")

html = patch_idb_version(html)
print("[OK] IDB-versjon økt til 4 (error_log store lagt til)")

html = patch_open_idb(html)
print("[OK] openIDB() utvidet med error_log store")

html = inject_error_log_module(html)
print("[OK] Error-log-modul injisert")

html = patch_save_progress_snapshot(html)
print("[OK] saveProgressSnapshotToIDB wrappet med try/catch + markSaveSuccess")

html = patch_update_fylke(html)
print("[OK] updateFylkeFromPosition får synkron flush ved fylke-bytte")

html = patch_gps_ui_save_status(html)
print("[OK] GPS-UI har save-status-badge")

html = patch_render_gps_save_status(html)
print("[OK] renderGPS oppdaterer save-status-badge")

html = patch_menu_v2051(html)
print("[OK] Meny ryddet (v2.0.51) + ny feillogg-knapp")

html = patch_event_listeners(html)
print("[OK] Event-listenere for feillogg lagt til")

html = patch_progress_split_view(html)
print("[OK] Fremdrift-fanen redigeringsliste injisert (v2.0.50)")

html = patch_restoresnap_button(html)
html = patch_repairdir_button(html)
print("[OK] Verktøy-knapper wiret opp")

write_target(html, source_path)
print(f"=== {NEW_VERSION} ferdig ===")
```

if **name** == ‘**main**’:
main()