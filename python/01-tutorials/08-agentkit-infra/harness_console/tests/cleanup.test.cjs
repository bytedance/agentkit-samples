const {test} = require('node:test');
const assert = require('node:assert/strict');
const {webcrypto} = require('node:crypto');
global.crypto ||= webcrypto;
const cleanup = require('../static/cleanup.js');
function fixture() {
  const ids = {sessions:'id', templates:'RuntimeTemplateId', stores:'SessionStoreId', resources:'ResourceId', keys:'ApiKeyId', environments:'EnvironmentId', harnesses:'HarnessId', endpoints:'EndpointId'};
  const boot = {local_keys:[{id:'key'}], catalog:Object.fromEntries(Object.entries(ids).map(([k,id]) => [k,{id,label:k,delete:k !== 'endpoints'}]))};
  const rows = {
    sessions:[{id:'session',environment_id:'env',runtime_template_id:'rt',agent:{id:'h'},status:'idle'}],
    templates:[{RuntimeTemplateId:'rt',SessionStoreId:'ss',Status:'Ready'}],
    stores:[{SessionStoreId:'ss',Status:'Ready'}],
    resources:[{ResourceId:'res',Target:{EnvironmentId:'env'},Status:'Ready'}],
    keys:[{ApiKeyId:'key',EnvironmentId:'env',EndpointId:'ep'}],
    environments:[{EnvironmentId:'env',Status:'Active'}],
    harnesses:[{HarnessId:'h',Status:'Active'},{HarnessId:'old-h',Status:'Archived'}],
    endpoints:[{EndpointId:'ep'}],
  };
  const calls = [];
  const api = async (path,b) => {
    calls.push([path,b]);
    if(path === 'list') return {items:structuredClone(rows[b.kind]), next_cursor:''};
    const row = rows[b.kind].find(r => r[ids[b.kind]] === b.id);
    if(path === 'get') {
      if(!row) throw Object.assign(new Error('not found'),{status:404});
      return structuredClone(row);
    }
    if(path === 'archive') row.Status = 'Archived';
    else if(path === 'delete') rows[b.kind] = rows[b.kind].filter(r => r !== row);
    return {accepted:true};
  };
  return {boot,rows,calls,api};
}
test('scan is read-only, covers archived resources, binds Sessions and completes pagination', async () => {
  const f = fixture();
  const api = (path,b) => b.kind === 'endpoints' && !b.cursor ? Promise.resolve({items:[],next_cursor:'second'}) : f.api(path,b);
  const result = await cleanup.scan(api,f.boot);
  assert.equal(result.entries.length,9);
  assert.ok(f.calls.every(([path]) => path === 'list'));
  assert.equal(f.calls.find(([,b])=>b.kind==='sessions')[1].context.key_id,'key');
  assert.equal(f.calls.find(([,b])=>b.kind==='harnesses')[1].filters.IncludeArchived,true);
  assert.ok(result.entries.find(e=>e.id==='old-h').blocked);
});
test('incomplete Session visibility protects dependencies and exposes missing credentials', async () => {
  const f=fixture(); f.boot.local_keys=[];
  const result=await cleanup.scan(f.api,f.boot);
  assert.equal(result.warnings.length,1);
  assert.ok(result.entries.every(e=>e.blocked));
});
test('scan fails on cyclic pagination instead of declaring a partial list complete', async () => {
  const f=fixture();
  await assert.rejects(cleanup.scan(async()=>({items:[],next_cursor:'loop'}),f.boot),/循环/);
});
test('scan tries another local key when the first key cannot read Sessions', async () => {
  const f=fixture(); f.rows.keys.push({...f.rows.keys[0],ApiKeyId:'backup'}); f.boot.local_keys.push({id:'backup'});
  const result=await cleanup.scan((path,b)=>b.kind==='sessions' && b.context.key_id==='key' ? Promise.reject(new Error('revoked')) : f.api(path,b), f.boot);
  assert.equal(result.warnings.length,0);
  assert.equal(result.entries.find(e=>e.kind==='sessions').context.key_id,'backup');
});
test('plan rejects unselected dependents and orders full cleanup before revoking the data key', async () => {
  const f=fixture(), {entries}=await cleanup.scan(f.api,f.boot);
  assert.throws(()=>cleanup.plan(entries,new Set(['stores:ss'])),/rt/);
  assert.throws(()=>cleanup.plan(entries,new Set(['templates:rt'])),/session/);
  assert.throws(()=>cleanup.plan(entries,new Set(['environments:env'])),/未勾选/);
  const plan=cleanup.plan(entries,new Set(entries.filter(e=>!e.blocked).map(e=>e.key)));
  assert.deepEqual(plan.map(e=>e.kind),['sessions','templates','stores','resources','keys','environments','harnesses']);
  const updates=[];
  const result=await cleanup.run(f.api,plan,'test reason',(...u)=>updates.push(u));
  assert.equal(result.completed,7);
  const mutations=f.calls.filter(([p])=>['delete','archive'].includes(p));
  assert.equal(mutations.length,7);
  assert.equal(mutations[1][1].reason,'test reason');
  assert.equal(mutations[6][0],'archive');
  assert.equal(f.rows.harnesses[0].Status,'Archived');
  assert.ok(updates.filter(([,s])=>s==='完成').length===7);
});
test('accepted async deletion waits for disappearance before touching its parent', async () => {
  const f=fixture(), {entries}=await cleanup.scan(f.api,f.boot);
  const plan=cleanup.plan(entries,new Set(entries.filter(e=>!e.blocked).map(e=>e.key)));
  let deleting=false, polls=0;
  const api=async(path,b)=>{
    if(b.kind==='sessions' && path==='delete'){deleting=true; return {accepted:true};}
    if(b.kind==='sessions' && path==='get' && deleting && ++polls<3) return {status:'deleting'};
    if(b.kind==='sessions' && path==='get' && deleting) {f.rows.sessions=[];}
    if(path==='delete' && b.kind==='templates') assert.ok(polls>=3);
    return f.api(path,b);
  };
  const result=await cleanup.run(api,plan,'reason',()=>{},()=>false,{sleep:async()=>{}});
  assert.equal(result.completed,7);
});
test('timeout stops all downstream mutations and never reports accepted as completed', async () => {
  const f=fixture(), {entries}=await cleanup.scan(f.api,f.boot);
  const plan=cleanup.plan(entries,new Set(entries.filter(e=>!e.blocked).map(e=>e.key)));
  const mutations=[], updates=[];
  const api=async(path,b)=>{
    if(path==='get') return {status:'idle'};
    mutations.push(b.kind);return {accepted:true};
  };
  const result=await cleanup.run(api,plan,'reason',(...u)=>updates.push(u),()=>false,{attempts:2,sleep:async()=>{}});
  assert.equal(result.failed,true);assert.equal(result.completed,0);
  assert.deepEqual(mutations,['sessions']);assert.match(updates.at(-1)[2],/超时/);
});
test('permission errors stop the batch and are not treated as absence; stop sends no request', async () => {
  const f=fixture(), {entries}=await cleanup.scan(f.api,f.boot);
  const plan=cleanup.plan(entries,new Set(entries.filter(e=>!e.blocked).map(e=>e.key)));
  const api=async()=>{throw Object.assign(new Error('denied'),{status:403});};
  assert.equal((await cleanup.run(api,plan,'reason',()=>{})).failed,true);
  let calls=0;
  const result=await cleanup.run(async()=>{calls++;},plan,'reason',()=>{},()=>true);
  assert.equal(result.stopped,true);assert.equal(calls,0);
});
