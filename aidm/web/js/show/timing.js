// How long the table holds each message (M26, docs/next/GOAL_DICE.md). The screen and the phones use the
// same numbers, so a phone never shows a result before the TV has. A roll out of combat is the roll
// stage; in a fight a roll plays on the board. Every other message is held 0 ms (it shows at once, in
// order). The shows themselves (js/show/stage.js, board.js) are built to fit these budgets.
import { reducedMotion } from '../settings/model.js';
import { keptIndex } from '../table/dice.js';

export const STAGE_MS = 3800; // 0.7 s to read the stage (owner: +0.5 s), the throw, bonuses, verdict, hold, fade
export const STAGE_TWO_MS = 300; // advantage / disadvantage: the dropped die steps aside
export const STAGE_NATURAL_MS = 400; // a natural 20 flares, a natural 1 cracks
export const STAGE_CRIT_HOLD_MS = 600; // a natural 20 is held a little longer
export const ATTACK_HIT_MS = 1100; // the die arcs to the target (0.43 s), lands, the verdict floats
export const ATTACK_MISS_MS = 1300; // a miss holds its verdict longer (nothing follows it)
export const DAMAGE_MS = 600; // damage dice pop under the target
export const DAMAGE_DIE_MS = 130; // each further damage die
export const SAVE_MS = 900; // a die drops under the saver, its verdict floats
export const DEATH_SAVE_MS = 1300;
export const HEAL_MS = 700;
export const OTHER_ROLL_MS = 400;
export const SPELL_LINE_MS = 1400; // a spell with no roll: its one line on the strip
export const FLOAT_MS = 500; // damage taken or a creature falling, on the board
const STAGE_KINDS = new Set(['check', 'save', 'death_save']);

/** True when the fight is on in the state the table is showing. */
export function inCombat(store) {
  return Boolean(store.get().snapshot?.state?.combat);
}

/** The kept d20 face of a roll (the higher with advantage, the lower with disadvantage). */
export function natural(dice) {
  const kept = keptIndex(dice);
  return dice.rolls[kept < 0 ? 0 : kept];
}

/** Does this roll play as the roll stage? Checks and saves out of combat do. */
export function isStageRoll(dice, combat) {
  return !combat && STAGE_KINDS.has(dice.kind);
}

function stageMs(dice) {
  let ms = STAGE_MS;
  if (dice.rolls.length === 2) ms += STAGE_TWO_MS;
  const face = natural(dice);
  if (dice.kind !== 'save' && (face === 20 || face === 1)) ms += STAGE_NATURAL_MS;
  if (dice.kind !== 'save' && face === 20) ms += STAGE_CRIT_HOLD_MS;
  return ms;
}

function boardMs(dice) {
  switch (dice.kind) {
    case 'attack':
      return dice.success === false ? ATTACK_MISS_MS : ATTACK_HIT_MS;
    case 'damage':
      return DAMAGE_MS + DAMAGE_DIE_MS * Math.max(0, dice.rolls.length - 1);
    case 'save':
    case 'check':
      return SAVE_MS;
    case 'death_save':
      return DEATH_SAVE_MS;
    case 'heal':
      return HEAL_MS;
    default:
      return OTHER_ROLL_MS;
  }
}

/** The full-speed hold of one message, in ms (0 = no show). */
export function nominalMs(msg, combat) {
  if (msg.type === 'dice_roll' && msg.dice) return isStageRoll(msg.dice, combat) ? stageMs(msg.dice) : boardMs(msg.dice);
  if (combat && msg.type === 'event' && msg.kind === 'spell_cast') return SPELL_LINE_MS;
  if (combat && msg.type === 'event' && msg.subject_id && (msg.kind === 'damage_taken' || msg.kind === 'creature_died')) return FLOAT_MS;
  return 0;
}

/** Shows speed up when rolls queue behind them, so the table never lags far behind the game. */
export function backlogFactor(waiting) {
  if (waiting >= 4) return 0.5;
  if (waiting >= 2) return 0.7;
  return 1;
}

/** Reduced motion keeps the order and the sounds but shortens every show; tests scale it down. */
export function motionFactor() {
  const scale = typeof window !== 'undefined' && typeof window.__aidmShowScale === 'number' ? window.__aidmShowScale : 1;
  return (reducedMotion() ? 0.6 : 1) * scale;
}
