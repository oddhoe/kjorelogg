const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const {createAppContext} = require('./app-vm.cjs');

// Selected NVDB V4 segment attributes and endpoints from Møre og Romsdal,
// 2026-11-21, Statens vegvesen (NLOD). WKT here uses only the endpoints.
const examples = [
  ['3925664-2-3',6138,1,'K','HOVED','Vegtrase','Kanalisert veg',8698.111,8722.487,'62.64749829 8.69529685,62.64734446 8.69496083'],
  ['3925666-1-3',6138,1,'K','DETALJERT','Kjørebane','Kanalisert veg',8698.111,8722.487,'62.64749829 8.69529685,62.64738927 8.69487294'],
  ['3925664-3-3',6138,1,'K','KONNEKTERING','Vegtrase','Kanalisert veg',8722.487,8725.862,'62.64734446 8.69496083,62.647324 8.69491253'],
  ['3907634-1-3',64,112,'G','KONNEKTERING','Vegtrase og kjørebane','Gang- og sykkelveg',0,2.562,'62.85395642 7.17400134,62.85395642 7.17395115'],
  ['3907634-3-3',64,112,'G','HOVED','Vegtrase og kjørebane','Gang- og sykkelveg',2.562,44.11,'62.85395642 7.17395115,62.85409976 7.17334353']
];
const rows = examples.map(([referanse,nummer,delstrekning,trafikantgruppe,type,detaljnivå,typeVeg,fra_meter,til_meter,coords]) => ({
  referanse,type,detaljnivå,typeVeg,
  vegsystemreferanse:{vegsystem:{vegkategori:'F',fase:'V',nummer},strekning:{strekning:1,delstrekning,trafikantgruppe,fra_meter,til_meter}},
  geometri:{wkt:'LINESTRING ('+coords+')'}
}));

test('Paged county road ingestion keeps one reference geometry and excludes motor and GSV connector metres', async () => {
  let calls=0;
  const fetch=async href=>{
    const url=new URL(href);
    assert.equal(url.searchParams.get('detaljniva'),'VT,VTKB,KB');
    assert.equal(url.searchParams.get('fylke'),'15');
    if(++calls===1){
      url.searchParams.set('start','3925664:3:3');
      return {ok:true,json:async()=>({objekter:rows.slice(0,2),metadata:{neste:{href:url.href}}})};
    }
    assert.equal(url.searchParams.get('start'),'3925664:3:3');
    return {ok:true,json:async()=>({objekter:rows.slice(2)})};
  };
  const ctx=createAppContext({fetch,URL});
  const roads=await vm.runInContext("settings.categoryFilter={F:true,FGSV:true};loadRoadsAround(62.7,8,3,'15')",ctx);
  assert.equal(calls,2);
  assert.deepEqual(Array.from(roads,r=>[r.key,r.parts.length,r.fra,r.til]),[
    ['Fv6138_S1D1',1,8698.111,8722.487],['Fv64_S1D112',1,2.562,44.11]
  ]);
  assert.equal(roads[0].gpsParts.length,1);
  assert.equal(roads[1].gpsParts,undefined);
});

test('FV669 acquisition uses a measured carriageway offset while progress, map and backup use the reference', async () => {
  // Actual consecutive vertices of 1221875-4-3 and 3372553-1-3, FV669 S1D1.
  const primary=[[8.12930034,63.23275794],[8.12971019,63.23282369]];
  const lane=[[8.129398,63.23261798],[8.12962165,63.23265091]];
  const object=(coords,type,detaljnivå)=>({
    type,detaljnivå,typeVeg:'Kanalisert veg',kommune:1573,
    vegsystemreferanse:{vegsystem:{vegkategori:'F',fase:'V',nummer:669},strekning:{strekning:1,delstrekning:1,trafikantgruppe:'K'}},
    geometri:{wkt:'LINESTRING('+coords.map(([lon,lat])=>lat+' '+lon).join(',')+')'}
  });
  let rows=[object([...lane].reverse(),'DETALJERT','Kjørebane')];
  const ctx=createAppContext({assert,URL,structuredClone,fetch:async()=>({ok:true,json:async()=>({objekter:rows})})});
  const query="loadRoadsAround(63.233,8.13,1,'15')";
  ctx.edge=structuredClone(await vm.runInContext(query,ctx));
  assert.equal(ctx.edge.length,0);
  assert.equal(ctx.edge.gpsAtTileEdges.length,1);
  rows=[object(primary,'HOVED','Vegtrase')];
  ctx.otherTile=await vm.runInContext(query,ctx);
  vm.runInContext(`
    const groups=new Map(),gpsPartsByKey=new Map();
    addRoadsToMerge(groups,edge,gpsPartsByKey);
    addRoadsToMerge(groups,otherTile,gpsPartsByKey);
    addRoadsToMerge(groups,edge,gpsPartsByKey);
    const [r]=finishRoadMerge(groups,gpsPartsByKey);
    assert.equal(r.parts.length,1);
    assert.equal(r.gpsParts.length,1);
    assert.equal(r.len,otherTile[0].len);
    const lat=63.232634445,lon=8.129509825;
    assert.ok(roadDist(lat,lon,r)>16&&roadDist(lat,lon,r)<17);
    assert.ok(roadDist(lat,lon,gpsRoadGeometry(r))<0.01);
    assert.ok(roadBBoxDist(lat,lon,r)>12);
    roads=[r];
    assert.equal(nearbyRoadsForGps(lat,lon,1)[0].key,r.key);
    // Within 10 m only the carriageway enters the view. No line/length may leak onto the map.
    const view=applySearchRadiusView([r],lat,lon,0.01);
    assert.equal(view.length,1);
    assert.equal(roadRenderParts(view[0]).length,0);
    assert.equal(roadRenderLen(view[0]),0);
    setAreaRoads(view);
    assert.equal(visibleRoadsList().length,0);
    const src=r.gpsParts[0],heading=bearingBetween(src[1][1],src[1][0],src[0][1],src[0][0]);
    assert.equal(roadAlignmentInfo(lat,lon,r,heading).dir,roadAlignmentInfo(lat,lon,otherTile[0],heading).dir);
    assert.equal(roadAlignmentInfo(lat,lon,r,heading).ok,true);
    gps.watching=true;gps.lastPos=[lat,lon];gps.heading=heading;gps.speed=12;gps.acc=2;
    // Only the GPS clock/UI side effects are stubs. Candidate selection, assignment and logging run.
    markRouteLogDirty=markDirectionDirty=markDirectionDriven=scheduleLiveProgressRender=saveGeomCache=setMessage=()=>{};
    for(let i=0;i<GPS_ENTER_CONSEC;i++)updateDistancesAndActiveRoad();
    assert.equal(gps.activeKey,r.key);
    assert.equal(routeLog[r.key][gps.activeDir].length,1);
    assert.equal(geomCache[r.key].parts.length,1);
    assert.equal(geomCache[r.key].gpsParts,undefined);
    assert.equal(compactGeomCacheForExport(geomCache)[r.key].parts.length,1);
    assert.equal(JSON.stringify(progressSnapshot()).includes('gpsParts'),false);
  `,ctx);
});

test('Recognized lower topology levels are excluded even with missing fields; a road name cannot remove a primary road', async () => {
  const objects=[
    {...rows[0],type:undefined,detaljnivå:undefined,topologinivå:'Kjørefelt'},
    {...rows[0],type:undefined,detaljnivå:undefined,detaljniva:'KB'},
    {...rows[0],type:'HOVED',detaljnivå:undefined,navn:'Tilknytningsvegen'},
    {...rows[0],type:'DETALJERT_KONNEKTERING',detaljnivå:undefined}
  ];
  const ctx=createAppContext({rows:objects});
  assert.deepEqual(Array.from(vm.runInContext('rows.map(isMeasurementRoadLink)',ctx)),[false,false,true,false]);
});
