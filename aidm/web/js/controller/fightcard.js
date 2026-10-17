// Fight rolls on my phone (M26.7, docs/next/GOAL_DICE.md): when a roll in a fight is MINE (my attack, my
// save) or is AIMED AT ME (a monster's attack on my hero), a card shows it in time with the TV: the die,
// the total against the target number, then the verdict at the moment the TV floats it over the token.
// The words are the party's (MISSED YOU, HIT YOU, RESISTED, CAUGHT). The card stays until the next one,
// or fades after a few seconds; HP comes off the strip when the state arrives (the pacer holds it).
import { myCreatureId } from '../combat/model.js';
import { creatureName } from '../table/lookup.js';
import { natural } from '../show/timing.js';
import { makeDie } from '../show/throw.js';
import { boardVerdict, onPartySide } from '../show/words.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

const VERDICT_MS = 590; // the die's arc (430) + its landing (160) on the TV
const STAY_MS = 4000;
export const FIGHT_KINDS = ['attack', 'check', 'save', 'death_save']; // the rest (damage, healing) stay toasts

function cardFor(dice, state, me) {
  const name = (id) => (id === me ? t('show.you') : creatureName(state, id));
  const mine = dice.roller_id === me;
  const atMe = dice.kind === 'attack' && dice.target_id === me && !mine;
  if (!mine && !atMe) return null;
  const verdict = boardVerdict(dice, state, (id) => name(id));
  const ours = onPartySide(state, dice.roller_id);
  const kind = verdict.tone === 'crit' ? 'crit' : ours ? 'hero' : 'foe';
  const title = atMe ? t('show.attacksYou', { name: creatureName(state, dice.roller_id), what: dice.label }) : dice.label;
  const target = dice.kind === 'attack' ? t('show.vsAc', { n: dice.target }) : t('show.vsDc', { n: dice.target });
  return { title, kind, face: natural(dice), total: dice.total, target, verdict, atMe };
}

export function mountFightCard(root, { store, pacer }) {
  let open = null;

  function close() {
    if (!open) return;
    open.timers.forEach((id) => clearTimeout(id));
    open.card.remove();
    open = null;
  }

  function show(msg, { scale }) {
    const state = store.get();
    const dice = msg.dice;
    const me = myCreatureId(state);
    if (!dice || !me || !FIGHT_KINDS.includes(dice.kind)) return;
    const c = cardFor(dice, state, me);
    if (!c) return;
    close();
    const die = makeDie(c.kind, 56, c.face);
    const verdict = h('span', { class: `fc-verdict ${c.verdict.tone}`, hidden: true, 'data-testid': 'fight-card-verdict' }, c.verdict.word);
    const card = h(
      'section',
      { class: `fc${c.atMe ? ' at-me' : ''}`, role: 'status', 'aria-live': 'polite', 'data-testid': 'fight-card' },
      h('div', { class: 'fc-die' }, die),
      h('div', { class: 'fc-body' }, h('div', { class: 'fc-title' }, c.title), h('div', { class: 'fc-math' }, h('b', {}, String(c.total)), ` ${c.target}`)),
      verdict,
    );
    root.append(card);
    open = {
      card,
      timers: [setTimeout(() => (verdict.hidden = false), VERDICT_MS * scale), setTimeout(close, STAY_MS)],
    };
  }

  const stop = pacer.onShow((msg, timing) => {
    if (msg.type === 'dice_roll' && timing.combat) show(msg, timing);
  });
  return () => {
    stop();
    close();
  };
}
