const assert = require('node:assert/strict');
const test = require('node:test');
const {createSpeedometer} = require('./speedometer-vm.cjs');

const latitude = 51.5;
const longitude = -0.125;
function way(id, lat, tags) {
  return {type: 'way', id, tags: {highway: 'residential', ...tags},
    geometry: [{lat, lon: -0.130}, {lat, lon: -0.120}]};
}

async function start(ways) {
  const queries = [];
  const app = await createSpeedometer(async (url, options) => {
    if (String(url).includes('kommuneinfo')) return {ok: true, json: async () => ({})};
    assert.match(String(url), /overpass/);
    queries.push(new URLSearchParams(options.body).get('data'));
    return {ok: true, json: async () => ({elements: ways})};
  });
  return {...app, queries};
}

test('An untagged OSM side road keeps its own identity and no sign', async () => {
  const sideLatitude = latitude + .00018;
  const app = await start([
    way(1, latitude, {ref: 'A1', maxspeed: '40 mph'}),
    way(2, sideLatitude, {name: 'Side Road', 'destination:ref': 'A1'}),
    way(3, sideLatitude, {highway: 'cycleway', name: 'Cycle Lane', maxspeed: '20'})
  ]);
  app.fix({latitude, longitude, heading: 90});
  await app.idle();
  assert.equal(app.sign(), '64');
  app.fix({latitude: sideLatitude, longitude, heading: 90});
  assert.equal(app.sign(), '--');
  assert.equal(app.road(), 'Side Road');
  assert.equal(app.queries.length, 1);
  assert.doesNotMatch(app.queries[0], /\["maxspeed"\]/);
});

test('OSM direction-specific limits follow the order of way coordinates', async () => {
  const app = await start([way(1, latitude, {name: 'Two Way', maxspeed: '60',
    'maxspeed:forward': '30', 'maxspeed:backward': '40 mph'})]);
  app.fix({latitude, longitude, heading: 90});
  await app.idle();
  assert.equal(app.sign(), '30');
  app.fix({latitude, longitude, heading: 270});
  assert.equal(app.sign(), '64');
  app.fix({latitude, longitude, heading: null, speed: 0});
  assert.equal(app.sign(), '--');
});

test('Conditional and compound OSM values do not produce a guessed speed', async () => {
  for (const tags of [
    {maxspeed: '30;50'}, {maxspeed: '40 @ (wet)'},
    {maxspeed: '60', 'maxspeed:conditional': '30 @ (wet)'},
    {maxspeed: '60', 'maxspeed:variable': 'yes'}
  ]) {
    const app = await start([way(1, latitude, {name: 'Test Road', ...tags})]);
    app.fix({latitude, longitude, heading: 90});
    await app.idle();
    assert.equal(app.sign(), '--');
    assert.equal(app.road(), 'Test Road');
  }
});

async function borderLookup(countryStatus, offsetMetres) {
  // Both countries' synthetic roads fit in the same 900 m query area.
  const lat = 59.09, lon = 11.27, roadLat = lat + offsetMetres / 111320;
  const segment = {
    veglenkesekvensid: 1001, startposisjon: 0, sluttposisjon: 1,
    vegsystemreferanse: {vegsystem: {vegkategori: 'E', fase: 'V', nummer: 6}},
    geometri: {srid: 4326, wkt: `LINESTRING (${roadLat} ${lon - .002},${roadLat} ${lon + .002})`}
  };
  const osm = {type: 'way', id: 2001, tags: {highway: 'residential', name: 'Sidovägen', maxspeed: '30'},
    geometry: [{lat, lon: lon - .002}, {lat, lon: lon + .002}]};
  const app = await createSpeedometer(async url => {
    const {hostname, pathname} = new URL(url);
    if (pathname.includes('/kommuneinfo/')) return {ok: false, status: countryStatus};
    if (hostname.includes('overpass')) return {ok: true, json: async () => ({elements: [osm]})};
    assert.match(pathname, /vegobjekter\/105|veglenkesekvenser\/segmentert/);
    const limit = {id: 3001, egenskaper: [{id: 2021, verdi: 80}], vegsegmenter: [segment]};
    return {ok: true, json: async () => ({objekter: [pathname.includes('vegobjekter') ? limit : segment]})};
  });
  app.fix({latitude: lat, longitude: lon, heading: 90});
  await app.idle();
  return [app.road(), app.sign()];
}

test('A Swedish fix uses OSM even when the NVDB search area includes a Norwegian road', async () => {
  assert.deepEqual(await borderLookup(404, 20), ['Sidovägen', '30']);
});

test('A municipality lookup outage still allows an available NVDB road and limit', async () => {
  assert.deepEqual(await borderLookup(503, 0), ['E6', '80']);
});
