// Validation dashboard: tabbed people lists, instant search and auto-submitting source filter.
document.addEventListener('DOMContentLoaded', () => {
  const tabs = [...document.querySelectorAll('.vd-tabs [data-tab]')];
  const search = document.querySelector('[data-people-search]');
  const activePanel = () => document.querySelector('.vd-panel:not([hidden])');
  const filter = () => {
    const panel = activePanel();
    if (!panel || !search) return;
    const q = search.value.trim().toLowerCase();
    let shown = 0;
    panel.querySelectorAll('tbody tr').forEach((row) => {
      const hit = !q || (row.dataset.search || '').includes(q);
      row.hidden = !hit; if (hit) shown += 1;
    });
    const none = panel.querySelector('.vd-noresults');
    if (none) none.hidden = shown > 0;
  };
  tabs.forEach((tab) => tab.addEventListener('click', () => {
    tabs.forEach((t) => {
      const on = t === tab;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      document.getElementById('panel-' + t.dataset.tab).hidden = !on;
    });
    const url = new URL(window.location); url.searchParams.set('tab', tab.dataset.tab);
    window.history.replaceState(null, '', url);
    document.querySelectorAll('input[name=tab]').forEach((input) => { input.value = tab.dataset.tab; });
    filter();
  }));
  if (search) search.addEventListener('input', filter);
  document.querySelectorAll('[data-autosubmit] select').forEach((select) => select.addEventListener('change', () => select.form.submit()));
  document.addEventListener('click', (event) => {
    const menu = document.querySelector('.vd-export[open]');
    if (menu && !menu.contains(event.target)) menu.removeAttribute('open');
  });
});

// "In their words": show a Read more toggle only on quotes that are actually cut off.
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-clamp]').forEach((quote) => {
    const text = quote.querySelector('.vd-quote-text');
    const button = quote.querySelector('.vd-more');
    if (!text || !button) return;
    if (text.scrollHeight - text.clientHeight > 2) button.hidden = false;
    button.addEventListener('click', () => {
      const open = quote.classList.toggle('is-open');
      button.textContent = open ? 'Show less' : 'Read more';
      button.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  });
});
