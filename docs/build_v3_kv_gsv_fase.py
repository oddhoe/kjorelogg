#!/usr/bin/env python3
# KV-GSV fase-deteksjon v3.
#
# Hovedregel etter verifisering mot Vegkart/NVDB:
#   - For kommunal veg (kat='K') skal bare vegsystemreferanse.fase === 'G'
#     klassifisere segmentet som GSV/KGSV.
#   - Delstrekning >= 100 skal IKKE alene gi KGSV for kommunale veger.
#   - For E/R/F beholdes gammel GSV-regel via S/D-delstrekning >= 100.
#
# Scriptet er laget for aa kunne kjores baade paa:
#   - pre-v2 index1.html
#   - feil v2 der KV brukte isGSV(seg)||fase=G
#   - allerede korrigert index1.html

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

# Sjekk forutsetninger fra KV-kategori-patch.
if "ALLOWED_KATS=new Set(['E','R','F','K'])" not in html:
    print('[ERROR] Forutsetter at KV-kategori-patch er kjort. ALLOWED_KATS uten K funnet.')
    sys.exit(1)

changes = []


def replace_first(label, old, new):
    global html
    if old in html:
        html = html.replace(old, new, 1)
        changes.append(label)
        print(f'[PATCH] {label}')
        return True
    return False


def ok(label):
    print(f'[OK] {label}')

# 1. getRoadMetaFromKey:
#    For K: bare Kv{nr}G gir gsv=true.
#    For E/R/F: delstrekning >= 100 er fortsatt GSV.
old_meta_pre_v2 = "function getRoadMetaFromKey(key){let kat='F';if(/^Ev/i.test(key))kat='E';else if(/^Rv/i.test(key))kat='R';else if(/^Kv/i.test(key))kat='K';const m=String(key).match(/S\\d+D(\\d+)/i);return{kat,gsv:!!(m&&Number(m[1])>=100)}}"
old_meta_wrong_v2 = "function getRoadMetaFromKey(key){let kat='F';let kvFaseG=false;if(/^Ev/i.test(key))kat='E';else if(/^Rv/i.test(key))kat='R';else if(/^Kv/i.test(key)){kat='K';if(/^Kv\\d+G/i.test(key))kvFaseG=true}const m=String(key).match(/S\\d+D(\\d+)/i);const gsv=kvFaseG||!!(m&&Number(m[1])>=100);return{kat,gsv}}"
new_meta = "function getRoadMetaFromKey(key){let kat='F';let kvFaseG=false;if(/^Ev/i.test(key))kat='E';else if(/^Rv/i.test(key))kat='R';else if(/^Kv/i.test(key)){kat='K';if(/^Kv\\d+G/i.test(key))kvFaseG=true}const m=String(key).match(/S\\d+D(\\d+)/i);const gsv=(kat==='K')?kvFaseG:!!(m&&Number(m[1])>=100);return{kat,gsv}}"
meta_correct_marker = "const gsv=(kat==='K')?kvFaseG:!!(m&&Number(m[1])>=100);return{kat,gsv}"
if not (replace_first('getRoadMetaFromKey: K bruker kun Kv{nr}G/fase-G, ikke D>=100', old_meta_wrong_v2, new_meta) or
        replace_first('getRoadMetaFromKey: legger inn K-regel med fase-G', old_meta_pre_v2, new_meta)):
    if meta_correct_marker in html:
        ok('getRoadMetaFromKey er allerede korrigert')
    else:
        print('[ERROR] getRoadMetaFromKey-anchor ikke funnet')
        sys.exit(1)

# 2. roadFilterKey:
#    For K ignoreres r.gsv dersom den bare kom fra D>=100.
old_filter_pre_v2 = "function roadFilterKey(r){return r.kat+(r.gsv?'GSV':'')}"
old_filter_wrong_v2 = "function roadFilterKey(r){const isKvFaseG=(r.kat==='K'&&r.fase==='G');return r.kat+((r.gsv||isKvFaseG)?'GSV':'')}"
new_filter = "function roadFilterKey(r){const isKvFaseG=(r.kat==='K'&&(r.fase==='G'||/^Kv\\d+G/i.test(String(r.veg||r.key||''))));const isGsv=(r.kat==='K')?isKvFaseG:!!r.gsv;return r.kat+(isGsv?'GSV':'')}"
filter_correct_marker = "const isGsv=(r.kat==='K')?isKvFaseG:!!r.gsv;return r.kat+(isGsv?'GSV':'')"
if not (replace_first('roadFilterKey: K bruker kun fase-G/Kv{nr}G', old_filter_wrong_v2, new_filter) or
        replace_first('roadFilterKey: legger inn K-regel med fase-G', old_filter_pre_v2, new_filter)):
    if filter_correct_marker in html:
        ok('roadFilterKey er allerede korrigert')
    else:
        print('[WARN] roadFilterKey-anchor ikke funnet')

# 3. loadRoadsAround: les vegsys.fase og bygg Kv{nr}G-prefiks.
old_load_pre_v2 = ("const strek=vs.strekning,seg=`S${strek.strekning}D${strek.delstrekning}`,gsv=isGSV(seg),"
                   "vegnavn=`${roadPrefixFromKat(kat)}${vegsys.nummer}${vs.klasse||vegsys.klasse||''}`,"
                   "parts=parseWkt(s?.geometri?.wkt).map(p=>p.filter(isVLL)).filter(p=>p.length>=2);")
new_load = ("const strek=vs.strekning,seg=`S${strek.strekning}D${strek.delstrekning}`,"
            "_kvFase=String(vegsys.fase||'').toUpperCase(),"
            "_isKvFaseG=(kat==='K'&&_kvFase==='G'),"
            "gsv=(kat==='K')?_isKvFaseG:isGSV(seg),"
            "_kvFaseSuffix=_isKvFaseG?'G':'',"
            "vegnavn=`${roadPrefixFromKat(kat)}${vegsys.nummer}${_kvFaseSuffix}${vs.klasse||vegsys.klasse||''}`,"
            "parts=parseWkt(s?.geometri?.wkt).map(p=>p.filter(isVLL)).filter(p=>p.length>=2);")
wrong_gsv_expr = "gsv=isGSV(seg)||_isKvFaseG,"
correct_gsv_expr = "gsv=(kat==='K')?_isKvFaseG:isGSV(seg),"
if replace_first('loadRoadsAround: leser fase og setter KGSV kun ved K+fase=G', old_load_pre_v2, new_load):
    pass
elif wrong_gsv_expr in html:
    html = html.replace(wrong_gsv_expr, correct_gsv_expr)
    changes.append('loadRoadsAround: rettet feil v2 fra isGSV(seg)||fase-G til K?fase-G:isGSV(seg)')
    print('[PATCH] loadRoadsAround: rettet feil v2 fra isGSV(seg)||fase-G til K?fase-G:isGSV(seg)')
elif correct_gsv_expr in html:
    ok('loadRoadsAround har allerede korrekt GSV-regel')
else:
    print('[ERROR] loadRoadsAround GSV-anchor ikke funnet')
    sys.exit(1)

# 4. loadRoadsAround: bevar fase paa road-objektet.
old_push_pre_v2 = ("out.push({key:`${vegnavn}_${seg}_${out.length}`,veg:vegnavn,kat,gsv,nr:Number(vegsys.nummer)||0,"
                   "seg,str:Number(strek.strekning)||0,dstr:Number(strek.delstrekning)||0,"
                   "fra:fraM,til:tilM,len:Number(s.lengde)||0,fylke:fylkeNr?String(fylkeNr):'',"
                   "typeVeg:s.typeVeg||'',detaljnivaa:s.detaljnivå||s.detaljniva||'',"
                   "partsWithMeter:parts.map(p=>({coords:p,fra:fraM,til:tilM})),parts,minDist:null})")
new_push = ("out.push({key:`${vegnavn}_${seg}_${out.length}`,veg:vegnavn,kat,gsv,fase:_kvFase,"
            "nr:Number(vegsys.nummer)||0,"
            "seg,str:Number(strek.strekning)||0,dstr:Number(strek.delstrekning)||0,"
            "fra:fraM,til:tilM,len:Number(s.lengde)||0,fylke:fylkeNr?String(fylkeNr):'',"
            "typeVeg:s.typeVeg||'',detaljnivaa:s.detaljnivå||s.detaljniva||'',"
            "partsWithMeter:parts.map(p=>({coords:p,fra:fraM,til:tilM})),parts,minDist:null})")
if not replace_first('loadRoadsAround: lagrer fase paa road-objekt', old_push_pre_v2, new_push):
    if "kat,gsv,fase:_kvFase" in html:
        ok('road-objekt lagrer allerede fase')
    else:
        print('[ERROR] out.push-anchor ikke funnet')
        sys.exit(1)

TARGET.write_text(html, encoding='utf-8')
print(f'[INFO] Skrev {TARGET.name} ({len(html)} bytes)')
print(f'[INFO] Endringer: {len(changes)}')
for c in changes:
    print(f'  - {c}')
print('=== Ferdig ===')
