"""Browser tests of the table: a /screen and two phones, one server."""

from pathlib import Path

from playwright.sync_api import Browser, Page

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import HAS_TEXT, PHONE, WIDE, snap, start_with_screen

OFFER = {
    "id": "o1",
    "node_id": "n1",
    "foes": ["Goblin", "Goblin"],
    "boss_name": None,
    "difficulty": "medium",
    "options": ["fight", "surprise", "escape", "parley"],
}
ACTION_ENABLED = "!document.querySelector('[data-testid=action-input]').disabled"
NARRATIONS = "[...document.querySelectorAll('[data-testid=narration]')]"
ALL_TOLD = NARRATIONS + ".every((n) => n.classList.contains('done'))"
PORTRAITS = "[data-testid=party-card] img.pc-portrait"
PLACEHOLDER = "/assets/placeholder/"
LAST = "document.querySelector('[data-testid=last-line]').textContent"
CHAIN_URL = """async () => {
    const assets = await import('/web/js/assets.js');
    const party = await import('/web/js/table/party.js');
    const hero = {portrait_id: 'race.unpainted.f', class_index: 'fighter'};
    return assets.assetUrl(party.portraitKeys(hero));
}"""
HERO_ID = "window.aidm.store.get().snapshot.state.party.find(c => c.name === 'Brienne').id"
ROLL = """({id, expression, rolls, adv, total}) => window.aidm.dispatch({type: 'dice_roll',
    seq: 9001, dice: {roller_id: id, label: 'stealth', expression, rolls, adv, modifier: 3,
    total, target: 14, success: true, crit: false}})"""


def _texts(page: Page) -> list[str]:
    return [" ".join(t.split()) for t in page.locator("[data-testid=narration]").all_inner_texts()]


def _vote_text(page: Page, word: str) -> None:
    page.wait_for_function(
        f"document.querySelector('[data-testid=vote-result]').textContent.includes('{word}')",
        timeout=20000,
    )


def test_two_players_see_opening_narration_party_and_scene(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, guest = start_with_screen(browser, live_server.base, errors)
    # The shared screen: scene, story and the whole party (nobody owns a card there).
    assert screen.locator("[data-testid=party-card]").count() == 2
    assert screen.locator("[data-testid=party-card].mine").count() == 0
    assert screen.locator("[data-testid=scene-name]").inner_text().strip()
    assert screen.locator("[data-testid=campaign-title]").inner_text().strip()
    first = screen.locator("[data-testid=narration]").first
    assert "tone-" in (first.get_attribute("class") or "")
    srcs = screen.eval_on_selector_all(PORTRAITS, "els => els.map((e) => e.getAttribute('src'))")
    assert len(srcs) == 2 and all(PLACEHOLDER not in s for s in srcs), srcs
    # Each phone is its own hero: strip with name and AC, the story is only one line.
    assert host.locator("[data-testid=strip-name]").inner_text() == "Brienne"
    assert guest.locator("[data-testid=strip-name]").inner_text() == "Mira"
    for phone in (host, guest):
        assert phone.locator("[data-testid=narration]").count() == 0
        assert phone.locator("[data-testid=party-card]").count() == 0
        assert len(phone.locator("[data-testid=last-line]").inner_text()) > 20
    # A race portrait without real art falls back to the real v1 class portrait.
    chained = host.evaluate(CHAIN_URL)
    assert "fighter" in chained and PLACEHOLDER not in chained
    # Fake mode tells its tale cleanly: no fallback banner for a working (fake) storyteller.
    for page in (screen, host, guest):
        assert page.locator("[data-testid=banner]").count() == 0
    snap(screen, shots_dir, "screen_start", 1280)
    snap(host, shots_dir, "controller_start", 390)
    assert errors == []


def test_action_shows_dice_and_narration_for_both(
    browser: Browser, scripted_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, guest = start_with_screen(browser, scripted_server.base, errors)
    before = screen.locator("[data-testid=narration]").count()
    guest_items = guest.evaluate("window.aidm.story.items.length")
    host.fill("[data-testid=action-input]", "I search the room carefully")
    host.click("[data-testid=action-send]")
    # The roll stage takes the screen (M26.6); only the roller's own phone shows a small toast.
    screen.wait_for_selector("[data-testid=roll-stage]", state="attached", timeout=20000)
    host.wait_for_selector("[data-testid=dice-toast]:not([hidden])", timeout=20000)
    assert guest.locator("[data-testid=dice-toast]").is_hidden()
    screen.wait_for_function(
        f"document.querySelectorAll('[data-testid=narration]').length > {before}", timeout=20000
    )
    guest.wait_for_function(f"window.aidm.story.items.length > {guest_items}", timeout=20000)
    assert guest.inner_text("[data-testid=last-line]").strip()
    host.wait_for_function(ACTION_ENABLED, timeout=20000)
    assert host.locator("[data-testid=action-input]").input_value() == ""
    line = "an Investigation check"
    screen.wait_for_function(
        "[...document.querySelectorAll('[data-testid=event-line]')]"
        f".some((n) => n.textContent.includes('{line}'))",
        timeout=20000,
    )
    assert guest.locator("[data-testid=banner]").count() == 0
    snap(screen, shots_dir, "screen_dice", 1280)
    snap(host, shots_dir, "controller_dice", 390)
    assert errors == []


def test_reload_restores_the_story_feed(browser: Browser, live_server: LiveServer) -> None:
    errors: list[str] = []
    screen, host, _guest = start_with_screen(browser, live_server.base, errors)
    host.fill("[data-testid=action-input]", "I look at the harbour")
    host.click("[data-testid=action-send]")
    screen.wait_for_function("document.querySelectorAll('[data-testid=narration]').length >= 2")
    host.wait_for_function(ACTION_ENABLED, timeout=20000)
    screen.wait_for_function(ALL_TOLD, timeout=20000)
    before = _texts(screen)
    last = host.evaluate(LAST)
    screen.reload()
    screen.wait_for_selector("[data-testid=feed]", timeout=20000)
    screen.wait_for_function(
        f"document.querySelectorAll('[data-testid=narration]').length >= {len(before)}",
        timeout=20000,
    )
    assert _texts(screen)[: len(before)] == before
    host.reload()
    host.wait_for_selector("[data-testid=controller]", timeout=20000)
    host.wait_for_function(f"{LAST} === {last!r}", timeout=20000)
    assert errors == []


def test_rest_vote_both_ready_passes(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, guest = start_with_screen(browser, live_server.base, errors)
    host.fill("[data-testid=action-input]", "we take a short rest")
    host.click("[data-testid=action-send]")
    for page in (host, guest):
        page.wait_for_selector("[data-testid=vote]:not([hidden])", timeout=20000)
        assert page.locator("[data-testid=vote-timer]").inner_text().endswith("s")
    # The screen shows the same vote read-only, with no buttons.
    screen.wait_for_selector("[data-testid=screen-vote]:not([hidden])", timeout=20000)
    assert screen.locator("[data-testid=screen-vote] button").count() == 0
    guest.wait_for_selector("[data-testid=vote-ready]:not([disabled])")
    snap(guest, shots_dir, "controller_vote", 390)
    snap(screen, shots_dir, "screen_vote", 1280)
    guest.click("[data-testid=vote-ready]")
    for page in (host, guest):
        page.wait_for_selector("[data-testid=vote][hidden]", state="attached", timeout=20000)
        _vote_text(page, "agrees")
    assert errors == []


def test_vote_decline_fails(browser: Browser, live_server: LiveServer) -> None:
    errors: list[str] = []
    _screen, host, guest = start_with_screen(browser, live_server.base, errors)
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
    _screen, host, _guest = start_with_screen(browser, live_server.base, errors)
    me = host.evaluate("window.aidm.store.get().me.playerId")
    host.evaluate(
        """(me) => window.aidm.dispatch({type: 'pending_confirmation', player_id: me,
            prompt: 'Striking the harbourmaster will start a fight. Continue?'})""",
        me,
    )
    dialog = host.locator("[data-testid=confirm-dialog]")
    dialog.wait_for(state="visible")
    assert "harbourmaster" in host.locator("[data-testid=confirm-text]").inner_text()
    snap(host, shots_dir, "controller_confirm", 390)
    host.click("[data-testid=confirm-no]")
    dialog.wait_for(state="hidden")
    host.evaluate("(o) => window.aidm.dispatch({type: 'encounter_offer', offer: o})", OFFER)
    host.screenshot(path=str(shots_dir / "controller_offer_390.png"))
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
    screen, host, _guest = start_with_screen(browser, live_server.base, errors)
    roll = {"id": None, "expression": "2d20", "rolls": [7, 15], "adv": "advantage", "total": 18}
    screen.evaluate(ROLL, roll)
    screen.wait_for_selector("[data-testid=screen-roll] .tag")
    assert screen.locator("[data-testid=screen-roll] .tag").first.inner_text() == "Advantage"
    kept = screen.locator("[data-testid=screen-roll] .sc-die.kept")
    dropped = screen.locator("[data-testid=screen-roll] .sc-die.dropped")
    assert kept.count() == 1 and dropped.count() == 1
    assert kept.first.inner_text() == "15" and dropped.first.inner_text() == "7"
    # A roll of the phone's own hero is a toast there; someone else's roll is not.
    hero = host.evaluate(HERO_ID)
    host.evaluate(ROLL, {**roll, "id": None})
    assert host.locator("[data-testid=dice-toast]").is_hidden()
    host.evaluate(ROLL, {**roll, "id": hero})
    host.wait_for_selector("[data-testid=dice-toast]:not([hidden])")
    toast = host.locator("[data-testid=dice-toast]")
    assert toast.locator(".ct-die.dropped").inner_text() == "7" and "18" in toast.inner_text()
    host.evaluate(
        "(id) => window.aidm.dispatch({type: 'level_up_available', creature_id: id, level: 2})",
        hero,
    )
    host.wait_for_selector("[data-testid=levelup-badge]:not([hidden])")
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


def test_roll_without_outcome_shows_no_null_on_the_phone(
    browser: Browser, live_server: LiveServer
) -> None:
    # A damage roll has no target and no success: the toast and the last roll printed "= 5null".
    errors: list[str] = []
    _screen, host, _guest = start_with_screen(browser, live_server.base, errors)
    damage = """(id) => window.aidm.dispatch({type: 'dice_roll', seq: 9002, dice: {roller_id: id,
        label: 'Dagger damage', expression: '1d4+1', rolls: [2], adv: 'normal', modifier: 1,
        total: 3, target: null, success: null, crit: false}})"""
    host.evaluate(damage, host.evaluate(HERO_ID))
    host.wait_for_selector("[data-testid=dice-toast]:not([hidden])")
    host.wait_for_selector("[data-testid=last-roll]:not([hidden])")
    for testid in ("dice-toast", "last-roll"):
        text = host.locator(f"[data-testid={testid}]").inner_text()
        assert "= 3" in text and "null" not in text, (testid, text)
    assert errors == []


def test_reduced_motion_reveals_narration_at_once(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    screen, _host, _guest = start_with_screen(browser, live_server.base, errors)
    screen.emulate_media(reduced_motion="reduce")
    text = "The tide rolls in over the old stones and the gulls wheel above the quay."
    screen.evaluate(
        """(text) => {
            const d = window.aidm.dispatch;
            d({type: 'narration_chunk', id: 'rm1', index: 0, text, tone: 'social',
               audio_url: null});
            d({type: 'narration_done', id: 'rm1'});
        }""",
        text,
    )
    node = screen.locator("[data-id=rm1]")
    assert text in node.inner_text()
    assert "tone-social" in (node.get_attribute("class") or "")
    assert errors == []


def test_phone_layout_has_no_overflow_and_works(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, _guest = start_with_screen(browser, live_server.base, errors, size=PHONE)
    no_scroll = "document.documentElement.scrollWidth <= window.innerWidth"
    assert host.evaluate(no_scroll)
    host.fill("[data-testid=action-input]", "we take a short rest")
    host.click("[data-testid=action-send]")
    host.wait_for_selector("[data-testid=vote]:not([hidden])", timeout=20000)
    assert host.evaluate(no_scroll)
    hero = host.evaluate(HERO_ID)
    host.evaluate(
        ROLL,
        {"id": hero, "expression": "2d20", "rolls": [4, 11], "adv": "disadvantage", "total": 6},
    )
    host.wait_for_selector("[data-testid=dice-toast]:not([hidden])")
    assert host.evaluate(no_scroll)
    snap(host, shots_dir, "controller_vote_toast", 390)
    assert screen.evaluate(no_scroll) and screen.viewport_size == WIDE
    screen.wait_for_function(HAS_TEXT)
    assert errors == []
