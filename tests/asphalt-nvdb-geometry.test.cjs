const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const {createAppContext} = require('./app-vm.cjs');

function appWithSegments(objects, globals = {}) {
  return createAppContext({
    URL, fetch: async () => ({ok: true, json: async () => ({objekter: objects})}),
    ...globals
  });
}

function segment(wkt, direction, from, to) {
  return {
    geometri: {wkt}, typeVeg: 'Enkel bilveg',
    vegsystemreferanse: {
      vegsystem: {vegkategori: 'F', nummer: 64},
      strekning: {strekning: 8, delstrekning: 1, trafikantgruppe: 'K',
        retning: direction, fra_meter: from, til_meter: to}
    }
  };
}

async function match(objects, from, to) {
  const app = appWithSegments(objects);
  const segments = await app.fetchAsphaltNvdbRoad(64, '15');
  return app.matchAsphaltRecordToNvdb({fraS: 8, tilS: 8, fraD: 1, tilD: 1,
    fraM: from, tilM: to}, segments);
}

// Statens vegvesen, NVDB Les V4, 2026-11-19. Adjoining segments 225821-7-8 and 239045-1-9.
const before = segment('LINESTRING Z (62.78194166 7.24631743 140.045,62.78264646 7.24486048 138.931)', 'MED', 2626.089, 2734.438);
const after = segment('LINESTRING Z (62.78811682 7.23687719 127.533,62.78773296 7.23724485 129.033,62.78664055 7.23837348 130.832,62.78610344 7.2389393 131.832,62.78577789 7.23931709 132.432,62.78547843 7.23970964 132.832,62.78518403 7.24012843 133.332,62.78491595 7.24055009 133.832,62.78467332 7.24097487 134.332,62.78419495 7.24188366 135.231,62.78264646 7.24486048 138.931)', 'MOT', 2734.438, 3474.84);

test('FV64 S8D1 crosses from MED to MOT at the same map coordinate', async () => {
  const job = await match([before, after], 2724.438, 2744.438);
  assert.equal(job.matchCount, 2);
  assert.deepEqual([...job.parts[0].at(-1)], [7.24486048, 62.78264646]);
  assert.deepEqual([...job.parts[1][0]], [7.24486048, 62.78264646]);
  assert.ok(job.matchKm > 0.019 && job.matchKm < 0.021);
});

test('A partial interval is applied once across disjoint geometry parts', async () => {
  const road = segment('MULTILINESTRING ((62 7,62 7.01),(62 7.02,62 7.03))', 'MOT', 0, 100);
  const job = await match([road], 25, 0);
  assert.equal(job.parts.length, 1);
  assert.deepEqual([...job.parts[0][0]], [7.03, 62]);
  assert.ok(Math.abs(job.parts[0].at(-1)[0] - 7.025) < 1e-8);
});

for (const [name, from, to] of [['forward', 3464.84, 3474.84], ['reverse', 3474.84, 3464.84]]) {
  test('High-meter end of the MOT segment, Excel interval ' + name, async () => {
    const job = await match([after], from, to);
    assert.equal(job.matchCount, 1);
    assert.deepEqual([...job.parts[0].at(-1)], [7.23687719, 62.78811682]);
    assert.ok(job.matchKm > 0.0095 && job.matchKm < 0.0105);
  });
}

test('Reimport of the same asphalt row corrects its geometry and keeps the manual status', async () => {
  const local = new Map();
  const app = appWithSegments([before, after], {
    setTimeout: () => 1, clearTimeout() {},
    console: {log() {}, table() {}, warn() {}, error() {}},
    localStorage: {getItem: k => local.get(k) ?? null, setItem: (k, v) => local.set(k, v), removeItem: k => local.delete(k)},
    planRow: {id: 'plan.xlsx:2:FV64', nr: 64, countyId: '15', source: 'plan.xlsx',
      fraS: 8, tilS: 8, fraD: 1, tilD: 1, fraM: 2724.438, tilM: 2744.438}
  });
  vm.runInContext(`
    asphaltPlan = normalizeAsphaltPlan([{...planRow, parts: [[[7, 62], [7.1, 62]]],
      manualStatus: 'deferred', manualStatusTs: 12345}]);
    ensureXlsxReady = async () => true;
    parseAsphaltWorkbook = () => ({format: 'MRFK', records: [{...planRow}], issues: [],
      summary: {columnA: {}, statusDiagnostics: []}});
    setMessage = applySettingsToUI = updateProgressMap = () => {};
  `, app);
  await app.importAsphaltExcelFile({name: 'plan.xlsx', arrayBuffer: async () => new ArrayBuffer(0)});
  const saved = JSON.parse(local.get('mr_veg_asphalt_plan_v1'));
  assert.equal(saved.length, 1);
  assert.equal(saved[0].manualStatus, 'deferred');
  assert.equal(saved[0].manualStatusTs, 12345);
  assert.deepEqual(saved[0].parts[1][0], [7.24486048, 62.78264646]);
});
