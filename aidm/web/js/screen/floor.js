// Floor widget: who is acting, who is typing and the numbered queue, from snapshot.state.floor.
// Hidden when nothing is going on.
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { publicState } from '../table/lookup.js';

const label = (seat) => (seat.hero_name ? `${seat.name} (${seat.hero_name})` : seat.name);

export function mountFloor(root, store) {
  const box = h('section', { class: 'sc-floor panel', hidden: true, 'aria-live': 'polite', 'data-testid': 'screen-floor' });
  root.append(box);
  function render(state) {
    const floor = publicState(state)?.floor;
    clear(box);
    const holder = floor?.holder ?? null;
    const typing = (floor?.typing ?? []).filter((s) => s.player_id !== holder?.player_id);
    const queue = floor?.queue ?? [];
    box.hidden = !holder && typing.length === 0 && queue.length === 0;
    if (box.hidden) return;
    if (holder) box.append(h('p', { class: 'sc-acting', 'data-testid': 'floor-acting' }, t('screen.acting', { name: holder.hero_name || holder.name })));
    typing.forEach((s) => box.append(h('p', { class: 'sc-typing', 'data-testid': 'floor-typing' }, t('screen.typing', { name: s.hero_name || s.name }))));
    if (queue.length) {
      box.append(
        h('p', { class: 'hint' }, t('screen.next')),
        h('ol', { class: 'sc-queue', 'data-testid': 'floor-queue' }, ...queue.map((s) => h('li', {}, label(s)))),
      );
    }
  }
  render(store.get());
  return store.subscribe(render);
}
