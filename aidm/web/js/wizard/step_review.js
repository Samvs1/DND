// Step 10: review the draft, create the hero (create_character), map server errors to friendly text
// per step, and show the sheet summary on success.
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { casting, finalScores, modifier, signed, ABILITIES } from './model.js';
import { titleCase } from '../ui/format.js';
import { namer } from './ui.js';
import { stepForField } from './steps_fields.js';
import { exportButton } from './transfer.js';

function row(label, value) {
  return h('div', { class: 'wz-row' }, h('dt', {}, label), h('dd', {}, value));
}

function draftSummary(env) {
  const { data, draft, ctx } = env;
  const names = namer(data);
  const finals = finalScores(draft, ctx);
  const cast = casting(draft, data, ctx);
  const rows = [
    row(t('steps.race'), ctx.sub ? `${ctx.race.name} (${ctx.sub.name})` : ctx.race.name),
    row(t('steps.class'), ctx.cls.name),
    row(t('steps.background'), ctx.bg.name),
    row(t('steps.abilities'), ABILITIES.map((a) => `${t(`abil.${a}`)} ${finals[a]} (${signed(modifier(finals[a]))})`).join(', ')),
    row(t('steps.skills'), [...draft.classSkills, ...draft.raceSkills].map(names.skill).join(', ') || t('wz.none')),
    row(t('wz.pronounsLabel'), draft.pronouns || t('wz.none')),
  ];
  if (cast) {
    const spells = [...draft.cantrips, ...draft.raceCantrips, ...draft.spells].map(names.spell).join(', ');
    rows.push(row(t('steps.spells'), spells || t('wz.none')));
  }
  return h(
    'div',
    { class: 'wz-review panel' },
    h('img', { class: 'wz-art', src: assetUrl([`portrait.${draft.portrait}`, `portrait.class.${draft.cls}`]), alt: '', width: 96, height: 96 }),
    h('h3', {}, draft.name.trim()),
    h('dl', {}, ...rows),
  );
}

function errorList(env) {
  const { result, goTo, ctx } = env;
  const grouped = new Map();
  for (const error of result.errors) {
    const step = stepForField(error.field, ctx);
    const text = t(`wzErr.${error.code}`);
    const known = text !== `wzErr.${error.code}`;
    if (!grouped.has(step)) grouped.set(step, new Set());
    grouped.get(step).add(known ? text : t('wzErr.generic'));
  }
  return h(
    'div',
    { class: 'wz-errors', role: 'alert', 'data-testid': 'creation-errors' },
    h('h3', {}, t('wz.fixThese')),
    ...[...grouped].map(([step, texts]) =>
      h(
        'div',
        { class: 'wz-error-group' },
        h('button', { type: 'button', class: 'btn btn-small', onclick: () => goTo(step) }, t(`steps.${step}`)),
        h('ul', {}, ...[...texts].map((x) => h('li', {}, x))),
      ),
    ),
  );
}

function sheetSummary(env) {
  const { result, data, ready } = env;
  const sheet = result.sheet;
  const cls = data.classes.find((c) => c.index === sheet.class_index);
  const identity = t('wz.identity', {
    level: sheet.level,
    race: titleCase(sheet.subrace ?? sheet.race),
    class: cls ? cls.name : sheet.class_index,
  });
  const abilities = sheet.abilities.map((a) => `${t(`abil.${a.ability}`)} ${a.score} (${signed(a.modifier)})`).join('  ');
  const attacks = sheet.attacks.map((a) => `${a.name} ${signed(a.attack_bonus)}, ${a.damage}`);
  const spells = sheet.spellcasting
    ? [...sheet.spellcasting.cantrips, ...sheet.spellcasting.levels.flatMap((l) => l.spells)].map((s) => s.name).join(', ')
    : '';
  return h(
    'div',
    { class: 'wz-sheet panel', 'data-testid': 'sheet-summary' },
    h('h3', { 'data-testid': 'sheet-name' }, sheet.name),
    h('p', {}, identity),
    h('p', { class: 'wz-vitals' }, t('wz.vitals', { hp: sheet.max_hp, ac: sheet.ac, speed: sheet.speed })),
    h('p', {}, abilities),
    attacks.length ? h('p', {}, t('wz.attacks', { list: attacks.join('; ') })) : null,
    spells ? h('p', {}, t('wz.spellsOnSheet', { list: spells })) : null,
    h('p', { class: 'hint' }, t('wz.features', { list: sheet.features.map((f) => f.name).join(', ') })),
    h('div', { class: 'wz-actions' }, h('button', { type: 'button', class: 'btn btn-primary', 'data-testid': 'hero-ready', onclick: ready }, t('wz.ready')), exportButton(env)),
  );
}

export function renderReview(env) {
  const { result, create } = env;
  if (result.status === 'ok') return sheetSummary(env);
  const sending = result.status === 'sending';
  return h(
    'div',
    {},
    draftSummary(env),
    result.status === 'errors' ? errorList(env) : null,
    h('button', { type: 'button', class: 'btn btn-primary', 'data-testid': 'create-hero', disabled: sending, onclick: create }, sending ? t('wz.creating') : t('wz.create')),
  );
}
