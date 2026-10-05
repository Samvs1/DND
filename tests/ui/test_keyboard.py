"""Keyboard-only play (M8.4): join, build a hero, act, open the sheet, close it with Escape."""

from pathlib import Path

from playwright.sync_api import Browser

from tests.ui.conftest import LiveServer
from tests.ui.kb_helpers import FOCUSED, activate, keyboard_wizard, tab_to, type_into
from tests.ui.table_helpers import HAS_TEXT, WIDE, snap


def test_whole_flow_with_the_keyboard_alone(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    page = browser.new_context(viewport=WIDE).new_page()
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(f"{live_server.base}/play")
    page.wait_for_selector("#join-name")
    # The first Tab stop is the skip link; it moves focus into the main region.
    page.keyboard.press("Tab")
    assert page.evaluate(FOCUSED, ".skip-link")
    page.keyboard.press("Enter")
    assert page.evaluate(FOCUSED, "#app") or page.evaluate("location.hash") == "#app"
    type_into(page, "#join-name", "Ann")
    page.keyboard.press("Enter")
    page.wait_for_selector("[data-testid=wizard]")
    page.wait_for_selector("[data-testid=wizard-body] .wz-card")
    assert page.evaluate(FOCUSED, "#join-name") is False
    keyboard_wizard(page, "Brienne")
    activate(page, "[data-testid=start]")
    page.wait_for_selector("[data-testid=feed]", timeout=20000)
    page.wait_for_function(HAS_TEXT, timeout=20000)
    type_into(page, "[data-testid=action-input]", "I look around the room")
    page.keyboard.press("Tab")  # to the Act button
    assert page.evaluate(FOCUSED, "[data-testid=action-send]")
    page.keyboard.press("Space")
    page.wait_for_function(
        "document.querySelectorAll('[data-testid=narration]').length >= 2", timeout=20000
    )
    activate(page, "[data-testid=sheet-open]")
    page.wait_for_selector("[data-testid=sheet][open]")
    assert page.evaluate(
        "document.querySelector('[data-testid=sheet]').contains(document.activeElement)"
    )
    page.wait_for_function(
        "document.querySelector('[data-testid=sheet]').textContent.includes('Human Fighter')"
    )
    snap(page, shots_dir, "keyboard_sheet", 1280)
    page.keyboard.press("Escape")
    page.wait_for_selector("[data-testid=sheet]:not([open])", state="attached")
    assert page.evaluate(FOCUSED, "[data-testid=sheet-open]"), "focus must return to the opener"
    tab_to(page, "[data-testid=open-settings]")
    assert errors == []
