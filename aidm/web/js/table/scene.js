// Scene header: region banner art, campaign title, location name and the active objective.
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { clamp } from '../ui/format.js';
import { publicState } from './lookup.js';

function objective(view) {
  const active = view.quests.find((q) => q.state === 'active') ?? view.quests.find((q) => q.state === 'offered');
  return active ? active.title : '';
}

export function mountScene(root, store) {
  const banner = h('img', { class: 'scene-art', alt: '', width: 640, height: 120 });
  const title = h('p', { class: 'scene-title', 'data-testid': 'campaign-title' });
  const place = h('h2', { class: 'scene-place', 'data-testid': 'scene-name' });
  const goal = h('p', { class: 'scene-goal', 'data-testid': 'objective' });
  const paused = h('span', { class: 'tag tag-host', hidden: true, role: 'status' }, t('table.paused'));
  root.append(banner, h('div', { class: 'scene-text' }, title, place, goal), paused);

  function render(state) {
    const view = publicState(state);
    if (!view) return;
    const tier = clamp(view.region_tier || 1, 1, 3);
    banner.src = assetUrl(`region_banner.tier${tier}`);
    title.textContent = view.campaign_title;
    place.textContent = view.scene ? view.scene.name : '';
    const text = objective(view);
    goal.textContent = text ? t('table.objective', { text }) : '';
    goal.hidden = !text;
    paused.hidden = !view.paused;
  }
  render(store.get());
  return store.subscribe(render);
}
