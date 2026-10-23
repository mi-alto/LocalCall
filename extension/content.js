(() => {
  if(globalThis.__localCallObserver)return;
  globalThis.__localCallObserver=true;
  let timer, observer, lastMute, tick, holdUntil=0;
  function halt(){clearInterval(timer);timer=null;observer?.disconnect();observer=null;tick=null;}
  // Close the gate before processing a toolbar click; reopen only on a later,
  // confirmed unmuted observation. Keyboard/other-device changes use DOM updates.
  document.addEventListener('pointerdown',e=>{
    const button=e.target.closest?.('button,[role="button"]');
    if(timer&&button&&(button.id==='microphone-button'||/microphone|microfono|^mute|^unmute/i.test(button.getAttribute('aria-label')||''))){holdUntil=Date.now()+750;tick?.();}
  },true);
  chrome.runtime.onMessage.addListener((m,sender,reply)=>{
    if(m.type==='stop-observing'){halt();reply({ok:true});return;}
    if(m.type==='observe'){
      halt();
      tick=()=>{
        const microphoneMuted=Date.now()<holdUntil?null:LocalCallAdapter.microphoneMuted();lastMute=microphoneMuted;
        chrome.runtime.sendMessage({target:'worker',type:'observation',event:{observedAt:performance.timeOrigin+performance.now(),microphoneMuted,meetingPhase:LocalCallAdapter.meetingPhase(),inMeeting:LocalCallAdapter.inMeeting(),...LocalCallAdapter.snapshot()}})
          .then(r=>{if(r?.active===false)halt();}).catch(()=>{});
      };
      observer=new MutationObserver(()=>{if(LocalCallAdapter.microphoneMuted()!==lastMute)tick?.();});
      observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['aria-label','data-is-muted']});
      timer=setInterval(tick,500);tick();reply({ok:true});
    }
  });
})();
