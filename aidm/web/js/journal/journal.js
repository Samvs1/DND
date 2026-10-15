// Journal panel (M23.7): the main quest pinned with the ways found so far, then quests grouped Active / Offered /
// Leads / Completed / Left behind and failed, then the public facts and the scene summaries. The journal shows what
// has been DONE (ticked steps and a short log), never what to do next: the server only sends done steps.
import { t } from '../strings.js';
import { createPanel } from '../ui/modal.js';
import { clear, h } from '../ui/dom.js';
import { publicState } from '../table/lookup.js';

const LOG_SHOWN = 3;

function ticks(texts, testid) {
  if (!texts.length) return null;
  return h('ul', { class: 'jr-steps', 'data-testid': testid }, ...texts.map((text) => h('li', { class: 'jr-step' }, text)));
}

function logLines(log) {
  if (!log.length) return null;
  const line = (text) => h('li', { class: 'jr-log-line' }, text);
  const rest = log.slice(0, -LOG_SHOWN);
  const recent = log.slice(-LOG_SHOWN);
  return h(
    'div',
    { class: 'jr-log hint', 'data-testid': 'journal-log' },
    rest.length ? h('details', {}, h('summary', {}, t('journal.logShow', { n: log.length })), h('ul', {}, ...rest.map(line))) : null,
    h('ul', {}, ...recent.map(line)),
  );
}

function stateOf(quest) {
  if (quest.state === 'failed') return quest.closed_reason === 'withdrawn' ? 'withdrawn' : quest.closed_reason ? 'left' : 'failed';
  return quest.state;
}

function questCard(quest) {
  const tag = quest.kind === 'favour' && quest.state !== 'completed' ? t('journal.kind_favour') : t(`journal.state_${stateOf(quest)}`);
  return h(
    'li',
    { class: `jr-quest state-${quest.state}`, 'data-testid': 'journal-quest', 'data-state': quest.state, 'data-quest': quest.id },
    h('div', { class: 'jr-quest-head' }, h('strong', {}, quest.title), h('span', { class: `tag jr-state ${quest.state}` }, tag)),
    quest.giver ? h('p', { class: 'jr-giver hint' }, t('journal.giver', { name: quest.giver })) : null,
    quest.objective ? h('p', { class: 'jr-objective' }, t('journal.objective', { text: quest.objective })) : null,
    ticks(quest.steps_done, 'journal-steps'),
    logLines(quest.log),
  );
}

function routeCard(route) {
  return h(
    'li',
    { class: `jr-route kind-${route.kind}${route.done ? ' done' : ''}`, 'data-testid': 'journal-route', 'data-route': route.id },
    h('div', { class: 'jr-route-head' }, h('strong', {}, route.title || t(`journal.routeKind_${route.kind}`)), route.title ? h('span', { class: 'tag' }, t(`journal.routeKind_${route.kind}`)) : null, route.done ? h('span', { class: 'tag jr-state completed' }, t('journal.routeDone')) : null),
    ticks(route.steps_done, 'journal-route-steps'),
  );
}

function mainCard(quest) {
  return h(
    'section',
    { class: 'jr-main', 'data-testid': 'journal-main', 'data-quest': quest.id },
    h('p', { class: 'jr-main-label' }, t('journal.mainLabel')),
    h('h4', { class: 'jr-main-title' }, quest.title),
    quest.objective ? h('p', { class: 'jr-objective' }, t('journal.objective', { text: quest.objective })) : null,
    quest.routes.length ? h('ul', { class: 'jr-list jr-routes' }, ...quest.routes.map(routeCard)) : null,
    logLines(quest.log),
  );
}

function group(key, items, testid) {
  return [h('h4', { class: 'jr-group' }, t(`journal.group_${key}`), ` (${items.length})`), h('ul', { class: 'jr-list', 'data-testid': testid }, ...items)];
}

function leftGroup(quests, ui) {
  const box = h('details', { class: 'jr-left', 'data-testid': 'journal-left', open: ui.leftOpen }, h('summary', { class: 'jr-group' }, t('journal.group_left'), ` (${quests.length})`), h('ul', { class: 'jr-list' }, ...quests.map(questCard)));
  box.addEventListener('toggle', () => (ui.leftOpen = box.open));
  return [box];
}

function questSection(view, ui) {
  const quests = view.quests ?? [];
  const leads = view.leads ?? [];
  const out = [h('h3', {}, t('journal.quests'))];
  if (!quests.length && !leads.length) return [...out, h('p', { class: 'hint', 'data-testid': 'journal-no-quests' }, t('journal.noQuests'))];
  const main = quests.find((q) => q.kind === 'main' && q.state === 'active');
  if (main) out.push(mainCard(main));
  const rest = quests.filter((q) => q !== main);
  const active = rest.filter((q) => q.state === 'active');
  const offered = rest.filter((q) => q.state === 'offered');
  const done = rest.filter((q) => q.state === 'completed');
  const left = rest.filter((q) => q.state === 'failed');
  if (active.length) out.push(...group('active', active.map(questCard), 'journal-active'));
  if (offered.length) out.push(...group('offered', offered.map(questCard), 'journal-offered'));
  if (leads.length) out.push(...group('leads', leads.map((text) => h('li', { class: 'jr-lead' }, text)), 'journal-leads'));
  if (done.length) out.push(...group('completed', done.map(questCard), 'journal-completed'));
  if (left.length) out.push(...leftGroup(left, ui));
  return out;
}

function listSection(titleKey, emptyKey, testid, items) {
  return [
    h('h3', {}, t(titleKey)),
    items.length ? h('ul', { class: 'jr-list jr-plain', 'data-testid': testid }, ...items) : h('p', { class: 'hint' }, t(emptyKey)),
  ];
}

export function mountJournal(root, store, embed = null) {
  const panel = createPanel(root, store, { key: 'journal', title: t('journal.title'), testid: 'journal', embed });
  const ui = { leftOpen: false };
  let last = '';
  function render(state) {
    if (!panel.sync(state)) return;
    const view = publicState(state);
    const key = JSON.stringify([view?.quests, view?.leads, view?.facts, view?.summaries]);
    if (key === last) return;
    last = key;
    clear(panel.body);
    if (!view) return;
    const facts = view.facts.map((text) => h('li', { class: 'jr-fact' }, text));
    const scenes = (view.summaries ?? []).map((s) => h('li', { class: 'jr-scene' }, s.title ? h('strong', {}, `${s.title} `) : null, s.text));
    panel.body.append(...questSection(view, ui), ...listSection('journal.facts', 'journal.noFacts', 'journal-facts', facts), ...listSection('journal.scenes', 'journal.noScenes', 'journal-scenes', scenes));
  }
  render(store.get());
  const stop = store.subscribe(render);
  return () => {
    stop();
    panel.remove();
  };
}
