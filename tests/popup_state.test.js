import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const popup=readFileSync(new URL('../extension/popup.js',import.meta.url),'utf8');
async function render(state,online){
 const elements=Object.fromEntries(['status','error','warning','micState','people','start','stop','activate','settings','open','microphoneSetup'].map(id=>[id,{}]));
 const context=vm.createContext({document:{getElementById:id=>elements[id]},AbortSignal,fetch:async()=>({ok:online}),setInterval(){},chrome:{storage:{local:{get:async()=>({token:'test'})}},runtime:{sendMessage:async()=>state}}});
 vm.runInContext(popup,context);
 await new Promise(resolve=>setImmediate(resolve));
 return elements;
}
test('recording remains explicit with microphone warning and service is disabled',async()=>{
 const ui=await render({status:'recording',warnings:['Microfono non disponibile'],microphone:'unavailable'},true);
 assert.match(ui.status.textContent,/Registrazione in corso/);
 assert.match(ui.warning.textContent,/la registrazione continua/);
 assert.match(ui.micState.textContent,/solo la scheda/);
 assert.equal(ui.activate.textContent,'✓ Servizio attivo');assert.equal(ui.activate.disabled,true);
 assert.equal(ui.start.disabled,true);assert.equal(ui.stop.disabled,false);
});
test('idle active service cannot be started twice; offline service can be activated',async()=>{
 const active=await render({status:'idle'},true);
 assert.equal(active.activate.disabled,true);assert.match(active.status.textContent,/nessuna registrazione/);
 const offline=await render({status:'idle'},false);
 assert.equal(offline.activate.disabled,false);assert.equal(offline.activate.textContent,'Attiva servizio sul Mac');
});
test('unreachable service during recording never enables a conflicting activation',async()=>{
 const ui=await render({status:'recording',microphone:'active'},false);
 assert.equal(ui.activate.disabled,true);assert.match(ui.activate.textContent,/non raggiungibile/);
 assert.match(ui.micState.textContent,/scheda \+ microfono/);
});
