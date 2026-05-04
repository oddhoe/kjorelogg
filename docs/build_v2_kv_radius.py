#!/usr/bin/env python3
# KV-radius-cap: hvis K eller KGSV er aktiv i categoryFilter, begrens effektiv
# NVDB-fetch-radius til 3 km. Brukeren ser radius-feltet uendret. Synlig
# melding nar cap-en slar inn.
# Idempotent.

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

if 'KV_RADIUS_CAP_KM' in html:
    print('[INFO] KV-radius-cap finnes allerede, hopper over')
    sys.exit(0)

changes = []

# 1. Legg til konstant rett etter DEFAULT_CATEGORY_FILTER
old1 = "const DEFAULT_CATEGORY_FILTER={E:false,EGSV:false,R:false,RGSV:false,F:true,FGSV:false,K:false,KGSV:false};"
new1 = old1 + "\nconst KV_RADIUS_CAP_KM=3;"
if old1 in html:
    html = html.replace(old1, new1)
    changes.append('KV_RADIUS_CAP_KM konstant')
else:
    print('[ERROR] Forutsetter at KV-kategori-patch er kjort. DEFAULT_CATEGORY_FILTER med K=false ikke funnet.')
    sys.exit(1)

# 2. Hjelpefunksjon: getEffectiveRadius(requestedKm). Plasseres rett etter currentProfile.
old2 = "function currentProfile(){return settings.dataSaver?DATA_SAVER_ON:DATA_SAVER_OFF}"
new2 = (old2 +
        "\nfunction kvFilterActive(){return !!(settings.categoryFilter&&(settings.categoryFilter.K||settings.categoryFilter.KGSV))}"
        "\nfunction getEffectiveRadiusKm(requestedKm){"
        "const r=Number(requestedKm);"
        "if(!Number.isFinite(r)||r<=0)return r;"
        "if(kvFilterActive()&&r>KV_RADIUS_CAP_KM)return KV_RADIUS_CAP_KM;"
        "return r;"
        "}")
if old2 in html:
    html = html.replace(old2, new2)
    changes.append('kvFilterActive + getEffectiveRadiusKm')
else:
    print('[WARN] currentProfile-anchor ikke funnet')

# 3. updateFromCenter: bytt radius-beregningen til a bruke effective radius.
# Vi finner den eksisterende linjen og legger inn cap-logikk pa toppen av den.
# Original-linjen er svaert lang og kompleks; vi gjor en mer fokusert endring.
old3 = "const lat=c.lat,lon=c.lon,requestedRadius=parseFloat(document.getElementById('radius').value)||currentProfile().radiusDefault,denseCityRule=getDenseCityRadiusRule(lat,lon,requestedRadius),radius=denseCityRule?DENSE_CITY_RADIUS_LIMIT_KM:requestedRadius;"
new3 = ("const lat=c.lat,lon=c.lon,_userRadius=parseFloat(document.getElementById('radius').value)||currentProfile().radiusDefault,"
        "_kvCappedRadius=getEffectiveRadiusKm(_userRadius),"
        "_kvCapApplied=_kvCappedRadius<_userRadius,"
        "requestedRadius=_kvCappedRadius,"
        "denseCityRule=getDenseCityRadiusRule(lat,lon,requestedRadius),"
        "radius=denseCityRule?DENSE_CITY_RADIUS_LIMIT_KM:requestedRadius;")
if old3 in html:
    html = html.replace(old3, new3)
    changes.append('updateFromCenter radius-cap')
else:
    print('[WARN] updateFromCenter radius-linje ikke funnet')

# 4. Vis melding nar cap-en slar inn. Plasseres etter denseCityRule-meldingen.
# Original loading-melding er:
#   setMessage(c.manual?'Laster vegnett rundt manuell markor...':(denseCityRule?...:''));
# Vi lar den vaere; etter den linjen logger vi i tillegg KV-cap-info hvis aktuelt.
old4 = "setMessage(c.manual?'Laster vegnett rundt manuell markør…':(denseCityRule?`${denseCityRule.name}: tett vegnett, radius satt til ${DENSE_CITY_RADIUS_LIMIT_KM} km for komplett lasting.`:''));"
new4 = (old4 +
        "\n  if(_kvCapApplied&&!denseCityRule){"
        "setMessage(`Kommunale veger aktiv - radius begrenset fra ${_userRadius} til ${KV_RADIUS_CAP_KM} km. Sla av KV i kategorier for full radius.`,'notice');"
        "}")
if old4 in html:
    html = html.replace(old4, new4)
    changes.append('KV-cap brukermelding')
else:
    print('[WARN] denseCityRule-meldingen ikke funnet')

# 5. applySettingsToUI: ikke overstyr radius-feltet basert pa KV-cap (brukeren ser
# fortsatt sin egen verdi). Ingen endring her - feltet skal vaere uendret.

# Skriv resultat
TARGET.write_text(html, encoding='utf-8')
print(f'[INFO] Skrev {TARGET.name} ({len(html)} bytes)')
print(f'[INFO] Endringer: {len(changes)}')
for c in changes:
    print(f'  - {c}')
print('=== Ferdig ===')
