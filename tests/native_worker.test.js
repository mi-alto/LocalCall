import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../extension/background.js',import.meta.url),'utf8');
function worker(){
 let calls=0,stored;
 const context=vm.createContext({chrome:{runtime:{getURL:p=>'chrome-extension://'+ 'a'.repeat(32)+'/'+p,onMessage:{addListener(){}},sendNativeMessage:async()=>{calls++;return {ok:true,token:'private-token'};}},storage:{local:{set:async value=>{stored=value;}}},tabs:{onUpdated:{addListener(){}}}}});
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
