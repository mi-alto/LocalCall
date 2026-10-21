import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../extension/background.js',import.meta.url),'utf8');
function worker(){
 let calls=0,stored;
 const context=vm.createContext({chrome:{runtime:{getURL:p=>'chrome-extension://'+ 'a'.repeat(32)+'/'+p,onMessage:{addListener(){}},sendNativeMessage:async()=>{calls++;return {ok:true,token:'private-token'};}},storage:{local:{set:async value=>{stored=value;}}},alarms:{onAlarm:{addListener(){}}},tabs:{onRemoved:{addListener(){}},onUpdated:{addListener(){}}}}});
 vm.runInContext(source,context);
 return {context,calls:()=>calls,stored:()=>stored};
}
test('meeting activation stores token privately and never returns it to the page',async()=>{
 const w=worker();w.context.sender={url:'https://meet.google.com/abc',tab:{id:1},frameId:0};
 const result=await vm.runInContext("handle({target:'worker',type:'activate-service'},sender)",w.context);
 assert.equal(result.ok,true);assert.equal(result.token,undefined);assert.equal(w.stored().token,'private-token');assert.equal(w.calls(),1);
});
test('unrelated websites and subframes cannot start the native service',async()=>{
 for(const sender of [{url:'https://example.com/',tab:{id:1},frameId:0},{url:'https://meet.google.com/abc',tab:{id:1},frameId:1}]){
  const w=worker();w.context.sender=sender;
  await assert.rejects(vm.runInContext("handle({target:'worker',type:'activate-service'},sender)",w.context));assert.equal(w.calls(),0);
 }
});

test('recording with warnings keeps the REC badge rather than an exclamation',async()=>{
 const w=worker();let badge,title;
 w.context.chrome.action={setBadgeText:async value=>{badge=value.text;},setBadgeBackgroundColor:async()=>{},setTitle:async value=>{title=value.title;}};
 w.context.sender={url:'chrome-extension://'+'a'.repeat(32)+'/offscreen.html'};
 await vm.runInContext("handle({target:'worker',type:'recorder-state',state:{status:'recording',warnings:['Microfono non disponibile']}},sender)",w.context);
 assert.equal(badge,'REC');assert.match(title,/Registrazione in corso/);assert.match(title,/Microfono/);
});

test('meeting end waits through brief UI loss and ignores prejoin and silence',async()=>{
 const w=worker();let data={},stops=0;
 w.context.chrome.storage.session={get:async()=>({...data}),set:async x=>Object.assign(data,x),remove:async keys=>keys.forEach(k=>delete data[k])};
 w.context.chrome.offscreen={hasDocument:async()=>true};
 w.context.chrome.runtime.sendMessage=async()=>{stops++;};
 w.context.chrome.alarms.clear=async()=>{};
 const check=(present,time)=>vm.runInContext(`checkMeeting(${present},${time})`,w.context);
 await check(false,1000);await check(false,90000);assert.equal(stops,0);
 await check(true,100000);await check(false,101000);await check(false,150000);assert.equal(stops,0);
 await check(true,151000);await check(true,250000);assert.equal(stops,0);
 await check(false,251000);await check(false,312000);assert.equal(stops,1);
});

test('only the recorded tab closes capture or stops it on external navigation',async()=>{
 const callbacks={};let stops=0,data={meetingTab:7};
 const context=vm.createContext({chrome:{runtime:{onMessage:{addListener(){}},sendMessage:async()=>{stops++;return {ok:true};}},storage:{session:{get:async()=>({...data}),remove:async keys=>keys.forEach(k=>delete data[k])}},offscreen:{hasDocument:async()=>true},alarms:{clear:async()=>{},onAlarm:{addListener(fn){callbacks.alarm=fn;}}},tabs:{sendMessage:async()=>{},onRemoved:{addListener(fn){callbacks.removed=fn;}},onUpdated:{addListener(fn){(callbacks.updated??=[]).push(fn);}}}}});
 vm.runInContext(source,context);
 await callbacks.removed(8);assert.equal(stops,0);
 await callbacks.removed(7);assert.equal(stops,1);
 data={meetingTab:7};
 for(const fn of callbacks.updated)await fn(7,{url:'https://example.org/'},{});
 assert.equal(stops,2);
});
