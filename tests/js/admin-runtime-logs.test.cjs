const test = require('node:test'); const assert = require('node:assert/strict'); const vm = require('node:vm'); const fs = require('node:fs');
function setup(){
 const nodes=new Map(),timers=new Map(),calls=[];let id=0;
 const make=()=>({children:[],value:'',checked:true,scrollTop:0,scrollHeight:100,clientHeight:100,style:{},classList:{add(){},remove(){}},addEventListener(k,f){this[k]=f;},setAttribute(){},appendChild(n){this.children.push(n);},replaceChildren(fragment){this.children=fragment ? fragment.children : [];}});
 const document={hidden:false,getElementById(k){if(!nodes.has(k))nodes.set(k,make());return nodes.get(k);},createElement:make,createDocumentFragment:make,addEventListener(){}};
 document.getElementById('runtime-level').value='all';
 vm.runInNewContext(fs.readFileSync('web/static/js/admin-runtime-logs.js','utf8'),{document,window:{addEventListener(){}},AbortController,Math,Date,Error,setTimeout(fn,ms){timers.set(++id,{fn,ms});return id;},clearTimeout(k){timers.delete(k);},fetch(url,options){return new Promise((resolve,reject)=>{calls.push({url,resolve});options.signal.addEventListener('abort',()=>reject(new Error('abort')));});}});
 return {nodes,timers,calls};
}
const flush=()=>new Promise(r=>setImmediate(r));
test('runtime filters keep safe text, and clearing does not rewind cursor',async()=>{
 const s=setup();s.calls[0].resolve({ok:true,status:200,json:async()=>({entries:[{id:1,timestamp:'2026-01-01',level:'INFO',message:'<script>alert(1)</script>'},{id:2,timestamp:'2026-01-01',level:'ERROR',message:'failure'}]})});await flush();
 const viewer=s.nodes.get('runtime-log-viewer');assert.equal(viewer.children.length,2);assert.equal(viewer.children[0].children[2].textContent,'<script>alert(1)</script>');
 const level=s.nodes.get('runtime-level');level.value='errors';level.change();assert.equal(viewer.children.length,1);
 s.nodes.get('runtime-search').value='missing';s.nodes.get('runtime-search').input();assert.equal(viewer.children.length,0);
 s.nodes.get('clear-logs').click();assert.equal(s.nodes.get('runtime-count').textContent,'0 of 0 buffered entries');
 const next=[...s.timers.values()].find(t=>t.ms===2000);assert.ok(next);next.fn();assert.ok(s.calls[1].url.endsWith('after=2'));
 s.calls[1].resolve({ok:false,status:401});await flush();assert.equal(s.nodes.get('logs-sign-in').hidden,false);
});
