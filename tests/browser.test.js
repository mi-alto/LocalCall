import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {chromium} from '@playwright/test';
import {readFileSync,writeFileSync,mkdtempSync,cpSync,readdirSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {spawn} from 'node:child_process';
import path from 'node:path';
const executablePath=process.env.CHROMIUM_PATH || chromium.executablePath();
const root=process.cwd();
const launch={executablePath,headless:true,args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',`--use-file-for-fake-audio-capture=${root}/.test-output/italiano.wav`]};

let base,token,extensionPath,testRoot,server;
before(async()=>{
 testRoot=mkdtempSync(path.join(tmpdir(),'localcall-browser-'));
 server=spawn('python3',['-m','localcall.server','--port','0','--data',path.join(testRoot,'data')],{cwd:root});
 const line=await new Promise((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(Error('Server startup timeout')),10000);server.once('error',reject);server.stdout.on('data',chunk=>{output+=chunk;if(output.includes('LocalCall:')){clearTimeout(timer);resolve(output.trim());}});});
 base=line.match(/http:\/\/127\.0\.0\.1:\d+/)[0];token=readFileSync(path.join(testRoot,'data/token'),'utf8').trim();
 extensionPath=path.join(testRoot,'extension');cpSync('extension',extensionPath,{recursive:true});
 for(const name of readdirSync(extensionPath)){if(/\.(js|json)$/.test(name)){const f=path.join(extensionPath,name);writeFileSync(f,readFileSync(f,'utf8').replaceAll('http://127.0.0.1:8765',base));}}
});
after(async()=>{server?.kill('SIGTERM');if(server?.exitCode===null)await new Promise(r=>server.once('exit',r));rmSync(testRoot,{recursive:true,force:true});});

test('Meet/Teams adapters: visible names, explicit speech, inactive widgets, missing names',async()=>{
 const browser=await chromium.launch(launch);try{
 const page=await browser.newPage();
 await page.setContent(`<div data-participant-id="a"><span class="zWGUib">Anna</span><div aria-label="Anna is speaking">●</div></div><div data-participant-id="b"><span class="zWGUib">Luca</span><div data-audio-level="0"></div></div><div data-participant-id="c" style="display:none" data-is-speaking="true"><span class="zWGUib">Hidden</span></div>`);
 await page.addScriptTag({path:'extension/adapters.js'});
 let s=await page.evaluate(()=>LocalCallAdapter.snapshot(document,'meet.google.com'));
 assert.deepEqual(s,{participants:['Anna','Luca'],speakers:['Anna']});
 await page.locator('[aria-label]').evaluate(el=>el.remove());
 assert.deepEqual(await page.evaluate(()=>LocalCallAdapter.snapshot(document,'meet.google.com').speakers),[]);
 await page.setContent('<div data-participant-id="x"><span class="zWGUib">Anna</span><i class="IisKdb" style="display:block">●</i></div>');
 assert.deepEqual(await page.evaluate(()=>LocalCallAdapter.snapshot(document,'meet.google.com').speakers),['Anna']);
 await page.setContent('<div data-tid="participant-tile" data-is-speaking="true"><span data-tid="participant-name">Michele</span></div>');
 s=await page.evaluate(()=>LocalCallAdapter.snapshot(document,'teams.microsoft.com'));
 assert.deepEqual(s.speakers,['Michele']);
 // Sanitized structure observed in Teams web on 2026-10-20. Same display name
 // on the self tile and remote tile must not cause the remote speaker to vanish.
 await page.setContent(`<div data-tid="myself-video"><div data-tid="participant-info-nametag"><span data-person-mri="self">Alex</span></div><div data-is-speaking="true">●</div></div>
 <div data-cid="calling-participant-stream" role="menuitem"><div data-tid="participant-speaker" aria-hidden="true">Avatar</div><div data-tid="participant-info-nametag"><span data-person-mri="remote">Alex</span><span>Guest</span></div><div class="vdi-frame-occlusion" data-tid="voice-level-stream-outline" data-is-speaking="true">●</div></div>`);
 assert.deepEqual(await page.evaluate(()=>LocalCallAdapter.snapshot(document,'teams.microsoft.com').speakers),['Alex']);
 await page.locator('[data-tid="voice-level-stream-outline"]').evaluate(el=>el.setAttribute('data-is-speaking','false'));
 assert.deepEqual(await page.evaluate(()=>LocalCallAdapter.snapshot(document,'teams.microsoft.com').speakers),[]);
 await page.locator('[data-tid="voice-level-stream-outline"]').evaluate(el=>el.removeAttribute('data-is-speaking'));
 assert.deepEqual(await page.evaluate(()=>LocalCallAdapter.snapshot(document,'teams.microsoft.com').speakers),[]);

 await page.setContent('<div data-participant-id="local" data-is-speaking="true"><span data-self-name="Io">Io</span></div><div data-participant-id="remote"><span class="zWGUib">Anna</span><div class="IisKdb" style="opacity:0">●</div></div>');
 assert.deepEqual(await page.evaluate(()=>LocalCallAdapter.snapshot(document,'meet.google.com').speakers),[]);
 }finally{await browser.close();}
});

test('UI: authenticate, record real WebM via fake mic, transcribe locally, export, no external requests',async()=>{
 const browser=await chromium.launch(launch);try{
 const context=await browser.newContext({permissions:['microphone']});
 const page=await context.newPage();const errors=[], external=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(!r.url().startsWith(base)&&!r.url().startsWith('blob:'))external.push(r.url());});
 await page.goto(base+'/#'+token);
 await page.locator('#engine').filter({hasText:'PRONTO'}).waitFor();
 await page.locator('#title').fill('Test automatico — Italiano');
 await page.locator('#selfName').fill('Michele');
 await page.locator('#language').selectOption('it');
 await page.locator('#record').click();
 await page.locator('#recordBadge').filter({hasText:'REGISTRAZIONE'}).waitFor();
 await page.waitForTimeout(9500);
 await page.locator('#stop').click();
 await page.locator('#detailStatus').filter({hasText:'Pronta'}).waitFor({timeout:180000});
 const text=await page.locator('#transcript').innerText();
 assert.match(text,/Michele/);assert.match(text,/progetto/i);
 const download=page.waitForEvent('download');await page.locator('[data-export="txt"]').click();
 await (await download).saveAs('.test-output/export.txt');
 await page.screenshot({path:'.test-output/interface.png',fullPage:true});
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 }finally{await browser.close();}
});

test('Extension recorder: two streams, speaker events, stop flush, local final transcript',async()=>{
 const context=await chromium.launchPersistentContext(path.join(testRoot,'extension-profile'),{
  ...launch,args:[...launch.args,`--disable-extensions-except=${extensionPath}`,`--load-extension=${extensionPath}`]
 });
 try{
 let worker=context.serviceWorkers()[0]||await context.waitForEvent('serviceworker');
 const extensionId=new URL(worker.url()).hostname;
 const page=await context.newPage();
 // Recorder component test with synthetic sources. Full native invocation is
 // exercised separately by extension_flow.test.js, not by this component test.
 await page.addInitScript(({english})=>{const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async constraints=>{if(constraints.audio?.mandatory)return original({audio:true});const ctx=new AudioContext();const dest=ctx.createMediaStreamDestination();const source=ctx.createBufferSource();source.buffer=await ctx.decodeAudioData(Uint8Array.from(atob(english),c=>c.charCodeAt(0)).buffer);source.connect(dest);source.start();await ctx.resume();return dest.stream;};},{english:readFileSync('.test-output/english.wav').toString('base64')});
 await page.goto(`chrome-extension://${extensionId}/options.html`);
 assert.deepEqual(await page.locator('#language option').evaluateAll(nodes=>nodes.map(n=>n.value)),['auto','it','en']);
 assert.equal(await page.locator('#microphone').isChecked(),false);
 await page.evaluate(()=>{globalThis.testOriginalMic=navigator.mediaDevices.getUserMedia;navigator.mediaDevices.getUserMedia=async()=>{throw new DOMException('Denied','NotAllowedError');};});
 await page.locator('#permission').click();
 await page.waitForFunction(()=>document.getElementById('message').textContent.includes('Permesso microfono negato'));
 assert.equal(await page.locator('#microphone').isChecked(),false);
 await page.evaluate(()=>{navigator.mediaDevices.getUserMedia=globalThis.testOriginalMic;});
 await page.locator('#permission').click();
 await page.waitForFunction(()=>document.getElementById('message').textContent.includes('Microfono pronto'));
 assert.equal(await page.locator('#microphone').isChecked(),true);
 assert.equal(await page.evaluate(async()=>(await chrome.storage.local.get('microphone')).microphone),true);
 await page.screenshot({path:'.test-output/microphone-setup.png'});

 await page.goto(`chrome-extension://${extensionId}/offscreen.html`);
 let metadataFailed=false;
 await context.route(base+'/api/sessions/*/events',async route=>{if(!metadataFailed){metadataFailed=true;await route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({error:'Synthetic event error'})});}else await route.continue();});
 let droppedAck=false;
 await context.route(base+'/api/sessions/*/audio/remote',async route=>{
  if(!droppedAck){droppedAck=true;await route.fetch();await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Synthetic lost acknowledgement'})});}
  else await route.continue();
 });
 const result=await page.evaluate(async(token)=>start({streamId:'synthetic-test-source',title:'Test estensione — Due tracce',config:{token,selfName:'Michele',language:'auto',microphone:true}}),token);
 assert.equal(result.status,'recording');
 // DOM timestamps are captured independently, as in an actual meeting tab.
 await page.evaluate(()=>{globalThis.testEvents=setInterval(()=>{chrome.runtime.sendMessage({target:'worker',type:'status'}).catch(()=>{});const e={t:context.currentTime-audioEpoch,participants:['Anna'],speakers:['Anna']};eventBuffer.push(e);},250);});
 await page.waitForTimeout(4500);
 await page.evaluate(()=>streams[1].getAudioTracks()[0].dispatchEvent(new Event('ended')));
 assert.equal(await page.evaluate(()=>state.status),'recording');
 assert.equal(await page.evaluate(()=>recorders[0].state),'recording');
 assert.equal(await page.evaluate(()=>state.microphone),'disconnected');
 await page.waitForTimeout(4500);
 const stopped=await page.evaluate(async()=>{clearInterval(globalThis.testEvents);return stop();});
 assert.equal(stopped.status,'saved');
 const headers={Authorization:'Bearer '+token};let session;
 for(let i=0;i<90;i++){
  session=await (await fetch(`${base}/api/sessions/${result.sessionId}`,{headers})).json();
  if(['done','error'].includes(session.status))break;
  await new Promise(r=>setTimeout(r,1000));
 }
 assert.equal(session.status,'done',session.error);
 assert.ok(session.transcript.some(r=>r.speaker==='Anna'));
 assert.ok(session.transcript.some(r=>r.speaker==='Michele'&&/project/i.test(r.text)));
 assert.ok(session.transcript.some(r=>r.speaker==='Anna'&&/progetto/i.test(r.text)));
 assert.ok(droppedAck);assert.ok(metadataFailed);
 assert.ok(session.warnings.some(w=>w.includes('Microfono scollegato')));
 assert.ok(session.warnings.some(w=>w.includes('nomi')));
 assert.ok(session.tracks.remote.next_seq>1);
 assert.ok(session.tracks.mic.next_seq>1);
 }finally{await context.close();}
});

test('History: clean meeting titles, visible time and equal-height cards',async()=>{
 const browser=await chromium.launch(launch);
 try{
  const page=await browser.newPage();
  const sessions=[
   {id:'a',title:'(30) Registrazione di prova | Microsoft Teams',created:1792479600,status:'done'},
   {id:'b',title:'(31) Partecipazione alla riunione | Riunione di progetto con un titolo molto lungo per verificare le due righe nella scheda | Microsoft Teams',created:1792476000,status:'done'},
   {id:'c',title:'Nota breve',created:1792472400,status:'done'}
  ];
  await page.route(base+'/api/sessions',route=>route.fulfill({json:sessions}));
  await page.goto(base+'/#'+token);
  await page.waitForFunction(()=>document.querySelectorAll('.history-card').length===3);
  assert.equal(await page.locator('#reload').innerText(),'History');
  assert.equal(await page.locator('.history-title').first().innerText(),'Registrazione di prova');
  const heights=await page.locator('.history-card').evaluateAll(nodes=>nodes.map(n=>n.getBoundingClientRect().height));
  assert.equal(new Set(heights).size,1);
  for(const text of await page.locator('.history-card time').allTextContents())assert.match(text,/\d{2}:\d{2}/);
  await page.screenshot({path:'.test-output/history.png',fullPage:true});
  await page.goto('about:blank');
  await page.addScriptTag({path:'extension/adapters.js'});
  for(const [title,expected] of [['(30) Registrazione di prova | Microsoft Teams','Registrazione di prova'],['(31) Partecipazione alla riunione | Sprint planning | Microsoft Teams','Sprint planning'],['Meet - Team sync','Team sync'],['Nota breve','Nota breve']]){
   await page.evaluate(t=>{document.title=t;},title);
   assert.equal(await page.evaluate(()=>LocalCallAdapter.meetingTitle()),expected);
  }
 }finally{await browser.close();}
});
