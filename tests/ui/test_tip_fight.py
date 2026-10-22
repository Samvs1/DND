"""The ? marks in a fight (M28.4): slots, foe health words, the advantage tag, Move badges, strip
conditions, plus the Hero tab follow-ups (one abilities ?, tiles alike, AC and HP on the strip)."""

from playwright.sync_api import Browser, Page

from tests.ui.conftest import SHOTS, LiveServer
from tests.ui.table_helpers import (
    HD,
    PHONE,
    go_tab,
    has_hit_chance,
    split_turn,
    start_fight,
    start_table,
)
from tests.ui.test_combat_view import NO_HSCROLL, PATCH_ZONE
from tests.ui.test_m27_11_fixes import IDS, MINE, ROLL, SPEED
from tests.ui.test_sheet import WIZARD
from tests.ui.test_sheet import _open as open_hero
from tests.ui.wizard_helpers import HeroSpec

OUT = SHOTS / "m28_4"
POP = "[data-testid=tip-pop]"
LIVE = ".tip-btn:not([hidden])"
COND = """async (name) => { const s = window.aidm.store.get(); const st = s.snapshot.state;
  const me = (await import('/web/js/combat/model.js')).myCreatureId(s);
  window.aidm.store.update({ snapshot: { ...s.snapshot, state: { ...st,
    party: st.party.map((c) => (c.id === me ? { ...c, conditions: [name] } : c)) } } }); }"""


def _shot(page: Page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.wait_for_function("[...document.images].every((i) => i.complete)")
    page.wait_for_timeout(700)
    page.screenshot(path=str(OUT / f"{name}.png"))


def _fight(browser: Browser, base: str, errors: list[str]) -> Page:
    _screen, host, guest = start_fight(browser, base, errors)
    active, _other = split_turn(host, guest)
    has_hit_chance(active)
    active.wait_for_selector(f"[data-testid=slot-dash] >> xpath=.. >> {LIVE}")
    return active


def _title(page: Page) -> str:
    page.wait_for_selector(POP)
    return page.inner_text(f"{POP} .tip-title")


def test_hotbar_slot_question_mark_opens_its_tip_and_never_picks(
    browser: Browser, combat_server: LiveServer
) -> None:
    errors: list[str] = []
    active = _fight(browser, combat_server.base, errors)
    cell = active.locator(".hb-cell", has=active.locator("[data-testid=slot-help]"))
    box = cell.locator(LIVE).bounding_box()
    assert box is not None and box["width"] >= 24 and box["height"] >= 24
    cell.locator(LIVE).click()
    assert _title(active) == "Help"
    assert active.inner_text("[data-testid=aim-bar]").strip() == ""  # the ? did not pick the slot
    assert active.locator("[data-testid=pip-action].on").count() == 1
    _shot(active, "hotbar_tip_open_390")
    active.click("[data-testid=tip-close]")
    active.click("[data-testid=slot-help]")  # tapping the slot still picks it
    assert active.inner_text("[data-testid=aim-bar]").strip() != ""
    active.click("[data-testid=aim-cancel]")
    _shot(active, "hotbar_question_marks_390")
    assert errors == []


def test_foe_health_word_and_zone_badge_and_strip_condition_marks(
    browser: Browser, combat_server: LiveServer
) -> None:
    errors: list[str] = []
    active = _fight(browser, combat_server.base, errors)
    foe = active.locator(
        ".tip-cell", has=active.locator("[data-testid=target-chip][data-side=hostile]")
    )
    before = active.locator("[data-testid=target-chip][aria-pressed=true]").count()
    foe.first.locator(LIVE).click()
    assert _title(active) == "Unhurt"
    assert active.locator("[data-testid=target-chip][aria-pressed=true]").count() == before
    _shot(active, "target_health_tip_390")
    active.click("[data-testid=tip-close]")
    zone = active.locator("[data-testid=zone-chip]").first.get_attribute("data-zone")
    active.evaluate(PATCH_ZONE, [zone, {"rough": True, "cover": "half"}])
    active.locator(".ct-tip-fact", has_text="Rough ground").locator(LIVE).click()
    assert _title(active) == "Rough ground"
    active.click("[data-testid=tip-close]")
    active.evaluate(COND, "prone")
    active.locator("[data-testid=strip] .conditions").locator(LIVE).click()
    assert _title(active) == "Prone"
    assert active.evaluate(NO_HSCROLL)
    assert errors == []


def test_advantage_tag_question_mark_explains_the_word_and_names_the_reason(
    browser: Browser, combat_server: LiveServer
) -> None:
    errors: list[str] = []
    screen, host, guest = start_fight(browser, combat_server.base, errors, screen_size=HD)
    split_turn(host, guest)
    screen.wait_for_timeout(1500)
    for page in (screen, host, guest):
        page.evaluate(SPEED)
    ids = screen.evaluate(IDS)
    me = host.evaluate(MINE)
    foe = ids["foe"] if ids["foe"] != me else ids["hero"]
    miss = {"roller_id": foe, "target_id": me, "rolls": [14, 6], "total": 11, "target": 16}
    host.evaluate(ROLL, [9701, {**miss, "success": False}])
    host.wait_for_selector(f"[data-testid=fight-card] {LIVE}", timeout=6000)
    host.locator(f"[data-testid=fight-card] {LIVE}").click()
    assert _title(host) == "Disadvantage"
    text = host.inner_text(POP)
    assert "keep the lower" in text and "Darkness" in text
    _shot(host, "dis_tag_tip_390")
    assert errors == []


def test_tooltips_off_hides_every_fight_question_mark(
    browser: Browser, combat_server: LiveServer
) -> None:
    errors: list[str] = []
    active = _fight(browser, combat_server.base, errors)
    go_tab(active, "more")
    active.click("[data-testid=open-settings]")
    active.uncheck("[data-testid=set-tooltips]")
    active.wait_for_function("document.querySelectorAll('.tip-btn:not([hidden])').length === 0")
    assert errors == []


def test_hero_overview_one_abilities_mark_alike_tiles_and_ac_hp_marks(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    _host, guest = start_table(
        browser, live_server.base, PHONE, errors, specs=(HeroSpec(name="Brienne"), WIZARD)
    )
    guest.wait_for_selector("[data-testid=strip] [data-tip='sheet:ac']:not([hidden])")
    guest.wait_for_selector("[data-testid=strip] [data-tip='sheet:hp']:not([hidden])")
    assert guest.evaluate(NO_HSCROLL)
    guest.locator("[data-testid=strip] [data-tip='sheet:ac']").click()
    assert _title(guest) == "Armour class"
    guest.click("[data-testid=tip-close]")
    open_hero(guest)
    guest.wait_for_selector(f"[data-testid=sh-ab] {LIVE}")
    assert guest.locator(f"[data-testid=sh-ab] {LIVE}").count() == 1
    guest.locator(f"[data-testid=sh-ab] {LIVE}").click()
    assert "saving throw" in guest.inner_text(POP)
    guest.click("[data-testid=tip-close]")
    offsets = guest.evaluate(
        """() => [...document.querySelectorAll('.sh-vitals .sh-stat')].map((tile) => {
          const a = tile.getBoundingClientRect();
          const b = tile.querySelector('.tip-btn').getBoundingClientRect();
          return [Math.round(a.right - b.right), Math.round(b.top - a.top)]; })"""
    )
    assert len(offsets) == 4 and all(o == offsets[0] for o in offsets), offsets
    guest.evaluate("window.scrollTo(0, 0)")
    _shot(guest, "hero_overview_390")
    assert errors == []
