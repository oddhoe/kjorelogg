#!/usr/bin/env python3
"""Bygg v2.0.49.1-ios fra v2.0.49-ios. Mini-patch: rampe/GSV-logikk."""
import sys
if len(sys.argv) != 3:
    print(__doc__); sys.exit(1)
INPUT, OUTPUT = sys.argv[1], sys.argv[2]
with open(INPUT, 'r', encoding='utf-8') as f:
    html = f.read()
original_len = len(html)
print(f"Lest {original_len} tegn")

# 1. APP_VERSION
old = "const APP_VERSION='v2.0.49-ios';"
assert old in html
html = html.replace(old, "const APP_VERSION='v2.0.49.1-ios';")
html = html.replace("Vegmåling · v2.0.49-ios", "Vegmåling · v2.0.49.1-ios")
html = html.replace("kjorelogg-nvdb-fartsgrense/v2.0.49", "kjorelogg-nvdb-fartsgrense/v2.0.49.1")
html = html.replace("kjorelogg-nvdb-gps/v2.0.49", "kjorelogg-nvdb-gps/v2.0.49.1")
print("OK 1: APP_VERSION")

# 2. Rampe-logikk i loop (foer manualFull-sjekk)
old = """ for(const key of allRevKeys){
  inspected++;
  const log=routeLog[key]||{};
  const hasRevPoints=Array.isArray(log.rev)&&log.rev.length>0;
  const hasFwdPoints=Array.isArray(log.fwd)&&log.fwd.length>0;
  const ds=directionState[key]||{};
  if(ds.manualFull){keptManualFull++;continue}"""
new = """ for(const key of allRevKeys){
  inspected++;
  const log=routeLog[key]||{};
  const hasRevPoints=Array.isArray(log.rev)&&log.rev.length>0;
  const hasFwdPoints=Array.isArray(log.fwd)&&log.fwd.length>0;
  const ds=directionState[key]||{};
  // v2.0.49.1: Ramper/GSV kjores alltid one-way.
  const meta=getRoadMetaFromKey(key);
  if(meta.gsv){
   if(ds.fwd&&ds.rev){
    const fwdCount=(log.fwd||[]).length;
    const revCount=(log.rev||[]).length;
    if(fwdCount>=revCount){
     delete routeLog[key].rev;
     if(directionState[key]){
      directionState[key].rev=false;
      delete directionState[key].revFirstTs;
      delete directionState[key].revLastTs;
     }
    }else{
     delete routeLog[key].fwd;
     if(directionState[key]){
      directionState[key].fwd=false;
      delete directionState[key].fwdFirstTs;
      delete directionState[key].fwdLastTs;
     }
    }
    cleanedRamp++;
    continue;
   }
   keptRamp++;
   continue;
  }
  if(ds.manualFull){keptManualFull++;continue}"""
assert old in html
html = html.replace(old, new)
print("OK 2: Rampe-logikk")

# 3. Tellere
old = "let cleanedInterleaved=0,cleanedShortNoData=0,keptManualFull=0,keptSeparate=0,keptOnlyRev=0,keptLongNoData=0,keptUnknownTs=0,inspected=0;"
new = "let cleanedInterleaved=0,cleanedShortNoData=0,cleanedRamp=0,keptManualFull=0,keptSeparate=0,keptOnlyRev=0,keptLongNoData=0,keptUnknownTs=0,keptRamp=0,inspected=0;"
assert old in html
html = html.replace(old, new)
print("OK 3: Tellere")

# 4. Total summering
old = """ const totalCleaned=cleanedInterleaved+cleanedShortNoData;
 const totalKept=keptManualFull+keptSeparate+keptOnlyRev+keptLongNoData+keptUnknownTs;"""
new = """ const totalCleaned=cleanedInterleaved+cleanedShortNoData+cleanedRamp;
 const totalKept=keptManualFull+keptSeparate+keptOnlyRev+keptLongNoData+keptUnknownTs+keptRamp;"""
assert old in html
html = html.replace(old, new)
print("OK 4: Summering")

# 5. Success-melding
old = """  if(cleanedInterleaved)parts.push(`${cleanedInterleaved} interleaved <5min`);
  if(cleanedShortNoData)parts.push(`${cleanedShortNoData} uten GPS-data <60s`);
  parts.push(`${totalKept} beholdt`);
  if(keptManualFull)parts.push(`${keptManualFull} manuelt ferdig`);
  if(keptSeparate)parts.push(`${keptSeparate} ekte motsatt-kjoring`);
  if(keptOnlyRev)parts.push(`${keptOnlyRev} kun rev`);
  if(keptLongNoData)parts.push(`${keptLongNoData} >=60s uten data`);
  if(keptUnknownTs)parts.push(`${keptUnknownTs} uten tidsstempler`);"""
new = """  if(cleanedRamp)parts.push(`${cleanedRamp} ramper/GSV med begge retninger`);
  if(cleanedInterleaved)parts.push(`${cleanedInterleaved} interleaved <5min`);
  if(cleanedShortNoData)parts.push(`${cleanedShortNoData} uten GPS-data <60s`);
  parts.push(`${totalKept} beholdt`);
  if(keptRamp)parts.push(`${keptRamp} ramper/GSV one-way (ok)`);
  if(keptManualFull)parts.push(`${keptManualFull} manuelt ferdig`);
  if(keptSeparate)parts.push(`${keptSeparate} ekte motsatt-kjoring`);
  if(keptOnlyRev)parts.push(`${keptOnlyRev} kun rev`);
  if(keptLongNoData)parts.push(`${keptLongNoData} >=60s uten data`);
  if(keptUnknownTs)parts.push(`${keptUnknownTs} uten tidsstempler`);"""
assert old in html
html = html.replace(old, new)
print("OK 5: Success-melding")

# 6. 'Ingen falske'-melding
old = """  const parts=[];
  if(keptManualFull)parts.push(`${keptManualFull} manuelt ferdig`);
  if(keptSeparate)parts.push(`${keptSeparate} ekte motsatt-kjoring`);
  if(keptOnlyRev)parts.push(`${keptOnlyRev} kun rev`);
  if(keptLongNoData)parts.push(`${keptLongNoData} >=60s uten data`);
  if(keptUnknownTs)parts.push(`${keptUnknownTs} uten tidsstempler`);
  setMessage(`Sjekket ${inspected} strekninger. Ingen falske rev-spor (${parts.join(', ')||'alt ok'}).`,'notice');"""
new = """  const parts=[];
  if(keptRamp)parts.push(`${keptRamp} ramper/GSV one-way`);
  if(keptManualFull)parts.push(`${keptManualFull} manuelt ferdig`);
  if(keptSeparate)parts.push(`${keptSeparate} ekte motsatt-kjoring`);
  if(keptOnlyRev)parts.push(`${keptOnlyRev} kun rev`);
  if(keptLongNoData)parts.push(`${keptLongNoData} >=60s uten data`);
  if(keptUnknownTs)parts.push(`${keptUnknownTs} uten tidsstempler`);
  setMessage(`Sjekket ${inspected} strekninger. Ingen falske rev-spor (${parts.join(', ')||'alt ok'}).`,'notice');"""
assert old in html
html = html.replace(old, new)
print("OK 6: Ingen falske-melding")

# 7. Confirm-dialog
old = "if(!confirm('Korriger retning?\\n\\nFjerner falske rev-merker:\\n- Rev-spor logget innen 5 min av fwd (samme tur)\\n- Rev-flagg uten GPS-data <60 sek\\n\\nManuelt ferdig og ekte motsatt-kjoringer (separate turer) beholdes.\\n\\nIDB-snapshot tas automatisk for sikkerhet.'))return;"
new = "if(!confirm('Korriger retning?\\n\\nFjerner falske rev-merker:\\n- Ramper/GSV med begge retninger satt (skal alltid vaere one-way)\\n- Rev-spor logget innen 5 min av fwd (samme tur)\\n- Rev-flagg uten GPS-data <60 sek\\n\\nManuelt ferdig og ekte motsatt-kjoringer (separate turer) beholdes.\\n\\nIDB-snapshot tas automatisk for sikkerhet.'))return;"
assert old in html
html = html.replace(old, new)
print("OK 7: Confirm-dialog")

# Valider
final_len = len(html)
print(f"\nDifferanse: +{final_len-original_len} tegn")
assert html.startswith('<!DOCTYPE html>')
assert html.rstrip().endswith('</html>')
assert 'v2.0.49-ios' not in html
assert 'v2.0.49.1-ios' in html
assert 'cleanedRamp' in html
assert 'meta.gsv' in html

with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"OK Skrevet til {OUTPUT}")
