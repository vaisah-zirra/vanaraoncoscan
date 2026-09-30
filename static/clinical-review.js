document.querySelectorAll('#clinical-decision-form, #followup-update-form').forEach(form => {
  const updatePathway = () => {
    const selected = form.querySelector('input[name="action"]:checked')?.value;
    form.querySelectorAll('[data-pathway]').forEach(section => {
      const active = section.dataset.pathway.split(' ').includes(selected);
      section.hidden = !active;
      section.querySelectorAll('input, select, textarea, button').forEach(input => {
        input.disabled = !active;
      });
    });
    if (form.id === 'followup-update-form') {
      const reschedule = selected === 'RESCHEDULE';
      const notes = form.querySelector('[name="notes"]');
      form.querySelector('label[for="id_notes"]').textContent = reschedule ? 'Reason for rescheduling:' : 'Review outcome:';
      notes.placeholder = reschedule ? 'Explain why the review needs a new date and record the agreed next step.' : 'Record the review outcome and agreed care plan.';
      form.querySelector('[name="due_date"]').required = reschedule;
      form.querySelector('label[for="id_due_date"]').textContent = 'New review date:';
    }
  };
  form.querySelectorAll('input[name="action"]').forEach(input => input.addEventListener('change', updatePathway));
  updatePathway();
});
