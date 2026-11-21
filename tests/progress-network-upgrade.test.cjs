const assert = require('node:assert/strict');
const vm = require('node:vm');
const test = require('node:test');
const {createAppContext} = require('./app-vm.cjs');

function run(source) {
  const context=createAppContext({assert});
  return vm.runInContext(`
    saveState=saveGeomCache=()=>{};
    const key='Fv64_S1D1',part1=[[7,62],[7.02,62]],branch=[[7,62.01],[7.02,62.01]];
    const road=(key,group,parts)=>({key,kat:'F',veg:'Fv64',gsv:group==='G',trafikantgruppe:group,
      fylke:'15',seg:'S1D1',parts,roadModel:ROAD_MODEL_VERSION,len:2000});
    const legacy=(key,group,parts)=>({...road(key,group,parts),roadModel:undefined});
    const scope={completeCounty:true,county:'15',categoryKeys:['F','FGSV']};
    ${source}`,context);
}

test('Old explicit group and measurements retain their identity as a new classified road gets a separate key',()=>run(`
  geomCache[key]=legacy(key,'G',[branch]);oneWayKeys.add(key);directionState[key]={fwd:true};
  routeLog[key]={fwd:[{lat:62.01,lon:7,ts:99}],rev:[]};roadComments[key]={text:'Kommentar'};
  const fresh=road(key,'K',[part1]);
  setAreaRoads([fresh]);
  assert.equal(roads[0].key,key+'_K');assert.equal(roadByKeyAny(key).trafikantgruppe,'G');
  cacheGeomForTrackedRoads([fresh],scope);
  assert.deepEqual(geomCache[key].parts,[branch]);
  assert.deepEqual(geomCache[key+'_K'].parts,[part1]);assert.ok(!directionState[key+'_K']);
  const saved=compactGeomCacheForExport(geomCache);geomCache=normalizeLegacyGeomCache(saved);
  setAreaRoads([fresh]);assert.equal(roads[0].key,key+'_K');assert.equal(roadComments[key].text,'Kommentar');
  assert.equal(routeLog[key].fwd[0].ts,99);assert.equal(geomCache[key+'_K'].separateFrom,key);
  const archive=JSON.parse(JSON.stringify(geomCache[key]));
  geomCache={[key]:fresh};
  mergeImportedGeomCache({[key]:archive});
  assert.equal(geomCache[key].trafikantgruppe,'G');assert.equal(geomCache[key+'_K'].trafikantgruppe,'K');
`));

test('Only a complete matching county replaces obsolete mixed geometry while preserving historic parts and GPS',()=>run(`
  geomCache[key]=legacy(key,'K',[part1,branch]);
  routeLog[key]={fwd:[{lat:62.01,lon:7,ts:99}],rev:[]};
  const fresh=road(key,'K',[part1]),split=road(key+'_KS1KD1','K',[branch]);
  cacheGeomForTrackedRoads([fresh]);assert.deepEqual(geomCache[key].parts,[part1,branch]);
  cacheGeomForTrackedRoads([fresh,split],scope);
  assert.deepEqual(geomCache[key].parts,[part1]);assert.deepEqual(geomCache[key].historicalParts,[branch]);
  assert.equal(routeLog[key].fwd[0].ts,99);assert.equal(routeLog[split.key],undefined);
  const roundtrip=normalizeLegacyGeomCache(compactGeomCacheForExport(geomCache));
  assert.deepEqual(roundtrip[key].historicalParts,[branch]);
  assert.ok(roundtrip[key].historicalUntil>=99);assert.equal(roundtrip[key].historicalUntil,geomCache[key].historicalUntil);
`));

test('Former unmeasured keys remain recoverable but retire only after a complete, matching county and category',()=>run(`
  const old=key+'_KS99KD1',traced=key+'_KS98KD1',commented=key+'_KS97KD1',out=key+'_KS96KD1',skip=key+'_KS95KD1';
  for(const k of [old,traced,commented,out,skip])geomCache[k]=legacy(k,'K',[branch]);
  geomCache[out].fylke='50';routeLog[traced]={fwd:[{ts:1,lat:62,lon:7}]};roadComments[commented]={text:'behold'};skipKeys.add(skip);
  const fresh=road(key,'K',[part1]);
  cacheGeomForTrackedRoads([fresh]);assert.ok(!geomCache[old].retiredFromNetwork);
  cacheGeomForTrackedRoads([fresh],{...scope,categoryKeys:['KGSV']});assert.ok(!geomCache[old].retiredFromNetwork);
  cacheGeomForTrackedRoads([fresh],scope);assert.equal(geomCache[old].retiredFromNetwork,true);
  for(const k of [traced,commented,out,skip])assert.ok(!geomCache[k].retiredFromNetwork);
  assert.deepEqual(geomCache[old].parts,[branch]);
  const newer=road(old,'K',[branch]);cacheGeomForTrackedRoads([newer],scope);assert.ok(!geomCache[old].retiredFromNetwork);
`));

test('Progress backups exclude county availability metadata and preserve unrelated extra data',()=>run(`
  const extras=[{key:'__county_meta_nvdb_county_v12_f15_cF',value:{count:200}},{key:'extra',value:{x:2}}];
  assert.deepEqual(getBackupAppDataItems(extras),extras.slice(1));
  assert.deepEqual(getImportedExtraAppDataItems({indexedDB:{appdata:extras}}),extras.slice(1));
`));
