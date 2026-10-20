const SUPPORTED = /^https:\/\/(meet\.google\.com|teams\.microsoft\.com|teams\.live\.com|teams\.cloud\.microsoft)\//;
let starting = false;
let activating;
async function activateService() {
  if (!activating) activating = (async()=>{
    let result;
    try { result=await chrome.runtime.sendNativeMessage('org.localcall.launcher',{action:'start'}); }
    catch { throw Error('Collegamento Mac non installato. Segui INSTALLATION.md oppure avvia LocalCall dal Finder.'); }
    if(result?.error)throw Error(result.error);
    if(!result?.ok||typeof result.token!=='string')throw Error('Risposta del servizio non valida.');
    await chrome.storage.local.set({token:result.token});
    return {ok:true};
  })().finally(()=>{activating=null;});
  return activating;
}
async function ensureOffscreen() {
  if (!(await chrome.offscreen.hasDocument())) await chrome.offscreen.createDocument({url:'offscreen.html', reasons:['USER_MEDIA'], justification:'Registrare localmente audio della scheda e microfono durante la riunione.'});
}
async function handle(m, sender) {
  if (m.target !== 'worker') return;
  if (m.type === 'activate-service') {
    const internal=sender.url?.startsWith(chrome.runtime.getURL(''));
    const meeting=sender.tab && sender.frameId===0 && SUPPORTED.test(sender.url||'');
    if(!internal && !meeting)throw Error('Richiesta non autorizzata');
    // Return no token to a page content script.
    return activateService();
  }
  if (m.type === 'observation') {
    const {meetingTab} = await chrome.storage.session.get('meetingTab');
    if (sender.tab?.id !== meetingTab || sender.frameId !== 0) return {active:false};
    if (!(await chrome.offscreen.hasDocument())) return {active:false};
    return chrome.runtime.sendMessage({...m, target:'recorder'});
  }
  if (sender.tab && !sender.url?.startsWith(chrome.runtime.getURL(''))) throw Error('Richiesta non autorizzata');
  if (m.type === 'recorder-state') {
    if(sender.url!==chrome.runtime.getURL('offscreen.html'))return;
    const s=m.state;const bad=s.status==='error'||s.observerStale||s.warnings?.length;
    await chrome.action.setBadgeText({text:bad?'!':s.status==='recording'?'REC':''});
    await chrome.action.setBadgeBackgroundColor({color:bad?'#bd552f':'#277c57'});
    await chrome.action.setTitle({title:s.error||s.warnings?.join(' ')||'LocalCall · '+s.status});
    return {ok:true};
  }
  if (m.type === 'status') {
    if (!(await chrome.offscreen.hasDocument())) return {status:'idle'};
    return chrome.runtime.sendMessage({target:'recorder', type:'status'});
  }
  if (m.type === 'start') {
    if (starting) throw Error('Avvio in corso');
    starting = true;
    try {
      const tab = await chrome.tabs.get(m.tabId);
      if (!SUPPORTED.test(tab?.url || '')) throw Error('Apri prima la scheda della call Meet o Teams.');
      // Capture still requires the explicit toolbar action. Native startup never records.
      let existing=await chrome.storage.local.get('token');
      let online=false;
      if(existing.token)try{online=(await fetch('http://127.0.0.1:8765/api/status',{headers:{Authorization:'Bearer '+existing.token},signal:AbortSignal.timeout(1500)})).ok;}catch{}
      if(!online)await activateService();
      const config = await chrome.storage.local.get(['token', 'selfName', 'language', 'microphone', 'deviceId']);
      if (!config.token) throw Error('Configura prima il codice di abbinamento.');
      await ensureOffscreen();
      const current = await chrome.runtime.sendMessage({target:'recorder',type:'status'});
      if (['recording','starting','stopping'].includes(current.status)) throw Error('Una registrazione è già attiva.');
      await chrome.scripting.executeScript({target:{tabId:tab.id},files:['adapters.js','content.js']});
      const streamId = await chrome.tabCapture.getMediaStreamId({targetTabId:tab.id});
      await chrome.storage.session.set({meetingTab:tab.id});
      const result = await chrome.runtime.sendMessage({target:'recorder',type:'start',streamId,config,title:tab.title});
      if (result.error) throw Error(result.error);
      try { await chrome.tabs.sendMessage(tab.id,{type:'observe',epoch:result.epoch}); }
      catch (e) { await chrome.runtime.sendMessage({target:'recorder',type:'stop'}); throw Error('Pagina della call cambiata durante l’avvio. Riapri il plugin nella call.'); }
      return result;
    } finally { starting = false; }
  }
  if (m.type === 'stop') {
    const {meetingTab} = await chrome.storage.session.get('meetingTab');
    if (meetingTab) await chrome.tabs.sendMessage(meetingTab,{type:'stop-observing'}).catch(()=>{});
    return chrome.runtime.sendMessage({target:'recorder', type:'stop'});
  }
}
chrome.runtime.onMessage.addListener((m,sender,reply)=>{
  if(m.target !== 'worker') return;
  handle(m,sender).then(reply).catch(e=>reply({error:e.message}));
  return true;
});

chrome.tabs.onUpdated.addListener(async(tabId,change,tab)=>{
  if(change.status!=='complete'||!SUPPORTED.test(tab.url||''))return;
  const {meetingTab}=await chrome.storage.session.get('meetingTab');
  if(tabId!==meetingTab||!(await chrome.offscreen.hasDocument()))return;
  try{
    const s=await chrome.runtime.sendMessage({target:'recorder',type:'status'});
    if(s.status!=='recording')return;
    await chrome.scripting.executeScript({target:{tabId},files:['adapters.js','content.js']});
    await chrome.tabs.sendMessage(tabId,{type:'observe',epoch:s.epoch});
  }catch(e){await chrome.action.setBadgeText({text:'!'});}
});
