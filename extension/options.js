const fields=['token','selfName','language','microphone','deviceId'];
const $=id=>document.getElementById(id);
async function devices(){const saved=await chrome.storage.local.get('deviceId');$('deviceId').replaceChildren(new Option('Predefinito di sistema',''));for(const d of await navigator.mediaDevices.enumerateDevices()){if(d.kind==='audioinput')$('deviceId').append(new Option(d.label||'Microfono',d.deviceId));}$('deviceId').value=saved.deviceId||'';}
devices().catch(()=>{});
chrome.storage.local.get(fields).then(c=>fields.forEach(k=>{if(c[k]!==undefined)$(k)[k==='microphone'?'checked':'value']=c[k];}));
$('save').onclick=async()=>{try{const c=Object.fromEntries(fields.map(k=>[k,$(k)[k==='microphone'?'checked':'value']]));const r=await fetch('http://127.0.0.1:8765/api/status',{headers:{Authorization:'Bearer '+c.token}});if(!r.ok)throw Error('Codice errato o app non disponibile');await chrome.storage.local.set(c);$('message').textContent='Abbinamento riuscito.';}catch(e){$('message').textContent=e.message;}};
$('permission').onclick=async()=>{try{const s=await navigator.mediaDevices.getUserMedia({audio:true});s.getTracks().forEach(t=>t.stop());await devices();$('message').textContent='Microfono abilitato. Scegli il dispositivo, attiva la casella e salva.';}catch(e){$('message').textContent='Microfono non disponibile: '+e.message;}};
