"""Browser tests of the phone controller (/play at 390x844) next to the shared /screen (M11.4)."""

import re
from pathlib import Path

from playwright.sync_api import Browser, Page

from aidm.models.damage import DamagePacket, DamageType
from aidm.rules.damage import resolve_damage
from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import (
    COMBAT_POS,
    HD,
    PHONE,
    go_tab,
    has_hit_chance,
    snap,
    split_turn,
    start_fight,
    start_with_screen,
)
from tests.ui.wizard_helpers import HeroSpec, complete_wizard, join

NO_HSCROLL = "document.documentElement.scrollWidth <= window.innerWidth"
TABS = ("play", "hero", "journal", "scribe", "more")
PANE = "[data-testid=pane-{}]"
ACTION_ENABLED = "!document.querySelector('[data-testid=action-input]').disabled"
CHIP = "document.querySelector('[data-testid=status-chip]').textContent"


def test_tab_navigation_shows_one_pane_and_never_scrolls_sideways(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, guest = start_with_screen(browser, live_server.base, errors, size=PHONE)
    assert host.locator(PANE.format("play")).is_visible()  # Play is the default tab
    assert host.locator("[data-testid=strip-name]").inner_text() == "Brienne"
    ac = host.locator("[data-testid=strip-ac]").inner_text()
    assert re.fullmatch(r"AC\s+\d+", ac.strip()), ac  # "AC" over the number on the shield (M24)
    assert host.locator("[data-testid=status-chip]").inner_text().strip()
    assert host.locator("[data-testid=hp-text]").inner_text() == "10/10"
    # Tab icons come from the manifest: owner art for play, M12.2 art for more (each falls back to
    # its placeholder while the file is missing, see test_placeholder_only).
    icon = "[data-testid=ct-tab-{}] img.ct-tab-icon"
    assert (
        host.locator(icon.format("play")).get_attribute("src") == "/static/img/icons/tabs/feed.png"
    )
    assert host.locator(icon.format("more")).get_attribute("src") == (
        "/static/img/icons/tabs/more.png"
    )
    for name in TABS:
        go_tab(host, name)
        for other in TABS:
            assert host.locator(PANE.format(other)).is_visible() == (other == name), (name, other)
        assert host.evaluate(NO_HSCROLL), name
        assert host.locator("[data-testid=strip]").is_visible()  # the hero strip is persistent
        snap(host, shots_dir, f"controller_{name}", 390)
    # Journal tab: journal and map are sub-tabs.
    go_tab(host, "journal")
    assert host.locator("[data-testid=journal]").is_visible()
    host.click("[data-testid=jtab-map]")
    assert host.locator("[data-testid=map]").is_visible()
    assert host.locator("[data-testid=journal]").is_hidden()
    # More tab: the host sees the host panel button, a guest does not; everyone has the hero file.
    go_tab(host, "more")
    assert host.locator("[data-testid=open-host]").is_visible()
    assert host.locator("[data-testid=export-hero]").is_visible()
    assert host.locator("[data-testid=leave-info]").is_visible()
    go_tab(guest, "more")
    assert guest.locator("[data-testid=open-host]").is_hidden()
    snap(screen, shots_dir, "screen_with_phones", 1280)
    assert errors == []


def test_play_tab_has_the_action_box_voice_slot_and_story_box(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    _screen, host, _guest = start_with_screen(browser, live_server.base, errors)
    box = host.locator("[data-testid=action-input]")
    assert box.is_visible() and host.locator("[data-testid=action-send]").is_visible()
    assert host.locator("[data-testid=mic-slot]").count() == 1
    voice = host.evaluate(
        "window.isSecureContext && !!(window.SpeechRecognition || window.webkitSpeechRecognition)"
    )
    assert host.locator("[data-testid=mic-slot]").is_visible() == voice
    hint = host.locator("[data-testid=dictation-hint]")
    assert hint.is_visible() != voice
    assert hint.inner_text() == "Tip: use the microphone key on your keyboard to dictate."
    # The story box shows the recent story in full; there is no tap-to-open dialog any more.
    assert host.locator("[data-testid=last-line] p").count() >= 1
    assert host.locator("[data-testid=recent-dialog]").count() == 0
    # Shift+Enter adds a line, Enter sends and clears the box.
    box.click()
    host.keyboard.type("first line")
    host.keyboard.press("Shift+Enter")
    host.keyboard.type("second line")
    assert box.input_value() == "first line\nsecond line"
    host.keyboard.press("Enter")
    host.wait_for_function("document.querySelector('[data-testid=action-input]').value === ''")
    assert errors == []


def test_action_from_a_phone_appears_in_the_screen_feed(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, guest = start_with_screen(browser, live_server.base, errors, screen_size=HD)
    # The "writing your campaign" notice goes as soon as play starts, it never hangs over the story.
    for page in (screen, host, guest):
        assert "writing your campaign" not in page.inner_text("[data-testid=notices]")
    before = screen.locator("[data-testid=narration]").count()
    told = guest.evaluate("window.aidm.story.items.length")
    host.fill("[data-testid=action-input]", "I knock on the harbour door")
    host.click("[data-testid=action-send]")
    screen.wait_for_function(
        f"document.querySelectorAll('[data-testid=narration]').length > {before}", timeout=20000
    )
    # Every phone follows the story through its last line, the box is free again afterwards.
    guest.wait_for_function(f"window.aidm.story.items.length > {told}", timeout=20000)
    assert guest.inner_text("[data-testid=last-line]").strip()
    host.wait_for_function(ACTION_ENABLED, timeout=20000)
    assert host.locator("[data-testid=action-input]").input_value() == ""
    assert host.evaluate(CHIP) == "Ready"
    snap(screen, shots_dir, "m11_screen_feed", 1920)
    snap(host, shots_dir, "m11_phone_after_action", 390)
    assert errors == []


def test_a_second_phone_queues_behind_the_first(
    browser: Browser, slow_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, guest = start_with_screen(browser, slow_server.base, errors, screen_size=HD)
    host.fill("[data-testid=action-input]", "I slowly examine the old door")
    host.click("[data-testid=action-send]")
    screen.wait_for_selector("[data-testid=floor-acting]", timeout=20000)
    assert "Brienne is acting" in screen.inner_text("[data-testid=floor-acting]")
    guest.fill("[data-testid=action-input]", "I wait by the fire")
    guest.click("[data-testid=action-send]")
    screen.wait_for_selector("[data-testid=floor-queue] li", timeout=20000)
    assert "Mira" in screen.inner_text("[data-testid=floor-queue]")
    assert screen.locator("[data-testid=floor-queue] li").count() == 1
    guest.wait_for_function(
        "document.querySelector('[data-testid=queue-place]').textContent !== ''"
    )
    assert "number 1" in guest.inner_text("[data-testid=queue-place]")
    assert guest.locator("[data-testid=action-input]").is_disabled()
    assert guest.locator("[data-testid=status-chip]").inner_text() == "Waiting (1)"
    assert "Brienne is acting" in screen.inner_text("[data-testid=screen-floor]")
    snap(screen, shots_dir, "m11_screen_queue", 1920)
    snap(guest, shots_dir, "controller_queue", 390)
    # Both actions play out in order and the queue empties.
    guest.wait_for_function(ACTION_ENABLED, timeout=60000)
    screen.wait_for_selector("[data-testid=floor-queue]", state="detached", timeout=60000)
    assert errors == []


def test_typing_indicator_reaches_the_screen(browser: Browser, live_server: LiveServer) -> None:
    errors: list[str] = []
    screen, host, _guest = start_with_screen(browser, live_server.base, errors)
    host.click("[data-testid=action-input]")
    host.keyboard.type("I am thinking about my next step")
    screen.wait_for_selector("[data-testid=floor-typing]", timeout=10000)
    assert "Brienne is typing" in screen.inner_text("[data-testid=floor-typing]")
    # Clearing the box (or leaving it) stops the indicator at once.
    host.fill("[data-testid=action-input]", "")
    screen.wait_for_selector("[data-testid=floor-typing]", state="detached", timeout=10000)
    host.keyboard.type("again")
    screen.wait_for_selector("[data-testid=floor-typing]", timeout=10000)
    host.click("[data-testid=ct-tab-hero]")  # focus leaves the box (blur)
    screen.wait_for_selector("[data-testid=floor-typing]", state="detached", timeout=10000)
    assert errors == []


def test_a_combat_turn_is_played_entirely_from_the_phone(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, guest = start_fight(browser, combat_server.base, errors, screen_size=HD)
    active, other = split_turn(host, guest)
    # Not my turn: the box is disabled with a reason, no target list, who is acting is named.
    assert other.locator("[data-testid=action-input]").is_disabled()
    assert "turn" in other.inner_text("[data-testid=action-note]")
    assert other.locator("[data-testid=targets]").is_hidden()
    assert "turn" in other.locator("[data-testid=hotbar-wait]").inner_text()
    # My turn: targets, hotbar and End Turn; the action box stays free for something creative.
    has_hit_chance(active)
    assert active.locator("[data-testid=action-input]").is_enabled()
    chips = active.locator("[data-testid=target-chip]")
    assert chips.count() >= 2
    first = active.locator("[data-testid=target-chip][data-side=hostile][aria-pressed=false]").first
    assert first.locator("[data-testid=target-hp]").inner_text() in (
        "Unhurt",
        "Wounded",
        "Bloodied",
    )
    picked = first.get_attribute("data-creature")
    first.click()
    pressed = active.locator(f"[data-testid=target-chip][data-creature='{picked}']")
    assert pressed.get_attribute("aria-pressed") == "true"
    has_hit_chance(active).click()
    active.wait_for_selector("[data-testid=pip-action].spent", timeout=20000)
    snap(active, shots_dir, "controller_combat_turn", 390)
    snap(other, shots_dir, "m11_phone_combat_waiting", 390)
    assert screen.locator("[data-testid=screen-invite]").is_hidden()
    snap(screen, shots_dir, "m11_screen_combat", 1920)
    assert re.fullmatch(r"Your turn - \d:\d\d", active.evaluate(CHIP))
    before = active.evaluate(f"JSON.stringify({COMBAT_POS})")
    active.click("[data-testid=end-turn]")
    # The turn passes (a downed partner is skipped, so the round may roll over instead).
    active.wait_for_function(f"JSON.stringify({COMBAT_POS}) !== {before!r}", timeout=45000)
    assert errors == []


def _wipe(live_server: LiveServer) -> None:
    """Kill every hero by a table job (a trap), exactly like the session tests do."""
    assert live_server.app is not None and live_server.loop is not None
    table = live_server.app.state.registry.table

    async def job() -> None:
        for creature in list(table.state.creatures.values()):
            if creature.pc is not None:
                packet = DamagePacket(amount=999, damage_type=DamageType.PIERCING)
                table.apply_all(resolve_damage(creature, [packet]))

    live_server.loop.call_soon_threadsafe(table.schedule, job)


def _travel(host: Page, guest: Page) -> None:
    """Travel through the Map tab and the party vote: the arrival writes the retry checkpoint."""
    go_tab(host, "journal")
    host.click("[data-testid=jtab-map]")
    button = host.locator("[data-testid=map-travel]:not([disabled])").first
    node = button.get_attribute("data-node")
    button.click()
    guest.wait_for_selector("[data-testid=vote-ready]", timeout=20000)
    guest.click("[data-testid=vote-ready]")
    host.wait_for_function(
        f"window.aidm.store.get().snapshot.state.scene.node_id === {node!r}", timeout=30000
    )
    host.wait_for_selector("[data-testid=pane-play]:not([hidden])")


def test_defeat_on_the_phones_host_chooses_and_retry_works(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, guest = start_with_screen(browser, live_server.base, errors, screen_size=HD)
    _travel(host, guest)
    assert host.locator("[data-testid=controller-defeat]").is_hidden()
    _wipe(live_server)
    for page in (host, guest):
        page.wait_for_selector("[data-testid=controller-defeat]:not([hidden])", timeout=30000)
    screen.wait_for_selector("[data-testid=screen-defeat]:not([hidden])", timeout=30000)
    # The host (Ann) gets the three choices; Bo only waits.
    assert host.locator("[data-testid=defeat-text]").inner_text().strip()
    assert "Retry from" in host.inner_text("[data-testid=defeat-retry]")
    assert host.locator("[data-testid=defeat-load]").is_visible()
    assert host.locator("[data-testid=defeat-new]").is_visible()
    assert guest.locator("[data-testid=defeat-choices]").is_hidden()
    assert guest.locator("[data-testid=defeat-wait]").is_visible()
    assert guest.locator("[data-testid=defeat-retry]").is_hidden()
    # Everything on the phones is locked while the party is down.
    for page in (host, guest):
        assert page.locator("[data-testid=status-chip]").inner_text() == "Defeated"
    snap(host, shots_dir, "controller_defeat", 390)
    snap(guest, shots_dir, "controller_defeat_waiting", 390)
    snap(screen, shots_dir, "m11_screen_defeat", 1920)
    # A typed refusal is friendly text, never the code or the server's words.
    host.evaluate(
        "() => window.aidm.dispatch({type: 'error', code: 'refused', text: 'raw words',"
        " refusal: 'no_checkpoint'})"
    )
    host.wait_for_function(
        "document.querySelector('[data-testid=defeat-status]').textContent.includes('checkpoint')"
    )
    assert "raw words" not in host.inner_text("body")
    # Load a save lists what the server has; New adventure asks first.
    host.click("[data-testid=defeat-load]")
    host.wait_for_selector("[data-testid=defeat-saves] *", timeout=10000)
    host.click("[data-testid=defeat-new]")
    assert host.locator("[data-testid=defeat-new-yes]").is_visible()
    host.click("[data-testid=defeat-new-no]")
    # Retry: the arrival checkpoint comes back, everyone is on the Play tab again and alive.
    host.click("[data-testid=defeat-retry]")
    host.wait_for_selector("[data-testid=controller-defeat]", state="hidden", timeout=30000)
    guest.wait_for_selector("[data-testid=controller-defeat]", state="hidden", timeout=30000)
    screen.wait_for_selector("[data-testid=screen-defeat]", state="hidden", timeout=30000)
    assert host.evaluate("window.aidm.store.get().phase") == "play"
    assert host.locator(PANE.format("play")).is_visible()
    host.wait_for_function(ACTION_ENABLED, timeout=20000)
    assert host.locator("[data-testid=status-chip]").inner_text() != "Defeated"
    assert errors == []


FAKE_MIC = """
window.__started = 0;
class FakeRec {
  start() { window.__started += 1; window.__rec = this; }
  stop() { if (this.onend) this.onend(); }
}
window.SpeechRecognition = FakeRec;
window.webkitSpeechRecognition = FakeRec;
"""
NO_MIC = """
Object.defineProperty(window, 'isSecureContext', { value: false });
delete window.SpeechRecognition; delete window.webkitSpeechRecognition;
"""


def _mic_page(browser: Browser, base: str, script: str, errors: list[str]) -> Page:
    context = browser.new_context(viewport=PHONE)
    context.add_init_script(script)
    page = context.new_page()
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    join(page, base, "Ann")
    complete_wizard(page, HeroSpec(name="Brienne"))
    page.wait_for_function("document.querySelectorAll('[data-testid=hero-state].ready').length")
    page.click("[data-testid=start]")
    page.wait_for_selector("[data-testid=action-input]", timeout=20000)
    return page


def test_mic_hidden_with_keyboard_hint_when_not_available(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    page = _mic_page(browser, live_server.base, NO_MIC, errors)
    assert page.locator("[data-testid=mic-button]").count() == 0
    assert page.locator("[data-testid=mic-slot]").is_hidden()
    assert page.locator("[data-testid=dictation-hint]").is_visible()
    assert errors == []


def test_mic_fills_the_action_box_and_reports_failure_gently(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    page = _mic_page(browser, live_server.base, FAKE_MIC, errors)
    assert page.evaluate("window.isSecureContext")  # 127.0.0.1 is a secure context
    assert page.locator("[data-testid=mic-button]").is_visible()
    assert page.locator("[data-testid=dictation-hint]").is_hidden()
    page.click("[data-testid=mic-button]")
    page.evaluate("window.__rec.onresult({ results: [[{ transcript: 'open the door' }]] })")
    assert page.locator("[data-testid=action-input]").input_value() == "open the door"
    page.evaluate("window.__rec.onerror({ error: 'not-allowed' })")
    note = page.locator("[data-testid=action-gentle]").inner_text()
    assert note == "The microphone did not catch that. Try again, or type your action."
    assert errors == []
