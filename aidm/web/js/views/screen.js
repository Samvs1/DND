// Spectator screen (/screen, SPEC 11): the shared display. Read-only: the story feed, the scene header,
// the party and, during a fight, the initiative strip and combat board. No hotbar, no action box, no seat.
// It says hello as a spectator (ws.js), so the server counts it and players' narration defaults to off;
// this view plays the narration (js/audio/narration.js) and the music (js/audio/music.js).
// Until the adventure starts it shows the invite panel (LAN address and QR code).
import { mountBoard } from '../combat/board.js';
import { mountInitiative } from '../combat/initiative.js';
import { t } from '../strings.js';
import { mountFeed } from '../table/feed.js';
import { mountParty } from '../table/party.js';
import { mountScene } from '../table/scene.js';
import { h } from '../ui/dom.js';
import { fetchLan, mountInvite } from '../ui/invite.js';

// The board only reads; this stands in for the interactive controller.
const WATCHER = { readOnly: true, ui: { arming: null, target: null }, subscribe: () => () => {}, pickToken() {}, pickZone() {} };

function applyPhase(state, waiting, table, combat) {
  const playing = state.snapshot?.state.phase === 'play' || state.snapshot?.state.phase === 'ended';
  waiting.hidden = playing;
  table.hidden = !playing;
  const fighting = Boolean(state.snapshot?.state.combat);
  combat.hidden = !fighting;
  document.body.classList.toggle('in-combat', fighting);
}

export function mountScreen(root, ctx) {
  const { store, story } = ctx;
  document.body.classList.add('is-table', 'is-screen');
  const slot = h('div', {});
  const waiting = h(
    'div',
    { class: 'sc-wait', 'data-testid': 'screen-waiting' },
    h('header', { class: 'masthead' }, h('h1', {}, t('app.title')), h('p', { class: 'tagline' }, t('screen.waiting'))),
    h('div', { class: 'lobby' }, slot),
  );
  const scene = h('header', { class: 'tb-scene' });
  const feed = h('section', { class: 'tb-feed', 'aria-label': t('table.feed') });
  const party = h('section', { class: 'tb-party panel', 'aria-label': t('table.party') });
  const side = h('aside', { class: 'tb-side' }, party);
  const initiative = h('div', { class: 'init-strip', 'data-testid': 'initiative' });
  const board = h('div', { class: 'board', 'data-testid': 'board' });
  const combat = h('section', { class: 'tb-combat panel', 'aria-label': t('combat.heading') }, initiative, board);
  const table = h('div', { class: 'tb sc', 'data-testid': 'screen-table' }, scene, combat, feed, side);
  root.append(waiting, table);

  const render = (state) => applyPhase(state, waiting, table, combat);
  render(store.get());
  const stops = [
    store.subscribe(render),
    mountInvite(slot, store),
    mountScene(scene, store),
    mountFeed(feed, story, ctx.audio),
    mountParty(party, store),
    mountInitiative(initiative, store),
    mountBoard(board, store, WATCHER),
  ];
  fetchLan(store);
  return () => {
    stops.forEach((stop) => stop());
    document.body.classList.remove('is-table', 'is-screen', 'in-combat');
  };
}
