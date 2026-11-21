const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../docs/speed.html'), 'utf8');
const script = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)]
  .map(match => match[1]).find(source => source.includes('function startGPS('));
const roads = [{source: 'osm', label: 'Example road', parts: [[[103.7, 16.1], [103.71, 16.1]]],
  speed: 80, speedForward: 80, speedBackward: 80}];

function cache(indexedDB) {
  const clock = {time: 1_800_000_000_000};
  const element = {addEventListener() {}};
  const context = vm.createContext({
    indexedDB, setTimeout, clearTimeout, Date: class extends Date {static now() {return clock.time;}},
    window: element, document: {addEventListener() {}, getElementById: () => element, querySelectorAll: () => []}
  });
  vm.runInContext(script, context);
  return {
    write: (options = {}, radius = 0.9) => context.writeOsmArea({lat: 16.1, lon: 103.7, roads, ...options}, radius),
    read: (lat = 16.1, lon = 103.7, radius = 0.9) => context.readOsmArea(lat, lon, radius),
    clock
  };
}

test('an OSM cache hit is local to the actual lookup centre and radius', async () => {
  const app = cache();
  await app.write();
  assert.equal((await app.read(16.1026)).roads[0].speed, 80);
  assert.equal(await app.read(16.1028), null);
  assert.equal(await app.read(16.1, 103.7, 1.5), null);
  const raw = cache();
  await raw.write({lat: 16.10049});
  assert.equal((await raw.read()).lat, 16.1);
  assert.equal(await raw.read(16.0977), null);
});

test('prefer a complete OSM response over a later general source until expiry', async () => {
  const app = cache();
  await app.write();
  const first = await app.read();
  app.clock.time += 10_000;
  await app.write({generalOnly: true});
  assert.equal((await app.read()).generalOnly, false);
  assert.equal((await app.read()).savedAt, first.savedAt);
  await app.write({lat: 16.101, generalOnly: true});
  assert.equal((await app.read(16.101)).generalOnly, false);
  app.clock.time = first.savedAt + 12 * 3600_000;
  assert.equal(await app.read(), null);
  await app.write({generalOnly: true});
  assert.equal((await app.read()).generalOnly, true);
  app.clock.time += 2 * 3600_000;
  assert.equal(await app.read(), null);
  await app.write({savedAt: app.clock.time + 10_000});
  assert.equal(await app.read(), null);
});

test('unavailable device storage still retains a bounded number of areas in memory', async () => {
  const app = cache({open() {throw new Error('storage denied');}});
  for (let i = 0; i < 9; i++) {
    app.clock.time += 1_000;
    await app.write({lat: 16.1 + i * .05});
  }
  assert.equal(await app.read(), null);
  assert.equal((await app.read(16.5)).roads[0].label, 'Example road');
  await app.write({lat: 17, roads: Array(1501).fill(roads[0])});
  await app.write({lat: 18, roads: [{parts: [Array(24001).fill([103.7, 16.1])]}]});
  assert.equal(await app.read(17), null);
  assert.equal(await app.read(18), null);
});
