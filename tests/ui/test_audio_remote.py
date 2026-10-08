"""M11.5: separate narrator and music sound, the phone as a remote for the screen, the migration."""

from playwright.sync_api import Browser

from tests.ui.conftest import LiveServer, open_screen
from tests.ui.table_helpers import HAS_TEXT, PHONE, WIDE, go_tab, start_table

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
SEND = """([id, url]) => window.aidm.dispatch({
  type: 'narration_chunk', id, index: 0, text: 'A line for the speakers.', audio_url: url,
  tone: 'exploration' })"""
SCREEN_AUDIO = "window.aidm.store.get().snapshot.state.audio"
STORED = "JSON.parse(window.localStorage.getItem('aidm.settings') || '{}')"
URL = "/tts/" + "e" * 40 + ".mp3"
SAVED = '{"mute":false,"muteSet":false,"volume":40,"speed":"fast","size":"normal"}'


def _table(browser: Browser, live_server: LiveServer, errors: list[str]):
    screen = open_screen(browser, live_server.base, errors, WIDE, f"({FAKE_AUDIO})()")
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    screen.wait_for_function(HAS_TEXT, timeout=20000)
    go_tab(host, "more")
    return screen, host


def test_phone_sliders_reach_the_screen_state_and_its_audio_element(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    screen, host = _table(browser, live_server, errors)
    host.fill("[data-testid=remote-narration-volume]", "35")
    host.fill("[data-testid=remote-music-volume]", "20")
    screen.wait_for_function(f"() => {SCREEN_AUDIO}.narration_volume === 35", timeout=10000)
    audio = screen.evaluate(SCREEN_AUDIO)
    assert audio["music_volume"] == 20 and not audio["narration_muted"]
    assert screen.evaluate(STORED)["musicVolume"] == 20
    screen.evaluate(SEND, ["r1", URL])
    screen.wait_for_function("() => window.__clips.some((c) => c.url.includes('/tts/'))")
    volume = screen.evaluate("window.__clips.find((c) => c.url.includes('/tts/')).volume")
    assert abs(volume - 0.35) < 0.001
    assert errors == []


def test_each_channel_can_be_muted_from_the_phone(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    screen, host = _table(browser, live_server, errors)
    host.check("[data-testid=remote-music-mute]")
    screen.wait_for_function(f"() => {SCREEN_AUDIO}.music_muted === true", timeout=10000)
    assert screen.evaluate("window.aidm.music.state().muted") is True
    assert screen.evaluate("window.aidm.audio.state().muted") is False
    host.check("[data-testid=remote-narration-mute]")
    screen.wait_for_function(f"() => {SCREEN_AUDIO}.narration_muted === true", timeout=10000)
    assert screen.evaluate("window.aidm.audio.state().muted") is True
    host.uncheck("[data-testid=remote-music-mute]")
    screen.wait_for_function(f"() => {SCREEN_AUDIO}.music_muted === false", timeout=10000)
    assert screen.evaluate("window.aidm.music.state().muted") is False
    assert errors == []


def test_dragging_a_slider_is_debounced_and_never_rate_limited(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    _screen, host = _table(browser, live_server, errors)
    host.evaluate(
        """() => { const el = document.querySelector('[data-testid=remote-music-volume]');
        for (let v = 0; v <= 100; v += 2) {
          el.value = String(v); el.dispatchEvent(new Event('input', { bubbles: true })); } }"""
    )
    host.wait_for_function(f"() => {SCREEN_AUDIO}.music_volume === 100", timeout=10000)
    assert host.evaluate("window.aidm.store.get().errorCode") in (None, "")
    assert host.locator("[data-testid=banner-error]").count() == 0
    assert errors == []


def test_old_single_volume_migrates_into_both_levels(
    browser: Browser, live_server: LiveServer
) -> None:
    page = browser.new_context(viewport=PHONE).new_page()
    page.add_init_script(
        f"if (!window.localStorage.getItem('aidm.settings')) "
        f"window.localStorage.setItem('aidm.settings', '{SAVED}');"
    )
    page.goto(live_server.base)
    page.wait_for_selector("body")
    stored = page.evaluate(STORED)
    assert "volume" not in stored
    assert stored["narrationVolume"] == 40 and stored["musicVolume"] == 40
    assert stored["speed"] == "fast"
