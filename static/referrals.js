const referralForm = document.getElementById('referral-form');
if (referralForm) {
 const stage = referralForm.querySelector('select[name="status"]');
 const update = () => {
  const notes = document.getElementById('referral-notes');
  notes.hidden = !stage.value;
  notes.querySelector('textarea').disabled = !stage.value;
  const scheduled = stage.value === 'SCHEDULED';
  const appointment = document.getElementById('referral-appointment');
  appointment.hidden = !scheduled;
  appointment.querySelector('input').disabled = !scheduled;
  appointment.querySelector('input').required = scheduled;
 };
 stage.addEventListener('change', update); update();
}
