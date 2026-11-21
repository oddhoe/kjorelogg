const assert=require('node:assert/strict');
const test=require('node:test');
const vm=require('node:vm');
const {createAppContext}=require('./app-vm.cjs');

function segment(kat,delstrekning,group,x,overrides={}) {
 const ref={vegsystem:{vegkategori:kat,nummer:61,fase:'V'},strekning:{strekning:3,delstrekning,trafikantgruppe:group,fra_meter:4,til_meter:20}};
 return {kommune:1506,type:'HOVED',detaljnivå:'Vegtrase og kjørebane',typeVeg:'Enkel bilveg',geometri:{wkt:`LINESTRING(${x} 62.7,${x+.0003} 62.7)`},vegsystemreferanse:ref,...overrides};
}
function replay(rows,scenario) {
 const ctx=createAppContext({assert,URL,rows,fetch:async()=>({ok:true,json:async()=>({objekter:rows})})});
 return vm.runInContext(`(async()=>{${scenario}})()`,ctx);
}

for(const kat of ['E','R','F','K']){
 test(`${kat} keeps groups and keys distinct across page order, individual areas and county merging`,async()=>{
  const prefix=kat[0]+'v', road=kat==='K'?'Kv1506-61':prefix+'61';
  const expected=kat==='K'?[road+'_S3D1',road+'G_S3D1',road+'_S3D120',road+'G_S3D120']:[road+'_S3D1',road+'_S3D1_G',road+'_S3D120_K',road+'_S3D120'];
  const rows=[segment(kat,1,'K',7.11,{typeVeg:'Gang- og sykkelveg'}),segment(kat,1,'G',7.12),segment(kat,120,'K',7.13),segment(kat,120,'G',7.14)];
  await replay(rows,`
   settings.categoryFilter={${kat}:true,${kat}GSV:true};
   const expected=${JSON.stringify(expected)};
   const original=rows.slice();
   for(const order of [original,original.slice().reverse()]){
    rows.splice(0,rows.length,...order);
    const all=await loadRoadsAround(62.7,7.1,1,'15');
    assert.equal(all.length,4);
    for(const [i,key] of expected.entries()){
     const r=all.find(r=>r.key===key);
     assert.equal(r.roadModel,ROAD_MODEL_VERSION);
     assert.equal(r.parts.length,1);
     assert.equal(r.gsv,!!(i%2));
     assert.equal(getRoadMetaFromKey(key).gsv,!!(i%2));
     assert.equal(r.parts[0][0][0],[7.11,7.12,7.13,7.14][i]);
    }
   }
   const county=new Map();
   for(const raw of original){rows.splice(0,rows.length,raw);addRoadsToMerge(county,await loadRoadsAround(62.7,7.1,1,'15'));}
   assert.deepEqual(finishRoadMerge(county).map(r=>r.key),expected);
  `);
 });
}

test('NVDB junctions and side facilities retain their own system, part, measures and traffic group', async()=>{
 const road=segment('F',1,'K',7.1);
 const make=(field,fields,x)=>({...segment('F',1,'K',x),vegsystemreferanse:{...road.vegsystemreferanse,[field]:fields}});
 const rows=[road,make('kryssystem',{kryssystem:1000,kryssdel:1,trafikantgruppe:'K',fra_meter:6,til_meter:26},7.2),make('kryssystem',{kryssystem:1001,kryssdel:1,trafikantgruppe:'G',fra_meter:7,til_meter:27},7.3),make('sideanlegg',{sideanlegg:3684,sideanleggsdel:1,trafikantgruppe:'K',fra_meter:8,til_meter:28},7.4)];
 await replay(rows,`
  settings.categoryFilter={F:true,FGSV:true};settings.includeSideanlegg=true;
  const all=await loadRoadsAround(62.7,7.1,1,'15');
  assert.deepEqual(all.map(r=>[r.key,r.trafikantgruppe,r.fra,r.til,r.parts.length]),[
   ['Fv61_S3D1','K',4,20,1],['Fv61_S3D1_KS1000KD1','K',6,26,1],
   ['Fv61_S3D1_KS1001KD1_G','G',7,27,1],['Fv61_S3D1_SA3684SD1','K',8,28,1]
  ]);
  assert.deepEqual(mergeRoads([...all,...all]).map(r=>r.key),all.map(r=>r.key));
  // Replay three good eastbound fixes on the physically separated junction, then inspect the logging key.
  setAreaRoads(all);gps.watching=true;gps.acc=4;gps.speed=8;gps.heading=90;
  const logged=[];
  logRoadDrivePoint=key=>logged.push(key);markDirectionDriven=persistRoadGeometry=()=>{};
  for(const lon of [7.20003,7.20009,7.20015]){gps.lastPos=[62.7,lon];updateDistancesAndActiveRoad();}
  assert.equal(gps.activeKey,'Fv61_S3D1_KS1000KD1');
  assert.deepEqual(logged,['Fv61_S3D1_KS1000KD1']);
  settings.includeSideanlegg=false;
  assert.equal((await loadRoadsAround(62.7,7.1,1,'15')).length,3);
 `);
});

test('Missing traffic groups use recorded path evidence, while an explicit K takes priority',async()=>{
 const rows=[segment('R',20,undefined,7.1,{typeVeg:'Gang- og sykkelveg'}),segment('R',21,{kode:'K',navn:'Kjørende'},7.2,{typeVeg:'Gang- og sykkelveg'}),segment('R',22,{kode:'G',navn:'Gående og syklende'},7.3)];
 await replay(rows,`
  settings.categoryFilter={R:true,RGSV:true};
  const all=await loadRoadsAround(62.7,7.1,1,'15');
  assert.deepEqual(all.map(r=>[r.key,roadFilterKey(r)]),[['Rv61_S3D20_G','RGSV'],['Rv61_S3D21','R'],['Rv61_S3D22_G','RGSV']]);
  assert.equal(roadFilterKey({kat:'K',trafikantgruppe:'K',typeVeg:'Gang- og sykkelveg',gsv:true}),'K');
  assert.equal(roadFilterKey({kat:'K',gsv:true}),'KGSV');
 `);
});

test('A subsidiary without its mandatory identity cannot silently populate the parent road',async()=>{
 const invalid=segment('F',1,'K',7.01);
 invalid.vegsystemreferanse.kryssystem={kryssdel:1,trafikantgruppe:'K'};
 await assert.rejects(replay([invalid], "await loadRoadsAround(62.7,7.1,1,'15');"),/mangler referanse/);
});
