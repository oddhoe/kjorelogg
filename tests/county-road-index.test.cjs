const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const {createAppContext} = require('./app-vm.cjs');

function run(scenario) {
  return vm.runInContext('(async()=>{' + scenario + '})()', createAppContext({assert}));
}

test('County index matches the full scan at cell and circle boundaries and after replacement', () => run(`
  const road=(key,parts)=>({key,parts,kat:'F',trafikantgruppe:'K'});
  const makeBackground=()=>Array.from({length:1024},(_,i)=>{
    const lon=6+(i%32)*0.107,lat=62+Math.floor(i/32)*0.053;
    return road('grid'+i,[[[lon,lat],[lon+0.06,lat+0.031]]]);
  });
  const cross=road('cross',[[[5,62.7],[14,62.7]]]);
  const multipart=road('multipart',[[[5,58],[5.001,58.001]],[[7.2,62.7],[7.201,62.701]]]);
  const data=makeBackground();
  data.splice(17,0,cross,road('empty',[]),multipart);
  data.push(road('same geometry, second feature',cross.parts));
  const saved=JSON.stringify(data);
  let snapshot=data;
  loadCountyCache=async()=>({data:snapshot,meta:{roadModel:ROAD_MODEL_VERSION}});
  const intersects=roadIntersectsBBox,visits=[];
  let count=0;
  roadIntersectsBBox=(...args)=>{count++;return intersects(...args)};
  for(const [lat,lon,radius] of [
    [62.7,7.2,1],[62.700000001,7.199999999,3],[62.7,8.2,10],[62.7,7.2,100],
    [58,5,1],[68,10,3],[71.6,25.1,5]
  ]){
    count=0;
    const area=(await loadCountyRoadsForArea(lat,lon,radius,'15')).area;
    visits.push(count);
    assert.deepEqual(area,applySearchRadiusView(data,lat,lon,radius));
  }
  assert.ok(visits[0]<data.length/4,'narrow query must visit fewer local candidates');
  assert.equal(JSON.stringify(data),saved,'index and clip must preserve source geometry');
  snapshot=[...data.slice(1),road('new road',[[[7.19,62.7],[7.21,62.7]]])];
  const replaced=(await loadCountyRoadsForArea(62.7,7.2,1,'15')).area;
  assert.deepEqual(replaced,applySearchRadiusView(snapshot,62.7,7.2,1));
  assert.ok(replaced.some(r=>r.key==='new road'));
`));

test('Replacing a county during import invalidates only committed county cache entries', () => run(`
  const replaced=activeCountyCacheKey('15'),untouched=activeCountyCacheKey('50');
  rememberCountyCache(replaced,{data:[]});
  rememberCountyCache(untouched,{data:[]});
  let fail=true;
  openIDB=async()=>({transaction:()=>{
    const tx={error:new Error('quota'),objectStore:()=>({put(){}})};
    Promise.resolve().then(()=>fail?tx.onabort():tx.oncomplete());
    return tx;
  }});
  const value={data:[{kat:'F',gsv:false}],ts:42,meta:{roadModel:ROAD_MODEL_VERSION,complete:true,cat:'F',count:1,categoryCounts:{F:1}}};
  const items=[{key:replaced,value}, {key:'nvdb_area_1',value:{data:[]}}];
  await assert.rejects(importAllTiles(items),/quota/);
  assert.ok(_countyCacheMem.has(replaced));
  fail=false;
  await importAllTiles(items);
  assert.equal(_countyCacheMem.has(replaced),false);
  assert.ok(_countyCacheMem.has(untouched));
  rememberCountyCache(replaced,value);
  assert.equal(await importAllTiles([{key:replaced,value:{data:[],ts:12,meta:{roadModel:2,complete:true}}}]),0);
  assert.equal(_countyCacheMem.get(replaced),value);
`));

test('Even a small county yields between expensive roads and returns a complete ordered result', () => run(`
  const data=Array.from({length:5},(_,i)=>({key:String(i),kat:'F',trafikantgruppe:'K',parts:[[[7.2,62.7],[7.201,62.7]]]}));
  const reference=applySearchRadiusView(data,62.7,7.2,1);
  loadCountyCache=async()=>({data,meta:{roadModel:ROAD_MODEL_VERSION}});
  let elapsed=0,processed=0;
  const checkpoints=[],add=addRoadToRadiusView;
  Date.now=()=>elapsed;
  addRoadToRadiusView=(...args)=>{add(...args);processed++;elapsed+=5};
  setTimeout=callback=>{checkpoints.push(processed);Promise.resolve().then(callback)};
  assert.deepEqual((await loadCountyRoadsForArea(62.7,7.2,1,'15')).area,reference);
  assert.deepEqual(checkpoints,[2,4]);
`));

test('Clipping retains rounded intersections, detached endpoints and zero length geometry', () => run(`
  const a=[7,59.98],b=[7,60.02],point=t=>[7,a[1]+(b[1]-a[1])*t];
  assert.deepEqual(clipSegmentToRadius(a,b,60,7,1113.2),[point(0.25),point(0.75)]);
  assert.equal(clipSegmentToRadius(a,b,60,7,0),null);
  assert.equal(clipSegmentToRadius(a,b,60,9,100),null);
  const whole=clipSegmentToRadius(a,b,60,7,10000);
  assert.deepEqual(whole,[point(0),point(1)]);
  assert.notEqual(whole[0],a);
  assert.notEqual(whole[1],b);
  assert.deepEqual(clipSegmentToRadius(a,a,60,7,10000),[a,a]);
`));
