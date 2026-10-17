// The screen's show player (M26, docs/next/GOAL_DICE.md): the pacer hands it each message that starts a
// show and waits for the promise it returns. A check or save out of combat plays the roll stage; rolls in a
// fight play on the board (js/show/board.js, M26.7). Anything it does not show returns null, and the pacer
// holds the nominal time instead, exactly as the phones do.
import { playStage } from './stage.js';
import { inCombat, isStageRoll } from './timing.js';

export function createDirector({ store, layer, sfx }) {
  return (msg, { scale, signal }) => {
    if (msg.type !== 'dice_roll' || !msg.dice) return null;
    if (isStageRoll(msg.dice, inCombat(store))) return playStage(layer, msg.dice, store.get(), sfx, { scale, signal });
    return null;
  };
}
