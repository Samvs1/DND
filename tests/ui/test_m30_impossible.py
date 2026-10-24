"""M30.3: the player side of an impossible action: one feed line, no dice card (390 px shots)."""

from pathlib import Path

from playwright.sync_api import Browser, ViewportSize

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import PHONE, snap, start_with_screen

NARROW: ViewportSize = {"width": 390, "height": 844}
PUSH = """([seq, kind, line]) => window.aidm.pacer.push({ type: 'event', seq, kind, line,
  subject_id: null, amount: null })"""
IMPOSSIBLE = "Brienne cannot do that: a person cannot jump onto a roof."
SCENE_CAST = "Brienne casts Misty Step (outside a fight: nobody is moved)."


def test_m30_impossible_line_has_no_dice_card(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, _host, _guest = start_with_screen(browser, live_server.base, errors, PHONE, NARROW)
    before = screen.locator("[data-testid=screen-dice] li").count()
    screen.evaluate(PUSH, [9001, "action_impossible", IMPOSSIBLE])
    screen.evaluate(PUSH, [9002, "spell_cast", SCENE_CAST])
    screen.wait_for_function(
        "(t) => [...document.querySelectorAll('[data-testid=event-line]')]"
        ".some((e) => e.textContent === t)",
        arg=IMPOSSIBLE,
        timeout=20000,
    )
    lines = screen.locator("[data-testid=event-line]").all_inner_texts()
    assert IMPOSSIBLE in lines
    assert SCENE_CAST in lines
    assert screen.locator("[data-testid=screen-dice] li").count() == before
    screen.locator("[data-testid=feed]").scroll_into_view_if_needed()
    snap(screen, shots_dir, "m30_impossible_feed", 390)
    assert errors == []
