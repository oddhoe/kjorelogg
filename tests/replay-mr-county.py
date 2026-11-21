#!/usr/bin/env python3
"""Replay a full Møre og Romsdal FV download, switch to FV-GSV, and reopen the app.

    python -m pip install playwright
    python -m playwright install chromium
    python tests/replay-mr-county.py --pages /path/to/frozen/pages --expect-km 198.3

Supply the original county-wide, EPSG:4326 NVDB response pages (*.gz, objekter).
Omit --expect-km for a newer snapshot. This uses a disposable browser profile,
emulated iPhone viewport and synthetic progress only. All requests are intercepted.
Local app files and responses from the snapshot are served without contacting
production. Bounding-box overlap approximates NVDB's spatial predicate. Reopening
serves a local copy of the app shell and rejects all further road network requests.
"""
import argparse
import gzip
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from playwright.sync_api import sync_playwright


ORIGIN = 'http://127.0.0.1:8534'
API_PATH = '/vegnett/api/v4/veglenkesekvenser/segmentert'
LEVEL_LABELS = {'VT': 'Vegtrase', 'VTKB': 'Vegtrase og kjørebane', 'KB': 'Kjørebane'}
NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
XY = re.compile(rf'(?:^|[(,])\s*({NUMBER})\s+({NUMBER})(?=[\s,)])')

SEED = """async () => {
    if (activeRoadCacheSignature() !== 'F') throw Error('Expected default FV profile');
    const key='Rv999_S1D1';
    directionState[key]={fwd:true,rev:false};
    oneWayKeys.add(key);
    routeLog[key]={fwd:[{ts:1700000000000,lat:62.7,lon:7.1}],rev:[]};
    roadComments[key]={text:'Testmerknad',ts:1,status:'oneway'};
    await flushProgressPersistence();
    const county=document.querySelector('#dl-fylke'), radius=document.querySelector('#dl-radius');
    county.value='15';
    const expected=generateTileGrid('15',Number(radius.value)||10).length;
    await startOfflineDownload();
    return {expected, message:document.querySelector('#dl-status').textContent,
            saved:(await getCountyCacheMeta('15'))?.tiles};
}"""
SWITCH = """async () => {
    settings.progressShowMissing=true; settings.progressShowDone=false;
    settings.progressShowOneway=false; saveSettings();
    document.querySelector('#btn-offlinemode').click();
    await showTab('progress');
    for(const cat of ['FGSV','F'])document.querySelector('.cat-chip[data-cat='+cat+']').click();
    updateProgressMap({fit:true});
}"""
READ = """async () => {
    const hit=await loadCountyRoadsForArea(62.47,6.16,10,'15');
    const key='Rv999_S1D1', meta=await getCountyCacheMeta('15');
    return {counts:meta?.categoryCounts,model:meta?.roadModel,
        area:hit?.area.length,groups:[...new Set((hit?.area||[]).map(roadFilterKey))],
        stats:document.querySelector('#progress-stats').textContent,
        profile:activeRoadCacheSignature(),track:routeLog[key],note:roadComments[key]?.text,
        direction:directionState[key],gps:gps.watching};
}"""


def read_pages(directory):
    records = []
    files = sorted(directory.glob('*.gz'))
    if not files:
        raise ValueError(f'No gzip files in {directory}')
    for path in files:
        with gzip.open(path, 'rt', encoding='utf-8') as source:
            rows = json.load(source)['objekter']
        for row in rows:
            road_system = row.get('vegsystemreferanse', {}).get('vegsystem', {})
            if str(row.get('fylke')) != '15' or (road_system.get('vegkategori'), road_system.get('fase')) != ('F', 'V'):
                raise ValueError(f'{path.name}: expected an FV extract for county 15')
            geometri = row['geometri']
            if int(geometri['srid']) != 4326:
                raise ValueError(f'{path.name}: expected SRID 4326')
            level = row.get('detaljnivå', row.get('detaljniva'))
            level = LEVEL_LABELS.get(level, level)
            if level not in LEVEL_LABELS.values():
                continue
            xy = [(float(x), float(y)) for x, y in XY.findall(geometri['wkt'])]
            if not xy:
                raise ValueError(f'{path.name}: missing coordinates')
            first, second = zip(*xy)
            # EPSG:4326 in these MR extracts uses latitude first. Also accept lon/lat WKT.
            lons, lats = (second, first) if first[0] > 55 else (first, second)
            records.append((min(lons), min(lats), max(lons), max(lats), level, row))
    if not records:
        raise ValueError('No eligible NVDB links in the supplied files')
    return records, len(files)


class Replay:
    def __init__(self, docs, records):
        self.docs = docs.resolve()
        self.app_html = (self.docs / 'index.html').read_bytes()
        self.records = records
        self.matches = {}
        self.requests = 0
        self.download_finished = False
        self.errors = []
        self.blocked = Counter()

    def serve(self, route):
        url = urlsplit(route.request.url)
        try:
            if f'{url.scheme}://{url.netloc}' == ORIGIN:
                if url.path in ('/', '/index.html'):
                    return route.fulfill(body=self.app_html, content_type='text/html; charset=utf-8')
                candidate = (self.docs / url.path.lstrip('/')).resolve()
                if candidate.is_relative_to(self.docs / 'vendor') and candidate.is_file():
                    return route.fulfill(path=candidate)
            if url.hostname == 'nvdbapiles.atlas.vegvesen.no' and url.path == API_PATH:
                return self.road_response(route, url)
            self.blocked[url.netloc] += 1
            return route.abort()
        except Exception as exc:
            self.errors.append(str(exc))
            return route.abort()

    def road_response(self, route, url):
        if self.download_finished:
            raise ValueError('Unexpected NVDB road request during offline readback')
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        if q.get('fylke') != '15' or q.get('vegsystemreferanse') != 'FV' or q.get('srid') != '4326':
            raise ValueError(f'Unsupported replay scope: {url.query}')
        levels = tuple(sorted(set(q.get('detaljniva', '').split(','))))
        if not set(levels) <= LEVEL_LABELS.keys():
            raise ValueError(f'Unexpected or missing NVDB detail level: {levels}')
        bbox = tuple(map(float, q['kartutsnitt'].split(',')))
        key = (bbox, levels)
        if key not in self.matches:
            west, south, east, north = bbox
            labels = {LEVEL_LABELS[code] for code in levels}
            self.matches[key] = [row for x1, y1, x2, y2, label, row in self.records
                                 if x1 <= east and x2 >= west and y1 <= north and y2 >= south and label in labels]
        self.requests += 1
        rows = self.matches[key]
        start, limit = int(q.get('test-offset', 0)), int(q['antall'])
        if start < 0 or limit < 1:
            raise ValueError('Invalid pagination')
        end = start + limit
        meta = {}
        if end < len(rows):
            query = urlencode({**q, 'test-offset': end})
            meta['neste'] = {'href': urlunsplit(url._replace(query=query))}
        return route.fulfill(json={'objekter': rows[start:end], 'metadata': meta},
                             headers={'Access-Control-Allow-Origin': '*'})


def readback(page, expected_km):
    result = page.evaluate(READ)
    assert result['profile'] == 'FGSV' and result['groups'] == ['FGSV'] and result['area'] > 0, result
    assert result['counts']['FGSV'] > 0 and result['counts']['F'] > 0, result
    assert result['track'] == {'fwd': [{'ts': 1700000000000, 'lat': 62.7, 'lon': 7.1}], 'rev': []}, result
    assert result['direction'] == {'fwd': True, 'rev': False} and result['note'] == 'Testmerknad', result
    assert not result['gps'], result
    match = re.search(r'([\d.,]+)\s*km ikke kjørt', result['stats'])
    assert match, result
    result['missingKm'] = float(match[1].replace(',', '.'))
    assert result['missingKm'] > 0, result
    if expected_km is not None:
        assert math.isclose(result['missingKm'], expected_km, rel_tol=0, abs_tol=1e-9), result
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--pages', type=Path, required=True, help='Directory with frozen *.gz NVDB response pages')
    parser.add_argument('--app', type=Path, default=Path(__file__).resolve().parents[1] / 'docs',
                        help='App directory containing index.html and vendor/ (default: ../docs)')
    parser.add_argument('--chromium', help='Chromium executable; defaults to Playwright Chromium')
    parser.add_argument('--chromium-args', type=Path, help='Optional JSON file containing an array of Chromium flags')
    parser.add_argument('--expect-km', type=float, help='Expected displayed FV-GSV missing km for this snapshot')
    args = parser.parse_args()
    flags = json.loads(args.chromium_args.read_text()) if args.chromium_args else []
    if not isinstance(flags, list) or not all(isinstance(x, str) for x in flags):
        parser.error('--chromium-args must point to a JSON array of strings')
    records, n_pages = read_pages(args.pages)
    replay = Replay(args.app, records)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=args.chromium, args=flags)
        device = {k: v for k, v in pw.devices['iPhone 12'].items() if k != 'default_browser_type'}
        ctx = browser.new_context(**device, service_workers='block')
        ctx.route('**/*', replay.serve)
        pg = ctx.new_page()
        pg.on('dialog', lambda d: d.accept())
        pg.on('pageerror', lambda e: replay.errors.append(str(e)))
        pg.goto(ORIGIN)
        pg.wait_for_function('_appReady')
        download = pg.evaluate(SEED)
        assert download['message'].startswith('✅') and download['saved'] == download['expected'], (download, replay.errors)
        assert replay.matches and all(set(levels) == LEVEL_LABELS.keys() for _, levels in replay.matches), replay.errors
        replay.download_finished = True
        pg.evaluate(SWITCH)
        before = readback(pg, args.expect_km)
        pg.reload()
        pg.wait_for_function('_appReady')
        pg.evaluate("async()=>{await showTab('progress');updateProgressMap({fit:true})}")
        after = readback(pg, args.expect_km)
        assert before == after, (before, after)
        assert not replay.errors, replay.errors
        result = {'appSha256': hashlib.sha256(replay.app_html).hexdigest(),
                  'browser': browser.version, 'fixturePages': n_pages, 'eligibleSourceRows': len(records),
                  'download': download, 'distinctQueries': len(replay.matches), 'pagedRequests': replay.requests,
                  'levels': list(LEVEL_LABELS), 'beforeReload': before, 'afterReload': after,
                  'blockedRequestsByHost': dict(replay.blocked), 'errors': replay.errors}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        browser.close()


if __name__ == '__main__':
    main()
