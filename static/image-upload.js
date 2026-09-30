(() => {
  const picker = document.getElementById('sample-picker');
  const preview = document.getElementById('full-preview');
  const data = JSON.parse(document.getElementById('sample-data').textContent);
  const form = document.getElementById('sample-form');
  const attach = document.getElementById('attach-selected');
  const previewSelected = document.getElementById('preview-selected');
  const image = document.getElementById('preview-image');
  const zoom = document.getElementById('zoom-surface');
  const zoomButton = document.getElementById('zoom-image');
  let selected = null;
  let trigger = null;
  const size = bytes => `${(bytes / 1024).toFixed(0)} KB`;
  function showPreview(url, name) {
    image.src = url; image.alt = `Breast ultrasound image: ${name}`;
    document.getElementById('preview-title').textContent = name;
    zoom.classList.remove('zoomed'); zoomButton.textContent = 'Zoom in';
    preview.showModal();
  }
  document.querySelectorAll('[data-open-picker]').forEach(button => button.addEventListener('click', () => {
    trigger = button; picker.showModal(); document.getElementById('sample-search').focus();
  }));
  document.querySelector('[data-close-picker]').addEventListener('click', () => picker.close());
  picker.addEventListener('close', () => trigger?.focus());
  document.getElementById('close-preview').addEventListener('click', () => preview.close());
  [picker, preview].forEach(dialog => dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const r = dialog.getBoundingClientRect();
    if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close();
  }));
  form.addEventListener('change', event => {
    if (event.target.name !== 'sample') return;
    selected = data.find(sample => String(sample.id) === event.target.value);
    attach.disabled = !selected; previewSelected.disabled = !selected;
    document.getElementById('selection-title').textContent = selected.filename;
    document.getElementById('selection-meta').textContent = `${selected.format} · ${size(selected.size)} · ${selected.width} × ${selected.height} px`;
  });
  previewSelected.addEventListener('click', () => selected && showPreview(selected.url, selected.filename));
  document.querySelectorAll('[data-preview-url]').forEach(button => button.addEventListener('click', () => showPreview(button.dataset.previewUrl, button.dataset.previewName)));
  zoomButton.addEventListener('click', () => {
    zoom.classList.toggle('zoomed');
    zoomButton.textContent = zoom.classList.contains('zoomed') ? 'Fit to view' : 'Zoom in';
  });
  document.getElementById('sample-search').addEventListener('input', event => {
    const query = event.target.value.trim().toLowerCase();
    let count = 0;
    document.querySelectorAll('.sample-card').forEach(card => {
      card.hidden = !card.dataset.search.toLowerCase().includes(query);
      if (!card.hidden) count += 1;
    });
    document.getElementById('sample-no-results').hidden = count !== 0;
  });
  form.addEventListener('submit', () => {
    if (!form.checkValidity()) return;
    attach.disabled = true; attach.textContent = 'Attaching image…';
    form.setAttribute('aria-busy', 'true');
  });
  // A browser back navigation must not restore a permanently disabled submit button.
  window.addEventListener('pageshow', () => {
    attach.disabled = !form.querySelector('input[name="sample"]:checked');
    attach.textContent = 'Attach selected image →'; form.removeAttribute('aria-busy');
  });
})();
