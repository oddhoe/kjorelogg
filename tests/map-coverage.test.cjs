const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');

const {createAppContext} = require('./app-vm.cjs');

function run(scenario) {
  const context = createAppContext({assert});
  vm.runInContext(scenario, context);
}

test('Geometry is built only for roads with a track or manual coverage', () => run(`
  const road = i => ({
    key: 'Fv' + i + '_S1D1', veg: 'Fv' + i, kat: 'F', seg: 'S1D1',
    parts: [[[7.20,62.7],[7.205,62.7]], [[7.22,62.7],[7.225,62.7]]]
  });
  roads = Array.from({length: 500}, (_, i) => road(i));
  const build = makeChainsFromParts;
  let builds = 0;
  makeChainsFromParts = (...args) => { builds++; return build(...args); };
  for (const r of roads) assert.equal(getCoverageDrawPlans(r.key).length, 0);
  assert.equal(builds, 0);

  const key = roads[0].key;
  directionState[key] = {fwd:true, rev:true};
  const manual = getCoverageDrawPlans(key);
  assert.equal(manual.length, 2);
  assert.ok(manual.every(plan => plan.manualFull && plan.bothKm > 0));
  routeLog[key] = {fwd:[{ts:1,lat:62.7,lon:7.22},{ts:1001,lat:62.7,lon:7.224}], rev:[]};
  builds = 0;
  const plans = getCoverageDrawPlans(key);
  const summary = getCoverageDrawPlan(key, plans);
  assert.equal(plans[0].totalKm, 0);
  assert.ok(plans[1].totalKm > 0.2);
  assert.equal(summary.totalKm, plans[1].totalKm);
  assert.equal(getRoadStatus(key, plans), 'oneway');
  drawCoveragePlans(null, key, [], {drawOne:false, drawBoth:false}, plans);
  assert.equal(builds, 1);
`));

test('Panning refreshes the visible overlay and a pending redraw skips a hidden map tab', () => run(`
  const handlers = {};
  let nextJob, visible = true, redraws = 0;
  document.querySelector = () => ({id: visible ? 'tab-map' : 'tab-table'});
  document.getElementById = () => ({classList:{contains:() => visible}});
  window.L = {
    map: () => ({
      on(events, fn) { for (const name of events.split(' ')) handlers[name] = fn; },
      whenReady() {}
    }),
    canvas: () => ({}), tileLayer() {},
    layerGroup: () => ({addTo() { return this; }, clearLayers() { redraws++; }})
  };
  globalThis.L = window.L;
  setMapError = () => {};
  addBaseLayerControl = () => {};
  createBaseLayers = () => ({});
  mapRoadsToRender = () => [];
  setTimeout = fn => { nextJob = fn; return 1; };
  clearTimeout = () => { nextJob = null; };
  initMap();
  handlers.moveend();
  nextJob();
  assert.equal(redraws, 1);
  handlers.zoomend();
  visible = false;
  nextJob();
  assert.equal(redraws, 1);
`));

test('County radius search skips distant geometry and retains segments crossing the circle', () => run(`
  const near = {key:'near', parts:[[[7.1,62.7],[7.3,62.7]]]};
  const distant = Array.from({length:500}, (_, i) => ({
    key:'distant' + i, parts:[[[9,63],[9.01,63.01]]]
  }));
  const exact = roadDist;
  let calls = 0;
  roadDist = (...args) => { calls++; return exact(...args); };
  const results = applySearchRadiusView([...distant,near],62.7,7.2,1);
  assert.equal(results.length,1);
  assert.equal(results[0].key,'near');
  assert.ok(Math.abs(results[0].displayLen - 2000) < 10);
  assert.equal(calls,1);

  // Replacing the geometry must invalidate its previously computed bounds.
  const changed = distant[0];
  changed.parts = near.parts;
  assert.equal(applySearchRadiusView([changed],62.7,7.2,1).length,1);
`));

test('Successive GPS fixes reuse the heading chain until road geometry changes', () => run(`
  const road = {parts:[[[7.2,62.7],[7.205,62.7]]]};
  const build = makeChainsFromParts;
  let builds = 0;
  makeChainsFromParts = (...args) => { builds++; return build(...args); };
  for(let i=0;i<60;i++){
    const result = getRoadHeadingAtPoint(62.7,7.2 + i*0.00005,road,90);
    assert.ok(Math.abs(result.heading-90)<1);
  }
  assert.equal(builds,1);
  road.parts = [[[7.2,62.7],[7.2,62.71]]];
  assert.equal(getRoadHeadingAtPoint(62.7,7.2,road,0).heading,0);
  assert.equal(builds,2);
`));
