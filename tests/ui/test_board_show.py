"""Rolls in a fight play on the board (M26.7, docs/next/GOAL_DICE.md): an attack's die arcs to its
target and the verdict floats over it, told from the party's side; the damage floats up; saves read
SAVED / RESISTED / CAUGHT; the strip spells out the action and THIS ROUND keeps one line per roll,
emptied each round; the phone shows its own fight card, whose verdict waits for the TV."""

from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, ViewportSize

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import WIDE, split_turn, start_fight

FULL_SPEED = "window.__aidmShowScale = 1"
FLOAT = "[data-testid=show-float]"
LINES = "[data-testid=round-line]"
IDS = """() => {
  const s = window.aidm.store.get().snapshot.state;
  const foes = s.combat.tokens.filter((t) => t.side === 'hostile').map((t) => t.creature_id);
  return { hero: s.party[0].id, foe: foes[0] };
}"""
PUSH = """([seq, dice]) => window.aidm.pacer.push({ type: 'dice_roll', seq, dice: {
  expression: '1d20', adv: 'normal', modifier: 5, label: 'Longsword', crit: false, parts: [],
  adv_why: [], ...dice } })"""
HURT = """([seq, id, amount]) => window.aidm.pacer.push({ type: 'event', seq, kind: 'damage_taken',
  line: '', subject_id: id, amount })"""
MINE = "async () => (await import('/web/js/combat/model.js')).myCreatureId(window.aidm.store.get())"


def _quiet_fight(
    browser: Browser, base: str, errors: list[str], size: ViewportSize = WIDE
) -> tuple[Page, Page, Page]:
    """A fight on a player's turn (the server waits for them: no goblin rolls arrive), the shows
    queued so far played out, then full speed."""
    screen, host, guest = start_fight(browser, base, errors, screen_size=size)
    split_turn(host, guest)
    screen.wait_for_timeout(1500)
    for page in (screen, host, guest):
        page.evaluate(FULL_SPEED)
    return screen, host, guest


def _float_text(screen: Page, word: str) -> str:
    screen.wait_for_function(
        f"[...document.querySelectorAll('{FLOAT}')].some((f) => f.textContent.includes('{word}'))",
        timeout=6000,
    )
    return " ".join(screen.locator(FLOAT).all_inner_texts())


def test_an_attack_lands_on_its_target_and_the_damage_floats_up(
    browser: Browser, combat_server: LiveServer
) -> None:
    errors: list[str] = []
    screen, _host, _guest = _quiet_fight(browser, combat_server.base, errors)
    ids = screen.evaluate(IDS)
    before = screen.locator(LINES).count()
    hit = {"kind": "attack", "roller_id": ids["hero"], "target_id": ids["foe"], "rolls": [15]}
    screen.evaluate(PUSH, [9201, {**hit, "total": 20, "target": 13, "success": True}])
    screen.wait_for_selector(".sb-host [data-testid=show-die]", timeout=3000)  # the die arcs
    assert "HIT" in _float_text(screen, "HIT")
    strip = screen.locator("[data-testid=show-strip]").inner_text()
    assert "vs AC 13" in strip and "20" in strip
    assert screen.locator(LINES).count() == before + 1
    assert screen.locator("[data-testid=screen-dice]").is_hidden()  # the old card stays out of it
    screen.evaluate(HURT, [9202, ids["foe"], 7])
    assert "-7" in _float_text(screen, "-7")
    screen.wait_for_function(
        f"document.querySelector('{LINES} .sr-chip').textContent.includes('7')", timeout=3000
    )
    miss = {"kind": "attack", "roller_id": ids["foe"], "target_id": ids["hero"], "rolls": [4]}
    screen.evaluate(PUSH, [9203, {**miss, "total": 8, "target": 16, "success": False}])
    hero = screen.evaluate("(id) => window.aidm.store.get().snapshot.state.party[0].name", None)
    assert f"MISSED {hero.upper()}" in _float_text(screen, "MISSED")
    assert screen.locator(LINES).count() == before + 2
    assert errors == []


def test_saves_read_from_the_party_side_and_this_round_empties_each_round(
    browser: Browser, combat_server: LiveServer
) -> None:
    errors: list[str] = []
    screen, _host, _guest = _quiet_fight(browser, combat_server.base, errors)
    ids = screen.evaluate(IDS)
    before = screen.locator(LINES).count()
    save = {"kind": "save", "label": "DEX save", "target": 13, "modifier": 2}
    foe = {**save, "roller_id": ids["foe"], "rolls": [14], "total": 16, "success": True}
    screen.evaluate(PUSH, [9301, foe])
    assert "RESISTED" in _float_text(screen, "RESISTED")
    hero = {**save, "roller_id": ids["hero"], "rolls": [3], "total": 5, "success": False}
    screen.evaluate(PUSH, [9302, hero])
    assert "FAILED" in _float_text(screen, "FAILED")
    screen.wait_for_function(
        f"document.querySelectorAll('{LINES}').length === {before + 2}", timeout=4000
    )
    assert screen.locator("[data-testid=this-round]").is_visible()
    screen.evaluate(
        """() => { const s = window.aidm.store.get(); const st = s.snapshot.state;
        window.aidm.store.update({ snapshot: { ...s.snapshot, state: { ...st,
          combat: { ...st.combat, round: st.combat.round + 1 } } } }); }"""
    )
    assert screen.locator(LINES).count() == 0
    assert errors == []


OVERLAPS = """() => {
  const box = (el) => el.getBoundingClientRect();
  const hit = (a, b) =>
    a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
  const words = [...document.querySelectorAll('[data-testid=show-float] .sb-word')].map(box);
  const names = [...document.querySelectorAll('.board .hex-name')].map(box);
  const out = [];
  words.forEach((w, i) => {
    names.forEach((n) => { if (hit(w, n)) out.push('word over a zone name'); });
    words.slice(i + 1).forEach((o) => { if (hit(w, o)) out.push('word over a word'); });
  });
  return out;
}"""
TWO_FOES = """() => {
  const all = window.aidm.store.get().snapshot.state.combat.tokens;
  const tokens = all.filter((t) => t.side === 'hostile');
  const zone = tokens.find((t) => tokens.some((o) => o !== t && o.zone_id === t.zone_id)).zone_id;
  return tokens.filter((t) => t.zone_id === zone).map((t) => t.creature_id).slice(0, 2);
}"""


@pytest.mark.parametrize("width,height", [(1280, 720), (1920, 1080)])
def test_stacked_floats_keep_the_zone_name_readable(
    browser: Browser, combat_server: LiveServer, shots_dir: Path, width: int, height: int
) -> None:
    errors: list[str] = []
    size = ViewportSize(width=width, height=height)
    screen, _host, _guest = _quiet_fight(browser, combat_server.base, errors, size)
    first, second = screen.evaluate(TWO_FOES)
    save = {"kind": "save", "label": "DEX save", "target": 13, "modifier": 2}
    resisted = {**save, "roller_id": first, "rolls": [14], "total": 16, "success": True}
    caught = {**save, "roller_id": second, "rolls": [3], "total": 5, "success": False}
    screen.evaluate(PUSH, [9501, resisted])
    screen.evaluate(PUSH, [9502, caught])
    screen.wait_for_function(
        f"document.querySelectorAll('{FLOAT} .sb-word').length === 2", timeout=6000
    )
    screen.wait_for_timeout(250)  # the second float's pop-in is over
    screen.screenshot(path=str(shots_dir / f"board_stacked_floats_{width}.png"))
    assert screen.evaluate(OVERLAPS) == []
    assert errors == []


def test_the_phone_card_shows_an_attack_on_me_after_the_tv(
    browser: Browser, combat_server: LiveServer
) -> None:
    errors: list[str] = []
    _screen, host, _guest = _quiet_fight(browser, combat_server.base, errors)
    me = host.evaluate(MINE)
    foe = host.evaluate(IDS)["foe"]
    attack = {"kind": "attack", "roller_id": foe, "target_id": me, "rolls": [4], "total": 8}
    host.evaluate(PUSH, [9401, {**attack, "target": 16, "success": False}])
    card = host.wait_for_selector("[data-testid=fight-card]", timeout=3000)
    assert card is not None and "attacks you" in card.inner_text()
    verdict = host.locator("[data-testid=fight-card-verdict]")
    assert verdict.is_hidden()  # the TV's die is still in the air
    host.wait_for_selector("[data-testid=fight-card-verdict]:not([hidden])", timeout=3000)
    assert verdict.inner_text() == "MISSED YOU"
    assert host.locator("[data-testid=dice-toast]").is_hidden()  # an attack has its card
    assert errors == []
