// The screen's show player (M26, docs/next/GOAL_DICE.md): the pacer hands it each message that starts a
// show and waits for the promise it returns. A check or save out of combat plays the roll stage; rolls in a
// fight, the damage taken and a creature falling play on the board. Anything else returns null, and the
// pacer holds the nominal time instead, exactly as the phones do.
import { createBoardShows } from './board.js';
import { playStage } from './stage.js';
import { inCombat, isStageRoll } from './timing.js';

export function createDirector({ store, layer, sfx, onStep }) {
  const board = createBoardShows({ layer, store, sfx, onStep });
  return (msg, { scale, signal }) => {
    const combat = inCombat(store);
    if (msg.type === 'dice_roll' && msg.dice) {
      if (isStageRoll(msg.dice, combat)) return playStage(layer, msg.dice, store.get(), sfx, { scale, signal });
      return combat ? board.play(msg, { scale, signal }) : null;
    }
    if (msg.type === 'event' && combat) return board.play(msg, { scale, signal });
    return null;
  };
}
