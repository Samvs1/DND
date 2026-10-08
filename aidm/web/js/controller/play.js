// The Play tab: the last narration line, the hotbar and target chips in a fight, the action box and a Trade
// button while a shopkeeper is present.
import { mountHotbar } from '../combat/hotbar.js';
import { publicState } from '../table/lookup.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { mountAction } from './action.js';
import { mountLastLine } from './lastline.js';
import { mountTargets } from './targets.js';

function mountTrade(root, { store }) {
  const button = h('button', { type: 'button', class: 'btn btn-small', hidden: true, 'aria-haspopup': 'dialog', 'data-testid': 'open-shop', onclick: () => store.update({ panel: 'shop' }) }, t('ct.trade'));
  root.append(button);
  const render = (state) => {
    const scene = publicState(state)?.scene;
    button.hidden = !(scene?.shop_npc_id || scene?.shopkeepers?.length);
  };
  render(store.get());
  return store.subscribe(render);
}

export function mountPlay(root, ctx, ctrl) {
  const last = h('div', { class: 'ct-last-wrap' });
  const hotbar = h('div', { class: 'hotbar', 'data-testid': 'hotbar', role: 'region', 'aria-label': t('hotbar.label') });
  const targets = h('div', { class: 'ct-targets-wrap' });
  const trade = h('div', { class: 'ct-trade' });
  const box = h('div', { class: 'ct-action' });
  root.append(last, hotbar, targets, trade, box);
  return [mountLastLine(last, ctx), mountHotbar(hotbar, ctx, ctrl), mountTargets(targets, ctx, ctrl), mountTrade(trade, ctx), mountAction(box, ctx)];
}
