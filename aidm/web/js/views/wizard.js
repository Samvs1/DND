// Character wizard view: a stepper over js/wizard/steps.js. The draft lives in a module variable so
// reopening the wizard ("edit hero") starts from the previous picks. Creation goes through the
// server (create_character -> creation_result); its errors are mapped to friendly strings per step.
// The first step also imports a hero file (import_character); the finished sheet exports one.
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { context, buildChoices, newDraft, prune } from '../wizard/model.js';
import { STEPS, activeSteps, stepProblem } from '../wizard/steps.js';
import { importBlock, saveExport } from '../wizard/transfer.js';

let keptDraft = null;

async function loadData() {
  const response = await fetch('/api/creation-data');
  if (!response.ok) throw new Error('creation data unavailable');
  return response.json();
}

function stepper(steps, state, goTo) {
  const items = steps.map((step, i) => {
    const current = step.id === state.step.id;
    const reached = i <= state.maxIndex;
    const cls = ['wz-step', current ? 'current' : '', reached && !current ? 'done' : ''].join(' ').trim();
    return h(
      'li',
      { class: cls },
      h(
        'button',
        { type: 'button', 'aria-current': current ? 'step' : null, disabled: !state.canGo(i), onclick: () => goTo(step.id), 'data-testid': `step-${step.id}` },
        h('span', { class: 'wz-step-n' }, String(i + 1)),
        h('span', { class: 'wz-step-name' }, t(`steps.${step.id}`)),
      ),
    );
  });
  return h('ol', { class: 'wz-steps' }, ...items);
}

export function mountWizard(root, view) {
  const { store, client } = view;
  const draft = keptDraft ?? (keptDraft = newDraft());
  if (store.get().wizardOpen === null) store.update({ wizardOpen: true });
  const state = { data: null, stepId: 'race', result: { status: 'idle', errors: [], sheet: null }, importState: { status: 'idle', errors: [] } };
  const title = h('h2', { tabindex: '-1', id: 'wz-title' });
  const nav = h('nav', { 'aria-label': t('wz.title') });
  const body = h('div', { class: 'wz-body', 'data-testid': 'wizard-body' });
  const hint = h('p', { class: 'hint wz-hint', 'aria-live': 'polite', 'data-testid': 'wizard-hint' });
  const back = h('button', { type: 'button', class: 'btn', 'data-testid': 'wizard-back' }, t('wz.back'));
  const next = h('button', { type: 'button', class: 'btn btn-primary', 'data-testid': 'wizard-next' }, t('wz.next'));
  const close = h('button', { type: 'button', class: 'btn', 'data-testid': 'wizard-close' }, t('wz.close'));
  const footer = h('div', { class: 'wz-footer' }, back, next, close);
  const failed = h('div', { class: 'panel', hidden: true }, h('p', {}, t('wz.loadFailed')), h('button', { type: 'button', class: 'btn', onclick: () => load() }, t('wz.retry')));
  const shell = h('section', { class: 'wizard', 'data-testid': 'wizard' }, title, nav, body, hint, footer);
  root.append(h('header', { class: 'masthead small' }, h('h1', {}, t('wz.title'))), shell, failed);

  const env = () => {
    const ctx = context(draft, state.data);
    const importState = state.importState;
    return { data: state.data, draft, ctx, update, touch, send: client.send, result: state.result, create, goTo, ready, importState, importHero };
  };

  function status() {
    const e = env();
    const steps = activeSteps(draft, state.data, e.ctx);
    const index = Math.max(0, steps.findIndex((s) => s.id === state.stepId));
    const problems = steps.map((s) => stepProblem(s, draft, state.data, e.ctx));
    const firstBad = problems.findIndex((p) => p !== null);
    const maxIndex = firstBad === -1 ? steps.length - 1 : firstBad;
    return { e, steps, index, problems, maxIndex, step: steps[index], canGo: (i) => i <= maxIndex };
  }

  function renderNav() {
    const s = status();
    const problem = s.problems[s.index];
    clear(nav);
    nav.append(stepper(s.steps, s, goTo));
    title.textContent = t('wz.stepOf', { n: s.index + 1, total: s.steps.length, name: t(`steps.${s.step.id}`) });
    back.disabled = s.index === 0;
    next.hidden = s.step.id === 'review';
    next.disabled = problem !== null;
    hint.textContent = problem && s.step.id !== 'review' ? t(`wzProblem.${problem}`) : '';
  }

  function renderBody(keepFocus) {
    const s = status();
    const active = document.activeElement;
    const focusKey = keepFocus && body.contains(active) ? active.dataset.key : null;
    clear(body);
    if (s.index === 0 && store.get().phase === 'lobby') body.append(importBlock(s.e));
    body.append(s.problems[s.index] === 'needEarlier' ? h('p', { class: 'hint' }, t('wzProblem.needEarlier')) : s.step.render(s.e));
    if (focusKey) body.querySelector(`[data-key="${CSS.escape(focusKey)}"]`)?.focus();
    renderNav();
  }

  function update(fn) {
    fn(draft);
    prune(draft, state.data);
    renderBody(true);
  }

  function touch(fn) {
    fn(draft);
    prune(draft, state.data);
    renderNav();
  }

  function goTo(id) {
    state.stepId = id;
    renderBody(false);
    title.focus();
  }

  function move(delta) {
    const s = status();
    const target = s.steps[s.index + delta];
    if (target) goTo(target.id);
  }

  function create() {
    const choices = buildChoices(draft, state.data);
    if (!choices) return;
    state.result = { status: 'sending', errors: [], sheet: null };
    if (!client.send('create_character', { choices })) state.result.status = 'idle';
    renderBody(false);
  }

  function importHero(text) {
    state.importState = { status: 'sending', errors: [] };
    if (!client.send('import_character', { text })) state.importState.status = 'idle';
    renderBody(false);
  }

  function ready() {
    store.update({ wizardOpen: false });
  }

  function onResult(msg) {
    if (state.importState.status === 'sending') {
      state.importState = { status: msg.ok ? 'idle' : 'errors', errors: msg.ok ? [] : msg.errors || [] };
      if (!msg.ok) {
        if (state.data) renderBody(false);
        return;
      }
      state.stepId = 'review';
    }
    state.result = msg.ok ? { status: 'ok', errors: [], sheet: msg.sheet } : { status: 'errors', errors: msg.errors || [], sheet: null };
    if (state.data) renderBody(false);
  }

  function onRolls(msg) {
    draft.rolls = msg.rolls || [];
    draft.assign = {};
    if (state.data) renderBody(true);
  }

  back.addEventListener('click', () => move(-1));
  next.addEventListener('click', () => move(1));
  close.addEventListener('click', ready);
  const stops = [store.on('creation_result', onResult), store.on('ability_rolls', onRolls), store.on('character_export', saveExport)];

  async function load() {
    failed.hidden = true;
    try {
      state.data = await loadData();
    } catch {
      shell.hidden = true;
      failed.hidden = false;
      return;
    }
    shell.hidden = false;
    prune(draft, state.data);
    if (!STEPS.some((s) => s.id === state.stepId)) state.stepId = 'race';
    renderBody(false);
  }

  shell.hidden = true;
  load();
  return () => stops.forEach((stop) => stop());
}
