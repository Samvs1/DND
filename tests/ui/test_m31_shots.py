"""M31.1a V4: the parley confirm card on the phone (390 px shot): the same confirm / cancel card
as a point-of-no-return act, with the parley prompt the server sends."""

from pathlib import Path

from playwright.sync_api import Browser, ViewportSize

from aidm.session.held import PARLEY_ASK
from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import PHONE, snap, start_with_screen

NARROW: ViewportSize = {"width": 390, "height": 844}


def test_m31_parley_confirm_card(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    _screen, host, _guest = start_with_screen(browser, live_server.base, errors, PHONE, NARROW)
    me = host.evaluate("window.aidm.store.get().me.playerId")
    host.evaluate(
        "([me, prompt]) => window.aidm.dispatch({type: 'pending_confirmation', player_id: me,"
        " prompt})",
        [me, PARLEY_ASK],
    )
    dialog = host.locator("[data-testid=confirm-dialog]")
    dialog.wait_for(state="visible")
    assert host.locator("[data-testid=confirm-text]").inner_text() == PARLEY_ASK
    for button in ("confirm-yes", "confirm-no"):
        box = host.locator(f"[data-testid={button}]").bounding_box()
        assert box is not None and box["x"] >= 0 and box["x"] + box["width"] <= 390
    snap(host, shots_dir, "m31_parley_confirm", 390)
    host.click("[data-testid=confirm-no]")
    dialog.wait_for(state="hidden")
    assert errors == []
