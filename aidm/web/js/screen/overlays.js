// Screen overlays: the level-up banner and the full-screen defeat overlay.
import { shadedBackground } from '../assets.js';
import { publicState } from '../table/lookup.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

const BANNER_MS = 7000;
const DEFEAT_KEY = 'scene.defeat';

export function mountLevelBanner(root, store) {
  const box = h('div', { class: 'sc-levelup', hidden: true, role: 'status', 'data-testid': 'screen-levelup' });
  root.append(box);
  let timer = null;
  const stop = store.on('event', (msg) => {
    if (msg.kind !== 'level_gained' || !msg.line) return;
    box.textContent = msg.line;
    box.hidden = false;
    clearTimeout(timer);
    timer = setTimeout(() => (box.hidden = true), BANNER_MS);
  });
  return () => {
    stop();
    clearTimeout(timer);
  };
}

export function mountDefeat(root, store) {
  const text = h('p', { class: 'sc-defeat-text', 'data-testid': 'defeat-text' });
  const checkpoint = h('p', { class: 'sc-defeat-cp', 'data-testid': 'defeat-checkpoint' });
  const overlay = h(
    'div',
    { class: 'sc-defeat', hidden: true, role: 'alertdialog', 'aria-labelledby': 'sc-defeat-h', 'data-testid': 'screen-defeat' },
    h('h2', { id: 'sc-defeat-h' }, t('screen.defeatTitle')),
    text,
    checkpoint,
    h('p', { class: 'sc-defeat-wait' }, t('screen.defeatWait')),
  );
  root.append(overlay);
  function render(state) {
    const view = publicState(state);
    const defeated = view?.phase === 'defeated';
    overlay.hidden = !defeated;
    if (!defeated) return;
    text.textContent = view.defeat ?? '';
    checkpoint.textContent = view.checkpoint ? t('screen.defeatCheckpoint', { label: view.checkpoint }) : '';
    checkpoint.hidden = !view.checkpoint;
    overlay.style.backgroundImage = shadedBackground(DEFEAT_KEY); // plain themed background until the art exists
  }
  render(store.get());
  return store.subscribe(render);
}
