const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const {createAppContext} = require('./app-vm.cjs');

function downloadContext(globals = {}) {
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) {
      elements.set(id, {value: id === 'dl-fylke' ? '15' : '10', style: {}, addEventListener() {}});
    }
    return elements.get(id);
  }
  return createAppContext({
    ...globals, assert, indexedDB: {}, confirm: () => true,
    console: {log() {}, warn() {}},
    document: {
      getElementById: element, addEventListener() {}, querySelectorAll: () => [], querySelector: () => null
    }
  });
}

function simulate(mode) {
  const context = downloadContext({mode});
  return vm.runInContext(`
    (async()=>{
      const events=[],tileWrites=[];
      const first=[[7,63],[7.01,63]],second=[[7.01,63],[7.02,63]];
      function road(parts,fra,til,extra={}){
        return {key:'Fv64_S1D1',keyBase:'Fv64_S1D1',veg:'Fv64',kat:'F',seg:'S1D1',fra,til,
          parts,partsWithMeter:parts.map(coords=>({coords,fra,til})),...extra};
      }
      const source=[
        [road([first],10,20,{typeVeg:'Bilferje'})],
        [road([[...first].reverse(),second],5,30,{kommune:'1539',typeVeg:'Veg'})]
      ];
      const old={id:'eksisterende fylke'};
      let installed=old,reads=0;
      generateTileGrid=()=>[[62,7],[63,7]];
      loadTile=async()=>null;
      loadRoadsAround=async()=>{
        const index=reads++;
        if(index===1){
          if(mode==='network')throw new Error('NVDB 503');
          if(mode==='cancel')await startOfflineDownload();
          if(mode==='filters')roadFilterRevision++;
        }
        return source[index];
      };
      saveTile=async(key,records)=>{
        if(mode==='tile-quota'&&tileWrites.length===1)throw new Error('QuotaExceededError');
        tileWrites.push(records);
      };
      saveCountyCache=async(f,records,meta)=>{
        events.push('county-write');
        assert.equal(f,'15');assert.equal(meta.tiles,2);assert.equal(meta.complete,true);
        if(mode==='county-quota')return false;
        installed=records;
        return true;
      };
      directionState.bevart={fwd:true};
      geomCache.bevart={key:'bevart',parts:[[[7,62],[7.1,62]]]};
      const oldGeometry=JSON.stringify(geomCache),oldDirection=JSON.stringify(directionState);
      const oldSkips=Array.from(skipKeys);
      cacheGeomForTrackedRoads=(records)=>{
        assert.equal(records,installed);
        events.push('tracking-after-commit');return 0;
      };
      updateProgressMap=()=>events.push('map');
      flushPendingIdbWrites=async()=>{};
      updateOfflineCacheInfo=async()=>{};
      await startOfflineDownload();
      assert.equal(JSON.stringify(geomCache),oldGeometry);
      assert.equal(JSON.stringify(directionState),oldDirection);
      assert.deepEqual(Array.from(skipKeys),oldSkips);
      assert.equal(_downloadInProgress,false);
      assert.equal(document.getElementById('dl-start').disabled,false);
      const message=document.getElementById('dl-status').textContent;
      if(mode==='success'){
        assert.match(message,/lagret som fylkes-cache/);
        assert.deepEqual(events,['county-write','tracking-after-commit','map']);
        const [r]=installed;
        assert.equal(r.ferryOnly,false);assert.equal(r.typeVeg,'Bilferje');assert.equal(r.kommune,'1539');
        assert.equal(r.fra,5);assert.equal(r.til,30);assert.equal(r.key,'Fv64_S1D1');
        assert.deepEqual(r.parts,[first,second]);
        assert.deepEqual(r.partsWithMeter,[...source[0][0].partsWithMeter,...source[1][0].partsWithMeter]);
        assert.equal(r.len,Math.round(calcPartsKm([first,second])*1000));
        assert.equal(tileWrites.length,2);
      }else{
        assert.equal(installed,old);
        assert.deepEqual(events,mode==='county-quota'?['county-write']:[]);
        assert.equal(tileWrites.length,mode==='county-quota'?2:1);
        if(mode==='network'||mode==='tile-quota')assert.match(message,/Del 2 av 2 feilet/);
        if(mode==='cancel'||mode==='filters')assert.match(message,/Avbrutt/);
        if(mode==='county-quota')assert.match(message,/kunne ikke lagres/);
      }
    })()
  `, context);
}

for (const mode of ['success','network','tile-quota','county-quota','cancel','filters']) {
  test('County download and tracking commit order: '+mode, () => simulate(mode));
}

test('Downloading from FV view saves FV and FV-GSV together and keeps the driver’s filter', async () => {
  const segments = [[1,'K'],[101,'G'],[102,'G']].map(([delstrekning,trafikantgruppe]) => ({
    type:'HOVED', detaljnivå:'Vegtrase og kjørebane', kommune:1539,
    typeVeg:trafikantgruppe==='G' ? 'Gang- og sykkelveg' : 'Enkel bilveg',
    vegsystemreferanse:{
      vegsystem:{vegkategori:'F',fase:'V',nummer:64},
      strekning:{strekning:1,delstrekning,trafikantgruppe,fra_meter:0,til_meter:50}
    },
    geometri:{wkt:'LINESTRING (7.68 62.56,7.681 62.56)'}
  }));
  const fetch = async href => {
    assert.equal(new URL(href).searchParams.get('vegsystemreferanse'),'FV');
    return {ok:true,json:async()=>({objekter:segments})};
  };
  const context = downloadContext({URL, fetch, queueMicrotask});
  await vm.runInContext(`(async()=>{
    settings.categoryFilter={F:true};
    const written=new Map();
    generateTileGrid=()=>[[62.56,7.68]];
    loadTile=async()=>null;
    saveTile=async()=>true;
    openIDB=async()=>({transaction(){
      const tx={objectStore:()=>({put:(value,key)=>written.set(key,value)})};
      queueMicrotask(()=>tx.oncomplete());
      return tx;
    }});
    saveGeomCache=()=>{};saveState=()=>{};flushPendingIdbWrites=async()=>{};
    updateOfflineCacheInfo=async()=>{};
    await startOfflineDownload();

    assert.deepEqual(settings.categoryFilter,{F:true});
    const key=activeCountyCacheKey('15',['F','FGSV']);
    const data=written.get(key).data, meta=written.get('__county_meta_'+key).value;
    assert.equal(meta.count,3);
    assert.deepEqual(meta.categoryCounts,{F:1,FGSV:2});
    assert.deepEqual(data.filter(roadPassesCategoryFilter).map(r=>r.key),['Fv64_S1D1']);
    assert.equal(Object.keys(geomCache).length,3);
    assert.match(document.getElementById('dl-status').textContent,/3 strekninger.*2 GSV/);
    settings.categoryFilter={FGSV:true};
    assert.deepEqual(data.filter(roadPassesCategoryFilter).map(r=>r.key),['Fv64_S1D101','Fv64_S1D102']);
  })()`,context);
});
