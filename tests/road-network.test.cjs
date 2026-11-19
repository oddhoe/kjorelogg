const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const {createAppContext} = require('./app-vm.cjs');

function run(scenario, globals = {}) {
  const context = createAppContext({assert, URL, ...globals});
  return vm.runInContext(scenario, context);
}

test('Parallel road geometries survive merging; reversed duplicates do not', () => run(`
  const south = [[7,63],[7.01,62.999],[7.02,63]];
  const north = [[7,63],[7.01,63.001],[7.02,63]];
  const road = parts => ({veg:'Fv64',seg:'S1D1',parts,partsWithMeter:[]});
  const [merged] = mergeRoads([road([south]),road([north,[...south].reverse()])]);
  assert.deepEqual(merged.parts, [south,north]);
  assert.equal(merged.len, Math.round(calcPartsKm([south,north])*1000));
`));

test('GPS recognizes both directions on a diagonal road at 63 degrees north', () => run(`
  const road={parts:[[[7.70,63.10],[7.71,63.105]]]};
  const info=roadAlignmentInfo(63.1025,7.705,road,42);
  assert.ok(info.ok);
  assert.equal(info.dir,'fwd');
  assert.ok(roadAlignmentInfo(63.1025,7.705,road,222).ok);
  assert.equal(roadAlignmentInfo(63.1025,7.705,road,222).dir,'rev');
  assert.equal(roadAlignmentInfo(63.1025,7.705,road,132).ok,false);
`));

test('Cache cells cover all requested positions and the reload distance fits inside the view', () => run(`
  for(const radius of [1,3,5,10,30,100]){
   for(const latitude of [57.25,63.12,71.66]){
    const anchor=roadTileForArea(latitude,7.75,radius,'15');
    const delta=0.499999*Math.min(2,radius/5)/111.32;
    const fetched=bboxFromPoint(anchor.lat,anchor.lon,anchor.radius);
    for(const lat of [anchor.lat-delta,anchor.lat+delta]){
     for(const lon of [anchor.lon-delta,anchor.lon+delta]){
      assert.deepEqual(roadTileForArea(lat,lon,radius,'15'),anchor);
      const wanted=bboxFromPoint(lat,lon,radius);
      for(const i of [0,1])assert.ok(fetched[i]<=wanted[i]+1e-9);
      for(const i of [2,3])assert.ok(fetched[i]>=wanted[i]-1e-9);
     }
    }
   }
   for(const saving of [true,false]){
    settings.dataSaver=saving;
    assert.ok(getReloadDistKm(radius)>0&&getReloadDistKm(radius)<=radius/2);
   }
  }
  const initial=roadTileForArea(63.12,7.75,1,'15');
  assert.notEqual(initial.key,roadTileForArea(63.12,7.78,1,'15').key);
  assert.notEqual(initial.key,roadTileForArea(63.12,7.75,1,'50').key);
  settings.includeRamper=true;
  assert.notEqual(initial.key,roadTileForArea(63.12,7.75,1,'15').key);
`));

test('A failed quadrant cannot become a completed dense-area download', async () => {
  let calls=0;
  const road={
    vegsystemreferanse:{vegsystem:{vegkategori:'K',nummer:1},strekning:{strekning:1,delstrekning:1,trafikantgruppe:'K'}},
    geometri:{wkt:'LINESTRING(10.74 59.91,10.75 59.92)'},kommune:301
  };
  const fetch = async () => ++calls===2 ? {ok:false,status:503} : {ok:true,json:async()=>({objekter:[road]})};
  await assert.rejects(run(`settings.categoryFilter.K=true; loadRoadsAround(59.9139,10.7522,5,'3')`,{fetch}),/NVDB 503/);
  assert.equal(calls,2);
});

test('Empty quadrants are valid and malformed or truncated NVDB pages are rejected', async () => {
  let calls=0;
  const fetch=async()=>{calls++;return {ok:true,json:async()=>({objekter:[]})}};
  const roads=await run(`settings.categoryFilter.K=true; loadRoadsAround(59.9139,10.7522,5,'3')`,{fetch});
  assert.equal(roads.length,0);
  assert.equal(calls,4);
  await assert.rejects(run(`loadRoadsAround(63,7,1,'15')`,{
    fetch:async()=>({ok:true,json:async()=>({})})
  }),/ugyldig/);
  const paged=async()=>({ok:true,json:async()=>({objekter:[],metadata:{neste:{href:'https://example.invalid/next'}}})});
  await assert.rejects(run(`loadRoadsAround(63,7,0.5,'15')`,{
    fetch:paged,console:{log(){},warn(){}}
  }),/ufullstendig/);
});

test('An online update never reuses a neighbouring legacy tile or saves a failed refresh as fresh', async () => run(`
 (async()=>{
  const el={value:'3',dataset:{},classList:{contains:()=>false}};
  document.getElementById=()=>el;
  gps.watching=true;
  loadCountyRoadsForArea=async()=>null;
  const reads=[],writes=[],messages=[],requests=[];
  const legacyKey=legacyTileKey(63.12,7.75,3,null);
  const tile=roadTileForArea(63.12,7.75,3,null);
  let available=new Map([[legacyKey,[]]]);
  loadTile=async key=>{reads.push(key);return available.get(key)??null};
  saveTile=async(key,roads)=>{writes.push(key);available.set(key,roads)};
  loadRoadsAround=async(...args)=>{requests.push(args);return []};
  cacheGeomForTrackedRoads=()=>{};
  updateDistancesAndActiveRoad=renderAllViews=()=>{};
  setMessage=t=>messages.push(t);
  await updateFromCenter(true,63.12,7.75);
  assert.deepEqual(reads,[tile.key]);
  assert.deepEqual(writes,[tile.key]);
  assert.deepEqual(requests,[[tile.lat,tile.lon,tile.radius,null]]);
  loadRoadsAround=async()=>{throw new Error('NVDB 400')};
  await updateFromCenter(true,63.12,7.75);
  assert.equal(writes.length,1);
  assert.ok(messages.some(t=>t.includes('viser sist lagrede')));
  available.delete(tile.key);
  offlineMode=true;
  await updateFromCenter(true,63.12,7.75);
  assert.deepEqual(reads.slice(-2),[tile.key,legacyKey]);
  assert.ok(messages.at(-1).includes('eldre lokal rute'));
 })()
`));

test('Only roads in service are fetched and changing a filter discards a pending result', async () => {
  const record=(fase,strekning,extra={})=>({
    vegsystemreferanse:{vegsystem:{vegkategori:'F',nummer:5336,fase},strekning:{strekning,delstrekning:1,trafikantgruppe:'K'},...extra},
    geometri:{wkt:'LINESTRING(5.0989 60.3517,5.0992 60.3518)'}
  });
  const objects=[record('A',1000),record('V',1),record('V',2,{sideanlegg:{sideanleggsdel:1}})];
  const fetch=async href=>{
    assert.equal(new URL(href).searchParams.get('vegsystemreferanse'),'FV');
    return {ok:true,json:async()=>({objekter:objects})};
  };
  const roads=await run(`loadRoadsAround(60.352,5.099,1,'46')`,{fetch});
  assert.deepEqual(Array.from(roads,r=>r.key),['Fv5336_S1D1']);
  await run(`
   (async()=>{
    gps.watching=true;
    document.getElementById=()=>({value:'3',dataset:{}});
    let finish;
    setMessage=()=>{};
    loadTile=async()=>null;
    loadRoadsAround=()=>new Promise(resolve=>{finish=resolve});
    saveTile=()=>assert.fail('Old categories were written after the selection changed');
    const loading=updateFromCenter(true,63.12,7.75);
    await Promise.resolve();
    settings.categoryFilter.K=true;
    roadFilterRevision++;
    finish([]);
    await loading;
    assert.equal(lastCenter,null);
   })()
  `);
});

test('County geometry from before the phase filter stays available offline', async () => run(`
 (async()=>{
  const payload={data:[],ts:Date.now(),meta:{complete:true}};
  loadCountyCache=async()=>payload;
  assert.equal(await loadCountyRoadsForArea(63,7,1,'15'),null);
  document.getElementById=()=>({value:'1',dataset:{}});
  gps.watching=true;gps.detectedFylke='15';
  loadTile=async()=>null;
  loadRoadsAround=async()=>{throw new Error('NVDB 400')};
  saveTile=()=>assert.fail('Legacy county data must not replace an area tile');
  setMessage=cacheGeomForTrackedRoads=updateDistancesAndActiveRoad=renderAllViews=()=>{};
  await updateFromCenter(true,63,7);
  assert.equal(lastCenterFylke,'15');
  offlineMode=true;
  assert.deepEqual((await loadCountyRoadsForArea(63,7,1,'15')).area,[]);
  offlineMode=false;
  payload.meta.roadModel=2;
  assert.deepEqual((await loadCountyRoadsForArea(63,7,1,'15')).area,[]);
 })()
`));

test('Explicit traffic groups override section numbers for main roads and older saved records', async () => {
  const segment=(delstrekning,trafikantgruppe)=>({
    vegsystemreferanse:{vegsystem:{vegkategori:'F',fase:'V',nummer:523},strekning:{strekning:2,delstrekning,trafikantgruppe}},
    geometri:{wkt:'LINESTRING(6.05 59.12,6.051 59.12)'}
  });
  const objects=[segment(20,'G'),segment(101,'K'),segment(110,undefined)];
  const fetch=async()=>({ok:true,json:async()=>({objekter:objects})});
  await run(`
   (async()=>{
    let selected=await loadRoadsAround(59.12,6.05,1,'11');
    assert.deepEqual(selected.map(r=>r.key),['Fv523_S2D101']);
    settings.categoryFilter={FGSV:true};
    selected=await loadRoadsAround(59.12,6.05,1,'11');
    assert.deepEqual(selected.map(r=>r.key),['Fv523_S2D20','Fv523_S2D110']);
    geomCache['Fv523_S2D20']={kat:'F',trafikantgruppe:'G',gsv:false};
    geomCache['Fv523_S2D101']={kat:'F',trafikantgruppe:'K',gsv:true};
    assert.equal(_isOneWayKey('Fv523_S2D20'),true);
    assert.equal(_isOneWayKey('Fv523_S2D101'),false);
    assert.ok(catBadgeHtml(geomCache['Fv523_S2D20']).includes('FV-GSV'));
    directionState['Fv523_S2D20']={fwd:true,rev:true,manualFull:true};
    setMessage=()=>{};
    repairFalseRevTracks();
    assert.ok(directionState['Fv523_S2D20'].rev);
   })()
  `,{fetch});
});
