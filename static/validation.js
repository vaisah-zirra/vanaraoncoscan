document.addEventListener('DOMContentLoaded', () => {
  const dialog = document.querySelector('[data-feedback-prompt]');
  if (dialog && typeof dialog.showModal === 'function') {
    dialog.showModal();
    dialog.addEventListener('cancel', event => {
      event.preventDefault();
      dialog.querySelector('form').requestSubmit();
    });
  }
  if (document.querySelector('[data-walkthrough]')) {
    document.addEventListener('click', event => {
      const link = event.target.closest('a[href]');
      if (!link) return;
      const match = new URL(link.href).pathname.match(/^\/cases\/([a-f0-9-]+)\/report\.pdf$/);
      if (!match) return;
      // Read the persisted server result after the download, never assume a click means completion.
      let attempts = 0;
      const check = async () => {
        try {
          const response = await fetch(`/walkthrough/status/${match[1]}/`, {headers:{'Accept':'application/json'}});
          if (!response.ok) return;
          const result = await response.json();
          if (result.prompt) {
            window.location.assign('/walkthrough/');
          } else if (++attempts < 5) {
            window.setTimeout(check, 2000);
          }
        } catch (_) { /* The next page visit will offer feedback if the report completed. */ }
      };
      window.setTimeout(check, 2000);
    });
  }
});

// Star rating: fill every star up to the selected one, preview on hover/focus.
document.addEventListener('DOMContentLoaded', () => {
  const group = document.querySelector('[data-star-rating]');
  if (!group) return;
  const labels = [...group.querySelectorAll('label')];
  const caption = document.querySelector('[data-star-caption]');
  const words = ['Not useful', 'Slightly useful', 'Moderately useful', 'Useful', 'Very useful'];
  const selected = () => labels.findIndex(label => label.querySelector('input').checked);
  const paint = () => {
    const n = selected();
    labels.forEach((label, i) => label.classList.toggle('is-filled', n >= 0 && i <= n));
    if (caption) caption.textContent = n >= 0 ? `${n + 1} of 5 · ${words[n]}` : '';
  };
  const preview = (n) => {
    group.classList.toggle('is-previewing', n >= 0);
    labels.forEach((label, i) => label.classList.toggle('is-preview', n >= 0 && i <= n));
  };
  labels.forEach((label, i) => {
    label.addEventListener('mouseenter', () => preview(i));
    label.querySelector('input').addEventListener('change', paint);
  });
  group.addEventListener('mouseleave', () => preview(-1));
  paint();
});
