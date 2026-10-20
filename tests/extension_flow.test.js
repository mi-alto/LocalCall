import {test} from 'node:test';
import assert from 'node:assert/strict';
import {chromium} from '@playwright/test';
import {readFileSync,mkdtempSync,rmSync,cpSync,readdirSync,writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
const executablePath=process.env.CHROMIUM_PATH||chromium.executablePath();
const platform=process.env.LOCALCALL_PLATFORM||'meet';
const meetingOrigin=platform==='teams'?'https://teams.microsoft.com':'https://meet.google.com';

test(`Real extension popup, worker, offscreen, tab capture and page observer on simulated ${platform}`,{skip:process.env.LOCALCALL_NATIVE_ACTION!=='1'},async()=>{
 const dir=mkdtempSync(path.join(tmpdir(),'localcall-flow-'));
 const server=spawn('python3',['-m','localcall.server','--port','0','--data',path.join(dir,'data')]);
 let context;
 try{
 const output=await new Promise((resolve,reject)=>{let data='';const timer=setTimeout(()=>reject(Error('Server startup timeout')),10000);server.stdout.on('data',c=>{data+=c;if(data.includes('LocalCall:')){clearTimeout(timer);resolve(data);}});});
 const base=output.match(/http:\/\/127\.0\.0\.1:\d+/)[0];
 const token=readFileSync(path.join(dir,'data/token'),'utf8').trim();
 const extensionPath=path.join(dir,'extension');cpSync('extension',extensionPath,{recursive:true});
 for(const name of readdirSync(extensionPath)){if(/\.(js|json)$/.test(name)){const f=path.join(extensionPath,name);writeFileSync(f,readFileSync(f,'utf8').replaceAll('http://127.0.0.1:8765',base));}}
 context=await chromium.launchPersistentContext(path.join(dir,'profile'),{headless:false,executablePath,args:[`--disable-extensions-except=${extensionPath}`,`--load-extension=${extensionPath}`,'--autoplay-policy=no-user-gesture-required']});
 const worker=context.serviceWorkers()[0]||await context.waitForEvent('serviceworker');
 const id=new URL(worker.url()).hostname;
 await worker.evaluate(async config=>chrome.storage.local.set(config),{token,language:'it',microphone:false});
 const wav=readFileSync('.test-output/italiano.wav').toString('base64');
 await context.route(meetingOrigin+'/**',route=>route.fulfill({contentType:'text/html',body:`<html><body><h1>Call sintetica</h1><div data-tid="participant-tile" data-participant-id="anna" data-is-speaking="true"><span data-tid="participant-name" class="zWGUib">Anna</span></div><audio id="voice" src="data:audio/wav;base64,${wav}" loop></audio></body></html>`}));
 const meet=await context.newPage();await meet.goto(meetingOrigin+'/aaa-bbbb-ccc');
 await meet.locator('body').click();await meet.evaluate(()=>document.getElementById('voice').play());
 await meet.bringToFront();
 // A native toolbar/keyboard action must grant activeTab. Programmatic openPopup does not.
 const cdp=await context.browser().newBrowserCDPSession();
 console.log('ACTION_REQUIRED: invoke LocalCall using Command+Shift+Y in the isolated browser.');
 let popupTarget;
 for(let n=0;n<600;n++){const targets=await cdp.send('Target.getTargets');popupTarget=targets.targetInfos.find(t=>t.url===`chrome-extension://${id}/popup.html`);if(popupTarget)break;await new Promise(r=>setTimeout(r,100));}
 assert.ok(popupTarget,'Popup target missing');
 const attached=await cdp.send('Target.attachToTarget',{targetId:popupTarget.targetId,flatten:false});
 let commandId=0;
 async function popupEval(expression){
  const command=++commandId;
  return new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error('Popup evaluation timed out')),10000);
   const listener=event=>{if(event.sessionId!==attached.sessionId)return;const m=JSON.parse(event.message);if(m.id!==command)return;clearTimeout(timer);cdp.off('Target.receivedMessageFromTarget',listener);if(m.error||m.result?.exceptionDetails)reject(Error(JSON.stringify(m)));else resolve(m.result?.result?.value);};
   cdp.on('Target.receivedMessageFromTarget',listener);
   cdp.send('Target.sendMessageToTarget',{sessionId:attached.sessionId,message:JSON.stringify({id:command,method:'Runtime.evaluate',params:{expression,awaitPromise:true,userGesture:true,returnByValue:true}})}).catch(reject);
  });
 }
 for(let n=0;n<50;n++){if(await popupEval('document.readyState')==='complete')break;await new Promise(r=>setTimeout(r,100));}
 await popupEval('window.observedStatuses=[];new MutationObserver(()=>observedStatuses.push(document.getElementById("status").textContent)).observe(document.getElementById("status"),{childList:true});document.getElementById("start").click()');
 let recording;
 for(let n=0;n<100;n++){recording=await worker.evaluate(()=>handle({target:'worker',type:'status'},{}));if(recording.status==='recording'||recording.error)break;await new Promise(r=>setTimeout(r,200));}
 assert.equal(recording.status,'recording',JSON.stringify({recording,popup:await popupEval('window.observedStatuses')}));
 assert.equal(await worker.evaluate(()=>chrome.offscreen.hasDocument()),true);
 await cdp.send('Target.closeTarget',{targetId:popupTarget.targetId});
 await new Promise(r=>setTimeout(r,4500));
 const active=await worker.evaluate(()=>chrome.runtime.sendMessage({target:'recorder',type:'status'}));
 assert.equal(active.status,'recording');assert.ok(active.speakers.includes('Anna'));
 // Page reload must restore observation with the original recording still active.
 await meet.reload();await meet.evaluate(()=>document.getElementById('voice').play());
 await new Promise(r=>setTimeout(r,3000));
 const again=await worker.evaluate(()=>chrome.runtime.sendMessage({target:'recorder',type:'status'}));
 assert.equal(again.status,'recording');assert.ok(again.speakers.includes('Anna'));
 const stopped=await worker.evaluate(()=>handle({target:'worker',type:'stop'},{url:chrome.runtime.getURL('popup.html')}));
 assert.equal(stopped.status,'saved');
 let session;
 for(let n=0;n<90;n++){session=await (await fetch(`${base}/api/sessions/${active.sessionId}`,{headers:{Authorization:'Bearer '+token}})).json();if(['done','error'].includes(session.status))break;await new Promise(r=>setTimeout(r,1000));}
 assert.equal(session.status,'done',session.error);assert.ok(session.event_count>4);assert.ok(session.transcript.some(r=>r.speaker==='Anna'&&/progetto/i.test(r.text)));
 }finally{await context?.close();server.kill('SIGTERM');if(server.exitCode===null)await new Promise(r=>server.once('exit',r));rmSync(dir,{recursive:true,force:true});}
});
