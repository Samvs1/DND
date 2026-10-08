// Dice roll model shared by the screen's big dice and the phone's own-roll toast.
import { t } from '../strings.js';

/** Index of the kept die: the highest on advantage, the lowest on disadvantage, else the first. */
export function keptIndex(roll) {
  if (roll.rolls.length < 2 || roll.expression !== '2d20') return -1;
  const target = roll.adv === 'disadvantage' ? Math.min(...roll.rolls) : Math.max(...roll.rolls);
  return roll.rolls.indexOf(target);
}

/** "Critical / vs 15 / Success" style outcome text of a roll, or ''. */
export function outcome(roll) {
  const parts = [];
  if (roll.crit) parts.push(t('table.crit'));
  if (roll.target !== null && roll.target !== undefined) parts.push(t('table.vs', { n: roll.target }));
  if (roll.success === true) parts.push(t('table.success'));
  if (roll.success === false) parts.push(t('table.failure'));
  return parts.join(' / ');
}
