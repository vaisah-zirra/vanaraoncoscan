const PIPELINES = {
  quality: {title: 'Checking image quality', steps: [
    ['Verifying file integrity', 'sha256'], ['Decoding image data', 'decode'], ['Checking dimensions & resolution', 'res'], ['Assessing acquisition readiness', 'ready']]},
  assess: {title: 'Running AI assessment', steps: [
    ['Preprocessing · speckle reduction & normalisation', 'pre'], ['Detecting lesion candidates', 'detect'], ['Segmenting regions of interest', 'seg'],
    ['Extracting BI-RADS lexicon features', 'feat'], ['Classifying & calibrating confidence', 'cls'], ['Composing structured report', 'report']]},
};
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

async function runPipeline(kind, dialog) {
  const pipeline = PIPELINES[kind];
  const list = document.getElementById('ai-steps');
  const bar = document.getElementById('ai-progress-bar');
  const pct = document.getElementById('ai-progress-pct');
  const elapsed = document.getElementById('ai-elapsed');
  const live = document.getElementById('processing-description');
  document.getElementById('processing-title').textContent = pipeline.title;
  list.replaceChildren(...pipeline.steps.map(([label]) => { const li = document.createElement('li'); li.textContent = label; return li; }));
  const started = performance.now();
  const clock = setInterval(() => { elapsed.textContent = ((performance.now() - started) / 1000).toFixed(1) + ' s'; }, 100);
  const items = [...list.children];
  for (let i = 0; i < items.length; i++) {
    const [label, stage] = pipeline.steps[i];
    dialog.dataset.stage = stage;
    items[i].classList.add('active'); live.textContent = label;
    const base = kind === 'assess' ? 650 + Math.random() * 650 : 420 + Math.random() * 380;
    const steps = 8; const t0 = performance.now();
    for (let k = 1; k <= steps; k++) {
      await wait(reducedMotion ? base / 4 / steps : base / steps);
      const value = Math.round(((i + k / steps) / items.length) * 100);
      bar.style.width = value + '%'; pct.textContent = value + '%';
    }
    items[i].classList.replace('active', 'done');
    const ms = document.createElement('small'); ms.textContent = Math.round(performance.now() - t0) + ' ms'; items[i].append(ms);
  }
  dialog.dataset.stage = 'done';
  clearInterval(clock);
}

document.querySelectorAll('[data-process-form]').forEach(form => {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (form.dataset.busy === 'true') return;
    form.dataset.busy = 'true';
    const button = form.querySelector('button');
    const dialog = document.getElementById('processing-dialog');
    const errorBox = document.getElementById('processing-error');
    const kind = form.dataset.processKind === 'assess' ? 'assess' : 'quality';
    button.disabled = true; errorBox.hidden = true; dialog.showModal();
    const request = fetch(form.getAttribute('action') || location.href, {method:'POST',body:new FormData(form),headers:{'X-Requested-With':'fetch'},credentials:'same-origin'})
      .then(async response => {
        if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('The request could not be completed. Please reload and try again.');
        const data = await response.json();
        if (!response.ok || !data.redirect) throw new Error(data.error || 'The request could not be completed. Please reload and try again.');
        return data;
      });
    request.catch(() => {});
    try {
      const [data] = await Promise.all([request, runPipeline(kind, dialog)]);
      document.getElementById('processing-title').textContent = kind === 'assess' ? 'Assessment complete' : 'Quality check complete';
      document.getElementById('ai-progress-pct').textContent = '100%';
      try { sessionStorage.setItem('vos-reveal', new URL(data.redirect, location.href).pathname); } catch (e) {}
      await wait(reducedMotion ? 100 : 450);
      location.assign(data.redirect);
    } catch(error) {
      dialog.close(); errorBox.textContent = error.message || 'Connection interrupted. Please try again.';
      errorBox.hidden = false; errorBox.scrollIntoView({block:'center'});
      button.disabled = false; form.dataset.busy = 'false';
    }
  });
});

(function revealResult() {
  let target = null;
  try { target = sessionStorage.getItem('vos-reveal'); } catch (e) {}
  if (!target || target !== location.pathname) return;
  try { sessionStorage.removeItem('vos-reveal'); } catch (e) {}
  if (reducedMotion) return;
  document.documentElement.classList.add('reveal-ready');
  // Confidence ring and number count up.
  document.querySelectorAll('.confidence-card').forEach(card => {
    const arc = card.querySelector('.confidence-arc'); const label = card.querySelector('.confidence-ring > span');
    if (!arc || !label) return;
    const [score] = arc.getAttribute('stroke-dasharray').split(' ').map(Number);
    const decimals = String(score).includes('.') ? 1 : 0; const t0 = performance.now(); const duration = 1400;
    const frame = now => {
      const p = Math.min(1, (now - t0) / duration); const eased = 1 - Math.pow(1 - p, 3); const v = score * eased;
      arc.setAttribute('stroke-dasharray', `${v.toFixed(2)} ${(100 - v).toFixed(2)}`);
      label.firstChild.textContent = v.toFixed(decimals);
      if (p < 1) requestAnimationFrame(frame); else arc.setAttribute('stroke-dasharray', `${score} ${Math.round((100 - score) * 10) / 10}`);
    };
    arc.setAttribute('stroke-dasharray', '0 100'); label.firstChild.textContent = '0';
    requestAnimationFrame(frame);
  });
  // Confidence bar fills from zero.
  document.querySelectorAll('.sr-confidence-fill').forEach(fill => { const w = fill.style.width; fill.style.width = '0'; requestAnimationFrame(() => requestAnimationFrame(() => { fill.style.width = w; })); });
  // Report blocks and descriptor rows rise in as they scroll into view.
  const items = document.querySelectorAll('.sr-birads, .sr-confidence, .sr-h, .sr-meta, .sr-lesion-head, .sr-location, .sr-table tbody tr, .sr-ol li, .sr-list li, .sr-reasoning, .sr-patient, .results-details > .panel');
  items.forEach(el => el.classList.add('reveal-item'));
  let delay = 0; let last = 0;
  const io = new IntersectionObserver(entries => {
    entries.filter(e => e.isIntersecting).forEach(entry => {
      const now = performance.now(); delay = now - last > 400 ? 0 : delay + 70; last = now;
      setTimeout(() => entry.target.classList.add('revealed'), delay + 300);
      io.unobserve(entry.target);
    });
  }, {threshold: .15});
  items.forEach(el => io.observe(el));
})();
const processingDialog = document.getElementById('processing-dialog');
processingDialog?.addEventListener('cancel', event => event.preventDefault());
const toggle = document.getElementById('annotation-toggle');
toggle?.addEventListener('change', () => {
  document.querySelectorAll('.roi-overlay').forEach(group => {group.style.display = toggle.checked ? '' : 'none';});
});
const resultPreview = document.getElementById('result-preview');
const previewStage = document.getElementById('result-preview-stage');
const zoomButton = document.getElementById('result-zoom');
document.querySelectorAll('[data-expand]').forEach(button => button.addEventListener('click', () => {
  previewStage.replaceChildren(document.getElementById(button.dataset.expand).querySelector('svg').cloneNode(true));
  previewStage.classList.remove('zoomed'); zoomButton.textContent = 'Zoom in';
  document.getElementById('result-preview-title').textContent = button.dataset.title;
  resultPreview.showModal();
}));
zoomButton?.addEventListener('click', () => {
  previewStage.classList.toggle('zoomed'); zoomButton.textContent = previewStage.classList.contains('zoomed') ? 'Fit to view' : 'Zoom in';
});
document.getElementById('result-close')?.addEventListener('click', () => resultPreview.close());
window.addEventListener('pageshow', () => {
  document.querySelectorAll('[data-process-form]').forEach(form => {form.dataset.busy='false'; form.querySelector('button').disabled=false;});
  if (processingDialog?.open) processingDialog.close();
});
