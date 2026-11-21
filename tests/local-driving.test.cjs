const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {createAppContext} = require('./app-vm.cjs');

test('GPS entry, continuing, exit and road switching use fresh fix distances', () => {
  const context = createAppContext({assert});
  vm.runInContext(`
    roads=[0,1].map(i=>({key:'Fv' + i + '_S1D1',veg:'Fv'+i,kat:'F',seg:'S1D1',
      parts:[[[7,63+i*.02],[7.03,63+i*.02]]]}));
    gps.watching=true;gps.acc=5;gps.speed=15;gps.heading=90;
    const distance=roadDist,counts=new Map();
    roadDist=(lat,lon,r)=>{counts.set(r.key,(counts.get(r.key)||0)+1);return distance(lat,lon,r)};
    const points=[];
    logRoadDrivePoint=(key,dir)=>points.push([key,dir]);
    markDirectionDriven=persistRoadGeometry=()=>{};
    function fix(lat){
      gps.lastPos=[lat,7.015];
      counts.clear();
      updateDistancesAndActiveRoad();
      for(const n of counts.values())assert.equal(n,1);
    }
    for(let i=0;i<GPS_ENTER_CONSEC;i++)fix(63);
    assert.equal(gps.activeKey,roads[0].key);
    const pick=pickEntryCandidate;
    pickEntryCandidate=()=>{throw Error('Unexpected new candidate while the same road is active')};
    fix(63);
    assert.equal(points.at(-1)[1],'fwd');
    pickEntryCandidate=pick;
    gps.acc=50;
    for(let i=0;i<EXIT_CONSEC;i++)fix(63.02);
    assert.equal(gps.activeKey,null);
    gps.acc=5;
    for(let i=0;i<GPS_ENTER_CONSEC;i++)fix(63.02);
    assert.equal(gps.activeKey,roads[1].key);
  `, context);
});

test('Offline is remembered with the explicitly selected county and skips Geonorge', async () => {
  let external=0;
  const storage=new Map(),handlers=new Map(),elements=new Map();
  const document={
    addEventListener(){},querySelectorAll(){return []},querySelector(){return null},
    getElementById(id){
      if(!elements.has(id))elements.set(id,{value:'',dataset:{},classList:{remove(){},contains(){return false}},
        addEventListener(type,fn){handlers.set(id+' '+type,fn)}});
      return elements.get(id);
    }
  };
  const globals={document,assert,fetch:()=>{external++;throw Error('Unexpected fetch')},
    localStorage:{getItem:key=>storage.get(key),setItem:(key,val)=>storage.set(key,val)}};
  const first=createAppContext(globals);
  vm.runInContext('updateHeaderTitle=refreshCurrentCenter=closeMenu=setMessage=()=>{};settings.settingsVersion=7',first);
  const county=document.getElementById('fylke');
  county.value='15';handlers.get('fylke change').call(county);
  handlers.get('btn-offlinemode click').call(document.getElementById('btn-offlinemode'));
  const second=createAppContext(globals);
  // Stop after the real preferences/controls have been restored, before unrelated hydration.
  await vm.runInContext(`
    loadPersistentAppState=async()=>{throw Error('stop after settings')};
    bootApp().catch(e=>assert.equal(e.message,'stop after settings')).then(async()=>{
      assert.equal(document.getElementById('fylke').value,'15');
      assert.equal(document.getElementById('fylke').dataset.manual,'1');
      assert.equal(offlineMode,true);
      await updateFylkeFromPosition(62.6,7.7);
    })
  `,second);
  assert.equal(external,0);
});

test('Both maps retain overlays through offline and restore the chosen background', () => {
  const context=createAppContext({assert});
  vm.runInContext(`
    const tile=name=>({name,addTo(map){map.layers.add(this);return this}});
    const makeMap=()=>({layers:new Set(),hasLayer(layer){return this.layers.has(layer)},
      removeLayer(layer){this.layers.delete(layer)}});
    globalThis.L={control:{layers(){return {addTo(){return this},remove(){}}}}};
    const maps=[makeMap(),makeMap()], overlay=tile('roads');
    const layers=maps.map(()=>({OpenStreetMap:tile('osm'),Topo:tile('topo'),'Stabil uten kartfliser':tile('blank')}));
    for(let i=0;i<2;i++){
      configureMapBackground(maps[i],layers[i]);
      maps[i].removeLayer(layers[i].OpenStreetMap);
      (i?layers[i].Topo:layers[i]['Stabil uten kartfliser']).addTo(maps[i]);
      overlay.addTo(maps[i]);
    }
    offlineMode=true;
    for(const m of maps){configureMapBackground(m);assert.ok(m.hasLayer(overlay));assert.equal(m.layers.size,2)}
    const cold=makeMap(),fresh=layers[1];
    configureMapBackground(cold,fresh);
    assert.equal(cold.layers.size,1);assert.ok(cold.hasLayer(fresh['Stabil uten kartfliser']));
    offlineMode=false;
    maps.forEach(m=>configureMapBackground(m));
    assert.ok(maps[0].hasLayer(layers[0]['Stabil uten kartfliser']));
    assert.ok(maps[1].hasLayer(layers[1].Topo));
  `,context);
});
