/* Searchable selects retain native submission and a no-JavaScript fallback. */
document.querySelectorAll('select').forEach((select, index) => {
  const wrapper = document.createElement('div');
  wrapper.className = 'search-select';
  const input = document.createElement('input');
  const list = document.createElement('ul');
  const empty = document.createElement('div');
  const originalId = select.id || `select-${index}`;
  const required = select.required;
  select.id = `${originalId}-native`;
  input.id = originalId;
  input.type = 'text';
  input.autocomplete = 'off';
  input.setAttribute('role', 'combobox');
  input.setAttribute('aria-autocomplete', 'list');
  input.setAttribute('aria-expanded', 'false');
  list.id = `${originalId}-options`;
  list.setAttribute('role', 'listbox');
  list.hidden = true;
  input.setAttribute('aria-controls', list.id);
  input.setAttribute('aria-required', String(required));
  empty.className = 'select-empty';
  empty.setAttribute('role', 'status');
  empty.textContent = 'No matches found. Try a different name or reference.';
  empty.hidden = true;
  select.before(wrapper);
  wrapper.append(input, list, empty, select);
  select.hidden = true;
  select.required = false;
  const options = Array.from(select.options).map(o => ({value:o.value, label:o.textContent}));
  let active = -1;
  let matches = [];
  let opened = false;
  const selectedLabel = () => options.find(o => o.value === select.value)?.label || '';
  const sync = () => {
    input.value = required && !select.value ? '' : selectedLabel();
    input.placeholder = options[0]?.label || 'Type to search';
    input.setCustomValidity(required && !select.value ? 'Select an option from the list.' : '');
  };
  function close() {
    opened = false; list.hidden = true; empty.hidden = true;
    input.setAttribute('aria-expanded','false'); input.removeAttribute('aria-activedescendant');
  }
  function highlight() {
    Array.from(list.children).forEach((li, i) => {
      li.classList.toggle('active', i === active);
      li.setAttribute('aria-selected', String(i === active));
    });
    if (active >= 0) {
      input.setAttribute('aria-activedescendant', list.children[active].id);
      list.children[active].scrollIntoView({block:'nearest'});
    } else input.removeAttribute('aria-activedescendant');
  }
  function choose(option) {
    select.value = option.value;
    sync(); close();
    select.dispatchEvent(new Event('change', {bubbles:true}));
  }
  function render(query = '') {
    matches = options.filter(o => (!required || o.value) && o.label.toLowerCase().includes(query.toLowerCase()));
    list.replaceChildren(); active = -1;
    matches.forEach((option, i) => {
      const li = document.createElement('li');
      li.id = `${list.id}-${i}`;
      li.setAttribute('role','option'); li.setAttribute('aria-selected','false');
      li.textContent = option.label;
      li.addEventListener('mousedown', e => e.preventDefault());
      li.addEventListener('click', () => choose(option));
      list.append(li);
    });
    opened = true; list.hidden = !matches.length; empty.hidden = Boolean(matches.length);
    input.setAttribute('aria-expanded','true');
    input.removeAttribute('aria-activedescendant');
  }
  input.addEventListener('focus', () => {render(); input.select();});
  input.addEventListener('click', () => {if (!opened) {render(); input.select();}});
  input.addEventListener('input', () => {
    // Never submit a stale patient ID after the visible query has changed.
    if (required) select.value = '';
    input.setCustomValidity(required ? 'Choose a matching option from the list.' : 'Choose an option from the list.');
    render(input.value);
  });
  input.addEventListener('keydown', event => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault(); if (!opened) render();
      if (matches.length) {active = (active + (event.key === 'ArrowDown' ? 1 : -1) + matches.length) % matches.length; highlight();}
    } else if (event.key === 'Enter' && opened) {
      event.preventDefault(); if (active >= 0) choose(matches[active]); else if (matches.length === 1) choose(matches[0]);
    } else if (event.key === 'Escape') {close(); sync();}
    else if (event.key === 'Tab') {close(); sync();}
  });
  input.addEventListener('blur', () => {close(); sync();});
  sync();
});

const contextData = document.getElementById('patient-contexts');
if (contextData) {
  const contexts = JSON.parse(contextData.textContent);
  const patient = document.querySelector('select[name="patient"]');
  const concern = document.getElementById('concern');
  patient.addEventListener('change', () => {
    concern.value = contexts[patient.value] || '';
    document.getElementById('context-status').textContent = concern.value
      ? 'Presenting history loaded. Review and amend before continuing.'
      : 'No presenting history is recorded for this patient. Add the relevant context below.';
  });
}
