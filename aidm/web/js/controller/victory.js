// Campaign victory on the phone: a full-page panel with the epilogue once the campaign is complete and the
// party is not defeated. The host (or the only player) can start a new campaign with the host panel's action.
import { confirmButton } from '../host/confirm.js';
import { shadedBackground } from '../assets.js';
import { portraitSrc } from '../scribe/portrait.js';
import { publicState } from '../table/lookup.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

export function victoryShown(view) {
  return Boolean(view && view.complete && !view.defeat && view.epilogue);
}

export function mountVictoryPanel(root, { store, client }) {
  const text = h('p', { class: 'ct-victory-text', 'data-testid': 'victory-text' });
  const portrait = h('img', { class: 'sc-portrait', src: portraitSrc('victory_campaign'), alt: t('scribe.portraitAlt'), width: 96, height: 96 });
  const host = h('div', { class: 'ct-victory-host', 'data-testid': 'victory-host' }, confirmButton({ label: t('host.newGame'), ask: t('host.newAsk'), yes: t('host.newYes'), testid: 'victory-new', onYes: () => client.send('host_new') }));
  const wait = h('p', { class: 'hint', 'data-testid': 'victory-wait' }, t('victory.waitHost'));
  const panel = h('section', { class: 'ct-victory', hidden: true, role: 'dialog', 'aria-labelledby': 'ct-victory-h', 'data-testid': 'controller-victory' }, portrait, h('h2', { id: 'ct-victory-h' }, t('victory.title')), text, host, wait);
  root.append(panel);
  function render(state) {
    const view = publicState(state);
    const shown = victoryShown(view);
    panel.hidden = !shown;
    if (!shown) return;
    panel.style.backgroundImage = shadedBackground('scene.scribe');
    portrait.src = portraitSrc('victory_campaign');
    text.textContent = view.epilogue;
    host.hidden = !state.me.isHost;
    wait.hidden = state.me.isHost;
  }
  render(store.get());
  return store.subscribe(render);
}
