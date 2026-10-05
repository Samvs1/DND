// Step 4: ability scores: point buy (27, live cost), standard array, or 4d6-drop-lowest rolled by the server.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import {
  ABILITIES,
  POINT_BUDGET,
  POINT_COSTS,
  POINT_MAX,
  POINT_MIN,
  STANDARD_ARRAY,
  assignableValues,
  bonuses,
  finalScores,
  modifier,
  pointCost,
  signed,
} from './model.js';

const METHODS = ['point_buy', 'standard_array', 'roll_4d6'];

function setMethod(env, method) {
  env.update((d) => {
    d.method = method;
    d.assign = {};
  });
}

function stepper(env, ability) {
  const { draft, update } = env;
  const score = draft.points[ability];
  const left = POINT_BUDGET - pointCost(draft.points);
  const nextCost = (POINT_COSTS[score + 1] ?? 99) - POINT_COSTS[score];
  const move = (delta) => update((d) => (d.points[ability] += delta));
  const name = t(`abil.${ability}`);
  return h(
    'div',
    { class: 'wz-stepper' },
    h('button', { type: 'button', class: 'btn btn-small', 'data-key': `minus-${ability}`, 'aria-label': t('wz.lower', { name }), disabled: score <= POINT_MIN, onclick: () => move(-1) }, '-'),
    h('output', { class: 'wz-score', 'aria-live': 'polite' }, String(score)),
    h('button', { type: 'button', class: 'btn btn-small', 'data-key': `plus-${ability}`, 'aria-label': t('wz.raise', { name }), disabled: score >= POINT_MAX || nextCost > left, onclick: () => move(1) }, '+'),
    h('span', { class: 'wz-cost' }, t('wz.cost', { n: POINT_COSTS[score] })),
  );
}

function picker(env, ability) {
  const { draft, update } = env;
  const values = assignableValues(draft);
  const used = new Set(Object.entries(draft.assign).filter(([a]) => a !== ability).map(([, i]) => i));
  const select = h(
    'select',
    { class: 'wz-select', 'data-key': `sel-${ability}`, 'aria-label': t(`abil.${ability}`) },
    h('option', { value: '' }, t('wz.unassigned')),
    ...values.map((v, i) => h('option', { value: String(i), disabled: used.has(i), selected: draft.assign[ability] === i }, String(v))),
  );
  select.addEventListener('change', () =>
    update((d) => {
      if (select.value === '') delete d.assign[ability];
      else d.assign[ability] = Number(select.value);
    }),
  );
  return select;
}

function table(env) {
  const { draft, ctx } = env;
  const extra = bonuses(draft, ctx);
  const finals = finalScores(draft, ctx);
  const rows = ABILITIES.map((a) =>
    h(
      'tr',
      {},
      h('th', { scope: 'row' }, t(`abil.${a}`)),
      h('td', {}, draft.method === 'point_buy' ? stepper(env, a) : picker(env, a)),
      h('td', { class: 'num' }, extra[a] ? signed(extra[a]) : '-'),
      h('td', { class: 'num strong' }, finals ? String(finals[a]) : '-'),
      h('td', { class: 'num' }, finals ? signed(modifier(finals[a])) : '-'),
    ),
  );
  return h(
    'table',
    { class: 'wz-table' },
    h('thead', {}, h('tr', {}, ...['ability', 'base', 'bonus', 'total', 'mod'].map((k) => h('th', { scope: 'col' }, t(`wz.col_${k}`))))),
    h('tbody', {}, ...rows),
  );
}

function diceRow(roll, index) {
  return h(
    'li',
    { class: 'wz-roll', 'data-testid': 'ability-roll' },
    h('span', { class: 'wz-roll-n' }, `#${index + 1}`),
    ...roll.dice.map((d) => h('span', { class: d.kept ? 'die' : 'die dropped', 'aria-label': d.kept ? null : t('wz.dropped') }, String(d.value))),
    h('strong', { class: 'wz-roll-total' }, String(roll.total)),
  );
}

function rollPanel(env) {
  const { draft, send } = env;
  const button = h('button', { type: 'button', class: 'btn', 'data-testid': 'roll-abilities', onclick: () => send('roll_abilities') }, draft.rolls.length ? t('wz.rollAgain') : t('wz.rollDice'));
  return h(
    'div',
    { class: 'wz-rolls' },
    h('p', { class: 'hint' }, t('wz.rollHint')),
    button,
    draft.rolls.length ? h('ol', { class: 'wz-roll-list' }, ...draft.rolls.map(diceRow)) : null,
  );
}

function summary(env) {
  const { draft } = env;
  if (draft.method === 'point_buy') {
    const left = POINT_BUDGET - pointCost(draft.points);
    return h('p', { class: 'wz-points', 'aria-live': 'polite', 'data-testid': 'points-left' }, t('wz.pointsLeft', { left, total: POINT_BUDGET }));
  }
  if (draft.method === 'standard_array') return h('p', { class: 'hint' }, t('wz.arrayHint', { list: STANDARD_ARRAY.join(', ') }));
  return null;
}

export function renderAbilities(env) {
  const { draft } = env;
  const tabs = METHODS.map((m) =>
    h('button', { type: 'button', class: draft.method === m ? 'btn selected' : 'btn', 'aria-pressed': String(draft.method === m), 'data-key': `method-${m}`, onclick: () => setMethod(env, m) }, t(`wz.method_${m}`)),
  );
  return h(
    'div',
    {},
    h('div', { class: 'wz-methods', role: 'group' }, ...tabs),
    summary(env),
    draft.method === 'roll_4d6' ? rollPanel(env) : null,
    table(env),
  );
}
