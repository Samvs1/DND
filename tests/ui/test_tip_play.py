"""The ? marks on Play, Journal, Scribe and More (M28.5): shown, right tip, switch off hides."""

from playwright.sync_api import Browser, Page

from tests.ui.conftest import SHOTS, LiveServer, open_screen
from tests.ui.dark_helpers import darken
from tests.ui.table_helpers import (
    HD,
    PHONE,
    go_tab,
    has_hit_chance,
    split_turn,
    start_fight,
    start_table,
    start_with_screen,
)
from tests.ui.test_roll_stage import MY_HERO, PUSH, _table
from tests.ui.test_scribe import _end_welcome, _kill, _set_gold

OUT = SHOTS / "m28_5"
POP = "[data-testid=tip-pop]"
LIVE = "[data-testid=tip-btn]:not([hidden]):visible"


def _title(page: Page, scope: str, nth: int = 0) -> str:
    page.locator(f"{scope} {LIVE}").nth(nth).click()
    page.wait_for_selector(POP)
    title = page.inner_text(f"{POP} .tip-title")
    page.click("[data-testid=tip-close]")
    return title


def _shot(page: Page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.wait_for_function("[...document.images].every((i) => i.complete)")
    page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / f"{name}.png"))


def test_now_card_chips_have_question_marks(browser: Browser, live_server: LiveServer) -> None:
    errors: list[str] = []
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    darken(host, light=True, boons=("Rope=Athletics",))
    host.wait_for_selector(f"[data-testid=now-card] {LIVE}")
    assert host.inner_text("[data-testid=now-dark]") == "Your torch lights the way."
    assert _title(host, ".ct-now-darkrow") == "Lit"
    assert _title(host, "[data-testid=now-gear]", 0) == "Lit"
    assert _title(host, "[data-testid=now-gear]", 1) == "Gear boon"
    _shot(host, "01_now_card_phone390")
    go_tab(host, "more")
    host.click("[data-testid=open-settings]")
    host.uncheck("[data-testid=set-tooltips]")
    host.keyboard.press("Escape")
    go_tab(host, "play")
    host.wait_for_selector("[data-testid=now-card] [data-testid=tip-btn]", state="hidden")
    assert host.locator(f"[data-testid=now-card] {LIVE}").count() == 0
    assert errors == []


def test_unlit_dark_place_tip_says_dark(browser: Browser, live_server: LiveServer) -> None:
    errors: list[str] = []
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    darken(host, light=False)
    host.wait_for_selector(f"[data-testid=now-card] {LIVE}")
    assert host.inner_text("[data-testid=now-dark]") == "It is dark here."
    assert _title(host, ".ct-now-darkrow") == "Dark"
    assert errors == []


def test_quest_offer_and_journal_headings_open_their_tips(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    _screen, host, _guest = start_with_screen(browser, live_server.base, errors)
    host.wait_for_selector("[data-testid=quest-offer]:not([hidden])", timeout=20000)
    host.wait_for_selector(f"[data-testid=quest-offer] {LIVE}")
    host.click(f"[data-testid=quest-offer] {LIVE}")
    host.wait_for_selector(POP)
    assert host.inner_text(f"{POP} .tip-title") == "A quest offer"
    _shot(host, "03_quest_offer_tip_phone390")
    host.click("[data-testid=tip-close]")
    go_tab(host, "journal")
    host.wait_for_selector(f"[data-testid=journal-main] {LIVE}")
    assert _title(host, "[data-testid=journal-main]") == "Main quest"
    _shot(host, "02_journal_phone390")
    assert errors == []


def test_scribe_price_has_a_tip(browser: Browser, live_server: LiveServer) -> None:
    errors: list[str] = []
    screen = open_screen(browser, live_server.base, errors, HD)
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    screen.wait_for_selector("[data-testid=screen-table]:not([hidden])", timeout=20000)
    _end_welcome(screen, host)
    go_tab(host, "scribe")
    _set_gold(live_server, "Mira", 0)
    _kill(live_server, "Mira")
    host.wait_for_selector("[data-testid=scribe-fallen]", timeout=20000)
    assert _title(host, "[data-testid=scribe-fallen]") == "The Scribe"
    go_tab(host, "more")
    assert _title(host, "[data-testid=pane-more]") == "Tooltips"
    assert errors == []


def test_roll_card_terms_have_question_marks(browser: Browser, live_server: LiveServer) -> None:
    errors: list[str] = []
    screen, host = _table(browser, live_server.base, errors)
    host.evaluate("window.__aidmShowScale = 1")
    mine = host.evaluate(MY_HERO)
    dice = {"roller_id": mine, "expression": "2d20", "rolls": [6, 13], "adv": "advantage"}
    for page in (screen, host):
        page.evaluate(PUSH, [9100, {**dice, "total": 15, "success": True}])
    host.wait_for_selector("[data-testid=roll-card]", timeout=5000)
    host.wait_for_selector("[data-testid=roll-card-verdict]:not([hidden])", timeout=8000)
    host.wait_for_selector("[data-testid=roll-card-terms]:not([hidden])", timeout=3000)
    assert _title(host, "[data-testid=roll-card-terms]", 0) == "Medium"
    assert _title(host, "[data-testid=roll-card-terms]", 1) == "Advantage"
    assert errors == []


def test_hotbar_throw_shove_and_jump_have_question_marks(
    browser: Browser, combat_server: LiveServer
) -> None:
    errors: list[str] = []
    _screen, host, guest = start_fight(browser, combat_server.base, errors)
    active, _other = split_turn(host, guest)
    has_hit_chance(active)
    for slot, title in (
        ("throw", "Throw"),
        ("shove-prone", "Shove prone"),
        ("shove-push", "Shove away"),
        ("jump", "Jump"),
    ):
        cell = active.locator(".hb-cell", has=active.locator(f"[data-testid=slot-{slot}]"))
        cell.locator(LIVE).click()
        active.wait_for_selector(POP)
        assert active.inner_text(f"{POP} .tip-title") == title
        active.click("[data-testid=tip-close]")
    active.locator("[data-testid=slot-throw]").scroll_into_view_if_needed()
    _shot(active, "04_hotbar_new_tips_phone390")
    assert errors == []
