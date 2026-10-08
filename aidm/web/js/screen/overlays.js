// Screen overlays: the level-up banner and the full-screen defeat overlay.
import { assetUrl } from '../assets.js';
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
    const art = assetUrl(DEFEAT_KEY);
    const real = art && !art.includes('/placeholder/'); // M12 adds the art; until then a plain themed background
    overlay.style.backgroundImage = real ? `linear-gradient(rgba(0,0,0,.65), rgba(0,0,0,.8)), url("${art}")` : '';
  }
  render(store.get());
  return store.subscribe(render);
}
