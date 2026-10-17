"""M26.8: the dice sounds. The phones' remote sets their level and mute on the screen, the screen's
gear has them too, the player never plays the same variant twice in a row, a sound that failed to
load is tried again, and audio the browser suspended wakes up on the next play."""

from playwright.sync_api import Browser, Page

from tests.ui.conftest import LiveServer, open_screen
from tests.ui.table_helpers import HAS_TEXT, PHONE, WIDE, go_tab, quiet_scribe, start_table

SCREEN_AUDIO = "window.aidm.store.get().snapshot.state.audio"
STORED = "JSON.parse(window.localStorage.getItem('aidm.settings') || '{}')"
PICKS = """async () => {
  const { createSfx, variantsOf } = await import('/web/js/audio/sfx.js');
  const store = { get: () => ({}) };
  const sfx = createSfx({ store, mode: 'screen', fetchFn: () => Promise.reject() });
  const picks = Array.from({ length: 40 }, () => sfx.pick('dice_throw'));
  return {
    picks, all: variantsOf('dice_throw'), hit: variantsOf('hit'), one: variantsOf('crit'),
    success: variantsOf('roll_success'),
  };
}"""


def test_the_phone_remote_sets_the_dice_sound_on_the_screen(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    screen = open_screen(browser, live_server.base, errors, WIDE)
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    screen.wait_for_function(HAS_TEXT, timeout=20000)
    quiet_scribe(screen, host)
    go_tab(host, "more")
    host.fill("[data-testid=remote-effects-volume]", "30")
    host.check("[data-testid=remote-effects-mute]")
    screen.wait_for_function(f"() => {SCREEN_AUDIO}.effects_muted === true", timeout=10000)
    assert screen.evaluate(SCREEN_AUDIO)["effects_volume"] == 30
    stored = screen.evaluate(STORED)
    assert stored["effectsVolume"] == 30 and stored["effectsMute"] is True
    # The screen's own gear shows the same two controls.
    screen.locator("[data-testid=screen-gear]").click()
    screen.wait_for_selector("[data-testid=settings][open]")
    assert screen.locator("[data-testid=set-effects-volume]").input_value() == "30"
    assert screen.locator("[data-testid=set-effects-mute]").is_checked()
    assert errors == []


COUNT_AUDIO = """window.__starts = 0; window.__ctxs = [];
const start = AudioBufferSourceNode.prototype.start;
AudioBufferSourceNode.prototype.start = function (...a) {
  window.__starts += 1;
  return start.apply(this, a);
};
const Ctx = window.AudioContext;
window.AudioContext = class extends Ctx {
  constructor(...a) { super(...a); window.__ctxs.push(this); }
};"""
UNTIL_HEARD = """async (sfx) => {
  const until = Date.now() + 8000;
  while (Date.now() < until && window.__starts === 0) {
    sfx.play('dice_clack', { file: 'dice_clack_1' });
    await new Promise((done) => setTimeout(done, 100));
  }
  return window.__starts;
}"""
FLAKY = f"""async () => {{
  const {{ createSfx }} = await import('/web/js/audio/sfx.js');
  const tries = {{}};
  const fetchFn = (url) => {{ // the first three requests of each file are throttled
    tries[url] = (tries[url] || 0) + 1;
    return tries[url] <= 3 ? Promise.resolve(new Response('busy', {{ status: 429 }})) : fetch(url);
  }};
  const sfx = createSfx({{ store: {{ get: () => ({{}}) }}, mode: 'screen', fetchFn }});
  sfx.unlock();
  const starts = await ({UNTIL_HEARD})(sfx);
  return {{ starts, tries: Math.max(...Object.values(tries)) }};
}}"""
SUSPENDED = f"""async () => {{
  const {{ createSfx }} = await import('/web/js/audio/sfx.js');
  const sfx = createSfx({{ store: {{ get: () => ({{}}) }}, mode: 'screen' }});
  sfx.unlock();
  await ({UNTIL_HEARD})(sfx);
  const ctx = window.__ctxs.at(-1);
  await ctx.suspend();
  const asleep = ctx.state;
  sfx.play('dice_clack', {{ file: 'dice_clack_1' }});
  await new Promise((done) => setTimeout(done, 400));
  return {{ asleep, after: ctx.state }};
}}"""


def _screen_with_counted_audio(browser: Browser, live_server: LiveServer) -> Page:
    page = browser.new_page()
    page.add_init_script(COUNT_AUDIO)
    page.goto(f"{live_server.base}/screen")
    page.wait_for_function("Boolean(window.aidm?.sfx)")
    page.mouse.click(5, 5)  # a user gesture: the browser lets the audio start
    return page


def test_a_throttled_sound_is_tried_again_until_it_plays(
    browser: Browser, live_server: LiveServer
) -> None:
    got = _screen_with_counted_audio(browser, live_server).evaluate(FLAKY)
    # Three failed tries inside one load, then the next play loads it again: a 4th request, heard.
    assert got["starts"] >= 1 and got["tries"] == 4


def test_suspended_audio_wakes_on_the_next_play(browser: Browser, live_server: LiveServer) -> None:
    got = _screen_with_counted_audio(browser, live_server).evaluate(SUSPENDED)
    assert got == {"asleep": "suspended", "after": "running"}


def test_a_variant_never_plays_twice_in_a_row(browser: Browser, live_server: LiveServer) -> None:
    page = browser.new_page()
    page.goto(f"{live_server.base}/screen")
    got = page.evaluate(PICKS)
    picks = got["picks"]
    assert all(a != b for a, b in zip(picks, picks[1:], strict=False))
    assert set(picks) <= set(got["all"]) and len(set(picks)) >= 4
    assert got["all"] == [f"dice_throw_{i}" for i in range(1, 7)]
    assert got["hit"] == ["hit", "hit_2"] and got["one"] == ["crit"]
    assert got["success"] == ["roll_success"]  # the approved sound, never alternated


def test_the_dice_timing_is_served_next_to_the_sounds(
    browser: Browser, live_server: LiveServer
) -> None:
    page = browser.new_page()
    page.goto(f"{live_server.base}/screen")
    page.wait_for_function("Boolean(window.aidm?.sfx)")
    timing = page.evaluate("() => window.aidm.sfx.loadTiming()")
    assert timing["land"] == 0.85
    assert len(timing["throw"]) == 6 and len(timing["throw_two"]) == 3
    assert all(track[-1][0] == 0.85 for track in timing["throw"].values())
