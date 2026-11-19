const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const {createAppContext} = require('./app-vm.cjs');

// Each case exercises the production functions with an isolated view, clock and transport.
function load(fetch) {
  const element = {addEventListener() {}, dataset: {}};
  const clock = {now: 100000};
  const context = createAppContext({
    document: {hidden: true, addEventListener() {}, querySelectorAll: () => [], getElementById: () => element},
    console: {log() {}, warn() {}, error() {}},
    URL, AbortController, fetch,
    Date: class extends Date { static now() { return clock.now; } }
  });
  return {run: code => vm.runInContext(code, context), clock};
}

function object(speed, lat = 63.1) {
  return {id: 1, egenskaper: [{id: 2021, navn: 'Fartsgrense', verdi: speed, enum_id: 2738}],
    geometri: {wkt: `LINESTRING Z (${lat} 7.70 20,${lat} 7.71 21)`}};
}

function response(objects, nextHref) {
  return {ok: true, json: async () => ({
    objekter: objects, metadata: {neste: nextHref ? {href: nextHref} : null}
  })};
}

test('Only the speed limit property can supply a sign value', () => {
  const {run} = load();
  for (const [data, expected] of [
    [object(80), 80], [{egenskaper: [{id: 1891, navn: 'Vedtaksnummer', verdi: '30'}]}, null],
    [object(2738), null], [{egenskaper: {2021: '110 km/t'}}, 110],
    [{egenskaper: [{id: 5156, navn: 'Variabel fartsgrense', verdi: 50}]}, null]
  ]) assert.equal(run(`getSpeedLimitFromObject(${JSON.stringify(data)})`), expected);
});

test('One nearby lookup serves repeated fixes and uses the newest GPS fix at completion', async () => {
  const requests = [];
  const {run} = load((url, options) => new Promise(resolve => requests.push({url, options, resolve})));
  const pending = run('refreshSpeedLimitsLight(63.1,7.705,true)');
  await run('refreshSpeedLimitsLight(63.101,7.705,true)');
  assert.equal(requests.length, 1);
  run('gps.watching=true; gps.lastPos=[63.101,7.705]');
  requests[0].resolve(response([object(50, 63.1), object(80, 63.101)]));
  await pending;
  assert.equal(run('currentSpeedLimit'), 80);
  await run('refreshSpeedLimitsLight(63.101,7.705)');
  assert.equal(requests.length, 1);
});

test('A superseded or pre-reset response cannot change the sign', async () => {
  const requests = [];
  const {run} = load((url, options) => new Promise(resolve => requests.push({options, resolve})));
  const first = run('refreshSpeedLimitsLight(63.1,7.705)');
  const second = run('refreshSpeedLimitsLight(63.2,7.705)');
  assert.ok(requests[0].options.signal.aborted);
  requests[1].resolve(response([object(80, 63.2)]));
  await second;
  requests[0].resolve(response([object(50)]));
  await first;
  assert.equal(run('currentSpeedLimit'), 80);
  const third = run('refreshSpeedLimitsLight(63.3,7.705)');
  run('++_dataGeneration');
  requests[2].resolve(response([object(60, 63.3)]));
  await third;
  assert.equal(run('currentSpeedLimit'), 80);
});

test('Failure on the next page keeps complete data and limits retries', async () => {
  const responses = [
    response([object(60)]),
    response([object(50)], 'https://example.test/next'),
    {ok: false, status: 503},
    response([])
  ];
  const {run, clock} = load(async () => responses.shift());
  await run('refreshSpeedLimitsLight(63.1,7.705)');
  await run('refreshSpeedLimitsLight(63.11,7.705)');
  assert.equal(run('updateCurrentSpeedLimit(63.1,7.705)'), 60);
  assert.equal(run('updateCurrentSpeedLimit(63.11,7.705)'), null);
  await run('refreshSpeedLimitsLight(63.11,7.705)');
  assert.equal(responses.length, 1);
  clock.now += 16000;
  await run('refreshSpeedLimitsLight(63.11,7.705)');
  assert.equal(responses.length, 0);
  assert.equal(run('speedLimits.length'), 0);
});

test('Far geometries are skipped before measuring precise distances', () => {
  const {run} = load();
  const objects = [object(70, 63.1), ...Array.from({length: 50}, (_, i) => object(50, 63.2 + i / 1000))];
  run(`speedLimits=${JSON.stringify(objects)}.map(normalizeSpeedLimitObject)`);
  run('let count=0;const original=roadDist;roadDist=(...args)=>{count++;return original(...args)}');
  assert.equal(run('updateCurrentSpeedLimit(63.1,7.705)'), 70);
  assert.equal(run('count'), 1);
});

test('Known, three-digit and unknown limits update the same accessible sign', () => {
  const marks = new Set(['unknown']);
  const sign = {
    textContent: '–',
    setAttribute(name, value) { this[name] = value; },
    classList: {toggle(name, active) { if (active) marks.add(name); else marks.delete(name); }}
  };
  const {run} = load();
  const doc = run('document');
  doc.hidden = false;
  doc.getElementById = id => id === 'gps-speed-limit' ? sign : null;
  for (const [speed, text, label] of [
    [80, '80', 'Fartsgrense 80 km/t'],
    [110, '110', 'Fartsgrense 110 km/t'],
    [null, '–', 'Ukjent fartsgrense']
  ]) {
    run(`currentSpeedLimit=${speed};renderGPS()`);
    assert.equal(sign.textContent, text);
    assert.equal(sign['aria-label'], label);
    assert.equal(marks.has('unknown'), speed === null);
    assert.equal(marks.has('three-digits'), speed === 110);
  }
});

test('A stationary GPS fix shows the fetched limit when NVDB ends with an empty page that still links onward', async () => {
  const requests = [];
  const next = 'https://example.test/next';
  const {run} = load(async url => {
    requests.push(url);
    return requests.length === 1 ? response([object(70)], next) : response([], next);
  });
  run('gps.watching=true; gps.speed=0; gps.heading=null; gps.lastPos=[63.10015,7.705]');
  await run('refreshSpeedLimitsLight(...gps.lastPos,true)');
  assert.equal(requests.length, 2);
  assert.equal(run('currentSpeedLimit'), 70);
});

test('A repeated nonempty page is rejected without replacing the last complete lookup', async () => {
  const repeated = 'https://example.test/repeated';
  let calls = 0;
  const {run} = load(async () => {
    calls++;
    return calls === 1 ? response([object(70)]) : response([object(50)], repeated);
  });
  await run('refreshSpeedLimitsLight(63.1,7.705)');
  await run('refreshSpeedLimitsLight(63.1,7.705,true)');
  assert.equal(calls, 3);
  assert.equal(run('currentSpeedLimit'), 70);
});
