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
  configureMapBackground = () => {};
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

test('Kart draws disconnected parts together while retaining hit targets, style order and fit bounds', () => run(`
  const a={key:'Fv1_S1D1',parts:[[[7,62],[7.01,62]],[[7.03,62],[7.04,62]]]};
  const b={key:'Fv2_S1D1',parts:[[[7.02,62.01],[7.02,62.02]]]};
  const calls=[],clicks=[];
  let fitBounds;
  activeTabId=()=>'map';
  map={fitBounds(bounds){fitBounds=bounds}};
  roadLayerGroup={clearLayers(){calls.length=0}};
  mapRoadsToRender=()=>[b,a];
  gps.activeKey=b.key;
  getCoverageDrawPlans=()=>[];
  getRoadStatus=()=>'';
  openRoadPopup=(key,at)=>clicks.push([key,at]);
  _svgRenderer={};
  globalThis.L={
    polyline(points,opts){return {points,opts,addTo(group){assert.equal(group,roadLayerGroup);calls.push(this);return this},on(event,fn){assert.equal(event,'click');this.click=fn}}},
    DomEvent:{stopPropagation(){}},latLngBounds:p=>p
  };
  updateMapOverlay(true);
  assert.deepEqual(calls.map(x=>x.opts.color),['#d32f2f','transparent','#2b2b31','transparent','#1e88ff','transparent']);
  assert.deepEqual(calls[0].points,[[[62,7],[62,7.01]],[[62,7.03],[62,7.04]]]);
  assert.deepEqual(calls[1].points,calls[0].points);
  assert.equal(calls[1].opts.weight,20);
  assert.deepEqual(calls[2].points,[[[62.01,7.02],[62.02,7.02]]]);
  assert.deepEqual(fitBounds,[[62,7],[62.02,7.04]]);
  calls[0].click({latlng:1});calls[1].click({latlng:2});calls[5].click({latlng:3});
  assert.deepEqual(clicks,[[a.key,1],[a.key,2],[b.key,3]]);
`));

test('Fremdrift preserves separate input paths and misses stay gaps, including the hit area', () => run(`
  const parts=[[[7.200,62.70],[7.203,62.70]],[[7.204,62.70],[7.207,62.70]]];
  const bounds=[],calls=[],clicks=[];
  const group={},key='Fv1_S1D1';
  globalThis.L={polyline(points,options){return{points,options,addTo(target){assert.equal(target,group);calls.push(this);return this},on(_,fn){this.click=fn}}},
    DomEvent:{stopPropagation(){}}};
  handleProgressRoadClick=(...args)=>clicks.push(args);
  drawProgressGeometry(group,parts,'#ef5350',3,.55,bounds,{interactiveKey:key,popup:'missing'});
  assert.equal(calls.length,2);
  const expected=[[[62.70,7.200],[62.70,7.203]],[[62.70,7.204],[62.70,7.207]]];
  assert.deepEqual(calls.map(l=>l.points),[expected,expected]);
  assert.deepEqual(calls.map(l=>l.options.color),['#ef5350','transparent']);
  for(const layer of calls)layer.click({latlng:'point'});
  assert.deepEqual(clicks,[[key,'point','missing'],[key,'point','missing']]);
  assert.deepEqual(bounds,[[62.70,7.200],[62.70,7.207]]);
`));

test('GPS chains consist of source edges, retain reverse digitization and stop at forks, breaks and small gaps', () => run(`
  const a=[7.2,62.7],b=[7.201,62.7],c=[7.202,62.7],d=[7.203,62.7],e=[7.2032,62.7],f=[7.205,62.7];
  const parts=[[b,c],[b,a],[d,c],[e,f]],saved=JSON.stringify(parts);
  assert.deepEqual(makeChainsFromParts(parts),[[a,b,c,d],[e,f]]);
  assert.equal(JSON.stringify(parts),saved);
  assert.deepEqual(makeChainsFromParts([[a,b],[b,c],[b,d]]),[[a,b],[b,c],[b,d]]);
  assert.deepEqual(makeChainsFromParts([[a,b,null,e,f]]),[[a,b],[e,f]]);
  assert.deepEqual(makeChainsFromParts([[a,b],[c,b],[c,a]])[0],[a,b,c,a]);
  const first={parts},a1=getRoadHeadingAtPoint(62.7,7.2004,first,90),a2=getRoadHeadingAtPoint(62.7,7.2026,first,90);
  assert.equal(a1.isForward,true);assert.equal(a2.isForward,true);
`));

test('Parallel disconnected roads cannot borrow GPS coverage or tunnel samples', () => run(`
  const key='Fv120_S1D1',south=62.7000,north=62.70015;
  const southLine=[[7.20,south],[7.215,south]], northLine=[[7.20,north],[7.215,north]];
  roads=[{key,veg:'Fv120',kat:'F',parts:[southLine,northLine]}];
  routeLog[key]={fwd:[{ts:1,lat:north,lon:7.201},{ts:2001,lat:north,lon:7.212}],rev:[]};
  directionState[key]={fwd:true,rev:false};
  const original=JSON.stringify(routeLog);
  const plans=getCoverageDrawPlans(key);
  assert.equal(plans.length,2);
  assert.equal(plans[0].oneKm,0);
  assert.ok(plans[1].oneKm>0.5);
  // Both raw fixes are within the tolerance of BOTH lines, but on different source geometries.
  const gap={fromPos:[south,7.201],toPos:[north,7.213],fromTs:0,toTs:60000};
  assert.equal(maybeBridgeGapOnSameRoad(gap,key,'fwd'),false);
  assert.equal(JSON.stringify(routeLog),original);
  gap.fromPos=[north,7.201];
  setMessage=()=>{};markDirectionDriven=()=>{};scheduleLiveProgressRender=()=>{};markRouteLogDirty=()=>{};
  assert.equal(maybeBridgeGapOnSameRoad(gap,key,'fwd'),true);
  const added=routeLog[key].fwd.filter(p=>p.syn);
  assert.ok(added.length>0);assert.ok(added.every(p=>p.lat===north));
`));

test('Separated visits to a chain cannot imply a continuous driven interval through an unmatched fix', () => run(`
  const key='Fv1_S1D1',lat=62.7;
  roads=[{key,veg:'Fv1',kat:'F',parts:[[[7.20,lat],[7.22,lat]]]}];
  routeLog[key]={fwd:[{lat,lon:7.201,ts:1},{lat:63,lon:7.3,ts:2001},{lat,lon:7.219,ts:4001}],rev:[]};
  directionState[key]={fwd:true,rev:false};
  assert.equal(getCoverageDrawPlans(key)[0].oneKm,0);
`));

test('Equidistant GPS samples cannot select one of two disconnected parallel chains', () => run(`
  const south=62.7,north=62.70015,mid=(south+north)/2;
  const key='Fv1_S1D1',parts=[[[7.20,south],[7.215,south]],[[7.20,north],[7.215,north]]];
  roads=[{key,veg:'Fv1',kat:'F',parts}];
  routeLog[key]={fwd:[{ts:1,lat:mid,lon:7.201},{ts:6011,lat:mid,lon:7.213}],rev:[]};
  directionState[key]={fwd:true,rev:false};
  const original=JSON.stringify(routeLog);
  assert.equal(getCoverageDrawPlans(key).reduce((km,p)=>km+p.oneKm,0),0);
  assert.equal(maybeBridgeGapOnSameRoad({fromPos:[mid,7.201],toPos:[mid,7.213],fromTs:0,toTs:60000},key,'fwd'),false);
  assert.equal(original,JSON.stringify(routeLog));
`));

test('Progress keeps unsnappable track evidence without coloring the whole road; legacy status-only roads stay visible',()=>run(`
  const key='Fv1_S1D1',parts=[[[7.20,62.7],[7.215,62.7]]];
  roads=[{key,veg:'Fv1',kat:'F',parts}];
  geomCache[key]=roads[0];
  directionState[key]={fwd:true,rev:false};
  oneWayKeys.add(key);
  progressMap={};
  progressLayerGroup={clearLayers(){}};
  document.getElementById=()=>({insertAdjacentHTML(){}});
  updateProgressSelectionUI=()=>{};
  keyPassesCategoryFilter=()=>true;keyHasTimeInRange=()=>true;keyPassesProgressFylke=()=>true;
  let calls=0;
  drawProgressGeometry=()=>{calls++};
  routeLog[key]={fwd:[{ts:1,lat:63,lon:7.22},{ts:2001,lat:63,lon:7.221}],rev:[]};
  const original=JSON.stringify(routeLog);
  updateProgressMap({fit:false,force:true});
  assert.equal(calls,0);assert.equal(JSON.stringify(routeLog),original);
  delete routeLog[key];
  updateProgressMap({fit:false,force:true});
  assert.equal(calls,1);
`));

test('Archived source geometry only displays earlier stored coordinates under the old key and adds no measured kilometres',()=>run(`
  const key='Fv61_S1D1',split='Fv61_S1D1_K',north=62.70015,south=62.7000;
  const live=[[7.20,north],[7.215,north]], old=[[7.20,south],[7.215,south]];
  roads=[{key,veg:'Fv61',kat:'F',roadModel:ROAD_MODEL_VERSION,parts:[live]},
         {key:split,veg:'Fv61',kat:'F',roadModel:ROAD_MODEL_VERSION,parts:[old]}];
  geomCache[key]={...roads[0],historicalParts:[old],historicalUntil:5000};
  geomCache[split]=roads[1];
  const first={ts:1,lat:south+.000004,lon:7.201},second={ts:3001,lat:south,lon:7.212};
  routeLog[key]={fwd:[first,second,{ts:4900,lat:south,lon:7.2121,syn:1},
    {ts:6000,lat:south-.001,lon:7.2122}],rev:[]};
  const before=JSON.stringify(routeLog);
  oneWayKeys.add(key);directionState[key]={fwd:true,rev:false};
  assert.deepEqual(getRoadPartsForKey(key),[live]);
  const history=[];
  assert.equal(getCoverageDrawPlans(key,history).reduce((km,p)=>km+p.totalKm,0),0);
  assert.deepEqual(history,[first,second]);
  assert.equal(getRoadStatus(split),'none');
  assert.deepEqual(getCoverageDrawPlans(split),[]);
  const points=[];
  progressMap={}; progressLayerGroup={clearLayers(){}};
  const ui={innerHTML:'',extras:[],insertAdjacentHTML(_,html){this.extras.push(html)}};
  document.getElementById=()=>ui;
  updateProgressSelectionUI=()=>{};
  keyPassesCategoryFilter=()=>true;keyHasTimeInRange=()=>true;keyPassesProgressFylke=()=>true;
  globalThis.L={circleMarker(at,opts){assert.equal(opts.interactive,false);return{addTo(){points.push(at)}}},
    polyline(){throw Error('Archived points must not create a polyline')}};
  updateProgressMap({fit:false,force:true});
  assert.deepEqual(points,[[first.lat,first.lon],[second.lat,second.lon]]);
  assert.ok(ui.extras.some(label=>label.includes('2 lagrede GPS-punkt')));
  assert.equal(before,JSON.stringify(routeLog));
`));

test('Compact GPS backup and reload preserve known estimated-point flags alongside legacy three-value points',()=>run(`
  const compact=compactRouteLogForExport({r:{fwd:[{ts:1,lat:62,lon:7},
    {ts:2,lat:62,lon:7,syn:1},{ts:3,lat:62,lon:7,syn:1,dr:1}]}});
  assert.deepEqual(compact.r.fwd,[[1,62,7],[2,62,7,1],[3,62,7,3]]);
  assert.deepEqual(normalizeRouteLog(compact).r.fwd,[{ts:1,lat:62,lon:7},{ts:2,lat:62,lon:7,syn:1},{ts:3,lat:62,lon:7,syn:1,dr:1}]);
`));
