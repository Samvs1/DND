// Quest moments on the phones (M23.7): a short toast when a quest is taken on, a step is done, a quest is
// completed or left behind, a way is found, a lead appears or a keepsake is handed over. The moments are read
// from what changed between two snapshots, so the first snapshot (and a different campaign) only sets the baseline
// and routine events never toast. Only text the journal may show is used: a step shown here is already done.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { publicState } from '../table/lookup.js';

const SHOW_MS = 4500;

function doneSteps(quest) {
  return [...quest.steps_done, ...quest.routes.flatMap((r) => r.steps_done)];
}

function digest(view) {
  return {
    campaign: view.campaign_id,
    quests: new Map(view.quests.map((q) => [q.id, q])),
    leads: new Set(view.leads ?? []),
  };
}

/** The toast texts for the change from `before` to `after` (pure, so tests can call it). */
export function questMoments(before, after) {
  const out = [];
  for (const [id, quest] of after.quests) {
    const old = before.quests.get(id);
    const title = quest.title;
    if (!old || old.state !== quest.state) {
      if (quest.state === 'active' && (!old || old.state === 'offered')) out.push(t('ct.jQuestAccepted', { title }));
      else if (quest.state === 'completed') out.push(t('ct.jQuestDone', { title }));
      else if (quest.state === 'failed' && quest.closed_reason === 'left_behind') out.push(t('ct.jLeft', { title }));
    }
    if (!old) continue;
    const knownRoutes = new Set(old.routes.map((r) => r.id));
    for (const route of quest.routes.filter((r) => !knownRoutes.has(r.id))) out.push(t('ct.jRouteFound', { title, route: route.title }));
    const was = new Set(doneSteps(old));
    for (const step of doneSteps(quest).filter((s) => !was.has(s))) out.push(t('ct.jStepDone', { title, step }));
  }
  for (const text of after.leads) if (!before.leads.has(text)) out.push(t('ct.jLead', { text }));
  return out;
}

export function mountQuestToast(root, { store, story }) {
  const box = h('div', { class: 'ct-toast ct-quest-toast', hidden: true, role: 'status', 'aria-live': 'polite', 'data-testid': 'quest-toast' });
  root.append(box);
  const queue = [];
  let timer = null;
  let base = null;

  function next() {
    const text = queue.shift();
    if (!text) {
      box.hidden = true;
      timer = null;
      return;
    }
    box.textContent = text;
    box.hidden = false;
    timer = setTimeout(next, SHOW_MS);
  }

  function enqueue(texts) {
    queue.push(...texts);
    if (!timer && queue.length) next();
  }

  function onState(state) {
    const view = publicState(state);
    if (!view) return;
    const now = digest(view);
    if (base && base.campaign === now.campaign) enqueue(questMoments(base, now));
    base = now;
  }

  onState(store.get());
  const stops = [
    store.subscribe(onState),
    story.subscribe((change) => {
      if (change.type === 'item' && change.item.kind === 'event' && change.item.eventKind === 'keepsake_given') enqueue([t('ct.jGiven', { text: change.item.text })]);
    }),
  ];
  return () => {
    stops.forEach((stop) => stop());
    clearTimeout(timer);
  };
}
