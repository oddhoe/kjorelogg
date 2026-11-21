const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../docs/speed.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

function lookup(reply) {
  const context = {
    URL, AbortController, setTimeout, clearTimeout,
    fetch: async (url, options) => ({ok: true, json: async () => reply(url, options)}),
    window: {addEventListener() {}},
    document: {getElementById: () => ({addEventListener() {}}), querySelectorAll: () => [], addEventListener() {}}
  };
  return vm.runInNewContext(script + '\n;fetchPostpassRoads', context);
}

const coords = [[-.129, 51.51], [-.128, 51.51]];
const line = {type: 'LineString', coordinates: coords};
function feature(id, count, tags = {}, geometry = line) {
  return {type: 'Feature', geometry, properties: {
    osm_id: id, area_count: count, tags: {highway: 'residential', ...tags}
  }};
}
const collection = features => ({type: 'FeatureCollection', features});

test('Postpass fetches the same area for tagged and untagged ways and keeps the OSM node order', async () => {
  const parts = [coords, [[-.128, 51.51], [-.127, 51.51]]];
  const read = lookup((url, options) => {
    assert.equal(url, 'https://postpass.geofabrik.de/api/interpreter');
    assert.equal(options.referrerPolicy, 'strict-origin');
    assert.equal(options.method, 'POST');
    const sql = new URLSearchParams(options.body).get('data');
    assert.match(sql, /ST_Intersects\(geom,ST_MakeEnvelope\(/);
    assert.match(sql, /osm_type='W'/);
    assert.doesNotMatch(sql, /\bLIMIT\b|ST_Intersection\(/i);
    return collection([
      feature(1, 3, {'maxspeed:forward': '20 mph', 'maxspeed:backward': '30 mph'}, {type:'MultiLineString', coordinates:parts}),
      feature(2, 3, {name:'Side Road'}), feature(3, 3, {motorcar:'no'})
    ]);
  });
  const roads = await read(51.51, -.128, .4);
  assert.equal(roads.length, 2);
  assert.equal(JSON.stringify(roads[0].parts), JSON.stringify(parts));
  assert.equal(roads[0].speedForward, 32);
  assert.equal(roads[0].speedBackward, 48);
  assert.equal(roads[1].label, 'Side Road');
  assert.equal(roads[1].speed, null);
});

test('Postpass rejects a partial or malformed road set, including duplicate ways', async () => {
  for (const reply of [
    {type:'FeatureCollection', features:null}, collection([feature(1, 2)]),
    collection([feature(1, 2), feature(1, 2)]), collection([feature(-1, 1)]),
    collection([feature(1, 1, {}, {type:'Polygon', coordinates:[coords]})]),
    collection([feature(1, 1, {}, {type:'LineString', coordinates:[coords[0],[200,12]]})])
  ]) await assert.rejects(lookup(() => reply)(51.51, -.128, .4), /Ufullstendig/);
});

test('Postpass wraps a dateline query and refuses invalid coordinates before making a request', async () => {
  let calls = 0;
  const read = lookup((url, options) => {
    calls++;
    const sql = new URLSearchParams(options.body).get('data');
    assert.equal(sql.match(/ST_Intersects\(/g).length, 2);
    return collection([]);
  });
  assert.equal((await read(0, 179.999, .4)).length, 0);
  await assert.rejects(read(NaN, 10, .4), /Ugyldig/);
  await assert.rejects(read(5, 181, .4), /Ugyldig/);
  await assert.rejects(read(5, '10', .4), /Ugyldig/);
  assert.equal(calls, 1);
});
