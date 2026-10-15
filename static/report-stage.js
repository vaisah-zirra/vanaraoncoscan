// Report stage: completing the download finishes the journey, then (2 s later)
// walkthrough participants are invited to rate the experience.
(() => {
  const tick = '<svg viewBox="0 0 16 16"><path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  const completeJourney = () => {
    const step = document.querySelector('.journey li:last-child');
    if (!step || step.classList.contains('js-done')) return;
    step.classList.remove('js-current'); step.classList.add('js-done');
    const dot = step.querySelector('.journey-dot'); if (dot) dot.innerHTML = tick;
    const note = step.querySelector('.journey-note'); if (note) note.textContent = 'Done';
    const meta = document.querySelector('.journey-meta');
    if (meta && meta.firstChild && meta.firstChild.nodeType === 3) {
      meta.firstChild.textContent = meta.firstChild.textContent.replace(/^\d+/, n => String(Math.min(6, +n + 1)));
    }
  };

  const offerFeedback = (statusUrl) => {
    const dialog = document.querySelector('[data-report-feedback]');
    if (!dialog || typeof dialog.showModal !== 'function' || dialog.open) return;
    if (document.querySelector('dialog[open]')) return; // another prompt is already showing
    let attempts = 0;
    const check = async () => {
      try {
        const response = await fetch(statusUrl, { headers: { Accept: 'application/json' } });
        if (response.ok && (await response.json()).prompt) {
          dialog.showModal();
          dialog.addEventListener('cancel', (event) => { event.preventDefault(); dialog.querySelector('form').requestSubmit(); }, { once: true });
          return;
        }
      } catch (_) { /* the next page visit will offer feedback */ }
      if (++attempts < 4) setTimeout(check, 1500);
    };
    check();
  };

  document.addEventListener('click', (event) => {
    const link = event.target.closest('[data-report-download]');
    if (!link) return;
    const box = link.closest('.rs-download');
    const state = box && box.querySelector('[data-report-state]');
    setTimeout(() => {
      if (box) box.classList.add('is-done');
      if (state) state.textContent = '✓ Report downloaded. Check your downloads folder.';
      completeJourney();
    }, 400);
    const hero = document.querySelector('[data-feedback-status]');
    if (hero) setTimeout(() => offerFeedback(hero.dataset.feedbackStatus), 2000);
  });
})();
