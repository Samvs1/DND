"""Browser tests of the combat view and hotbar: two players, an ambush starts a fight (M7.4)."""

from pathlib import Path

from playwright.sync_api import Browser, Locator, Page, ViewportSize

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import PHONE, WIDE, snap, start_table

MAIN = "[data-testid=slot-attack-main_hand]"
WAIT = "[data-testid=hotbar-wait]"
COMBAT_POS = (
    "(() => { const c = window.aidm.store.get().snapshot.state.combat;"
    " return c ? [c.round, c.active_id] : null; })()"
)


def _fight(browser: Browser, base: str, size: ViewportSize, errors: list[str]) -> tuple[Page, Page]:
    host, guest = start_table(browser, base, size, errors)
    host.fill("[data-testid=action-input]", "I ambush the goblins from the shadows")
    host.click("[data-testid=action-send]")
    for page in (host, guest):
        page.wait_for_selector("[data-testid=board]:not([hidden])", timeout=30000)
        page.wait_for_selector(f"{MAIN}, {WAIT}", timeout=30000)
    return host, guest


def _split(host: Page, guest: Page) -> tuple[Page, Page]:
    """(active page, other page); waits until one of them has the hotbar."""
    for _ in range(100):
        if host.locator(MAIN).count():
            return host, guest
        if guest.locator(MAIN).count():
            return guest, host
        host.wait_for_timeout(200)
    raise AssertionError("nobody got the hotbar")


def _has_hit_chance(page: Page) -> Locator:
    """Wait for the previews; return an attack slot that shows a percentage (in range)."""
    page.wait_for_function(
        "[...document.querySelectorAll('[data-testid^=slot-attack-] [data-testid=slot-sub]')]"
        ".some((n) => n.textContent.includes('%'))",
        timeout=20000,
    )
    return page.locator("[data-testid^=slot-attack-]", has_text="%").first


def test_two_players_fight_attack_move_suggest_and_end_turn(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, guest = _fight(browser, combat_server.base, WIDE, errors)
    active, other = _split(host, guest)
    for page in (host, guest):
        assert page.locator("[data-testid=zone]").count() >= 3
        assert page.locator("[data-testid=token][data-side=hostile]").count() == 2
        assert page.locator("[data-testid=init-entry]").count() == 4
        assert page.locator("[data-testid=init-entry].current").count() == 1
        assert "Round 1" in page.locator("[data-testid=round]").inner_text()
        states = page.locator("[data-testid=enemy-state]").all_inner_texts()
        assert states and all(s in ("Unhurt", "Wounded", "Bloodied") for s in states)
    srcs = active.eval_on_selector_all(
        "[data-testid=token][data-side=hostile] img.tk-art", "els => els.map((e) => e.src)"
    )
    assert srcs and all("goblin" in s for s in srcs), srcs
    # The active player sees hit chances and the action pips; the other one cannot act.
    swing = _has_hit_chance(active)
    assert active.locator("[data-testid=pip-action].on").count() == 1
    swing.hover()
    tip = swing.locator(".hb-tip").inner_text()
    assert "AC" in tip and "Hits" in tip
    assert other.locator(WAIT).is_visible()
    assert other.locator("[data-testid=end-turn]").count() == 0
    # The other player suggests; the active one sees it.
    other.fill("[data-testid=suggest-input]", "go for the left goblin")
    other.click("[data-testid=suggest-send]")
    active.wait_for_selector("[data-testid=suggestion]", timeout=10000)
    assert "left goblin" in active.locator("[data-testid=suggestion]").first.inner_text()
    # Attack: the action pip is spent (or one attack is left).
    swing.click()
    active.wait_for_selector("[data-testid=pip-action].spent", timeout=20000)
    active.wait_for_selector("[data-testid=event-line]", timeout=20000)
    # Move to another zone the hero can reach.
    go = active.locator(
        "[data-testid=zone]:has([data-testid=move-cost]:not(.far)) [data-testid=zone-go]"
    )
    if go.count():
        before = active.locator("[data-testid=pip-move]").inner_text()
        go.first.click()
        active.wait_for_function(
            f"document.querySelector('[data-testid=pip-move]').innerText !== {before!r}",
            timeout=20000,
        )
    # Keyboard shortcut: the first slot has number key 1.
    assert active.locator(f"{MAIN} .hb-key").inner_text() == "1"
    snap(host, shots_dir, "combat_board", 1280)
    before = active.evaluate(f"JSON.stringify({COMBAT_POS})")
    active.click("[data-testid=end-turn]")
    # The turn passes (a downed partner is skipped, so the round may roll over instead).
    active.wait_for_function(f"JSON.stringify({COMBAT_POS}) !== {before!r}", timeout=45000)
    assert errors == []


def _fighter_turn(host: Page, guest: Page) -> None:
    """Pass the rogue's turns until the host's fighter has the hotbar."""
    for _ in range(60):
        if host.locator(MAIN).count():
            return
        if guest.locator("[data-testid=end-turn]").count():
            guest.click("[data-testid=end-turn]")
            guest.wait_for_selector("[data-testid=end-turn]", state="detached", timeout=30000)
        host.wait_for_timeout(500)
    raise AssertionError("the fighter never got a turn")


def test_fighter_feature_actions_on_the_hotbar(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, guest = _fight(browser, combat_server.base, WIDE, errors)
    _fighter_turn(host, guest)
    _has_hit_chance(host)
    wind = host.locator("[data-testid=slot-feat-second-wind]")
    assert wind.locator("[data-testid=slot-sub]").inner_text() == "1 of 1 left"
    assert "Bonus action" in wind.locator(".hb-tip").inner_text()
    snap(host, shots_dir, "combat_hotbar", 1280)
    hurt = host.evaluate(
        "(() => { const s = window.aidm.store.get().sheet.sheet; return s.hp < s.max_hp; })()"
    )
    wind.click()
    if hurt:
        host.wait_for_function(
            "document.querySelector('[data-testid=slot-feat-second-wind] [data-testid=slot-sub]')"
            ".textContent === '0 of 1 left'",
            timeout=20000,
        )
        assert host.locator("[data-testid=pip-bonus].spent").count() == 1
    else:
        host.wait_for_function(
            "document.querySelector('[data-testid=hotbar-note]').textContent.length > 0",
            timeout=20000,
        )
        assert host.locator("[data-testid=hotbar-note]").inner_text().startswith("Already at full")
    assert errors == []


def test_refusal_is_friendly_text_and_escape_cancels_aiming(
    browser: Browser, combat_server: LiveServer
) -> None:
    errors: list[str] = []
    host, guest = _fight(browser, combat_server.base, WIDE, errors)
    active, _other = _split(host, guest)
    _has_hit_chance(active)
    active.click("[data-testid=slot-throw]")
    active.wait_for_selector("[data-testid=aim-bar] [data-testid=aim-cancel]")
    active.keyboard.press("Escape")
    active.wait_for_selector("[data-testid=aim-cancel]", state="detached")
    # Dodge twice: the second one is refused with friendly wording, never a code or raw text.
    active.click("[data-testid=slot-dodge]")
    active.wait_for_selector("[data-testid=pip-action].spent", timeout=20000)
    active.evaluate(
        """() => window.aidm.dispatch({type: 'error', code: 'refused', text: 'raw server words',
            refusal: 'no_action'})"""
    )
    note = active.locator("[data-testid=hotbar-note]")
    active.wait_for_function(
        "document.querySelector('[data-testid=hotbar-note]').textContent.length > 0"
    )
    assert note.inner_text() == "You have already used your action."
    assert "raw server" not in active.locator("body").inner_text()
    assert errors == []


def test_phone_layout_in_a_fight(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, guest = _fight(browser, combat_server.base, PHONE, errors)
    active, other = _split(host, guest)
    _has_hit_chance(active)
    for page in (active, other):
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    snap(active, shots_dir, "combat_hotbar", 390)
    snap(other, shots_dir, "combat_board", 390)
    assert errors == []
