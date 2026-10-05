"""Browser tests of the table view: two players, FakeLLM, dice, votes (Playwright, M7.3)."""

from pathlib import Path

from playwright.sync_api import Browser, Page, ViewportSize

from tests.ui.conftest import LiveServer
from tests.ui.wizard_helpers import HeroSpec, complete_wizard, join

WIDE = ViewportSize(width=1280, height=800)
PHONE = ViewportSize(width=390, height=844)
ROGUE = HeroSpec(name="Mira", race="elf", cls="rogue", background="criminal")
HAS_TEXT = (
    "[...document.querySelectorAll('[data-testid=narration]')]"
    ".some(n => n.textContent.trim().length > 20)"
)
OFFER = {
    "id": "o1",
    "node_id": "n1",
    "foes": ["Goblin", "Goblin"],
    "boss_name": None,
    "difficulty": "medium",
    "options": ["fight", "surprise", "escape", "parley"],
}
ACTION_ENABLED = "!document.querySelector('[data-testid=action-input]').disabled"


def _player(
    browser: Browser, base: str, name: str, spec: HeroSpec, size: ViewportSize, errors: list[str]
) -> Page:
    context = browser.new_context(viewport=size)
    page = context.new_page()
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    join(page, base, name)
    complete_wizard(page, spec)
    return page


def _start(browser: Browser, base: str, size: ViewportSize, errors: list[str]) -> tuple[Page, Page]:
    host = _player(browser, base, "Ann", HeroSpec(name="Brienne"), size, errors)
    guest = _player(browser, base, "Bo", ROGUE, size, errors)
    ready = "document.querySelectorAll('[data-testid=hero-state].ready').length === 2"
    host.wait_for_function(ready)
    host.click("[data-testid=start]")
    for page in (host, guest):
        page.wait_for_selector("[data-testid=feed]", timeout=20000)
        page.wait_for_function(HAS_TEXT, timeout=20000)
    return host, guest


def _narration_count(page: Page) -> int:
    return page.locator("[data-testid=narration]").count()


def _no_overflow(page: Page) -> bool:
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def _snap(page: Page, shots: Path, name: str, width: int) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_function("[...document.images].every((i) => i.complete)")
    page.wait_for_timeout(700)
    page.screenshot(path=str(shots / f"table_{name}_{width}.png"))


def _vote_text(page: Page, word: str) -> None:
    page.wait_for_function(
        f"document.querySelector('[data-testid=vote-result]').textContent.includes('{word}')",
        timeout=20000,
    )


def test_two_players_see_opening_narration_party_and_scene(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, guest = _start(browser, live_server.base, WIDE, errors)
    for page in (host, guest):
        assert page.locator("[data-testid=party-card]").count() == 2
        assert page.locator("[data-testid=scene-name]").inner_text().strip()
        assert page.locator("[data-testid=campaign-title]").inner_text().strip()
        first = page.locator("[data-testid=narration]").first
        assert "tone-" in (first.get_attribute("class") or "")
    assert "Brienne" in host.locator("[data-testid=party-card].mine").inner_text()
    assert "Mira" in guest.locator("[data-testid=party-card].mine").inner_text()
    _snap(host, shots_dir, "start", 1280)
    assert errors == []


def test_action_shows_dice_and_narration_for_both(
    browser: Browser, scripted_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, guest = _start(browser, scripted_server.base, WIDE, errors)
    before = _narration_count(guest)
    host.fill("[data-testid=action-input]", "I search the room carefully")
    host.click("[data-testid=action-send]")
    for page in (host, guest):
        page.wait_for_selector("[data-testid=dice-roll]", timeout=20000)
        assert page.locator("[data-testid=dice-roll] [data-testid=die]").count() >= 1
        assert page.locator("[data-testid=dice-roll] .die.kept").count() >= 1
        assert page.locator("[data-testid=dice-roll] .roll-out").first.inner_text().strip()
    count = f"document.querySelectorAll('[data-testid=narration]').length > {before}"
    guest.wait_for_function(count, timeout=20000)
    host.wait_for_function(ACTION_ENABLED, timeout=20000)
    assert host.locator("[data-testid=action-input]").input_value() == ""
    _snap(guest, shots_dir, "dice", 1280)
    assert errors == []


def test_rest_vote_both_ready_passes(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, guest = _start(browser, live_server.base, WIDE, errors)
    host.fill("[data-testid=action-input]", "we take a short rest")
    host.click("[data-testid=action-send]")
    for page in (host, guest):
        page.wait_for_selector("[data-testid=vote]:not([hidden])", timeout=20000)
        assert page.locator("[data-testid=vote-timer]").inner_text().endswith("s")
    guest.wait_for_selector("[data-testid=vote-ready]:not([disabled])")
    _snap(guest, shots_dir, "vote", 1280)
    guest.click("[data-testid=vote-ready]")
    for page in (host, guest):
        page.wait_for_selector("[data-testid=vote][hidden]", state="attached", timeout=20000)
        _vote_text(page, "agrees")
    assert errors == []


def test_vote_decline_fails(browser: Browser, live_server: LiveServer) -> None:
    errors: list[str] = []
    host, guest = _start(browser, live_server.base, WIDE, errors)
    host.fill("[data-testid=action-input]", "we take a long rest")
    host.click("[data-testid=action-send]")
    guest.wait_for_selector("[data-testid=vote]:not([hidden])", timeout=20000)
    guest.click("[data-testid=vote-decline]")
    for page in (host, guest):
        _vote_text(page, "against")
    assert errors == []


def test_point_of_no_return_dialog_and_encounter_offer(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, _guest = _start(browser, live_server.base, WIDE, errors)
    me = host.evaluate("window.aidm.store.get().me.playerId")
    host.evaluate(
        """(me) => window.aidm.dispatch({type: 'pending_confirmation', player_id: me,
            prompt: 'Striking the harbourmaster will start a fight. Continue?'})""",
        me,
    )
    dialog = host.locator("[data-testid=confirm-dialog]")
    dialog.wait_for(state="visible")
    assert "harbourmaster" in host.locator("[data-testid=confirm-text]").inner_text()
    _snap(host, shots_dir, "confirm", 1280)
    host.click("[data-testid=confirm-no]")
    dialog.wait_for(state="hidden")
    host.evaluate("(o) => window.aidm.dispatch({type: 'encounter_offer', offer: o})", OFFER)
    host.screenshot(path=str(shots_dir / "table_offer_1280.png"))
    # A server snapshot may replace the offer at any moment, so check and click in one step.
    visible = host.evaluate(
        """(o) => {
            window.aidm.dispatch({type: 'encounter_offer', offer: o});
            const ids = ['fight', 'surprise', 'escape', 'parley'];
            const shown = ids.every((c) => document.querySelector(`[data-testid=offer-${c}]`));
            document.querySelector('[data-testid=offer-parley]').click();
            return shown;
        }""",
        OFFER,
    )
    assert visible
    # The server has no such offer, so it refuses; the banner shows friendly text, never the code.
    banner = host.locator("[data-testid=banner]")
    banner.wait_for(timeout=10000)
    assert "refused" not in banner.inner_text().lower()
    assert errors == []


def test_dice_advantage_levelup_badge_and_gentle_notice(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    host, _guest = _start(browser, live_server.base, WIDE, errors)
    host.evaluate(
        """() => window.aidm.dispatch({type: 'dice_roll', seq: 9001, dice: {roller_id: null,
            label: 'stealth', expression: '2d20', rolls: [7, 15], adv: 'advantage',
            modifier: 3, total: 18, target: 14, success: true, crit: false}})"""
    )
    host.wait_for_selector("[data-testid=adv-label]")
    assert host.locator("[data-testid=adv-label]").first.inner_text() == "Advantage"
    host.wait_for_timeout(900)
    kept = host.locator("[data-testid=dice-roll] .die.kept")
    dropped = host.locator("[data-testid=dice-roll] .die.dropped")
    assert kept.count() == 1 and dropped.count() == 1
    assert kept.first.inner_text() == "15" and dropped.first.inner_text() == "7"
    hero = host.evaluate(
        "window.aidm.store.get().snapshot.state.party.find(c => c.name === 'Brienne').id"
    )
    host.evaluate(
        "(id) => window.aidm.dispatch({type: 'level_up_available', creature_id: id, level: 2})",
        hero,
    )
    host.wait_for_selector("[data-testid=levelup-badge]")
    host.click("[data-testid=levelup-button]")
    host.wait_for_selector("[data-testid=levelup-dialog]", state="visible")
    host.keyboard.press("Escape")
    host.evaluate(
        "() => window.aidm.dispatch({type: 'notice', kind: 'refused', text: 'Not just now.'})"
    )
    host.wait_for_function(
        "document.querySelector('[data-testid=action-gentle]').textContent === 'Not just now.'"
    )
    assert errors == []


def test_reduced_motion_reveals_narration_at_once(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    host, _guest = _start(browser, live_server.base, WIDE, errors)
    host.emulate_media(reduced_motion="reduce")
    text = "The tide rolls in over the old stones and the gulls wheel above the quay."
    host.evaluate(
        """(text) => {
            const d = window.aidm.dispatch;
            d({type: 'narration_chunk', id: 'rm1', index: 0, text, tone: 'social',
               audio_url: null});
            d({type: 'narration_done', id: 'rm1'});
        }""",
        text,
    )
    node = host.locator("[data-id=rm1]")
    assert text in node.inner_text()
    assert "tone-social" in (node.get_attribute("class") or "")
    assert errors == []


def test_phone_layout_has_no_overflow_and_works(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, _guest = _start(browser, live_server.base, PHONE, errors)
    assert _no_overflow(host)
    _snap(host, shots_dir, "start", 390)
    host.fill("[data-testid=action-input]", "we take a short rest")
    host.click("[data-testid=action-send]")
    host.wait_for_selector("[data-testid=vote]:not([hidden])", timeout=20000)
    assert _no_overflow(host)
    _snap(host, shots_dir, "vote", 390)
    host.evaluate(
        """() => window.aidm.dispatch({type: 'dice_roll', seq: 9002, dice: {roller_id: null,
            label: 'perception', expression: '2d20', rolls: [4, 11], adv: 'disadvantage',
            modifier: 2, total: 6, target: 12, success: false, crit: false}})"""
    )
    host.wait_for_function(
        "document.querySelector('[data-testid=dice-latest]').textContent.includes('perception')"
    )
    host.click("summary")
    host.wait_for_selector("[data-testid=dice-roll]")
    _snap(host, shots_dir, "dice", 390)
    assert _no_overflow(host)
    assert errors == []
