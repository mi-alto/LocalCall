(() => {
  if (window.top !== window || document.getElementById('localcall-invitation')) return;
  // A non-modal invitation; navigation alone never starts the backend or recording.
  const host=document.createElement('div');host.id='localcall-invitation';
  host.style.cssText='position:fixed;right:20px;bottom:20px;z-index:2147483647';
  const shadow=host.attachShadow({mode:'closed'});
  const box=document.createElement('section');
  box.style.cssText='font:14px system-ui;background:#fff;color:#17251e;border:1px solid #277c57;border-radius:12px;padding:16px;max-width:300px;box-shadow:0 5px 25px #0003';
  box.setAttribute('aria-label','LocalCall');
  const text=document.createElement('p');text.textContent='LocalCall: vuoi attivare il servizio locale per questa riunione? Nessun audio verrà registrato automaticamente.';
  const yes=document.createElement('button');yes.textContent='Attiva servizio';
  const no=document.createElement('button');no.textContent='Non ora';
  for(const button of [yes,no])button.style.cssText='font:inherit;padding:8px;margin:4px;cursor:pointer';
  no.onclick=()=>host.remove();
  yes.onclick=async(event)=>{
    if(!event.isTrusted)return;
    yes.disabled=true;text.textContent='Avvio sul Mac…';
    try{
      const result=await chrome.runtime.sendMessage({target:'worker',type:'activate-service'});
      if(result?.error)throw Error(result.error);
      text.textContent='Servizio pronto. Apri LocalCall dalla barra del browser e premi Avvia registrazione. Il modello si carica solo quando trascrivi.';
      yes.remove();no.textContent='Chiudi';
    }catch(error){text.textContent=error.message;yes.disabled=false;}
  };
  box.append(text,yes,no);shadow.append(box);document.documentElement.append(host);
})();
