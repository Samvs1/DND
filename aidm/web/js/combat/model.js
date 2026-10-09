// Pure helpers over the public combat view (no DOM): who is who, movement cost, coarse enemy health.
import { mySeat } from '../state.js';

export function combatOf(state) {
  return state.snapshot?.state.combat ?? null;
}

export function tokenById(combat, id) {
  return combat?.tokens.find((tk) => tk.creature_id === id) ?? null;
}

export function myCreatureId(state) {
  return mySeat(state)?.creature_id ?? null;
}

/** True when the fight is on and the active creature is the local player's hero. */
export function isMyTurn(state) {
  const combat = combatOf(state);
  const me = myCreatureId(state);
  return Boolean(combat && me && combat.active_id === me);
}

export function isEnemy(token) {
  return token.side === 'hostile';
}

export function isLive(token) {
  return !token.dead && !token.withdrawn;
}

/** Monsters show a coarse state, never numbers: healthy, wounded (half or less), bloodied (a quarter or less). */
export function healthState(token) {
  if (token.dead) return 'fallen';
  const ratio = token.max_hp > 0 ? token.hp / token.max_hp : 0;
  if (ratio <= 0.25) return 'bloodied';
  if (ratio <= 0.5) return 'wounded';
  return 'healthy';
}

export function neighbours(combat, zoneId) {
  const out = [];
  for (const edge of combat.edges) {
    if (edge.a === zoneId) out.push({ id: edge.b, feet: edge.feet });
    else if (edge.b === zoneId) out.push({ id: edge.a, feet: edge.feet });
  }
  return out;
}

/** True when entering the zone costs double (terrain or a difficult surface; `rough` is the server's effective flag). */
export function isRough(zone) {
  return Boolean(zone?.rough ?? zone?.difficult);
}

/** Feet to walk from one zone to another (cheapest route; entering a difficult zone costs double), or null. */
export function moveCost(combat, fromId, toId) {
  if (fromId === toId) return 0;
  const zones = new Map(combat.zones.map((z) => [z.id, z]));
  const best = new Map([[fromId, 0]]);
  const open = [fromId];
  while (open.length) {
    open.sort((a, b) => best.get(a) - best.get(b));
    const here = open.shift();
    for (const next of neighbours(combat, here)) {
      const factor = isRough(zones.get(next.id)) ? 2 : 1;
      const cost = best.get(here) + next.feet * factor;
      if (!best.has(next.id) || cost < best.get(next.id)) {
        best.set(next.id, cost);
        open.push(next.id);
      }
    }
  }
  return best.has(toId) ? best.get(toId) : null;
}

/** Zones in rows by distance from `startId` (breadth first), so the board reads like a small map. */
export function zoneRows(combat, startId) {
  const seen = new Set([startId]);
  const rows = [[startId]];
  for (let row = 0; row < rows.length; row += 1) {
    const next = [];
    for (const id of rows[row]) {
      for (const n of neighbours(combat, id)) {
        if (!seen.has(n.id)) {
          seen.add(n.id);
          next.push(n.id);
        }
      }
    }
    if (next.length) rows.push(next);
  }
  const rest = combat.zones.map((z) => z.id).filter((id) => !seen.has(id));
  if (rest.length) rows.push(rest);
  return rows;
}

/** A string that changes whenever a hit-chance preview could change. */
export function previewKey(combat) {
  return JSON.stringify([
    combat.round,
    combat.active_id,
    combat.tokens.map((tk) => [tk.creature_id, tk.zone_id, tk.conditions, tk.dead]),
    combat.zones.map((z) => [z.id, z.surfaces.map((s) => s.kind)]),
  ]);
}

export function percent(p) {
  return `${Math.round(p * 100)}%`;
}
