"""M23.9 the finale card on the phone: after the last region resolves both phones show the question
and the two endings; an ending asks "Are you sure? This ends the story." (Back returns to the
choice), Yes ends the story: the card is gone on every phone and the victory panel follows."""

from pathlib import Path

from playwright.sync_api import Browser

from aidm.models.campaign_events import RegionResolved
from aidm.models.campaign_state import RegionResolution
from aidm.session.table import Table
from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import PHONE, snap, start_table

CARD = "[data-testid=finale-card]"
SHOWN = f"{CARD}:not([hidden])"
NO_HSCROLL = "document.documentElement.scrollWidth <= window.innerWidth"


def _resolve_last_region(live: LiveServer) -> None:
    assert live.app is not None and live.loop is not None
    table: Table = live.app.state.registry.table

    async def run() -> None:
        campaign = table.state.campaign
        assert campaign is not None
        region = campaign.plan.all_regions()[-1].id
        table.apply(RegionResolved(region_id=region, how=RegionResolution.DEFEAT, final=True))
        table.broadcast_snapshot()

    live.loop.call_soon_threadsafe(table.schedule, run)


def test_finale_card_choose_confirm_and_gone(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, guest = start_table(browser, live_server.base, PHONE, errors)
    host.wait_for_selector("[data-testid=quest-offer]:not([hidden])", timeout=20000)
    host.click("[data-testid=quest-offer-later]")  # the giver's card from the opening
    host.wait_for_selector("[data-testid=quest-offer]", state="hidden", timeout=20000)
    _resolve_last_region(live_server)
    for page in (host, guest):
        page.wait_for_selector(SHOWN, timeout=20000)
    card = host.locator(CARD)
    assert "Silence the Hollow Choir forever" in card.inner_text()
    options = host.locator("[data-testid=finale-option]")
    assert options.count() == 2
    assert options.nth(1).inner_text() == "Let the last verse be sung"
    assert host.evaluate(NO_HSCROLL)
    snap(host, shots_dir, "m23_finale", 390)
    options.nth(0).click()
    assert "Are you sure? This ends the story." in card.inner_text()
    assert "You chose: Silence the song" in card.inner_text()
    snap(host, shots_dir, "m23_finale_confirm", 390)
    host.click("[data-testid=finale-back]")
    assert host.locator("[data-testid=finale-option]").count() == 2
    host.locator("[data-testid=finale-option]").nth(1).click()
    host.click("[data-testid=finale-confirm]")
    for page in (host, guest):
        page.wait_for_selector(CARD, state="hidden", timeout=30000)
    chosen = "() => window.aidm.store.get().snapshot?.state.finale?.chosen ?? null"
    assert host.evaluate(chosen) == "let-it-finish"
    host.wait_for_selector("[data-testid=controller-victory]:not([hidden])", timeout=60000)
    assert errors == []
