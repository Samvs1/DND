// Read-only lookups over the latest snapshot: who is who, which hero is mine, what is pending.
import { mySeat } from '../state.js';

export function publicState(state) {
  return state.snapshot?.state ?? null;
}

export function myHero(state) {
  const seat = mySeat(state);
  return publicState(state)?.party.find((c) => c.id === seat?.creature_id) ?? null;
}

export function playerName(state, playerId) {
  return state.players.find((p) => p.id === playerId)?.name ?? '';
}

export function creatureName(state, creatureId) {
  const view = publicState(state);
  const hero = view?.party.find((c) => c.id === creatureId);
  if (hero) return hero.name;
  return view?.combat?.tokens.find((tk) => tk.creature_id === creatureId)?.name ?? '';
}

/** True while a queued or resolving action belongs to the local player. */
export function hasPendingAction(state) {
  const view = publicState(state);
  if (!view) return false;
  const me = state.me.playerId;
  return view.queue.some((e) => e.player_id === me) || view.resolving?.player_id === me;
}
