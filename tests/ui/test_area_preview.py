"""M29.7d (R26): an aimed cone asks for a zone, and while an area spell is armed every zone chip
of the Move list says who it would catch (allies marked) or that the cone cannot reach it."""

from pathlib import Path

from playwright.sync_api import Browser

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import PHONE, snap

RENDER = """async () => {
  const { startCast } = await import('/web/js/combat/hotbar_magic.js');
  const { mountMoves } = await import('/web/js/controller/moves.js');
  const sent = [];
  const armed = [];
  const ctrl = {
    ui: { target: null, chances: {}, arming: null },
    send: (cmd) => sent.push(cmd),
    arm: (spec) => armed.push(spec),
    actor: () => 'hero',
    subscribe: () => () => {},
    pickZone: () => {},
  };
  const base = {
    level: 1, target_count: 1, count_per_slot: 0, target_kind: 'area', range_kind: 'self',
  };
  const me = { ctrl, me: 'hero' };
  startCast(me, { ...base, index: 'burning-hands', area_shape: 'cone', area_feet: 15 }, 1);
  startCast(me, { ...base, index: 'spirit-guardians', level: 3, area_feet: null }, 3);
  const token = (id, name, side, zone) => ({
    creature_id: id, name, side, zone_id: zone, hp: 9, max_hp: 9, conditions: [],
    dead: false, withdrawn: false, monster_index: side === 'hostile' ? 'cultist' : null,
  });
  const zone = (id, name) => ({
    id, name, cover: 'none', high_ground: false, difficult: false, surfaces: [],
  });
  const combat = {
    active_id: 'hero',
    zones: [
      zone('reeds', 'Cattail Bed'), zone('archway', 'Broken Archway'),
      zone('shack', "Fisher's Shack"),
    ],
    edges: [{ a: 'reeds', b: 'archway', feet: 25 }, { a: 'reeds', b: 'shack', feet: 15 }],
    tokens: [
      token('hero', 'Vex', 'party', 'reeds'), token('ally', 'Brienne', 'party', 'reeds'),
      token('foe', 'Cultist', 'hostile', 'shack'),
      token('foe2', 'Cultist B', 'hostile', 'archway'),
    ],
    economy: { action: true, bonus_action: true, movement_left: 30, dashed: false },
  };
  const state = {
    snapshot: { state: { combat } },
    players: [{ id: 'p1', creature_id: 'hero' }],
    me: { playerId: 'p1' },
  };
  const store = { get: () => state, subscribe: () => () => {} };
  ctrl.ui.arming = { steps: armed[0].steps, step: 0, picks: [[]] };
  const root = document.createElement('main');
  root.style.cssText = 'padding:12px;max-width:390px';
  document.body.replaceChildren(root);
  mountMoves(root, { store }, ctrl);
  const chips = [...root.querySelectorAll('[data-testid=zone-chip]')].map((c) => ({
    zone: c.dataset.zone,
    caught: c.querySelector('[data-testid=zone-caught]')?.textContent ?? null,
    ally: c.querySelector('[data-testid=zone-caught]')?.dataset.ally ?? null,
  }));
  return { sent, needs: armed.map((a) => a.steps[0].need), area: armed[0].steps[0].area, chips };
}"""


def test_m29_aimed_cone_shows_who_it_catches(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    page = browser.new_page(viewport=PHONE)
    page.goto(f"{live_server.base}/play")
    page.wait_for_selector("#join-name")
    out = page.evaluate(RENDER)
    assert out["needs"] == ["zone"]  # Burning Hands aims; Spirit Guardians casts at once
    assert [c["spell_id"] for c in out["sent"]] == ["spirit-guardians"]
    assert out["area"] == {"caster": "hero", "feet": 15}
    chips = {c["zone"]: c for c in out["chips"]}
    assert chips["reeds"]["caught"] == "Hits: Brienne (ally)" and chips["reeds"]["ally"] == "1"
    assert chips["shack"]["caught"] == "Hits: Cultist" and chips["shack"]["ally"] == "0"
    assert chips["archway"]["caught"] == "Out of reach"
    snap(page, shots_dir, "controller_area_preview", 390)
