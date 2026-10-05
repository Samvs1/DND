// Level-up dialog: builds valid `level_up` choices from the server's options (subclass, ability score
// improvement, class and feature picks, new cantrips and spells, an optional spell swap). The submit button
// enables only when every pick count is right; a refusal from the server shows friendly text here.
import { myHero } from '../table/lookup.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { titleCase } from '../ui/format.js';

const ABILITIES = ['str', 'dex', 'con', 'int', 'wis', 'cha'];

function openDialog(dialog) {
  if (dialog.open) return;
  if (typeof dialog.showModal === 'function') dialog.showModal();
  else dialog.setAttribute('open', '');
}

function closeDialog(dialog) {
  if (!dialog.open) return;
  if (typeof dialog.close === 'function') dialog.close();
  else dialog.removeAttribute('open');
}

function newForm() {
  return { mode: 'one', asi: [], groups: {}, replace: '', replacement: '' };
}

function pickGroup(form, key, group, onChange) {
  const picked = (form.groups[key] ??= []);
  const counter = h('span', { class: 'hint lu-count', 'data-testid': `lu-count-${key}` });
  const refresh = () => (counter.textContent = t('levelup.pickN', { n: group.choose, have: picked.length }));
  refresh();
  const boxes = group.options.map((o) => {
    const box = h('input', { type: 'checkbox', value: o.id, 'data-testid': `lu-${key}-${o.id}` });
    box.addEventListener('change', () => {
      const at = picked.indexOf(o.id);
      if (box.checked && at < 0) picked.push(o.id);
      if (!box.checked && at >= 0) picked.splice(at, 1);
      refresh();
      onChange();
    });
    return h('label', { class: 'lu-opt' }, box, ' ', o.level ? `${o.name} (${t('levelup.levelOf', { n: o.level })})` : o.name);
  });
  return h('fieldset', { class: 'lu-group', 'data-testid': `lu-group-${key}` }, h('legend', {}, group.name), counter, h('div', { class: 'lu-opts' }, ...boxes));
}

function asiBlock(form, onChange) {
  const need = () => (form.mode === 'one' ? 1 : 2);
  const hint = h('span', { class: 'hint' });
  const refresh = () => (hint.textContent = t('levelup.asiPick', { n: need() }));
  refresh();
  const radio = (mode, label) => {
    const input = h('input', { type: 'radio', name: 'asi-mode', value: mode, checked: form.mode === mode, 'data-testid': `lu-asi-${mode}` });
    input.addEventListener('change', () => {
      form.mode = mode;
      form.asi = [];
      boxes.forEach((b) => (b.checked = false));
      refresh();
      onChange();
    });
    return h('label', { class: 'lu-opt' }, input, ' ', label);
  };
  const boxes = ABILITIES.map((a) => {
    const box = h('input', { type: 'checkbox', value: a, 'data-testid': `lu-asi-${a}` });
    box.addEventListener('change', () => {
      form.asi = form.asi.filter((x) => x !== a);
      if (box.checked) form.asi.push(a);
      if (form.asi.length > need()) {
        const drop = form.asi.shift();
        boxes.find((b) => b.value === drop).checked = false;
      }
      onChange();
    });
    return box;
  });
  return h('fieldset', { class: 'lu-group', 'data-testid': 'lu-asi' }, h('legend', {}, t('levelup.asi')), radio('one', t('levelup.asiOne')), radio('two', t('levelup.asiTwo')), hint, h('div', { class: 'lu-opts' }, ...ABILITIES.map((a, i) => h('label', { class: 'lu-opt' }, boxes[i], ' ', t(`abil.${a}`)))));
}

function swapBlock(form, options, onChange) {
  const select = (label, items, key) => {
    const el = h('select', { 'data-testid': `lu-${key}`, 'aria-label': label }, h('option', { value: '' }, key === 'replace' ? t('levelup.swapNone') : label), ...items.map((o) => h('option', { value: o.id }, o.name)));
    el.addEventListener('change', () => {
      form[key] = el.value;
      onChange();
    });
    return el;
  };
  const pool = (options.spells?.options ?? []).filter((o) => !options.replace_from.some((r) => r.id === o.id));
  return h('fieldset', { class: 'lu-group', 'data-testid': 'lu-swap' }, h('legend', {}, t('levelup.swap')), select(t('levelup.swapNone'), options.replace_from, 'replace'), ' ', t('levelup.swapFor'), ' ', select(t('levelup.swapFor'), pool, 'replacement'));
}

export function validForm(form, options) {
  const groups = [...options.class_choices.map((g) => [`cc-${g.id}`, g]), ...options.feature_choices.map((g) => [`fc-${g.id}`, g]), ...(options.cantrips ? [['cantrips', options.cantrips]] : []), ...(options.spells ? [['spells', options.spells]] : [])];
  if (groups.some(([key, g]) => (form.groups[key] ?? []).length !== g.choose)) return false;
  if (options.asi && form.asi.length !== (form.mode === 'one' ? 1 : 2)) return false;
  return Boolean(form.replace) === Boolean(form.replacement);
}

export function buildChoices(form, options) {
  const pick = (prefix, list) => Object.fromEntries(list.map((g) => [g.id, form.groups[`${prefix}-${g.id}`] ?? []]));
  const asi = options.asi ? Object.fromEntries(form.asi.map((a) => [a, form.mode === 'one' ? 2 : 1])) : {};
  return {
    subclass: options.subclass?.id ?? null,
    class_choices: pick('cc', options.class_choices),
    feature_choices: pick('fc', options.feature_choices),
    asi,
    cantrips: form.groups.cantrips ?? [],
    spells: form.groups.spells ?? [],
    replace_spell: form.replace || null,
    replacement: form.replacement || null,
  };
}

function buildBody(body, options, form, onChange) {
  clear(body);
  if (options.subclass) body.append(h('p', { class: 'lu-sub', 'data-testid': 'lu-subclass' }, h('strong', {}, t('levelup.subclass')), ': ', t('levelup.subclassPick', { name: titleCase(options.subclass.id) })));
  if (options.asi) body.append(asiBlock(form, onChange));
  for (const g of options.class_choices) body.append(pickGroup(form, `cc-${g.id}`, g, onChange));
  for (const g of options.feature_choices) body.append(pickGroup(form, `fc-${g.id}`, g, onChange));
  if (options.cantrips) body.append(pickGroup(form, 'cantrips', options.cantrips, onChange));
  if (options.spells) body.append(pickGroup(form, 'spells', options.spells, onChange));
  if (options.replace_from.length) body.append(swapBlock(form, options, onChange));
}

/** The badge button (shown while the hero can level up) and the level-up dialog. */
export function mountLevelUp(root, { store, client }) {
  const title = h('h2', { id: 'levelup-h' }, t('table.levelUpTitle'));
  const body = h('div', { class: 'lu-body' });
  const error = h('p', { class: 'form-error', role: 'alert', 'data-testid': 'lu-error' });
  const submit = h('button', { type: 'button', class: 'btn btn-primary', disabled: true, 'data-testid': 'lu-submit' }, t('levelup.submit'));
  const cancel = h('button', { type: 'button', class: 'btn', onclick: () => store.update({ levelUpOpen: false }) }, t('levelup.cancel'));
  const dialog = h('dialog', { class: 'dialog lu-dialog', 'aria-labelledby': 'levelup-h', 'data-testid': 'levelup-dialog' }, title, body, error, h('div', { class: 'dialog-actions' }, submit, cancel));
  const button = h('button', { type: 'button', class: 'btn btn-small levelup-btn', hidden: true, 'data-testid': 'levelup-button', onclick: () => store.update({ levelUpOpen: true }) }, t('table.levelUp'));
  root.append(button, dialog);
  let form = newForm();
  let built = null;
  let submitted = false;

  const options = () => store.get().sheet?.level_up ?? null;
  const sync = () => (submit.disabled = !(options() && validForm(form, options())));
  dialog.addEventListener('close', () => store.update({ levelUpOpen: false }));
  submit.addEventListener('click', () => {
    const o = options();
    if (!o || !validForm(form, o)) return;
    submitted = true;
    error.textContent = '';
    client.send('level_up', { choices: buildChoices(form, o) });
  });

  function show(state) {
    const o = options();
    if (!o) {
      built = null;
      clear(body);
      body.append(h('p', { class: 'dialog-text' }, t('levelup.wait')));
      submit.disabled = true;
      return;
    }
    title.textContent = t('levelup.title', { level: o.level });
    if (built !== o.level) {
      built = o.level;
      form = newForm();
      buildBody(body, o, form, sync);
    }
    sync();
  }

  function render(state) {
    const hero = myHero(state);
    const offered = hero ? state.levelUps[hero.id] : 0;
    button.hidden = !(hero && ((offered && (hero.level ?? 1) < offered) || options()));
    if (submitted && state.errorCode) {
      submitted = false;
      error.textContent = t('levelup.invalid');
      store.update({ errorCode: null });
      return;
    }
    if (submitted && !options()) {
      submitted = false;
      store.update({ levelUpOpen: false });
    }
    if (state.levelUpOpen) {
      if (!dialog.open) client.send('request_sheet');
      show(state);
      openDialog(dialog);
    } else closeDialog(dialog);
  }
  render(store.get());
  return store.subscribe(render);
}
