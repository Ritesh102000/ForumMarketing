/* Public form renderer: handles the three display modes, validation and submit. */

const form = document.getElementById('form');
const intro = document.getElementById('intro');
const progress = document.getElementById('progress');
const backBtn = document.getElementById('back');
const nextBtn = document.getElementById('next');
const submitBtn = document.getElementById('submit');
const done = document.getElementById('done');
const trust = document.getElementById('trust');
const hint = document.getElementById('hint');
const bookingBlock = document.getElementById('calendly-booking');
const againBtn = document.getElementById('again');

const mode = window.FORM_MODE;
let steps = [];
let current = 0;
let responseSaving = false;
let responseSaved = false;
let responseId = '';

function buildSteps() {
  if (mode === 'single') return [];
  if (mode === 'section') return Array.from(document.querySelectorAll('[data-step]'));
  // one_by_one: every question is its own step
  return Array.from(document.querySelectorAll('.field[data-hidden="0"]'));
}

function showStep(index) {
  if (!steps.length) return;
  current = Math.max(0, Math.min(index, steps.length - 1));

  steps.forEach((step, i) => {
    const active = i === current;
    step.hidden = !active;
    if (active) step.classList.add('enter');
  });

  if (mode === 'one_by_one') {
    // Each question is its own step, so show only the section that holds it.
    document.querySelectorAll('[data-step]').forEach((section) => {
      section.hidden = !section.contains(steps[current]);
    });
  }

  if (intro) intro.hidden = current > 0;
  // The trust strip is a first-impression element, not a distraction mid-flow.
  if (trust) trust.hidden = current > 0;
  backBtn.hidden = current === 0;
  nextBtn.hidden = current >= steps.length - 1;
  if (submitBtn) submitBtn.hidden = current < steps.length - 1;
  if (hint) hint.hidden = nextBtn.hidden;

  progress.style.width = `${((current + 1) / steps.length) * 100}%`;
  window.scrollTo({ top: 0, behavior: 'smooth' });

  // preventScroll matters: without it the browser scrolls the field into view
  // and undoes the scroll-to-top above.
  const firstInput = steps[current].querySelector('input, select, textarea');
  if (firstInput) setTimeout(() => firstInput.focus({ preventScroll: true }), 60);
}

function readField(field) {
  const id = field.dataset.question;
  const type = field.dataset.type;
  if (type === 'checkbox') {
    return Array.from(field.querySelectorAll('input:checked')).map((el) => el.value);
  }
  if (type === 'radio' || type === 'scale' || type === 'rating') {
    const picked = field.querySelector('input:checked');
    return picked ? picked.value : '';
  }
  const el = field.querySelector('input, select, textarea');
  return el ? el.value : '';
}

function setError(field, message) {
  const slot = field.querySelector('.field-error');
  slot.textContent = message || '';
  slot.hidden = !message;
  field.classList.toggle('has-error', Boolean(message));
}

function validate(fields) {
  let ok = true;
  fields.forEach((field) => {
    const value = readField(field);
    const required = field.dataset.required === '1';
    const empty = Array.isArray(value) ? value.length === 0 : !String(value).trim();

    if (required && empty) {
      setError(field, 'This question is required.');
      ok = false;
      return;
    }
    if (field.dataset.type === 'email' && !empty && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value)) {
      setError(field, 'Enter a valid email address.');
      ok = false;
      return;
    }
    setError(field, '');
  });
  if (!ok) {
    const first = fields.find((f) => f.classList.contains('has-error'));
    if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  return ok;
}

function fieldsIn(step) {
  if (!step) return Array.from(document.querySelectorAll('.field[data-hidden="0"]'));
  return step.classList.contains('field') ? [step] : Array.from(step.querySelectorAll('.field'));
}

function collect() {
  const payload = {};
  document.querySelectorAll('.field').forEach((field) => {
    payload[field.dataset.question] = readField(field);
  });
  return payload;
}

nextBtn?.addEventListener('click', () => {
  if (validate(fieldsIn(steps[current]))) showStep(current + 1);
});

backBtn?.addEventListener('click', () => showStep(current - 1));

form.addEventListener('keydown', (event) => {
  if (event.key !== 'Enter') return;
  const tag = event.target.tagName;
  if (tag === 'TEXTAREA') return;
  if (!nextBtn.hidden) {
    event.preventDefault();
    nextBtn.click();
  }
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (responseSaving || responseSaved) return;
  if (!validate(fieldsIn(null))) {
    return;
  }

  if (window.IS_PREVIEW) {
    alert('This form is a draft. Publish it before collecting responses.');
    return;
  }

  responseSaving = true;
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting…';
  }

  try {
    const res = await fetch(`/f/${window.FORM_REF}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(collect()),
    });
    const data = await res.json();

    if (res.status === 422 && data.errors) {
      Object.entries(data.errors).forEach(([qid, message]) => {
        const field = document.querySelector(`[data-question="${qid}"]`);
        if (field) setError(field, message);
      });
      const first = document.querySelector('.has-error');
      if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    if (!res.ok) throw new Error(data.detail || 'Something went wrong.');

    responseSaved = true;
    responseId = data.id || '';
    document.getElementById('done-msg').textContent = data.message;
    form.hidden = true;
    progress.parentElement.hidden = true;
    if (trust) trust.hidden = true;
    done.hidden = false;
    if (bookingBlock) bookingBlock.hidden = false;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } catch (err) {
    alert(err.message || 'Could not submit. Please try again.');
  } finally {
    responseSaving = false;
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Submit form';
    }
  }
});

window.addEventListener('message', async (event) => {
  if (
    event.origin !== 'https://calendly.com'
    || event.data?.event !== 'calendly.event_scheduled'
  ) return;

  const payload = event.data?.payload || {};
  const bookingFields = {
    status: 'Booked',
    event_uri: payload.event?.uri || '',
    invitee_uri: payload.invitee?.uri || '',
    completed_at: new Date().toISOString(),
  };
  document.querySelectorAll('[data-calendly-field]').forEach((field) => {
    const input = field.querySelector('input');
    if (input) input.value = bookingFields[field.dataset.calendlyField] || '';
  });
  if (againBtn) againBtn.hidden = false;
  const status = document.getElementById('booking-status');
  if (status) status.textContent = 'Meeting booked. Linking it to your submitted response…';
  if (!responseId) return;

  try {
    const res = await fetch(`/f/${window.FORM_REF}/responses/${responseId}/booking`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bookingFields),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not link booking details.');
    if (status) {
      status.textContent = data.sheet_connected && !data.sheet_synced
        ? 'Meeting booked. Your details are saved and Google Sheet synchronization is pending.'
        : 'Meeting booked. The booking details were added to your submitted response.';
    }
  } catch (err) {
    if (status) status.textContent = 'Meeting booked. Your form response is safe, but the booking details could not be linked yet.';
  }
});

againBtn?.addEventListener('click', () => {
  window.location.reload();
});

// Star ratings fill up to the hovered/selected value.
document.querySelectorAll('.rating').forEach((group) => {
  const stars = Array.from(group.querySelectorAll('.star'));
  const paint = (upto) => stars.forEach((s, i) => s.classList.toggle('on', i <= upto));
  stars.forEach((star, index) => {
    star.addEventListener('mouseenter', () => paint(index));
    star.addEventListener('click', () => paint(index));
  });
  group.addEventListener('mouseleave', () => {
    const picked = stars.findIndex((s) => s.querySelector('input').checked);
    paint(picked);
  });
});

steps = buildSteps();
if (steps.length) {
  showStep(0);
} else {
  progress.parentElement.hidden = true;
  backBtn.hidden = true;
  nextBtn.hidden = true;
  if (hint) hint.hidden = true;
}
