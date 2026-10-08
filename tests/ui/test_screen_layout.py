"""Browser tests of the shared /screen widgets (M11.3) at 1920x1080 and 1280."""

from pathlib import Path

from playwright.sync_api import Browser, Page, ViewportSize

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import WIDE, snap, start_table

FULL_HD = ViewportSize(width=1920, height=1080)

PATCH = """(patch) => {
  const snap = window.aidm.store.get().snapshot;
  window.aidm.dispatch({ ...snap, state: { ...snap.state, ...patch } });
}"""
SEAT = {"player_id": "p1", "name": "Ann", "hero_name": "Brienne", "position": 1}
SEAT2 = {"player_id": "p2", "name": "Bo", "hero_name": "Mira", "position": 1}
ROLL = {
    "type": "dice_roll",
    "seq": 9001,
    "dice": {
        "expression": "1d20",
        "rolls": [17],
        "modifier": 3,
        "total": 20,
        "label": "Stealth",
        "roller_id": None,
        "adv": "normal",
        "target": 15,
        "success": True,
        "crit": False,
    },
}
NO_HSCROLL = "document.documentElement.scrollWidth <= window.innerWidth"


def _screen(browser: Browser, base: str, size: ViewportSize, errors: list[str]) -> Page:
    page = browser.new_context(viewport=size).new_page()
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(f"{base}/screen")
    page.wait_for_selector("[data-testid=screen-waiting]:not([hidden])")
    return page


def test_screen_widgets_at_two_sizes(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen = _screen(browser, live_server.base, FULL_HD, errors)
    start_table(browser, live_server.base, WIDE, errors)
    screen.wait_for_selector("[data-testid=screen-table]:not([hidden])", timeout=20000)
    screen.wait_for_function(
        "[...document.querySelectorAll('[data-testid=narration]')]"
        ".some((n) => n.textContent.trim().length > 20)",
        timeout=20000,
    )
    assert screen.locator("[data-testid=scene-name]").inner_text().strip()
    assert screen.locator("[data-testid=screen-floor]:not([hidden])").count() == 0
    floor = {"holder": SEAT, "queue": [SEAT2], "typing": []}
    screen.evaluate(PATCH, {"floor": floor})
    assert "acting" in screen.locator("[data-testid=floor-acting]").inner_text()
    assert screen.locator("[data-testid=floor-queue] li").count() == 1
    screen.evaluate(PATCH, {"floor": {"holder": None, "queue": [], "typing": [SEAT2]}})
    assert "typing" in screen.locator("[data-testid=floor-typing]").inner_text()
    screen.evaluate(PATCH, {"floor": None})
    assert screen.locator("[data-testid=screen-floor]:not([hidden])").count() == 0
    screen.evaluate("(m) => window.aidm.dispatch(m)", ROLL)
    screen.wait_for_selector("[data-testid=screen-roll]")
    assert "20" in screen.locator("[data-testid=screen-dice]").inner_text()
    event = {"type": "event", "seq": 9002, "kind": "level_gained", "line": "Ann reached level 3"}
    screen.evaluate("(m) => window.aidm.dispatch(m)", event)
    assert "level 3" in screen.locator("[data-testid=screen-levelup]").inner_text()
    assert screen.locator("[data-testid=screen-invite]:not([hidden])").count() == 1  # seats free
    screen.locator("[data-testid=screen-gear]").click()
    screen.wait_for_selector("[data-testid=settings][open]")
    screen.keyboard.press("Escape")
    snap(screen, shots_dir, "screen_widgets", 1920)
    assert screen.evaluate(NO_HSCROLL)
    screen.set_viewport_size(WIDE)
    assert screen.evaluate(NO_HSCROLL)
    snap(screen, shots_dir, "screen_widgets", 1280)
    assert errors == []


def test_screen_defeat_overlay(browser: Browser, live_server: LiveServer, shots_dir: Path) -> None:
    errors: list[str] = []
    screen = _screen(browser, live_server.base, FULL_HD, errors)
    start_table(browser, live_server.base, WIDE, errors)
    screen.wait_for_selector("[data-testid=screen-table]:not([hidden])", timeout=20000)
    assert screen.locator("[data-testid=screen-defeat]:not([hidden])").count() == 0
    screen.evaluate(
        PATCH, {"phase": "defeated", "defeat": "All is lost.", "checkpoint": "The Gate"}
    )
    overlay = screen.locator("[data-testid=screen-defeat]")
    overlay.wait_for(state="visible")
    text = overlay.inner_text()
    assert "All is lost." in text and "The Gate" in text
    assert "Waiting for the host to choose on their phone" in text
    assert overlay.locator("button, input").count() == 0
    snap(screen, shots_dir, "screen_defeat", 1920)
    screen.evaluate(PATCH, {"phase": "play"})
    assert screen.locator("[data-testid=screen-defeat]:not([hidden])").count() == 0
    assert errors == []
