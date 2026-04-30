#!/usr/bin/env python3
"""
Bygg v2.0.48-ios fra v2.0.47-ios.

Endring: utvidet repairFalseRevTracks som også fanger rev-flagg satt uten
routeLog-data (typisk fra v2.0.46-bug). 60-sekunders tidsterskel.
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
old = "const APP_VERSION='v2.0.47-ios';"
new = "const APP_VERSION='v2.0.48-ios';"
assert old in html, "Fant ikke APP_VERSION"
html = html.replace(old, new)
html = html.replace("Vegmåling · v2.0.47-ios", "Vegmåling · v2.0.48-ios")
html = html.replace("kjorelogg-nvdb-fartsgrense/v2.0.47", "kjorelogg-nvdb-fartsgrense/v2.0.48")
html = html.replace("kjorelogg-nvdb-gps/v2.0.47", "kjorelogg-nvdb-gps/v2.0.48")
print("OK APP_VERSION")

# ENDRING 2: Erstatt v2.0.47 repair-funksjonen
old_repair = """function intervalOverlapM(a,b){return Math.max(0,Math.min(a.end,b.end)-Math.max(a.start,b.start))}
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
}"""

new_repair = """function intervalOverlapM(a,b){return Math.max(0,Math.min(a.end,b.end)-Math.max(a.start,b.start))}
function totalOverlap(intervalsA,intervalsB){
 let total=0;
 for(const a of intervalsA){for(const b of intervalsB){total+=intervalOverlapM(a,b)}}
 return total;
}
// v2.0.48: utvidet retningskorrigering. Fanger BAADE keys med rev-routeLog (overlap-test)
// OG keys med directionState.rev=true uten routeLog (60s tidsterskel).
function repairFalseRevTracks(){
 const allRevKeys=new Set();
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

assert old_repair in html, "Fant ikke v2.0.47 repair-funksjon"
html = html.replace(old_repair, new_repair)
print("OK repairFalseRevTracks utvidet")

# ENDRING 3: Confirm-dialog
old_confirm = "if(!confirm('Korriger retning?\\n\\nLeter etter rev-spor som er en delmengde av fwd-spor (>=90% overlapp) og fjerner dem. Disse er sannsynligvis falske rev-merker fra tidligere bug. Reelle motsatt-kjoringer beholdes.'))return;"
new_confirm = "if(!confirm('Korriger retning?\\n\\nFjerner falske rev-merker fra tidligere bug:\\n- Rev-spor med >=90% overlapp med fwd (samme strekning)\\n- Rev-flagg uten GPS-data der flagget var aktivt <60 sek\\n\\nReelle motsatt-kjoringer beholdes. Auto-backup tas av appen automatisk - kan rulles tilbake hvis noe gar galt.'))return;"
assert old_confirm in html, "Fant ikke confirm-dialog"
html = html.replace(old_confirm, new_confirm)
print("OK Confirm-dialog oppdatert")

# VALIDER
final_len = len(html)
print(f"\nDifferanse: +{final_len-original_len} tegn")
assert html.startswith('<!DOCTYPE html>')
assert html.rstrip().endswith('</html>')
assert 'v2.0.47-ios' not in html, "Restspor av v2.0.47"
assert 'v2.0.48-ios' in html

with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"OK Skrevet til {OUTPUT}")
