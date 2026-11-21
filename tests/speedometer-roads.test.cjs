const assert = require('node:assert/strict');
const test = require('node:test');
const {createSpeedometer} = require('./speedometer-vm.cjs');

// All roads and GPS positions are synthetic. XY distances are in metres.
function point(x, y) {
  return {latitude: 63 + y / 111320, longitude: 7.7 + x / (111320 * Math.cos(63 * Math.PI / 180))};
}

function segment(id, a, b, {side = false, category = 'R', number = 70, start = 0, end = 1} = {}) {
  const points = [a, b].map(([x, y]) => point(x, y));
  const reference = {
    vegsystem: {vegkategori: category, fase: 'V', nummer: number},
    strekning: {strekning: 1, delstrekning: 1, trafikantgruppe: 'K', retning: 'MED'},
    kortform: category + 'V' + number + ' S1D1'
  };
  if (side) {
    reference.sideanlegg = {sideanlegg: 1001, sideanleggsdel: 1, trafikantgruppe: 'K', retning: 'MED'};
    reference.kortform += ' m100 SD1 m0-100';
  }
  return {
    veglenkesekvensid: id, startposisjon: start, sluttposisjon: end,
    vegsystemreferanse: reference, retning: 'MED', typeVeg: 'Enkel bilveg',
    detaljnivå: 'Vegtrase og kjørebane', feltoversikt: ['1', '2'],
    kommune: 1505, fylke: 15,
    geometri: {srid: 4326, wkt: 'LINESTRING Z (' + points.map(p => p.latitude + ' ' + p.longitude + ' 4').join(',') + ')'}
  };
}

function limit(id, value, ...segments) {
  return {
    id,
    egenskaper: [{id: 2021, navn: 'Fartsgrense', verdi: value, egenskapstype: 'Heltallenum'}],
    lokasjon: {vegsystemreferanser: segments.map(s => s.vegsystemreferanse)},
    vegsegmenter: segments
  };
}

async function load(roads, limits, delay = Promise.resolve()) {
  const unexpectedRequests = [];
  const app = await createSpeedometer(async url => {
    const {pathname} = new URL(url);
    let data;
    if (pathname.includes('/kommuneinfo/')) data = {fylkesnummer: '15'};
    else if (pathname.includes('/vegobjekter/105')) {
      await delay;
      data = {objekter: limits, metadata: {returnert: limits.length}};
    } else if (pathname.includes('/veglenkesekvenser/segmentert')) {
      data = {objekter: roads, metadata: {returnert: roads.length}};
    } else {
      unexpectedRequests.push(pathname);
      throw new Error('Unexpected request: ' + pathname);
    }
    return {ok: true, json: async () => data};
  });
  async function drive(x, y, options) {
    app.fix({...point(x, y), ...options});
    await app.idle();
    assert.deepEqual(unexpectedRequests, []);
    return app.sign();
  }
  return {...app, drive};
}

const main = segment(101, [-100, 0], [100, 0]);
const parallel = segment(102, [-100, 12], [100, 12], {side: true});
const turn = segment(103, [0, 0], [0, 100], {category: 'K', number: 1200});

test('parallel sideanlegg and main road show their own limits despite sharing a road number', async () => {
  for (const y of [0, 12]) {
    const app = await load([main, parallel], [limit(1, 80, main), limit(2, 30, parallel)]);
    assert.equal(await app.drive(-40, y, {heading: 90}), y ? '30' : '80');
  }
});

test('an unregistered side-road limit never borrows the main-road sign', async () => {
  const app = await load([main, parallel], [limit(1, 80, main)]);
  assert.equal(await app.drive(35, 12, {heading: 90}), '--');
  assert.match(app.road(), /rv\s*70/i);
});

test('at a cold start between parallel roads, reversing the API order cannot choose a sign', async () => {
  for (const reverse of [false, true]) {
    const roads = [main, parallel];
    const limits = [limit(1, 80, main), limit(2, 30, parallel)];
    if (reverse) { roads.reverse(); limits.reverse(); }
    const app = await load(roads, limits);
    assert.equal(await app.drive(-50, 6, {accuracy: 9, heading: null}), '--');
  }
});

test('passing a junction keeps the through-road sign, then turning picks the side-road sign', async () => {
  const app = await load([main, turn], [limit(1, 80, main), limit(2, 30, turn)]);
  assert.equal(await app.drive(-40, 0, {heading: 90}), '80');
  assert.equal(await app.drive(0, 0, {heading: 90}), '80');
  assert.equal(await app.drive(0, 30, {heading: null}), '30');
  assert.match(app.road(), /kv\s*1200/i);
});

test('a reported northbound course of zero degrees is usable on the first intersection fix', async () => {
  const app = await load([main, turn], [limit(1, 80, main), limit(2, 30, turn)]);
  assert.equal(await app.drive(0, 0, {heading: 0}), '30');
});

test('limits on the same road link end at the registered position, including a gap', async () => {
  const before = segment(101, [-100, 0], [-10, 0], {end: 0.45});
  const after = segment(101, [10, 0], [100, 0], {start: 0.55});
  const app = await load([main], [limit(1, 80, before), limit(2, 50, after)]);
  assert.equal(await app.drive(-20, 0, {heading: 90}), '80');
  assert.equal(await app.drive(0, 0, {heading: 90}), '--');
  assert.equal(await app.drive(20, 0, {heading: 90}), '50');
});

test('after driving onto a side road during the lookup, the first response uses the latest fix', async () => {
  let release;
  const delay = new Promise(resolve => { release = resolve; });
  const app = await load([main, turn], [limit(1, 80, main), limit(2, 30, turn)], delay);
  await app.drive(-40, 0, {heading: 90});
  await app.drive(0, 30, {heading: 0});
  release();
  await app.idle();
  assert.equal(app.sign(), '30');
  assert.match(app.road(), /kv\s*1200/i);
});

test('a stationary fix 20 m from a single covered road displays its limit', async () => {
  const app = await load([main], [limit(1, 80, main)]);
  assert.equal(await app.drive(0, 20, {accuracy: 6, speed: 0, heading: null}), '80');
});

test('a side-road decision number cannot be used as a speed limit', async () => {
  const decisionOnly = limit(2, null, parallel);
  decisionOnly.egenskaper = [{id: 1891, navn: 'Vedtaksnummer', verdi: '50'}];
  const app = await load([main, parallel], [limit(1, 80, main), decisionOnly]);
  assert.equal(await app.drive(35, 12, {heading: 90}), '--');
});

test('an object spanning several roads uses the reference of each speed-limit segment', async () => {
  const street = segment(104, [-100, 12], [100, 12], {category: 'K', number: 1200});
  const farRv = segment(105, [-350, -40], [-260, -40]);
  const farKv = segment(106, [-350, 40], [-260, 40], {category: 'K', number: 1200});
  for (const [y, sign, road] of [[0, '80', /rv\s*70/i], [12, '30', /kv\s*1200/i]]) {
    const app = await load(
      [main, street, farRv, farKv],
      [limit(1, 80, farKv, main), limit(2, 30, farRv, street)]
    );
    assert.equal(await app.drive(-25, y, {heading: 90}), sign);
    assert.match(app.road(), road);
  }
});

test('a single imprecise fix drifting toward a parallel side road cannot flash its sign', async () => {
  const app = await load([main, parallel], [limit(1, 80, main), limit(2, 30, parallel)]);
  assert.equal(await app.drive(-75, 0, {heading: 90}), '80');
  assert.notEqual(await app.drive(-50, 7, {accuracy: 10, heading: 90}), '30');
  assert.equal(await app.drive(-25, 0, {heading: 90}), '80');
});

test('leaving all mapped roads clears both the previous sign and its road label', async () => {
  const app = await load([main], [limit(1, 80, main)]);
  assert.equal(await app.drive(0, 0, {heading: 90}), '80');
  assert.equal(await app.drive(0, 90, {heading: null}), '--');
  assert.equal(app.road(), 'Veg ukjent');
});

test('lane-specific limits require a distinguishable direction and a single speed for that direction', async () => {
  const single = lane => ({...main, kjørefelt: [lane]});
  const twoLanes = [limit(1, 80, single('1')), limit(2, 70, single('2'))];
  for (const [heading, sign] of [[90, '80'], [270, '70'], [null, '--']]) {
    const app = await load([main], twoLanes);
    assert.equal(await app.drive(0, 0, {heading}), sign, 'heading ' + heading);
  }

  const threeLaneRoad = {...main, feltoversikt: ['1', '2', '3']};
  const restricted = (id, speed, lane) => limit(id, speed, {...threeLaneRoad, kjørefelt: [lane]});
  const app = await load([threeLaneRoad], [restricted(1, 80, '1'), restricted(2, 70, '2'), restricted(3, 60, '3')]);
  assert.equal(await app.drive(0, 0, {heading: 90}), '--');
});

test('a missing GPS speed leaves the measured speed unknown without hiding the road limit', async () => {
  const app = await load([main], [limit(1, 80, main)]);
  assert.equal(await app.drive(0, 0, {speed: null}), '80');
  assert.equal(app.speed(), '--');
  assert.equal(app.message(), 'Fart ukjent');
  await app.drive(0, 0, {speed: 0});
  assert.equal(app.speed(), '0');
});
