// The words of a roll's result (M26, docs/next/GOAL_DICE.md), always told from the party's side: the die's
// look says WHO rolled it, the verdict's colour says what it MEANS for the party (good = teal, bad = crimson).
// A monster making its save against a hero reads RESISTED (bad), failing it CAUGHT (good); a monster's attack
// on a hero reads MISSED <hero> (good) or HIT <hero> (bad).
import { t } from '../strings.js';
import { natural } from './timing.js';

/** The stage verdict of a check or save: nat20 | nat1 (checks only) | success | failure. */
export function verdictOf(dice) {
  const face = natural(dice);
  if (dice.kind === 'check' && face === 20) return 'nat20';
  if (dice.kind === 'check' && face === 1) return 'nat1';
  return dice.success ? 'success' : 'failure';
}

/** True when the creature fights on the party's side (a hero or an ally) in the state shown. */
export function onPartySide(state, creatureId) {
  const view = state.snapshot?.state;
  if (view?.party?.some((c) => c.id === creatureId)) return true;
  const token = view?.combat?.tokens?.find((tk) => tk.creature_id === creatureId);
  return token ? token.side !== 'hostile' : false;
}

/**
 * The board verdict of a roll: { word, tone } with tone good | bad | crit. `name(id)` gives a creature's name.
 * Attacks speak of the target, saves and checks of the roller.
 */
export function boardVerdict(dice, state, name) {
  const roller = dice.roller_id;
  const face = natural(dice);
  if (dice.kind === 'attack') {
    const ours = onPartySide(state, roller);
    if (ours) {
      if (dice.crit && dice.success) return { word: t('show.critHit'), tone: 'crit' };
      return dice.success ? { word: t('show.hit'), tone: 'good' } : { word: t('show.miss'), tone: 'bad' };
    }
    const who = name(dice.target_id).toUpperCase();
    return dice.success ? { word: t('show.hitHero', { name: who }), tone: 'bad' } : { word: t('show.missedHero', { name: who }), tone: 'good' };
  }
  if (dice.kind === 'death_save') {
    if (face === 20) return { word: t('show.revived'), tone: 'crit' };
    return dice.success ? { word: t('show.success'), tone: 'good' } : { word: t('show.failure'), tone: 'bad' };
  }
  if (onPartySide(state, roller)) {
    if (dice.kind === 'check') return dice.success ? { word: t('show.success'), tone: 'good' } : { word: t('show.failure'), tone: 'bad' };
    return dice.success ? { word: t('show.saved'), tone: 'good' } : { word: t('show.failed'), tone: 'bad' };
  }
  return dice.success ? { word: t('show.resisted'), tone: 'bad' } : { word: t('show.caught'), tone: 'good' };
}

/** "DIS · Darkness" / "ADV · Hidden" for a roll that had advantage or disadvantage, else ''. */
export function advTag(dice) {
  if (dice.adv !== 'advantage' && dice.adv !== 'disadvantage') return '';
  const tag = t(dice.adv === 'advantage' ? 'show.advShort' : 'show.disShort');
  const why = (dice.adv_why || []).join(', ');
  return why ? t('show.advTag', { tag, why }) : tag;
}
