(() => {
  if(globalThis.__localCallObserver)return;
  globalThis.__localCallObserver=true;
  let timer;
  function halt(){clearInterval(timer);timer=null;}
  chrome.runtime.onMessage.addListener((m,sender,reply)=>{
    if(m.type==='stop-observing'){halt();reply({ok:true});return;}
    if(m.type==='observe'){
      halt();
      const tick=()=>chrome.runtime.sendMessage({target:'worker',type:'observation',event:{observedAt:performance.timeOrigin+performance.now(),inMeeting:LocalCallAdapter.inMeeting(),...LocalCallAdapter.snapshot()}})
        .then(r=>{if(r?.active===false)halt();}).catch(()=>{});
      timer=setInterval(tick,500);tick();reply({ok:true});
    }
  });
})();
