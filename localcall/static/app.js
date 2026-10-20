function meetingTitle(raw) {
  let title=(raw||'').replace(/\s+/g,' ').trim();
  const teams=/\s*[|–—-]\s*Microsoft Teams$/i.test(title);
  const meet=/^Meet\s*[-–—]|\s*[|–—-]\s*Google Meet$/i.test(title);
  if(teams||meet){
    title=title.replace(/^\(\d+\)\s*/, '');
    title=title.replace(/\s*[|–—-]\s*(Microsoft Teams|Google Meet)$/i,'');
    title=title.replace(/^(Partecipazione alla riunione|Join (the )?meeting)\s*\|\s*/i,'');
    title=title.replace(/^Meet\s*[-–—]\s*/i,'').trim();
  }
  return title||'Riunione senza titolo';
}
const $=id=>document.getElementById(id);
let token=location.hash.slice(1)||sessionStorage.getItem('localcall-token')||'';
history.replaceState(null,'',location.pathname+location.search);
$('token').value=token;
let renderedTranscriptKey=null;
let selected=new URLSearchParams(location.search).get('call'), recorder=null, stream=null, current=null, upload=Promise.resolve(), uploadError=null, pendingBytes=0;
const states={recording:'Registrazione',queued:'In coda',transcribing:'Trascrizione in corso',done:'Trascritta',error:'Errore',interrupted:'Interrotta'};
async function api(path,{body,method='GET',headers={}}={}) {
  const response=await fetch('/api/'+path,{method,headers:{Authorization:'Bearer '+token,...headers},body:body===undefined?undefined:body instanceof Blob?body:JSON.stringify(body),signal:AbortSignal.timeout(20000)});
  if(!response.ok){const e=await response.json();throw Error(e.error);}
  return response.json();
}
function message(e){$('message').textContent=e?.message||String(e||'');}
async function connect(){token=$('token').value.trim();const status=await api('status');sessionStorage.setItem('localcall-token',token);$('engine').textContent=status.model&&status.engine&&status.ffmpeg?'● MOTORE LOCALE PRONTO':'○ INSTALLAZIONE DA COMPLETARE';await refresh();}
$('connect').onclick=()=>connect().catch(message);
$('copy').onclick=()=>navigator.clipboard.writeText(token).then(()=>message('Codice copiato. Incollalo nelle impostazioni dell’estensione.')).catch(message);
let sessionsCache=[];
let setupView=new URLSearchParams(location.search).get('view')==='setup'||!token;
function setView(setup, push=true){
  setupView=setup;$('setupPage').hidden=!setup;$('detail').hidden=setup||!selected;$('emptyHistory').hidden=setup||!!selected;
  if(push)history.pushState(null,'',setup?'?view=setup':selected?'?call='+encodeURIComponent(selected):location.pathname);
}
$('setupLink').onclick=e=>{e.preventDefault();setView(true);};
window.addEventListener('popstate',()=>{const q=new URLSearchParams(location.search);selected=q.get('call');setView(q.get('view')==='setup',false);if(selected)show(selected,false).catch(message);});
setView(setupView,false);
for(const id of ['search','dateFrom','dateTo'])$(id).oninput=()=>renderHistory();
$('clearFilters').onclick=()=>{for(const id of ['search','dateFrom','dateTo'])$(id).value='';renderHistory();};
function searchKey(value){return String(value).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase();}
function localDay(created){const d=new Date(created*1000);return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');}
function namesFor(s){return [...new Set([...(s.participants||[]),...(s.latest_event?.participants||[]),...(s.transcript||[]).filter(r=>['dom','microphone'].includes(r.source)).map(r=>r.speaker)])];}
function renderHistory(){
  const query=searchKey($('search').value.trim()),from=$('dateFrom').value,to=$('dateTo').value;
  const invalid=from&&to&&from>to;
  const sessions=invalid?[]:sessionsCache.filter(s=>{
    const day=localDay(s.created);
    return (!from||day>=from)&&(!to||day<=to)&&(!query||searchKey(meetingTitle(s.title)+' '+namesFor(s).join(' ')+' '+(s.contacts||[]).map(c=>c.email).join(' ')).includes(query));
  });
  $('filterStatus').textContent=invalid?'La data Dal deve precedere la data Al.':sessions.length?`${sessions.length} registrazioni`:'Nessuna registrazione trovata.';
  $('sessions').replaceChildren();
  for(const s of sessions){
    const b=document.createElement('button');b.className='history-card';b.title=meetingTitle(s.title);b.setAttribute('aria-pressed',String(s.id===selected));
    const title=document.createElement('span');title.className='history-title';title.textContent=meetingTitle(s.title);
    const date=document.createElement('time');date.dateTime=new Date(s.created*1000).toISOString();date.textContent=callDate(s.created);
    const status=document.createElement('small');status.textContent=states[s.status]||s.status;
    b.append(title,date,status);b.onclick=()=>show(s.id).catch(message);$('sessions').append(b);
  }
}
function callDate(created){return new Intl.DateTimeFormat('it-IT',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(new Date(created*1000));}
async function refresh(){
  if(!token)return;
  sessionsCache=await api('sessions');renderHistory();
  if(!selected&&!setupView&&sessionsCache.length)selected=sessionsCache[0].id;
  if(selected)await show(selected,false);
}
async function show(id,navigate=true){const s=await api('sessions/'+id);selected=id;if(navigate)setView(false);else setView(setupView,false);renderHistory();$('participants').replaceChildren();const names=namesFor(s);for(const name of names){const li=document.createElement('li');li.textContent=name;const emails=[...new Set((s.contacts||[]).filter(c=>c.name===name).map(c=>c.email))];for(const email of emails){const address=document.createElement('small');address.className='participant-email';address.textContent=email;li.append(address);}$('participants').append(li);}if(!names.length){const li=document.createElement('li');li.textContent='Nessun nome rilevato';$('participants').append(li);}$('detailTitle').textContent=meetingTitle(s.title);$('detailDate').textContent='Inizio registrazione · '+callDate(s.created);$('detailStatus').textContent=states[s.status];$('diagnostic').textContent=s.error||(s.warnings?.length?s.warnings.join(' '):'')||'';$('retry').disabled=['queued','transcribing','done'].includes(s.status);$('delete').disabled=['recording','queued','transcribing'].includes(s.status);document.querySelectorAll('[data-export]').forEach(b=>b.disabled=s.status!=='done');const transcriptKey=JSON.stringify([id,s.status,s.segments,s.transcript]);if(renderedTranscriptKey===transcriptKey)return;renderedTranscriptKey=transcriptKey;$('transcript').replaceChildren();for(const row of s.transcript){const div=document.createElement('div');div.className='utterance';const t=document.createElement('time');t.textContent=new Date(row.start*1000).toISOString().slice(11,19);const n=document.createElement('strong');n.textContent=row.speaker;if(row.source!=='dom'&&row.source!=='microphone')n.className='uncertain';const p=document.createElement('p');p.textContent=row.text;p.style.margin='0';div.append(t,n,p);$('transcript').append(div);}if(!s.transcript.length){const p=document.createElement('p');p.className='empty';p.textContent=s.status==='done'?'Nessun parlato rilevato.':'Il testo comparirà qui al termine dell’elaborazione locale.';$('transcript').append(p);}}
$('record').onclick=async()=>{try{$('record').disabled=true;current=null;pendingBytes=0;message('');stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});current=await api('sessions',{method:'POST',body:{title:$('title').value,self_name:$('selfName').value,language:$('language').value}});await api(`sessions/${current.id}/tracks`,{method:'POST',body:{mic:0}});recorder=new MediaRecorder(stream,{mimeType:'audio/webm;codecs=opus'});let seq=0;uploadError=null;upload=Promise.resolve();recorder.ondataavailable=e=>{if(!e.data.size)return;pendingBytes+=e.data.size;if(pendingBytes>24*1024*1024){uploadError=Error('Salvataggio troppo lento: registrazione interrotta.');if(recorder.state==='recording')recorder.stop();}const n=seq++;upload=upload.then(async()=>{if(uploadError)return;for(let attempt=0;attempt<3;attempt++){try{await api(`sessions/${current.id}/audio/mic`,{method:'POST',body:e.data,headers:{'X-Sequence':String(n)}});return;}catch(err){if(attempt===2)throw err;}}}).catch(e=>{uploadError=e;message(e);if(recorder.state==='recording')recorder.stop();}).finally(()=>{pendingBytes-=e.data.size;});};recorder.onstop=finalize;recorder.onerror=()=>{uploadError=Error('Errore del microfono');if(recorder.state==='recording')recorder.stop();};stream.getTracks().forEach(t=>t.onended=()=>{if(recorder.state==='recording')recorder.stop();});recorder.start(2000);$('stop').disabled=false;$('recordBadge').textContent='● REGISTRAZIONE';selected=current.id;await refresh();}catch(e){stream?.getTracks().forEach(t=>t.stop());if(current)await api(`sessions/${current.id}/abort`,{method:'POST',body:{}}).catch(()=>{});$('record').disabled=false;message(e);}};
$('stop').onclick=()=>{if(recorder?.state==='recording'){recorder.stop();$('stop').disabled=true;}};
async function finalize(){stream.getTracks().forEach(t=>t.stop());await upload;try{await api(`sessions/${current.id}/${uploadError?'abort':'finish'}`,{method:'POST',body:{}});if(uploadError)throw uploadError;}catch(e){message(e);}finally{$('stop').disabled=true;$('record').disabled=false;$('recordBadge').textContent='● SALVATO';await refresh().catch(message);if(current)await show(current.id).catch(message);}}
$('retry').onclick=async()=>{try{await api(`sessions/${selected}/retry`,{method:'POST',body:{}});await refresh();}catch(e){message(e);}};
$('delete').onclick=async()=>{if(!confirm('Eliminare definitivamente audio e trascrizione di questa registrazione?'))return;try{await api('sessions/'+selected,{method:'DELETE'});selected=null;setView(false);await refresh();}catch(e){message(e);}};
document.querySelectorAll('[data-export]').forEach(b=>b.onclick=async()=>{try{const r=await fetch(`/api/sessions/${selected}/export.${b.dataset.export}`,{headers:{Authorization:'Bearer '+token}});if(!r.ok)throw Error('Esportazione non disponibile');const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download=`localcall-${selected}.${b.dataset.export}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){message(e);}});
window.addEventListener('beforeunload',e=>{if(recorder?.state==='recording'){e.preventDefault();e.returnValue='';}});
if(token)connect().catch(message);setInterval(()=>refresh().catch(()=>{}),3000);
