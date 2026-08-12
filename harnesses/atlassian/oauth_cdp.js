#!/usr/bin/env node
'use strict';
const fs=require('fs');
const CALLBACK_FRAME_MAX=8192;
/* Managed-Chromium Atlassian consent driver.
 *
 * Atlassian renders product/category labels rather than every literal scope.
 * This allowlist is deliberately closed: null means Atlassian intentionally
 * does not render the scope; every other entry is a set of accepted visible
 * tokens, of which at least one must appear. Unknown scopes fail closed.
 */
const CONSENT_SCOPE_TOKENS = Object.freeze({
  'offline_access': null,
  'read:me': ['me'],
  'read:jira-work': ['jira-work', 'jira work'],
  'write:jira-work': ['jira-work', 'jira work'],
  'read:jira-user': ['jira-user', 'jira user'],
  'manage:jira-project': ['jira-project', 'jira project'],
  'manage:jira-configuration': ['jira-configuration', 'jira configuration'],
  'read:confluence-content.all': ['confluence-content.all'],
  'read:confluence-space.summary': ['confluence-space.summary'],
  'write:confluence-content': ['confluence-content'],
  'write:confluence-file': ['confluence-file'],
  'read:space:confluence': ['read space', 'view spaces', 'spaces'],
  'read:page:confluence': ['read page', 'view pages', 'pages'],
  'write:page:confluence': ['write page', 'create pages', 'pages'],
  'read:content:confluence': ['confluence content', 'content'],
  'search:confluence': ['confluence']
});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const fail=(code,message)=>({ok:false,code,message});
function verifyScopes(scopes,text){
  text=String(text||'').toLowerCase();
  const hasToken=token=>{const escaped=token.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');return new RegExp('(^|[^a-z0-9.-])'+escaped+'(?=$|[^a-z0-9.-])','i').test(text)};
  for(const scope of scopes){
    if(!Object.prototype.hasOwnProperty.call(CONSENT_SCOPE_TOKENS,scope)) return fail('oauth_scope_unmapped','requested scope has no approved consent mapping');
    const tokens=CONSENT_SCOPE_TOKENS[scope];
    if(tokens && !tokens.some(hasToken)) return fail('oauth_scope_missing','consent page omitted a requested permission category');
  }
  return {ok:true};
}
function inspectAuthorization(c,page){
  const expected=new URL(c.authorize_url);
  if(expected.searchParams.get('state')!==c.state || expected.searchParams.get('redirect_uri')!==c.redirect_uri)
    return fail('oauth_callback_mismatch','authorization callback or state mismatch');
  return verifyScopes(c.scopes,String(page.text||'').toLowerCase());
}
function inspectCallback(c,value){
  let actual,expected;
  try{actual=new URL(value);expected=new URL(c.redirect_uri)}catch(_){return fail('oauth_callback_mismatch','authorization callback mismatch')}
  if(actual.origin!==expected.origin||actual.pathname!==expected.pathname||actual.username||actual.password||actual.hash)
    return fail('oauth_callback_mismatch','authorization callback mismatch');
  const states=actual.searchParams.getAll('state'),codes=actual.searchParams.getAll('code'),errors=actual.searchParams.getAll('error');
  for(const key of actual.searchParams.keys())if(!['state','code','error'].includes(key))return fail('oauth_response_invalid','authorization response is invalid');
  if(states.length!==1||states[0]!==c.state)return fail('oauth_state_mismatch','authorization state mismatch');
  if(codes.length>1||errors.length>1||Boolean(codes.length)===Boolean(errors.length))return fail('oauth_response_invalid','authorization response is invalid');
  if(codes.length===1&&!codes[0])return fail('oauth_response_invalid','authorization response is invalid');
  return {ok:true};
}
async function transferCallback(c,value){
  const checked=inspectCallback(c,value);if(!checked.ok)return checked;
  try{
    if(!Number.isInteger(c.callback_fd)||c.callback_fd<3){
      if(process.env.OAUTH_CDP_TEST_MODE==='1'){
        const response=await fetch(value,{method:'GET',redirect:'manual'});
        return response.status===200||response.status===409?{ok:true,phase:'callback-relayed'}:fail('oauth_callback_transport_invalid','authorization callback transport failed');
      }
      return fail('oauth_callback_transport_invalid','authorization callback transport is invalid');
    }
    const body=Buffer.from(value,'utf8');
    if(!body.length||body.length>CALLBACK_FRAME_MAX)return fail('oauth_callback_transport_invalid','authorization callback transport is invalid');
    const frame=Buffer.allocUnsafe(4+body.length);frame.writeUInt32BE(body.length,0);body.copy(frame,4);
    let offset=0;while(offset<frame.length)offset+=fs.writeSync(c.callback_fd,frame,offset,frame.length-offset);
    fs.closeSync(c.callback_fd);c.callback_fd=-1;
    return {ok:true,phase:'callback-transferred'};
  }catch(_){try{if(c.callback_fd>=3)fs.closeSync(c.callback_fd)}catch(_){}c.callback_fd=-1;return fail('oauth_callback_transport_invalid','authorization callback transport failed')}
}
function callbackFromTargets(c,targets,before,currentId){
  const eligible=(targets||[]).filter(t=>t&&typeof t.id==='string'&&(t.id===currentId||!before.has(t.id)||before.get(t.id)!==t.url));
  const paths=eligible.filter(t=>{try{const a=new URL(t.url),e=new URL(c.redirect_uri);return a.origin===e.origin&&a.pathname===e.pathname}catch(_){return false}});
  if(paths.length>1)return fail('oauth_callback_ambiguous','authorization callback is ambiguous');
  if(paths.length===0)return null;
  const checked=inspectCallback(c,paths[0].url);return checked.ok?{ok:true,value:paths[0].url}:checked;
}
async function listTargets(c){
  try{
    const response=await fetch(c.endpoint+'/json/list',{redirect:'error'});
    if(!response.ok)return null;
    const targets=await response.json();return Array.isArray(targets)?targets:null;
  }catch(_){return null}
}
async function synthetic(c){
  if(c.testCallbackUrl)return transferCallback(c,c.testCallbackUrl);
  if(c.testTargetSnapshots){
    const before=new Map((c.testBeforeTargets||[]).map(t=>[t.id,t.url]));
    for(const id of c.testBeforeTargetIds||[])if(!before.has(id))before.set(id,undefined);
    for(const targets of c.testTargetSnapshots){
      const found=callbackFromTargets(c,targets,before,c.testCurrentTargetId);
      if(!found)continue;
      if(!found.ok)return found;
      return transferCallback(c,found.value);
    }
    return fail('oauth_timeout','authorization timed out');
  }
  let waited=false;
  const pages=c.testSnapshots||[];
  for(let i=0;i<pages.length;i++){
    const page=pages[i];
    if(page.login){waited=true;continue}
    const checked=inspectAuthorization(c,page); if(!checked.ok)return checked;
    const host=new URL(c.resource_url).hostname.toLowerCase();
    const origins=[...new Set((page.siteOrigins||[]).map(x=>x.toLowerCase()))];
    let selected=origins.length===1&&origins[0]===host;
    if(!selected){
      const native=(page.nativeOptions||[]).filter(x=>x.toLowerCase()===host);
      const custom=(page.comboboxOptions||[]).filter(x=>x.toLowerCase()===host);
      if(native.length+custom.length!==1)return fail(native.length+custom.length?'oauth_site_ambiguous':'oauth_site_mismatch','approved Atlassian site selection is missing or ambiguous');
      const settled=pages[++i];
      if(!settled)return fail('oauth_site_unsettled','site selection did not settle');
      const settledAuth=inspectAuthorization(c,settled);if(!settledAuth.ok)return settledAuth;
      const settledOrigins=[...new Set((settled.siteOrigins||[]).map(x=>x.toLowerCase()))];
      if(settledOrigins.length!==1||settledOrigins[0]!==host)return fail('oauth_site_unsettled','selected Atlassian site was not confirmed');
      selected=true;
    }
    if((page.acceptButtons||[]).filter(x=>/^(accept|allow|authorize|continue)$/i.test(x)).length!==1)return fail('oauth_consent_ambiguous','consent action is missing or ambiguous');
    if(!c.skipCallback){const callback=new URL(c.redirect_uri);callback.searchParams.set('state',c.state);callback.searchParams.set('code','synthetic-code');await fetch(callback).then(r=>{if(!r.ok)throw Error('callback')})}
    return {ok:true,phase:'pending-consent',waitedForLogin:waited,selectedSite:host,accepted:true};
  }
  return fail('oauth_timeout','authorization timed out');
}
async function run(c){
  if(process.env.OAUTH_CDP_TEST_MODE==='1') return synthetic(c);
  const target=await fetch(c.endpoint+'/json/new?'+encodeURIComponent(c.authorize_url),{method:'PUT'}).then(r=>r.json());
  if(!target.webSocketDebuggerUrl)return fail('browser_open_failed','could not open managed browser');
  const ws=new WebSocket(target.webSocketDebuggerUrl); await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
  let seq=0,waits=new Map(); ws.onmessage=e=>{const x=JSON.parse(e.data);if(x.id&&waits.has(x.id)){waits.get(x.id)(x);waits.delete(x.id)}};
  const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;waits.set(id,resolve);ws.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(waits.delete(id))reject(Error('timeout'))},3000)});
  const evaljs=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});return r.result&&r.result.result&&r.result.result.value};
  const readPage=`(()=>{const text=(document.body&&document.body.innerText||'').slice(0,50000),visible=e=>!!(e&&e.getClientRects().length&&e.getAttribute('aria-hidden')!=='true');const marked=[...document.querySelectorAll('option:checked,[role=option][aria-selected=true],[aria-current=true],[data-selected=true],[class*=site i],[id*=site i],[data-testid*=site i]')].filter(visible);for(const input of document.querySelectorAll('input:checked')){const label=input.labels&&input.labels[0];if(visible(label))marked.push(label)}const values=marked.flatMap(e=>[e.textContent,e.value,e.href,e.getAttribute&&e.getAttribute('data-value')]).filter(Boolean);const sites=[...new Set(values.flatMap(v=>[...String(v).matchAll(/(?:https?:\\/\\/)?([a-z0-9.-]+\\.atlassian\\.net)/ig)].map(m=>m[1].toLowerCase())))];return {url:location.href,text,sites,login:!!document.querySelector('input[type=password],input[name*=otp i],input[autocomplete=one-time-code]')}})()`;
  const deadline=Date.now()+Math.min(Math.max(Number(c.timeout)||300,5),600)*1000;
  while(Date.now()<deadline){
    const page=await evaljs(readPage);
    if(!page){await sleep(300);continue} if(page.login){await sleep(500);continue}
    const u=new URL(page.url),expected=new URL(c.authorize_url),callbackExpected=new URL(c.redirect_uri);
    if(u.origin===callbackExpected.origin&&u.pathname===callbackExpected.pathname){
      const relayed=await transferCallback(c,page.url);ws.close();return relayed
    }
    if(u.origin===expected.origin&&/authorize|consent/i.test(u.pathname+' '+page.text)){
      const checked=inspectAuthorization(c,page);if(!checked.ok){ws.close();return checked}
      const host=new URL(c.resource_url).hostname.toLowerCase();
      if(!(page.sites.length===1&&page.sites[0]===host)){
       const choice=await evaljs(`(async()=>{const wanted=${JSON.stringify(host)},exact=e=>{const vals=[e.textContent,e.innerText,e.value,e.getAttribute&&e.getAttribute('data-value')].filter(Boolean).map(x=>String(x).trim().toLowerCase());return vals.includes(wanted)||vals.includes('https://'+wanted)},find=()=>{let hits=[];for(const s of document.querySelectorAll('select'))for(const o of s.options)if(exact(o))hits.push({kind:'native',s,o});for(const o of document.querySelectorAll('[role=option]'))if(exact(o))hits.push({kind:'custom',o});return hits};let hits=find();if(!hits.length){const boxes=[...document.querySelectorAll('[role=combobox]')];if(boxes.length===1){boxes[0].click();await new Promise(r=>setTimeout(r,200));hits=find()}}if(hits.length!==1)return {n:hits.length};const h=hits[0];if(h.kind==='native'){h.s.value=h.o.value;h.s.dispatchEvent(new Event('change',{bubbles:true}))}else{h.o.click()}return {n:1}})()`);
       if(!choice||choice.n!==1){ws.close();return fail(choice&&choice.n?'oauth_site_ambiguous':'oauth_site_mismatch','approved Atlassian site selection is missing or ambiguous')}
       await sleep(300);
       const settled=await evaljs(readPage);
       if(!settled||settled.sites.length!==1||settled.sites[0]!==host){ws.close();return fail('oauth_site_unsettled','selected Atlassian site was not confirmed')}
      }
      const beforeTargets=await listTargets(c);
      if(!beforeTargets){ws.close();return fail('browser_automation_failed','managed browser target discovery failed')}
      const beforeIds=new Map(beforeTargets.filter(t=>t&&typeof t.id==='string').map(t=>[t.id,t.url]));
      const clicked=await evaljs(`(()=>{const xs=[...document.querySelectorAll('button,input[type=submit]')].filter(e=>/^(accept|allow|authorize|continue)$/i.test((e.innerText||e.value||'').trim())&&!e.disabled);if(xs.length!==1)return xs.length;xs[0].click();return 1})()`);
      if(clicked!==1){ws.close();return fail('oauth_consent_ambiguous','consent action is missing or ambiguous')}
      while(Date.now()<deadline){
        const location=await evaljs('location.href').catch(()=>null);
        if(location){
          let candidate=false;try{const a=new URL(location),e=new URL(c.redirect_uri);candidate=a.origin===e.origin&&a.pathname===e.pathname}catch(_){}
          if(candidate){const relayed=await transferCallback(c,location);ws.close();return relayed}
        }
        const targets=await listTargets(c);
        if(!targets){ws.close();return fail('browser_automation_failed','managed browser target discovery failed')}
        const found=callbackFromTargets(c,targets,beforeIds,target.id);
        if(found){
          if(!found.ok){ws.close();return found}
          const relayed=await transferCallback(c,found.value);ws.close();return relayed
        }
        await sleep(200);
      }
      ws.close();return fail('oauth_timeout','authorization timed out');
    }
    await sleep(400);
  }
  ws.close();return fail('oauth_timeout','authorization timed out');
}
let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',x=>input+=x);process.stdin.on('end',async()=>{let c;try{c=JSON.parse(input);console.log(JSON.stringify(await run(c)))}catch(_){console.log(JSON.stringify(fail('browser_automation_failed','managed browser automation failed')))}finally{try{if(c&&c.callback_fd>=3)fs.closeSync(c.callback_fd)}catch(_){}}});
