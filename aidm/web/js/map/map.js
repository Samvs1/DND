// Map panel: the act/region banner (assetUrl), the fogged region graph, and a Travel button per neighbour of the
// current place. Travel sends the same text action a player could type, which opens the table's travel vote.
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { createPanel } from '../ui/modal.js';
import { clear, h } from '../ui/dom.js';
import { clamp } from '../ui/format.js';
import { publicState } from '../table/lookup.js';
import { buildGraph } from './graph.js';

function travelList(view, client, store) {
  const exits = view.scene?.exits ?? [];
  if (!exits.length) return [h('p', { class: 'hint' }, t('map.noExits'))];
  const fighting = Boolean(view.combat);
  const rows = exits.map((exit) => {
    const go = () => {
      client.send('submit_action', { text: `go to ${exit.name}` });
      store.update({ panel: null });
    };
    const label = exit.locked ? t('map.travelLocked', { name: exit.name }) : t('map.travel', { name: exit.name });
    const button = h('button', { type: 'button', class: 'btn btn-small', disabled: exit.locked || fighting, 'data-testid': 'map-travel', 'data-node': exit.node_id, onclick: go }, label);
    return h('li', { class: `map-exit${exit.locked ? ' locked' : ''}` }, button);
  });
  return [h('ul', { class: 'map-travel-list' }, ...rows), h('p', { class: 'hint' }, fighting ? t('map.inFight') : t('map.travelHint'))];
}

export function mountMap(root, { store, client }) {
  const panel = createPanel(root, store, { key: 'map', title: t('map.title'), testid: 'map' });
  let last = '';
  function render(state) {
    if (!panel.sync(state)) return;
    const view = publicState(state);
    const key = JSON.stringify([view?.map, view?.scene?.exits, view?.region_tier, Boolean(view?.combat), view?.campaign_title]);
    if (key === last) return;
    last = key;
    clear(panel.body);
    if (!view?.map) {
      panel.body.append(h('p', { class: 'hint' }, t('map.empty')));
      return;
    }
    const tier = clamp(view.region_tier || 1, 1, 3);
    const labels = new Map((view.scene?.exits ?? []).map((e) => [e.node_id, e.name]));
    const banner = h(
      'div',
      { class: 'map-banner', 'data-testid': 'map-banner' },
      h('img', { src: assetUrl(`region_banner.tier${tier}`), alt: '', width: 640, height: 120 }),
      h('p', { class: 'map-region' }, h('strong', {}, t('map.region', { tier })), ' ', view.campaign_title),
    );
    panel.body.append(banner, h('div', { class: 'map-wrap' }, buildGraph(view.map, labels)), h('h3', {}, t('map.travelHeading')), ...travelList(view, client, store));
  }
  render(store.get());
  const stop = store.subscribe(render);
  return () => {
    stop();
    panel.remove();
  };
}
