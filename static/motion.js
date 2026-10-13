document.querySelectorAll('main > .toast-message').forEach((toast, i) => {
  toast.setAttribute('tabindex', '-1');
  const dismiss = () => { toast.classList.add('leaving'); setTimeout(() => toast.remove(), 400); };
  toast.addEventListener('click', dismiss);
  setTimeout(dismiss, 5200 + i * 600);
});

function showToast(text) {
  const main = document.querySelector('main'); if (!main) return;
  const toast = document.createElement('div'); toast.className = 'toast-message'; toast.setAttribute('role', 'status'); toast.textContent = text;
  main.prepend(toast);
}

document.querySelectorAll('[data-review-status]').forEach(panel => {
  const order = ['queued', 'assigned', 'reading', 'reporting', 'signed'];
  const label = panel.querySelector('.sp-stage-label');
  const paint = stage => {
    const at = order.indexOf(stage === 'reporting' ? 'reading' : stage);
    panel.querySelectorAll('.sp-stages li').forEach(li => {
      const i = order.indexOf(li.dataset.stage);
      const final = stage === 'signed';
      li.classList.toggle('done', final || i < at); li.classList.toggle('current', !final && i === at);
    });
  };
  let stopped = false;
  const poll = async () => {
    if (stopped) return;
    try {
      const response = await fetch(panel.dataset.reviewStatus, {headers: {'Accept': 'application/json'}, credentials: 'same-origin'});
      if (!response.ok) return;
      const data = await response.json();
      if (data.signed) {
        stopped = true; paint('signed');
        if (label) label.textContent = 'Report signed';
        showToast(`Teleradiology report received${data.reviewer ? ' from ' + data.reviewer : ''}${data.birads ? ' · BI-RADS ' + data.birads : ''}`);
        setTimeout(() => { history.replaceState(null, '', location.pathname + location.search + '#specialist-response'); location.reload(); }, 1800);
        return;
      }
      paint(data.stage || 'queued');
      if (label) label.textContent = data.label || '';
    } catch (e) {}
    setTimeout(poll, 1500);
  };
  poll();
});
