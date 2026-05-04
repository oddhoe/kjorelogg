#!/usr/bin/env python3
# KV-GSV v8:
# - KV-GSV = kommunal veg (K) + trafikantgruppe G / kortform KV... G / tydelig GSV-type.
# - D>=100 skal ikke alene klassifisere KV som GSV.
# - Underfilterene "langs FV/EV/RV" er begrenset:
#   direkte langs hovedveg + korte sidearmer ett ledd ut fra direkte treff.
# - Hindrer at hele sammenhengende boligfelt/GSV-nett arver "langs FV".

import base64
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / 'docs'
TARGETS = [p for p in [DOCS_DIR / 'index1.html', DOCS_DIR / 'index.html'] if p.exists()]
if not TARGETS:
    print('[ERROR] Fant verken docs/index1.html eller docs/index.html')
    sys.exit(1)


def find_function_span(src: str, name: str):
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

    # Fjern eldre injiserte helperblokker. Dette gjør workflowen idempotent.
    for tag in ['KV-GSV langs filter v5', 'KV-GSV v6', 'KV-GSV v7', 'KV-GSV v8']:
        html2, n = re.subn(
            rf"\n?/\* === {re.escape(tag)} === \*/.*?/\* === /{re.escape(tag)} === \*/\n?",
            "\n",
            html,
            flags=re.DOTALL,
        )
        if n:
            html = html2
            print(f'[INFO] Fjernet gammel blokk: {tag} ({n})')

    helper_and_filter = r"""/* === KV-GSV v8 === */
function kgsvV8Text(v){if(v==null)return'';if(typeof v==='string'||typeof v==='number'||typeof v==='boolean')return String(v);if(Array.isArray(v))return v.map(kgsvV8Text).join(' ');if(typeof v==='object'){return [v.kode,v.verdi,v.navn,v.name,v.tekst,v.value,v.id,v.beskrivelse].map(kgsvV8Text).filter(Boolean).join(' ')}return String(v)}
function kgsvV8Upper(v){return kgsvV8Text(v).toUpperCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'')}
function kgsvV8IsTrafG(v){const s=kgsvV8Upper(v);return /(^|[^A-Z])G([^A-Z]|$)/.test(s)||s.includes('GAENDE')||s.includes('GÅENDE')||s.includes('SYKLENDE')||s.includes('GANG')&&s.includes('SYKKEL')}
function kgsvV8IsGsvType(v){const s=kgsvV8Upper(v);return s.includes('GANG- OG SYKKEL')||s.includes('GANG OG SYKKEL')||s.includes('GANG/SYKKEL')||s.includes('SYKKELVEG')||s.includes('SYKKELVEI')||s.includes('GANGVEG')||s.includes('GANGVEI')}
function kgsvV8HasKvG(v){const s=kgsvV8Text(v);return /\bKV\s*\d+\s+G\b/i.test(s)||/\bK\s*V\s*\d+\s+G\b/i.test(s)||/^Kv\d+G/i.test(s)}
function kgsvV8IsKvGsv(r){if(!r||String(r.kat||'').toUpperCase()!=='K')return false;const txt=String(r.veg||r.key||'');return kgsvV8IsTrafG(r.trafikantgruppe)||kgsvV8HasKvG(txt)||kgsvV8HasKvG(r.kortform)||kgsvV8IsGsvType(r.typeVegText||r.typeVeg||r.typeveg||r.objekttype||r.navn||r.detNavn)}
function kgsvV8AllRoads(){try{if(typeof roads!=='undefined'&&Array.isArray(roads))return roads}catch(e){}try{if(typeof allRoads!=='undefined'&&Array.isArray(allRoads))return allRoads}catch(e){}try{if(typeof roadData!=='undefined'&&Array.isArray(roadData))return roadData}catch(e){}try{if(typeof visibleRoads!=='undefined'&&Array.isArray(visibleRoads))return visibleRoads}catch(e){}try{if(window&&Array.isArray(window.roads))return window.roads}catch(e){}try{if(window&&Array.isArray(window.allRoads))return window.allRoads}catch(e){}try{if(window&&window.state&&Array.isArray(window.state.roads))return window.state.roads}catch(e){}return []}
function kgsvV8Pt(p){if(Array.isArray(p))return{lat:Number(p[0]),lon:Number(p[1])};if(p&&typeof p==='object')return{lat:Number(p.lat??p.latitude??p.y??p[0]),lon:Number(p.lng??p.lon??p.longitude??p.x??p[1])};return null}
function kgsvV8XY(p,refLat){const R=6371000,lat=Number(p.lat)*Math.PI/180,lon=Number(p.lon)*Math.PI/180,rl=Number(refLat)*Math.PI/180;return{x:R*lon*Math.cos(rl),y:R*lat}}
function kgsvV8DistPtSegM(p,a,b){p=kgsvV8Pt(p);a=kgsvV8Pt(a);b=kgsvV8Pt(b);if(!p||!a||!b||!Number.isFinite(p.lat)||!Number.isFinite(p.lon)||!Number.isFinite(a.lat)||!Number.isFinite(a.lon)||!Number.isFinite(b.lat)||!Number.isFinite(b.lon))return Infinity;const ref=(p.lat+a.lat+b.lat)/3,P=kgsvV8XY(p,ref),A=kgsvV8XY(a,ref),B=kgsvV8XY(b,ref),dx=B.x-A.x,dy=B.y-A.y,len2=dx*dx+dy*dy;if(!len2)return Math.hypot(P.x-A.x,P.y-A.y);let t=((P.x-A.x)*dx+(P.y-A.y)*dy)/len2;t=Math.max(0,Math.min(1,t));return Math.hypot(P.x-(A.x+t*dx),P.y-(A.y+t*dy))}
function kgsvV8Parts(r){const p=r?.parts||r?.coords||r?.geometry||[];if(!Array.isArray(p))return[];if(p.length&&Array.isArray(p[0])&&typeof p[0][0]==='number')return[p];return p.filter(x=>Array.isArray(x)&&x.length)}
function kgsvV8BBox(r){if(r&&r._kgsvV8BBox)return r._kgsvV8BBox;let minLat=Infinity,minLon=Infinity,maxLat=-Infinity,maxLon=-Infinity;for(const part of kgsvV8Parts(r)){for(const q of part){const p=kgsvV8Pt(q);if(!p||!Number.isFinite(p.lat)||!Number.isFinite(p.lon))continue;minLat=Math.min(minLat,p.lat);maxLat=Math.max(maxLat,p.lat);minLon=Math.min(minLon,p.lon);maxLon=Math.max(maxLon,p.lon)}}const b=Number.isFinite(minLat)?{minLat,minLon,maxLat,maxLon}:{minLat:0,minLon:0,maxLat:0,maxLon:0};if(r)r._kgsvV8BBox=b;return b}
function kgsvV8BBoxClose(a,b,m){a=kgsvV8BBox(a);b=kgsvV8BBox(b);const d=m/111320;return !(a.maxLat+d<b.minLat||b.maxLat+d<a.minLat||a.maxLon+d<b.minLon||b.maxLon+d<a.minLon)}
function kgsvV8RoadDistM(a,b,stopAt){const pa=kgsvV8Parts(a),pb=kgsvV8Parts(b);let best=Infinity;for(const A of pa){const stepA=Math.max(1,Math.floor(A.length/35));for(let i=0;i<A.length;i+=stepA){for(const B of pb){for(let j=1;j<B.length;j++){const d=kgsvV8DistPtSegM(A[i],B[j-1],B[j]);if(d<best){best=d;if(best<=stopAt)return best}}}}}return best}
function kgsvV8IsOrdinaryMain(o){const k=String(o?.kat||'').toUpperCase();if(k!=='F'&&k!=='E'&&k!=='R')return false;if(o?.gsv===true||kgsvV8IsKvGsv(o)||/GSV/i.test(String(o?.veg||o?.key||'')))return false;return true}
function kgsvV8RoadLenM(r){let v=Number(r?.len);if(Number.isFinite(v)&&v>0)return v;let sum=0;for(const part of kgsvV8Parts(r)){for(let i=1;i<part.length;i++){const a=kgsvV8Pt(part[i-1]),b=kgsvV8Pt(part[i]);if(a&&b&&Number.isFinite(a.lat)&&Number.isFinite(a.lon)&&Number.isFinite(b.lat)&&Number.isFinite(b.lon)){const ref=(a.lat+b.lat)/2,A=kgsvV8XY(a,ref),B=kgsvV8XY(b,ref);sum+=Math.hypot(B.x-A.x,B.y-A.y)}}}return sum}
function kgsvV8Sig(all){return all.length+'|'+all.map((r,i)=>String(r?.key||r?.veg||i)).join('¦')}
function kgsvV8BuildCache(){const all=kgsvV8AllRoads(),sig=kgsvV8Sig(all);if(window.__kgsvV8Cache&&window.__kgsvV8Cache.sig===sig)return window.__kgsvV8Cache;const DIRECT=85,SIDE_CONNECT=30,SIDE_MAX=170,SIDE_LEN_MAX=130;const kgsv=all.filter(r=>String(r?.kat||'').toUpperCase()==='K'&&kgsvV8IsKvGsv(r));const main=all.filter(kgsvV8IsOrdinaryMain);const direct=kgsv.map(()=>new Set());const finalCats=kgsv.map(()=>new Set());const near=kgsv.map(()=>({F:Infinity,E:Infinity,R:Infinity}));for(let i=0;i<kgsv.length;i++){const r=kgsv[i];for(const o of main){if(!kgsvV8BBoxClose(r,o,SIDE_MAX))continue;const cat=String(o.kat).toUpperCase();const d=kgsvV8RoadDistM(r,o,SIDE_MAX);if(d<near[i][cat])near[i][cat]=d;if(d<=DIRECT){direct[i].add(cat);finalCats[i].add(cat)}}}const adj=kgsv.map(()=>[]);for(let i=0;i<kgsv.length;i++){for(let j=i+1;j<kgsv.length;j++){if(!kgsvV8BBoxClose(kgsv[i],kgsv[j],SIDE_CONNECT))continue;const d=kgsvV8RoadDistM(kgsv[i],kgsv[j],SIDE_CONNECT);if(d<=SIDE_CONNECT){adj[i].push(j);adj[j].push(i)}}}for(let i=0;i<kgsv.length;i++){const len=kgsvV8RoadLenM(kgsv[i]);if(!(len>0&&len<=SIDE_LEN_MAX))continue;for(const cat of ['F','E','R']){if(finalCats[i].has(cat))continue;if(near[i][cat]>SIDE_MAX)continue;if(adj[i].some(j=>direct[j].has(cat)))finalCats[i].add(cat)}}const catsByKey={};for(let i=0;i<kgsv.length;i++){const key=String(kgsv[i].key||kgsv[i].veg||i);catsByKey[key]=Array.from(finalCats[i]);try{kgsv[i]._kgsvV8Cats=catsByKey[key].join(',');kgsv[i]._kgsvV8NearF=Math.round(near[i].F);kgsv[i]._kgsvV8Len=Math.round(kgsvV8RoadLenM(kgsv[i]))}catch(e){}}const cache={sig,catsByKey,count:kgsv.length,mainCount:main.length,rule:'direct<=85m, side-arm<=130m one-hop and <=170m from main'};window.__kgsvV8Cache=cache;return cache}
function kgsvV8AlongCats(r){const c=kgsvV8BuildCache();return new Set(c.catsByKey[String(r?.key||r?.veg||'')]||[])}
function kgsvV8Mode(){const m=String(window.__kgsvV8AlongMode||'').toUpperCase();return (m==='F'||m==='E'||m==='R')?m:''}
function roadFilterKey(r){const kat=String(r?.kat||'').toUpperCase();const isKvGsv=(kat==='K')?kgsvV8IsKvGsv(r):false;const isGsv=(kat==='K')?isKvGsv:!!r?.gsv;if(kat==='K'&&isGsv){const m=kgsvV8Mode();if(m){return kgsvV8AlongCats(r).has(m)?'KGSV':'KGSV_OTHER'}return 'KGSV'}return kat+(isGsv?'GSV':'')}
function kgsvV8ElText(el){return String(el?.textContent||'').replace(/\s+/g,' ').trim()}
function kgsvV8FindCatEl(label){const want=label.toUpperCase();const els=[...document.querySelectorAll('button,[role="button"],label,span,div,a')];return els.find(e=>kgsvV8ElText(e).toUpperCase()===want)||els.find(e=>kgsvV8ElText(e).toUpperCase().includes(want)&&kgsvV8ElText(e).length<=40)}
function kgsvV8Active(el){if(!el)return false;return el.classList.contains('active')||el.classList.contains('selected')||el.getAttribute('aria-pressed')==='true'||el.getAttribute('aria-selected')==='true'||el.checked===true||/active|selected|on/i.test(String(el.className||''))}
function kgsvV8CallRefresh(){window.__kgsvV8Cache=null;['renderAll','render','refresh','refreshViews','renderRoads','renderMap','renderTable','renderOverview','updateUI','updateStats','applyFilters','updateRoadVisibility','drawRoads'].forEach(n=>{try{if(typeof window[n]==='function')window[n]()}catch(e){}});try{window.dispatchEvent(new Event('resize'))}catch(e){}}
function kgsvV8SyncBase(){const base=kgsvV8FindCatEl('KV-GSV');if(!base){kgsvV8CallRefresh();return}window.__kgsvV8Syncing=true;const was=kgsvV8Active(base);try{if(was){base.click();setTimeout(()=>{try{base.click()}catch(e){}window.__kgsvV8Syncing=false;kgsvV8CallRefresh();kgsvV8UpdateUI()},40)}else{base.click();setTimeout(()=>{window.__kgsvV8Syncing=false;kgsvV8CallRefresh();kgsvV8UpdateUI()},40)}}catch(e){window.__kgsvV8Syncing=false;kgsvV8CallRefresh()}}
function kgsvV8SetMode(m){window.__kgsvV8AlongMode=(kgsvV8Mode()===m)?'':m;kgsvV8UpdateUI();kgsvV8SyncBase()}
function kgsvV8UpdateUI(){const m=kgsvV8Mode();document.querySelectorAll('[data-kgsv-v8-mode]').forEach(b=>{const on=b.getAttribute('data-kgsv-v8-mode')===m;b.classList.toggle('active',on);b.style.background=on?'#d6a900':'rgba(255,255,255,.06)';b.style.color=on?'#111':'#fff';b.style.borderColor=on?'#ffe066':'rgba(255,255,255,.18)'})}
function kgsvV8InstallUI(){if(document.getElementById('kgsv-v8-langs-ui')){kgsvV8UpdateUI();return true}const base=kgsvV8FindCatEl('KV-GSV');if(!base)return false;const host=base.parentElement||base;const wrap=document.createElement('div');wrap.id='kgsv-v8-langs-ui';wrap.style.cssText='display:flex;gap:6px;flex-wrap:wrap;margin-top:6px;margin-bottom:2px;width:100%';[['F','langs FV'],['E','langs EV'],['R','langs RV']].forEach(([m,t])=>{const b=document.createElement('button');b.type='button';b.textContent=t;b.setAttribute('data-kgsv-v8-mode',m);b.style.cssText='border:1px solid rgba(255,255,255,.18);border-radius:999px;padding:6px 9px;font-weight:800;font-size:12px;background:rgba(255,255,255,.06);color:#fff;cursor:pointer';b.addEventListener('click',ev=>{ev.preventDefault();ev.stopPropagation();kgsvV8SetMode(m)});wrap.appendChild(b)});try{host.appendChild(wrap)}catch(e){base.insertAdjacentElement('afterend',wrap)}base.addEventListener('click',()=>{if(!window.__kgsvV8Syncing){window.__kgsvV8AlongMode='';setTimeout(()=>{kgsvV8UpdateUI();kgsvV8CallRefresh()},0)}},true);document.addEventListener('click',ev=>{const t=kgsvV8ElText(ev.target).toUpperCase();if(!window.__kgsvV8Syncing&&(t==='ALLE'||t==='INGEN'||t==='NULLSTILL')){window.__kgsvV8AlongMode='';setTimeout(()=>{kgsvV8UpdateUI();kgsvV8CallRefresh()},0)}},true);kgsvV8UpdateUI();return true}
(function(){let tries=0;function tick(){tries++;kgsvV8InstallUI();if(tries<40&&!document.getElementById('kgsv-v8-langs-ui'))setTimeout(tick,400)}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',tick);else tick()})();
/* === /KV-GSV v8 === */"""

    # 1) roadFilterKey + helper block
    if 'function roadFilterKey(' in html:
        replace_function('roadFilterKey', helper_and_filter, 'roadFilterKey + KV-GSV v8 begrenset langsfilter')
    elif 'KV-GSV v8' not in html:
        pos = html.rfind('</script>')
        if pos >= 0:
            html = html[:pos] + '\n' + helper_and_filter + '\n' + html[pos:]
            changes.append('injiserer KV-GSV v8 begrenset langsfilter før </script>')
            print('[PATCH] injiserer KV-GSV v8 begrenset langsfilter før </script>')
        else:
            print('[ERROR] Fant ikke roadFilterKey eller </script>')
            raise RuntimeError('Mangler roadFilterKey og </script>')

    # 2) getRoadMetaFromKey: eldre lagrede nøkler. For KV er bare Kv{nr}G sikker GSV-indikator.
    new_meta = "function getRoadMetaFromKey(key){let kat='F';let kvG=false;if(/^Ev/i.test(key))kat='E';else if(/^Rv/i.test(key))kat='R';else if(/^Kv/i.test(key)){kat='K';kvG=/^Kv\\d+G/i.test(String(key))||/\\bKV\\s*\\d+\\s+G\\b/i.test(String(key))}const m=String(key).match(/S\\d+D(\\d+)/i);const gsv=(kat==='K')?kvG:!!(m&&Number(m[1])>=100);return{kat,gsv}}"
    if 'function getRoadMetaFromKey(' in html:
        replace_function('getRoadMetaFromKey', new_meta, 'getRoadMetaFromKey: KV bruker Kv{nr}G, ikke D>=100')

    # 3) loadRoadsAround: robust KV-GSV-deteksjon fra trafikantgruppe/kortform/type.
    new_load = ("const strek=vs.strekning||{},seg=`S${strek.strekning}D${strek.delstrekning}`,")
    new_load += ("_kvKort=String(vs.kortform||s?.vegsystemreferanse?.kortform||''),")
    new_load += ("_kvTrafikantgruppeRaw=(strek.trafikantgruppe??vs.trafikantgruppe??s?.trafikantgruppe??''),")
    new_load += ("_kvTrafikantgruppe=kgsvV8Text(_kvTrafikantgruppeRaw).toUpperCase(),")
    new_load += ("_kvTypeRaw=(s?.typeVeg??s?.typeveg??s?.type??s?.objekttype??s?.navn??s?.detaljnivå??s?.detaljniva??''),")
    new_load += ("_kvTypeText=kgsvV8Text(_kvTypeRaw),")
    new_load += ("_kvKortErG=kgsvV8HasKvG(_kvKort),")
    new_load += ("_isKvGsv=(kat==='K'&&(kgsvV8IsTrafG(_kvTrafikantgruppeRaw)||_kvKortErG||kgsvV8IsGsvType(_kvTypeText))),")
    new_load += ("gsv=(kat==='K')?_isKvGsv:isGSV(seg),")
    new_load += ("_kvGsvSuffix=_isKvGsv?'G':'',")
    new_load += ("vegnavn=`${roadPrefixFromKat(kat)}${vegsys.nummer}${_kvGsvSuffix}${vs.klasse||vegsys.klasse||''}`,parts=parseWkt(s?.geometri?.wkt).map(p=>p.filter(isVLL)).filter(p=>p.length>=2);")

    # Match både original og v6-variant av linja som bygger vegnavn/parts.
    load_patterns = [
        (r"const strek=vs\.strekning,seg=`S\$\{strek\.strekning\}D\$\{strek\.delstrekning\}`.*?parts=parseWkt\(s\?\.geometri\?\.wkt\)\.map\(p=>p\.filter\(isVLL\)\)\.filter\(p=>p\.length>=2\);"),
        (r"const strek=vs\.strekning\|\|\{\},seg=`S\$\{strek\.strekning\}D\$\{strek\.delstrekning\}`.*?parts=parseWkt\(s\?\.geometri\?\.wkt\)\.map\(p=>p\.filter\(isVLL\)\)\.filter\(p=>p\.length>=2\);"),
    ]
    patched_load = False
    for pat in load_patterns:
        html2, n = re.subn(pat, lambda m: new_load, html, count=1, flags=re.DOTALL)
        if n:
            html = html2
            patched_load = True
            changes.append('loadRoadsAround: KV-GSV via trafikantgruppe/kortform/type')
            print('[PATCH] loadRoadsAround: KV-GSV via trafikantgruppe/kortform/type')
            break
    if not patched_load:
        if '_isKvGsv=(kat===\'K\'&&' in html and ('_kvTrafikantgruppe' in html or 'trafikantgruppe:_kvTrafikantgruppe' in html):
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
