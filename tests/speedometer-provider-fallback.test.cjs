const assert = require('node:assert/strict');
const test = require('node:test');
const {createSpeedometer} = require('./speedometer-vm.cjs');

const fix = {latitude: 16.05, longitude: 103.65, speed: 25, heading: 90};
const coordinates = [[103.649,16.05],[103.651,16.05]];
const wayId = 7531;
const json = data => ({ok: true, json: async () => data});
const unavailable = () => ({ok: false, status: 503});
const feature = properties => ({type: 'Feature', geometry: {type: 'LineString', coordinates}, properties});

function regional(url) {
  return json(url.searchParams.get('returnIdsOnly')
    ? {objectIdFieldName: 'objectid', objectIds: [1]}
    : {type: 'FeatureCollection', features: [feature({
      objectid: 1, osm_id2: String(wayId), highway: 'primary', name: 'Regional', maxspeed: '50'
    })]});
}
function overpass(tags) {
  return json({elements: [{id: wayId, type: 'way', tags: {highway: 'primary', name: 'Raw', ...tags},
    geometry: coordinates.map(([lon,lat]) => ({lon,lat}))}]});
}
function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return {promise, resolve};
}

async function drive({post = unavailable, raw = unavailable, region = regional} = {}) {
  const calls = [];
  const app = await createSpeedometer(async input => {
    const url = new URL(input), host = url.hostname;
    calls.push(host);
    if (host === 'postpass.geofabrik.de') return post(url);
    if (host.startsWith('overpass.')) return raw(url);
    if (host.startsWith('services-ap1.')) return region(url);
    if (host === 'ws.geonorge.no') return json({navn: []});
    if (host === 'services.kystverket.no') return {ok: true, text: async () => ''};
    throw new Error('Unexpected test endpoint: ' + host);
  });
  app.fix(fix);
  await app.idle();
  return {app, calls};
}

function checkRegional(app) {
  assert.equal(app.sign(), '50');
  assert.equal(app.message(), 'Kartverdi · vilkår ukjent');
  assert.equal(app.hasClass('speedSign', 'general-limit'), true);
  assert.equal(app.hasClass('speedSign', 'blink'), false);
  assert.equal(app.hasClass('speed', 'danger'), false);
}

test('A regional road with only the general tag has no speeding warning at 90 km/h', async () => {
  const {app} = await drive();
  checkRegional(app);
});

test('Later complete tags replace the regional value, including an unknown conditional limit', async () => {
  for (const [tags, sign, warning] of [
    [{maxspeed: '60'}, '60', true], [{maxspeed:'60','maxspeed:conditional':'40 @ (wet)'}, '--', false]
  ]) {
    const pending = deferred();
    const {app} = await drive({raw: () => pending.promise});
    checkRegional(app);
    pending.resolve(overpass(tags));
    await app.idle();
    assert.equal(app.road(), 'Raw');
    assert.equal(app.sign(), sign);
    assert.equal(app.hasClass('speedSign', 'general-limit'), false);
    assert.equal(app.hasClass('speedSign', 'blink'), warning);
    assert.equal(app.hasClass('speed', 'danger'), warning);
  }
});

test('Late complete tags from an abandoned road session cannot replace the current result', async () => {
  const pending = deferred();
  const {app} = await drive({raw: () => pending.promise});
  checkRegional(app);
  app.chooseUnit('knots');
  await app.idle();
  assert.equal(app.sign(), 'KN');
  app.chooseUnit('kmh');
  await app.idle();
  checkRegional(app);
  pending.resolve(overpass({maxspeed:'60'}));
  await app.idle();
  checkRegional(app);
  assert.equal(app.road(), 'Regional');
});

test('Failure of every source without a cached area reports unavailable road data', async () => {
  const {app} = await drive({region: unavailable});
  assert.equal(app.sign(), '--');
  assert.equal(app.message(), 'Vegdata utilgjengelige');
});

test('A successful complete Postpass area needs no other road provider', async () => {
  const {app, calls} = await drive({post: () => json({type:'FeatureCollection', features:[feature({
    area_count:1, osm_id:wayId, tags:{highway:'primary',name:'Postpass',maxspeed:'70'}
  })]})});
  assert.deepEqual(calls, ['postpass.geofabrik.de']);
  assert.equal(app.road(), 'Postpass');
  assert.equal(app.sign(), '70');
  assert.equal(app.hasClass('speedSign','general-limit'), false);
  assert.equal(app.hasClass('speedSign','blink'), true);
});
