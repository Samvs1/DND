// The table menu: one button per panel (journal, map, shop, host for the host only, settings). A button sets
// `store.panel`; each panel module opens its own modal dialog from that. Closing a panel returns focus here.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { publicState } from './lookup.js';

const BUTTONS = ['journal', 'map', 'shop', 'host', 'settings'];

export function mountToolbar(root, { store }) {
  const nav = h('nav', { class: 'tb-tools', 'aria-label': t('tools.label'), 'data-testid': 'tools' });
  const buttons = new Map();
  for (const key of BUTTONS) {
    const button = h('button', { type: 'button', class: 'btn btn-small tool-btn', 'data-testid': `open-${key}`, 'aria-haspopup': 'dialog', onclick: () => store.update({ panel: key }) }, t(`tools.${key}`));
    buttons.set(key, button);
    nav.append(button);
  }
  root.append(nav);

  function render(state) {
    buttons.get('host').hidden = !state.me.isHost;
    const view = publicState(state);
    const trading = Boolean(view?.scene?.shop_npc_id) || Boolean(view?.scene?.shopkeepers?.length);
    buttons.get('shop').classList.toggle('has-shop', trading);
  }
  render(store.get());
  const stop = store.subscribe(render);
  return () => {
    stop();
    nav.remove();
  };
}
