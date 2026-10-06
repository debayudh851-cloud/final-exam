'use strict';
document.querySelectorAll('.sidebar nav a').forEach(link => {
  if (link.pathname === location.pathname) link.classList.add('active');
});
const candidateForm = document.querySelector('[data-email-check]');
if (candidateForm) {
  const input = candidateForm.querySelector('[name=email]');
  const message = document.getElementById('email-message');
  let timer, controller;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    controller?.abort();
    timer = setTimeout(async () => {
      if (!input.value) { message.textContent = ''; return; }
      controller = new AbortController();
      try {
        const body = new URLSearchParams({email: input.value, exclude: candidateForm.dataset.exclude});
        const response = await fetch(candidateForm.dataset.emailCheck, {method: 'POST', body,
          headers: {'X-CSRFToken': candidateForm.querySelector('[name=csrfmiddlewaretoken]').value}, signal: controller.signal});
        const data = await response.json();
        message.textContent = data.error || (data.exists ? 'This email already has an application.' : 'Email is available.');
        message.className = data.exists || data.error ? 'error-text' : 'muted';
      } catch (error) {
        if (error.name !== 'AbortError') message.textContent = 'Email check unavailable. The form will validate it when saved.';
      }
    }, 350);
  });
}
const roleSelect = document.querySelector('[data-slots-url]');
if (roleSelect) {
  const loadSlots = async () => {
    const message = document.getElementById('slots-message');
    const slotSelect = document.getElementById('id_slot');
    try {
      const response = await fetch(`${roleSelect.dataset.slotsUrl}?role=${encodeURIComponent(roleSelect.value)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Could not load interview slots.');
      slotSelect.replaceChildren(new Option('Choose a slot', ''));
      data.slots.forEach(slot => slotSelect.add(new Option(slot.label, slot.id)));
      message.textContent = data.slots.length ? '' : 'No available slots for this role.';
    } catch (error) { message.textContent = error.message; }
  };
  roleSelect.addEventListener('change', loadSlots);
  loadSlots();
}
const batch = document.getElementById('batch-progress');
if (batch && ['QUEUED', 'PROCESSING'].includes(batch.dataset.state)) {
  const poll = async () => {
    try {
      const response = await fetch(batch.dataset.statusUrl);
      if (!response.ok) throw new Error('Could not refresh batch status.');
      const data = await response.json();
      document.getElementById('batch-state').textContent = data.status;
      document.getElementById('progress').max = data.total_rows || 1;
      document.getElementById('progress').value = data.processed_rows;
      document.getElementById('progress-label').textContent = `${data.processed_rows} / ${data.total_rows} rows processed`;
      document.getElementById('accepted-count').textContent = data.accepted_count;
      document.getElementById('rejected-count').textContent = data.rejected_count;
      document.getElementById('batch-error').textContent = data.error;
      if (['COMPLETED', 'FAILED'].includes(data.status)) { location.reload(); return; }
    } catch (error) { document.getElementById('batch-error').textContent = error.message; }
    setTimeout(poll, 2500);
  };
  setTimeout(poll, 1500);
}
