#!/usr/bin/env python3
"""Bygg v2.0.50-ios fra v2.0.49.1-ios. Liste under kart paa Fremdrift."""
import sys
if len(sys.argv) != 3:
    print(__doc__); sys.exit(1)
INPUT, OUTPUT = sys.argv[1], sys.argv[2]
with open(INPUT, 'r', encoding='utf-8') as f:
    html = f.read()
original_len = len(html)
print(f"Lest {original_len} tegn")

# 1. APP_VERSION
old = "const APP_VERSION='v2.0.49.1-ios';"
assert old in html
html = html.replace(old, "const APP_VERSION='v2.0.50-ios';")
html = html.replace("Vegmåling · v2.0.49.1-ios", "Vegmåling · v2.0.50-ios")
html = html.replace("kjorelogg-nvdb-fartsgrense/v2.0.49.1", "kjorelogg-nvdb-fartsgrense/v2.0.50")
html = html.replace("kjorelogg-nvdb-gps/v2.0.49.1", "kjorelogg-nvdb-gps/v2.0.50")
print("OK 1: APP_VERSION")

# 2. CSS for liste
new_css = """
/* v2.0.50: Fremdrift-redigeringsliste */
#progress-splitter{height:14px;background:#1a1a1f;cursor:row-resize;display:flex;align-items:center;justify-content:center;flex-shrink:0;border-top:1px solid rgba(255,255,255,.1);border-bottom:1px solid rgba(255,255,255,.1);touch-action:none;user-select:none;-webkit-user-select:none}
#progress-splitter::before{content:'';width:36px;height:4px;background:#555;border-radius:2px}
#progress-splitter.dragging::before{background:#1e88ff}
#progress-edit-section{display:flex;flex-direction:column;background:#16161b;flex-shrink:0;overflow:hidden;min-height:80px}
#progress-edit-toolbar{padding:6px 8px;display:flex;gap:6px;flex-wrap:wrap;align-items:center;background:#1a1a1f;border-bottom:1px solid rgba(255,255,255,.06);flex-shrink:0}
#progress-edit-search{flex:1;min-width:120px;padding:8px 10px;border:none;border-radius:10px;background:#323237;color:#fff;font-size:13px}
#progress-edit-sort{padding:8px 10px;border:none;border-radius:10px;background:#323237;color:#fff;font-size:12px;font-weight:800}
#progress-batch-toolbar{padding:6px 8px;display:flex;gap:6px;flex-wrap:wrap;background:#1a1a1f;border-bottom:1px solid rgba(255,255,255,.06);flex-shrink:0}
.pe-btn{border:none;border-radius:10px;padding:8px 11px;font-size:12px;font-weight:900;cursor:pointer;white-space:nowrap}
.pe-btn-done{background:#1a3a1a;color:#8fca8f;border:1px solid #2a5a2a}
.pe-btn-one{background:#3a3000;color:#f9a825;border:1px solid #7a6500}
.pe-btn-skip{background:#3a1a00;color:#ffaa55;border:1px solid #aa5500}
.pe-btn-null{background:#1a1a1a;color:#aaa;border:1px solid #444}
.pe-btn-del{background:#3a1a1a;color:#ffb8b8;border:1px solid #7a2a2a}
.pe-btn-sel{background:#1a1a2e;color:#dfe9ff;border:1px solid #2a3a5a}
.pe-btn:disabled{opacity:.4;cursor:not-allowed}
#progress-edit-list{flex:1;overflow-y:auto;background:#0e0e12;-webkit-overflow-scrolling:touch}
.pe-row{display:flex;align-items:center;gap:8px;padding:9px 10px;border-bottom:1px solid rgba(255,255,255,.05);font-size:12px;cursor:pointer}
.pe-row:hover{background:#1a1a22}
.pe-row.selected{background:#243348}
.pe-row.highlight{background:#3a3a00;animation:pehlt 2s ease-out forwards}
@keyframes pehlt{0%{background:#5a5a00}100%{background:transparent}}
.pe-cb{width:18px;height:18px;flex-shrink:0;accent-color:#1e88ff}
.pe-veg{font-weight:900;font-size:12px;color:#fff;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pe-seg{color:#9aa3b8;font-weight:600;margin-left:4px}
.pe-meta{font-size:10px;color:#7a8294;display:flex;gap:8px;flex-shrink:0}
.pe-status{font-size:13px;flex-shrink:0;width:18px;text-align:center}
.pe-empty{padding:24px 16px;text-align:center;color:#7a8294;font-size:13px}
#progress-edit-summary{padding:6px 10px;background:#1a1a1f;color:#9aa3b8;font-size:11px;font-weight:700;border-bottom:1px solid rgba(255,255,255,.06);display:flex;justify-content:space-between;align-items:center;flex-shrink:0}
#progress-edit-more{padding:10px;background:#1a1a1f;color:#7bc1ff;text-align:center;font-size:12px;font-weight:900;cursor:pointer;border-top:1px solid rgba(255,255,255,.06)}
#progress-edit-more:hover{background:#23232a}
</style>"""
old = "</style>"
idx = html.find(old)
assert idx != -1
html = html[:idx] + new_css + html[idx+len(old):]
print("OK 2: CSS")

# 3. HTML i Fremdrift
old = """<div id="progress-map-container"></div><div class="map-tools"><button class="map-tool-btn" id="fit-progress-btn">🎯 Tilpass kart</button></div></div>"""
new = """<div id="progress-map-container"></div><div class="map-tools"><button class="map-tool-btn" id="fit-progress-btn">🎯 Tilpass kart</button></div><div id="progress-splitter" title="Dra for å justere kart/liste"></div><div id="progress-edit-section"><div id="progress-edit-toolbar"><input id="progress-edit-search" placeholder="🔍 Søk veg/segment..."> <select id="progress-edit-sort"><option value="recent">Sist endret</option><option value="veg-asc">Veg A-Å</option><option value="veg-desc">Veg Å-A</option><option value="len-desc">Lengde lengst</option><option value="len-asc">Lengde kortest</option></select></div><div id="progress-batch-toolbar"><button class="pe-btn pe-btn-sel" id="pe-select-all">☑️ Alle synlige</button> <button class="pe-btn pe-btn-sel" id="pe-clear-sel">↩ Tøm valg</button> <button class="pe-btn pe-btn-done" id="pe-set-done">✅ Ferdig</button> <button class="pe-btn pe-btn-one" id="pe-set-one">🟡 1 rtn</button> <button class="pe-btn pe-btn-skip" id="pe-set-skip">⛔ Kjøres ikke</button> <button class="pe-btn pe-btn-null" id="pe-set-null">↩ Nullstill</button> <button class="pe-btn pe-btn-del" id="pe-set-del">🗑 Slett valgte</button></div><div id="progress-edit-summary"><span id="pe-summary-text">0 valgt · 0 synlige</span></div><div id="progress-edit-list"></div><div id="progress-edit-more" style="display:none">Vis flere ⌄</div></div></div>"""
assert old in html
html = html.replace(old, new)
print("OK 3: HTML")

# 4. State-variabler
old = "let map=null,carMarker=null,carTailLayer=null,roadLayers=[],progressMap=null;"
new = """let map=null,carMarker=null,carTailLayer=null,roadLayers=[],progressMap=null;
let selectedProgressKeys=new Set();
let progressListRenderLimit=200;
let progressListFilter='';
let progressListSort='recent';
let progressEditPolylineMap=new Map();"""
assert old in html
html = html.replace(old, new)
print("OK 4: State")

# 5. Settings-lasting
old = """if(typeof d?.planMode==='boolean')settings.planMode=d.planMode;"""
new = """if(typeof d?.planMode==='boolean')settings.planMode=d.planMode;
   if(Number.isFinite(d?.progressSplitRatio))settings.progressSplitRatio=Math.max(0.15,Math.min(0.85,d.progressSplitRatio));"""
assert old in html
html = html.replace(old, new)
print("OK 5: progressSplitRatio")

# 6. Redigeringsliste-funksjoner
edit_funcs = """
/* ---------------- v2.0.50: FREMDRIFT REDIGERINGSLISTE ---------------- */
function getProgressListKeys(){
 const all=new Set([...drivenKeys,...oneWayKeys,...skipKeys]);
 const range=getProgressRangeInfo(),fylke=getProgressFylkeId();
 const out=[];
 for(const key of all){
  if(!keyPassesCategoryFilter(key))continue;
  if(!keyHasTimeInRange(key,range))continue;
  if(!keyPassesProgressFylke(key,fylke))continue;
  out.push(key);
 }
 return out;
}
function getProgressListItem(key){
 const meta=getReportRoadMeta(key);
 const ds=directionState[key]||{};
 const isSkip=skipKeys.has(key);
 const isDone=drivenKeys.has(key);
 const isOne=oneWayKeys.has(key)&&!isDone;
 const lastTs=Math.max(ds.fwdLastTs||0,ds.revLastTs||0,ds.manualTs||0);
 const dirLabel=isSkip?'⛔':(ds.fwd&&ds.rev?'🟢':(ds.fwd||ds.rev?'🟡':'•'));
 return {key,veg:meta.veg,seg:meta.seg,fylke:meta.fylke,fylkeName:fylkeName(meta.fylke)||'–',lenKm:meta.lenKm||0,lastTs,isSkip,isDone,isOne,dirLabel,manualFull:!!ds.manualFull};
}
function filterProgressItems(items,searchText){
 if(!searchText)return items;
 const q=searchText.toLowerCase().trim();
 if(!q)return items;
 const terms=q.split(/\\s+/).filter(Boolean);
 return items.filter(it=>{
  const hay=(it.veg+' '+it.seg+' '+(it.fylkeName||'')).toLowerCase();
  return terms.every(t=>hay.includes(t));
 });
}
function sortProgressItems(items,sortMode){
 const arr=items.slice();
 if(sortMode==='recent')arr.sort((a,b)=>(b.lastTs||0)-(a.lastTs||0));
 else if(sortMode==='veg-asc')arr.sort((a,b)=>a.veg.localeCompare(b.veg,'no')||a.seg.localeCompare(b.seg,'no'));
 else if(sortMode==='veg-desc')arr.sort((a,b)=>b.veg.localeCompare(a.veg,'no')||a.seg.localeCompare(b.seg,'no'));
 else if(sortMode==='len-desc')arr.sort((a,b)=>(b.lenKm||0)-(a.lenKm||0));
 else if(sortMode==='len-asc')arr.sort((a,b)=>(a.lenKm||0)-(b.lenKm||0));
 return arr;
}
function renderProgressList(){
 const listEl=document.getElementById('progress-edit-list');
 const moreEl=document.getElementById('progress-edit-more');
 if(!listEl)return;
 const allKeys=getProgressListKeys();
 const items=allKeys.map(k=>getProgressListItem(k));
 const filtered=filterProgressItems(items,progressListFilter);
 const sorted=sortProgressItems(filtered,progressListSort);
 const total=sorted.length;
 const shown=sorted.slice(0,progressListRenderLimit);
 if(!total){
  listEl.innerHTML='<div class="pe-empty">Ingen strekninger matcher filteret. Endre Periode/Fylke/Kategori eller slett soekstekst.</div>';
  moreEl.style.display='none';
 }else{
  listEl.innerHTML=shown.map(it=>{
   const sel=selectedProgressKeys.has(it.key);
   const km=(it.lenKm||0).toFixed(2);
   const dt=it.lastTs?formatDateOnly(it.lastTs):'–';
   const tag=it.manualFull?' <span style="color:#7bc1ff;font-weight:700">[manuell]</span>':'';
   return `<div class="pe-row${sel?' selected':''}" data-key="${esc(it.key)}"><input type="checkbox" class="pe-cb" data-cbkey="${esc(it.key)}" ${sel?'checked':''}><div class="pe-veg">${esc(it.veg)}<span class="pe-seg">${esc(it.seg)}</span>${tag}</div><div class="pe-meta"><span>${km}km</span><span>${esc(it.fylkeName)}</span><span>${dt}</span></div><div class="pe-status">${it.dirLabel}</div></div>`;
  }).join('');
  if(total>shown.length){
   moreEl.style.display='block';
   moreEl.textContent=`Vis flere (${total-shown.length} til) ⌄`;
  }else{
   moreEl.style.display='none';
  }
  listEl.querySelectorAll('.pe-row').forEach(row=>{
   row.addEventListener('click',(ev)=>{
    if(ev.target.classList.contains('pe-cb'))return;
    const cb=row.querySelector('.pe-cb');
    if(cb){cb.checked=!cb.checked;cb.dispatchEvent(new Event('change',{bubbles:true}))}
   });
  });
  listEl.querySelectorAll('.pe-cb').forEach(cb=>{
   cb.addEventListener('change',()=>{
    const k=cb.getAttribute('data-cbkey');
    if(cb.checked)selectedProgressKeys.add(k);
    else selectedProgressKeys.delete(k);
    const row=cb.closest('.pe-row');
    if(row)row.classList.toggle('selected',cb.checked);
    updateProgressListSummary(total);
   });
  });
 }
 updateProgressListSummary(total);
}
function updateProgressListSummary(total){
 const sumEl=document.getElementById('pe-summary-text');
 if(!sumEl)return;
 sumEl.textContent=`${selectedProgressKeys.size} valgt · ${total} synlige`;
}
function highlightProgressListKey(key){
 const listEl=document.getElementById('progress-edit-list');
 if(!listEl)return;
 const row=listEl.querySelector(`.pe-row[data-key="${CSS.escape(key)}"]`);
 if(!row){
  progressListRenderLimit=Math.max(progressListRenderLimit,1000);
  renderProgressList();
  setTimeout(()=>highlightProgressListKey(key),50);
  return;
 }
 row.classList.remove('highlight');
 void row.offsetWidth;
 row.classList.add('highlight');
 row.scrollIntoView({behavior:'smooth',block:'center'});
}
function selectAllVisibleProgressKeys(){
 const allKeys=getProgressListKeys();
 const items=allKeys.map(k=>getProgressListItem(k));
 const filtered=filterProgressItems(items,progressListFilter);
 const sorted=sortProgressItems(filtered,progressListSort);
 const visible=sorted.slice(0,progressListRenderLimit);
 for(const it of visible)selectedProgressKeys.add(it.key);
 renderProgressList();
}
function clearProgressSelection(){
 selectedProgressKeys.clear();
 renderProgressList();
}
function batchProgressAction(action){
 const keys=[...selectedProgressKeys];
 if(!keys.length){setMessage('Ingen strekninger valgt.','notice');return}
 if(action==='delete'&&!confirm(`Slette ALL status og spor for ${keys.length} strekninger?\\n\\nFjerner directionState, routeLog og skip-flagg. Bruk Gjenopprett fra snapshot hvis noe gar galt.\\n\\nIDB-snapshot tas automatisk for sikkerhet.`))return;
 if(action==='delete'||action==='done'||action==='skip'){
  saveIdbSnapshot('batch-'+action,true).catch(()=>{});
 }
 let count=0;
 for(const key of keys){
  if(action==='done'){setRoadDoneFull(key);count++}
  else if(action==='one'){
   const ds=directionState[key]||{};
   if(!ds.fwd&&!ds.rev)continue;
   const keepFwd=!!ds.fwd,keepRev=!!ds.rev;
   if(keepFwd&&keepRev){
    const fwdCount=(routeLog[key]?.fwd||[]).length;
    const revCount=(routeLog[key]?.rev||[]).length;
    if(fwdCount>=revCount){
     directionState[key].rev=false;
     delete directionState[key].revFirstTs;delete directionState[key].revLastTs;
     if(routeLog[key])delete routeLog[key].rev;
    }else{
     directionState[key].fwd=false;
     delete directionState[key].fwdFirstTs;delete directionState[key].fwdLastTs;
     if(routeLog[key])delete routeLog[key].fwd;
    }
   }
   directionState[key].manualFull=false;
   delete directionState[key].manualTs;
   count++;
  }
  else if(action==='skip'){setRoadSkipFromTable(key);count++}
  else if(action==='null'){clearRoadProgressForKey(key,{clearSkip:true});count++}
  else if(action==='delete'){
   delete directionState[key];
   delete routeLog[key];
   skipKeys.delete(key);
   drivenKeys.delete(key);
   oneWayKeys.delete(key);
   delete visitLog[key];
   count++;
  }
 }
 saveDirectionState();saveRouteLog();saveState();
 rebuildStatusSetsFromDirections();
 selectedProgressKeys.clear();
 renderAllViews();
 const labels={done:'satt til ferdig',one:'satt til 1 retning',skip:'satt til kjoeres ikke',null:'nullstilt',delete:'slettet'};
 setMessage(`${count} strekninger ${labels[action]||'oppdatert'}.`,'success');
}
function applyProgressSplitRatio(){
 const ratio=Math.max(0.15,Math.min(0.85,Number(settings.progressSplitRatio)||0.5));
 const map=document.getElementById('progress-map-container');
 const sec=document.getElementById('progress-edit-section');
 if(!map||!sec)return;
 map.style.flex=`${ratio} ${ratio} 0`;
 sec.style.flex=`${1-ratio} ${1-ratio} 0`;
 if(progressMap&&typeof progressMap.invalidateSize==='function'){
  setTimeout(()=>progressMap.invalidateSize(true),50);
 }
}
function setupProgressSplitter(){
 const splitter=document.getElementById('progress-splitter');
 if(!splitter||splitter._setup)return;
 splitter._setup=true;
 let dragging=false,startY=0,startRatio=0,tabHeight=0;
 const onStart=(clientY)=>{
  dragging=true;startY=clientY;
  startRatio=Math.max(0.15,Math.min(0.85,Number(settings.progressSplitRatio)||0.5));
  const tab=document.getElementById('tab-progress');
  const filterBox=document.getElementById('progress-filter-box');
  const stats=document.getElementById('progress-stats');
  const headerH=(filterBox?.offsetHeight||0)+(stats?.offsetHeight||0)+(splitter.offsetHeight||14);
  tabHeight=Math.max(200,(tab?.clientHeight||500)-headerH);
  splitter.classList.add('dragging');
 };
 const onMove=(clientY)=>{
  if(!dragging)return;
  const dy=clientY-startY;
  const newRatio=Math.max(0.15,Math.min(0.85,startRatio+dy/tabHeight));
  settings.progressSplitRatio=newRatio;
  applyProgressSplitRatio();
 };
 const onEnd=()=>{
  if(!dragging)return;
  dragging=false;
  splitter.classList.remove('dragging');
  saveSettings();
 };
 splitter.addEventListener('mousedown',e=>{e.preventDefault();onStart(e.clientY)});
 document.addEventListener('mousemove',e=>{if(dragging){e.preventDefault();onMove(e.clientY)}});
 document.addEventListener('mouseup',onEnd);
 splitter.addEventListener('touchstart',e=>{if(e.touches[0]){onStart(e.touches[0].clientY)}},{passive:true});
 splitter.addEventListener('touchmove',e=>{if(e.touches[0]&&dragging){e.preventDefault();onMove(e.touches[0].clientY)}},{passive:false});
 splitter.addEventListener('touchend',onEnd);
 splitter.addEventListener('touchcancel',onEnd);
}
function setupProgressEditEventHandlers(){
 const search=document.getElementById('progress-edit-search');
 if(search&&!search._setup){
  search._setup=true;
  search.addEventListener('input',()=>{
   progressListFilter=search.value||'';
   progressListRenderLimit=200;
   renderProgressList();
  });
 }
 const sort=document.getElementById('progress-edit-sort');
 if(sort&&!sort._setup){
  sort._setup=true;
  sort.addEventListener('change',()=>{progressListSort=sort.value;renderProgressList()});
 }
 const more=document.getElementById('progress-edit-more');
 if(more&&!more._setup){
  more._setup=true;
  more.addEventListener('click',()=>{progressListRenderLimit+=200;renderProgressList()});
 }
 const wireBtn=(id,fn)=>{
  const b=document.getElementById(id);
  if(b&&!b._setup){b._setup=true;b.addEventListener('click',fn)}
 };
 wireBtn('pe-select-all',selectAllVisibleProgressKeys);
 wireBtn('pe-clear-sel',clearProgressSelection);
 wireBtn('pe-set-done',()=>batchProgressAction('done'));
 wireBtn('pe-set-one',()=>batchProgressAction('one'));
 wireBtn('pe-set-skip',()=>batchProgressAction('skip'));
 wireBtn('pe-set-null',()=>batchProgressAction('null'));
 wireBtn('pe-set-del',()=>batchProgressAction('delete'));
}

"""
old_marker = "/* ---------------- v2.0.49: IDB-SNAPSHOT-ROTASJON ---------------- */"
assert old_marker in html
html = html.replace(old_marker, edit_funcs + old_marker, 1)
print("OK 6: Liste-funksjoner")

# 7. updateProgressMap utvidet
old = "function updateProgressMap(){"
new = "function updateProgressMap(){renderProgressList();setupProgressEditEventHandlers();applyProgressSplitRatio();"
assert old in html
html = html.replace(old, new, 1)
print("OK 7: updateProgressMap hook")

# 8. Polyline click
old = """function drawCoverageIntervals(targetMap,plan,intervals,col,weight,opacity,bounds){let drew=false;for(const it of intervals||[]){const parts=extractChainInterval(plan.chain,plan.measures,it.start,it.end);for(const part of parts){const lls=part.map(c=>[c[1],c[0]]);if(lls.length>=2){const pl=L.polyline(lls,{color:col,weight,opacity}).addTo(targetMap);if(targetMap===map&&Array.isArray(roadLayers))roadLayers.push(pl);bounds.push(...lls);drew=true}}}return drew}"""
new = """function drawCoverageIntervals(targetMap,plan,intervals,col,weight,opacity,bounds){let drew=false;for(const it of intervals||[]){const parts=extractChainInterval(plan.chain,plan.measures,it.start,it.end);for(const part of parts){const lls=part.map(c=>[c[1],c[0]]);if(lls.length>=2){const pl=L.polyline(lls,{color:col,weight,opacity}).addTo(targetMap);if(targetMap===map&&Array.isArray(roadLayers))roadLayers.push(pl);if(targetMap===progressMap&&plan.key){pl.on('click',()=>{highlightProgressListKey(plan.key)})}bounds.push(...lls);drew=true}}}return drew}"""
assert old in html
html = html.replace(old, new)
print("OK 8: Polyline click")

# 9. showTab progress
old = """ if(t==='progress'){
  const ok=await ensureLeafletReady();
  if(!ok){setMapError('progress-map-container','Leaflet ble ikke lastet. Legg vendor/leaflet.js + vendor/leaflet.css i apppakken, eller test med nett slik at CDN-fallback virker.');closeMenu();return}
  initProgressMap();
  setTimeout(()=>{safeInvalidate(progressMap);updateProgressMap();setTimeout(()=>safeInvalidate(progressMap),350)},80);
 }"""
new = """ if(t==='progress'){
  const ok=await ensureLeafletReady();
  if(!ok){setMapError('progress-map-container','Leaflet ble ikke lastet. Legg vendor/leaflet.js + vendor/leaflet.css i apppakken, eller test med nett slik at CDN-fallback virker.');closeMenu();return}
  initProgressMap();
  setupProgressEditEventHandlers();
  setupProgressSplitter();
  applyProgressSplitRatio();
  setTimeout(()=>{safeInvalidate(progressMap);updateProgressMap();setTimeout(()=>safeInvalidate(progressMap),350)},80);
 }"""
assert old in html
html = html.replace(old, new)
print("OK 9: showTab progress")

# 10. tab-progress flex-column
old = "#tab-map,#tab-progress{position:relative;min-height:0}"
new = "#tab-map,#tab-progress{position:relative;min-height:0}#tab-progress{display:none}#tab-progress.active{display:flex;flex-direction:column}"
assert old in html
html = html.replace(old, new)
print("OK 10: flex-column")

# Valider
final_len = len(html)
print(f"\nDifferanse: +{final_len-original_len} tegn")
assert html.startswith('<!DOCTYPE html>')
assert html.rstrip().endswith('</html>')
assert 'v2.0.49.1-ios' not in html
assert 'v2.0.50-ios' in html
assert 'progress-edit-list' in html
assert 'renderProgressList' in html
assert 'setupProgressSplitter' in html
assert 'progressSplitRatio' in html
assert 'highlightProgressListKey' in html
assert 'batchProgressAction' in html

with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"OK Skrevet til {OUTPUT}")
