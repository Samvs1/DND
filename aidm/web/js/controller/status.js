// What the phone's status chip says: whose turn it is, in a fight or at the free-for-all floor.
import { combatOf, isMyTurn, tokenById } from '../combat/model.js';
import { myHero, publicState } from '../table/lookup.js';
import { t } from '../strings.js';

export function isDown(state) {
  const hero = myHero(state);
  return Boolean(hero && (hero.dead || hero.dying || hero.hp <= 0));
}

/** My 1-based place in the action queue, or 0. */
export function queuePosition(state) {
  const seat = (publicState(state)?.floor?.queue ?? []).find((s) => s.player_id === state.me.playerId);
  return seat?.position ?? 0;
}

/** {key, text}: key is one of mine | acting | waiting | down | defeated | idle. */
export function statusOf(state) {
  const view = publicState(state);
  if (!view) return { key: 'idle', text: t('ct.status_waiting') };
  if (view.phase === 'defeated') return { key: 'defeated', text: t('ct.status_defeated') };
  if (isDown(state)) return { key: 'down', text: t('ct.status_down') };
  const combat = combatOf(state);
  if (combat) {
    if (isMyTurn(state)) return { key: 'mine', text: t('ct.status_yourTurn') };
    const who = tokenById(combat, combat.active_id)?.name ?? '';
    return { key: 'acting', text: t('ct.status_acting', { name: who }) };
  }
  const holder = view.floor?.holder ?? null;
  if (holder) {
    if (holder.player_id === state.me.playerId) return { key: 'mine', text: t('ct.status_mine') };
    const queued = queuePosition(state);
    if (queued) return { key: 'waiting', text: t('ct.status_queued', { n: queued }) };
    return { key: 'acting', text: t('ct.status_acting', { name: holder.hero_name || holder.name }) };
  }
  const place = queuePosition(state);
  if (place) return { key: 'waiting', text: t('ct.status_queued', { n: place }) };
  // Outside a fight nobody has a turn: the floor is free and everyone may act.
  return { key: 'mine', text: t('ct.status_ready') };
}
