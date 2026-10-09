"""M15.1 playtest defects in the browser: the confirm survives narration, the turn countdown shows
on the phone and the screen, a defeat never flashes the victory banner."""

import re

from playwright.sync_api import Browser

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import HD, split_turn, start_fight, start_with_screen

PROMPT = "Striking the harbourmaster will start a fight. Continue?"


def test_playtest_confirm_survives_narration(browser: Browser, live_server: LiveServer) -> None:
    errors: list[str] = []
    _screen, host, _guest = start_with_screen(browser, live_server.base, errors)
    me = host.evaluate("window.aidm.store.get().me.playerId")
    host.evaluate(
        "([me, p]) => window.aidm.dispatch("
        "{type: 'pending_confirmation', player_id: me, prompt: p})",
        [me, PROMPT],
    )
    dialog = host.locator("[data-testid=confirm-dialog]")
    dialog.wait_for(state="visible")
    host.evaluate(
        "() => window.aidm.dispatch({type: 'narration_chunk', id: 'n990', index: 0,"
        " text: 'Sam stands on the brink of violence.', tone: 'exploration'})"
    )
    host.wait_for_timeout(500)
    assert dialog.is_visible(), "narration never answers the question for the player"
    host.click("[data-testid=confirm-no]")
    dialog.wait_for(state="hidden")
    assert errors == []


def test_playtest_turn_countdown_on_phone_and_screen(
    browser: Browser, combat_server: LiveServer
) -> None:
    errors: list[str] = []
    screen, host, guest = start_fight(browser, combat_server.base, errors, screen_size=HD)
    active, _other = split_turn(host, guest)
    chip = active.locator("[data-testid=status-chip]")
    active.wait_for_function(
        "/Your turn - [0-9]:[0-9][0-9]/.test("
        "document.querySelector('[data-testid=status-chip]').textContent)",
        timeout=10000,
    )
    first = chip.inner_text()
    active.wait_for_timeout(2100)
    assert chip.inner_text() != first, "the countdown ticks"
    screen.wait_for_selector("[data-testid=floor-acting]", timeout=10000)
    assert re.search(r"is acting - \d:\d\d", screen.inner_text("[data-testid=floor-acting]"))
    assert errors == []


def test_playtest_defeat_shows_no_victory_banner(
    browser: Browser, combat_server: LiveServer
) -> None:
    errors: list[str] = []
    screen, _host, _guest = start_fight(browser, combat_server.base, errors, screen_size=HD)
    screen.wait_for_selector("[data-testid=init-entry].ally.current", timeout=30000)
    # The fight ends in defeat while the snapshot still shows the party standing (stale HP).
    screen.evaluate(
        "() => window.aidm.dispatch({type: 'combat_state', combat: null, outcome: 'defeat'})"
    )
    screen.wait_for_timeout(2000)
    assert screen.locator("[data-testid=screen-victory-banner]").is_hidden()
    assert screen.evaluate("window.aidm.music.state().playing") != "victory"
    assert errors == []
