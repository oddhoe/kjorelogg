const assert = require('node:assert/strict');
const test = require('node:test');
const {createAppContext} = require('./app-vm.cjs');

const mrfk = [
  ['Nr', 'FraS', 'FraDs', 'FraM', 'TilS', 'TilDs', 'TilM'],
  [64, 8, 1, 0, 8, 1, 110]
];
const nordland = [
  ['Punkt.Nr', 'Kommune', 'Fv.nr', 'S/D', 'Fra meter', 'S/D', 'Til meter'],
  [1, 'Bodø', 17, '1/1', 0, '1/1', 110]
];

function parse(sheets) {
  const readSheets = [];
  const xlsx = {
    read: () => ({SheetNames: Object.keys(sheets), Sheets: sheets}),
    utils: {
      sheet_to_json(rows) { readSheets.push(rows); return rows; },
      decode_range: () => ({s: {r: 0}})
    }
  };
  const app = createAppContext({window: {addEventListener() {}, XLSX: xlsx}});
  const result = app.parseAsphaltWorkbook(null, 'Asfaltplan-2026.xlsx');
  return {result, readSheets};
}

test('MRFK with cover sheet and header after introductory rows', () => {
  const rows = [...Array(16).fill(['Merknad']), ...mrfk];
  const {result, readSheets} = parse({Forside: [['Asfalt']], Tiltak: rows, Vedlegg: []});
  assert.equal(result.sheet, 'Tiltak');
  assert.equal(result.records[0].vegref, 'FV64 S8D1 m0 - S8D1 m110');
  assert.equal(result.records[0].row, 18);
  assert.equal(readSheets.length, 2);
});

test('Nordland on a named second sheet, preserving an explicit zero meter', () => {
  const {result} = parse({Forside: [['Asfalt']], Nordland: nordland});
  assert.equal(result.sheet, 'Nordland');
  assert.equal(result.format, 'NORDLAND');
  assert.equal(result.records[0].fraM, 0);
});

test('single-sheet MRFK keeps the same row id, and MRFK retains priority in mixed workbooks', () => {
  const single = parse({Plan: mrfk}).result;
  const mixed = parse({Alternativ: nordland, Plan: mrfk}).result;
  assert.equal(single.records[0].id, mixed.records[0].id);
  assert.equal(single.sheet, 'Plan');
  assert.equal(mixed.format, 'MRFK');
});

test('MRFK survey dates and stable ID preserve field history across file and row changes', () => {
  const rows = [[...mrfk[0], 'Tiltaks-ID', 'Dato lagt dekke', 'Dato utført vegmerking'],
    [...mrfk[1], 'MR-26-1', '02.06.2026', '2026-06-05']];
  const row = parse({Plan: rows}).result.records[0];
  assert.equal(row.laidDate, '2026-06-02');
  assert.equal(row.markedDate, '2026-06-05');
  const app = createAppContext();
  const [saved] = app.mergeSurveyPlans([], [row]);
  saved.surveyRuns.push({work: 'Bilder', finished: false, vegref: row.vegref});
  const [updated] = app.normalizeAsphaltPlan(app.mergeSurveyPlans([saved], [{...row, id: 'ny-fil:annen-rad'}]));
  assert.equal(updated.id, saved.id);
  assert.equal(updated.surveyRuns[0].work, 'Bilder');
  updated.manualStatus='none';
  assert.equal(app.asphaltReady(updated),true);
  updated.surveyRuns[0].finished=true;
  assert.equal(app.asphaltReady(updated),false);
  assert.equal(app.asphaltWorkDate('31.02.2026'), '');
  assert.throws(()=>app.mergeSurveyPlans([], [row,row]), /Duplikat/);
});
