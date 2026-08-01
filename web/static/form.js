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

function buildSteps() {
  if (mode === 'single') return [];
  if (mode === 'section') return Array.from(document.querySelectorAll('[data-step]'));
  // one_by_one: every question is its own step
  return Array.from(document.querySelectorAll('.field'));
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
  submitBtn.hidden = current < steps.length - 1;
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
  if (!step) return Array.from(document.querySelectorAll('.field'));
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
  if (!validate(fieldsIn(null))) return;

  if (window.IS_PREVIEW) {
    alert('This form is a draft. Publish it before collecting responses.');
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = 'Submitting…';

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

    document.getElementById('done-msg').textContent = data.message;
    form.hidden = true;
    progress.parentElement.hidden = true;
    if (trust) trust.hidden = true;
    done.hidden = false;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } catch (err) {
    alert(err.message || 'Could not submit. Please try again.');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Send response';
  }
});

document.getElementById('again')?.addEventListener('click', () => {
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
