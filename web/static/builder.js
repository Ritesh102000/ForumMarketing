/* Form builder: holds the form in memory, renders it, and saves as JSON. */

const OPTION_TYPES = window.OPTION_TYPES;
const SCALE_TYPES = window.SCALE_TYPES;

const els = {
  title: document.getElementById('f-title'),
  description: document.getElementById('f-description'),
  accent: document.getElementById('f-accent'),
  confirm: document.getElementById('f-confirm'),
  published: document.getElementById('f-published'),
  sections: document.getElementById('sections'),
  addSection: document.getElementById('add-section'),
  save: document.getElementById('save-form'),
  del: document.getElementById('delete-form'),
  state: document.getElementById('save-state'),
  headTitle: document.getElementById('head-title'),
};

let state = window.FORM_DATA
  ? {
      title: window.FORM_DATA.title,
      description: window.FORM_DATA.description,
      display_mode: window.FORM_DATA.display_mode,
      accent: window.FORM_DATA.accent,
      is_published: window.FORM_DATA.is_published,
      confirm_msg: window.FORM_DATA.confirm_msg,
      sections: window.FORM_DATA.sections.map((s) => ({
        id: s.id,
        title: s.title,
        description: s.description,
        questions: s.questions.map((q) => ({
          id: q.id,
          type: q.type,
          label: q.label,
          help_text: q.help_text,
          placeholder: q.placeholder,
          required: q.required,
          options: q.options,
          config: q.config,
        })),
      })),
    }
  : {
      title: '',
      description: '',
      display_mode: 'single',
      accent: '#4f46e5',
      is_published: false,
      confirm_msg: 'Thanks — your response has been recorded.',
      sections: [{ title: '', description: '', questions: [blankQuestion()] }],
    };

function blankQuestion() {
  return {
    type: 'short_text',
    label: '',
    help_text: '',
    placeholder: '',
    required: false,
    options: [],
    config: {},
  };
}

function markDirty() {
  els.state.textContent = 'Unsaved changes';
  els.state.classList.add('is-dirty');
}

function move(list, index, delta) {
  const target = index + delta;
  if (target < 0 || target >= list.length) return;
  [list[index], list[target]] = [list[target], list[index]];
}

/* ------------------------------------------------------------------ render */

function renderOptions(wrap, question) {
  const list = wrap.querySelector('.opt-list');
  list.innerHTML = '';
  question.options.forEach((value, index) => {
    const row = document.createElement('div');
    row.className = 'opt-row';
    const input = document.createElement('input');
    input.type = 'text';
    input.value = value;
    input.placeholder = `Option ${index + 1}`;
    input.addEventListener('input', () => {
      question.options[index] = input.value;
      markDirty();
    });
    const remove = document.createElement('button');
    remove.className = 'icon-btn danger';
    remove.textContent = '✕';
    remove.addEventListener('click', () => {
      question.options.splice(index, 1);
      renderOptions(wrap, question);
      markDirty();
    });
    row.append(input, remove);
    list.append(row);
  });
}

function renderQuestion(question, sectionIndex, questionIndex) {
  const node = document.getElementById('tpl-question').content.firstElementChild.cloneNode(true);
  const label = node.querySelector('.q-label');
  const type = node.querySelector('.q-type');
  const help = node.querySelector('.q-help');
  const required = node.querySelector('.q-required');
  const optionsWrap = node.querySelector('.q-options');
  const scaleWrap = node.querySelector('.q-scale');
  const min = node.querySelector('.q-min');
  const max = node.querySelector('.q-max');

  label.value = question.label;
  type.value = question.type;
  help.value = question.help_text;
  required.checked = question.required;
  min.value = question.config.min ?? 1;
  max.value = question.config.max ?? 5;

  const syncVisibility = () => {
    optionsWrap.classList.toggle('hidden', !OPTION_TYPES.includes(question.type));
    scaleWrap.classList.toggle('hidden', !SCALE_TYPES.includes(question.type));
  };

  label.addEventListener('input', () => { question.label = label.value; markDirty(); });
  help.addEventListener('input', () => { question.help_text = help.value; markDirty(); });
  required.addEventListener('change', () => { question.required = required.checked; markDirty(); });

  type.addEventListener('change', () => {
    question.type = type.value;
    if (OPTION_TYPES.includes(question.type) && question.options.length === 0) {
      question.options = ['Option 1'];
      renderOptions(optionsWrap, question);
    }
    if (SCALE_TYPES.includes(question.type)) {
      question.config.min = Number(min.value);
      question.config.max = Number(max.value);
    } else {
      question.config = {};
    }
    syncVisibility();
    markDirty();
  });

  min.addEventListener('input', () => { question.config.min = Number(min.value); markDirty(); });
  max.addEventListener('input', () => { question.config.max = Number(max.value); markDirty(); });

  node.querySelector('[data-act="add-opt"]').addEventListener('click', () => {
    question.options.push(`Option ${question.options.length + 1}`);
    renderOptions(optionsWrap, question);
    markDirty();
  });

  node.querySelectorAll('.q-main [data-act]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const list = state.sections[sectionIndex].questions;
      const act = btn.dataset.act;
      if (act === 'del') list.splice(questionIndex, 1);
      if (act === 'up') move(list, questionIndex, -1);
      if (act === 'down') move(list, questionIndex, 1);
      render();
      markDirty();
    });
  });

  renderOptions(optionsWrap, question);
  syncVisibility();
  return node;
}

function renderSection(section, index) {
  const node = document.getElementById('tpl-section').content.firstElementChild.cloneNode(true);
  const title = node.querySelector('.s-title');
  const desc = node.querySelector('.s-desc');
  const questions = node.querySelector('.questions');

  title.value = section.title;
  desc.value = section.description;
  title.addEventListener('input', () => { section.title = title.value; markDirty(); });
  desc.addEventListener('input', () => { section.description = desc.value; markDirty(); });

  section.questions.forEach((question, qi) => {
    questions.append(renderQuestion(question, index, qi));
  });

  node.querySelector('[data-act="add-q"]').addEventListener('click', () => {
    section.questions.push(blankQuestion());
    render();
    markDirty();
  });

  node.querySelectorAll('.section-head [data-act]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const act = btn.dataset.act;
      if (act === 'del') {
        if (state.sections.length === 1) return alert('A form needs at least one section.');
        state.sections.splice(index, 1);
      }
      if (act === 'up') move(state.sections, index, -1);
      if (act === 'down') move(state.sections, index, 1);
      render();
      markDirty();
    });
  });

  return node;
}

function render() {
  els.sections.innerHTML = '';
  state.sections.forEach((section, index) => {
    els.sections.append(renderSection(section, index));
  });
}

/* ------------------------------------------------------------------- wire */

els.title.value = state.title;
els.description.value = state.description;
els.accent.value = state.accent;
els.confirm.value = state.confirm_msg;
els.published.checked = state.is_published;
document.querySelector(`input[name="mode"][value="${state.display_mode}"]`).checked = true;

els.title.addEventListener('input', () => {
  state.title = els.title.value;
  els.headTitle.textContent = state.title || 'New form';
  markDirty();
});
els.description.addEventListener('input', () => { state.description = els.description.value; markDirty(); });
els.accent.addEventListener('input', () => {
  state.accent = els.accent.value;
  document.documentElement.style.setProperty('--accent', state.accent);
  markDirty();
});
els.confirm.addEventListener('input', () => { state.confirm_msg = els.confirm.value; markDirty(); });
els.published.addEventListener('change', () => { state.is_published = els.published.checked; markDirty(); });
document.querySelectorAll('input[name="mode"]').forEach((radio) => {
  radio.addEventListener('change', () => { state.display_mode = radio.value; markDirty(); });
});

els.addSection.addEventListener('click', () => {
  state.sections.push({ title: '', description: '', questions: [blankQuestion()] });
  render();
  markDirty();
});

els.save.addEventListener('click', async () => {
  if (!state.title.trim()) return alert('Give the form a title first.');
  const empty = state.sections.flatMap((s) => s.questions).find((q) => !q.label.trim());
  if (empty) return alert('Every question needs a label.');

  els.save.disabled = true;
  els.state.textContent = 'Saving…';

  const isNew = !window.FORM_ID;
  const res = await fetch(isNew ? '/api/forms' : `/api/forms/${window.FORM_ID}`, {
    method: isNew ? 'POST' : 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(state),
  });

  if (!res.ok) {
    els.save.disabled = false;
    const detail = await res.json().catch(() => ({}));
    els.state.textContent = 'Save failed';
    alert(typeof detail.detail === 'string' ? detail.detail : 'Could not save. Check the console.');
    console.error(detail);
    return;
  }

  const data = await res.json();
  if (isNew) {
    window.location.href = `/admin/${data.id}`;
    return;
  }
  els.save.disabled = false;
  if (data.sheet?.updated) {
    els.state.textContent = 'Saved · Sheet updated';
  } else if (data.sheet && data.sheet.detail !== 'No spreadsheet is linked.' && data.sheet.detail !== 'Google sync is off.') {
    els.state.textContent = 'Saved · Sheet pending';
    console.warn('Google Sheet update:', data.sheet.detail);
  } else {
    els.state.textContent = 'Saved';
  }
  els.state.classList.remove('is-dirty');
});

els.del?.addEventListener('click', async () => {
  if (!confirm('Delete this form and all of its responses? The Google Sheet is not deleted.')) return;
  await fetch(`/api/forms/${window.FORM_ID}`, { method: 'DELETE' });
  window.location.href = '/';
});

document.documentElement.style.setProperty('--accent', state.accent);
render();
