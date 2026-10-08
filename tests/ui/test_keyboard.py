"""Keyboard-only play (M8.4, M11.4): join, build a hero, act on the phone, move between its tabs."""

from pathlib import Path

from playwright.sync_api import Browser

from tests.ui.conftest import LiveServer
from tests.ui.kb_helpers import FOCUSED, activate, keyboard_wizard, tab_to, type_into
from tests.ui.table_helpers import PHONE, PHONE_TEXT, snap


def test_whole_flow_with_the_keyboard_alone(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    page = browser.new_context(viewport=PHONE).new_page()
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
    page.wait_for_selector("[data-testid=controller]", timeout=20000)
    page.wait_for_function(PHONE_TEXT, timeout=20000)
    first = page.inner_text("[data-testid=last-line]")
    type_into(page, "[data-testid=action-input]", "I look around the room")
    page.keyboard.press("Tab")  # to the Act button (the hidden microphone slot is skipped)
    assert page.evaluate(FOCUSED, "[data-testid=action-send]")
    page.keyboard.press("Space")
    page.wait_for_function(
        "(text) => document.querySelector('[data-testid=last-line]').textContent !== text",
        arg=first,
        timeout=20000,
    )
    # The tab bar is one tab stop; Arrow keys move between the tabs and select them.
    tab_to(page, "[data-testid=ct-tab-play]")
    page.keyboard.press("ArrowRight")
    assert page.evaluate(FOCUSED, "[data-testid=ct-tab-hero]")
    page.wait_for_selector("[data-testid=sheet]:not([hidden])")
    page.wait_for_function(
        "document.querySelector('[data-testid=sheet]').textContent.includes('Human Fighter')"
    )
    snap(page, shots_dir, "keyboard_hero", 390)
    page.keyboard.press("ArrowLeft")
    assert page.evaluate(FOCUSED, "[data-testid=ct-tab-play]")
    assert page.locator("[data-testid=sheet]").is_hidden()
    assert page.locator("[data-testid=action-input]").is_visible()
    for _ in range(3):
        page.keyboard.press("ArrowRight")
    assert page.evaluate(FOCUSED, "[data-testid=ct-tab-more]")
    tab_to(page, "[data-testid=open-settings]")
    assert errors == []
