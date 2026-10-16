// "Your last roll" on the Play tab (M18.2): my most recent roll stays readable after its toast fades (the big
// dice are on the shared screen). `rollNodes` is shared with the toast so both show a roll the same way.
import { myCreatureId } from '../combat/model.js';
import { keptIndex, outcome } from '../table/dice.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';

/** Label, each die (dropped dice struck through), total and outcome of one roll. */
export function rollNodes(roll) {
  const kept = keptIndex(roll);
  const dice = roll.rolls.map((v, i) => h('span', { class: `ct-die${kept < 0 || kept === i ? '' : ' dropped'}` }, String(v)));
  const result = outcome(roll);
  // No null in the list: Element.append prints it as the text "null" (a damage roll has no outcome).
  return [h('strong', {}, roll.label || roll.expression), ' ', ...dice, ` = ${roll.total}`, ...(result ? [h('span', { class: 'hint' }, ` ${result}`)] : [])];
}

export function mountLastRoll(root, { store, story }) {
  const body = h('p', { class: 'ct-roll-body' });
  const card = h('section', { class: 'ct-roll', hidden: true, 'aria-label': t('ct.lastRoll'), 'data-testid': 'last-roll' }, h('h3', { class: 'ct-idea-h' }, t('ct.lastRoll')), body);
  root.append(card);
  let shown = null;

  function render() {
    const me = myCreatureId(store.get());
    const roll = me ? story.dice.find((r) => r.roller_id === me) : undefined;
    card.hidden = !roll;
    if (!roll || roll === shown) return;
    shown = roll;
    clear(body);
    body.append(...rollNodes(roll));
    card.dataset.success = roll.success === true ? 'yes' : roll.success === false ? 'no' : '';
  }
  render();
  const stops = [story.subscribe(render), store.subscribe(render)];
  return () => stops.forEach((stop) => stop());
}
