#!/usr/bin/env python3
# KV-GSV fase-deteksjon: les fase=G fra NVDB og klassifiser kommunale GSV-er korrekt.
# 
# Endring:
#   1. loadRoadsAround leser vegsys.fase og lagrer det pa road-objektet
#   2. For kat=K og fase=G bygges veg-prefikset som "Kv{nr}G" i stedet for "Kv{nr}"
#   3. roadFilterKey faar gsv=true hvis kat=K og fase=G (override av isGSV som ser pa S/D)
#   4. getRoadMetaFromKey gjenkjenner /^Kv\d+G/i som KV-GSV
#
# IKKE endret:
#   - FV/EV/RV-klassifisering (uendret, bruker fortsatt isGSV via S/D-nummer)
#   - Eksisterende historikk (Kv...-noekler uten G blir vanlig KV til omraadet lastes paa nytt)
#   - GPS-deteksjon, IDB-skjema, andre datafelt
#
# Idempotent: kan kjores flere ganger trygt.

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / 'docs'
TARGET = DOCS_DIR / 'index1.html'

if not TARGET.exists():
    print(f'[ERROR] {TARGET} finnes ikke')
    sys.exit(1)

html = TARGET.read_text(encoding='utf-8')
print(f'[INFO] Leste {TARGET.name} ({len(html)} bytes)')

if "/^Kv\\d+G/i.test(key)" in html or "_kvFase" in html:
    print('[INFO] KV-fase-deteksjon finnes allerede, hopper over')
    sys.exit(0)

# Sjekk forutsetninger fra forrige patch (KV-kategori)
if "ALLOWED_KATS=new Set(['E','R','F','K'])" not in html:
    print('[ERROR] Forutsetter at KV-kategori-patch er kjort. ALLOWED_KATS uten K funnet.')
    sys.exit(1)

changes = []

# 1. getRoadMetaFromKey: gjenkjenn Kv...G som KGSV.
# Nyt mønster: hvis nøkkelen starter med Kv tallene G (f.eks. Kv399G_S4D1_0), 
# settes kat=K og gsv=true uavhengig av S/D-nummer.
# Original (etter forrige patch):
old1 = "function getRoadMetaFromKey(key){let kat='F';if(/^Ev/i.test(key))kat='E';else if(/^Rv/i.test(key))kat='R';else if(/^Kv/i.test(key))kat='K';const m=String(key).match(/S\\d+D(\\d+)/i);return{kat,gsv:!!(m&&Number(m[1])>=100)}}"
new1 = "function getRoadMetaFromKey(key){let kat='F';let kvFaseG=false;if(/^Ev/i.test(key))kat='E';else if(/^Rv/i.test(key))kat='R';else if(/^Kv/i.test(key)){kat='K';if(/^Kv\\d+G/i.test(key))kvFaseG=true}const m=String(key).match(/S\\d+D(\\d+)/i);const gsv=kvFaseG||!!(m&&Number(m[1])>=100);return{kat,gsv}}"
if old1 in html:
    html = html.replace(old1, new1)
    changes.append('getRoadMetaFromKey: gjenkjenner Kv{nr}G som KGSV')
else:
    print('[ERROR] getRoadMetaFromKey-anchor ikke funnet (forventet form fra KV-kategori-patch)')
    sys.exit(1)

# 2. roadFilterKey: hvis kat=K og r.fase=G eller r.gsv=true, returner KGSV.
# Original-funksjonen er ikke direkte tilgjengelig som enkelt-anchor, men:
old2 = "function roadFilterKey(r){return r.kat+(r.gsv?'GSV':'')}"
new2 = "function roadFilterKey(r){const isKvFaseG=(r.kat==='K'&&r.fase==='G');return r.kat+((r.gsv||isKvFaseG)?'GSV':'')}"
if old2 in html:
    html = html.replace(old2, new2)
    changes.append('roadFilterKey: KV+fase=G klassifiseres som KGSV')
else:
    print('[WARN] roadFilterKey-anchor ikke funnet')

# 3. loadRoadsAround: les vegsys.fase og bruk den i nøkkel + segment-felt for KV-GSV.
# Vi finner linjen som bygger road-objektet og legger fase + justert nøkkelprefiks.
# Originallinje:
old3 = ("const strek=vs.strekning,seg=`S${strek.strekning}D${strek.delstrekning}`,gsv=isGSV(seg),"
        "vegnavn=`${roadPrefixFromKat(kat)}${vegsys.nummer}${vs.klasse||vegsys.klasse||''}`,"
        "parts=parseWkt(s?.geometri?.wkt).map(p=>p.filter(isVLL)).filter(p=>p.length>=2);")
new3 = ("const strek=vs.strekning,seg=`S${strek.strekning}D${strek.delstrekning}`,"
        "_kvFase=String(vegsys.fase||'').toUpperCase(),"
        "_isKvFaseG=(kat==='K'&&_kvFase==='G'),"
        "gsv=isGSV(seg)||_isKvFaseG,"
        "_kvFaseSuffix=_isKvFaseG?'G':'',"
        "vegnavn=`${roadPrefixFromKat(kat)}${vegsys.nummer}${_kvFaseSuffix}${vs.klasse||vegsys.klasse||''}`,"
        "parts=parseWkt(s?.geometri?.wkt).map(p=>p.filter(isVLL)).filter(p=>p.length>=2);")
if old3 in html:
    html = html.replace(old3, new3)
    changes.append('loadRoadsAround: leser fase, bygger Kv{nr}G-prefiks for KV-GSV')
else:
    print('[ERROR] loadRoadsAround road-bygging-anchor ikke funnet')
    sys.exit(1)

# 4. loadRoadsAround: bevar fase i out.push(...) slik at r.fase er tilgjengelig for roadFilterKey.
old4 = ("out.push({key:`${vegnavn}_${seg}_${out.length}`,veg:vegnavn,kat,gsv,nr:Number(vegsys.nummer)||0,"
        "seg,str:Number(strek.strekning)||0,dstr:Number(strek.delstrekning)||0,"
        "fra:fraM,til:tilM,len:Number(s.lengde)||0,fylke:fylkeNr?String(fylkeNr):'',"
        "typeVeg:s.typeVeg||'',detaljnivaa:s.detaljnivå||s.detaljniva||'',"
        "partsWithMeter:parts.map(p=>({coords:p,fra:fraM,til:tilM})),parts,minDist:null})")
new4 = ("out.push({key:`${vegnavn}_${seg}_${out.length}`,veg:vegnavn,kat,gsv,fase:_kvFase,"
        "nr:Number(vegsys.nummer)||0,"
        "seg,str:Number(strek.strekning)||0,dstr:Number(strek.delstrekning)||0,"
        "fra:fraM,til:tilM,len:Number(s.lengde)||0,fylke:fylkeNr?String(fylkeNr):'',"
        "typeVeg:s.typeVeg||'',detaljnivaa:s.detaljnivå||s.detaljniva||'',"
        "partsWithMeter:parts.map(p=>({coords:p,fra:fraM,til:tilM})),parts,minDist:null})")
if old4 in html:
    html = html.replace(old4, new4)
    changes.append('loadRoadsAround: lagrer fase pa road-objekt')
else:
    print('[ERROR] out.push-anchor ikke funnet')
    sys.exit(1)

# Skriv resultat
TARGET.write_text(html, encoding='utf-8')
print(f'[INFO] Skrev {TARGET.name} ({len(html)} bytes)')
print(f'[INFO] Endringer: {len(changes)}')
for c in changes:
    print(f'  - {c}')
print('=== Ferdig ===')
