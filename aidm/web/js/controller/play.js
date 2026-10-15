// The Play tab (M18.2: the phone is a controller, not a second screen): the Now card; in a fight on my turn the
// Move list (M19.4), the hotbar and the target chips; the action box near the top (no bottom toolbar or keyboard
// hides it), idea chips from the scene (Trade among them) and my last roll. The story itself is told on the
// screen (and kept under Journal, Story).
import { mountHotbar } from '../combat/hotbar.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { mountAction } from './action.js';
import { mountIdeas } from './ideas.js';
import { mountLastRoll } from './lastroll.js';
import { mountMoves } from './moves.js';
import { mountNow } from './now.js';
import { mountTargets } from './targets.js';
import { mountWhatNow } from './what_now.js';

export function mountPlay(root, ctx, ctrl) {
  const now = h('div', { class: 'ct-now-wrap' });
  const whatNow = h('div', { class: 'ct-wn-wrap' });
  const moves = h('div', { class: 'ct-moves-wrap' });
  const hotbar = h('div', { class: 'hotbar', 'data-testid': 'hotbar', role: 'region', 'aria-label': t('hotbar.label') });
  const targets = h('div', { class: 'ct-targets-wrap' });
  const box = h('div', { class: 'ct-action' });
  const ideas = h('div', { class: 'ct-ideas-wrap' });
  const roll = h('div', { class: 'ct-roll-wrap' });
  root.append(now, whatNow, moves, hotbar, targets, box, ideas, roll);
  return [mountNow(now, ctx), mountWhatNow(whatNow, ctx), mountMoves(moves, ctx, ctrl), mountHotbar(hotbar, ctx, ctrl), mountTargets(targets, ctx, ctrl), mountAction(box, ctx), mountIdeas(ideas, ctx), mountLastRoll(roll, ctx)];
}
