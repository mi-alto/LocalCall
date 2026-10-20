const fields=['token','selfName','language','microphone','deviceId'];
const $=id=>document.getElementById(id);
async function devices(selected=''){
  $('deviceId').replaceChildren(new Option('Predefinito di sistema',''));
  for(const d of await navigator.mediaDevices.enumerateDevices())if(d.kind==='audioinput')$('deviceId').append(new Option(d.label||'Microfono',d.deviceId));
  $('deviceId').value=selected;
  if($('deviceId').selectedIndex<0){$('deviceId').value='';$('message').textContent='Il dispositivo salvato non è collegato. Verifica il microfono predefinito.';}
}
const initialized=chrome.storage.local.get(fields).then(async c=>{
  fields.forEach(k=>{if(c[k]!==undefined)$(k)[k==='microphone'?'checked':'value']=c[k];});
  await devices(c.deviceId||'').catch(()=>{});
});
$('permission').onclick=async()=>{
  let stream;$('permission').disabled=true;
  try{
    await initialized;
    const selected=$('deviceId').value;
    stream=await navigator.mediaDevices.getUserMedia({audio:selected?{deviceId:{exact:selected}}:true});
    const track=stream.getAudioTracks()[0];
    if(!track||track.readyState!=='live')throw Error('Nessuna traccia audio disponibile');
    await chrome.storage.local.set({microphone:true,deviceId:selected});
    $('microphone').checked=true;
    await devices(selected);
    $('message').textContent='✓ Microfono pronto: '+(track.label||'predefinito')+'. La tua voce sarà inclusa dalla prossima registrazione. Non serve premere Salva.';
  }catch(e){$('message').textContent=microphoneError(e);}
  finally{stream?.getTracks().forEach(t=>t.stop());$('permission').disabled=false;}
};
$('microphone').onchange=async()=>{
  if($('microphone').checked){$('microphone').checked=false;await $('permission').onclick();}
  else{await chrome.storage.local.set({microphone:false});$('message').textContent='La prossima registrazione includerà solo la scheda.';}
};
$('deviceId').onchange=()=>{$('message').textContent='Premi Abilita e verifica il microfono per salvare questo dispositivo.';};
$('save').onclick=async()=>{
  await chrome.storage.local.set({selfName:$('selfName').value,language:$('language').value});
  $('message').textContent='Nome e lingua salvati per la prossima registrazione.';
};
$('pair').onclick=async()=>{try{
  const token=$('token').value;
  const response=await fetch('http://127.0.0.1:8765/api/status',{headers:{Authorization:'Bearer '+token},signal:AbortSignal.timeout(2000)});
  if(!response.ok)throw Error('Codice errato o servizio non disponibile');
  await chrome.storage.local.set({token});$('message').textContent='Abbinamento riuscito.';
}catch(e){$('message').textContent=e.message;}};
