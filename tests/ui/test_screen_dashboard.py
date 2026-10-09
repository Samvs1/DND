"""M15.2: the /screen is a dashboard that never scrolls the page, at 1280x720 and 1920x1080."""

from pathlib import Path

from playwright.sync_api import Browser, Page, ViewportSize

from tests.ui.conftest import LiveServer, open_screen
from tests.ui.table_helpers import PHONE, start_fight, start_with_screen

SMALL = ViewportSize(width=1280, height=720)
FULL = ViewportSize(width=1920, height=1080)
NO_SCROLL = (
    "document.documentElement.scrollHeight <= window.innerHeight"
    " && document.documentElement.scrollWidth <= window.innerWidth"
)
# Every listed element must lie fully inside the viewport (1px of slack for rounding).
INSIDE = """(sel) => [...document.querySelectorAll(sel)].every((el) => {
  const r = el.getBoundingClientRect();
  return r.left >= -1 && r.top >= -1 && r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1;
})"""


def _shot(page: Page, shots: Path, name: str) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_function("[...document.images].every((i) => i.complete)")
    page.wait_for_timeout(700)
    page.screenshot(path=str(shots / f"{name}.png"))


def _check_fits(screen: Page) -> None:
    assert screen.evaluate(NO_SCROLL)
    assert screen.evaluate(INSIDE, "[data-testid=zone]")
    assert screen.evaluate(INSIDE, "[data-testid=token]")
    assert screen.evaluate(INSIDE, "[data-testid=party-card]")
    assert screen.locator("[data-testid=screen-invite]").count() == 0
    assert screen.locator("[data-testid=zone]").first.is_visible()


def test_screen_lobby_shows_invite_only_there(browser: Browser, live_server: LiveServer) -> None:
    errors: list[str] = []
    screen = open_screen(browser, live_server.base, errors, SMALL)
    assert screen.locator("[data-testid=lan-url]").first.is_visible()
    assert errors == []


def test_screen_dashboard_exploration(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, _host, _guest = start_with_screen(browser, live_server.base, errors, PHONE, SMALL)
    assert screen.evaluate(NO_SCROLL)
    assert screen.evaluate(INSIDE, "[data-testid=party-card]")
    assert screen.locator("[data-testid=screen-invite]").count() == 0
    assert screen.evaluate(
        "(() => { const f = document.querySelector('.tb.sc .feed');"
        " return f.scrollHeight >= f.clientHeight && getComputedStyle(f).overflowY === 'auto'; })()"
    )
    _shot(screen, shots_dir, "screen_explore_1280x720")
    screen.set_viewport_size(FULL)
    assert screen.evaluate(NO_SCROLL)
    _shot(screen, shots_dir, "screen_explore_1920")
    assert errors == []


def test_screen_dashboard_fight(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, _host, _guest = start_fight(browser, combat_server.base, errors, PHONE, SMALL)
    print(
        screen.evaluate(
            "JSON.stringify([...document.querySelectorAll('.sc-main,.tb-combat,[data-testid=board],.tb-feed')].map(e=>[e.className,e.getBoundingClientRect().height]))"
        )
    )
    _check_fits(screen)
    _shot(screen, shots_dir, "screen_combat_1280x720")
    screen.set_viewport_size(FULL)
    _check_fits(screen)
    _shot(screen, shots_dir, "screen_combat_1920")
    assert errors == []
