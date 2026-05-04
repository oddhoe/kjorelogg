#!/usr/bin/env python3
# KV-GSV v6:
# - KV-GSV defineres på KV + trafikantgruppe G / gående og syklende, eventuelt kortform med KV... G.
# - D>=100 skal ikke alene klassifisere kommunal veg som GSV.
# - Legger inn synlige underfilterknapper for KV-GSV langs FV/EV/RV uten å være avhengig av eksisterende kategoriliste.
# - Underfilteret bruker nærmeste ordinære F/E/R-veg i allerede innlastet road-datasett.

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / 'docs'
TARGETS = [p for p in [DOCS_DIR / 'index1.html', DOCS_DIR / 'index.html'] if p.exists()]
if not TARGETS:
    print('[ERROR] Fant verken docs/index1.html eller docs/index.html')
    sys.exit(1)


def find_function_span(src, name):
    start = src.find(f'function {name}(')
    if start < 0:
        return None
    brace = src.find('{', start)
    if brace < 0:
        return None
    depth = 0
    quote = None
    esc = False
    for i in range(brace, len(src)):
        ch = src[i]
        if quote:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == quote:
                quote = None
            continue
        if ch in ('"', "'", '`'):
            quote = ch
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
    return None


def patch_target(TARGET: Path):
    html = TARGET.read_text(encoding='utf-8')
    orig = html
    changes = []
    print(f'[INFO] Leser {TARGET.relative_to(REPO_ROOT)} ({len(html)} bytes)')

    def replace_function(name, new_code, label, required=False):
        nonlocal html
        span = find_function_span(html, name)
        if not span:
            msg = '[ERROR]' if required else '[WARN]'
            print(f'{msg} Fant ikke function {name}')
            if required:
                raise RuntimeError(f'Mangler function {name}')
            return False
        old = html[span[0]:span[1]]
        if old == new_code:
            print(f'[OK] {label} allerede korrekt')
            return True
        html = html[:span[0]] + new_code + html[span[1]:]
        changes.append(label)
        print(f'[PATCH] {label}')
        return True

    # Fjern eldre helperblokker, men la resten av koden stå.
    for tag in ['KV-GSV langs filter v5', 'KV-GSV v6']:
        html2, n = re.subn(rf"\n?/\* === {re.escape(tag)} === \*/.*?/\* === /{re.escape(tag)} === \*/\n?", "\n", html, flags=re.DOTALL)
        if n:
            html = html2
            print(f'[INFO] Fjernet gammel blokk: {tag} ({n})')

    helper_and_filter = r"""/* === KV-GSV v6 === */
function kgsvV6Text(v){if(v==null)return'';if(typeof v==='string'||typeof v==='number'||typeof v==='boolean')return String(v);if(Array.isArray(v))return v.map(kgsvV6Text).join(' ');if(typeof v==='object'){return [v.kode,v.verdi,v.navn,v.name,v.tekst,v.value,v.id,v.beskrivelse].map(kgsvV6Text).filter(Boolean).join(' ')}return String(v)}
function kgsvV6Upper(v){return kgsvV6Text(v).toUpperCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'')}
function kgsvV6IsTrafG(v){const s=kgsvV6Upper(v);return /(^|[^A-Z])G([^A-Z]|$)/.test(s)||s.includes('GAENDE')||s.includes('GÅENDE')||s.includes('SYKLENDE')||s.includes('GANG')&&s.includes('SYKKEL')}
function kgsvV6IsGsvType(v){const s=kgsvV6Upper(v);return s.includes('GANG- OG SYKKEL')||s.includes('GANG OG SYKKEL')||s.includes('GANG/SYKKEL')||s.includes('SYKKELVEG')||s.includes('SYKKELVEI')||s.includes('GANGVEG')||s.includes('GANGVEI')||s.includes('GATE')&&s.includes('GA')}
function kgsvV6HasKvG(v){const s=kgsvV6Text(v);return /\bKV\s*\d+\s+G\b/i.test(s)||/\bK\s*V\s*\d+\s+G\b/i.test(s)||/^Kv\d+G/i.test(s)}
function kgsvV6IsKvGsv(r){if(!r||String(r.kat||'').toUpperCase()!=='K')return false;const txt=String(r.veg||r.key||'');return kgsvV6IsTrafG(r.trafikantgruppe)||kgsvV6HasKvG(txt)||kgsvV6HasKvG(r.kortform)||kgsvV6IsGsvType(r.typeVegText||r.typeVeg||r.typeveg||r.objekttype||r.navn||r.detNavn)}
function kgsvV6AllRoads(){try{if(typeof roads!=='undefined'&&Array.isArray(roads))return roads}catch(e){}try{if(typeof allRoads!=='undefined'&&Array.isArray(allRoads))return allRoads}catch(e){}try{if(typeof roadData!=='undefined'&&Array.isArray(roadData))return roadData}catch(e){}try{if(typeof visibleRoads!=='undefined'&&Array.isArray(visibleRoads))return visibleRoads}catch(e){}try{if(window&&Array.isArray(window.roads))return window.roads}catch(e){}try{if(window&&Array.isArray(window.allRoads))return window.allRoads}catch(e){}try{if(window&&window.state&&Array.isArray(window.state.roads))return window.state.roads}catch(e){}return []}
function kgsvV6Pt(p){if(Array.isArray(p))return{lat:Number(p[0]),lon:Number(p[1])};if(p&&typeof p==='object')return{lat:Number(p.lat??p.latitude??p.y??p[0]),lon:Number(p.lng??p.lon??p.longitude??p.x??p[1])};return null}
function kgsvV6XY(p,refLat){const R=6371000,lat=Number(p.lat)*Math.PI/180,lon=Number(p.lon)*Math.PI/180,rl=Number(refLat)*Math.PI/180;return{x:R*lon*Math.cos(rl),y:R*lat}}
function kgsvV6DistPtSegM(p,a,b){p=kgsvV6Pt(p);a=kgsvV6Pt(a);b=kgsvV6Pt(b);if(!p||!a||!b||!Number.isFinite(p.lat)||!Number.isFinite(p.lon)||!Number.isFinite(a.lat)||!Number.isFinite(a.lon)||!Number.isFinite(b.lat)||!Number.isFinite(b.lon))return Infinity;const ref=(p.lat+a.lat+b.lat)/3,P=kgsvV6XY(p,ref),A=kgsvV6XY(a,ref),B=kgsvV6XY(b,ref),dx=B.x-A.x,dy=B.y-A.y,len2=dx*dx+dy*dy;if(!len2)return Math.hypot(P.x-A.x,P.y-A.y);let t=((P.x-A.x)*dx+(P.y-A.y)*dy)/len2;t=Math.max(0,Math.min(1,t));return Math.hypot(P.x-(A.x+t*dx),P.y-(A.y+t*dy))}
function kgsvV6Parts(r){const p=r?.parts||r?.coords||r?.geometry||[];if(!Array.isArray(p))return[];if(p.length&&Array.isArray(p[0])&&typeof p[0][0]==='number')return[p];return p.filter(x=>Array.isArray(x)&&x.length)}
function kgsvV6RoadDistM(a,b,stopAt){const pa=kgsvV6Parts(a),pb=kgsvV6Parts(b);let best=Infinity;for(const A of pa){const stepA=Math.max(1,Math.floor(A.length/30));for(let i=0;i<A.length;i+=stepA){for(const B of pb){for(let j=1;j<B.length;j++){const d=kgsvV6DistPtSegM(A[i],B[j-1],B[j]);if(d<best){best=d;if(best<=stopAt)return best}}}}}return best}
function kgsvV6AlongCat(r){const MAX=90,all=kgsvV6AllRoads();const sig=all.length+'|'+String(r?.key||r?.veg||'');if(r&&r._kgsvV6Sig===sig)return r._kgsvV6Cat||'';let best=Infinity,cat='';for(const o of all){if(!o||o===r)continue;const k=String(o.kat||'').toUpperCase();if(k!=='F'&&k!=='E'&&k!=='R')continue;if((k==='F'||k==='E'||k==='R')&&(o.gsv===true||kgsvV6IsKvGsv(o)||String(o.veg||o.key||'').match(/GSV/i)))continue;const d=kgsvV6RoadDistM(r,o,Math.min(best,MAX));if(d<best){best=d;cat=k}}if(r){r._kgsvV6Sig=sig;r._kgsvV6M=best;r._kgsvV6Cat=(best<=MAX)?cat:''}return(best<=MAX)?cat:''}
function kgsvV6Mode(){const m=String(window.__kgsvV6AlongMode||'').toUpperCase();return (m==='F'||m==='E'||m==='R')?m:''}
function roadFilterKey(r){const kat=String(r?.kat||'').toUpperCase();const isKvGsv=(kat==='K')?kgsvV6IsKvGsv(r):false;const isGsv=(kat==='K')?isKvGsv:!!r?.gsv;if(kat==='K'&&isGsv){const m=kgsvV6Mode();if(m){return kgsvV6AlongCat(r)===m?'KGSV':'KGSV_OTHER'}return 'KGSV'}return kat+(isGsv?'GSV':'')}
function kgsvV6ElText(el){return String(el?.textContent||'').replace(/\s+/g,' ').trim()}
function kgsvV6FindCatEl(label){const want=label.toUpperCase();const els=[...document.querySelectorAll('button,[role="button"],label,span,div,a')];return els.find(e=>kgsvV6ElText(e).toUpperCase()===want)||els.find(e=>kgsvV6ElText(e).toUpperCase().includes(want)&&kgsvV6ElText(e).length<=40)}
function kgsvV6Active(el){if(!el)return false;return el.classList.contains('active')||el.classList.contains('selected')||el.getAttribute('aria-pressed')==='true'||el.getAttribute('aria-selected')==='true'||el.checked===true||/active|selected|on/i.test(String(el.className||''))}
function kgsvV6CallRefresh(){['renderAll','render','refresh','refreshViews','renderRoads','renderMap','renderTable','renderOverview','updateUI','updateStats','applyFilters','updateRoadVisibility','drawRoads'].forEach(n=>{try{if(typeof window[n]==='function')window[n]()}catch(e){}});try{window.dispatchEvent(new Event('resize'))}catch(e){}}
function kgsvV6SyncBase(){const base=kgsvV6FindCatEl('KV-GSV');if(!base){kgsvV6CallRefresh();return}window.__kgsvV6Syncing=true;const was=kgsvV6Active(base);try{if(was){base.click();setTimeout(()=>{try{base.click()}catch(e){}window.__kgsvV6Syncing=false;kgsvV6CallRefresh();kgsvV6UpdateUI()},40)}else{base.click();setTimeout(()=>{window.__kgsvV6Syncing=false;kgsvV6CallRefresh();kgsvV6UpdateUI()},40)}}catch(e){window.__kgsvV6Syncing=false;kgsvV6CallRefresh()}}
function kgsvV6SetMode(m){window.__kgsvV6AlongMode=(kgsvV6Mode()===m)?'':m;kgsvV6UpdateUI();kgsvV6SyncBase()}
function kgsvV6UpdateUI(){const m=kgsvV6Mode();document.querySelectorAll('[data-kgsv-v6-mode]').forEach(b=>{const on=b.getAttribute('data-kgsv-v6-mode')===m;b.classList.toggle('active',on);b.style.background=on?'#d6a900':'rgba(255,255,255,.06)';b.style.color=on?'#111':'#fff';b.style.borderColor=on?'#ffe066':'rgba(255,255,255,.18)'})}
function kgsvV6InstallUI(){if(document.getElementById('kgsv-v6-langs-ui')){kgsvV6UpdateUI();return true}const base=kgsvV6FindCatEl('KV-GSV');if(!base)return false;const host=base.parentElement||base;const wrap=document.createElement('div');wrap.id='kgsv-v6-langs-ui';wrap.style.cssText='display:flex;gap:6px;flex-wrap:wrap;margin-top:6px;margin-bottom:2px;width:100%';[['F','langs FV'],['E','langs EV'],['R','langs RV']].forEach(([m,t])=>{const b=document.createElement('button');b.type='button';b.textContent=t;b.setAttribute('data-kgsv-v6-mode',m);b.style.cssText='border:1px solid rgba(255,255,255,.18);border-radius:999px;padding:6px 9px;font-weight:800;font-size:12px;background:rgba(255,255,255,.06);color:#fff;cursor:pointer';b.addEventListener('click',ev=>{ev.preventDefault();ev.stopPropagation();kgsvV6SetMode(m)});wrap.appendChild(b)});try{host.appendChild(wrap)}catch(e){base.insertAdjacentElement('afterend',wrap)}base.addEventListener('click',()=>{if(!window.__kgsvV6Syncing){window.__kgsvV6AlongMode='';setTimeout(()=>{kgsvV6UpdateUI();kgsvV6CallRefresh()},0)}},true);document.addEventListener('click',ev=>{const t=kgsvV6ElText(ev.target).toUpperCase();if(!window.__kgsvV6Syncing&&(t==='ALLE'||t==='INGEN'||t==='NULLSTILL')){window.__kgsvV6AlongMode='';setTimeout(()=>{kgsvV6UpdateUI();kgsvV6CallRefresh()},0)}},true);kgsvV6UpdateUI();return true}
(function(){let tries=0;function tick(){tries++;kgsvV6InstallUI();if(tries<40&&!document.getElementById('kgsv-v6-langs-ui'))setTimeout(tick,400)}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',tick);else tick()})();
/* === /KV-GSV v6 === */"""

    # 1) roadFilterKey + helper block
    if 'function roadFilterKey(' in html:
        replace_function('roadFilterKey', helper_and_filter, 'roadFilterKey + KV-GSV v6 helper/UI')
    elif 'KV-GSV v6' not in html:
        pos = html.rfind('</script>')
        if pos >= 0:
            html = html[:pos] + '\n' + helper_and_filter + '\n' + html[pos:]
            changes.append('injiserer KV-GSV v6 helper/UI før </script>')
            print('[PATCH] injiserer KV-GSV v6 helper/UI før </script>')
        else:
            print('[ERROR] Fant ikke roadFilterKey eller </script>')
            raise RuntimeError('Mangler roadFilterKey og </script>')

    # 2) getRoadMetaFromKey: eldre lagrede nøkler. For KV er bare Kv{nr}G sikker GSV-indikator.
    new_meta = "function getRoadMetaFromKey(key){let kat='F';let kvG=false;if(/^Ev/i.test(key))kat='E';else if(/^Rv/i.test(key))kat='R';else if(/^Kv/i.test(key)){kat='K';kvG=/^Kv\\d+G/i.test(String(key))||/\\bKV\\s*\\d+\\s+G\\b/i.test(String(key))}const m=String(key).match(/S\\d+D(\\d+)/i);const gsv=(kat==='K')?kvG:!!(m&&Number(m[1])>=100);return{kat,gsv}}"
    if 'function getRoadMetaFromKey(' in html:
        replace_function('getRoadMetaFromKey', new_meta, 'getRoadMetaFromKey: KV bruker Kv{nr}G, ikke D>=100')

    # 3) loadRoadsAround: robust KV-GSV-deteksjon fra trafikantgruppe/kortform.
    new_load = ("const strek=vs.strekning||{},seg=`S${strek.strekning}D${strek.delstrekning}`,")
    new_load += ("_kvKort=String(vs.kortform||s?.vegsystemreferanse?.kortform||''),")
    new_load += ("_kvTrafikantgruppeRaw=(strek.trafikantgruppe??vs.trafikantgruppe??s?.trafikantgruppe??''),")
    new_load += ("_kvTrafikantgruppe=kgsvV6Text(_kvTrafikantgruppeRaw).toUpperCase(),")
    new_load += ("_kvTypeRaw=(s?.typeVeg??s?.typeveg??s?.type??s?.objekttype??s?.navn??s?.detaljnivå??s?.detaljniva??''),")
    new_load += ("_kvTypeText=kgsvV6Text(_kvTypeRaw),")
    new_load += ("_kvKortErG=kgsvV6HasKvG(_kvKort),")
    new_load += ("_isKvGsv=(kat==='K'&&(kgsvV6IsTrafG(_kvTrafikantgruppeRaw)||_kvKortErG||kgsvV6IsGsvType(_kvTypeText))),")
    new_load += ("gsv=(kat==='K')?_isKvGsv:isGSV(seg),")
    new_load += ("_kvGsvSuffix=_isKvGsv?'G':'',")
    new_load += ("vegnavn=`${roadPrefixFromKat(kat)}${vegsys.nummer}${_kvGsvSuffix}${vs.klasse||vegsys.klasse||''}`,parts=parseWkt(s?.geometri?.wkt).map(p=>p.filter(isVLL)).filter(p=>p.length>=2);")
    load_pat = (r"const strek=vs\.strekning,seg=`S\$\{strek\.strekning\}D\$\{strek\.delstrekning\}`"
                r".*?parts=parseWkt\(s\?\.geometri\?\.wkt\)\.map\(p=>p\.filter\(isVLL\)\)\.filter\(p=>p\.length>=2\);")
    html2, n = re.subn(load_pat, lambda m: new_load, html, count=1, flags=re.DOTALL)
    if n:
        html = html2
        changes.append('loadRoadsAround: KV-GSV via trafikantgruppe/kortform/type')
        print('[PATCH] loadRoadsAround: KV-GSV via trafikantgruppe/kortform/type')
    elif '_isKvGsv=(kat===\'K\'&&' in html and '_kvTrafikantgruppe' in html:
        print('[OK] loadRoadsAround har allerede KV-GSV trafikantgruppe-regel')
    else:
        print('[WARN] loadRoadsAround-anchor ikke funnet; roadFilterKey/UI ble likevel oppdatert')

    # 4) out.push: lagre trafikantgruppe, kortform og typeVegText på road-objektet.
    new_push = ("out.push({key:`${vegnavn}_${seg}_${out.length}`,veg:vegnavn,kat,gsv,")
    new_push += ("trafikantgruppe:_kvTrafikantgruppe,kortform:_kvKort,typeVegText:_kvTypeText,")
    new_push += ("nr:Number(vegsys.nummer)||0,seg,str:Number(strek.strekning)||0,dstr:Number(strek.delstrekning)||0,")
    new_push += ("fra:fraM,til:tilM,len:Number(s.lengde)||0,fylke:fylkeNr?String(fylkeNr):'',")
    new_push += ("typeVeg:s.typeVeg||'',detaljnivaa:s.detaljnivå||s.detaljniva||'',")
    new_push += ("partsWithMeter:parts.map(p=>({coords:p,fra:fraM,til:tilM})),parts,minDist:null})")
    push_pat = (r"out\.push\(\{key:`\$\{vegnavn\}_\$\{seg\}_\$\{out\.length\}`"
                r".*?partsWithMeter:parts\.map\(p=>\(\{coords:p,fra:fraM,til:tilM\}\)\),parts,minDist:null\}\)")
    html2, n = re.subn(push_pat, lambda m: new_push, html, count=1, flags=re.DOTALL)
    if n:
        html = html2
        changes.append('road-objekt: lagrer trafikantgruppe/kortform/typeVegText')
        print('[PATCH] road-objekt: lagrer trafikantgruppe/kortform/typeVegText')
    elif 'trafikantgruppe:_kvTrafikantgruppe' in html:
        print('[OK] road-objekt lagrer allerede trafikantgruppe/kortform')
    else:
        print('[WARN] out.push-anchor ikke funnet')

    if html != orig:
        TARGET.write_text(html, encoding='utf-8')
    print(f'[INFO] Skrev {TARGET.relative_to(REPO_ROOT)} ({len(html)} bytes), endringer: {len(changes)}')
    for c in changes:
        print(f'  - {c}')
    return len(changes)


total = 0
for target in TARGETS:
    try:
        total += patch_target(target)
    except Exception as e:
        print(f'[ERROR] Patch feilet for {target}: {e}')
        sys.exit(1)
print(f'=== Ferdig. Totalt endringer: {total} ===')

