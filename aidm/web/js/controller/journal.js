// The Journal tab: the journal and the map as two sub-tabs (store.jtab). Both are inline panels.
import { mountJournal } from '../journal/journal.js';
import { mountMap } from '../map/map.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

const SUBS = ['journal', 'map'];

export function mountJournalTab(root, ctx) {
  const { store } = ctx;
  const bar = h('div', { class: 'ct-subtabs', role: 'tablist', 'aria-label': t('ct.subtabs') });
  const buttons = SUBS.map((id) => h('button', { type: 'button', role: 'tab', class: 'ct-subtab', 'data-testid': `jtab-${id}`, onclick: () => store.update({ jtab: id }) }, t(`ct.sub_${id}`)));
  bar.append(...buttons);
  root.append(bar);
  const showing = (id) => (state) => state.ctab === 'journal' && (state.jtab ?? 'journal') === id;
  const render = (state) => buttons.forEach((b, i) => b.setAttribute('aria-selected', (state.jtab ?? 'journal') === SUBS[i] ? 'true' : 'false'));
  render(store.get());
  const stops = [store.subscribe(render), mountJournal(root, store, showing('journal')), mountMap(root, ctx, showing('map'))];
  return () => stops.forEach((stop) => stop());
}
