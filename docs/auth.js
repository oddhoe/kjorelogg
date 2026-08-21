(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;root.KjoreloggAuth=api})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 function configured(config){return /^https:\/\/[a-z0-9-]+\.supabase\.co$/i.test(config?.SUPABASE_URL||'')&&String(config?.SUPABASE_ANON_KEY||'').length>20}
 function create(options={}){
  const config=options.config||globalThis.KJORELOGG_CONFIG||{},library=options.library||globalThis.supabase;let client=null,session=null,listeners=new Set();
  function emit(event){for(const listener of listeners)try{listener({event,session,user:session?.user||null,configured:isConfigured()})}catch(error){console.warn('Auth listener failed',error)}}
  function isConfigured(){return configured(config)&&!!library?.createClient}
  function getClient(){
   if(!isConfigured())return null;
   if(!client)client=library.createClient(config.SUPABASE_URL,config.SUPABASE_ANON_KEY,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:true},global:{headers:{'X-Client-Info':'kjorelogg/2.0.95'}}});
   return client;
  }
  async function initialize(){const c=getClient();if(!c){emit('DISABLED');return{configured:false,session:null}}const result=await c.auth.getSession();if(result.error)console.warn('Auth session read failed',result.error.message);session=result.data?.session||null;c.auth.onAuthStateChange((event,next)=>{session=next||null;emit(event)});emit('INITIAL_SESSION');return{configured:true,session}}
  async function signIn(email,password){const c=getClient();if(!c)throw new Error('Supabase er ikke konfigurert');const result=await c.auth.signInWithPassword({email:String(email||'').trim(),password:String(password||'')});if(result.error)throw result.error;session=result.data.session;emit('SIGNED_IN');return result.data}
  async function signOut(){const c=getClient();if(!c)return;const result=await c.auth.signOut({scope:'local'});if(result.error)throw result.error;session=null;emit('SIGNED_OUT')}
  async function getSession(){if(session)return session;const c=getClient();if(!c)return null;const result=await c.auth.getSession();session=result.data?.session||null;return session}
  function onChange(listener){listeners.add(listener);return()=>listeners.delete(listener)}
  return{initialize,isConfigured,getClient,getSession,getUser:()=>session?.user||null,signIn,signOut,onChange};
 }
 return{configured,create};
});
