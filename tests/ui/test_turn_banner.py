"""Turns the table can follow, in the browser (M20.3, owner playtest 3: "it is not always clear
whose turn it is"): the screen names whose turn it is (monsters too, held for the AI-turn pause)
and the phone that ends its turn loses the hotbar at once. FakeLLM server; no network."""

from pathlib import Path

from playwright.sync_api import Browser, Page

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import MAIN, split_turn, start_fight

BANNER = "[data-testid=turn-banner]"
WATCH = """() => {
  window.__turns = [];
  window.aidm.store.on('combat_state', (m) => {
    if (m.combat) window.__turns.push(m.combat.turn_of);
  });
}"""
GOBLIN_SEEN = "window.__turns.some((id) => id && id.startsWith('goblin'))"
HELD = """() => {
  const c = window.aidm.store.get().snapshot.state.combat;
  const gob = c.tokens.find((tk) => tk.creature_id.startsWith('goblin') && !tk.dead);
  const held = { ...c, active_id: null, economy: null, turn_of: gob.creature_id };
  window.aidm.dispatch({ type: 'combat_state', combat: held });
  return gob.name;
}"""


def _hero_turn(host: Page, guest: Page) -> Page | None:
    for page in (host, guest):
        if page.locator(MAIN).count():
            return page
    return None


def test_screen_names_every_turn_and_the_phone_flips_on_end_turn(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, guest = start_fight(browser, combat_server.base, errors)
    active, _other = split_turn(host, guest)
    name = active.evaluate(
        "(() => { const s = window.aidm.store.get(); const c = s.snapshot.state.combat;"
        " return c.tokens.find((tk) => tk.creature_id === c.active_id).name; })()"
    )
    screen.wait_for_function(
        f"document.querySelector('{BANNER}').textContent === \"It is {name}'s turn\"", timeout=20000
    )
    screen.evaluate(WATCH)
    for _ in range(4):  # end hero turns until a goblin has had one
        ending = _hero_turn(host, guest)
        if ending is None:
            host.wait_for_timeout(300)
            continue
        ending.click("[data-testid=end-turn]")
        ending.wait_for_selector(MAIN, state="detached", timeout=3000)  # flips at once
        if screen.evaluate(GOBLIN_SEEN):
            break
        host.wait_for_timeout(1500)
        if screen.evaluate(GOBLIN_SEEN):
            break
    assert screen.evaluate(GOBLIN_SEEN), "the screen never got a goblin's turn"
    split_turn(host, guest)  # a hero's turn again: no more combat_state until they act
    goblin = screen.evaluate(HELD)  # a held goblin turn: the banner names it
    assert screen.inner_text(BANNER) == f"It is {goblin}'s turn"
    assert screen.locator(".init.current", has_text=goblin).count() >= 1
    screen.screenshot(path=str(shots_dir / "screen_goblin_turn_1280.png"))
    assert errors == []
