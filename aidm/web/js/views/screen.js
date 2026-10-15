// Spectator screen (/screen, SPEC 11): the shared display. Read-only: the story feed, the scene header,
// the party and, during a fight, the initiative strip and combat board. No hotbar, no action box, no seat.
// It says hello as a spectator (ws.js), so the server counts it and players' narration defaults to off;
// this view plays the narration (js/audio/narration.js) and the music (js/audio/music.js).
// Until the adventure starts it shows the invite panel (LAN address and QR code); never during play.
import { mountBoard } from '../combat/board.js';
import { mountInitiative } from '../combat/initiative.js';
import { t } from '../strings.js';
import { mountGear } from '../screen/gear.js';
import { mountScreenDice } from '../screen/dice.js';
import { mountFloor } from '../screen/floor.js';
import { mountDefeat, mountLevelBanner } from '../screen/overlays.js';
import { mountScribeOverlay } from '../screen/scribe.js';
import { mountFightBanner, mountVictory } from '../screen/victory.js';
import { mountScreenVote } from '../screen/vote.js';
import { mountSettings } from '../settings/settings.js';
import { mountFeed } from '../table/feed.js';
import { mountNotices } from '../table/notices.js';
import { mountParty } from '../table/party.js';
import { mountScene } from '../table/scene.js';
import { h } from '../ui/dom.js';
import { fetchLan, mountInvite } from '../ui/invite.js';

function applyPhase(state, waiting, table, combat, tagline) {
  const writing = state.snapshot?.state.phase === 'generating'; // M18.1: the Scribe speaks over this wait
  const line = t(writing ? 'screen.writing' : 'screen.waiting');
  if (tagline.textContent !== line) tagline.textContent = line;
  const playing = ['play', 'ended', 'defeated'].includes(state.snapshot?.state.phase);
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
  const tagline = h('p', { class: 'tagline', 'data-testid': 'screen-tagline' }, t('screen.waiting'));
  const waiting = h(
    'div',
    { class: 'sc-wait', 'data-testid': 'screen-waiting' },
    h('header', { class: 'masthead' }, h('h1', {}, t('app.title')), tagline),
    h('div', { class: 'lobby' }, slot),
  );
  const scene = h('header', { class: 'tb-scene' });
  const feed = h('section', { class: 'tb-feed', 'aria-label': t('table.feed') });
  const party = h('section', { class: 'tb-party panel', 'aria-label': t('table.party') });
  const widgets = h('div', { class: 'sc-widgets' });
  const side = h('aside', { class: 'tb-side' }, party, widgets);
  const initiative = h('div', { class: 'init-strip', 'data-testid': 'initiative' });
  const board = h('div', { class: 'board', 'data-testid': 'board' });
  const combat = h('section', { class: 'tb-combat panel', 'aria-label': t('combat.heading') }, initiative, board);
  const table = h('div', { class: 'tb sc', 'data-testid': 'screen-table' }, scene, h('div', { class: 'sc-main' }, combat, feed), side);
  const overlays = h('div', { class: 'sc-overlays' });
  root.append(waiting, table, overlays);

  const render = (state) => applyPhase(state, waiting, table, combat, tagline);
  render(store.get());
  const stops = [
    store.subscribe(render),
    mountInvite(slot, store),
    mountFloor(widgets, store),
    mountScreenVote(widgets, store),
    mountNotices(widgets, store),
    mountScreenDice(widgets, ctx),
    mountLevelBanner(overlays, store),
    mountDefeat(overlays, store),
    mountVictory(overlays, store),
    mountFightBanner(overlays, store),
    mountScribeOverlay(overlays, ctx),
    mountGear(overlays, store),
    mountSettings(overlays, ctx),
    mountScene(scene, store),
    mountFeed(feed, story, ctx.audio, store),
    mountParty(party, store),
    mountInitiative(initiative, store),
    mountBoard(board, store),
  ];
  fetchLan(store);
  return () => {
    stops.forEach((stop) => stop());
    document.body.classList.remove('is-table', 'is-screen', 'in-combat');
  };
}
