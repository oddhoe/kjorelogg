const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');

const {createAppContext} = require('./app-vm.cjs');

const key = 'Fv64_S1D1';
const routeStore = 'mr_veg_route_log_v1';
const commentStore = 'mr_veg_road_comments_v1';
const settingsStore = 'mr_veg_settings_v3';

function oldStorage() {
  const values = {
    [settingsStore]: {settingsVersion: 6},
    mr_veg_nvdb_state: {driven: [key]},
    mr_veg_dir_state_v1: {[key]: {fwd: true, rev: true}},
    [routeStore]: {[key]: {fwd: [[2, 62, 7], [3, 62.01, 7.01]]}},
    [commentStore]: {[key]: {text: 'testkommentar', ts: 5}},
    mr_veg_geom: {[key]: [[[7, 62], [7.01, 62.01]]]}
  };
  return new Map(Object.entries(values).map(([name, value]) => [name, JSON.stringify(value)]));
}

async function openApp(local, database, mode) {
  const context = createAppContext({
    console: {log() {}, warn() {}, error() {}},
    setTimeout: () => 1, clearTimeout() {}, setInterval: () => 1, clearInterval() {},
    localStorage: {getItem: k => local.get(k) ?? null, setItem: (k, v) => local.set(k, v), removeItem: k => local.delete(k)},
    indexedDB: mode === 'no-indexeddb' ? undefined : {},
    read: async k => {
      if (mode === 'failed-read') throw Error('Simulert lesefeil');
      return structuredClone(database.get(k));
    },
    write: async (k, value) => {
      if (mode === 'failed-write' && [routeStore, 'mr_veg_geom_v2'].includes(k)) return false;
      database.set(k, {value: structuredClone(value), ts: Date.now()});
      return true;
    },
    road: key
  });
  return vm.runInContext(`(async () => {
    idbGetAppDataRecord = read;
    idbGetAppData = async k => (await read(k))?.value ?? null;
    idbSetAppData = write;
    loadSettings();
    await loadPersistentAppState();
    return [drivenKeys.has(road), directionState[road]?.rev, routeLog[road]?.fwd.length,
            geomCache[road]?.parts.length, roadComments[road]?.text ?? null];
  })()`, context);
}

for (const scenario of ['new-indexeddb', 'failed-read', 'failed-write', 'existing-indexeddb', 'no-indexeddb']) {
  test('Legacy progress migration / ' + scenario, async () => {
    const local = oldStorage(), database = new Map();
    // An intentionally cleared IDB store takes precedence over an older local value.
    if (scenario === 'existing-indexeddb') database.set(commentStore, {ts: 100, value: {}});
    for (let attempt = 0; attempt < 2; attempt++) {
      const mode = attempt === 1 && scenario.startsWith('failed-') ? 'new-indexeddb' : scenario;
      if (mode === 'failed-read') {
        await assert.rejects(openApp(local, database, mode), /Simulert lesefeil/);
      } else {
        const data = await openApp(local, database, mode);
        const comment = scenario === 'existing-indexeddb' ? null : 'testkommentar';
        assert.deepEqual(Array.from(data), [true, true, 2, 1, comment]);
      }
      const complete = ['new-indexeddb', 'existing-indexeddb'].includes(mode);
      assert.equal(local.has(routeStore), !complete);
      assert.equal(local.has('mr_veg_geom'), !complete);
      assert.equal(JSON.parse(local.get(settingsStore)).settingsVersion, complete ? 7 : 6);
    }
  });
}

test('Progress migrates even when the legacy settings key is missing', async () => {
  const local = oldStorage(), database = new Map();
  local.delete(settingsStore);
  const data = await openApp(local, database, 'new-indexeddb');
  assert.deepEqual(Array.from(data), [true, true, 2, 1, 'testkommentar']);
  assert.equal(JSON.parse(local.get(settingsStore)).settingsVersion, 7);
});
