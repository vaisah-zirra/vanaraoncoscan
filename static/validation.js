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
