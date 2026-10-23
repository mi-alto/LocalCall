/* Observable DOM only: no internal tokens, call APIs, or outbound requests.
   These adapters are heuristics, not a stable provider API. */
(() => {
  function visible(el, accessibilityHidden=false) {
    if(!accessibilityHidden&&el.closest('[aria-hidden="true"]'))return false;
    if(el.checkVisibility&&!el.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}))return false;
    const box=el.getBoundingClientRect();
    return box.width>0&&box.height>0&&getComputedStyle(el).visibility!=='hidden';
  }
  // Teams audio-stage is aria-hidden for accessibility, not visually hidden.
  // Its outline may be painted by CSS without an independent bounding box.
  function renderedOutline(el,tile) {
    for(let node=el;node;node=node.parentElement){
      const css=getComputedStyle(node);
      if(node.hidden||css.display==='none'||css.visibility==='hidden'||css.visibility==='collapse'||Number(css.opacity)===0)return false;
      if(node===tile)break;
    }
    return visible(tile,true);
  }
  function clean(s) { return (s||'').replace(/\s+/g,' ').trim().slice(0,100); }
  function emailAddress(value){
    const email=(value||'').trim();
    return email.length<=254&&/^[A-Z0-9.!#$%&'*+\/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9.-]*[A-Z0-9])?\.[A-Z]{2,}$/i.test(email)?email:'';
  }
  function tileEmails(tile,label,meet){
    const values=[];
    for(const el of [tile,label])if(el){
      values.push(el.getAttribute('data-email'),el.getAttribute('data-email-address'));
    }
    // Observed in Teams: the stream tile's data-tid can be an email.
    // Never interpret opaque participant IDs or fetch private profile APIs.
    if(!meet&&tile.matches('[data-cid="calling-participant-stream"]'))values.push(tile.getAttribute('data-tid'));
    for(const el of tile.querySelectorAll('a[href^="mailto:"]'))if(visible(el)){
      try{values.push(decodeURIComponent(el.getAttribute('href').slice(7).split('?')[0]));}catch{}
    }
    return [...new Set(values.map(emailAddress).filter(Boolean))];
  }
  function snapshot(doc = document, host = location.hostname) {
    const meet = host === 'meet.google.com';
    const tiles = [...doc.querySelectorAll(meet ? '[data-participant-id], [data-requested-participant-id]' : '[data-cid="calling-participant-stream"], [data-tid="myself-video"], [data-tid="participant-tile"], [data-tid="video-tile"], [data-participant-id]')];
    const participants = new Set(), speakers = new Set(), contacts = new Map(), selves = new Set();
    for (const tile of tiles) {
      if (!visible(tile,!meet)) continue;
      // Selector lists follow DOM order, not selector priority: an icon can precede the name.
      const isName=el=>!el.matches('.google-symbols, .material-icons, .material-symbols-outlined, [data-icon-name]')&&
        !/^(keep|keep_off|keep_outline|frame_person|sticker)$/.test(clean(el.textContent));
      const label = meet ? ['[data-participant-name]', '.zWGUib', '[data-self-name]', '.notranslate']
        .map(selector=>[...tile.querySelectorAll(selector)].find(isName)).find(Boolean) :
        tile.querySelector('[data-tid="participant-info-nametag"] [data-person-mri], [data-tid="participant-name"], [data-tid="display-name"], [data-participant-name]');
      const name = clean(tile.getAttribute('data-participant-name') || label?.getAttribute('data-participant-name') || label?.textContent || label?.getAttribute('data-self-name'));
      if (!name) continue;
      participants.add(name);
      for(const email of tileEmails(tile,label,meet))contacts.set(name+'\0'+email.toLowerCase(),{name,email});
      // Use explicit speaking state or a visible speaking indicator; never infer
      // from a merely present audio-level widget, focus, selection, or tile order.
      const explicit = tile.matches('[data-is-speaking="true"], [data-speaking="true"]');
      const indicators = [...tile.querySelectorAll('[data-is-speaking="true"], [data-speaking="true"], [data-tid="speaking-indicator"], [aria-label]')];
      const knownIndicator = meet ? '.IisKdb, .wnPUne' : '[data-tid="voice-level-stream-outline"][data-is-speaking="true"]';
      const visual = [tile, ...tile.querySelectorAll(knownIndicator)].some(el => el.matches(knownIndicator) && (meet?visible(el):renderedOutline(el,tile)));
      const active = explicit || visual || indicators.some(el => visible(el,!meet) && (
        el.matches('[data-is-speaking="true"], [data-speaking="true"], [data-tid="speaking-indicator"]') ||
        /^(speaking|sta parlando|sta intervenendo)$| (is speaking|sta parlando)$/i.test(clean(el.getAttribute('aria-label')))
      ));
      const self=tile.matches('[data-tid="myself-video"], [data-is-self="true"], [data-self="true"]')||(!!label?.hasAttribute('data-self-name')&&name===clean(label.getAttribute('data-self-name')))||/^(you|tu)$|\((you|tu)\)$/i.test(name);
      if (self) selves.add(name);
      if (active&&!self) speakers.add(name);
    }
    return {participants:[...participants], speakers:[...speakers], ...(selves.size===1?{self_name:[...selves][0]}:{}), ...(contacts.size?{contacts:[...contacts.values()]}:{})};
  }
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
  function inMeeting() {
    // Presence, not CSS visibility: toolbars can hide while presenting.
    if([...document.querySelectorAll('#prejoin-join-button, [data-tid="prejoin-join-button"]')].some(el=>visible(el,true)))return false;
    if([...document.querySelectorAll('[data-tid="calling-stage-container"], [data-tid="modern-stage-wrapper"], [data-tid="audio-stage"]')].some(el=>visible(el,true)))return true;
    return !!document.querySelector('#hangup-button, [data-tid="call-hangup"], [data-tid="hangup-button"], button[aria-label="Leave call"], button[aria-label="Leave meeting"], button[aria-label="Abbandona la chiamata"], button[aria-label="Abbandona la riunione"], button[aria-label="Esci dalla chiamata"]');
  }
  function meetingPhase() {
    if(inMeeting())return 'active';
    if([...document.querySelectorAll('#prejoin-join-button, [data-tid="prejoin-join-button"]')].some(el=>visible(el,true)))return 'prejoin';
    return 'unknown';
  }
  function microphoneMuted() {
    const controls=[...document.querySelectorAll('#microphone-button, button[aria-label], [role="button"][aria-label]')];
    const states=[];
    for(const el of controls){
      if(el.closest('[data-participant-id], [data-cid="calling-participant-stream"]'))continue;
      const label=(el.getAttribute('aria-label')||'').trim().toLowerCase();
      // Action labels describe what clicking WILL do, not the current state.
      if(/^(unmute(?: microphone)?|turn on microphone|attiva(?: il)? microfono|riattiva(?: il)? microfono)(?:$|\s*[(（])/i.test(label))states.push(true);
      else if(/^(mute(?: microphone)?|turn off microphone|disattiva(?: il)? microfono)(?:$|\s*[(（])/i.test(label))states.push(false);
    }
    return states.length&&states.every(s=>s===states[0])?states[0]:null;
  }
  globalThis.LocalCallAdapter = {microphoneMuted, inMeeting, meetingPhase, snapshot, meetingTitle:()=>meetingTitle(document.title)};
})();
