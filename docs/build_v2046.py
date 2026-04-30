#!/usr/bin/env python3
"""
Bygg v2.0.47-ios fra v2.0.46-ios.

Endringer:
  1. APP_VERSION: v2.0.46-ios -> v2.0.47-ios
  2. getRoadHeadingAtPoint: bruk normalisert chain (fikser fwd/rev-flipping
     pga inkonsistent intern orientering i NVDB-segmenter)
  3. Ny meny-handling "Korriger retning": rydder eksisterende falske rev-spor
"""
import sys

if len(sys.argv) != 3:
    print(__doc__)
    sys.exit(1)

INPUT, OUTPUT = sys.argv[1], sys.argv[2]

with open(INPUT, 'r', encoding='utf-8') as f:
    html = f.read()

original_len = len(html)
print(f"Lest {original_len} tegn fra {INPUT}")

# ENDRING 1: APP_VERSION
old = "const APP_VERSION='v2.0.46-ios';"
new = "const APP_VERSION='v2.0.47-ios';"
assert old in html, "Fant ikke APP_VERSION"
html = html.replace(old, new)
html = html.replace("Vegmåling · v2.0.46-ios", "Vegmåling · v2.0.47-ios")
html = html.replace("kjorelogg-nvdb-fartsgrense/v2.0.46", "kjorelogg-nvdb-fartsgrense/v2.0.47")
html = html.replace("kjorelogg-nvdb-gps/v2.0.46", "kjorelogg-nvdb-gps/v2.0.47")
print("OK APP_VERSION")

# ENDRING 2: getRoadHeadingAtPoint bruker chain
old = "function getRoadHeadingAtPoint(lat,lon,r,myHeading){if(!r.parts)return null;let bestDist=Infinity,bestHeading=null;for(const part of r.parts){for(let i=0;i<part.length-1;i++){const a=part[i],b=part[i+1],d=ptSeg(lat,lon,a,b);if(d<bestDist){bestDist=d;const dy=b[1]-a[1],dx=b[0]-a[0];bestHeading=(Math.atan2(dx,dy)*180/Math.PI+360)%360}}}if(bestHeading===null)return null;let diff=Math.abs((myHeading??0)-bestHeading);if(diff>180)diff=360-diff;return{heading:bestHeading,isForward:diff<90}}"

new = """function getRoadHeadingAtPoint(lat,lon,r,myHeading){
 // v2.0.47: bruker normalisert chain via makeChainsFromParts i stedet for raa r.parts.
 // Tidligere kunne samme kjoretning klassifiseres vekselvis som fwd og rev nar GPS-fix
 // krysset fra ett NVDB-segment til et annet med motsatt intern retning. Chain-en er
 // normalisert av orderPartsForBridging og gir konsistent retning langs hele veg-objektet.
 if(!r||!r.parts)return null;
 const chains=makeChainsFromParts(r.parts,35);
 if(!chains.length)return null;
 let bestDist=Infinity,bestHeading=null;
 for(const chain of chains){
  for(let i=0;i<chain.length-1;i++){
   const a=chain[i],b=chain[i+1],d=ptSeg(lat,lon,a,b);
   if(d<bestDist){bestDist=d;const dy=b[1]-a[1],dx=b[0]-a[0];bestHeading=(Math.atan2(dx,dy)*180/Math.PI+360)%360}
  }
 }
 if(bestHeading===null)return null;
 let diff=Math.abs((myHeading??0)-bestHeading);
 if(diff>180)diff=360-diff;
 return{heading:bestHeading,isForward:diff<90};
}"""

assert old in html, "Fant ikke getRoadHeadingAtPoint"
html = html.replace(old, new)
print("OK getRoadHeadingAtPoint")

# ENDRING 3: repairFalseRevTracks-funksjon
repair_func = """
/* ---------------- v2.0.47: KORRIGER RETNING ---------------- */
function intervalOverlapM(a,b){return Math.max(0,Math.min(a.end,b.end)-Math.max(a.start,b.start))}
function totalOverlap(intervalsA,intervalsB){
 let total=0;
 for(const a of intervalsA){for(const b of intervalsB){total+=intervalOverlapM(a,b)}}
 return total;
}
function repairFalseRevTracks(){
 const candidates=Object.keys(routeLog||{}).filter(k=>{
  const log=routeLog[k];
  return log&&Array.isArray(log.rev)&&log.rev.length>0&&Array.isArray(log.fwd)&&log.fwd.length>0;
 });
 if(!candidates.length){
  setMessage('Ingen kandidater for retningskorrigering funnet.','notice');
  return;
 }
 let cleaned=0,kept=0,inspected=0;
 for(const key of candidates){
  inspected++;
  const r=getRoadObjectForDisplay(key)||roadByKeyAny(key);
  if(!r||!r.parts)continue;
  const chains=makeChainsFromParts(r.parts,35);
  if(!chains.length)continue;
  let totalRevLen=0,overlapLen=0;
  for(const chain of chains){
   const measures=chainMeasures(chain);
   const fwdInts=buildIntervalsFromTrackPoints(routeLog[key].fwd||[],chain,measures);
   const revInts=buildIntervalsFromTrackPoints(routeLog[key].rev||[],chain,measures);
   if(!revInts.length)continue;
   totalRevLen+=intervalsKm(revInts)*1000;
   overlapLen+=totalOverlap(fwdInts,revInts);
  }
  if(totalRevLen<10){kept++;continue}
  const overlapRatio=overlapLen/totalRevLen;
  if(overlapRatio>=0.9){
   delete routeLog[key].rev;
   if(directionState[key]){
    directionState[key].rev=false;
    delete directionState[key].revFirstTs;
    delete directionState[key].revLastTs;
   }
   cleaned++;
  }else{
   kept++;
  }
 }
 if(cleaned>0){
  saveRouteLog();
  saveDirectionState();
  rebuildStatusSetsFromDirections();
  saveState();
  renderAllViews();
  setMessage(`Retningskorrigering ferdig: ${cleaned} strekninger renset, ${kept} beholdt (av ${inspected}).`,'success');
 }else{
  setMessage(`Sjekket ${inspected} strekninger. Ingen falske rev-spor funnet.`,'notice');
 }
}

"""

old_marker = "/* \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 IMPORT / EXPORT \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 */"
assert old_marker in html, "Fant ikke IMPORT/EXPORT-markor"
html = html.replace(old_marker, repair_func + old_marker, 1)
print("OK repairFalseRevTracks lagt til")

# ENDRING 4: Meny-knapp
old = '<button class="menu-item" id="btn-repairgeom">\U0001f527 Reparer geometri</button>'
new = '<button class="menu-item" id="btn-repairgeom">\U0001f527 Reparer geometri</button> <button class="menu-item" id="btn-repairdir">\U0001f504 Korriger retning</button>'
assert old in html, "Fant ikke btn-repairgeom-knapp"
html = html.replace(old, new)
print("OK Meny-knapp lagt til")

# ENDRING 5: Event handler
old = "document.getElementById('btn-repairgeom').addEventListener('click',()=>{const ok=repairGeomCacheFromRoads();closeMenu();rebuildMapIfNeeded();updateProgressMap();setMessage(ok?'Geometri-cache reparert/utvidet fra innlastede veger.':'Ingen ny geometri \u00e5 reparere akkurat n\u00e5. Trykk Oppdater i omr\u00e5det f\u00f8rst.','success');renderStats();});"

new = "document.getElementById('btn-repairgeom').addEventListener('click',()=>{const ok=repairGeomCacheFromRoads();closeMenu();rebuildMapIfNeeded();updateProgressMap();setMessage(ok?'Geometri-cache reparert/utvidet fra innlastede veger.':'Ingen ny geometri \u00e5 reparere akkurat n\u00e5. Trykk Oppdater i omr\u00e5det f\u00f8rst.','success');renderStats();});\ndocument.getElementById('btn-repairdir')?.addEventListener('click',()=>{closeMenu();if(!confirm('Korriger retning?\\n\\nLeter etter rev-spor som er en delmengde av fwd-spor (>=90% overlapp) og fjerner dem. Disse er sannsynligvis falske rev-merker fra tidligere bug. Reelle motsatt-kjoringer beholdes.'))return;repairFalseRevTracks()});"

assert old in html, "Fant ikke btn-repairgeom event handler"
html = html.replace(old, new)
print("OK Event handler wire-et opp")

# VALIDER
final_len = len(html)
print(f"\nDifferanse: +{final_len-original_len} tegn")
assert html.startswith('<!DOCTYPE html>')
assert html.rstrip().endswith('</html>')
assert 'v2.0.46-ios' not in html, "Restspor av v2.0.46"
assert 'v2.0.47-ios' in html

with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"OK Skrevet til {OUTPUT}")
