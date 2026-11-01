const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function setup() {
 const nodes = new Map(); const events = {}; const timers = new Map(); const calls = []; let serial = 0;
 const document = {hidden:false, getElementById(id) { if (!nodes.has(id)) nodes.set(id,{textContent:'',style:{},hidden:true,classList:{add(){},remove(){}},addEventListener(type,fn){this[type]=fn;},setAttribute(){}}); return nodes.get(id); },addEventListener(type,fn){events[type]=fn;}};
 vm.runInNewContext(fs.readFileSync('web/static/js/admin-performance.js','utf8'), {document,window:{addEventListener(){}},AbortController,Date,Math,Number,Error,setTimeout(fn,ms){timers.set(++serial,{fn,ms});return serial;},clearTimeout(id){timers.delete(id);},fetch(url,options){return new Promise((resolve,reject)=>{calls.push({resolve,reject,options});options.signal.addEventListener('abort',()=>reject(new Error('aborted')));});}});
 return {document,nodes,events,timers,calls};
}
const flush = () => new Promise(resolve=>setImmediate(resolve));
const success = {ok:true,status:200,json:async()=>({cpu_percent:10,cpu_temperature_celsius:null,memory_percent:null,disk_percent:null,load_average:null})};
test('only one request is in flight and next sample waits for completion',async()=>{
 const s=setup();assert.equal(s.calls.length,1);assert.equal(s.timers.size,1);
 s.calls[0].resolve(success);await flush();assert.equal(s.nodes.get('metrics-status').textContent,'Live');assert.equal(s.nodes.get('disk-percent').textContent,'Unavailable');assert.deepEqual([...s.timers.values()].map(t=>t.ms),[5000]);
});
test('hidden tabs abort requests and resume when visible',async()=>{
 const s=setup();s.document.hidden=true;s.events.visibilitychange();await flush();assert.equal(s.calls[0].options.signal.aborted,true);assert.equal(s.timers.size,0);
 s.document.hidden=false;s.events.visibilitychange();assert.equal(s.calls.length,2);s.calls[1].resolve(success);await flush();
});
test('pause cancels updates, resume fetches, expired session stops polling',async()=>{
 const s=setup();s.calls[0].resolve(success);await flush();s.nodes.get('metrics-toggle').click();assert.equal(s.timers.size,0);assert.equal(s.nodes.get('metrics-status').textContent,'Paused');
 s.nodes.get('metrics-toggle').click();assert.equal(s.calls.length,2);s.calls[1].resolve({ok:false,status:401});await flush();assert.equal(s.nodes.get('metrics-sign-in').hidden,false);assert.equal(s.nodes.get('metrics-toggle').disabled,true);assert.equal(s.timers.size,0);
});
test('failed requests back off and retain last updated label',async()=>{
 const s=setup();s.calls[0].reject(new Error('offline'));await flush();assert.equal(s.nodes.get('metrics-status').textContent,'Update failed · retrying');assert.deepEqual([...s.timers.values()].map(t=>t.ms),[10000]);
});
