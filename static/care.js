// Care pages: auto-submit filters, and refresh when a pending second read gets signed.
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-autosubmit] select').forEach((s) => s.addEventListener('change', () => s.form.submit()));
  const pending = [...document.querySelectorAll('[data-pending-review]')].map((el) => el.dataset.pendingReview);
  if (!pending.length) return;
  let tries = 0;
  const check = async () => {
    for (const url of pending) {
      try {
        const res = await fetch(url, { headers: { Accept: 'application/json' } });
        if (res.ok && (await res.json()).signed) { window.location.reload(); return; }
      } catch (_) { /* try again shortly */ }
    }
    if (++tries < 120) setTimeout(check, 4000);
  };
  setTimeout(check, 3000);
});
