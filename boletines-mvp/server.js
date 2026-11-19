import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {GoogleAuth} from 'google-auth-library';

const __dirname=path.dirname(fileURLToPath(import.meta.url));
const port=Number(process.env.PORT||10000), dataDir=process.env.DATA_DIR||'/tmp/observatorio-boletines';
fs.mkdirSync(dataDir,{recursive:true});
const storeFile=path.join(dataDir,'store.json');
const adminPassword=process.env.ADMIN_PASSWORD||'';
const initialized=adminPassword.length>=12 && !!process.env.SESSION_SECRET && process.env.SESSION_SECRET.length>=32;
let store={users:{},history:[],jobs:[],previews:{}};
try{store=JSON.parse(fs.readFileSync(storeFile,'utf8'))}catch{}
store.users ||= {};store.history ||= [];store.jobs ||= [];store.previews ||= {};store.automation ||= {lastRun:null,lastResult:'No ejecutado'};
const dataPersistent=!!process.env.DATA_DIR && process.env.DATA_DIR!=='/tmp/observatorio-boletines'; // Requires a real persistent Render disk
function persist(){fs.writeFileSync(storeFile,JSON.stringify(store,null,2),{mode:0o600})}
function log(user,action,status,detail=''){store.history.unshift({at:new Date().toISOString(),user,action,status,detail:String(detail).slice(0,160)});store.history=store.history.slice(0,250);persist()}
function passhash(value,salt=crypto.randomBytes(16).toString('hex')){return salt+':'+crypto.scryptSync(value,salt,64).toString('hex')}
function passverify(value,stored){try{const [salt]=stored.split(':');return crypto.timingSafeEqual(Buffer.from(passhash(value,salt)),Buffer.from(stored))}catch{return false}}
function sign(payload){const content=Buffer.from(JSON.stringify(payload)).toString('base64url');return content+'.'+crypto.createHmac('sha256',process.env.SESSION_SECRET).update(content).digest('base64url')}
function verify(token){try{const [content,sig]=String(token).split('.');if(!sig)return null;const expected=crypto.createHmac('sha256',process.env.SESSION_SECRET).update(content).digest('base64url');if(!crypto.timingSafeEqual(Buffer.from(sig),Buffer.from(expected)))return null;const p=JSON.parse(Buffer.from(content,'base64url'));return p.exp>Date.now()?p:null}catch{return null}}
function session(req){let token=(req.headers.cookie||'').split('; ').find(s=>s.startsWith('obs_session='))?.slice(12);let s=verify(token);if(!s)return null;if(s.username==='admin')return {username:'admin',role:'admin'};if(!store.users[s.username]||store.users[s.username].disabled)return null;return {username:s.username,role:'member'}}
function send(res,status,data,headers={}){res.writeHead(status,{'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff',...headers});res.end(JSON.stringify(data))}
function fail(res,status,error){send(res,status,{error})}
function body(req){return new Promise((resolve,reject)=>{let raw='';req.on('data',d=>{raw+=d;if(raw.length>50000){reject(Error('Solicitud demasiado grande'));req.destroy()}});req.on('end',()=>{try{resolve(JSON.parse(raw||'{}'))}catch{reject(Error('JSON inválido'))}});req.on('error',reject)})}
function cookie(token){return 'obs_session='+token+'; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=28800'}
const attempts=new Map();
function throttle(key){const now=Date.now();let a=attempts.get(key)||[];a=a.filter(x=>now-x<600000);a.push(now);attempts.set(key,a);return a.length>8}
function safeConfig(){return {initialized,automation:{enabled:process.env.AUTO_SYNC_ENABLED==='true',lastRun:store.automation.lastRun,lastResult:store.automation.lastResult},integrations:{
'Google Sheets (01 y 03)':process.env.GOOGLE_SERVICE_ACCOUNT_JSON?'Credencial configurada':'Sin credencial',
'Mapeo verificado hacia salida 07':process.env.FIELD_MAPPING_JSON?'Configurado (requiere comprobación)':'Pendiente',
'Controles QA del archivo 07':process.env.REQUIRE_07_QA==='false'?'Desactivados por configuración':'Obligatorios',
'Automatización programada':process.env.AUTO_SYNC_ENABLED==='true'?'Habilitada (requiere servicio activo)':'Desactivada',
'Canva (copia autorizada)':process.env.CANVA_ACCESS_TOKEN&&process.env.CANVA_TEST_DESIGN_ID?'Configurado':'Pendiente',
'Envíos a Canva':process.env.ENABLE_CANVA_WRITES==='true'?'Habilitados por configuración':'Desactivados (seguro)',
'Persistencia de cuentas':dataPersistent?'Directorio configurado: comprobar disco persistente':'Volátil: creación de usuarios deshabilitada'
}}}
const ids={SEPTIEMBRE:{'01':'1pWN78WnqK85X9e1AxuWnJ8_8afJ7yfBxFUBXybtBrrU','03':'1FqDSBhahYp9IchMIlzN_xhuyVBd2k8EzKIyEMJRCJOU','07':'1BO4yodj8oGWagTVqD6pGiXLDrwF5F7rcdFCAwvT-D8s'}};
function monthConfig(month){if(month==='SEPTIEMBRE')return ids.SEPTIEMBRE;try{return JSON.parse(process.env.MONTH_SHEETS_JSON||'{}')[month]||null}catch{return null}}
function mappings(){try{const m=JSON.parse(process.env.FIELD_MAPPING_JSON||'[]');if(!Array.isArray(m))return [];return m}catch{return []}}
let authCache={token:'',until:0};
async function googleToken(){if(authCache.token&&Date.now()<authCache.until)return authCache.token;
const json=process.env.GOOGLE_SERVICE_ACCOUNT_JSON;if(!json)throw Error('Falta GOOGLE_SERVICE_ACCOUNT_JSON. Comparte los libros con la cuenta de servicio.');
const credentials=JSON.parse(json);
const auth=new GoogleAuth({credentials,scopes:['https://www.googleapis.com/auth/spreadsheets.readonly']});
const client=await auth.getClient();const response=await client.getAccessToken();if(!response.token)throw Error('No se pudo obtener token de Google');authCache={token:response.token,until:Date.now()+45*60000};return response.token}
async function sheetMetadata(id){
 const token=await googleToken();
 const response=await fetch('https://sheets.googleapis.com/v4/spreadsheets/'+encodeURIComponent(id)+'?fields=properties(title),sheets(properties(title,gridProperties(rowCount,columnCount)))',{headers:{Authorization:'Bearer '+token}});
 if(!response.ok)throw Error('No se pudo consultar el libro: Google HTTP '+response.status);
 const obj=await response.json();
 return {title:obj.properties?.title||'',sheets:(obj.sheets||[]).map(x=>({name:x.properties?.title||'',rows:x.properties?.gridProperties?.rowCount||0}))};
}
async function qualityCheck(month){
 const cfg=monthConfig(month);if(!cfg?.['07'])throw Error('Falta el archivo 07 de referencia para verificar controles QA');
 const [authorized,states,fields]=await Promise.all([
 sheetValues(cfg['07'],"'00_INDICE_PAGINAS'!L2"),
 sheetValues(cfg['07'],"'QA_PUBLICACION'!L2:L5"),
 sheetValues(cfg['07'],"'CAMPOS_CANVA'!D2:D500")
 ]);
 const gate=authorized[0]?.[0];
 if(gate!==true&&String(gate).toUpperCase()!=='TRUE')throw Error('07: autorización 00_INDICE_PAGINAS!L2 no activada');
 const checks=states.map(x=>String(x[0]??'').trim().toUpperCase());
 if(checks.some(x=>!x||x.includes('NO PUBLICAR')||x.includes('PENDIENTE')||x.includes('BLOQUE')))throw Error('07: control QA pendiente o bloqueado');
 const tags=fields.map(r=>String(r[0]||'').trim()).filter(Boolean);
 if(new Set(tags).size!==tags.length)throw Error('07: etiquetas Canva duplicadas');
 return {tags,checks};
}
async function sheetValues(id,range){const token=await googleToken();const r=await fetch('https://sheets.googleapis.com/v4/spreadsheets/'+encodeURIComponent(id)+'/values/'+encodeURIComponent(range)+'?valueRenderOption=UNFORMATTED_VALUE',{headers:{Authorization:'Bearer '+token}});if(!r.ok)throw Error('Google Sheets '+r.status+' al leer '+range+' (verifica nombre de hoja y permisos)');const o=await r.json();return o.values||[]}
function numeric(value){if(typeof value==='number')return Number.isFinite(value)?value:null;const s=String(value??'').trim();if(!s)return null;const clean=s.replace(/\s/g,'');let t=clean;if(/^-?\d{1,3}(\.\d{3})+(,\d+)?$/.test(t))t=t.replace(/\./g,'').replace(',','.');else if(/^-?\d{1,3}(,\d{3})+(\.\d+)?$/.test(t))t=t.replace(/,/g,'');else if(/^[-+]?\d+,\d+$/.test(t))t=t.replace(',','.');if(!/^[-+]?\d+(\.\d+)?$/.test(t))return null;const n=Number(t);return Number.isFinite(n)?n:null}
function formatNumber(value){return new Intl.NumberFormat('es-CO',{maximumFractionDigits:2}).format(value)}
function hash(obj){return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex')}
const allowedMonths=new Set(['ENERO','FEBRERO','MARZO','ABRIL','MAYO','JUNIO','JULIO','AGOSTO','SEPTIEMBRE','OCTUBRE','NOVIEMBRE','DICIEMBRE']);
async function previewVerified07(user,req){
 const month=String(req.month||'').toUpperCase(),year=Number(req.year);
 if(!allowedMonths.has(month)||!Number.isInteger(year)||year<2025||year>2100)throw Error('Periodo inválido');
 const cfg=monthConfig(month);
 if(!cfg?.['07'])throw Error('No hay archivo 07 configurado para '+month);
 const qa=await qualityCheck(month);
 const data=await sheetValues(cfg['07'],"'SYNC_CANVA_INTERNO'!A2:E17");
 if(data.length!==16)throw Error('07: se requieren 16 filas en SYNC_CANVA_INTERNO!A2:E17');
 const fields=data.map((row,i)=>{
  const key=String(row[0]??'').trim();
  const value=String(row[4]??'').trim();
  if(!/^[A-Z0-9_]{3,100}$/.test(key))throw Error('07: etiqueta inválida en fila '+(i+2));
  if(!value||value.length>500||!/\d/.test(value))throw Error('07: valor sin cifras en '+key);
  if(!qa.tags.includes(key))throw Error('07: etiqueta no registrada en CAMPOS_CANVA: '+key);
  return {key,value,source:'07!SYNC_CANVA_INTERNO!E'+(i+2)};
 });
 if(new Set(fields.map(x=>x.key)).size!==16)throw Error('07: etiquetas duplicadas o incompletas');
 const previewId=crypto.randomUUID();
 const fingerprint=hash({month,year,fields,design:process.env.CANVA_TEST_DESIGN_ID||null,source:'07'});
 const enabled=process.env.ENABLE_CANVA_WRITES==='true'&&!!process.env.CANVA_ACCESS_TOKEN&&!!process.env.CANVA_TEST_DESIGN_ID;
 store.previews[previewId]={user:user.username,created:Date.now(),month,year,fields,fingerprint,canSync:enabled,sourceMode:'07'};
 log(user.username,'preview 07 '+month,'OK','16 campos del archivo verificado');
 return {month,year,fields,previewId,fingerprint,canSync:enabled,sourceMode:'07'};
}
async function preview(user,req){
const month=String(req.month||'').toUpperCase(),year=Number(req.year);
if(!allowedMonths.has(month)||!Number.isInteger(year)||year<2025||year>2100)throw Error('Periodo inválido');
const cfg=monthConfig(month);if(!cfg?.['01']||!cfg?.['03'])throw Error('No están configuradas las fuentes 01 y 03 para '+month);
const mapping=mappings();if(!mapping.length)throw Error('No existe FIELD_MAPPING_JSON con referencias validadas desde 01/03 hasta los campos de Canva.');
if(mapping.length>500)throw Error('Demasiados campos');
const fields=[];
const qa=process.env.REQUIRE_07_QA==='false'?null:await qualityCheck(month);
for(const entry of mapping){
if(!['01','03'].includes(entry.source)||typeof entry.range!=='string'||!/^[\p{L}\d _-]+![A-Z]{1,3}[1-9]\d*$/u.test(entry.range)||!/^([A-Z0-9_]{3,100})$/.test(entry.key))throw Error('Mapeo inválido: '+String(entry.key));
let arr=await sheetValues(cfg[entry.source],entry.range);let v=numeric(arr[0]?.[0]);if(v===null)throw Error('Cifra ausente o inválida en '+entry.source+' '+entry.range);
fields.push({key:entry.key,value:formatNumber(v),numericValue:v,source:entry.source+'!'+entry.range});
}
if(new Set(fields.map(x=>x.key)).size!==fields.length)throw Error('Etiquetas repetidas');
if(qa){const missing=fields.filter(x=>!qa.tags.includes(x.key));if(missing.length)throw Error('Etiquetas ausentes en CAMPOS_CANVA de 07: '+missing.map(x=>x.key).join(', '));}
const previewId=crypto.randomUUID();const fingerprint=hash({month,year,fields,design:process.env.CANVA_TEST_DESIGN_ID||null});
const enabled=process.env.ENABLE_CANVA_WRITES==='true'&&!!process.env.CANVA_ACCESS_TOKEN&&!!process.env.CANVA_TEST_DESIGN_ID;
const result={month,year,fields,previewId,fingerprint,canSync:enabled};
store.previews[previewId]={user:user.username,created:Date.now(),month,year,fields,fingerprint,canSync:enabled};
for(const k of Object.keys(store.previews))if(Date.now()-store.previews[k].created>900000)delete store.previews[k];
log(user.username,'preview '+month,'OK',String(fields.length)+' campos');return result}
let locked=false;
async function sync(user,p){
const x=store.previews[String(p.previewId||'')];if(!x||Date.now()-x.created>900000)throw Error('Vista previa caducada; vuelve a generar.');
if(!x.canSync||process.env.ENABLE_CANVA_WRITES!=='true')throw Error('Envío desactivado');
if(store.jobs.some(j=>j.design===process.env.CANVA_TEST_DESIGN_ID&&j.status==='in_progress'))throw Error('Existe un trabajo pendiente sobre esta copia; consulta su resultado primero');
if(locked)throw Error('Ya existe un envío en curso');locked=true;
try{
const cfg=monthConfig(x.month);
 if(process.env.REQUIRE_07_QA!=='false')await qualityCheck(x.month);
 if(x.sourceMode==='07'){
   const fresh=await sheetValues(cfg['07'],"'SYNC_CANVA_INTERNO'!A2:E17");
   if(fresh.length!==x.fields.length||fresh.some((r,i)=>String(r[0]??'').trim()!==x.fields[i].key||String(r[4]??'').trim()!==x.fields[i].value))throw Error('El archivo 07 cambió después de la vista previa');
 }else{
   const mapping=mappings();if(mapping.length!==x.fields.length)throw Error('Mapeo modificado; vuelve a generar');
   for(let i=0;i<mapping.length;i++){const m=mapping[i],source=cfg[m.source];const values=await sheetValues(source,m.range);const value=numeric(values[0]?.[0]);if(value!==x.fields[i].numericValue)throw Error('Los datos cambiaron después de la vista previa')}
 }
if(store.jobs.some(j=>j.fingerprint===x.fingerprint&&j.status!=='failed'))throw Error('Estos datos ya fueron enviados o existe un trabajo pendiente');
const design=process.env.CANVA_TEST_DESIGN_ID,token=process.env.CANVA_ACCESS_TOKEN;
const dis=await fetch('https://api.canva.com/rest/v1/designs/'+encodeURIComponent(design),{headers:{Authorization:'Bearer '+token}});if(!dis.ok)throw Error('No se pudo verificar el destino de Canva: HTTP '+dis.status);
const info=(await dis.json()).design||{};if(info.id!==design||!/PRUEBA|COPIA/i.test(info.title||''))throw Error('El destino no está identificado como copia de prueba');
const ds=await fetch('https://api.canva.com/rest/v1/designs/'+encodeURIComponent(design)+'/dataset',{headers:{Authorization:'Bearer '+token}});if(!ds.ok)throw Error('No se pudo consultar dataset Canva: HTTP '+ds.status);
const dataset=(await ds.json()).dataset||{};for(const f of x.fields){if(dataset[f.key]?.type!=='text')throw Error('El campo '+f.key+' no existe o no es de texto en Canva')}
const payload={type:'update_design',design_id:design,data:Object.fromEntries(x.fields.map(f=>[f.key,{type:'text',text:f.value}]))};
const response=await fetch('https://api.canva.com/rest/v1/autofills',{method:'POST',headers:{Authorization:'Bearer '+token,'content-type':'application/json'},body:JSON.stringify(payload)});
if(!response.ok)throw Error('Canva rechazó el envío: HTTP '+response.status);
const result=(await response.json()).job||{};if(!result.id)throw Error('Canva no devolvió identificador de trabajo');
store.jobs.unshift({jobId:result.id,fingerprint:x.fingerprint,design,status:result.status||'in_progress',month:x.month,user:user.username,at:new Date().toISOString()});delete store.previews[p.previewId];
log(user.username,'sync '+x.month,'SOLICITUD ACEPTADA',result.id);return {jobId:result.id,status:result.status||'in_progress'}
}finally{locked=false}}
async function reconcileJobs(){
 if(!process.env.CANVA_ACCESS_TOKEN)return {checked:0,updated:0};
 let checked=0,updated=0;
 for(const job of store.jobs.filter(j=>j.status==='in_progress').slice(0,20)){
  checked++;
  try{
   const response=await fetch('https://api.canva.com/rest/v1/autofills/'+encodeURIComponent(job.jobId),{headers:{Authorization:'Bearer '+process.env.CANVA_ACCESS_TOKEN}});
   if(!response.ok)throw Error('HTTP '+response.status);
   const result=(await response.json()).job;
   if(!result||result.id!==job.jobId)throw Error('ID de Canva no corresponde');
   if(result.status==='success'){
    if(result.result?.type!=='update_design'||result.result?.design?.id!==job.design)throw Error('Canva devolvió un diseño distinto al autorizado');
    job.status='success';updated++;log('sistema','confirmar Canva '+job.month,'COMPLETADO',job.jobId);
   }else if(result.status==='failed'){job.status='failed';updated++;log('sistema','confirmar Canva '+job.month,'FALLIDO',job.jobId)}
  }catch(e){console.error('Consulta Canva',job.jobId,String(e.message).slice(0,100))}
 }
 if(updated)persist();
 return {checked,updated};
}
let timerBusy=false;
async function automaticCycle(){
 if(timerBusy||process.env.AUTO_SYNC_ENABLED!=='true'||process.env.ENABLE_CANVA_WRITES!=='true'||!initialized||!dataPersistent)return;
 timerBusy=true;store.automation.lastRun=new Date().toISOString();
 try{
  await reconcileJobs();
  const months=String(process.env.AUTO_SYNC_MONTHS||'SEPTIEMBRE').split(',').map(x=>x.trim().toUpperCase()).filter(x=>allowedMonths.has(x));
  for(const month of months){
   if(store.jobs.some(j=>j.month===month&&j.status==='in_progress'))continue;
   try{
    const mode=process.env.AUTO_SYNC_SOURCE_MODE||'07';
    const p=await (mode==='07'?previewVerified07:preview)({username:'sistema'}, {month,year:Number(process.env.AUTO_SYNC_YEAR||new Date().getFullYear())});
    if(p.canSync&&!store.jobs.some(j=>j.fingerprint===p.fingerprint&&j.status!=='failed'))await sync({username:'sistema'},{previewId:p.previewId});
   }catch(e){console.error('Automatización',month,String(e.message).slice(0,160))}
  }
  store.automation.lastResult='Ciclo realizado; revisar historial y trabajos';
 }catch(e){store.automation.lastResult='Error: '+String(e.message).slice(0,120)}
 finally{persist();timerBusy=false}
}
if(process.env.AUTO_SYNC_ENABLED==='true')setInterval(automaticCycle,Math.max(5,Number(process.env.AUTO_SYNC_MINUTES||15))*60000).unref();
async function handler(req,res){
const url=new URL(req.url,'http://localhost');
if(url.pathname==='/health'){return send(res,200,{ok:true,configured:initialized})}
if(url.pathname==='/'&&req.method==='GET'){res.writeHead(200,{'content-type':'text/html; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff','content-security-policy':"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"});return fs.createReadStream(path.join(__dirname,'public','index.html')).pipe(res)}
if(!url.pathname.startsWith('/api/'))return fail(res,404,'No encontrado');
if(req.method==='POST'){const origin=req.headers.origin,host=req.headers.host;if(origin&&new URL(origin).host!==host)return fail(res,403,'Origen no permitido')}
if(url.pathname==='/api/status'&&req.method==='GET')return send(res,200,safeConfig());
if(!initialized)return fail(res,503,'Configuración inicial pendiente: ADMIN_PASSWORD y SESSION_SECRET');
if(url.pathname==='/api/login'&&req.method==='POST'){
if(throttle(req.socket.remoteAddress||'unknown'))return fail(res,429,'Demasiados intentos; intenta más tarde');
const b=await body(req);const username=String(b.username||'').trim().toLowerCase(),password=String(b.password||'');
const ok=username==='admin'?crypto.timingSafeEqual(Buffer.from(crypto.createHash('sha256').update(password).digest('hex')),Buffer.from(crypto.createHash('sha256').update(adminPassword).digest('hex'))):store.users[username]&&!store.users[username].disabled&&passverify(password,store.users[username].hash);
if(!ok)return fail(res,401,'Credenciales incorrectas');
return send(res,200,{ok:true},{'set-cookie':cookie(sign({username,exp:Date.now()+8*3600000}))})}
if(url.pathname==='/api/logout'&&req.method==='POST')return send(res,200,{ok:true},{'set-cookie':'obs_session=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0'});
const me=session(req);if(!me)return fail(res,401,'Sesión requerida');
if(url.pathname==='/api/me'&&req.method==='GET')return send(res,200,me);
if(url.pathname==='/api/history'&&req.method==='GET')return send(res,200,{items:store.history.slice(0,50)});
if(url.pathname==='/api/jobs'&&req.method==='GET')return send(res,200,{jobs:store.jobs.slice(0,20)});
if(url.pathname==='/api/inspect'&&req.method==='GET'){
 if(me.role!=='admin')return fail(res,403,'Sin permisos');
 const cfg=monthConfig('SEPTIEMBRE');const entries=await Promise.all(['01','03','07'].map(async key=>({source:key,...await sheetMetadata(cfg[key])})));
 return send(res,200,{sources:entries});
}
if(url.pathname==='/api/reconcile'&&req.method==='POST'){
 if(me.role!=='admin')return fail(res,403,'Sin permisos');
 return send(res,200,await reconcileJobs());
}
if(url.pathname==='/api/users'&&req.method==='POST'){
if(me.role!=='admin')return fail(res,403,'Sin permisos');if(!dataPersistent)return fail(res,503,'Configura almacenamiento persistente antes de crear integrantes');
const b=await body(req);let username=String(b.username||'').toLowerCase().trim(),password=String(b.password||'');
if(!/^[a-z0-9._-]{3,40}$/.test(username)||username==='admin'||password.length<12||password.length>128)return fail(res,400,'Usuario o contraseña inválidos');
if(store.users[username])return fail(res,409,'Usuario ya existe');
store.users[username]={hash:passhash(password),disabled:false,created:new Date().toISOString()};persist();log(me.username,'crear usuario','OK',username);return send(res,201,{ok:true})}
if(url.pathname==='/api/preview'&&req.method==='POST')return send(res,200,await preview(me,await body(req)));
if(url.pathname==='/api/preview07'&&req.method==='POST')return send(res,200,await previewVerified07(me,await body(req)));
if(url.pathname==='/api/sync'&&req.method==='POST')return send(res,200,await sync(me,await body(req)));
return fail(res,404,'Ruta no encontrada')}
const server=http.createServer((req,res)=>{handler(req,res).catch(e=>{console.error(new Date().toISOString(),String(e.message).slice(0,220));if(!res.headersSent)fail(res,400,e.message||'Error interno')})});
server.listen(port,'0.0.0.0',()=>console.log('Observatorio boletines escuchando en '+port));
