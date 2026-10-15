"""The Scribe in the browser (M13.5): the phone tab, his overlay on /screen, host skip, the visual
fight banner (no voice) and the campaign victory screens. FakeLLM server; no network."""

from collections.abc import Awaitable, Callable
from pathlib import Path

from playwright.sync_api import Browser, Page

from aidm.models.campaign_events import FinaleChosen, RegionResolved
from aidm.models.campaign_state import RegionResolution
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.events import GoldChanged
from aidm.rules.damage import resolve_damage
from aidm.session.table import Table
from aidm.session.telling import maybe_epilogue
from tests.ui.conftest import LiveServer, open_screen
from tests.ui.table_helpers import HD, PHONE, go_tab, snap, start_fight, start_table

NO_HSCROLL = "document.documentElement.scrollWidth <= window.innerWidth"
# A fake audio element: play() resolves and the clip never ends by itself (only a skip ends it).
HOLD_AUDIO = (
    "window.__aidmMakeAudio = (url) => ({ url, volume: 1, play: () => Promise.resolve(),"
    " pause() {} });"
)
WATCH = """() => {
  window.__lines = [];
  window.aidm.store.on('scribe_line', (m) => window.__lines.push(m.group));
}"""
TEXT_LEN = "document.querySelector('[data-testid={}]').textContent.trim().length > 5"


def _job(live: LiveServer, fn: Callable[[Table], Awaitable[None]]) -> None:
    assert live.app is not None and live.loop is not None
    table = live.app.state.registry.table

    async def run() -> None:
        await fn(table)
        table.broadcast_snapshot()

    live.loop.call_soon_threadsafe(table.schedule, run)


def _hero(table: Table, name: str) -> str:
    return next(c.id for c in table.state.creatures.values() if c.pc is not None and c.name == name)


def _kill(live: LiveServer, name: str) -> None:
    async def job(table: Table) -> None:
        creature = table.state.creatures[_hero(table, name)]
        packet = DamagePacket(amount=999, damage_type=DamageType.PIERCING)
        table.apply_all(resolve_damage(creature, [packet]))

    _job(live, job)


def _set_gold(live: LiveServer, name: str, gold: int) -> None:
    async def job(table: Table) -> None:
        cid = _hero(table, name)
        pc = table.state.creatures[cid].pc
        assert pc is not None
        table.apply(GoldChanged(creature_id=cid, delta=gold - pc.gold, gold=gold))

    _job(live, job)


def _my_gold(page: Page) -> int:
    return int(
        page.evaluate(
            "(() => { const s = window.aidm.store.get(); const seat = s.players.find("
            "(p) => p.id === s.me.playerId); return s.snapshot.state.party.find("
            "(c) => c.id === seat.creature_id).gold; })()"
        )
    )


def _end_welcome(screen: Page, host: Page) -> None:
    """Skip the long welcome on the screen so later assertions see a quiet screen."""
    if screen.locator("[data-testid=screen-scribe]").is_hidden():
        return
    screen.click("[data-testid=screen-scribe-skip]")
    screen.wait_for_selector("[data-testid=screen-scribe]", state="hidden", timeout=10000)


def test_scribe_tab_empty_fallen_revive_and_refusals(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen = open_screen(browser, live_server.base, errors, HD, HOLD_AUDIO)
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    screen.wait_for_selector("[data-testid=screen-table]:not([hidden])", timeout=20000)
    _end_welcome(screen, host)
    go_tab(host, "scribe")
    icon = host.locator("[data-testid=ct-tab-scribe] img.ct-tab-icon")
    assert icon.get_attribute("src") == "/static/img/icons/tabs/scribe.png"
    assert host.locator("[data-testid=ct-tabs] [role=tab]").count() == 5
    host.wait_for_function(TEXT_LEN.format("scribe-reason"))
    assert host.locator("[data-testid=scribe-fallen]").count() == 0
    assert host.evaluate(NO_HSCROLL)
    snap(host, shots_dir, "scribe_tab", 390)
    # Mira falls with an empty purse (M20.4: her own gold would pay first): one card with the
    # price; Brienne has too little gold at first.
    _set_gold(live_server, "Brienne", 10)
    _set_gold(live_server, "Mira", 0)
    _kill(live_server, "Mira")
    host.wait_for_selector("[data-testid=scribe-fallen]", timeout=20000)
    assert host.locator("[data-testid=scribe-fallen]").count() == 1
    assert host.inner_text("[data-testid=scribe-fallen-name]") == "Mira"
    assert host.inner_text("[data-testid=scribe-price]") == "25 gp"
    assert "You have 10 gp" in host.inner_text("[data-testid=scribe-gold-warn]")
    assert host.evaluate(NO_HSCROLL)
    snap(host, shots_dir, "scribe_tab_fallen", 390)
    # Not enough gold: the server refuses; the phone shows his refusal text, nothing is spoken.
    host.evaluate(WATCH)
    screen.evaluate(WATCH)
    host.click("[data-testid=scribe-revive]")
    host.click("[data-testid=scribe-revive-yes]")
    host.wait_for_function(TEXT_LEN.format("scribe-status"), timeout=15000)
    assert host.locator("[data-testid=scribe-toast]").is_visible()
    host.wait_for_timeout(500)
    assert host.evaluate("window.__lines") == [] and screen.evaluate("window.__lines") == []
    assert screen.locator("[data-testid=screen-scribe]").is_hidden()
    # Enough gold: the revive works, gold drops, the screen shows the Scribe card.
    _set_gold(live_server, "Brienne", 100)
    host.wait_for_function(
        "document.querySelector('[data-testid=scribe-gold-warn]') === null", timeout=15000
    )
    host.click("[data-testid=scribe-revive]")
    host.click("[data-testid=scribe-revive-yes]")
    screen.wait_for_selector("[data-testid=screen-scribe]:not([hidden])", timeout=20000)
    assert screen.locator("[data-testid=screen-scribe-text]").inner_text().strip()
    host.wait_for_function("document.querySelectorAll('[data-testid=scribe-fallen]').length === 0")
    assert _my_gold(host) == 75
    assert "revive" in screen.evaluate("window.__lines")
    assert errors == []


def test_welcome_overlay_and_host_skip(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen = open_screen(browser, live_server.base, errors, HD, HOLD_AUDIO)
    host, guest = start_table(browser, live_server.base, PHONE, errors)
    screen.wait_for_selector("[data-testid=screen-scribe]:not([hidden])", timeout=20000)
    card = screen.locator("[data-testid=screen-scribe]")
    assert card.get_attribute("data-group") == "welcome_first"
    assert screen.locator("[data-testid=screen-scribe-text]").inner_text().strip()
    snap(screen, shots_dir, "screen_scribe_welcome", 1920)
    assert host.locator("[data-testid=controller-scribe-line]").count() == 0  # never a phone popup
    assert guest.locator("[data-testid=screen-scribe]").count() == 0
    go_tab(host, "more")
    host.click("[data-testid=open-host]")
    host.click("[data-testid=host-scribe-skip]")
    screen.wait_for_selector("[data-testid=screen-scribe]", state="hidden", timeout=10000)
    assert errors == []


def test_tab_is_disabled_in_combat_with_his_refusal(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    _screen, host, _guest = start_fight(browser, combat_server.base, errors)
    go_tab(host, "scribe")
    host.wait_for_function(TEXT_LEN.format("scribe-reason"))
    assert "outside combat" in host.inner_text("[data-testid=scribe-hint]")
    assert host.locator("[data-testid=scribe-revive]").count() == 0
    snap(host, shots_dir, "scribe_tab_combat", 390)
    assert errors == []


def test_fight_victory_banner_has_no_voice(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, _guest = start_fight(browser, combat_server.base, errors, screen_size=HD)
    screen.wait_for_selector("[data-testid=init-entry].ally.current", timeout=30000)
    _end_welcome(screen, host)
    screen.evaluate(WATCH)
    screen.evaluate(
        "() => { window.aidm.dispatch({ type: 'combat_state', combat: null, outcome: 'victory' });"
        " const s = window.aidm.store.get().snapshot;"
        " window.aidm.dispatch({ ...s, state: { ...s.state, combat: null } }); }"
    )
    screen.wait_for_selector("[data-testid=screen-victory-banner]:not([hidden])", timeout=10000)
    snap(screen, shots_dir, "screen_victory_banner", 1920)
    assert screen.evaluate("window.__lines") == []
    assert screen.locator("[data-testid=screen-scribe]").is_hidden()
    assert errors == []


def test_campaign_victory_screens(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen = open_screen(browser, live_server.base, errors, HD, HOLD_AUDIO)
    host, guest = start_table(browser, live_server.base, PHONE, errors)
    screen.wait_for_selector("[data-testid=screen-table]:not([hidden])", timeout=20000)

    async def win(table: Table) -> None:
        campaign = table.state.campaign
        assert campaign is not None
        region = campaign.plan.all_regions()[-1].id
        table.apply(RegionResolved(region_id=region, how=RegionResolution.DEFEAT, final=True))
        table.apply(FinaleChosen(option_id="silence-the-song"))  # M23.9: the ending is chosen
        await maybe_epilogue(table)

    _job(live_server, win)
    screen.wait_for_selector("[data-testid=screen-victory]:not([hidden])", timeout=60000)
    assert screen.locator("[data-testid=screen-victory-text]").inner_text().strip()
    host.wait_for_selector("[data-testid=controller-victory]:not([hidden])", timeout=20000)
    guest.wait_for_selector("[data-testid=controller-victory]:not([hidden])", timeout=20000)
    assert host.locator("[data-testid=victory-new]").is_visible()
    assert guest.locator("[data-testid=victory-new]").is_hidden()
    assert host.evaluate(NO_HSCROLL)
    snap(host, shots_dir, "controller_victory", 390)
    screen.click("[data-testid=screen-scribe-skip]")
    screen.wait_for_selector("[data-testid=screen-scribe]", state="hidden", timeout=10000)
    snap(screen, shots_dir, "screen_victory", 1920)
    assert errors == []
