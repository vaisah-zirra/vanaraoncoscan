document.querySelectorAll('[data-process-form]').forEach(form => {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (form.dataset.busy === 'true') return;
    form.dataset.busy = 'true';
    const button = form.querySelector('button');
    const dialog = document.getElementById('processing-dialog');
    const errorBox = document.getElementById('processing-error');
    const assessing = form.dataset.processKind === 'assess';
    document.getElementById('processing-title').textContent = assessing ? 'Preparing your assessment' : 'Checking the attached image';
    document.getElementById('processing-description').textContent = assessing ? 'Preparing the findings, source annotations and recommended next step.' : 'Verifying image integrity, dimensions and review resolution.';
    button.disabled = true; errorBox.hidden = true; dialog.showModal();
    try {
      const response = await fetch(form.getAttribute('action') || location.href, {method:'POST',body:new FormData(form),headers:{'X-Requested-With':'fetch'},credentials:'same-origin'});
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('The request could not be completed. Please reload and try again.');
      const data = await response.json();
      if (!response.ok || !data.redirect) throw new Error(data.error || 'The request could not be completed. Please reload and try again.');
      location.assign(data.redirect);
    } catch(error) {
      dialog.close(); errorBox.textContent = error.message || 'Connection interrupted. Please try again.';
      errorBox.hidden = false; errorBox.scrollIntoView({block:'center'});
      button.disabled = false; form.dataset.busy = 'false';
    }
  });
});
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
