"""Browser tests of the fight: the board on /screen, hotbar and target chips on phones (M11.4)."""

from pathlib import Path

from playwright.sync_api import Browser, Locator, Page

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import (
    COMBAT_POS,
    MAIN,
    WAIT,
    has_hit_chance,
    snap,
    split_turn,
    start_fight,
)

NO_HSCROLL = "document.documentElement.scrollWidth <= window.innerWidth"


def _board_facts(screen: Page) -> None:
    assert screen.locator("[data-testid=zone]").count() >= 3
    assert screen.locator("[data-testid=token][data-side=hostile]").count() == 2
    assert screen.locator("[data-testid=init-entry]").count() == 4
    assert screen.locator("[data-testid=init-entry].current").count() == 1
    assert "Round 1" in screen.locator("[data-testid=round]").inner_text()
    states = screen.locator("[data-testid=enemy-state]").all_inner_texts()
    assert states and all(s in ("Unhurt", "Wounded", "Bloodied") for s in states)
    srcs = screen.eval_on_selector_all(
        "[data-testid=token][data-side=hostile] img.tk-art", "els => els.map((e) => e.src)"
    )
    assert srcs and all("goblin" in s for s in srcs), srcs


def test_two_players_fight_attack_move_suggest_and_end_turn(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, guest = start_fight(browser, combat_server.base, errors)
    active, other = split_turn(host, guest)
    _board_facts(screen)
    # The active phone shows target chips (two goblins, the partner) and hit chances.
    assert active.locator("[data-testid=board]").count() == 0
    chips = active.locator("[data-testid=target-chip]")
    assert chips.count() == 3
    assert active.locator("[data-testid=target-chip][data-side=hostile]").count() == 2
    swing = has_hit_chance(active)
    active.wait_for_selector("[data-testid=target-hit]:text('to hit')")
    assert active.locator("[data-testid=target-where]").first.inner_text().strip()
    assert active.locator("[data-testid=pip-action].on").count() == 1
    swing.hover()
    tip = swing.locator(".hb-tip").text_content() or ""
    assert "AC" in tip and "Hits" in tip
    # The other phone waits: no end turn, no target list.
    assert other.locator(WAIT).is_visible()
    assert other.locator("[data-testid=end-turn]").count() == 0
    assert other.locator("[data-testid=targets]").is_hidden()
    assert "is acting" in other.locator("[data-testid=status-chip]").inner_text()
    assert active.locator("[data-testid=status-chip]").inner_text().startswith("Your turn")
    # The other player suggests; the active one sees it.
    other.fill("[data-testid=suggest-input]", "go for the left goblin")
    other.click("[data-testid=suggest-send]")
    active.wait_for_selector("[data-testid=suggestion]", timeout=10000)
    assert "left goblin" in active.locator("[data-testid=suggestion]").first.inner_text()
    # Tapping a chip picks the target (what tapping the token on the board did).
    foe = active.locator("[data-testid=target-chip][data-side=hostile][aria-pressed=false]").first
    picked = foe.get_attribute("data-creature")
    foe.click()
    pressed = active.locator(f"[data-testid=target-chip][data-creature='{picked}']")
    assert pressed.get_attribute("aria-pressed") == "true"
    # Attack: the action pip is spent; the line appears in the screen's feed.
    has_hit_chance(active).click()
    active.wait_for_selector("[data-testid=pip-action].spent", timeout=20000)
    screen.wait_for_selector("[data-testid=event-line]", timeout=20000)
    # Move to a zone the hero can reach: the Move to list on the phone.
    go = active.locator("[data-testid=zone-chip]:not([disabled])")
    if go.count():
        active.click("[data-testid=places] summary")
        before = active.locator("[data-testid=pip-move]").inner_text()
        go.first.click()
        active.wait_for_function(
            f"document.querySelector('[data-testid=pip-move]').innerText !== {before!r}",
            timeout=20000,
        )
    assert active.locator(f"{MAIN} .hb-key").inner_text() == "1"
    snap(screen, shots_dir, "screen_combat", 1280)
    snap(active, shots_dir, "controller_combat", 390)
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
    _screen, host, guest = start_fight(browser, combat_server.base, errors)
    _fighter_turn(host, guest)
    has_hit_chance(host)
    wind = host.locator("[data-testid=slot-feat-second-wind]")
    assert wind.locator("[data-testid=slot-sub]").inner_text() == "1 of 1 left"
    assert "Bonus action" in (wind.locator(".hb-tip").text_content() or "")
    snap(host, shots_dir, "controller_combat_hotbar", 390)
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
    _screen, host, guest = start_fight(browser, combat_server.base, errors)
    active, _other = split_turn(host, guest)
    has_hit_chance(active)
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


def test_places_list_names_every_zone_and_disables_the_current_one(
    browser: Browser, combat_server: LiveServer
) -> None:
    """The Move to list holds one chip per zone; the one the hero stands in cannot be picked."""
    errors: list[str] = []
    _screen, host, guest = start_fight(browser, combat_server.base, errors)
    active, _other = split_turn(host, guest)
    has_hit_chance(active)
    assert active.locator("[data-testid=places]").count() == 1
    chips = active.locator("[data-testid=zone-chip]")
    assert chips.count() >= 3
    here = active.locator("[data-testid=zone-chip]", has_text="here")
    assert here.count() == 1 and here.first.is_disabled()
    assert errors == []


def test_phone_layout_in_a_fight_and_the_screen_board(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, guest = start_fight(browser, combat_server.base, errors)
    active, other = split_turn(host, guest)
    has_hit_chance(active)
    for page in (active, other, screen):
        assert page.evaluate(NO_HSCROLL)
    snap(other, shots_dir, "controller_combat_waiting", 390)
    snap(screen, shots_dir, "screen_combat_board", 1280)
    assert errors == []


PATCH_ZONE = """([id, extra]) => {
  const combat = window.aidm.store.get().snapshot.state.combat;
  const zones = combat.zones.map((z) => (z.id === id ? { ...z, ...extra } : z));
  window.aidm.dispatch({ type: 'combat_state', combat: { ...combat, zones } });
}"""


def _feet(chip: Locator) -> int:
    return int(chip.inner_text().split(",")[1].split("ft")[0])


def test_move_to_list_shows_zone_badges_and_the_rough_cost(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    """Cover, high ground and a grease surface appear on the chip; grease doubles the cost shown."""
    errors: list[str] = []
    _screen, host, guest = start_fight(browser, combat_server.base, errors)
    active, _other = split_turn(host, guest)
    has_hit_chance(active)
    active.click("[data-testid=places] summary")
    zone_id = active.locator("[data-testid=zone-chip]:not([disabled])").first.get_attribute(
        "data-zone"
    )
    chip = active.locator(f"[data-zone='{zone_id}']")
    before = _feet(chip)
    extra = {
        "cover": "half",
        "high_ground": True,
        "rough": True,
        "surfaces": [{"kind": "grease", "rounds_left": 2}],
    }
    active.evaluate(PATCH_ZONE, [zone_id, extra])
    chip.locator("[data-testid=zone-badge]", has_text="Grease (2)").wait_for()
    texts = chip.locator("[data-testid=zone-badge]").all_inner_texts()
    assert "High ground" in texts and "Rough ground" in texts
    assert any("Half" in x for x in texts)
    assert _feet(chip) == before * 2
    # The point of the fix: a zone the doubled cost puts out of reach is greyed out, so the
    # phone never offers a move the server would refuse.
    left = active.evaluate(
        "async () => (await import('/web/js/combat/model.js'))"
        ".combatOf(window.aidm.store.get()).economy.movement_left"
    )
    assert isinstance(left, int)
    assert chip.is_disabled() == (_feet(chip) > left)
    assert active.evaluate(NO_HSCROLL)
    snap(active, shots_dir, "controller_move_to", 390)
    assert errors == []
