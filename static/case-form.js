(() => {
  const form = document.getElementById('case-form');
  if (!form) return;
  const select = form.querySelector('select[name="patient"]');
  const concern = document.getElementById('concern');
  const count = document.getElementById('concern-count');
  const preview = document.getElementById('patient-preview');
  const contexts = JSON.parse(document.getElementById('patient-contexts').textContent || '{}');
  const updateCount = () => { count.textContent = concern.value.length; };
  const updatePreview = () => {
    const opt = select.selectedOptions[0];
    if (!opt || !opt.value) { preview.dataset.empty = 'true'; return; }
    const [name, ref] = opt.textContent.split(' · ');
    document.getElementById('pp-name').textContent = name.trim();
    document.getElementById('pp-ref').textContent = 'Reference ' + (ref || '').trim();
    document.getElementById('pp-avatar').textContent = name.trim().charAt(0).toUpperCase();
    preview.dataset.empty = 'false';
    const status = document.getElementById('context-status');
    status.classList.toggle('loaded', !!contexts[opt.value]);
  };
  select.addEventListener('change', () => { setTimeout(() => { updatePreview(); updateCount(); }, 0); });
  concern.addEventListener('input', updateCount);
  updateCount(); updatePreview();
})();
