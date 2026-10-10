"""The phone fits the visible viewport (M16.3) and is a controller, not a second screen (M18.2).

M18.2 owner report: in Brave on Android the bottom toolbar lies over the page, so the tab bar sits
at the TOP, an open vote is a card under it, and nothing important is pinned to the bottom. The
Play tab shows no story text (the screen tells it); the story is under Journal, Story.
"""

from pathlib import Path

from playwright.sync_api import Browser, Page, ViewportSize

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import go_tab, split_turn, start_fight, start_table

SMALL = ViewportSize(width=393, height=702)
TALL = ViewportSize(width=390, height=844)
TABS = "[data-testid=ct-tabs]"
PLAY = "[data-testid=pane-play]"
STORY = "[data-testid=last-line]"
TOOLBAR = 80  # about what Brave's bottom toolbar covers, in CSS px


def tabs_on_top(page: Page) -> None:
    height = page.evaluate("window.innerHeight")
    box = page.locator(TABS).bounding_box()
    assert box is not None
    assert box["y"] >= 0 and box["y"] + box["height"] <= 0.4 * height  # under the strip
    assert page.evaluate("document.scrollingElement.scrollHeight") <= height + 1


def shot(page: Page, shots: Path, name: str) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    page.screenshot(path=str(shots / f"{name}.png"))


def test_phone_play_tab_is_a_controller_393x702(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, _guest = start_table(browser, live_server.base, SMALL, errors)
    tabs_on_top(host)
    host.locator("[data-testid=now-card]").wait_for()
    assert host.locator(f"{PLAY} {STORY}").count() == 0  # no story text on the Play tab
    action = host.locator("[data-testid=action-input]").bounding_box()
    assert action is not None and action["y"] + action["height"] < 702 - TOOLBAR
    talk = host.locator("[data-testid=idea-chip][data-kind=talk]").first
    talk.wait_for()
    name = talk.inner_text().strip()
    talk.click()
    assert host.input_value("[data-testid=action-input]") == f"I talk to {name}."
    assert host.evaluate("window.aidm.store.get().snapshot.state.queue.length") == 0  # never sent
    assert host.locator("[data-testid=idea-chip][data-kind=look]").count() == 1
    shot(host, shots_dir, "phone_play_393x702")
    host.evaluate("window.aidm.store.update({ fallback: true })")
    host.wait_for_selector("#banner .banner")
    tabs_on_top(host)
    shot(host, shots_dir, "phone_play_banner_393x702")
    host.evaluate("window.aidm.store.update({ fallback: false })")
    go_tab(host, "journal")
    host.click("[data-testid=jtab-story]")
    host.wait_for_function(
        "document.querySelector('[data-testid=story-panel] [data-testid=last-line]')"
        ".textContent.trim().length > 20"
    )
    shot(host, shots_dir, "phone_journal_story_393x702")
    host.set_viewport_size(TALL)
    go_tab(host, "play")
    host.wait_for_timeout(300)
    tabs_on_top(host)
    shot(host, shots_dir, "phone_play_390x844")
    assert errors == []


def test_phone_vote_card_sits_under_the_tab_bar(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, guest = start_table(browser, live_server.base, SMALL, errors)
    host.fill("[data-testid=action-input]", "We take a short rest")
    host.click("[data-testid=action-send]")
    card = guest.locator("[data-testid=vote]")
    card.wait_for(timeout=15000)
    box = card.bounding_box()
    assert box is not None and box["y"] + box["height"] < 702 - TOOLBAR
    shot(guest, shots_dir, "phone_vote_393x702")
    assert errors == []


def test_phone_fight_393x702_and_390x844(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    _screen, host, guest = start_fight(browser, combat_server.base, errors, SMALL)
    tabs_on_top(host)
    assert not host.locator("[data-testid=ideas]").is_visible()
    active, waiting = split_turn(host, guest)
    waiting.wait_for_function(
        "document.querySelector('[data-testid=now-place]').textContent.startsWith('Round ')"
    )
    assert not waiting.locator("[data-testid=action-input]").is_visible()  # not my turn
    shot(waiting, shots_dir, "phone_combat_393x702")
    assert active.locator("[data-testid=now-card][data-status=mine]").is_visible()
    shot(active, shots_dir, "phone_combat_myturn_393x702")
    host.set_viewport_size(TALL)
    go_tab(host, "play")
    assert host.locator("[data-testid=hotbar]").is_visible()
    tabs_on_top(host)
    shot(host, shots_dir, "phone_combat_390x844")
    assert errors == []
