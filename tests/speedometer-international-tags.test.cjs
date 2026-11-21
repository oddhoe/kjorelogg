const assert = require('node:assert/strict');
const test = require('node:test');
const {createSpeedometer} = require('./speedometer-vm.cjs');

// Coordinates anchor each example. All OSM tags and road geometry here are synthetic.
async function signAt([latitude, longitude], tags, heading = 90) {
  const road = {id: 1, type: 'way', tags: {highway: 'primary', name: 'Test', ...tags},
    geometry: [{lat: latitude, lon: longitude - .001}, {lat: latitude, lon: longitude + .001}]};
  const app = await createSpeedometer(async url => {
    if (String(url).includes('vegvesen.no')) return {ok: true, json: async () => ({objekter: [], metadata: {returnert: 0}})};
    assert.match(String(url), /overpass/);
    return {ok: true, json: async () => ({elements: [road]})};
  });
  app.fix({latitude, longitude, heading});
  await app.idle();
  return app.sign();
}

const oslo = [59.91, 10.75], stockholm = [59.33, 18.06], copenhagen = [55.68, 12.57];
const vienna = [48.21, 16.37], london = [51.51, -.12], roiEt = [16.05, 103.65];

test('Explicit OSM country codes describe the selected road, and a posted value takes precedence', async () => {
  for (const [point, tags, sign] of [
    [oslo, {maxspeed: 'NO:rural'}, '80'],
    [stockholm, {'source:maxspeed': 'SE:rural'}, '70'],
    [copenhagen, {'maxspeed:type': 'DK:urban'}, '50'],
    [vienna, {maxspeed: 'AT:rural'}, '100'],
    [london, {'maxspeed:type': 'GB:nsl_single'}, '97'],
    [stockholm, {maxspeed: '40', 'source:maxspeed': 'SE:rural'}, '40'],
    [stockholm, {maxspeed: 'signals', 'source:maxspeed': 'SE:rural'}, '--'],
    [london, {'maxspeed:type': 'GB:nsl_restricted'}, '--']
  ]) assert.equal(await signAt(point, tags), sign, JSON.stringify(tags));
});

test('Thai car limits can differ from general and motorcycle limits; an untagged road stays unknown', async () => {
  const tags = {maxspeed: '80', 'maxspeed:motorcar': '90', 'maxspeed:motorcycle': '60'};
  assert.equal(await signAt(roiEt, tags), '90');
  assert.equal(await signAt(roiEt, {...tags, 'maxspeed:forward': '60'}), '--');
  assert.equal(await signAt(roiEt, {...tags, 'maxspeed:motorcar:forward': '100 kph'}), '100');
  assert.equal(await signAt(roiEt, {'maxspeed:motorcycle': '60'}), '--');
  assert.equal(await signAt(roiEt, {'maxspeed:type': 'TH:rural'}), '--');
  assert.equal(await signAt(roiEt, {}), '--');
});

test('A lane-dependent limit needs agreement for every lane in the driving direction', async () => {
  const tags = {maxspeed: '80', 'maxspeed:lanes:forward': '|60', 'maxspeed:lanes:backward': '|80'};
  assert.equal(await signAt(roiEt, tags, 90), '--');
  assert.equal(await signAt(roiEt, tags, 270), '80');
  assert.equal(await signAt(roiEt, {'maxspeed:lanes': '50|50'}), '50');
  assert.equal(await signAt(roiEt, {maxspeed: '90', 'maxspeed:motorcar:conditional': '60 @ (wet)'}), '--');
});

test('GPS course distinguishes two parallel one-way carriageways, including reverse OSM ways', async () => {
  const [lat, lon] = roiEt;
  const elements = ['yes', '-1'].map((oneway, i) => ({
    type: 'way', id: i + 1, tags: {highway: 'primary', oneway, maxspeed: i ? '60' : '80'},
    geometry: [{lat: lat + .00004 * i, lon: lon - .001}, {lat: lat + .00004 * i, lon: lon + .001}]
  }));
  const app = await createSpeedometer(async url => {
    if (!String(url).includes('overpass')) return {ok: false, status: 503};
    return {ok: true, json: async () => ({elements})};
  });
  for (const [heading, expected] of [[90, '80'], [270, '60'], [null, '--']]) {
    app.fix({latitude: lat + .00002, longitude: lon, speed: 12, accuracy: 5, heading});
    await app.idle();
    assert.equal(app.sign(), expected);
  }
});
