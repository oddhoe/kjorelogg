(function(root,factory){
 const api=factory();
 if(typeof module==='object'&&module.exports)module.exports=api;
 root.KjoreloggCanonical=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';

 const STATUS=Object.freeze({NOT_STARTED:'NOT_STARTED',ONE_DIRECTION:'ONE_DIRECTION',COMPLETED:'COMPLETED',SKIPPED:'SKIPPED'});
 const EXCEL_COMPLETED_RGB='FF92D050';

 function numberOrNull(value){
  if(value===null||value===undefined||value==='')return null;
  const n=typeof value==='number'?value:Number(String(value).trim().replace(',','.').replace(/\s/g,''));
  return Number.isFinite(n)?n:null;
 }
 function integerOrZero(value){const n=numberOrNull(value);return n===null?0:Math.trunc(n)}
 function formatPlanNumber(value){
  const n=numberOrNull(value);
  if(n===null)throw new Error('Ugyldig meterverdi i asfaltplan-key');
  return n.toFixed(3).replace(/\.0+$/,'').replace(/(\.\d*?)0+$/,'$1');
 }
 function normalizeToken(value){
  const text=String(value??'').trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
  return text.replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'')||'-';
 }
 function planYearFromRecord(record){
  const explicit=integerOrZero(record?.planYear??record?.plan_year);
  if(explicit>=2000&&explicit<=2200)return explicit;
  for(const value of[record?.asfaltDato,record?.asphaltDate,record?.asphalt_date,record?.source,record?.sourceName,record?.source_name]){
   const match=String(value??'').match(/\b(20\d{2})\b/);
   if(match)return Number(match[1]);
  }
  throw new Error('Planår mangler for asfaltparsell');
 }
 function compareRef(a,b){return a.s-b.s||a.d-b.d||a.m-b.m}
 function makeAsphaltPlanKey(record){
  const county=String(record?.countyId??record?.county_id??record?.fylke??'15').trim();
  const category=String(record?.roadCategory??record?.road_category??record?.kat??'F').trim().toUpperCase();
  const roadNumber=integerOrZero(record?.roadNumber??record?.road_number??record?.nr);
  if(!county||!['E','R','F','K'].includes(category)||roadNumber<=0)throw new Error('Ugyldig fylke/kategori/vegnummer i asfaltplan-key');
  const a={s:integerOrZero(record?.fromS??record?.from_s??record?.fraS),d:integerOrZero(record?.fromD??record?.from_d??record?.fraD),m:numberOrNull(record?.fromM??record?.from_m??record?.fraM)};
  const b={s:integerOrZero(record?.toS??record?.to_s??record?.tilS),d:integerOrZero(record?.toD??record?.to_d??record?.tilD),m:numberOrNull(record?.toM??record?.to_m??record?.tilM)};
  if(a.m===null||b.m===null||a.s<0||a.d<0||b.s<0||b.d<0||a.m<0||b.m<0)throw new Error('Ugyldig VSR i asfaltplan-key');
  const low=compareRef(a,b)<=0?a:b,high=low===a?b:a,year=planYearFromRecord(record);
  const lowRef=`s${low.s}d${low.d}m${formatPlanNumber(low.m)}`,highRef=`s${high.s}d${high.d}m${formatPlanNumber(high.m)}`;
  return `asphalt:v1:${county}:${category}${roadNumber}:${lowRef}-${highRef}:${year}:${normalizeToken(record?.contract??record?.kontrakt)}`;
 }

 function normalizeRgb(value){
  let rgb=String(value??'').replace(/^#/,'').toUpperCase();
  if(rgb.length===6)rgb='FF'+rgb;
  return rgb;
 }
 function cellFill(cell){
  const style=cell?.s;
  if(!style||typeof style!=='object')return null;
  return style.fill&&typeof style.fill==='object'?style.fill:style;
 }
 function isVerifiedExcelGreenCell(cell){
  const fill=cellFill(cell);
  if(!fill)return false;
  const pattern=String(fill.patternType??fill.fillType??'').toLowerCase();
  const foreground=fill.fgColor??fill.foregroundColor??fill.foreground??{};
  const rgb=normalizeRgb(typeof foreground==='string'?foreground:foreground.rgb);
  return pattern==='solid'&&rgb===EXCEL_COMPLETED_RGB;
 }
 // Exactly the seven required identity cells: Nr, FraS, FraDs, FraM, TilS, TilDs, TilM.
 function isExcelAsphaltCompleted(identityCells){
  return Array.isArray(identityCells)&&identityCells.length===7&&identityCells.every(isVerifiedExcelGreenCell);
 }

 function resolveAsphaltImportStatus(existingStatus,sourceCompleted){
  const existing=Object.values(STATUS).includes(existingStatus)?existingStatus:null;
  if(existing===STATUS.SKIPPED&&sourceCompleted){
   return{status:STATUS.SKIPPED,conflict:'SKIPPED_VS_EXCEL_COMPLETED',sourceApplied:false};
  }
  if(sourceCompleted&&(!existing||existing===STATUS.NOT_STARTED||existing===STATUS.ONE_DIRECTION)){
   return{status:STATUS.COMPLETED,conflict:null,sourceApplied:true};
  }
  return{status:existing||(sourceCompleted?STATUS.COMPLETED:STATUS.NOT_STARTED),conflict:null,sourceApplied:!!sourceCompleted&&!existing};
 }
 function localStatusForKey(key,state,options={}){
  const direction=state?.directionState?.[key]||{};
  if(state?.skipKeys?.has?.(key)||Array.isArray(state?.skipKeys)&&state.skipKeys.includes(key))return STATUS.SKIPPED;
  if(direction.manualFull||direction.sourceCompleted)return STATUS.COMPLETED;
  const fwd=!!direction.fwd,rev=!!direction.rev;
  if(!fwd&&!rev){
   if(state?.drivenKeys?.has?.(key)||Array.isArray(state?.drivenKeys)&&state.drivenKeys.includes(key))return STATUS.COMPLETED;
   if(state?.oneWayKeys?.has?.(key)||Array.isArray(state?.oneWayKeys)&&state.oneWayKeys.includes(key))return STATUS.ONE_DIRECTION;
   return STATUS.NOT_STARTED;
  }
  if(typeof options.getRoadStatus==='function'){
   const status=options.getRoadStatus(key);
   if(status==='done')return STATUS.COMPLETED;
   if(status==='oneway')return STATUS.ONE_DIRECTION;
  }
  if(typeof options.isOneWay==='function'&&options.isOneWay(key))return STATUS.COMPLETED;
  return fwd&&rev?STATUS.COMPLETED:STATUS.ONE_DIRECTION;
 }
 function latestIso(values){
  const timestamps=values.map(Number).filter(Number.isFinite);
  return timestamps.length?new Date(Math.max(...timestamps)).toISOString():null;
 }
 function commentValue(value){return typeof value==='string'?value:String(value?.text??'')||null}

 function resolveCanonicalRoadProgress(state,options={}){
  const keys=new Set();
  for(const setName of['drivenKeys','oneWayKeys','skipKeys','deletedGeomKeys'])for(const key of state?.[setName]||[])keys.add(key);
  for(const objectName of['directionState','routeLog','geomCache','roadComments'])for(const key of Object.keys(state?.[objectName]||{}))keys.add(key);
  const out=[];
  for(const key of[...keys].sort()){
   if(String(key).startsWith('ASPHALT::'))continue;
   const direction=state?.directionState?.[key]||{},geometry=state?.geomCache?.[key]||{},comment=state?.roadComments?.[key];
   const status=localStatusForKey(key,state,options),legacyDirection=!state?.directionState?.[key];
   let fwd=!!direction.fwd,rev=!!direction.rev;
   if(legacyDirection&&status===STATUS.ONE_DIRECTION)fwd=true;
   const measured=latestIso([direction.manualTs,direction.fwdLastTs,direction.revLastTs,comment?.ts]);
   out.push({road_key:key,road_key_version:1,status,direction_fwd:fwd,direction_rev:rev,manual_full:!!direction.manualFull,single_direction:typeof options.isOneWay==='function'?!!options.isOneWay(key):false,measured_at:measured,comment:commentValue(comment),county_id:String(geometry.fylke||'')||null,road_category:geometry.kat||null,road_number:numberOrNull(geometry.nr),segment:geometry.seg||null,length_km:Number.isFinite(Number(geometry.len))?Number(geometry.len)/1000:null,client_updated_at:measured,warnings:legacyDirection&&status!==STATUS.NOT_STARTED?[status===STATUS.ONE_DIRECTION?'LEGACY_DIRECTION_INFERRED':'LEGACY_DIRECTION_UNKNOWN']:[]});
  }
  return out;
 }
function resolveCanonicalAsphaltProgress(state,options={}){
  return(state?.asphaltPlan||[]).map(record=>{
   const planKey=record.planKey||record.plan_key||makeAsphaltPlanKey(record),legacyKey=`ASPHALT::${String(record.legacyId||record.legacy_id||record.id||'')}`,stableKey=`ASPHALT::${planKey}`;
   const hasStable=!!(state?.directionState?.[stableKey]||state?.roadComments?.[stableKey]||state?.drivenKeys?.has?.(stableKey)||state?.oneWayKeys?.has?.(stableKey)||state?.skipKeys?.has?.(stableKey));
   const key=hasStable?stableKey:legacyKey;
   const existing=localStatusForKey(key,state,options),resolved=resolveAsphaltImportStatus(existing,!!record.sourceCompleted);
   const direction=state?.directionState?.[key]||{},comment=state?.roadComments?.[key],clientUpdatedAt=latestIso([direction.manualTs,direction.fwdLastTs,direction.revLastTs,comment?.ts,record.sourceImportedAt]);
   return{plan_key:planKey,road_number:integerOrZero(record.nr),from_s:integerOrZero(record.fraS),from_d:integerOrZero(record.fraD),from_m:numberOrNull(record.fraM),to_s:integerOrZero(record.tilS),to_d:integerOrZero(record.tilD),to_m:numberOrNull(record.tilM),plan_year:planYearFromRecord(record),contract:record.kontrakt??record.contract??null,status:resolved.status,source_completed:!!record.sourceCompleted,source_completed_reason:record.sourceCompletedReason||null,comment:commentValue(comment),client_updated_at:clientUpdatedAt,conflict:record.sourceStatusConflict||resolved.conflict};
  });
 }

 return{STATUS,EXCEL_COMPLETED_RGB,normalizeToken,formatPlanNumber,planYearFromRecord,makeAsphaltPlanKey,isVerifiedExcelGreenCell,isExcelAsphaltCompleted,resolveAsphaltImportStatus,resolveLocalStatus:localStatusForKey,resolveCanonicalRoadProgress,resolveCanonicalAsphaltProgress};
});
