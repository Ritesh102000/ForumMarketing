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

const mode = window.FORM_MODE;
let steps = [];
let current = 0;
let bookingCompleted = false;
let responseSaving = false;
let responseSaved = false;
let responseId = '';
let draftSavePromise = null;
let autosaveTimer = null;

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

function requiredFieldsComplete() {
  return Array.from(document.querySelectorAll('.field[data-required="1"]')).every((field) => {
    const value = readField(field);
    const empty = Array.isArray(value) ? value.length === 0 : !String(value).trim();
    if (empty) return false;
    return field.dataset.type !== 'email' || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value);
  });
}

function setCalendlyField(name, value) {
  const field = document.querySelector(`[data-calendly-field="${name}"]`);
  const input = field?.querySelector('input');
  if (input) input.value = value;
}

function fieldsIn(step) {
  if (!step) return Array.from(document.querySelectorAll('.field'));
  return step.classList.contains('field') ? [step] : Array.from(step.querySelectorAll('.field'));
}

function collect() {
  const payload = {};
  document.querySelectorAll('.field').forEach((field) => {
    payload[field.dataset.question] = readField(field);
  });
  if (responseId) payload._response_id = responseId;
  return payload;
}

async function saveBeforeBooking() {
  if (responseSaving || !validate(fieldsIn(null))) return false;
  if (window.IS_PREVIEW) return false;

  responseSaving = true;
  setCalendlyField('status', 'Not booked yet');
  const status = document.getElementById('booking-status');
  if (status) status.textContent = 'Saving your business details…';
  try {
    const res = await fetch(`/f/${window.FORM_REF}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(collect()),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not save your details.');
    responseId = data.id || '';
    if (status) status.textContent = 'Details saved. Complete your booking in Calendly.';
    return Boolean(responseId);
  } catch (err) {
    if (status) status.textContent = err.message || 'Could not save your details.';
    return false;
  } finally {
    responseSaving = false;
  }
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
  if (window.HAS_BOOKING && !bookingCompleted) {
    document.getElementById('calendly-booking')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }
  if (responseSaving || responseSaved) return;
  if (!validate(fieldsIn(null))) {
    const status = document.getElementById('booking-status');
    if (status && bookingCompleted) {
      status.textContent = 'Meeting booked. Complete the required fields above so we can save your business details.';
    }
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

    responseId = data.id || responseId;
    responseSaved = true;
    document.getElementById('done-msg').textContent = data.message;
    form.hidden = true;
    progress.parentElement.hidden = true;
    if (trust) trust.hidden = true;
    done.hidden = false;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } catch (err) {
    alert(err.message || 'Could not submit. Please try again.');
  } finally {
    responseSaving = false;
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Send response';
    }
  }
});

window.addEventListener('message', async (event) => {
  if (event.origin !== 'https://calendly.com' || bookingCompleted) return;

  if (event.data?.event === 'calendly.date_and_time_selected') {
    draftSavePromise = saveBeforeBooking();
    await draftSavePromise;
    return;
  }

  if (event.data?.event !== 'calendly.event_scheduled') return;
  if (draftSavePromise) await draftSavePromise;

  bookingCompleted = true;
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
  const status = document.getElementById('booking-status');
  if (status) status.textContent = 'Meeting booked. Saving your business details…';
  form.requestSubmit();
});

form.addEventListener('input', () => {
  if (bookingCompleted && !responseSaving && !responseSaved) {
    form.requestSubmit();
    return;
  }
  window.clearTimeout(autosaveTimer);
  if (requiredFieldsComplete()) {
    autosaveTimer = window.setTimeout(() => {
      draftSavePromise = saveBeforeBooking();
    }, 700);
  }
});

document.getElementById('again')?.addEventListener('click', () => {
  if (window.HAS_BOOKING) {
    window.location.reload();
    return;
  }
  form.reset();
  document.querySelectorAll('.field').forEach((f) => setError(f, ''));
  form.hidden = false;
  done.hidden = true;
  progress.parentElement.hidden = false;
  if (trust) trust.hidden = false;
  if (steps.length) showStep(0);
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
