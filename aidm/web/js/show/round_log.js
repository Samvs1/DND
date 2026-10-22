// The words around the board shows (M26.7, docs/next/GOAL_DICE.md): the STRIP under the board spells out
// the action being shown step by step (who at whom, the die and the maths, the verdict, the damage, who
// falls), and THIS ROUND in the side column keeps one line per finished roll, newest on top (it replaces
// the old dice card). Both are fed by the board shows' steps (board.js `onStep`).
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { keptIndex } from '../table/dice.js';
import { natural } from './timing.js';
import { diceSides } from './board.js';
import { spriteKey } from './throw.js';
import { tipButton } from '../ui/tip.js';
import { advTag, advTip } from './words.js';

const MAX_LINES = 6;

function miniDie(kind, value) {
  return h('span', { class: 'sr-die' }, h('img', { src: assetUrl(spriteKey(kind)), alt: '' }), h('b', {}, String(value)));
}

/** One mini d20, or two when the roll had advantage or disadvantage (the dropped one dimmed). */
function d20s(kind, dice) {
  const kept = keptIndex(dice);
  if (kept < 0) return [miniDie(kind, natural(dice))];
  return dice.rolls.map((v, i) => {
    const die = miniDie(kind, v);
    if (i !== kept) die.classList.add('dropped');
    return die;
  });
}

function tagChip(dice) {
  const text = advTag(dice);
  if (!text) return null;
  const tip = advTip(dice);
  return h('span', { class: 'sr-tagrow' }, h('span', { class: 'sr-tag', 'data-testid': 'adv-tag' }, text), tipButton(tip.key, text, tip.why));
}

function chip(word, tone) {
  return h('span', { class: `sr-chip ${tone}` }, word);
}

function signed(n) {
  return `${n >= 0 ? '+' : '-'} ${Math.abs(n)}`;
}

export function mountRoundLog({ strip, list }) {
  const lines = h('div', { class: 'sr-lines', 'data-testid': 'round-lines' });
  list.append(h('div', { class: 'lab' }, t('show.thisRound')), lines);
  let lastLine = null; // the line of the roll whose damage may still come

  function stripStart(...nodes) {
    clear(strip);
    strip.append(...nodes);
  }

  function addLine(kind, dice, text, word, tone) {
    const row = h('div', { class: 'sr-line', 'data-testid': 'round-line' }, h('span', { class: 'sr-dice' }, ...d20s(kind, dice)), h('span', { class: 'sr-text' }, text, tagChip(dice)), chip(word, tone));
    lines.prepend(row);
    while (lines.children.length > MAX_LINES) lines.lastChild.remove();
    lastLine = row;
  }

  function onAttack({ dice, verdict, name, ours }) {
    const kind = verdict.tone === 'crit' ? 'crit' : ours ? 'hero' : 'foe';
    const who = name(dice.roller_id);
    const at = name(dice.target_id);
    stripStart(
      h('span', {}, h('b', {}, who), ` ${t('show.at', { name: at })}`),
      h('span', { class: 'sr-arrow' }, '>'),
      ...d20s(kind, dice),
      h('span', {}, `${signed(dice.modifier)} = `, h('b', {}, String(dice.total)), ` ${t('show.vsAc', { n: dice.target })}`),
      tagChip(dice),
      chip(verdict.word, verdict.tone),
    );
    addLine(kind, dice, `${who} ${t('show.at', { name: at })}`, verdict.word, verdict.tone);
  }

  function onRolled({ dice, type }) {
    const sides = diceSides(dice.expression, dice.rolls.length);
    const parts = dice.rolls.map((v, i) => miniDie([4, 6, 8, 10, 12].includes(sides[i]) ? `d${sides[i]}` : 'hero', v));
    strip.append(h('span', { class: 'sr-arrow' }, '>'), h('span', {}, dice.label || t(`show.${type}`)), ...parts, dice.modifier ? ` ${signed(dice.modifier)}` : '', ' = ', h('b', {}, String(dice.total)));
  }

  function onSave({ dice, verdict, name, ours }) {
    stripStart(h('span', {}, h('b', {}, name(dice.roller_id)), ` ${dice.label}`), h('span', { class: 'sr-arrow' }, '>'), ...d20s(ours ? 'hero' : 'foe', dice), h('span', {}, `= `, h('b', {}, String(dice.total)), ` ${t('show.vsDc', { n: dice.target })}`), tagChip(dice), chip(verdict.word, verdict.tone));
    addLine(ours ? 'hero' : 'foe', dice, `${name(dice.roller_id)} ${dice.label}`, verdict.word, verdict.tone);
  }

  function onSpell({ line }) {
    stripStart(h('span', { 'data-testid': 'spell-line' }, line));
    const row = h('div', { class: 'sr-line sr-spell', 'data-testid': 'round-line' }, h('span', { class: 'sr-text' }, line));
    lines.prepend(row);
    while (lines.children.length > MAX_LINES) lines.lastChild.remove();
    lastLine = null;
  }

  function onTaken({ amount }) {
    const word = lastLine?.querySelector('.sr-chip');
    if (word && !word.dataset.amount) {
      word.dataset.amount = String(amount);
      word.textContent = t('show.withAmount', { word: word.textContent, n: amount });
    }
  }

  function onFell({ id, ours, name }) {
    strip.append(h('span', { class: 'sr-arrow' }, '>'), chip(t('show.falls', { name: name(id).toUpperCase() }), ours ? 'bad' : 'good'));
  }

  return {
    step(step) {
      if (step.type === 'attack') onAttack(step);
      else if (step.type === 'damage' || step.type === 'heal') onRolled(step);
      else if (step.type === 'save' || step.type === 'check' || step.type === 'death_save') onSave(step);
      else if (step.type === 'spell') onSpell(step);
      else if (step.type === 'taken') onTaken(step);
      else if (step.type === 'fell') onFell(step);
    },
    clear() {
      clear(strip);
      clear(lines);
      lastLine = null;
    },
  };
}
