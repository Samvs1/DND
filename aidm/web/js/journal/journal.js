// Journal panel: quests grouped by state (title, giver, objective), the public facts of the ledger and the
// scene summaries. Everything comes from the snapshot, which only carries what the public projection allows.
import { t } from '../strings.js';
import { createPanel } from '../ui/modal.js';
import { clear, h } from '../ui/dom.js';
import { publicState } from '../table/lookup.js';

const GROUPS = ['active', 'offered', 'completed', 'failed'];

function questCard(quest) {
  return h(
    'li',
    { class: `jr-quest state-${quest.state}`, 'data-testid': 'journal-quest', 'data-state': quest.state, 'data-quest': quest.id },
    h('div', { class: 'jr-quest-head' }, h('strong', {}, quest.title), h('span', { class: `tag jr-state ${quest.state}` }, t(`journal.state_${quest.state}`))),
    quest.giver ? h('p', { class: 'jr-giver hint' }, t('journal.giver', { name: quest.giver })) : null,
    quest.objective ? h('p', { class: 'jr-objective' }, t('journal.objective', { text: quest.objective })) : null,
  );
}

function questSection(quests) {
  if (!quests.length) return [h('h3', {}, t('journal.quests')), h('p', { class: 'hint', 'data-testid': 'journal-no-quests' }, t('journal.noQuests'))];
  const out = [h('h3', {}, t('journal.quests'))];
  for (const group of GROUPS) {
    const mine = quests.filter((q) => q.state === group);
    if (!mine.length) continue;
    out.push(h('h4', { class: 'jr-group' }, t(`journal.group_${group}`), ` (${mine.length})`), h('ul', { class: 'jr-list', 'data-testid': `journal-${group}` }, ...mine.map(questCard)));
  }
  return out;
}

function listSection(titleKey, emptyKey, testid, items) {
  return [
    h('h3', {}, t(titleKey)),
    items.length ? h('ul', { class: 'jr-list jr-plain', 'data-testid': testid }, ...items) : h('p', { class: 'hint' }, t(emptyKey)),
  ];
}

export function mountJournal(root, store) {
  const panel = createPanel(root, store, { key: 'journal', title: t('journal.title'), testid: 'journal' });
  let last = '';
  function render(state) {
    if (!panel.sync(state)) return;
    const view = publicState(state);
    const key = JSON.stringify([view?.quests, view?.facts, view?.summaries]);
    if (key === last) return;
    last = key;
    clear(panel.body);
    if (!view) return;
    const facts = view.facts.map((text) => h('li', { class: 'jr-fact' }, text));
    const scenes = (view.summaries ?? []).map((s) => h('li', { class: 'jr-scene' }, s.title ? h('strong', {}, `${s.title} `) : null, s.text));
    panel.body.append(...questSection(view.quests), ...listSection('journal.facts', 'journal.noFacts', 'journal-facts', facts), ...listSection('journal.scenes', 'journal.noScenes', 'journal-scenes', scenes));
  }
  render(store.get());
  const stop = store.subscribe(render);
  return () => {
    stop();
    panel.remove();
  };
}
