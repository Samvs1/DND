"""M23.8 What now? on the phone: the button in the Now card opens the engine's answer in a panel
under the card (asker only), the shared screen shows it as one card in its feed, Dismiss closes it."""

from pathlib import Path

from playwright.sync_api import Browser, Page

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import snap, start_with_screen

BUTTON = "[data-testid=what-now]"
ANSWER = "[data-testid=what-now-answer]"
SHOWN = f"{ANSWER}:not([hidden])"


def _box(page: Page, selector: str) -> dict[str, float]:
    box = page.locator(selector).first.bounding_box()
    assert box is not None
    return {"x": box["x"], "y": box["y"], "w": box["width"], "h": box["height"]}


def test_what_now_button_opens_the_answer_on_the_asker_phone_and_the_screen(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, guest = start_with_screen(browser, live_server.base, errors)
    host.wait_for_selector("[data-testid=quest-offer]:not([hidden])", timeout=20000)
    host.click("[data-testid=quest-offer-accept]")
    host.wait_for_selector("[data-testid=quest-offer]", state="hidden", timeout=20000)
    card = _box(host, "[data-testid=now-card]")
    button = _box(host, BUTTON)
    assert button["y"] >= card["y"] and button["y"] + button["h"] <= card["y"] + card["h"]
    host.click(BUTTON)
    host.wait_for_selector(SHOWN, timeout=20000)
    lines = host.locator(f"{ANSWER} li").all_inner_texts()
    assert len(lines) >= 1
    assert any("Gullmere Quay" in line for line in lines)
    assert any("The Missing Ledger" in line for line in lines)
    panel = _box(host, ANSWER)
    assert panel["y"] >= card["y"] + card["h"] - 1  # under the Now card, not over it
    assert panel["x"] >= 0 and panel["x"] + panel["w"] <= 391
    screen.wait_for_selector("[data-testid=what-now-card]", timeout=20000)
    assert "What now? asked by" in screen.locator("[data-testid=what-now-card]").inner_text()
    assert guest.locator(SHOWN).count() == 0  # only the asker's phone opens it
    snap(host, shots_dir, "m23_what_now", 390)
    snap(screen, shots_dir, "m23_what_now_screen", 1280)
    host.click("[data-testid=what-now-close]")
    host.wait_for_selector(ANSWER, state="hidden")
    assert errors == []
