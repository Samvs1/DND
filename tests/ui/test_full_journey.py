"""M9.3, M11.4: ONE end-to-end journey, three browser contexts (a /screen, two phones).

Join, wizard, start, streamed opening on the screen, an action with dice, a fight through the phone
hotbar with the board on the screen, a suggestion from the other player, then reconnects of the
screen and of a phone that must restore everything.
"""

import json
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Locator, Page, ViewportSize

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import HAS_TEXT, PHONE, PHONE_TEXT, ROGUE, WIDE
from tests.ui.wizard_helpers import HeroSpec, complete_wizard, join

MAIN = "[data-testid=slot-attack-main_hand]"
WAIT = "[data-testid=hotbar-wait]"
NARRATION = "[data-testid=narration]"
# The recent rolls (newest first) as "label total" text, read from the story model of the page.
DICE_TEXTS = "window.aidm.story.dice.map((r) => `${r.label} ${r.total}`)"
ACTION_ENABLED = "!document.querySelector('[data-testid=action-input]').disabled"
ALL_TOLD = (
    f"[...document.querySelectorAll('{NARRATION}')].every((n) => n.classList.contains('done'))"
)
COMBAT_POS = (
    "(() => { const c = window.aidm.store.get().snapshot.state.combat;"
    " return c ? [c.round, c.active_id] : null; })()"
)
LAST = "document.querySelector('[data-testid=last-line]').textContent"
# Records the total narration length each time the DOM changes, so growth over time is provable.
WATCH_NARRATION = """
(() => {
  const lens = [];
  window.__narrLens = lens;
  const total = () => [...document.querySelectorAll('[data-testid=narration]')]
    .reduce((sum, n) => sum + n.textContent.length, 0);
  new MutationObserver(() => {
    const now = total();
    if (lens.length === 0 || lens[lens.length - 1] !== now) lens.push(now);
  }).observe(document, {subtree: true, childList: true, characterData: true});
})();
"""


class Journey:
    """The pages plus the wire facts the test asserts on."""

    def __init__(self, shots: Path) -> None:
        self.shots = shots
        self.errors: list[str] = []
        # per page (by label): narration id -> chunk indexes seen on that page's socket
        self.chunks: dict[str, dict[str, set[int]]] = {}

    def watch(self, page: Page, label: str) -> None:
        page.on("pageerror", lambda exc: self.errors.append(str(exc)))
        seen = self.chunks.setdefault(label, {})
        page.on("websocket", lambda ws: ws.on("framereceived", lambda p: self._frame(seen, p)))

    @staticmethod
    def _frame(seen: dict[str, set[int]], payload: str | bytes) -> None:
        try:
            msg = json.loads(payload)
        except ValueError:
            return
        if isinstance(msg, dict) and msg.get("type") == "narration_chunk":
            seen.setdefault(str(msg.get("id")), set()).add(int(msg.get("index", 0)))

    def new_page(self, context: BrowserContext, label: str) -> Page:
        page = context.new_page()
        self.watch(page, label)
        return page

    def shot(self, page: Page, name: str) -> None:
        page.wait_for_load_state("networkidle")
        page.wait_for_function("[...document.images].every((i) => i.complete)")
        page.wait_for_timeout(600)
        page.screenshot(path=str(self.shots / f"journey_{name}.png"))


def _context(browser: Browser, size: ViewportSize = PHONE) -> BrowserContext:
    context = browser.new_context(viewport=size)
    context.add_init_script(WATCH_NARRATION)
    return context


def _enter(journey: Journey, context: BrowserContext, base: str, name: str, spec: HeroSpec) -> Page:
    page = journey.new_page(context, name)
    join(page, base, name)
    complete_wizard(page, spec)
    return page


def _hit_chance(page: Page) -> Locator:
    """Wait for the hit-chance previews; return an attack slot that shows a percentage."""
    page.wait_for_function(
        "[...document.querySelectorAll('[data-testid^=slot-attack-] [data-testid=slot-sub]')]"
        ".some((n) => n.textContent.includes('%'))",
        timeout=20000,
    )
    return page.locator("[data-testid^=slot-attack-]", has_text="%").first


def _who_acts(host: Page, guest: Page) -> tuple[Page, Page]:
    """(active page, other page), once exactly one of them shows the attack hotbar."""
    for _ in range(100):
        if host.locator(MAIN).count():
            return host, guest
        if guest.locator(MAIN).count():
            return guest, host
        host.wait_for_timeout(200)
    raise AssertionError("nobody got the hotbar")


def _stage_start(journey: Journey, browser: Browser, base: str) -> tuple[Page, Page, Page]:
    screen = journey.new_page(_context(browser, WIDE), "Screen")
    screen.goto(f"{base}/screen")
    screen.wait_for_selector("[data-testid=screen-waiting]:not([hidden])")
    host = _enter(journey, _context(browser), base, "Ann", HeroSpec(name="Brienne"))
    guest = _enter(journey, _context(browser), base, "Bo", ROGUE)
    host.wait_for_function(
        "document.querySelectorAll('[data-testid=hero-state].ready').length === 2"
    )
    guest.wait_for_selector("[data-testid=roster]")
    journey.shot(host, "01_lobby_ready")
    host.click("[data-testid=start]")
    for page in (host, guest):
        page.wait_for_selector("[data-testid=controller]", timeout=20000)
        page.wait_for_function(PHONE_TEXT, timeout=20000)
    screen.wait_for_selector("[data-testid=screen-table]:not([hidden])", timeout=20000)
    screen.wait_for_function(HAS_TEXT, timeout=20000)
    return screen, host, guest


def _assert_streamed(journey: Journey, screen: Page, host: Page, guest: Page) -> None:
    """The opening narration reaches every socket as several sentence chunks of one narration."""
    screen.wait_for_function(ALL_TOLD, timeout=30000)
    for label in ("Ann", "Bo", "Screen"):
        opening = journey.chunks[label]
        assert opening and max(len(indexes) for indexes in opening.values()) >= 2, opening
    journey.shot(screen, "02_opening_narration_screen")
    journey.shot(host, "03_opening_narration_phone")
    journey.shot(guest, "03_opening_narration_phone_guest")


def _assert_grew(page: Page) -> None:
    """The live narration is typed: the total text length passed through several values."""
    lens: list[int] = page.evaluate("window.__narrLens")
    assert len(set(lens)) >= 3 and lens[0] < lens[-1], lens[:12]


def _stage_action(journey: Journey, screen: Page, host: Page, guest: Page) -> None:
    before = screen.locator(NARRATION).count()
    guest_line = guest.evaluate(LAST)
    screen.evaluate("window.__narrLens.length = 0")
    host.fill("[data-testid=action-input]", "Search this place by going through things")
    host.click("[data-testid=action-send]")
    # M26.6: a check out of combat plays the roll stage (tests/ui/test_roll_stage.py covers it)
    screen.wait_for_selector("[data-testid=roll-stage]", state="attached", timeout=20000)
    # M26.7: a check shows as the roll card, then stays in Your last roll (no toast)
    host.wait_for_selector("[data-testid=last-roll]:not([hidden])", timeout=20000)
    screen.wait_for_function(
        f"document.querySelectorAll('{NARRATION}').length > {before}", timeout=20000
    )
    guest.wait_for_function(f"{LAST} !== {guest_line!r}", timeout=20000)
    host.wait_for_function(ACTION_ENABLED, timeout=20000)
    screen.wait_for_function(ALL_TOLD, timeout=20000)
    _assert_grew(screen)
    journey.shot(screen, "04_dice_and_narration_screen")
    journey.shot(host, "04_dice_toast_phone")


def _stage_combat(journey: Journey, screen: Page, host: Page, guest: Page) -> None:
    host.fill("[data-testid=action-input]", "I ambush the goblins from the shadows")
    host.click("[data-testid=action-send]")
    screen.wait_for_selector("[data-testid=board]:not([hidden])", timeout=30000)
    assert screen.locator("[data-testid=token][data-side=hostile]").count() == 2
    for page in (host, guest):
        page.wait_for_selector(f"{MAIN}, {WAIT}", timeout=30000)
    active, other = _who_acts(host, guest)
    journey.shot(screen, "05_combat_start_screen")
    # The active player: hit-chance tooltip and target chips, then an attack spends the action pip.
    swing = _hit_chance(active)
    assert active.locator("[data-testid=pip-action].on").count() == 1
    assert active.locator("[data-testid=target-chip][data-side=hostile]").count() == 2
    swing.hover()
    tip = swing.locator(".hb-tip").text_content() or ""
    assert "AC" in tip and "Hits" in tip
    journey.shot(active, "06_hotbar_and_targets_phone")
    # The other player cannot act but can suggest.
    assert other.locator(WAIT).is_visible()
    assert other.locator("[data-testid=end-turn]").count() == 0
    other.fill("[data-testid=suggest-input]", "go for the left goblin")
    other.click("[data-testid=suggest-send]")
    active.wait_for_selector("[data-testid=suggestion]", timeout=10000)
    assert "left goblin" in active.locator("[data-testid=suggestion]").first.inner_text()
    swing.click()
    active.wait_for_selector("[data-testid=pip-action].spent", timeout=20000)
    screen.wait_for_selector("[data-testid=event-line]", timeout=20000)
    journey.shot(active, "07_after_attack_pips")
    journey.shot(other, "08_other_player_view")


def _same_combat(page: Page, host: Page) -> None:
    """The restored round and active creature equal what the player who stayed sees (live state)."""
    for _ in range(50):
        mine = page.evaluate(f"JSON.stringify({COMBAT_POS})")
        if mine == host.evaluate(f"JSON.stringify({COMBAT_POS})") and mine != "null":
            return
        page.wait_for_timeout(200)
    raise AssertionError("the reconnected page never matched the table's combat state")


def _stage_reconnect_screen(journey: Journey, base: str, screen: Page, host: Page) -> Page:
    """Close the screen (socket drops), reopen it: story, board and dice must all come back."""
    screen.wait_for_function(ALL_TOLD, timeout=20000)  # never capture a line still being typed
    texts = [" ".join(t.split()) for t in screen.locator(NARRATION).all_inner_texts()]
    screen.wait_for_timeout(800)
    rolls = screen.evaluate(DICE_TEXTS)
    assert rolls, "the fight so far must have shown dice"
    context = screen.context
    screen.close()
    page = journey.new_page(context, "Screen-again")
    page.goto(f"{base}/screen")
    page.wait_for_selector("[data-testid=board]:not([hidden])", timeout=20000)
    page.wait_for_function(
        f"document.querySelectorAll('{NARRATION}').length >= {len(texts)}", timeout=20000
    )
    page.wait_for_function(ALL_TOLD, timeout=20000)
    assert [" ".join(t.split()) for t in page.locator(NARRATION).all_inner_texts()][
        : len(texts)
    ] == texts
    _same_combat(page, host)
    # M9.4: the recent rolls come back from story_history after a reconnect.
    page.wait_for_function(f"{DICE_TEXTS}.length >= {len(rolls)}", timeout=20000)
    assert rolls[0] in page.evaluate(DICE_TEXTS), "the newest roll before the drop is shown"
    assert page.locator("[data-testid=init-entry]").count() == 4
    assert page.locator("[data-testid=token][data-side=hostile]").count() == 2
    page.wait_for_selector("[data-testid=event-line]", timeout=20000)
    journey.shot(page, "09_screen_after_reconnect")
    return page


def _stage_reconnect_phone(journey: Journey, base: str, guest: Page, host: Page) -> Page:
    """Close B's phone (socket drops), reopen with the same token; the controller must come back."""
    me = guest.evaluate("window.aidm.store.get().me.playerId")
    line = guest.evaluate(
        "(() => { const i = window.aidm.story.items.at(-1);"
        " return (i.text ?? i.sentences.map((s) => s.text).join(' ')).trim(); })()"
    )
    context = guest.context
    guest.close()
    page = journey.new_page(context, "Bo-again")
    page.goto(f"{base}/play")
    page.wait_for_selector("[data-testid=controller]", timeout=20000)
    assert page.evaluate("window.aidm.store.get().me.playerId") == me
    # The story came back from story_history (the table may have moved on meanwhile): the line
    # the phone showed before the drop is in it, and the last-line control shows something.
    page.wait_for_function(
        "(line) => window.aidm.story.items.some((i) =>"
        " (i.text ?? i.sentences.map((s) => s.text).join(' ')).includes(line))",
        arg=line,
        timeout=20000,
    )
    assert page.inner_text("[data-testid=last-line]").strip()
    assert page.locator("[data-testid=strip-name]").inner_text() == "Mira"
    _same_combat(page, host)
    page.wait_for_selector(f"{MAIN}, {WAIT}", timeout=20000)
    journey.shot(page, "10_phone_after_reconnect")
    return page


def _end_turn(page: Page) -> None:
    before = page.evaluate(f"JSON.stringify({COMBAT_POS})")
    page.click("[data-testid=end-turn]")
    page.wait_for_function(f"JSON.stringify({COMBAT_POS}) !== {before!r}", timeout=45000)


def _pass_until_my_attack(me: Page, other: Page) -> None:
    """End whichever turn is open (monsters play on their own) until `me` has an unspent action."""
    for _ in range(80):
        if me.locator(MAIN).count() and me.locator("[data-testid=pip-action].on").count():
            return
        for page in (other, me):
            if page.locator("[data-testid=end-turn]:visible").count():
                _end_turn(page)
                break
        me.wait_for_timeout(300)
    raise AssertionError("the reconnected player never got a fresh turn")


def _stage_resume_play(journey: Journey, screen: Page, back: Page, other: Page) -> None:
    _pass_until_my_attack(back, other)
    swing = _hit_chance(back)
    events = screen.locator("[data-testid=event-line]").count()
    swing.click()
    back.wait_for_selector("[data-testid=pip-action].spent", timeout=20000)
    screen.wait_for_function(
        f"document.querySelectorAll('[data-testid=event-line]').length > {events}", timeout=20000
    )
    journey.shot(back, "11_reconnected_player_acts")


def test_full_journey_screen_and_two_phones_join_play_fight_and_reconnect(
    browser: Browser, journey_server: LiveServer, shots_dir: Path
) -> None:
    journey = Journey(shots_dir)
    screen, host, guest = _stage_start(journey, browser, journey_server.base)
    _assert_streamed(journey, screen, host, guest)
    _stage_action(journey, screen, host, guest)
    _stage_combat(journey, screen, host, guest)
    screen = _stage_reconnect_screen(journey, journey_server.base, screen, host)
    back = _stage_reconnect_phone(journey, journey_server.base, guest, host)
    _stage_resume_play(journey, screen, back, host)
    assert journey.errors == []
