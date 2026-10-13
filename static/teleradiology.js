(() => {
  const toggle = document.getElementById('tr-annotations');
  toggle?.addEventListener('change', () => document.querySelectorAll('.tr-overlay').forEach(g => { g.style.display = toggle.checked ? '' : 'none'; }));
  const button = document.getElementById('tr-insert-draft');
  const form = document.getElementById('tr-form');
  if (button && form) button.addEventListener('click', () => {
    const draft = JSON.parse(button.dataset.draft || '{}');
    const radio = form.querySelector(`input[name="concordance"][value="${draft.concordance}"]`);
    if (radio) radio.checked = true;
    ['birads', 'findings', 'assessment', 'recommendation'].forEach(name => {
      const field = form.elements[name];
      if (!field || draft[name] === undefined) return;
      field.value = draft[name];
      field.classList.remove('tr-filled'); void field.offsetWidth; field.classList.add('tr-filled');
    });
    button.textContent = '✓ AI-drafted wording inserted — review before signing';
    button.disabled = true;
    form.elements.findings?.focus();
  });
  form?.addEventListener('submit', () => {
    const sign = form.querySelector('.tr-sign');
    if (sign && form.checkValidity()) { sign.disabled = true; sign.textContent = 'Signing report…'; }
  });
})();
