const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const {createAppContext} = require('./app-vm.cjs');

function profileTest(scenario) {
  const context = createAppContext({
    assert, indexedDB: {}, IDBKeyRange: {bound:(lower,upper)=>({lower,upper})}, queueMicrotask
  });
  return vm.runInContext(`
    (async()=>{
      const payloads=new Map(), metadata=new Map(), geometryReads=[];
      // Enqueue IDB request callbacks before the transaction's complete event.
      openIDB=async()=>({
        transaction(){
          let pending=0;
          const tx={objectStore(name){
            function request(value){
              pending++;
              const req={result:value};
              queueMicrotask(()=>{
                req.onsuccess?.();
                if(--pending===0)tx.oncomplete?.();
              });
              return req;
            }
            return {
              getAllKeys:({lower,upper})=>request([...payloads.keys()].filter(k=>k>=lower&&k<=upper)),
              get(key){
                if(name===IDB_META_STORE)return request(metadata.get(key));
                geometryReads.push(key);
                return request(payloads.get(key));
              }
            };
          }};
          return tx;
        }
      });
      function seed(cats,updates={},county='15'){
        const key=activeCountyCacheKey(county,cats),data=cats.map((c,i)=>({key:'test'+i,category:c}));
        const meta={count:data.length,cat:cats.join('-'),complete:true,roadModel:ROAD_MODEL_VERSION,errors:0,
          categoryCounts:Object.fromEntries(cats.map(k=>[k,1])),...updates};
        payloads.set(key,{data,meta:{...meta},ts:Date.now()});
        metadata.set('__county_meta_'+key,{value:{...meta,ts:Date.now()}});
        return key;
      }
      settings.categoryFilter={F:true};
      const F=['F','FGSV'],R=['R','RGSV'],E=['E','EGSV'],K=['K','KGSV'];
      ${scenario}
    })()
  `,context);
}

test('Exact and smallest paired package have priority; county, flags and reference category match',()=>profileTest(`
  const all=seed([...E,...R,...F,...K]), fk=seed([...F,...K]), f=seed(F);
  const exact=activeCountyCacheKey('15');
  assert.equal(await preferredCountyCacheKey('15'),f);
  seed(['F']); assert.equal(await preferredCountyCacheKey('15'),exact);
  settings.categoryFilter={KGSV:true};settings.kvgsvLangsKat='F';
  assert.equal(await preferredCountyCacheKey('15'),fk);
  settings.includeSideanlegg=true;
  const sideExact=activeCountyCacheKey('15'),sideAll=seed([...E,...R,...F,...K]);
  seed(F,{},'18');
  assert.equal(await preferredCountyCacheKey('15'),sideAll);
  settings.includeRamper=true;
  assert.equal(await preferredCountyCacheKey('15'),activeCountyCacheKey('15'));
  assert.notEqual(await preferredCountyCacheKey('15'),sideExact);
  assert.deepEqual(geometryReads,[]);
`));

test('Orphan metadata, incomplete packages, invalid counts and a legacy exact profile cannot mask a valid package',()=>profileTest(`
  const all=seed([...E,...R,...F,...K]), orphan=seed(F), partial=seed([...R,...F],{complete:false});
  const nonpaired=seed(['E','F','FGSV']),legacy=seed(['F'],{roadModel:2});
  payloads.delete(orphan);
  seed([...F,...K],{categoryCounts:{F:80,FGSV:0,K:0,KGSV:0}});
  assert.equal(await preferredCountyCacheKey('15'),all);
  assert.deepEqual(geometryReads,[]);
  assert.equal((await loadCountyCache('15')).key,all);
  assert.deepEqual(geometryReads,[all]);
  payloads.delete(all);_countyCacheMem.clear();
  assert.equal(await preferredCountyCacheKey('15'),legacy);
  assert.equal((await loadCountyCache('15')).meta.roadModel,2);
`));

test('A malformed smaller payload falls through to the next valid package',()=>profileTest(`
  const all=seed([...E,...R,...F,...K]), small=seed(F), exact=seed(['F']);
  payloads.get(small).data.length=0;
  payloads.get(exact).meta.cat='R';
  assert.equal((await loadCountyCache('15')).key,all);
  assert.deepEqual(geometryReads,[exact,small,all]);
`));

test('An empty subgroup in a complete paired package is legitimate',()=>profileTest(`
  const all=seed([...E,...R,...F,...K]);
  const f=seed(F,{categoryCounts:{F:2,FGSV:0}});
  settings.categoryFilter={FGSV:true};
  assert.equal(await preferredCountyCacheKey('15'),f);
`));
