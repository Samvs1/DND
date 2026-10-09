"""Browser tests of the /screen spectator view and the music (M8.3).

The screen's audio elements are a fake (`add_init_script`): `play()` resolves, `pause()` is
recorded and the test ends a stinger by hand, so which track plays is asserted exactly.
"""

from pathlib import Path

from playwright.sync_api import Browser, Page, ViewportSize

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import PHONE, WIDE, quiet_scribe, snap, start_table

FULL_HD = ViewportSize(width=1920, height=1080)
FAKE_AUDIO = """() => {
  window.__clips = [];
  window.__aidmMakeAudio = (url) => {
    const clip = {
      url, volume: 1, paused: true, loop: false, preload: '', onended: null, onerror: null,
      play() { this.paused = false; return Promise.resolve(); },
      pause() { this.paused = true; },
    };
    window.__clips.push(clip);
    return clip;
  };
}"""
MUSIC = "window.aidm.music.state()"
LIVE_MUSIC = (
    "window.__clips.filter((c) => c.url.includes('/music/') && !c.paused).map((c) => c.url)"
)
SPEECH = "/tts/" + "d" * 40 + ".mp3"
STAND_DOWN = """() => {
  const snap = window.aidm.store.get().snapshot;
  window.aidm.dispatch({ ...snap, state: { ...snap.state, combat: null } });
}"""

DEFEATED = """() => {
  const snap = window.aidm.store.get().snapshot;
  const state = { ...snap.state, combat: null, phase: 'defeated', defeat: 'All is lost.' };
  window.aidm.dispatch({ ...snap, state });
}"""


def _screen(browser: Browser, base: str, size: ViewportSize, errors: list[str]) -> Page:
    page = browser.new_context(viewport=size).new_page()
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.add_init_script(f"({FAKE_AUDIO})()")
    page.goto(f"{base}/screen")
    page.wait_for_selector("[data-testid=screen-waiting]:not([hidden])")
    return page


def _names(page: Page) -> list[str]:
    return page.evaluate(LIVE_MUSIC)


def test_screen_shows_the_story_and_party_read_only_and_mutes_players(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    screen = _screen(browser, live_server.base, WIDE, errors)
    assert screen.locator("[data-testid=lan-url]").count() >= 1  # invite panel while waiting
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    screen.wait_for_selector("[data-testid=screen-table]:not([hidden])", timeout=20000)
    screen.wait_for_function(
        "[...document.querySelectorAll('[data-testid=narration]')]"
        ".some((n) => n.textContent.trim().length > 20)",
        timeout=20000,
    )
    assert screen.locator("[data-testid=party-card]").count() == 2
    assert screen.locator("[data-testid=scene-name]").inner_text().strip()
    for hidden in ("action-input", "hotbar", "sheet-open", "open-settings"):
        assert screen.locator(f"[data-testid={hidden}]").count() == 0, hidden
    assert screen.locator("[data-testid=board]:not([hidden])").count() == 0  # no fight yet
    assert screen.evaluate("window.aidm.store.get().joined") is False  # watching, not seated
    # The server counted the screen: players default to silent, the screen plays.
    host.wait_for_function("window.aidm.audio.state().muted === true")
    assert screen.evaluate("window.aidm.audio.state().muted") is False
    assert host.evaluate("window.aidm.store.get().snapshot.state.screens") == 1
    screen.close()
    host.wait_for_function("window.aidm.audio.state().muted === false")  # the screen left
    assert errors == []


def test_screen_plays_narration_and_music_follows_the_fight(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen = _screen(browser, combat_server.base, WIDE, errors)
    host, _guest = start_table(browser, combat_server.base, PHONE, errors)
    screen.wait_for_selector("[data-testid=screen-table]:not([hidden])", timeout=20000)
    quiet_scribe(screen, host)
    screen.wait_for_function("window.aidm.music.state().playing === 'exploration'", timeout=20000)
    assert _names(screen) == [screen.evaluate("window.aidm.music.state().url")]
    assert _names(screen)[0].endswith("/audio/music/ambient.mp3")
    screen.evaluate(
        "(url) => window.aidm.dispatch({ type: 'narration_chunk', id: 'n950', index: 0,"
        " text: 'The screen reads this aloud.', audio_url: url, tone: 'exploration' })",
        SPEECH,
    )
    screen.wait_for_function(f"window.aidm.audio.state().playing === '{SPEECH}'", timeout=10000)
    host.fill("[data-testid=action-input]", "I ambush the goblins from the shadows")
    host.click("[data-testid=action-send]")
    screen.wait_for_selector("[data-testid=board]:not([hidden])", timeout=30000)
    assert screen.locator("[data-testid=zone]").count() >= 3
    assert screen.locator("[data-testid=token][data-side=hostile]").count() == 2
    assert screen.locator("[data-testid=init-entry]").count() == 4
    for hidden in ("zone-go", "hotbar", "action-input"):
        assert screen.locator(f"[data-testid={hidden}]").count() == 0, hidden
    screen.wait_for_function("window.aidm.music.state().playing === 'combat'", timeout=20000)
    screen.wait_for_function(f"({LIVE_MUSIC}).length === 1", timeout=10000)  # crossfade done
    assert _names(screen)[0].endswith("/audio/music/combat.mp3")
    screen.wait_for_selector("[data-testid=token]")
    # Wait for a hero's turn: the server is then idle, so no late snapshot can undo STAND_DOWN.
    screen.wait_for_selector("[data-testid=init-entry].ally.current", timeout=30000)
    snap(screen, shots_dir, "screen", 1280)
    screen.set_viewport_size(FULL_HD)
    snap(screen, shots_dir, "screen", 1920)
    # The fight ends: the victory stinger plays once, then the ambient bed returns.
    screen.evaluate(STAND_DOWN)
    screen.wait_for_function(f"({MUSIC}).playing === 'victory'", timeout=10000)
    screen.wait_for_function(f"({LIVE_MUSIC}).length === 1", timeout=10000)
    assert _names(screen)[0].endswith("/audio/music/victory.mp3")
    screen.evaluate(
        "[...window.__clips].reverse().find((c) => c.url.includes('victory')).onended()"
    )
    screen.wait_for_function(f"({MUSIC}).playing === 'exploration'", timeout=10000)
    # A party wipe (M11.1): the DEFEATED phase keeps the screen up and plays the defeat track.
    screen.evaluate(DEFEATED)
    screen.wait_for_function(f"({MUSIC}).playing === 'defeat'", timeout=10000)
    assert screen.locator("[data-testid=screen-table]:not([hidden])").count() == 1
    assert errors == []


def test_music_is_silent_when_muted_or_a_screen_plays_it(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    screen = _screen(browser, live_server.base, WIDE, errors)
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    host.evaluate(FAKE_AUDIO)
    host.evaluate("window.aidm.store.update({})")  # re-evaluate the music with the fake installed
    assert host.evaluate(MUSIC)["muted"] is True and host.evaluate(MUSIC)["playing"] is None
    assert host.evaluate("window.__clips.filter((c) => c.url.includes('/music/')).length") == 0
    screen.wait_for_function("window.aidm.music.state().playing === 'exploration'", timeout=20000)
    assert errors == []
