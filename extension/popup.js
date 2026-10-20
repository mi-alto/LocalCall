const $=id=>document.getElementById(id);
let lastError='', activating=false, refreshing=false;
const labels={idle:'Pronto · nessuna registrazione',starting:'Avvio della registrazione…',recording:'● Registrazione in corso',stopping:'Salvataggio della registrazione…',saved:'Registrazione terminata · trascrizione avviata sul Mac',error:'Registrazione interrotta'};
async function send(type){let tabId;if(type==='start'){const [tab]=await chrome.tabs.query({active:true,currentWindow:true});tabId=tab?.id;if(tab?.url){const origin=new URL(tab.url).origin+'/*';if(!await chrome.permissions.contains({origins:[origin]}))await chrome.permissions.request({origins:[origin]});}}return chrome.runtime.sendMessage({target:'worker',type,tabId});}
async function serviceOnline(){
  try{
    const {token}=await chrome.storage.local.get('token');
    if(!token)return false;
    return (await fetch('http://127.0.0.1:8765/api/status',{headers:{Authorization:'Bearer '+token},signal:AbortSignal.timeout(1500)})).ok;
  }catch{return false;}
}
async function refresh(){
  if(refreshing)return;
  refreshing=true;
  try{
    const [s,online]=await Promise.all([send('status'),serviceOnline()]);
    const recording=s.status==='recording';
    const busy=['starting','recording','stopping'].includes(s.status);
    $('status').textContent=labels[s.status]||'Stato non disponibile';
    $('status').className=recording?'recording-status':'';
    const warnings=[...(s.warnings||[]),...(s.observerStale?['Nomi non aggiornati: torna nella scheda della call.']:[])];
    $('warning').textContent=warnings.length?'Avvisi'+(recording?' · la registrazione continua':'')+': '+warnings.join(' '):'';
    $('error').textContent=s.error||lastError;
    $('micState').textContent=recording?(s.microphone==='active'?'Audio registrato: scheda + microfono. Il microfono registra anche quando sei in muto nella call.':'Audio registrato: solo la scheda. La tua voce dal microfono non viene registrata.') : '';
    $('people').textContent=recording?(s.speakers?.length?'Sta parlando: '+s.speakers.join(', '):'Nomi dei parlanti non rilevati: le parti senza attribuzione resteranno “Non identificato”.'):'';
    $('start').disabled=busy;
    $('start').textContent=recording?'● Registrazione in corso':'● Avvia registrazione';
    $('stop').disabled=!recording;
    $('activate').disabled=online||busy||activating;
    $('activate').textContent=activating?'Attivazione servizio…':online?'✓ Servizio attivo':busy?'Servizio non raggiungibile · verifica gli avvisi':'Attiva servizio sul Mac';
  }catch(error){$('error').textContent=error.message;}
  finally{refreshing=false;}
}
for(const type of ['start','stop']) $(type).onclick=async()=>{
  try{lastError='';$(type).disabled=true;const s=await send(type);if(s.error)throw Error(s.error);await refresh();}
  catch(e){lastError=e.message;$('error').textContent=e.message;$(type).disabled=false;}
};
$('activate').onclick=async()=>{
  activating=true;lastError='';$('activate').disabled=true;$('activate').textContent='Attivazione servizio…';
  try{const result=await send('activate-service');if(result.error)throw Error(result.error);}
  catch(e){lastError=e.message;}
  finally{activating=false;await refresh();}
};
$('settings').onclick=()=>chrome.runtime.openOptionsPage();
$('open').onclick=async()=>{const {token}=await chrome.storage.local.get('token');chrome.tabs.create({url:'http://127.0.0.1:8765/#'+(token||'')});};
refresh();setInterval(refresh,2000);
