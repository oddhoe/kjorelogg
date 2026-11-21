const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../docs/speed.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
function source(reply) {
  const fetch = async url => ({ok: true, json: async () => reply(new URL(url))});
  const context = {
    URL, AbortController, fetch, setTimeout, clearTimeout,
    document: {getElementById: () => ({addEventListener() {}}), querySelectorAll: () => [], addEventListener() {}},
    window: {addEventListener() {}}
  };
  return vm.runInNewContext(script + '\n;({region:osmRegionalService,read:fetchRegionalRoads})', context);
}

function way(oid, changes = {}, geometry = {type: 'LineString', coordinates: [[12.55,55.67], [12.56,55.67]]}) {
  return {type: 'Feature', properties: {OBJECTID: oid, osm_id2: String(oid + 50), highway: 'tertiary',
    name: 'Testvegen', maxspeed: '50', ...changes}, geometry};
}
const collection = features => ({type: 'FeatureCollection', features});
const ids = objectIds => ({objectIdFieldName: 'OBJECTID', objectIds});

test('Regional schemas keep untagged roads, multipart geometry and generic speed provenance', async () => {
  const parts = [[[100,13], [100.01,13]], [[100.02,13], [100.03,13]]];
  const api = source(url => {
    const p = url.searchParams;
    assert.ok(url.hostname.startsWith('services-ap1.'));
    if (p.get('returnIdsOnly')) return {objectIdFieldName: 'objectid', objectIds: [17,18,19,20]};
    assert.doesNotMatch(p.get('outFields'), /motorcar/);
    return collection([
      way(17,{objectid:17, ref:'TH1', maxspeed:'30 mph'}, {type:'MultiLineString', coordinates:parts}),
      way(18,{objectid:18, maxspeed:null}), way(19,{objectid:19,highway:'cycleway'}),
      way(20,{objectid:20,access:'no'})
    ]);
  });
  const service = api.region(13.75,100.5);
  assert.equal(service, api.region(15.84,103.88));
  assert.equal(api.region(55.68,12.57), api.region(59.33,18.06));
  assert.equal(api.region(40,-75), null);
  const roads = await api.read(13.75,100.5,.9,service);
  assert.equal(roads.length, 2);
  assert.equal(JSON.stringify(roads[0].parts), JSON.stringify(parts));
  assert.equal(roads[0].generalOnly, true);
  assert.equal(roads[0].label, 'TH1');
  assert.equal(roads[0].speedForward, 48);
  assert.equal(roads[0].speedBackward, 48);
  assert.equal(roads[1].speed, null);
});

test('Account for every requested ObjectID across pages and collapse identical replicas of an OSM way', async () => {
  let calls = 0;
  const api = source(url => {
    const p = url.searchParams;
    assert.ok(url.hostname.startsWith('services-eu1.'));
    calls++;
    if (p.get('returnIdsOnly')) return ids(Array.from({length:1002}, (_, i) => 1002 - i));
    assert.match(p.get('outFields'), /motorcar/);
    assert.doesNotMatch(p.get('where'), /maxspeed/);
    if (calls === 2) {
      assert.match(p.get('where'), /BETWEEN 1 AND 1000$/);
      return collection(Array.from({length:1000}, (_, i) => way(i+1)));
    }
    assert.match(p.get('where'), /BETWEEN 1001 AND 1002$/);
    return collection([way(1001, {osm_id2:'51'}),way(1002, {area:'yes'})]);
  });
  const roads = await api.read(55.676,12.569,.9,api.region(55.676,12.569));
  assert.equal(calls, 3);
  assert.equal(roads.length, 1000);
  assert.equal(new Set(roads.map(road => road.key)).size, roads.length);
});

test('Reject incomplete, duplicate or inconsistent regional responses', async () => {
  for (const [list,page] of [
    [ids([1,2]),collection([way(1)])],
    [ids([1,2]),collection([way(1),way(1)])],
    [ids([1,2]),collection([way(1),way(2,{osm_id2:'51',maxspeed:'80'})])],
    [ids([1]),{...collection([way(1)]),exceededTransferLimit:true}],
    [ids([1]),collection([way(1,{}, {type:'MultiLineString',coordinates:[[]]})])],
    [ids([1]),{error:{code:498}}],
    [ids([1,1]),collection([])]
  ]) {
    const api = source(url => url.searchParams.get('returnIdsOnly') ? list : page);
    await assert.rejects(api.read(59.33,18.06,.9,api.region(59.33,18.06)));
  }
});
