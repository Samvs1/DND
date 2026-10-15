"""M22.1 (owner request 2026-10-15): the words a player types show on the shared screen with who
typed them (the hero's portrait, the player's name and the hero's name) before the telling, stay
there after a reload, and read as Name (Hero): "..." in the phone's Journal > Story."""

from pathlib import Path

from playwright.sync_api import Browser

from tests.ui.conftest import LiveServer, dismiss_gate
from tests.ui.table_helpers import HD, PHONE, WIDE, go_tab, snap, start_with_screen

CABIN = "I look inside the cabin"
CARD = "[data-testid=player-action]"
TOLD_AFTER = """(text) => {
  const card = [...document.querySelectorAll('[data-testid=player-action]')]
    .find((c) => c.querySelector('[data-testid=player-action-text]').textContent === text);
  return Boolean(card) && [...document.querySelectorAll('[data-testid=narration]')].some(
    (n) => (card.compareDocumentPosition(n) & Node.DOCUMENT_POSITION_FOLLOWING) > 0
      && n.textContent.trim().length > 0,
  );
}"""
# The card's portrait is the same art as the hero's party card (one source: portraitKeys).
SAME_ART = """(creature) => {
  const at = `[data-creature="${creature}"] img`;
  const card = document.querySelector(`[data-testid=player-action]${at}`);
  const party = document.querySelector(`[data-testid=party-card]${at}`);
  return Boolean(card && party && card.getAttribute('src') === party.getAttribute('src'));
}"""


def test_a_typed_action_shows_on_the_screen_with_who_typed_it(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, guest = start_with_screen(browser, live_server.base, errors, PHONE, WIDE)
    host.fill("[data-testid=action-input]", CABIN)
    host.click("[data-testid=action-send]")
    screen.wait_for_selector(CARD, timeout=20000)
    card = screen.locator(CARD).last
    assert card.locator("[data-testid=player-action-name]").inner_text() == "Ann"
    assert card.locator("[data-testid=player-action-text]").inner_text() == CABIN
    assert "as Brienne" in card.inner_text()
    creature = card.get_attribute("data-creature")
    assert creature and screen.evaluate(SAME_ART, creature)
    screen.wait_for_function(TOLD_AFTER, arg=CABIN, timeout=20000)

    go_tab(guest, "journal")
    guest.click("[data-testid=jtab-story]")
    guest.wait_for_function(
        "(t) => document.querySelector('[data-testid=last-line]').textContent.includes(t)",
        arg=f'Ann (Brienne): "{CABIN}"',
    )
    snap(screen, shots_dir, "m22_player_action", 1280)
    screen.set_viewport_size(HD)
    snap(screen, shots_dir, "m22_player_action", 1920)

    screen.reload()
    dismiss_gate(screen)
    screen.wait_for_selector(CARD, timeout=20000)
    texts = screen.locator("[data-testid=player-action-text]").all_inner_texts()
    assert CABIN in texts  # restored from the story history
    assert errors == []
