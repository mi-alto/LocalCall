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
 assert.equal(await page.evaluate(()=>LocalCallAdapter.inMeeting()),false);
 await page.evaluate(()=>{const b=document.createElement('button');b.id='hangup-button';b.style.display='none';document.body.append(b);});
 assert.equal(await page.evaluate(()=>LocalCallAdapter.inMeeting()),true);
 await page.locator('#hangup-button').evaluate(b=>{b.removeAttribute('id');b.setAttribute('aria-label','Leave call');});
 assert.equal(await page.evaluate(()=>LocalCallAdapter.inMeeting()),true);
 await page.locator('button').evaluate(b=>b.remove());
 assert.equal(await page.evaluate(()=>LocalCallAdapter.inMeeting()),false);
 for(const [label,expected] of [['Attiva microfono',true],['Disattiva microfono (⌘+D)',false],['Unmute microphone',true],['Mute microphone',false],['Microfono',null]]){
   await page.evaluate(label=>{const b=document.createElement('button');b.id='microphone-button';b.setAttribute('aria-label',label);document.body.append(b);},label);
   assert.equal(await page.evaluate(()=>LocalCallAdapter.microphoneMuted()),expected);
   await page.locator('#microphone-button').evaluate(b=>b.remove());
 }
 assert.equal(await page.evaluate(()=>LocalCallAdapter.microphoneMuted()),null);
 let s=await page.evaluate(()=>LocalCallAdapter.snapshot(document,'meet.google.com'));
 assert.deepEqual(s,{participants:['Anna','Luca'],speakers:['Anna']});
 await page.locator('[aria-label]').evaluate(el=>el.remove());
 assert.deepEqual(await page.evaluate(()=>LocalCallAdapter.snapshot(document,'meet.google.com').speakers),[]);
 await page.setContent('<div data-participant-id="x"><span class="zWGUib">Anna</span><i class="IisKdb" style="display:block">●</i></div>');
 assert.deepEqual(await page.evaluate(()=>LocalCallAdapter.snapshot(document,'meet.google.com').speakers),['Anna']);
 await page.setContent('<div data-participant-id="self"><span data-self-name="You">You</span></div><div data-participant-id="remote" data-is-speaking="true"><span data-self-name="You">Anna</span></div>');
 s=await page.evaluate(()=>LocalCallAdapter.snapshot(document,'meet.google.com'));
 assert.deepEqual(s.participants,['You','Anna']);assert.deepEqual(s.speakers,['Anna']);assert.equal(s.self_name,'You');
 await page.setContent('<div data-participant-id="remote" data-is-speaking="true"><span class="notranslate google-symbols">keep_outline</span><span class="zWGUib">Anna</span></div><div data-participant-id="icon"><span class="notranslate">frame_person</span></div>');
 s=await page.evaluate(()=>LocalCallAdapter.snapshot(document,'meet.google.com'));
 assert.deepEqual(s.participants,['Anna']);assert.deepEqual(s.speakers,['Anna']);
 await page.setContent('<div data-tid="participant-tile" data-is-speaking="true"><span data-tid="participant-name">Michele</span></div>');
 s=await page.evaluate(()=>LocalCallAdapter.snapshot(document,'teams.microsoft.com'));
 assert.deepEqual(s.speakers,['Michele']);
 await page.setContent('<div data-cid="calling-participant-stream" data-tid="alex@example.org"><div data-tid="participant-info-nametag"><span data-person-mri="opaque-id">Alex</span></div></div><a href="mailto:unrelated@example.org">Unrelated chat</a>');
 assert.deepEqual(await page.evaluate(()=>LocalCallAdapter.snapshot(document,'teams.microsoft.com').contacts),[{name:'Alex',email:'alex@example.org'}]);
 await page.setContent('<div data-participant-id="opaque-id" data-email="anna@example.org"><span class="zWGUib">Anna</span></div>');
 assert.deepEqual(await page.evaluate(()=>LocalCallAdapter.snapshot(document,'meet.google.com').contacts),[{name:'Anna',email:'anna@example.org'}]);
 await page.setContent('<div data-participant-id="user@example.org"><span class="zWGUib">Anna</span><a style="display:none" href="mailto:hidden@example.org">Hidden</a></div>');
 assert.equal(await page.evaluate(()=>LocalCallAdapter.snapshot(document,'meet.google.com').contacts),undefined);

 // Sanitized structure observed in Teams web on 2026-10-20. Same display name
 // on the self tile and remote tile must not cause the remote speaker to vanish.
 await page.setContent(`<div data-tid="myself-video"><div data-tid="participant-info-nametag"><span data-person-mri="self">Alex</span></div><div data-is-speaking="true">●</div></div>
 <div data-cid="calling-participant-stream" role="menuitem"><div data-tid="participant-speaker" aria-hidden="true">Avatar</div><div data-tid="participant-info-nametag"><span data-person-mri="remote">Alex</span><span>Guest</span></div><div class="vdi-frame-occlusion" data-tid="voice-level-stream-outline" data-is-speaking="true">●</div></div>`);
 assert.deepEqual(await page.evaluate(()=>LocalCallAdapter.snapshot(document,'teams.microsoft.com').speakers),['Alex']);
 assert.equal(await page.evaluate(()=>LocalCallAdapter.snapshot(document,'teams.microsoft.com').self_name),'Alex');
 await page.locator('[data-tid="voice-level-stream-outline"]').evaluate(el=>el.setAttribute('data-is-speaking','false'));
 assert.deepEqual(await page.evaluate(()=>LocalCallAdapter.snapshot(document,'teams.microsoft.com').speakers),[]);
 await page.locator('[data-tid="voice-level-stream-outline"]').evaluate(el=>el.removeAttribute('data-is-speaking'));
 assert.deepEqual(await page.evaluate(()=>LocalCallAdapter.snapshot(document,'teams.microsoft.com').speakers),[]);

 await page.setContent('<div data-participant-id="local" data-is-speaking="true"><span data-self-name="Io">Io</span></div><div data-participant-id="remote"><span class="zWGUib">Anna</span><div class="IisKdb" style="opacity:0">●</div></div>');
 assert.equal(await page.evaluate(()=>LocalCallAdapter.snapshot(document,'meet.google.com').self_name),'Io');
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
 await page.locator('#setupLink').click();
 await page.locator('#title').fill('Test automatico — Italiano');
 await page.locator('#selfName').fill('Michele');
 await page.locator('#language').selectOption('it');
 await page.locator('#record').click();
 await page.locator('#recordBadge').filter({hasText:'REGISTRAZIONE'}).waitFor();
 await page.waitForTimeout(9500);
 await page.locator('#stop').click();
 await page.locator('#detailStatus').filter({hasText:'Trascritta'}).waitFor({timeout:180000});
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
 await page.evaluate(()=>{globalThis.testEvents=setInterval(()=>{chrome.runtime.sendMessage({target:'worker',type:'status'}).catch(()=>{});applyMeetingMicrophone({observedAt:now(),microphoneMuted:false,inMeeting:true});const e={t:context.currentTime-audioEpoch,participants:['Anna'],speakers:['Anna']};eventBuffer.push(e);},250);});
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
 // This nine-second fixture cannot meet the acoustic 20-second name-support span.
 // Verify captured DOM evidence independently of conservative acoustic abstention.
 const leaves=rows=>rows.flatMap(r=>r.parts?leaves(r.parts):[r]);
 const detailed=await (await fetch(`${base}/api/sessions/${result.sessionId}/export.json`,{headers})).json();
 const remote=leaves(detailed).filter(r=>r.track==='remote');
 assert.ok(remote.some(r=>(r.original_attribution?.speaker||r.speaker)==='Anna'));
 assert.ok(session.transcript.some(r=>r.speaker==='Michele'&&/project/i.test(r.text)));
 assert.ok(remote.some(r=>/progetto/i.test(r.text)));
 assert.ok(remote.every(r=>['Anna','Non identificato'].includes(r.speaker)));
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
   {id:'a',title:'(30) Registrazione di prova | Microsoft Teams',created:1792479600,status:'done',participants:['Anna Rossi'],contacts:[{name:'Anna Rossi',email:'anna@example.org'}]},
   {id:'b',title:'(31) Partecipazione alla riunione | Riunione di progetto con un titolo molto lungo per verificare le due righe nella scheda | Microsoft Teams',created:1792389600,status:'done',participants:['Luca Bianchi']},
   {id:'c',title:'Nota breve',created:1792472400,status:'done'}
  ];
  await page.route(base+'/api/sessions',route=>route.fulfill({json:sessions}));
  await page.route(base+'/api/sessions/*',route=>{const id=route.request().url().split('/').pop();route.fulfill({json:{...sessions.find(s=>s.id===id),transcript:[]}});});
  await page.goto(base+'/#'+token);
  await page.waitForFunction(()=>document.querySelectorAll('.history-card').length===3);
  assert.equal(await page.locator('.history-filters h2').innerText(),'History');
  assert.equal(await page.locator('.history-title').first().innerText(),'Registrazione di prova');
  const heights=await page.locator('.history-card').evaluateAll(nodes=>nodes.map(n=>n.getBoundingClientRect().height));
  assert.equal(new Set(heights).size,1);
  for(const text of await page.locator('.history-card time').allTextContents())assert.match(text,/\d{2}:\d{2}/);
  await page.locator('#detail').waitFor({state:'visible'});
  assert.equal(await page.locator('#pair').isVisible(),false);
  assert.match(await page.locator('#participants').innerText(),/Anna Rossi/);
  assert.match(await page.locator('#participants').innerText(),/anna@example.org/);
  await page.locator('#search').fill('anna@example.org');
  assert.equal(await page.locator('.history-card').count(),1);
  await page.locator('#search').fill('anna');
  assert.equal(await page.locator('.history-card').count(),1);
  await page.locator('#search').fill('riunione di progetto');
  assert.equal(await page.locator('.history-card').count(),1);
  await page.locator('#search').fill('');
  await page.locator('#dateFrom').fill('2026-10-20');await page.locator('#dateTo').fill('2026-10-20');
  assert.equal(await page.locator('.history-card').count(),2);
  await page.locator('#search').fill('Luca');
  assert.equal(await page.locator('.history-card').count(),0);
  await page.locator('#clearFilters').click();
  assert.equal(await page.locator('.history-card').count(),3);
  await page.locator('#dateFrom').fill('2026-10-21');await page.locator('#dateTo').fill('2026-10-20');
  assert.match(await page.locator('#filterStatus').innerText(),/deve precedere/);
  await page.locator('#clearFilters').click();
  await page.screenshot({path:'.test-output/history.png',fullPage:true});
  await page.locator('#setupLink').click();
  assert.equal(await page.locator('#pair').isVisible(),true);
  assert.equal(await page.locator('#detail').isVisible(),false);
  await page.locator('.history-card').first().click();
  await page.locator('#detail').waitFor({state:'visible'});
  assert.equal(await page.locator('#detail').isVisible(),true);
  assert.equal(await page.locator('#pair').isVisible(),false);
  await page.goto('about:blank');
  await page.addScriptTag({path:'extension/adapters.js'});
  for(const [title,expected] of [['(30) Registrazione di prova | Microsoft Teams','Registrazione di prova'],['(31) Partecipazione alla riunione | Sprint planning | Microsoft Teams','Sprint planning'],['Meet - Team sync','Team sync'],['Nota breve','Nota breve']]){
   await page.evaluate(t=>{document.title=t;},title);
   assert.equal(await page.evaluate(()=>LocalCallAdapter.meetingTitle()),expected);
  }
 }finally{await browser.close();}
});

test('Microphone privacy gate: audio is silent when muted, unknown or stale',async()=>{
 const browser=await chromium.launch(launch);
 try{
 const page=await browser.newPage();
 await page.route(base+'/privacy-test.html',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><title>Privacy gate test</title>'}));
 await page.goto(base+'/privacy-test.html');
 await page.evaluate(()=>{globalThis.chrome={runtime:{onMessage:{addListener(){}},sendMessage:async()=>({})}};});
 await page.route(base+'/privacy-test.js',route=>route.fulfill({contentType:'application/javascript',body:readFileSync('extension/offscreen.js','utf8')}));
 await page.addScriptTag({url:base+'/privacy-test.js'});
 await page.evaluate(async()=>{
   context=new AudioContext();micGate=context.createGain();micGate.gain.value=0;
   const tone=context.createOscillator();tone.frequency.value=440;tone.connect(micGate);
   globalThis.analyser=context.createAnalyser();micGate.connect(analyser);analyser.connect(context.destination);tone.start();await context.resume();
   globalThis.energy=()=>{const a=new Float32Array(analyser.fftSize);analyser.getFloatTimeDomainData(a);return Math.sqrt(a.reduce((s,x)=>s+x*x,0)/a.length);};
 });
 const rms=async()=>{await page.waitForTimeout(120);return page.evaluate(()=>energy());};
 assert.ok(await rms()<0.00001,'default closed');
 await page.evaluate(()=>applyMeetingMicrophone({observedAt:now(),microphoneMuted:false,inMeeting:true}));
 assert.ok(await rms()>.1,'confirmed unmuted audio passes');
 await page.evaluate(()=>applyMeetingMicrophone({observedAt:now(),microphoneMuted:true,inMeeting:true}));
 assert.ok(await rms()<0.00001,'mute removes audio');
 await page.evaluate(()=>applyMeetingMicrophone({observedAt:now(),microphoneMuted:null,inMeeting:true}));
 assert.ok(await rms()<0.00001,'unknown stays silent');
 await page.evaluate(()=>applyMeetingMicrophone({observedAt:now()-2000,microphoneMuted:false,inMeeting:true}));
 assert.ok(await rms()<0.00001,'delayed unmute is rejected');
 await page.evaluate(()=>applyMeetingMicrophone({observedAt:now(),microphoneMuted:false,inMeeting:false}));
 assert.ok(await rms()<0.00001,'outside call stays silent');
 await page.evaluate(()=>applyMeetingMicrophone({observedAt:now(),microphoneMuted:false,inMeeting:true}));
 assert.ok(await rms()>.1);
 await page.waitForTimeout(1400);
 assert.ok(await rms()<0.00001,'audio clock expires permission without another observation');
 }finally{await browser.close();}
});

test('Speaker audit: suggestions and uncertainty keep the original name visible',async()=>{
 const browser=await chromium.launch(launch);
 try{
  const page=await browser.newPage();
  const session={id:'audit',title:'Audit test',created:1792479600,status:'done',participants:['Anna','Luca'],segments:2};
  await page.route(base+'/api/sessions',route=>route.fulfill({json:[session]}));
  await page.route(base+'/api/sessions/audit',route=>route.fulfill({json:{...session,transcript:[
   {start:0,end:3,speaker:'Anna',source:'dom',text:'Testo invariato',speaker_proposal:{speaker:'Luca',status:'needs_review'}},
   {start:4,end:7,speaker:'Anna',source:'dom',text:'Altro testo',speaker_check:{status:'uncertain'}},
   {start:8,end:12,speaker:'Anna',source:'dom',text:'Frase ricomposta',context_inferred:true},
   {start:13,end:15,speaker:'Anna',source:'channel',text:'Canale separato',channel_inferred:true}
  ]}}));
  await page.goto(base+'/#'+token);
  await page.waitForFunction(()=>document.querySelectorAll('.utterance').length===4);
  const names=await page.locator('.utterance strong').allTextContents();
  assert.match(names[0],/Anna.*Luca.*da verificare/);
  assert.match(names[1],/Anna.*voce non confermata/);
  assert.match(names[2],/Anna.*continuità stimata/);
  assert.match(names[3],/Anna.*canale remoto/);
  assert.equal(await page.locator('.utterance p').first().textContent(),'Testo invariato');
 }finally{await browser.close();}
});
