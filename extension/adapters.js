/* Observable DOM only: no internal tokens, call APIs, or outbound requests.
   These adapters are heuristics, not a stable provider API. */
(() => {
  function visible(el) {
    if(el.closest('[aria-hidden="true"]'))return false;
    if(el.checkVisibility&&!el.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}))return false;
    const box=el.getBoundingClientRect();
    return box.width>0&&box.height>0&&getComputedStyle(el).visibility!=='hidden';
  }
  function clean(s) { return (s||'').replace(/\s+/g,' ').trim().slice(0,100); }
  function snapshot(doc = document, host = location.hostname) {
    const meet = host === 'meet.google.com';
    const tiles = [...doc.querySelectorAll(meet ? '[data-participant-id], [data-requested-participant-id]' : '[data-tid="participant-tile"], [data-tid="video-tile"], [data-participant-id]')];
    const participants = new Set(), speakers = new Set();
    for (const tile of tiles) {
      if (!visible(tile)) continue;
      const label = tile.querySelector(meet ? '[data-self-name], [data-participant-name], .zWGUib, .notranslate' : '[data-tid="participant-name"], [data-tid="display-name"], [data-participant-name]');
      const name = clean(tile.getAttribute('data-participant-name') || label?.getAttribute('data-self-name') || label?.getAttribute('data-participant-name') || label?.textContent);
      if (!name) continue;
      participants.add(name);
      // Use explicit speaking state or a visible speaking indicator; never infer
      // from a merely present audio-level widget, focus, selection, or tile order.
      const explicit = tile.matches('[data-is-speaking="true"], [data-speaking="true"]');
      const indicators = [...tile.querySelectorAll('[data-is-speaking="true"], [data-speaking="true"], [data-tid="speaking-indicator"], [aria-label]')];
      const knownIndicator = meet ? '.IisKdb, .wnPUne' : '.vdi-frame-occlusion';
      const visual = [tile, ...tile.querySelectorAll(knownIndicator)].some(el => el.matches(knownIndicator) && visible(el));
      const active = explicit || visual || indicators.some(el => visible(el) && (
        el.matches('[data-is-speaking="true"], [data-speaking="true"], [data-tid="speaking-indicator"]') ||
        /^(speaking|sta parlando|sta intervenendo)$| (is speaking|sta parlando)$/i.test(clean(el.getAttribute('aria-label')))
      ));
      const self=tile.matches('[data-is-self="true"], [data-self="true"]')||!!tile.querySelector('[data-self-name]')||/^(you|tu)$|\((you|tu)\)$/i.test(name);
      if (active&&!self) speakers.add(name);
    }
    return {participants:[...participants], speakers:[...speakers]};
  }
  globalThis.LocalCallAdapter = {snapshot};
})();
