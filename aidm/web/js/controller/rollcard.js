// "Your roll" on the roller's phone (M26.6, docs/next/GOAL_DICE.md): while the TV plays the roll stage for
// MY hero, the phone shows the same roll as a card, in time with the TV (the pacer tells it when the show
// starts and how long it lasts). The die flickers until it lands, then the total and the verdict appear at
// the moment the TV slams its verdict. Afterwards "Your last roll" keeps it (lastroll.js).
import { myCreatureId } from '../combat/model.js';
import { N20_BEATS } from '../show/natural20.js';
import { stageModel } from '../show/stage.js';
import { makeDie } from '../show/throw.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

const LAND_MS = 1550; // the stage's fade-in (200), its reading pause (500) and the throw (850)
const VERDICT_MS = 2250; // landing, settle, bonuses, then the verdict
const SETTLE_MS = 160; // the TV's die settles before a natural 20 starts its sound
const TWO_MS = 300; // advantage / disadvantage: the dropped die steps aside first

export function mountRollCard(root, { store, pacer }) {
  let open = null;

  function close() {
    if (!open) return;
    open.timers.forEach((id) => clearTimeout(id));
    clearInterval(open.spin);
    open.card.remove();
    open = null;
  }

  function show(msg, { ms, scale }) {
    const dice = msg.dice;
    const state = store.get();
    if (!dice || dice.roller_id !== myCreatureId(state)) return;
    close();
    const m = stageModel(dice, state);
    const die = makeDie('hero', 150, '?');
    die.classList.add('spin');
    const total = h('div', { class: 'rc-total', hidden: true }, `${m.face} ${m.parts.map((p) => `${p.value >= 0 ? '+' : '-'} ${Math.abs(p.value)}`).join(' ')} = `, h('b', {}, String(m.total)), ` ${t('show.vsDc', { n: m.dc })}`);
    const verdict = h('div', { class: `rc-verdict v-${m.verdict}`, hidden: true, 'data-testid': 'roll-card-verdict' }, t(`show.${m.verdict}`));
    const card = h(
      'section',
      { class: 'rc', role: 'status', 'aria-live': 'polite', 'data-testid': 'roll-card' },
      h('div', { class: 'rc-head' }, h('span', { class: 'rc-lab' }, t('show.yourRoll')), h('span', { class: 'rc-lab muted' }, t('show.onTheTv'))),
      h('div', { class: 'rc-title' }, m.title),
      h('div', { class: 'rc-die' }, die),
      total,
      verdict,
    );
    root.append(card);
    const two = m.rolls.length === 2 ? TWO_MS : 0;
    // a natural 20's banner slams with its sound, which runs in real time once the die has settled
    const verdictAt = m.verdict === 'nat20' ? (LAND_MS + SETTLE_MS + two) * scale + N20_BEATS.slam * 1000 : (VERDICT_MS + two) * scale;
    const spin = setInterval(() => (die.num.textContent = String(1 + Math.floor(Math.random() * 20))), 70);
    const timers = [
      setTimeout(() => {
        clearInterval(spin);
        die.classList.remove('spin');
        die.num.textContent = String(m.face);
      }, LAND_MS * scale),
      setTimeout(() => {
        total.hidden = false;
        verdict.hidden = false;
      }, verdictAt),
      setTimeout(close, ms),
    ];
    open = { card, timers, spin };
  }

  const stop = pacer.onShow((msg, timing) => {
    if (msg.type === 'dice_roll' && timing.stage) show(msg, timing);
  });
  return () => {
    stop();
    close();
  };
}
