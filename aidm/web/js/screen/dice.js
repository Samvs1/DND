// Big dice display for the shared screen: the newest roll(s) shown large for a few seconds. Read-only;
// it reuses the roll model of js/table/dice.js (kept die, advantage label) but has no controls.
import { keptIndex } from '../table/dice.js';
import { creatureName } from '../table/lookup.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';

const SHOW_MS = 6000;
const MAX_SHOWN = 3;

function outcome(roll) {
  const parts = [];
  if (roll.crit) parts.push(t('table.crit'));
  if (roll.target !== null && roll.target !== undefined) parts.push(t('table.vs', { n: roll.target }));
  if (roll.success === true) parts.push(t('table.success'));
  if (roll.success === false) parts.push(t('table.failure'));
  return parts.join(' / ');
}

function bigRoll(roll, state) {
  const kept = keptIndex(roll);
  const who = creatureName(state, roll.roller_id);
  const dice = roll.rolls.map((v, i) => h('span', { class: `sc-die ${kept < 0 || kept === i ? 'kept' : 'dropped'}` }, String(v)));
  const adv = roll.adv && roll.adv !== 'normal' ? h('span', { class: 'tag' }, t(`table.adv_${roll.adv}`)) : null;
  return h(
    'li',
    { class: 'sc-roll', 'data-testid': 'screen-roll' },
    h('div', { class: 'sc-roll-head' }, h('strong', {}, roll.label || roll.expression), who ? h('span', { class: 'muted' }, who) : null, adv),
    h('div', { class: 'sc-roll-dice' }, ...dice, h('strong', { class: 'sc-roll-total' }, `= ${roll.total}`)),
    outcome(roll) ? h('div', { class: 'sc-roll-out' }, outcome(roll)) : null,
  );
}

export function mountScreenDice(root, { store, story }) {
  const list = h('ol', { class: 'sc-dice', hidden: true, 'data-testid': 'screen-dice', 'aria-live': 'polite' });
  root.append(list);
  let timer = null;
  const stop = story.subscribe((change) => {
    if (change.type !== 'dice') return;
    const now = Date.now();
    const rolls = story.dice.filter((r) => now - r.at < SHOW_MS).slice(0, MAX_SHOWN);
    clear(list);
    list.append(...rolls.map((r) => bigRoll(r, store.get())));
    list.hidden = rolls.length === 0;
    clearTimeout(timer);
    timer = setTimeout(() => {
      list.hidden = true;
      clear(list);
    }, SHOW_MS);
  });
  return () => {
    stop();
    clearTimeout(timer);
  };
}
