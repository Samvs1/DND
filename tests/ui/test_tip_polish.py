"""M28.6 polish: a '?' never covers or clips content or crowds another tap target.

Also takes the review shots into artifacts/ui/m28_6/fix/ at 390x844 and 393x702.
"""

import pytest
from playwright.sync_api import Browser, Page, ViewportSize

from tests.ui.conftest import SHOTS, LiveServer
from tests.ui.table_helpers import (
    PHONE,
    go_tab,
    has_hit_chance,
    split_turn,
    start_fight,
    start_table,
)
from tests.ui.test_combat_view import NO_HSCROLL
from tests.ui.test_panels import _merchant, _open
from tests.ui.test_sheet import WIZARD
from tests.ui.test_sheet import _open as open_hero
from tests.ui.wizard_helpers import HeroSpec

OUT = SHOTS / "m28_6" / "fix"
SHORT = ViewportSize(width=393, height=702)
SIZES = pytest.mark.parametrize("size", [PHONE, SHORT], ids=["390", "393x702"])
POP = "[data-testid=tip-pop]"
LIVE = ".tip-btn:not([hidden])"
# the line boxes of a node's text (Range rects), then the box of one element
TEXT_BOX = """(el) => { const r = document.createRange(); r.selectNodeContents(el);
  return [...r.getClientRects()].map(
    (b) => ({ l: b.left, r: b.right, t: b.top, b: b.bottom })); }"""
BOX = """(el) => { const b = el.getBoundingClientRect();
  return { l: b.left, r: b.right, t: b.top, b: b.bottom }; }"""


def _shot(page: Page, name: str, size: ViewportSize) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.wait_for_function("[...document.images].every((i) => i.complete)")
    page.wait_for_timeout(700)
    page.screenshot(path=str(OUT / f"{name}_{size['width']}x{size['height']}.png"))


def _clear(lines: list[dict[str, float]], mark: dict[str, float], gap: float = 4) -> bool:
    """On the mark's own line the text ends `gap` px before it; other lines must not meet it."""
    for line in lines:
        overlap = min(line["b"], mark["b"]) - max(line["t"], mark["t"])
        if overlap > (line["b"] - line["t"]) / 2:
            if not (line["r"] + gap <= mark["l"] or mark["r"] + gap <= line["l"]):
                return False
        elif not _apart(line, mark, -1):
            return False
    return True


def _apart(a: dict[str, float], b: dict[str, float], gap: float = 0) -> bool:
    """True when the two boxes are at least `gap` px apart."""
    return (
        a["r"] + gap <= b["l"]
        or b["r"] + gap <= a["l"]
        or a["b"] + gap <= b["t"]
        or b["b"] + gap <= a["t"]
    )


def _hero(browser: Browser, base: str, size: ViewportSize) -> tuple[Page, list[str]]:
    errors: list[str] = []
    _host, guest = start_table(
        browser, base, size, errors, specs=(HeroSpec(name="Brienne"), WIZARD)
    )
    open_hero(guest)
    return guest, errors


@SIZES
def test_shop_name_and_question_mark_do_not_overlap(
    browser: Browser, live_server: LiveServer, size: ViewportSize
) -> None:
    errors: list[str] = []
    host, guest = start_table(browser, live_server.base, size, errors)
    _merchant(live_server, 400)
    host.wait_for_selector("[data-testid=open-shop]:not([hidden])", timeout=20000)
    _open(host, "shop")
    host.click("[data-testid=shop-visit]")
    host.wait_for_selector("[data-testid=vote]:not([hidden])", timeout=20000)
    guest.wait_for_selector("[data-testid=vote-ready]", timeout=20000)
    guest.click("[data-testid=vote-ready]")
    line = "[data-testid=shop-stock] [data-testid=shop-line]"
    host.wait_for_selector(f"{line} {LIVE}", timeout=30000)
    host.evaluate(  # a long name must wrap before the '?'
        "() => { const s = document.querySelector('[data-testid=shop-line] strong');"
        " s.textContent = 'Wooden staff of the long road to nowhere in particular'; }"
    )
    rows = host.locator(line)
    for i in range(rows.count()):
        name = rows.nth(i).locator("strong").evaluate(TEXT_BOX)
        mark = rows.nth(i).locator(LIVE).evaluate(BOX)
        assert _clear(name, mark), (i, name, mark)
    assert host.evaluate(NO_HSCROLL)
    _shot(host, "shop", size)
    host.locator(f"{line} {LIVE}").last.click()
    host.wait_for_selector(POP)
    _shot(host, "shop_tip_bottom", size)
    assert errors == []


@SIZES
def test_spellbook_name_gap_and_tip_stays_above_the_strip(
    browser: Browser, live_server: LiveServer, size: ViewportSize
) -> None:
    guest, errors = _hero(browser, live_server.base, size)
    guest.click("[data-testid=tab-spells]")
    guest.wait_for_selector("[data-testid=spell-line] .tip-btn:not([hidden])")
    lines = guest.locator("[data-testid=spell-line]")
    for i in range(lines.count()):
        name = lines.nth(i).locator("strong").evaluate(TEXT_BOX)
        mark = lines.nth(i).locator(LIVE).first.evaluate(BOX)
        assert _clear(name, mark), (i, name, mark)
    _shot(guest, "spellbook", size)
    guest.locator("[data-testid=spell-line]").last.scroll_into_view_if_needed()
    guest.locator("[data-testid=spell-line]").last.locator(LIVE).first.click()
    guest.wait_for_selector(POP)
    pop = guest.locator(POP).evaluate(BOX)
    strip = guest.locator("[data-testid=strip]").evaluate(BOX)
    assert pop["b"] <= strip["t"], (pop, strip)
    _shot(guest, "spell_tip_bottom", size)
    assert errors == []


@SIZES
def test_hotbar_mark_is_off_the_art_strip_is_spaced_and_moves_tips_sit_by_badges(
    browser: Browser, combat_server: LiveServer, size: ViewportSize
) -> None:
    errors: list[str] = []
    _screen, host, guest = start_fight(browser, combat_server.base, errors, size)
    active, _other = split_turn(host, guest)
    has_hit_chance(active)
    active.wait_for_selector(".hb-cell .tip-btn:not([hidden])")
    cells = active.locator(".hb-cell")
    for i in range(cells.count()):
        art = cells.nth(i).locator(".hb-art")
        mark = cells.nth(i).locator(LIVE)
        if art.count() and mark.count():
            assert _apart(art.first.evaluate(BOX), mark.first.evaluate(BOX)), i
            box = mark.first.bounding_box()
            assert box is not None and box["width"] >= 24 and box["height"] >= 24
    mark = cells.locator(LIVE).first
    mark.click()
    active.wait_for_selector(POP)
    _shot(active, "hotbar_tip_open", size)
    active.click("[data-testid=tip-close]")
    ready = active.locator("[data-testid=status-chip]").evaluate(BOX)
    strip_marks = active.locator(f"[data-testid=strip] {LIVE}")
    assert strip_marks.count() == 2
    shield = active.locator("[data-testid=strip-ac]").evaluate(BOX)
    for i in range(2):
        box = strip_marks.nth(i).evaluate(BOX)
        assert _apart(ready, box, 8), (ready, box)
        assert _apart(shield, box, 7), (shield, box)
    assert active.evaluate(NO_HSCROLL)
    _shot(active, "strip", size)
    go_tab(active, "play")
    for _ in range(40):
        if active.locator("[data-testid=zone-chip]").count():
            break
        active.wait_for_timeout(200)
    for cell in active.locator(".ct-place-cell").all():
        chip = cell.locator("[data-testid=zone-chip]").evaluate(BOX)
        marks = cell.locator(LIVE)
        assert marks.count() == 1
        assert _apart(chip, marks.first.evaluate(BOX)), (chip, marks.first.evaluate(BOX))
    chip = active.locator("[data-testid=zone-chip]:not([disabled])")
    if chip.count():
        box = chip.first.bounding_box()
        assert box is not None
        active.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        assert active.locator(POP).count() == 0
    _shot(active, "moves", size)
    assert errors == []
