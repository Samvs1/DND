// Scene header of the screen (M24 dark pixel): the location's name on a ribbon over its region banner (the
// place's terrain, else the tier banner), and the campaign title with the active main quest's objective as a
// caption on the picture.
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { clamp } from '../ui/format.js';
import { publicState } from './lookup.js';

/** The objective of the ACTIVE main quest (M23.7): never a side quest title; "" when there is none. */
export function mainObjective(view) {
  return view?.quests?.find((q) => q.kind === 'main' && q.state === 'active')?.objective ?? '';
}

/** Art keys for the place's picture: its terrain banner first, the tier banner as the fallback. */
export function sceneArt(view) {
  const tier = `region_banner.tier${clamp(view?.region_tier || 1, 1, 3)}`;
  const terrain = view?.scene?.terrain;
  return terrain ? [`region_banner.${terrain}`, tier] : tier;
}

export function mountScene(root, store) {
  const banner = h('img', { class: 'scene-art', alt: '', width: 640, height: 120 });
  const title = h('p', { class: 'scene-title', 'data-testid': 'campaign-title' });
  const place = h('h2', { class: 'scene-place', 'data-testid': 'scene-name' });
  const goal = h('p', { class: 'scene-goal', 'data-testid': 'objective' });
  const paused = h('span', { class: 'tag tag-host', hidden: true, role: 'status' }, t('table.paused'));
  const ribbon = h('div', { class: 'scene-ribbon' }, place);
  const picture = h('div', { class: 'scene-pic' }, banner, h('div', { class: 'scene-text' }, title, goal), paused);
  root.append(ribbon, picture);

  function render(state) {
    const view = publicState(state);
    if (!view) return;
    const src = assetUrl(sceneArt(view));
    if (banner.getAttribute('src') !== src) banner.src = src;
    title.textContent = view.campaign_title;
    place.textContent = view.scene ? view.scene.name : '';
    const text = mainObjective(view);
    goal.textContent = text ? t('table.objective', { text }) : '';
    goal.hidden = !text;
    paused.hidden = !view.paused;
  }
  render(store.get());
  return store.subscribe(render);
}
