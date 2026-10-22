"""M27.11 review fixes: a lit dark place says LIT (badge, picture, phone line), fight rolls with
advantage or disadvantage show both d20s and the reason, and a spell with no roll gets a line."""

from playwright.sync_api import Browser, Page

from tests.ui.conftest import SHOTS, LiveServer
from tests.ui.dark_helpers import darken
from tests.ui.table_helpers import HD, PHONE, split_turn, start_fight, start_with_screen

OUT = SHOTS / "m27_11" / "fix"
SPEED = "window.__aidmShowScale = 1"
STRIP = "[data-testid=show-strip]"
LINES = "[data-testid=round-line]"
LIT = """(name) => { const s = window.aidm.store.get(); const st = s.snapshot.state;
  window.aidm.store.update({ snapshot: { ...s.snapshot, state: { ...st,
    scene: { ...st.scene, dark: true, lit: name } } } }); }"""
IDS = """() => { const s = window.aidm.store.get().snapshot.state;
  const foes = s.combat.tokens.filter((t) => t.side === 'hostile').map((t) => t.creature_id);
  return { hero: s.party[0].id, foe: foes[0] }; }"""
ROLL = """([seq, dice]) => window.aidm.pacer.push({ type: 'dice_roll', seq, dice: {
  expression: '2d20', adv: 'disadvantage', modifier: 5, label: 'Longsword', crit: false, parts: [],
  adv_why: ['Darkness'], kind: 'attack', ...dice } })"""
SPELL = """([seq, id, line]) => window.aidm.pacer.push({ type: 'event', seq, kind: 'spell_cast',
  line, subject_id: id, amount: null })"""
MINE = "async () => (await import('/web/js/combat/model.js')).myCreatureId(window.aidm.store.get())"


def _shot(page: Page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.wait_for_function("[...document.images].every((i) => i.complete)")
    page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / f"{name}.png"))


def test_a_lit_dark_place_says_lit_on_the_screen_and_the_phone(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    screen, host, _guest = start_with_screen(browser, live_server.base, errors, PHONE, HD)
    for page in (screen, host):
        darken(page, light=False)
    screen.wait_for_selector("[data-testid=dark-badge]:not([hidden])")
    assert screen.inner_text("[data-testid=dark-badge]").strip().lower() == "dark"
    assert screen.locator(".scene-pic.is-dark").count() == 1
    assert host.inner_text("[data-testid=now-dark]") == "It is dark here."
    for page in (screen, host):
        page.evaluate(LIT, "Torch")
    screen.wait_for_function(
        "document.querySelector('[data-testid=dark-badge]').textContent.trim() === 'Lit'"
    )
    assert screen.locator(".scene-pic.is-dark").count() == 0  # the picture is not dimmed
    assert screen.locator("[data-testid=dark-badge].is-lit").count() == 1
    host.wait_for_function(
        "document.querySelector('[data-testid=now-dark]').textContent.includes('torch')"
    )
    assert host.inner_text("[data-testid=now-dark]") == "Your torch lights the way."
    assert host.locator(".ct-pic.is-dark").count() == 0
    assert host.inner_text(".ct-ribbon [data-testid=dark-badge]").strip().lower() == "lit"
    _shot(screen, "A09_torch_lit_tv1920")
    host.evaluate("window.scrollTo(0, 0)")
    _shot(host, "A11_torch_lit_phone390")
    assert errors == []


def _quiet_fight(browser: Browser, base: str, errors: list[str]) -> tuple[Page, Page, Page]:
    screen, host, guest = start_fight(browser, base, errors, screen_size=HD)
    split_turn(host, guest)
    screen.wait_for_timeout(1500)
    for page in (screen, host, guest):
        page.evaluate(SPEED)
    return screen, host, guest


def test_a_disadvantaged_attack_shows_two_dice_and_the_reason(
    browser: Browser, combat_server: LiveServer
) -> None:
    errors: list[str] = []
    screen, host, _guest = _quiet_fight(browser, combat_server.base, errors)
    ids = screen.evaluate(IDS)
    me = host.evaluate(MINE)
    foe = ids["foe"] if ids["foe"] != me else ids["hero"]
    miss = {"roller_id": foe, "target_id": me, "rolls": [14, 6], "total": 11, "target": 16}
    for page in (screen, host):
        page.evaluate(ROLL, [9601, {**miss, "success": False}])
    screen.wait_for_function(
        f"document.querySelector('{STRIP}').textContent.includes('DIS')", timeout=6000
    )
    assert "DIS · Darkness" in screen.inner_text(STRIP)
    assert screen.locator(f"{STRIP} .sr-die").count() == 2
    assert screen.locator(f"{STRIP} .sr-die.dropped").count() == 1
    row = screen.locator(LINES).first
    assert row.locator(".sr-die").count() == 2 and row.locator(".sr-die.dropped").count() == 1
    assert "DIS · Darkness" in row.inner_text()
    card = host.wait_for_selector("[data-testid=fight-card]", timeout=4000)
    assert card is not None
    assert host.inner_text("[data-testid=fight-card-tag]") == "DIS · Darkness"
    _shot(screen, "B12g_after_attack_d_tv1920")
    adv = {**miss, "adv": "advantage", "adv_why": ["Hidden"], "rolls": [3, 17], "success": True}
    screen.evaluate(ROLL, [9602, {**adv, "total": 22}])
    screen.wait_for_function(
        f"document.querySelector('{STRIP}').textContent.includes('ADV')", timeout=6000
    )
    assert "ADV · Hidden" in screen.inner_text(STRIP)
    assert errors == []


def test_a_spell_with_no_roll_gets_a_line_on_the_strip_and_in_this_round(
    browser: Browser, combat_server: LiveServer
) -> None:
    errors: list[str] = []
    screen, _host, _guest = _quiet_fight(browser, combat_server.base, errors)
    hero = screen.evaluate(IDS)["hero"]
    before = screen.locator(LINES).count()
    line = "Elowen reads Sleep: Goblin A, Goblin B asleep"
    screen.evaluate(SPELL, [9701, hero, line])
    screen.wait_for_selector("[data-testid=spell-line]", timeout=4000)
    assert screen.inner_text(STRIP).strip() == line
    assert screen.locator(LINES).count() == before + 1
    assert line in screen.locator(LINES).first.inner_text()
    _shot(screen, "D09_after_sleep_tv1920")
    assert errors == []
