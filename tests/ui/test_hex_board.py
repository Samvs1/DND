"""M21 hex battle map on the shared screen (owner: "hexagonal grids that fit into each other so it's
clear which zone is next to which one", with icons for cover, rough ground and the like): linked
zones are touching hexes, the map and its tokens fit the screen, and each zone shows its marks."""

from pathlib import Path

from playwright.sync_api import Browser, Page, ViewportSize

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import HD, snap, start_fight

LAPTOP = ViewportSize(width=1280, height=800)
NO_SCROLL = "document.documentElement.scrollHeight <= innerHeight + 1"
INSIDE = """(sel) => [...document.querySelectorAll(sel)].every((el) => {
  const r = el.getBoundingClientRect();
  return r.left >= -1 && r.top >= -1 && r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1;
})"""
# Centre distance of every pair of hexes, in hex widths, with whether the zones are linked.
PAIRS = """() => {
  const c = window.aidm.store.get().snapshot.state.combat;
  const linked = new Set(c.edges.map((e) => [e.a, e.b].sort().join('|')));
  const hexes = [...document.querySelectorAll('[data-testid=zone]')].map((el) => {
    const r = el.getBoundingClientRect();
    return { id: el.dataset.zone, x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width };
  });
  const out = [];
  hexes.forEach((a, i) => hexes.slice(i + 1).forEach((b) => out.push({
    linked: linked.has([a.id, b.id].sort().join('|')),
    gap: Math.hypot(a.x - b.x, a.y - b.y) / a.w,
  })));
  return out;
}"""
# Six crypt zones in two rows with every kind of mark; heroes in the first, goblins in the third.
SIX = """() => {
  const c = window.aidm.store.get().snapshot.state.combat;
  const spots = [
    [0, 0, 'sarcophagi', 'Sarcophagus Row', {cover: 'half'}],
    [1, 0, 'dais', 'Raised Dais', {high_ground: true, rough: true}],
    [2, 0, 'ossuary', 'Bone-Lined Ossuary', {surfaces: [
      {kind: 'grease', rounds_left: 2},
      {kind: 'fire', rounds_left: 1}
    ]}],
    [-1, 1, 'collapsed_vault', 'Collapsed Vault', {cover: 'three_quarters'}],
    [0, 1, 'corridor', 'Burial Corridor', {surfaces: [{kind: 'web', rounds_left: null}]}],
    [1, 1, 'flooded_cell', 'Flooded Cell', {}],
  ];
  const plain = {cover: 'none', high_ground: false, rough: false, difficult: false, surfaces: []};
  const zones = spots.map(([q, r, id, name, extra]) => ({
    ...c.zones[0], ...plain, id, name, q, r, terrain: 'crypt', ...extra,
    distance_label: 'about 20 ft across',
  }));
  const steps = [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]];
  const near = (a, b) => steps.some(([dq, dr]) => b.q - a.q === dq && b.r - a.r === dr);
  const edges = [];
  zones.forEach((a, i) => zones.slice(i + 1).forEach((b) => {
    if (near(a, b)) edges.push({ a: a.id, b: b.id, feet: 25 });
  }));
  const zoneOf = (tk) => (tk.side === 'party' ? 'sarcophagi' : 'ossuary');
  const tokens = c.tokens.map((tk) => ({ ...tk, zone_id: zoneOf(tk) }));
  window.aidm.dispatch({ type: 'combat_state', combat: { ...c, zones, edges, tokens } });
}"""


def _check_map(screen: Page) -> None:
    pairs = screen.evaluate(PAIRS)
    assert pairs, "at least two zones"
    for pair in pairs:
        if pair["linked"]:
            assert 0.9 < pair["gap"] < 1.1, pair  # linked zones touch: one hex width apart
        else:
            assert pair["gap"] > 1.5, pair  # unlinked zones never touch
    assert screen.evaluate(NO_SCROLL)
    assert screen.evaluate(INSIDE, "[data-testid=zone]")
    assert screen.evaluate(INSIDE, "[data-testid=token]")


def test_screen_draws_the_fight_as_touching_hexes(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, _host, _guest = start_fight(browser, combat_server.base, errors, screen_size=HD)
    screen.wait_for_selector("[data-testid=token][data-side=hostile]")
    _check_map(screen)
    legend = screen.inner_text("[data-testid=hex-legend]")
    assert "Touching zones are" in legend and "ft apart" in legend
    snap(screen, shots_dir, "m21_hex_fight", 1920)
    screen.set_viewport_size(LAPTOP)
    _check_map(screen)
    snap(screen, shots_dir, "m21_hex_fight", 1280)
    assert errors == []


def test_six_zones_with_every_mark_fit_and_read(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, _host, _guest = start_fight(browser, combat_server.base, errors, screen_size=HD)
    # A hero's turn: the server is idle, so no live combat_state replaces the drawn map.
    screen.wait_for_selector("[data-testid=init-entry].ally.current", timeout=30000)
    screen.evaluate(SIX)
    screen.wait_for_function("document.querySelectorAll('[data-testid=zone]').length === 6")
    _check_map(screen)
    marks = screen.locator("[data-testid=zone][data-zone=ossuary] [data-testid=hex-mark]")
    assert marks.all_inner_texts() == ["Grease (2)", "Fire (1)"]
    hill = screen.locator("[data-testid=zone][data-zone=dais] [data-testid=hex-mark]")
    assert hill.all_inner_texts() == ["High ground", "Rough ground"]
    legend = screen.locator("[data-testid=hex-legend] [data-testid=hex-mark]").all_inner_texts()
    assert "Half cover" in legend and "Three-quarters cover" in legend and "Web" in legend
    snap(screen, shots_dir, "m21_hex_six", 1920)
    screen.set_viewport_size(LAPTOP)
    _check_map(screen)
    snap(screen, shots_dir, "m21_hex_six", 1280)
    assert errors == []
