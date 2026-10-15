"""M23.4 the giver's quest card on the phone: shown after the opening (the sample campaign's
first giver stands at the arrival), back after a reload, Not now closes it on every phone and
keeps the quest offered; the screen shows no card."""

from pathlib import Path

from playwright.sync_api import Browser, Page

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import PHONE, snap, start_with_screen

CARD = "[data-testid=quest-offer]"
SHOWN = f"{CARD}:not([hidden])"
QUEST_STATE = """(id) => (window.aidm.store.get().snapshot?.state.quests ?? [])
    .find((q) => q.id === id)?.state ?? null"""


def _card_text(page: Page) -> str:
    page.wait_for_selector(SHOWN, timeout=20000)
    return page.locator(CARD).inner_text()


def test_quest_card_accept_and_not_now(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, guest = start_with_screen(browser, live_server.base, errors)
    text = _card_text(host)
    assert "Tobin Marrow asks: The Missing Ledger" in text
    assert "Accept" in text and "Not now" in text
    assert host.viewport_size == PHONE
    snap(host, shots_dir, "controller_quest_offer", 390)
    assert screen.locator(CARD).count() == 0  # the shared screen tells it, no card
    guest.reload()
    guest.wait_for_selector("[data-testid=controller]", timeout=20000)
    assert "The Missing Ledger" in _card_text(guest)  # the card survives a reconnect
    guest.click("[data-testid=quest-offer-later]")
    for page in (host, guest):
        page.wait_for_selector(CARD, state="hidden", timeout=20000)
    assert host.evaluate(QUEST_STATE, "missing-ledger") == "offered"
    assert errors == []


def test_quest_card_accept_makes_the_quest_active(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    _screen, host, guest = start_with_screen(browser, live_server.base, errors)
    _card_text(guest)
    host.wait_for_selector(SHOWN, timeout=20000)
    host.click("[data-testid=quest-offer-accept]")
    for page in (host, guest):
        page.wait_for_selector(CARD, state="hidden", timeout=20000)
    host.wait_for_function(f"({QUEST_STATE})('missing-ledger') === 'active'", timeout=20000)
    assert errors == []


def test_other_tabs_show_a_slim_strip_not_the_card(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    _screen, host, _guest = start_with_screen(browser, live_server.base, errors)
    host.wait_for_selector(SHOWN, timeout=20000)
    host.click("[data-testid=ct-tab-hero]")
    strip = host.locator("[data-testid=quest-offer-strip]")
    strip.wait_for(state="visible", timeout=20000)
    assert "Tobin Marrow asks: The Missing Ledger" in strip.inner_text()
    assert host.locator(CARD).is_hidden()
    box = strip.bounding_box()
    assert box is not None and box["height"] < 60
    snap(host, shots_dir, "m23_offer_strip", 390)
    host.click("[data-testid=quest-offer-answer]")
    host.wait_for_selector(SHOWN, timeout=20000)
    assert strip.is_hidden()
    assert errors == []
