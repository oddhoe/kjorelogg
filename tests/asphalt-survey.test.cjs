const assert = require('node:assert/strict');
const test = require('node:test');
const {createAppContext} = require('./app-vm.cjs');

const plan = {
  id: 'survey', tiltakId: 'MR-26-1', sourceFormat: 'MRFK', nr: 64,
  vegref: 'FV64 S8D1 m0 - S8D1 m110',
  fraS: 8, fraD: 1, fraM: 0, tilS: 8, tilD: 1, tilM: 110,
  laidDate: '2026-06-02', markedDate: '2026-06-05',
  matchedRanges: [{s: 8, d: 1, from: 0, to: 110}]
};
const run = (from, to, overrides = {}) => ({
  nr: 64, s: 8, d: 1, from, to, direction: 'Stigende',
  work: 'Skanning og bilder', vegref: plan.vegref, ...overrides
});

test('10 metres of photos on a 110 metre job remain partial despite a legacy finish flag', () => {
  const app = createAppContext();
  const r = {...plan, surveyRuns: [run(0, 10, {work: 'Bilder', finished: true})]};
  const coverage = app.surveyCoverage(r);
  const gaps = Array.from(coverage.gaps, gap => [gap.work, gap.direction, gap.from, gap.to]);
  assert.deepEqual(gaps, [
    ['Skanning', 'Stigende', 0, 110], ['Bilder', 'Stigende', 10, 110],
    ['Skanning', 'Synkende', 0, 110], ['Bilder', 'Synkende', 0, 110]
  ]);
  assert.equal(app.surveyState(r), 'partial');
  assert.equal(app.asphaltReady(r), true);
  assert.equal(app.confirmSurvey(r), false);
  const panel = app.surveyPanel(r);
  assert.match(panel, /Bilder · Stigende · S8D1 m10–110/);
  assert.doesNotMatch(panel, /Bekreft målebiloppdrag fullført/);
});

test('coverage joins overlapping and touching runs separately for each work type and direction', () => {
  const app = createAppContext();
  const r = {...plan, surveyRuns: [
    run(60, 110), run(0, 60, {work: 'Bilder'}), run(0, 45, {work: 'Skanning'}),
    run(40, 59, {work: 'Skanning'}), run(0, 110, {direction: 'Synkende'}),
    run(59, 60, {s: 9}), run(59, 60, {d: 2}), run(59, 60, {nr: 65})
  ]};
  assert.deepEqual(Array.from(app.surveyCoverage(r).gaps, g => [g.work, g.from, g.to]),
    [['Skanning', 59, 60]]);
  r.surveyRuns.push(run(59, 60, {work: 'Skanning'}));
  assert.equal(app.surveyState(r), 'unconfirmed');
  assert.equal(app.asphaltReady(r), true);
  assert.equal(app.confirmSurvey(r), true);
  assert.equal(app.surveyState(r), 'complete');
  assert.equal(app.asphaltReady(r), false);
});

test('every matched section is required, regardless of overlapping metre numbers', () => {
  const app = createAppContext();
  const r = {...plan, tilS: 9, tilM: 20, matchedRanges: [
    ...plan.matchedRanges, {s: 9, d: 1, from: 0, to: 20}
  ], surveyRuns: [run(0, 110), run(0, 110, {direction: 'Synkende'})]};
  const gaps = app.surveyCoverage(r).gaps;
  assert.equal(gaps.length, 4);
  assert.ok(gaps.every(gap => gap.s === 9 && gap.from === 0 && gap.to === 20));
  assert.equal(app.confirmSurvey(r), false);
});

test('missing or partial NVDB data cannot be treated as full coverage', () => {
  const app = createAppContext();
  const r = {...plan, matchedRanges: [], surveyRuns: []};
  assert.equal(app.confirmSurvey(r), false);
  r.matchedRanges = [{s: 8, d: 1, from: 0, to: 10}];
  r.surveyRuns = [run(0, 10), run(0, 10, {direction: 'Synkende'})];
  assert.equal(app.surveyCoverage(r).gaps.length, 0);
  assert.match(app.surveyPanel(r), /Mangler NVDB-intervall for S8D1 m10–110/);
  assert.equal(app.confirmSurvey(r), false);
});

test('a reason is required for an override, and it survives reload and reimport of the same plan', () => {
  const app = createAppContext();
  const r = {...plan, surveyRuns: [run(0, 110)]};
  assert.equal(app.confirmSurvey(r, '   '), false);
  assert.equal(app.confirmSurvey(r, ' Kun stigende. <Envegsregulert> '), true);
  const [saved] = app.normalizeAsphaltPlan(JSON.parse(JSON.stringify([r])));
  const [updated] = app.normalizeAsphaltPlan(app.mergeSurveyPlans([saved], [plan]));
  assert.equal(app.surveyState(updated), 'override');
  assert.equal(app.asphaltReady(updated), false);
  assert.match(app.surveyPanel(updated), /Kun stigende. &lt;Envegsregulert&gt;/);
  assert.equal(updated.surveyRuns.length, 1);
  const [extended] = app.mergeSurveyPlans([updated], [{...plan, tilM: 120}]);
  assert.equal(app.asphaltReady(extended), true);
});

test('survey forms save a run separately from confirmation and can reopen an override', () => {
  const listeners = {};
  const app = createAppContext({
    document: {
      addEventListener(type, listener) { listeners[type] = listener; },
      getElementById: () => ({addEventListener() {}}),
      querySelector: () => null,
      querySelectorAll: () => []
    },
    FormData: class {
      constructor(form) { this.fields = form.fields; }
      get(name) { return this.fields[name] ?? null; }
    },
    alert: message => { throw new Error(message); }
  });
  const r = {...plan, surveyRuns: []};
  app.asphaltRecordByKey = () => r;
  app.saveAsphaltPlan = () => {};
  app.refreshProgressAfterPopup = () => {};
  const submit = (id, fields = {}) => {
    let prevented = false;
    listeners.submit({target: {id, fields}, preventDefault() { prevented = true; }});
    assert.equal(prevented, true);
  };

  submit('survey-run', {range: '0', from: '0', to: '10', date: '2026-06-06',
    work: 'Bilder', direction: 'Stigende', finished: 'on'});
  assert.equal(r.surveyRuns[0].finished, false);
  assert.equal(app.asphaltReady(r), true);
  assert.throws(() => submit('survey-complete'), /Gjennomgå manglende dekning/);
  submit('survey-complete', {reason: 'Arbeid avbrutt etter avtale'});
  assert.equal(app.asphaltReady(r), false);
  submit('survey-reopen');
  assert.equal(app.asphaltReady(r), true);
  assert.equal(r.surveyRuns.length, 1);
});
