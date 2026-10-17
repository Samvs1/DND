"""The roll stage (M26.6, docs/next/GOAL_DICE.md): a check out of combat takes the whole TV, the
story waits for its verdict, the roller's phone shows the same roll, and every case (advantage,
natural 20, natural 1, a skip) plays as designed. Shows run at full speed here."""

from playwright.sync_api import Browser, Page

from tests.ui.conftest import LiveServer, open_screen
from tests.ui.table_helpers import HAS_TEXT, PHONE, WIDE, quiet_scribe, start_table

FULL_SPEED = "window.__aidmShowScale = 1; window.__aidmSfxLog = [];"
STAGE = "[data-testid=roll-stage]"
VERDICT = "[data-testid=stage-verdict]"
PHONE_VERDICT = "[data-testid=roll-card-verdict]:not([hidden])"
LINES = "[...document.querySelectorAll('[data-testid=event-line]')].map((n) => n.textContent)"
TOLD = "document.querySelectorAll('[data-testid=narration]').length"
BRIENNE = "window.aidm.store.get().snapshot.state.party.find((c) => c.name === 'Brienne').id"
PUSH = """([seq, dice]) => window.aidm.pacer.push({ type: 'dice_roll', seq, dice: {
  expression: '1d20', adv: 'normal', modifier: 2, label: 'Stealth', kind: 'check', target: 15,
  difficulty: 'medium', parts: [{ name: 'DEX', value: 2 }], adv_why: [], crit: false,
  ...dice } })"""


def _text(page: Page, selector: str, timeout: int) -> str:
    page.wait_for_selector(selector, timeout=timeout)
    return page.locator(selector).first.inner_text()


def _table(browser: Browser, base: str, errors: list[str]) -> tuple[Page, Page]:
    screen = open_screen(browser, base, errors, WIDE, FULL_SPEED)
    host, guest = start_table(browser, base, PHONE, errors)
    screen.wait_for_function(HAS_TEXT, timeout=20000)
    quiet_scribe(screen, host, guest)
    return screen, host


def _push(screen: Page, seq: int, **dice: object) -> None:
    hero = screen.evaluate(BRIENNE)
    screen.evaluate(PUSH, [seq, {"roller_id": hero, **dice}])
    screen.wait_for_selector(STAGE, timeout=5000)


def test_a_search_plays_the_stage_and_the_story_waits_for_its_verdict(
    browser: Browser, scripted_server: LiveServer
) -> None:
    errors: list[str] = []
    screen, host = _table(browser, scripted_server.base, errors)
    host.evaluate("window.__aidmShowScale = 1")
    told = screen.evaluate(TOLD)
    host.fill("[data-testid=action-input]", "I search the room for anything hidden")
    host.click("[data-testid=action-send]")
    screen.wait_for_selector(STAGE, timeout=30000)
    assert "INVESTIGATION" in screen.locator(".ss-title").inner_text()
    # The roller's phone shows the same roll while the TV plays it.
    host.wait_for_selector("[data-testid=roll-card]", timeout=3000)
    # Nothing tells the result before the verdict: no check line, no new narration.
    assert not any("Investigation" in line for line in screen.evaluate(LINES))
    assert screen.evaluate(TOLD) == told
    verdict = _text(screen, VERDICT, 5000)
    assert verdict in ("SUCCESS", "FAILURE", "NATURAL 20", "NATURAL 1")
    assert _text(host, PHONE_VERDICT, 3000) == verdict
    screen.wait_for_selector(STAGE, state="detached", timeout=6000)
    screen.wait_for_function(f"{LINES}.some((l) => l.includes('Investigation'))", timeout=5000)
    screen.wait_for_function(f"{TOLD} > {told}", timeout=15000)
    played = screen.evaluate("window.__aidmSfxLog")
    assert any(s.startswith("dice_throw_") for s in played)
    assert any(s.startswith(("roll_success", "roll_failure", "roll_natural")) for s in played)
    assert errors == []


def test_advantage_drops_the_lower_die_and_names_why(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    screen, _host = _table(browser, live_server.base, errors)
    _push(
        screen,
        9001,
        expression="2d20",
        rolls=[6, 13],
        adv="advantage",
        adv_why=["the guards are distracted"],
        total=15,
        success=True,
    )
    assert screen.locator(".ss-adv").inner_text().startswith("ADVANTAGE")
    screen.wait_for_selector("[data-testid=show-die]", timeout=3000)  # thrown after the 0.5 s read
    assert screen.locator("[data-testid=show-die]").count() == 2
    screen.wait_for_selector(".sh-die.dropped", timeout=4000)
    assert screen.locator(".sh-die.dropped .sh-num").inner_text() == "6"
    assert _text(screen, VERDICT, 5000) == "SUCCESS"
    assert screen.locator("[data-testid=stage-total]").inner_text() == "15"
    assert errors == []


N20_WATCH = """window.__n20 = []; window.__n20t0 = null;
const start = AudioBufferSourceNode.prototype.start;
AudioBufferSourceNode.prototype.start = function (...a) {
  const n20 = this.buffer && Math.abs(this.buffer.duration - 3.0) < 0.05;
  if (n20) window.__n20t0 = performance.now();
  return start.apply(this, a);
};
new MutationObserver((changes) => changes.forEach((c) => c.addedNodes.forEach((n) => {
  const mark = (name) => window.__n20.push([name, performance.now()]);
  if (!n.classList) return;
  if (n.classList.contains('sh-ring')) mark('flare');
  if (n.matches('[data-testid=stage-verdict]')) mark('banner');
  if (n.classList.contains('sh-burst')) mark('spark');
}))).observe(document, { childList: true, subtree: true });"""
NAT20_LOADED = """() => performance.getEntriesByType('resource')
  .some((e) => e.name.endsWith('/roll_natural_20.mp3') && e.responseEnd > 0)"""
MY_HERO = (
    "async () => (await import('/web/js/combat/model.js')).myCreatureId(window.aidm.store.get())"
)
LEAD = 0.03  # js/show/natural20.js: a visual fires this early to be seen on its beat


def _n20_table(browser: Browser, base: str, errors: list[str]) -> tuple[Page, Page]:
    screen = open_screen(browser, base, errors, WIDE, FULL_SPEED + N20_WATCH)
    host, guest = start_table(browser, base, PHONE, errors)
    screen.wait_for_function(HAS_TEXT, timeout=20000)
    quiet_scribe(screen, host, guest)
    return screen, host


def test_a_natural_20_plays_its_beats_in_order_and_a_natural_1_cracks(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    screen, _host = _n20_table(browser, live_server.base, errors)
    _push(screen, 9002, rolls=[20], total=22, success=True)
    assert _text(screen, VERDICT, 6000) == "NATURAL 20"
    assert screen.locator(".sh-die.gold").count() == 1
    assert screen.locator("[data-testid=stage-total]").inner_text() == "22"
    screen.wait_for_selector(".sh-burst", timeout=3000)  # the spark jumps after the banner
    order = [name for name, _at in screen.evaluate("window.__n20")]
    assert order == ["flare", "banner", "spark"], order
    screen.wait_for_selector(STAGE, state="detached", timeout=8000)
    _push(screen, 9003, rolls=[1], total=3, success=False)
    assert _text(screen, VERDICT, 6000) == "NATURAL 1"
    assert screen.locator(".sh-die.cracked").count() == 1
    assert "roll_natural_20" in screen.evaluate("window.__aidmSfxLog")
    assert errors == []


def test_the_natural_20_lands_on_its_sound(browser: Browser, live_server: LiveServer) -> None:
    """The show runs on the sound's clock as heard (owner sign-off on prototype v17): the flare on
    the ignite hit (0.21 s), the banner's entrance 0.26 s before the slam (1.315 s) so it lands on
    it, the spark 40 ms before the recording's own ring (1.79 s); each fires LEAD early, then the
    speakers' delay (headless ~0.05 s) and a frame come on top."""
    errors: list[str] = []
    screen, _host = _n20_table(browser, live_server.base, errors)
    screen.wait_for_function(NAT20_LOADED, timeout=10000)
    screen.wait_for_timeout(400)  # decoded
    _push(screen, 9005, rolls=[20], total=22, success=True)
    screen.wait_for_selector(".sh-burst", timeout=8000)
    t0 = screen.evaluate("window.__n20t0")
    assert t0 is not None, "the natural 20 sound did not play"
    seen = {name: (at - t0) / 1000 for name, at in screen.evaluate("window.__n20")}
    want = {"flare": 0.21, "banner": 1.315 - 0.26, "spark": 1.79 - 0.04}
    for name, at in want.items():
        assert at - LEAD - 0.02 <= seen[name] <= at - LEAD + 0.2, (name, seen)
    assert errors == []


def test_the_phone_never_shows_a_natural_20_before_the_tv(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    screen, host = _table(browser, live_server.base, errors)
    host.evaluate("window.__aidmShowScale = 1")
    mine = host.evaluate(MY_HERO)
    for page in (screen, host):
        page.evaluate(
            PUSH, [9006, {"roller_id": mine, "rolls": [20], "total": 22, "success": True}]
        )
    assert _text(host, PHONE_VERDICT, 8000) == "NATURAL 20"
    # The TV's banner is in when the phone shows the verdict (it slams 1.3 s into the sound).
    assert screen.locator(VERDICT).count() == 1
    assert errors == []


def test_a_click_on_the_screen_skips_to_the_verdict(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    screen, _host = _table(browser, live_server.base, errors)
    _push(screen, 9004, rolls=[9], total=11, success=False)
    screen.wait_for_timeout(300)
    started = screen.evaluate("performance.now()")
    screen.mouse.click(640, 400)
    screen.wait_for_selector(STAGE, state="detached", timeout=2000)
    assert screen.evaluate("performance.now()") - started < 1200
    assert errors == []
