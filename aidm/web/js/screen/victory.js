// Victory on /screen. The fight banner is visual only (the Scribe does not speak after an ordinary fight):
// it shows a few seconds after a won fight unless that fight completed the campaign. The campaign victory
// screen (like the defeat overlay) shows once the campaign is complete and carries the epilogue.
import { stingerFor } from '../audio/music.js';
import { shadedBackground } from '../assets.js';
import { portraitSrc } from '../scribe/portrait.js';
import { victoryShown } from '../controller/victory.js';
import { publicState } from '../table/lookup.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

const BANNER_MS = 5000;
const SETTLE_MS = 1200; // the campaign flags may follow the end of the fight by a moment

export function mountFightBanner(root, store) {
  const box = h('div', { class: 'sc-victory-banner', hidden: true, role: 'status', 'data-testid': 'screen-victory-banner' }, t('victory.banner'));
  root.append(box);
  let wasCombat = Boolean(publicState(store.get())?.combat);
  let settle = null;
  let hide = null;
  const reveal = () => {
    const view = publicState(store.get());
    if (!view || view.complete || view.defeat || view.phase === 'defeated' || stingerFor(view) !== 'victory') return;
    box.hidden = false;
    clearTimeout(hide);
    hide = setTimeout(() => (box.hidden = true), BANNER_MS);
  };
  const stop = store.subscribe((state) => {
    const view = publicState(state);
    const inCombat = Boolean(view?.combat);
    if (wasCombat && !inCombat && view) {
      clearTimeout(settle);
      settle = setTimeout(reveal, SETTLE_MS);
    }
    if (inCombat) box.hidden = true;
    wasCombat = inCombat;
  });
  return () => {
    stop();
    clearTimeout(settle);
    clearTimeout(hide);
  };
}

export function mountVictory(root, store) {
  const text = h('p', { class: 'sc-victory-text', 'data-testid': 'screen-victory-text' });
  const portrait = h('img', { class: 'sc-scribe-portrait', src: portraitSrc('victory_campaign'), alt: t('scribe.portraitAlt') });
  const overlay = h('div', { class: 'sc-victory', hidden: true, role: 'dialog', 'aria-labelledby': 'sc-victory-h', 'data-testid': 'screen-victory' }, portrait, h('h2', { id: 'sc-victory-h' }, t('victory.title')), h('h3', {}, t('victory.epilogue')), text);
  root.append(overlay);
  function render(state) {
    const view = publicState(state);
    const shown = victoryShown(view);
    overlay.hidden = !shown;
    if (!shown) return;
    text.textContent = view.epilogue;
    portrait.src = portraitSrc('victory_campaign');
    overlay.style.backgroundImage = shadedBackground('scene.scribe');
  }
  render(store.get());
  return store.subscribe(render);
}
