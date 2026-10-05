// Table view (M7.3): scene header, story feed, party, queue, dice tray, action box, vote prompt,
// dialogs and notices. Each component builds its DOM once and patches from the store / story.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { mountBoard } from '../combat/board.js';
import { createController } from '../combat/controller.js';
import { mountHotbar } from '../combat/hotbar.js';
import { mountInitiative } from '../combat/initiative.js';
import { mountSheet } from '../sheet/drawer.js';
import { mountLevelUp } from '../sheet/levelup.js';
import { mountSheetSync } from '../sheet/sync.js';
import { mountAction } from '../table/action.js';
import { mountConfirm, mountOffer } from '../table/dialogs.js';
import { mountDice } from '../table/dice.js';
import { mountFeed } from '../table/feed.js';
import { mountNotices } from '../table/notices.js';
import { mountParty } from '../table/party.js';
import { mountQueue } from '../table/queue.js';
import { mountScene } from '../table/scene.js';
import { mountVote } from '../table/vote.js';

function showWhileFighting(node, store) {
  const apply = (state) => {
    const fighting = Boolean(state.snapshot?.state.combat);
    node.hidden = !fighting;
    document.body.classList.toggle('in-combat', fighting);
  };
  apply(store.get());
  const stop = store.subscribe(apply);
  return () => {
    stop();
    document.body.classList.remove('in-combat');
  };
}

export function mountTable(root, ctx) {
  const { store, story } = ctx;
  document.body.classList.add('is-table');
  const slot = (tag, cls, label) => h(tag, { class: cls, 'aria-label': label || null });
  const scene = slot('header', 'tb-scene');
  const feed = slot('section', 'tb-feed', t('table.feed'));
  const party = slot('section', 'tb-party panel', t('table.party'));
  const queue = slot('section', 'tb-queue panel', t('table.queue'));
  const dice = slot('details', 'tb-dice panel', t('table.dice'));
  dice.open = window.matchMedia('(min-width: 900px)').matches;
  const combat = slot('section', 'tb-combat panel', t('combat.heading'));
  const initiative = h('div', { class: 'init-strip', 'data-testid': 'initiative' });
  const board = h('div', { class: 'board', 'data-testid': 'board' });
  combat.append(initiative, board);
  combat.hidden = true;
  const hotbar = h('div', { class: 'hotbar', 'data-testid': 'hotbar', role: 'region', 'aria-label': t('hotbar.label') });
  const dock = slot('div', 'tb-dock');
  dock.append(hotbar);
  const noticeSlot = slot('div', 'tb-notices');
  const dialogs = slot('div', 'tb-dialogs');
  const side = h('aside', { class: 'tb-side' }, party, queue, dice);
  const latest = h('span', { class: 'dice-latest muted', 'data-testid': 'dice-latest' });
  dice.append(h('summary', {}, t('table.dice'), ' ', latest));
  const diceBody = h('div', { class: 'dice-body' });
  dice.append(diceBody);
  root.append(h('div', { class: 'tb' }, scene, noticeSlot, combat, feed, side, dock, dialogs));
  const ctrl = createController(ctx);

  const stops = [
    () => ctrl.stop(),
    mountSheetSync(ctx),
    mountInitiative(initiative, store),
    mountBoard(board, store, ctrl),
    mountHotbar(hotbar, ctx, ctrl),
    showWhileFighting(combat, store),
    mountScene(scene, store),
    mountNotices(noticeSlot, store),
    mountFeed(feed, story),
    mountParty(party, store),
    mountQueue(queue, store),
    mountDice(diceBody, { ...ctx, latest }),
    mountVote(dock, ctx),
    mountLevelUp(dock, ctx),
    mountAction(dock, ctx),
    mountConfirm(dialogs, ctx),
    mountOffer(dialogs, ctx),
    mountSheet(dialogs, ctx),
  ];
  return () => {
    stops.forEach((stop) => stop());
    document.body.classList.remove('is-table');
  };
}
