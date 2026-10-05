// Table view (M7.3): scene header, story feed, party, queue, dice tray, action box, vote prompt,
// dialogs and notices. Each component builds its DOM once and patches from the store / story.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { mountAction } from '../table/action.js';
import { mountConfirm, mountLevelUp, mountOffer } from '../table/dialogs.js';
import { mountDice } from '../table/dice.js';
import { mountFeed } from '../table/feed.js';
import { mountNotices } from '../table/notices.js';
import { mountParty } from '../table/party.js';
import { mountQueue } from '../table/queue.js';
import { mountScene } from '../table/scene.js';
import { mountVote } from '../table/vote.js';

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
  const dock = slot('div', 'tb-dock');
  const noticeSlot = slot('div', 'tb-notices');
  const dialogs = slot('div', 'tb-dialogs');
  const side = h('aside', { class: 'tb-side' }, party, queue, dice);
  const latest = h('span', { class: 'dice-latest muted', 'data-testid': 'dice-latest' });
  dice.append(h('summary', {}, t('table.dice'), ' ', latest));
  const diceBody = h('div', { class: 'dice-body' });
  dice.append(diceBody);
  root.append(h('div', { class: 'tb' }, scene, noticeSlot, feed, side, dock, dialogs));

  const stops = [
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
  ];
  return () => {
    stops.forEach((stop) => stop());
    document.body.classList.remove('is-table');
  };
}
