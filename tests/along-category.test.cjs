const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const {createAppContext} = require('./app-vm.cjs');

function makeRoad(kat, nr, offsetM, gsv=false) {
  const lat = 63 + offsetM/111320;
  return {
    kommune:1505, geometri:{wkt:`LINESTRING(7.01 ${lat},7.015 ${lat})`},
    vegsystemreferanse:{
      vegsystem:{vegkategori:kat, fase:'V', nummer:nr},
      strekning:{strekning:1,delstrekning:1,trafikantgruppe:gsv?'G':'K'}
    }
  };
}

for(const kat of ['F','E','R']){
  test('KV-GSV along '+kat+'V fetches and caches the reference without displaying or tracking it', async () => {
    const requests=[];
    const objects=[
      makeRoad(kat,64,0), makeRoad(kat,65,2000,true),
      makeRoad('K',1,11,true), makeRoad('K',2,129.9,true),
      makeRoad('K',3,130.1,true), makeRoad('K',4,2000,true)
    ];
    const fetch=async url=>{
      requests.push(new URL(url).searchParams.get('vegsystemreferanse'));
      return {ok:true,json:async()=>({objekter:objects})};
    };
    const context=createAppContext({assert,URL,kat,fetch,indexedDB:{}});
    await vm.runInContext(`(async()=>{
      document.getElementById=()=>({value:'5',dataset:{},classList:{contains:()=>false}});
      gps.watching=true;gps.detectedFylke='15';
      renderAllViews=setMessage=()=>{};
      const tracked=[],messages=[];
      cacheGeomForTrackedRoads=list=>tracked.push(...list.map(r=>r.key));
      setMessage=text=>messages.push(text);
      const tiles=new Map();
      loadTile=async key=>tiles.get(key)??null;
      saveTile=async(key,rows)=>tiles.set(key,rows);

      settings.categoryFilter={KGSV:true};
      const oldKey=activeCountyCacheKey('15');
      settings.kvgsvLangsKat=kat;
      const refKey=activeCountyCacheKey('15');
      assert.notEqual(refKey,oldKey);
      await updateFromCenter(true,63,7.01);
      const visible=visibleRoadsList().map(r=>r.nr);
      assert.deepEqual(visible,[1,2]);
      assert.ok(roads.every(r=>r.kat==='K'));
      assert.ok(tracked.every(key=>key.startsWith('Kv')));
      assert.ok(sortedRoadCandidates(63,7.01).every(({r})=>r.kat==='K'));
      assert.equal(_kvgsvReferenceRoads.length,1);
      const stored=[...tiles.values()][0];
      assert.equal(stored.filter(r=>r.kat===kat).length,1);

      offlineMode=true;
      settings.categoryFilter[kat]=true;
      assert.equal(activeCountyCacheKey('15'),refKey);
      rememberCountyCache(refKey,{data:stored,ts:Date.now(),meta:{roadModel:ROAD_MODEL_VERSION}});
      tiles.clear();
      await updateFromCenter(true,63,7.01);
      assert.deepEqual(visibleRoadsList().filter(r=>r.kat==='K').map(r=>r.nr),visible);
      assert.ok(visibleRoadsList().some(r=>r.kat===kat));

      settings.categoryFilter[kat]=false;
      await updateFromCenter(true,63,7.01);
      assert.deepEqual(visibleRoadsList().map(r=>r.nr),visible);
      _countyCacheMem.clear();
      rememberCountyCache(oldKey,{data:stored.filter(r=>r.kat==='K'),ts:Date.now(),meta:{}});
      await updateFromCenter(true,63,7.01);
      assert.equal(roads.length,0);
      assert.ok(messages.at(-1).includes('Last ned fylkets vegnett med dette filteret'));
    })()`,context);
    assert.deepEqual(requests,[kat+'V,KV']);
  });
}

test('Changing the visible categories stops tracking the reference road before a reload completes', () => {
  const button = dataset => ({
    dataset, classList:{toggle(){}}, addEventListener(type,fn){this[type]=fn;}
  });
  const county=button({cat:'F'}),along=button({langs:'F'});
  const context=createAppContext({assert,county,along,document:{
    addEventListener(){},getElementById:()=>button({}),
    querySelectorAll:selector=>selector==='.kgsv-langs-btn'?[along]:selector==='.cat-chip'?[county]:[]
  }});
  vm.runInContext(`
    const ref={key:'Fv64_S1D1',kat:'F',parts:[[[7,63],[7.01,63]]]};
    const path={key:'Kv1505-1G_S1D1',kat:'K',trafikantgruppe:'G',parts:[[[7,63.0001],[7.01,63.0001]]]};
    roads=[ref,path];settings.categoryFilter={F:true,KGSV:true};
    gps.watching=true;gps.lastPos=[63,7];gps.activeKey=ref.key;gps.activeDir='fwd';
    saveSettings=applySettingsToUI=renderAllViews=logRoadDrivePoint=()=>{};
    let reloads=0;
    updateFromCenter=()=>{reloads++};
    along.click();
    assert.equal(settings.kvgsvLangsKat,'F');
    assert.equal(reloads,0);
    county.click();
    assert.equal(gps.activeKey,null);
    assert.equal(reloads,1);
    assert.deepEqual(roads.map(r=>r.key),[path.key]);
    assert.deepEqual(visibleRoadsList().map(r=>r.key),[path.key]);
    assert.ok(sortedRoadCandidates(63,7).every(({r})=>r.key===path.key));
    along.click();
    assert.equal(settings.kvgsvLangsKat,'');
    assert.equal(reloads,2);
    assert.equal(_kvgsvReferenceRoads.length,0);
    assert.deepEqual(roads.map(r=>r.key),[path.key]);
  `,context);
});
