"""The ? marks on the Hero tab and in the shop (M28.3): they show, open the right tip, never act."""

from pathlib import Path

from playwright.sync_api import Browser, Page

from tests.ui.conftest import SHOTS, LiveServer
from tests.ui.table_helpers import PHONE, start_table
from tests.ui.test_panels import SNAPSHOT, _merchant, _open
from tests.ui.test_sheet import SHEET, WIZARD
from tests.ui.test_sheet import _open as open_hero
from tests.ui.wizard_helpers import HeroSpec

OUT = SHOTS / "m28_3"
POP = "[data-testid=tip-pop]"
LIVE = "[data-testid=tip-btn]:not([hidden])"


def _hero(browser: Browser, base: str) -> tuple[Page, list[str]]:
    errors: list[str] = []
    _host, guest = start_table(
        browser, base, PHONE, errors, specs=(HeroSpec(name="Brienne"), WIZARD)
    )
    open_hero(guest)
    guest.wait_for_selector(f"[data-testid=sh-sk] {LIVE}")
    return guest, errors


def _tip_title(page: Page, scope: str) -> str:
    page.locator(f"{scope} {LIVE}").first.click()
    page.wait_for_selector(POP)
    return page.inner_text(f"{POP} .tip-title")


def test_hero_overview_marks_open_the_right_tip(browser: Browser, live_server: LiveServer) -> None:
    guest, errors = _hero(browser, live_server.base)
    assert _tip_title(guest, "[data-testid=sh-sk]") == "Skills"
    guest.click("[data-testid=tip-close]")
    assert _tip_title(guest, "[data-testid=sh-ab]") == "Abilities"
    guest.click("[data-testid=tip-close]")
    assert _tip_title(guest, "[data-testid=sh-train]") == "Training"
    guest.click("[data-testid=tip-close]")
    assert _tip_title(guest, "[data-testid=sh-speed]") == "Speed"
    guest.click("[data-testid=tip-close]")
    assert _tip_title(guest, "[data-testid=sh-ft] li[data-feature]:not([data-feature=darkvision])")
    guest.click("[data-testid=tip-close]")
    trait = guest.locator("[data-testid=sh-ft] [data-tip^='trait:']").first
    assert trait.is_visible()
    trait.click()
    guest.wait_for_selector(POP)
    assert "A racial trait of the" in guest.inner_text(POP)
    OUT.mkdir(parents=True, exist_ok=True)
    guest.screenshot(path=str(OUT / "hero_trait_tip_390.png"))
    assert errors == []


def test_hero_spell_and_slot_marks(browser: Browser, live_server: LiveServer) -> None:
    guest, errors = _hero(browser, live_server.base)
    guest.click("[data-testid=tab-spells]")
    guest.wait_for_selector("[data-testid=sh-slots] [data-tip='sheet:slots']:not([hidden])")
    assert _tip_title(guest, "[data-testid=sh-slots]") == "Spell slots"
    guest.click("[data-testid=tip-close]")
    spell = guest.locator("[data-testid=spell-line] [data-tip^='spell:']:not([hidden])").first
    name = guest.locator("[data-testid=spell-line] strong").first.inner_text()
    spell.click()
    guest.wait_for_selector(POP)
    assert guest.inner_text(f"{POP} .tip-title") == name
    guest.screenshot(path=str(OUT / "hero_spell_tip_390.png"))
    assert errors == []


def test_tapping_an_item_mark_does_not_equip_or_drop(
    browser: Browser, live_server: LiveServer
) -> None:
    guest, errors = _hero(browser, live_server.base)
    guest.click("[data-testid=tab-inventory]")
    guest.wait_for_selector(f"[data-testid=inv-detail] {LIVE}")
    before = guest.evaluate(f"JSON.stringify({SHEET}.inventory)")
    guest.locator("[data-testid=inv-detail] [data-tip^='item:']").click()
    guest.wait_for_selector(POP)
    assert guest.inner_text(f"{POP} .tip-title") == guest.inner_text(
        "[data-testid=inv-detail-name]"
    )
    guest.wait_for_timeout(500)
    assert guest.evaluate(f"JSON.stringify({SHEET}.inventory)") == before
    guest.screenshot(path=str(OUT / "hero_item_tip_390.png"))
    assert errors == []


def test_tooltips_off_hides_every_mark_on_the_hero_tab(
    browser: Browser, live_server: LiveServer
) -> None:
    guest, errors = _hero(browser, live_server.base)
    assert guest.locator(LIVE).count() > 3
    guest.click("[data-testid=ct-tab-more]")
    guest.click("[data-testid=open-settings]")
    guest.uncheck("[data-testid=set-tooltips]")
    guest.wait_for_function(
        "document.querySelectorAll('[data-testid=tip-btn]:not([hidden])').length === 0"
    )
    assert errors == []


def test_shop_marks_open_item_tips_and_never_buy(browser: Browser, live_server: LiveServer) -> None:
    errors: list[str] = []
    host, guest = start_table(browser, live_server.base, PHONE, errors)
    _merchant(live_server, 400)
    host.wait_for_selector("[data-testid=open-shop]:not([hidden])", timeout=20000)
    _open(host, "shop")
    host.click("[data-testid=shop-visit]")
    host.wait_for_selector("[data-testid=vote]:not([hidden])", timeout=20000)
    guest.wait_for_selector("[data-testid=vote-ready]", timeout=20000)
    guest.click("[data-testid=vote-ready]")
    host.wait_for_selector("[data-testid=shop-stock] [data-testid=shop-line]", timeout=30000)
    gold = host.evaluate(f"{SNAPSHOT}.party.map(c => c.gold).join()")
    line = "[data-testid=shop-stock] [data-testid=shop-line]"
    host.wait_for_selector(f"{line} {LIVE}")
    name = host.locator(f"{line} strong").first.inner_text()
    host.locator(f"{line} {LIVE}").first.click()
    host.wait_for_selector(POP)
    assert host.inner_text(f"{POP} .tip-title") == name
    host.wait_for_timeout(500)
    assert host.evaluate(f"{SNAPSHOT}.party.map(c => c.gold).join()") == gold
    host.screenshot(path=str(OUT / "shop_tip_390.png"))
    assert errors == []


def test_dense_grid_fallback_screenshot(browser: Browser, live_server: LiveServer) -> None:
    guest, _errors = _hero(browser, live_server.base)
    guest.locator("[data-testid=sh-ab]").scroll_into_view_if_needed()
    guest.wait_for_timeout(500)
    guest.screenshot(path=str(OUT / "hero_dense_grid_390.png"))
    assert guest.locator("[data-testid=sh-ab] .sh-ability .tip-btn").count() == 0
    assert Path(OUT / "hero_dense_grid_390.png").exists()
