const BASE='http://127.0.0.1:8765';
let state={status:'idle'}, config, session, epoch, audioEpoch=0, recorders=[], streams=[], context;
let queue=Promise.resolve(), eventQueue=Promise.resolve(), pendingBytes=0, eventBuffer=[], eventTimer, fault=null;
let eventBusy=false, lastObservation=0, micSource, micDestination, micLive=false, reconnecting=false;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const now=()=>performance.timeOrigin+performance.now();
function notify(){chrome.runtime.sendMessage({target:'worker',type:'recorder-state',state}).catch(()=>{});}
function warn(text){state.warnings=[...new Set([...(state.warnings||[]),text])];notify();}
async function api(path,body,headers={},attempts=4) {
  let last;
  for(let attempt=0;attempt<attempts;attempt++) {
    try {
      const response=await fetch(BASE+path,{method:'POST',headers:{Authorization:'Bearer '+config.token,...headers},body:body instanceof Blob?body:JSON.stringify(body),signal:AbortSignal.timeout(15000)});
      const result=await response.json();
      if(!response.ok){const e=Error(result.error);e.permanent=response.status<500;throw e;}
      return result;
    }catch(e){last=e;if(e.permanent)throw e;if(attempt+1<attempts)await sleep(500*2**attempt);}
  }
  throw last;
}
function enqueue(fn,bytes=0) {
  pendingBytes+=bytes;
  queue=queue.then(async()=>{if(!fault)await fn();}).catch(e=>{fault=e;state.error=e.message;void stop();}).finally(()=>{pendingBytes-=bytes;});
  if(pendingBytes>24*1024*1024&&!fault){fault=Error('Connessione locale troppo lenta: registrazione interrotta.');void stop();}
}
function flushEvents() {
  if(eventBusy||!eventBuffer.length)return eventQueue;
  const batch=eventBuffer.splice(0,100);
  eventBusy=true;
  // Metadata failure never cancels audio or blocks its upload queue.
  eventQueue=api(`/api/sessions/${session.id}/events`,batch,{},1)
    .catch(()=>warn('Alcuni nomi non sono stati salvati. L’audio continua.'))
    .finally(()=>{eventBusy=false;});
  return eventQueue;
}
async function attachMicrophone() {
  if(reconnecting)return;
  reconnecting=true;
  try{
    const audio={echoCancellation:true,noiseSuppression:true,autoGainControl:true};
    if(config.deviceId)audio.deviceId={exact:config.deviceId};
    const mic=await navigator.mediaDevices.getUserMedia({audio,video:false});
    if(!['starting','recording'].includes(state.status)){mic.getTracks().forEach(t=>t.stop());return;}
    streams.push(mic);
    micSource?.disconnect();
    micSource=context.createMediaStreamSource(mic);
    micSource.connect(micDestination);
    micLive=true;state.microphone='active';notify();
    mic.getAudioTracks().forEach(track=>track.addEventListener('ended',()=>{
      micSource?.disconnect();micLive=false;state.microphone='disconnected';
      warn('Microfono scollegato: continuo a registrare la riunione. La tua voce manca finché non si ricollega.');
    }));
  }catch(e){micLive=false;state.microphone='unavailable';warn('Microfono non disponibile: registro solo la scheda. Abilitalo nelle impostazioni per la prossima call.');}
  finally{reconnecting=false;}
}
navigator.mediaDevices.addEventListener('devicechange',()=>{
  if(state.status==='recording'&&config.microphone===true&&!micLive)void attachMicrophone();
});
async function start(m) {
  if(['recording','starting','stopping'].includes(state.status))throw Error('Registrazione già attiva');
  state={status:'starting',warnings:[]};config=m.config;session=null;fault=null;
  queue=Promise.resolve();eventQueue=Promise.resolve();eventBusy=false;pendingBytes=0;eventBuffer=[];recorders=[];streams=[];micLive=false;lastObservation=0;
  notify();
  try{
    const remote=await navigator.mediaDevices.getUserMedia({audio:{mandatory:{chromeMediaSource:'tab',chromeMediaSourceId:m.streamId}},video:false});
    streams.push(remote);
    context=new AudioContext();
    const remoteSource=context.createMediaStreamSource(remote);
    const remoteDestination=context.createMediaStreamDestination();
    remoteSource.connect(context.destination); // Preserve meeting playback after tab capture.
    remoteSource.connect(remoteDestination);
    micDestination=context.createMediaStreamDestination();
    // A continuous silent source keeps both recorded timelines on the same media clock.
    const silence=context.createConstantSource();silence.offset.value=0;
    silence.connect(remoteDestination);silence.connect(micDestination);silence.start();
    await context.resume();
    if(config.microphone===true)await attachMicrophone();else state.microphone='off';
    const requestId=crypto.randomUUID().replaceAll('-','');
    session=await api('/api/sessions',{title:m.title,self_name:config.selfName||'Io',language:config.language||'auto'},{'X-Request-Id':requestId});
    const tracks={remote:0};
    const capture=[['remote',remoteDestination.stream]];
    if(config.microphone===true){tracks.mic=0;capture.push(['mic',micDestination.stream]);}
    await api(`/api/sessions/${session.id}/tracks`,tracks);
    for(const [name,stream] of capture){
      const recorder=new MediaRecorder(stream,{mimeType:'audio/webm;codecs=opus',audioBitsPerSecond:64000});
      let seq=0;
      recorder.ondataavailable=e=>{if(e.data.size){const n=seq++;enqueue(()=>api(`/api/sessions/${session.id}/audio/${name}`,e.data,{'X-Sequence':String(n),'Content-Type':'audio/webm'}),e.data.size);}};
      recorder.onerror=e=>{fault=Error(e.error?.message||'Errore registrazione');void stop();};
      recorders.push(recorder);
    }
    epoch=now();audioEpoch=context.currentTime;
    recorders.forEach(rec=>rec.start(2000));
    state={...state,status:'recording',sessionId:session.id,epoch,participants:[],speakers:[]};
    remote.getAudioTracks().forEach(t=>t.addEventListener('ended',()=>void stop()));
    eventTimer=setInterval(()=>{
      flushEvents();
      if(now()-(lastObservation||epoch)>5000){state.observerStale=true;state.speakers=[];notify();}
    },2000);
    notify();return state;
  }catch(e){
    streams.forEach(s=>s.getTracks().forEach(t=>t.stop()));
    if(context)await context.close().catch(()=>{});
    state={status:'error',error:e.message};notify();
    if(session)await api(`/api/sessions/${session.id}/abort`,{}).catch(()=>{});
    throw e;
  }
}
async function stop() {
  if(state.status!=='recording')return state;
  state.status='stopping';notify();clearInterval(eventTimer);
  await Promise.all(recorders.map(rec=>new Promise(resolve=>{
    if(rec.state==='inactive')return resolve();
    rec.addEventListener('stop',resolve,{once:true});rec.stop();
  })));
  streams.forEach(s=>s.getTracks().forEach(t=>t.stop()));
  if(context)await context.close().catch(()=>{});
  await eventQueue;
  while(eventBuffer.length)await flushEvents();
  await queue;
  try{
    if(fault){await api(`/api/sessions/${session.id}/abort`,{});throw fault;}
    await api(`/api/sessions/${session.id}/finish`,{warnings:state.warnings});
    state={status:'saved',sessionId:session.id,warnings:state.warnings};
  }catch(e){state={status:'error',sessionId:session.id,error:e.message+' — I blocchi ricevuti sono conservati sul Mac.'};}
  notify();return state;
}
chrome.runtime.onMessage.addListener((m,sender,reply)=>{
  if(m.target!=='recorder')return;
  if(m.type==='status'){reply(state);return;}
  if(m.type==='observation'){
    if(state.status==='recording'){
      const e=m.event||{};
      const valid=Array.isArray(e.speakers)&&Array.isArray(e.participants);
      const delayed=typeof e.observedAt!=='number'||now()-e.observedAt>1250||now()<e.observedAt;
      if(valid){
        const speakers=delayed||e.speakers.length>30?[]:e.speakers.map(n=>String(n).slice(0,100));
        eventBuffer.push({t:Math.max(0,context.currentTime-audioEpoch),speakers,participants:e.participants.slice(0,100)});
        if(eventBuffer.length>100)eventBuffer.splice(0,eventBuffer.length-100);
        state.participants=e.participants;state.speakers=speakers;state.observerStale=delayed;lastObservation=now();
      }
    }
    reply({ok:true,active:state.status==='recording'});return;
  }
  if(!['start','stop'].includes(m.type)){reply({error:'Comando sconosciuto'});return;}
  (m.type==='start'?start(m):stop()).then(reply).catch(e=>reply({error:e.message}));return true;
});
