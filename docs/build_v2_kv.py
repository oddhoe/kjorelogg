#!/usr/bin/env python3
# Legger til KV og KV-GSV i vegkategori-filteret pa index1.html.
# Endrer:
#   - ALLOWED_KATS: legger til 'K'
#   - ROAD_FETCH_REFS: 'E,R,F' -> 'E,R,F,K'
#   - roadPrefixFromKat: K -> 'Kv'
#   - roadMainKatLabel: K -> 'KV'
#   - DEFAULT_CATEGORY_FILTER: K=false, KGSV=false
#   - Cat-chip CSS for K og KGSV (gul)
#   - Meny-chips for KV og KV-GSV
#   - activeCategoryText() inkluderer KV og KV-GSV
# Ingen endringer i GPS-logikk eller IDB-skjema.
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

# Idempotens-sjekk
if 'data-cat="K"' in html and 'KGSV' in html:
    print('[INFO] KV-stotte finnes allerede, hopper over')
    sys.exit(0)

changes = []

# 1. ALLOWED_KATS
old1 = "const ALLOWED_KATS=new Set(['E','R','F']);"
new1 = "const ALLOWED_KATS=new Set(['E','R','F','K']);"
if old1 in html:
    html = html.replace(old1, new1)
    changes.append('ALLOWED_KATS')
else:
    print('[WARN] ALLOWED_KATS ikke funnet')

# 2. ROAD_FETCH_REFS
old2 = "const ROAD_FETCH_REFS='E,R,F'"
new2 = "const ROAD_FETCH_REFS='E,R,F,K'"
if old2 in html:
    html = html.replace(old2, new2)
    changes.append('ROAD_FETCH_REFS')
else:
    print('[WARN] ROAD_FETCH_REFS ikke funnet')

# 3. roadPrefixFromKat
old3 = "function roadPrefixFromKat(k){return k==='E'?'Ev':k==='R'?'Rv':'Fv'}"
new3 = "function roadPrefixFromKat(k){return k==='E'?'Ev':k==='R'?'Rv':k==='K'?'Kv':'Fv'}"
if old3 in html:
    html = html.replace(old3, new3)
    changes.append('roadPrefixFromKat')
else:
    print('[WARN] roadPrefixFromKat ikke funnet')

# 4. roadMainKatLabel
old4 = "function roadMainKatLabel(k){return k==='E'?'EV':k==='R'?'RV':'FV'}"
new4 = "function roadMainKatLabel(k){return k==='E'?'EV':k==='R'?'RV':k==='K'?'KV':'FV'}"
if old4 in html:
    html = html.replace(old4, new4)
    changes.append('roadMainKatLabel')
else:
    print('[WARN] roadMainKatLabel ikke funnet')

# 5. getRoadMetaFromKey - legg til K-prefiks-deteksjon
old5 = "function getRoadMetaFromKey(key){let kat='F';if(/^Ev/i.test(key))kat='E';else if(/^Rv/i.test(key))kat='R';"
new5 = "function getRoadMetaFromKey(key){let kat='F';if(/^Ev/i.test(key))kat='E';else if(/^Rv/i.test(key))kat='R';else if(/^Kv/i.test(key))kat='K';"
if old5 in html:
    html = html.replace(old5, new5)
    changes.append('getRoadMetaFromKey')
else:
    print('[WARN] getRoadMetaFromKey ikke funnet')

# 6. DEFAULT_CATEGORY_FILTER
old6 = "const DEFAULT_CATEGORY_FILTER={E:false,EGSV:false,R:false,RGSV:false,F:true,FGSV:false};"
new6 = "const DEFAULT_CATEGORY_FILTER={E:false,EGSV:false,R:false,RGSV:false,F:true,FGSV:false,K:false,KGSV:false};"
if old6 in html:
    html = html.replace(old6, new6)
    changes.append('DEFAULT_CATEGORY_FILTER')
else:
    print('[WARN] DEFAULT_CATEGORY_FILTER ikke funnet')

# 7. CSS for K og KGSV chips - gult tema
# Finn slutten av FGSV CSS og legg til etter
old7_anchor = '.cat-chip[data-cat=FGSV]{background:#173c22;color:#c2f7c7;border-color:#43a047}'
new7_addition = '.cat-chip[data-cat="K"]{background:#3a3000;color:#ffd866;border-color:#9a7c00}.cat-chip[data-cat=KGSV]{background:#3d3500;color:#ffe199;border-color:#bd9a00}'
if old7_anchor in html and '.cat-chip[data-cat="K"]' not in html:
    html = html.replace(old7_anchor, old7_anchor + new7_addition)
    changes.append('CSS K/KGSV passive')
else:
    print('[WARN] FGSV CSS-anchor ikke funnet eller K finnes allerede')

# 8. CSS active state for K og KGSV
old8_anchor = '.cat-chip.active[data-cat=FGSV]{background:#43a047;color:#fff;border-color:#43a047}'
new8_addition = '.cat-chip.active[data-cat="K"]{background:#9a7c00;color:#fff;border-color:#9a7c00}.cat-chip.active[data-cat=KGSV]{background:#bd9a00;color:#fff;border-color:#bd9a00}'
if old8_anchor in html and '.cat-chip.active[data-cat="K"]' not in html:
    html = html.replace(old8_anchor, old8_anchor + new8_addition)
    changes.append('CSS K/KGSV active')
else:
    print('[WARN] FGSV active CSS-anchor ikke funnet')

# 9. catBadgeHtml - legg til K og KGSV i color-mapping
old9 = "const k=roadFilterKey(r),color=k==='E'?'#6a1b9a':k==='EGSV'?'#8e24aa':k==='R'?'#1565c0':k==='RGSV'?'#1976d2':k==='F'?'#2e7d32':'#43a047';"
new9 = "const k=roadFilterKey(r),color=k==='E'?'#6a1b9a':k==='EGSV'?'#8e24aa':k==='R'?'#1565c0':k==='RGSV'?'#1976d2':k==='F'?'#2e7d32':k==='FGSV'?'#43a047':k==='K'?'#9a7c00':k==='KGSV'?'#bd9a00':'#43a047';"
if old9 in html:
    html = html.replace(old9, new9)
    changes.append('catBadgeHtml')
else:
    print('[WARN] catBadgeHtml color-mapping ikke funnet')

# 10. Meny-chips: legg til KV og KV-GSV etter FV-GSV
old10 = '<button class="cat-chip" data-cat="F">FV</button> <button class="cat-chip" data-cat="FGSV">FV-GSV</button>'
new10 = '<button class="cat-chip" data-cat="F">FV</button> <button class="cat-chip" data-cat="FGSV">FV-GSV</button> <button class="cat-chip" data-cat="K">KV</button> <button class="cat-chip" data-cat="KGSV">KV-GSV</button>'
# Vi vil bare legge til hvis active-klassen eksisterer pa F-chip i originalen
old10_active_variant = '<button class="cat-chip active" data-cat="F">FV</button> <button class="cat-chip" data-cat="FGSV">FV-GSV</button>'
new10_active_variant = '<button class="cat-chip active" data-cat="F">FV</button> <button class="cat-chip" data-cat="FGSV">FV-GSV</button> <button class="cat-chip" data-cat="K">KV</button> <button class="cat-chip" data-cat="KGSV">KV-GSV</button>'

if old10_active_variant in html:
    html = html.replace(old10_active_variant, new10_active_variant)
    changes.append('Meny-chips (active F)')
elif old10 in html:
    html = html.replace(old10, new10)
    changes.append('Meny-chips')
else:
    print('[WARN] FV/FV-GSV meny-chips ikke funnet')

# 11. activeCategoryText - legg til KV og KV-GSV
old11 = "if(cf.F)a.push('FV');if(cf.FGSV)a.push('FV-GSV');return a.length?a.join('/'): 'Ingen'"
new11 = "if(cf.F)a.push('FV');if(cf.FGSV)a.push('FV-GSV');if(cf.K)a.push('KV');if(cf.KGSV)a.push('KV-GSV');return a.length?a.join('/'): 'Ingen'"
if old11 in html:
    html = html.replace(old11, new11)
    changes.append('activeCategoryText')
else:
    print('[WARN] activeCategoryText ikke funnet')

# 12. cat-all (Alle-knapp) skal ogsa sla pa K og KGSV
old12 = "settings.categoryFilter={E:true,EGSV:true,R:true,RGSV:true,F:true,FGSV:true};"
new12 = "settings.categoryFilter={E:true,EGSV:true,R:true,RGSV:true,F:true,FGSV:true,K:true,KGSV:true};"
if old12 in html:
    html = html.replace(old12, new12)
    changes.append('cat-all (Alle)')
else:
    print('[WARN] cat-all (Alle) ikke funnet')

# 13. cat-none (Ingen-knapp) skal ogsa sla av K og KGSV
old13 = "settings.categoryFilter={E:false,EGSV:false,R:false,RGSV:false,F:false,FGSV:false};"
new13 = "settings.categoryFilter={E:false,EGSV:false,R:false,RGSV:false,F:false,FGSV:false,K:false,KGSV:false};"
if old13 in html:
    html = html.replace(old13, new13)
    changes.append('cat-none (Ingen)')
else:
    print('[WARN] cat-none (Ingen) ikke funnet')

# 14. Settings-migration: bump til v8 og fyll inn K/KGSV i eksisterende installs
old14 = "if(!settings.settingsVersion||settings.settingsVersion<7){"
new14 = ("if(!settings.settingsVersion||settings.settingsVersion<8){"
         "if(typeof settings.categoryFilter.K!=='boolean')settings.categoryFilter.K=false;"
         "if(typeof settings.categoryFilter.KGSV!=='boolean')settings.categoryFilter.KGSV=false;"
         "settings.settingsVersion=8;saveSettings();"
         "console.info('v8: KV og KV-GSV lagt til i kategori-filter');"
         "}"
         "if(!settings.settingsVersion||settings.settingsVersion<7){")
if old14 in html and "settings.settingsVersion<8" not in html:
    html = html.replace(old14, new14)
    changes.append('Settings migration v8')
else:
    print('[WARN] Settings migration ikke patchet (eller allerede pa v8)')

# Skriv resultatet
TARGET.write_text(html, encoding='utf-8')
print(f'[INFO] Skrev {TARGET.name} ({len(html)} bytes)')
print(f'[INFO] Endringer: {len(changes)}')
for c in changes:
    print(f'  - {c}')
print('=== Ferdig ===')
