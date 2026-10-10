// The Journal tab: the journal, the map and the story as three sub-tabs (store.jtab). All are inline panels.
// Story (M18.2) is the recent story in full, for a player who missed a line on the screen.
import { mountJournal } from '../journal/journal.js';
import { mountMap } from '../map/map.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { mountLastLine } from './lastline.js';

const SUBS = ['journal', 'map', 'story'];

export function mountJournalTab(root, ctx) {
  const { store } = ctx;
  const bar = h('div', { class: 'ct-subtabs', role: 'tablist', 'aria-label': t('ct.subtabs') });
  const buttons = SUBS.map((id) => h('button', { type: 'button', role: 'tab', class: 'ct-subtab', 'data-testid': `jtab-${id}`, onclick: () => store.update({ jtab: id }) }, t(`ct.sub_${id}`)));
  bar.append(...buttons);
  const story = h('div', { class: 'ct-story', 'data-testid': 'story-panel' });
  root.append(bar, story);
  const showing = (id) => (state) => state.ctab === 'journal' && (state.jtab ?? 'journal') === id;
  const render = (state) => {
    buttons.forEach((b, i) => b.setAttribute('aria-selected', (state.jtab ?? 'journal') === SUBS[i] ? 'true' : 'false'));
    const opening = story.hidden && showing('story')(state);
    story.hidden = !showing('story')(state);
    const box = story.firstElementChild;
    if (opening && box) box.scrollTop = box.scrollHeight; // open on the newest line
  };
  render(store.get());
  const stops = [store.subscribe(render), mountJournal(root, store, showing('journal')), mountMap(root, ctx, showing('map')), mountLastLine(story, ctx)];
  return () => stops.forEach((stop) => stop());
}
