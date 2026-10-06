// Dice tray: the latest rolls with every d20 shown, the kept die highlighted, an advantage or
// disadvantage label, the modifier, the total and the outcome against its target. The newest roll
// tumbles and its numbers cycle before settling; reduced motion shows the result at once.
import { reducedMotion } from '../settings/model.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { creatureName } from './lookup.js';

const SHOWN = 5;
const CYCLE_MS = 600;
const FRAME_MS = 60;

/** Index of the kept die: the highest on advantage, the lowest on disadvantage, else the first. */
export function keptIndex(roll) {
  if (roll.rolls.length < 2 || roll.expression !== '2d20') return -1;
  const target = roll.adv === 'disadvantage' ? Math.min(...roll.rolls) : Math.max(...roll.rolls);
  return roll.rolls.indexOf(target);
}

function sidesOf(roll) {
  const match = /d(\d+)/.exec(roll.expression);
  return match ? Number(match[1]) : 20;
}

function cycle(el, final, sides) {
  if (reducedMotion()) return;
  const started = Date.now();
  const timer = setInterval(() => {
    if (Date.now() - started >= CYCLE_MS || !el.isConnected) {
      clearInterval(timer);
      el.textContent = String(final);
      return;
    }
    el.textContent = String(1 + Math.floor(Math.random() * sides));
  }, FRAME_MS);
}

function dieNode(value, kind, fresh, sides) {
  const el = h('span', { class: `die ${kind}${fresh ? ' fresh' : ''}`, 'data-testid': 'die' }, String(value));
  if (fresh) cycle(el, value, sides);
  return el;
}

function outcome(roll) {
  const parts = [];
  if (roll.crit) parts.push(t('table.crit'));
  if (roll.target !== null && roll.target !== undefined) parts.push(t('table.vs', { n: roll.target }));
  if (roll.success === true) parts.push(t('table.success'));
  if (roll.success === false) parts.push(t('table.failure'));
  return parts.join(' / ');
}

function rollNode(roll, state, fresh) {
  const kept = keptIndex(roll);
  const sides = sidesOf(roll);
  const dice = roll.rolls.map((v, i) => dieNode(v, kept < 0 || kept === i ? 'kept' : 'dropped', fresh, sides));
  const who = creatureName(state, roll.roller_id);
  const mod = roll.modifier ? ` ${roll.modifier > 0 ? '+' : '-'} ${Math.abs(roll.modifier)}` : '';
  const adv = roll.adv && roll.adv !== 'normal' ? h('span', { class: `tag adv-${roll.adv}`, 'data-testid': 'adv-label' }, t(`table.adv_${roll.adv}`)) : null;
  return h(
    'li',
    { class: fresh ? 'roll fresh' : 'roll', 'data-testid': 'dice-roll' },
    h('div', { class: 'roll-head' }, h('strong', {}, roll.label || roll.expression), who ? h('span', { class: 'muted' }, who) : null, adv),
    h('div', { class: 'roll-dice' }, ...dice, h('span', { class: 'roll-sum' }, `${mod} = `), h('strong', { class: 'roll-total' }, String(roll.total))),
    outcome(roll) ? h('div', { class: 'roll-out' }, outcome(roll)) : null,
  );
}

export function mountDice(root, { store, story, latest }) {
  const list = h('ol', { class: 'dice-list', 'data-testid': 'dice-tray' });
  const live = h('p', { class: 'sr-only', 'aria-live': 'polite' });
  const empty = h('p', { class: 'hint' }, t('table.diceEmpty'));
  root.append(list, empty, live);

  function render(freshSeq) {
    clear(list);
    const rolls = story.dice.slice(0, SHOWN);
    empty.hidden = rolls.length > 0;
    rolls.forEach((roll, i) => list.append(rollNode(roll, store.get(), i === 0 && roll.seq === freshSeq)));
    const top = rolls[0];
    live.textContent = top ? `${top.label} ${top.total} ${outcome(top)}` : '';
    if (latest) latest.textContent = top ? `${top.label}: ${top.total}` : '';
  }
  render(null);
  return story.subscribe((change) => {
    if (change.type === 'dice') render(change.roll.seq);
    if (change.type === 'reset' || change.type === 'load') render(null);
  });
}
