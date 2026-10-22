"""M27.8: real-app screenshots of the item screens for the owner (artifacts/ui/m27_8/)."""

from pathlib import Path

from playwright.sync_api import Browser, Page

from tests.ui.conftest import LiveServer
from tests.ui.dark_helpers import OUT, shot
from tests.ui.table_helpers import PHONE

HOTBAR = (Path(__file__).parent / "js" / "hotbar_items.js").read_text(encoding="utf-8")

SPELLBOOK = (Path(__file__).parent / "js" / "spellbook_copy.js").read_text(encoding="utf-8")


def _phone(browser: Browser, base: str) -> Page:
    page = browser.new_page(viewport=PHONE)
    page.goto(f"{base}/play")
    page.wait_for_selector("#join-name")
    return page


def test_shots_hotbar_items_and_spellbook(browser: Browser, live_server: LiveServer) -> None:
    page = _phone(browser, live_server.base)
    page.evaluate(HOTBAR)
    shot(page, "00_hotbar_items_phone390")
    page.evaluate(SPELLBOOK)
    shot(page, "00_spellbook_copy_phone390")
    assert (OUT / "00_spellbook_copy_phone390.png").exists()
