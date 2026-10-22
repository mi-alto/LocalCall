import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
test('Recorder forwards only fresh, consistent local participant identity',()=>{
 let listener;const sandbox={performance,navigator:{mediaDevices:{addEventListener(){}}},chrome:{runtime:{sendMessage:async()=>({}),onMessage:{addListener(f){listener=f;}}}}};
 vm.createContext(sandbox);vm.runInContext(readFileSync('extension/offscreen.js','utf8'),sandbox);
 vm.runInContext("state={status:'recording'}; context={currentTime:10};",sandbox);
 const event={observedAt:performance.timeOrigin+performance.now(),participants:['Self','Remote'],speakers:['Remote'],self_name:'Self'};
 listener({target:'recorder',type:'observation',event},{},()=>{});
 assert.equal(vm.runInContext('eventBuffer.at(-1).self_name',sandbox),'Self');
 for(let i=0;i<105;i++)listener({target:'recorder',type:'observation',event},{},()=>{});
 assert.ok(vm.runInContext('eventGaps',sandbox)>0);
 for(const change of [{self_name:'Remote'},{self_name:'Missing'},{observedAt:0}]){
  listener({target:'recorder',type:'observation',event:{...event,...change}},{},()=>{});
  assert.equal(vm.runInContext('eventBuffer.at(-1).self_name',sandbox),undefined);
 }
});
