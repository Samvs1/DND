"""M16.3: the phone controller fits the visible viewport (tab bar inside, no page scroll)."""

from pathlib import Path

from playwright.sync_api import Browser, Page, ViewportSize

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import go_tab, start_fight, start_table

SMALL = ViewportSize(width=393, height=702)
TALL = ViewportSize(width=390, height=844)
TABS = "[data-testid=ct-tabs]"
BOX = "[data-testid=last-line]"


def tabs_inside(page: Page) -> None:
    height = page.evaluate("window.innerHeight")
    box = page.locator(TABS).bounding_box()
    assert box is not None
    assert box["y"] >= 0 and box["y"] + box["height"] <= height + 1
    assert page.evaluate("document.scrollingElement.scrollHeight") <= height + 1


def shot(page: Page, shots: Path, name: str) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    page.screenshot(path=str(shots / f"{name}.png"))


def test_phone_fit_393x702_tab_bar_banner_and_story_box(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, _guest = start_table(browser, live_server.base, SMALL, errors)
    tabs_inside(host)
    box = host.locator(BOX).bounding_box()
    assert box is not None and box["height"] > 0.4 * 702
    action = host.locator(".ct-action").bounding_box()
    assert action is not None and action["y"] - (box["y"] + box["height"]) <= 24 + 80
    shot(host, shots_dir, "phone_play_393x702")
    host.evaluate("window.aidm.store.update({ fallback: true })")
    host.wait_for_selector("#banner .banner")
    tabs_inside(host)
    shot(host, shots_dir, "phone_play_banner_393x702")
    host.evaluate("window.aidm.store.update({ fallback: false })")
    long_text = "A long tale told in many words. " * 19
    host.evaluate(
        "(text) => window.aidm.dispatch({ type: 'narration_chunk', id: 'long1', index: 0,"
        " text, audio_url: null, tone: 'calm' })",
        long_text,
    )
    host.wait_for_function(
        "(n) => document.querySelector('[data-testid=last-line]').textContent.includes(n)",
        arg=long_text.strip()[:200],
    )
    tabs_inside(host)
    assert host.evaluate(f"document.querySelector('{BOX}').scrollHeight") >= 40
    host.set_viewport_size(TALL)
    host.wait_for_timeout(300)
    tabs_inside(host)
    shot(host, shots_dir, "phone_play_390x844")
    assert errors == []


def test_phone_fit_390x844_play_and_combat(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    _screen, host, _guest = start_fight(browser, combat_server.base, errors, SMALL)
    tabs_inside(host)
    shot(host, shots_dir, "phone_combat_393x702")
    host.set_viewport_size(TALL)
    go_tab(host, "play")
    assert host.locator("[data-testid=hotbar]").is_visible()
    tabs_inside(host)
    shot(host, shots_dir, "phone_combat_390x844")
    assert errors == []
