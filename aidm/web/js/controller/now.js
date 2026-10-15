// The Now card at the top of the Play tab (M18.2): one big line about what is going on for ME, with the place and
// the active main quest's objective under it. Never the story text: that is told on the shared screen.
// M20.2: outside a fight, a standing hero gets one "Help <name> up" button per downed ally (1 HP, `help_up`), and a
// downed hero's own line says what can raise them.
// M23.8: the What now? button sits beside the objective (controller/what_now.js).
import { combatOf, isLive, myCreatureId, tokenById } from '../combat/model.js';
import { myHero, playerName, publicState } from '../table/lookup.js';
import { mainObjective } from '../table/scene.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { everySecond } from '../ui/countdown.js';
import { statusOf } from './status.js';
import { whatNowButton } from './what_now.js';

/** True while a narration is still arriving (the screen is telling it). */
export function telling(story) {
  const last = story.items.findLast((item) => item.kind === 'narration');
  return Boolean(last && !last.done);
}

/** {key, text} for the Now card; key drives the colour (mine | acting | waiting | telling | down | ...). */
export function nowLine(state, story, now = Date.now()) {
  const view = publicState(state);
  if (!view) return { key: 'idle', text: t('ct.now_connecting') };
  if (view.paused) return { key: 'waiting', text: t('ct.now_paused') };
  const status = statusOf(state, now);
  if (status.key === 'down' && !combatOf(state) && !myHero(state)?.dead) return { key: 'down', text: t('ct.now_downHelp') };
  if (status.key === 'defeated' || status.key === 'down' || combatOf(state)) return status;
  if (telling(story)) return { key: 'telling', text: t('ct.now_telling') };
  const resolving = view.resolving;
  if (resolving && resolving.player_id !== state.me.playerId) {
    return { key: 'acting', text: t('ct.now_weighing', { name: playerName(state, resolving.player_id) }) };
  }
  if (resolving) return { key: 'mine', text: t('ct.now_yours') };
  if (status.key === 'mine' && status.text === t('ct.status_ready')) {
    return { key: 'mine', text: t('ct.now_move', { name: myHero(state)?.name ?? '' }) };
  }
  return status;
}

/** In a fight: how many turns until mine (0 = mine now), counting only creatures still in it; else null. */
export function turnsUntilMine(state) {
  const combat = combatOf(state);
  const me = myCreatureId(state);
  if (!combat || !me) return null;
  const order = combat.initiative.filter((id) => {
    const token = tokenById(combat, id);
    return token && isLive(token);
  });
  const at = order.indexOf(combat.active_id ?? combat.turn_of);
  const mine = order.indexOf(me);
  return at < 0 || mine < 0 ? null : (mine - at + order.length) % order.length;
}

function fightLine(state) {
  const combat = combatOf(state);
  const n = turnsUntilMine(state);
  const round = t('ct.now_round', { n: combat.round });
  if (!n) return round; // my turn now (the big line says so) or I am not in the order
  return `${round} - ${n === 1 ? t('ct.now_next') : t('ct.now_inTurns', { n })}`;
}

/** Allies I can help up right now: outside a fight, me standing, them alive at 0 HP. */
export function helpableAllies(state) {
  const view = publicState(state);
  const me = myHero(state);
  if (!view || combatOf(state) || !me || me.dead || me.hp <= 0) return [];
  return view.party.filter((p) => p.id !== me.id && !p.dead && p.hp <= 0);
}

function renderHelp(box, state, client) {
  const allies = helpableAllies(state);
  const key = allies.map((p) => p.id).join(',');
  if (box.dataset.key === key) return;
  box.dataset.key = key;
  box.hidden = !allies.length;
  box.replaceChildren(
    ...allies.map((p) => h('button', { type: 'button', class: 'btn btn-primary ct-help-up', 'data-testid': 'help-up', 'data-creature': p.id, onclick: () => client.send('help_up', { target_id: p.id }) }, t('ct.helpUp', { name: p.name }))),
  );
}

export function mountNow(root, { store, story, client }) {
  const line = h('p', { class: 'ct-now-line', role: 'status', 'aria-live': 'polite', 'data-testid': 'now-line' });
  const place = h('p', { class: 'ct-now-place', 'data-testid': 'now-place' });
  const goal = h('p', { class: 'ct-now-goal', 'data-testid': 'now-goal' });
  const help = h('div', { class: 'ct-help', hidden: true, 'data-testid': 'help-up-list' });
  const row = h('div', { class: 'ct-now-row' }, goal, whatNowButton(client));
  const card = h('section', { class: 'ct-now', 'data-testid': 'now-card' }, line, place, row, help);
  root.append(card);

  function render(state) {
    const now = nowLine(state, story);
    if (line.textContent !== now.text) line.textContent = now.text;
    card.dataset.status = now.key;
    const view = publicState(state);
    const fighting = Boolean(combatOf(state));
    place.textContent = fighting ? fightLine(state) : view?.scene?.name ?? '';
    place.hidden = !place.textContent;
    const objective = mainObjective(view);
    goal.textContent = objective;
    goal.hidden = fighting || !objective;
    renderHelp(help, state, client);
  }
  render(store.get());
  const stops = [store.subscribe(render), story.subscribe(() => render(store.get())), everySecond(store, render)];
  return () => stops.forEach((stop) => stop());
}
