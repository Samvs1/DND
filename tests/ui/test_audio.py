"""Browser tests of narration audio (M8.2, M11.4): ordered playback, text sync, mute, blocked hint.

The shared /screen is the audio device (it types the story in step with the clips); the phone only
keeps its own muted default.

The page's audio elements are replaced by a fake (`window.__aidmMakeAudio`): `play()` resolves (or
rejects as an autoplay block) and the test ends each clip by hand, so order is asserted exactly.
"""

from playwright.sync_api import Browser, Page

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import go_tab, start_with_screen

FAKE_AUDIO = """() => {
  window.__clips = [];
  window.__block = false;
  window.__aidmMakeAudio = (url) => {
    const clip = {
      url, volume: 1, paused: true, preload: '', onended: null, onerror: null,
      play() {
        if (window.__block) {
          return Promise.reject(Object.assign(new Error('blocked'), { name: 'NotAllowedError' }));
        }
        this.paused = false;
        return Promise.resolve();
      },
      pause() { this.paused = true; },
    };
    window.__clips.push(clip);
    return clip;
  };
}"""
SEND = """([id, index, text, url]) => window.aidm.dispatch({
  type: 'narration_chunk', id, index, text, audio_url: url, tone: 'exploration' })"""
STATE = "window.aidm.audio.state()"
URLS = [f"/tts/{c * 40}.mp3" for c in "abc"]
TEXTS = ["The first sentence rings out.", "A second one follows it.", "Then a third closes."]


def _sentence_text(page: Page, nid: str) -> str:
    return page.evaluate(
        "(id) => document.querySelector(`[data-id=${id}]`)?.textContent ?? ''",
        nid,
    )


def _setup(browser: Browser, live_server: LiveServer, errors: list[str]) -> Page:
    """The /screen of a started table with the fake audio installed."""
    screen, _host, _guest = start_with_screen(browser, live_server.base, errors)
    screen.evaluate(FAKE_AUDIO)
    return screen


def test_chunks_play_in_order_and_text_follows_audio(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    host = _setup(browser, live_server, errors)
    for i, (text, url) in enumerate(zip(TEXTS, URLS, strict=True)):
        host.evaluate(SEND, ["n900", i, text, url])
    state = host.evaluate(STATE)
    assert state["playing"] == URLS[0] and state["queued"] == URLS[1:]
    host.wait_for_function("(t) => document.body.textContent.includes(t)", arg=TEXTS[0])
    shown = _sentence_text(host, "n900")
    assert TEXTS[0] in shown and TEXTS[1] not in shown and TEXTS[2] not in shown
    host.evaluate("window.__clips[0].onended()")
    host.wait_for_function("(t) => document.body.textContent.includes(t)", arg=TEXTS[1])
    assert TEXTS[2] not in _sentence_text(host, "n900")
    assert host.evaluate(STATE)["playing"] == URLS[1]
    host.evaluate("window.__clips[1].onended()")
    host.wait_for_function("(t) => document.body.textContent.includes(t)", arg=TEXTS[2])
    host.evaluate("window.__clips[2].onended()")
    final = host.evaluate(STATE)
    assert final["played"] == URLS and final["playing"] is None and final["queued"] == []
    assert errors == []


def test_sentence_without_audio_is_typed_not_played(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    host = _setup(browser, live_server, errors)
    host.evaluate(SEND, ["n901", 0, "No voice for this line at all.", None])
    host.wait_for_function(
        "() => document.body.textContent.includes('No voice for this line at all.')", timeout=20000
    )
    assert host.evaluate("window.__clips.length") == 0
    assert errors == []


def test_mute_skips_audio_and_reveals_text(browser: Browser, live_server: LiveServer) -> None:
    errors: list[str] = []
    host = _setup(browser, live_server, errors)
    host.click("[data-testid=screen-gear]")
    host.wait_for_selector("[data-testid=settings][open]")
    host.check("[data-testid=set-mute]")
    host.click("[data-testid=settings-close]")
    host.evaluate(SEND, ["n902", 0, "Muted clients still read this.", URLS[0]])
    host.wait_for_function(
        "() => document.body.textContent.includes('Muted clients still read this.')", timeout=20000
    )
    state = host.evaluate(STATE)
    assert state["muted"] is True and state["playing"] is None and state["played"] == []
    assert host.evaluate("window.__clips.length") == 0
    assert errors == []


def test_muting_mid_queue_stops_playback_and_shows_the_rest(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    host = _setup(browser, live_server, errors)
    for i, (text, url) in enumerate(zip(TEXTS, URLS, strict=True)):
        host.evaluate(SEND, ["n903", i, text, url])
    host.click("[data-testid=screen-gear]")
    host.wait_for_selector("[data-testid=settings][open]")
    host.check("[data-testid=set-mute]")
    host.click("[data-testid=settings-close]")
    state = host.evaluate(STATE)
    assert state["playing"] is None and state["queued"] == []
    host.wait_for_function(
        "(t) => document.body.textContent.includes(t)", arg=TEXTS[2], timeout=20000
    )
    assert errors == []


def test_blocked_autoplay_shows_a_hint_and_a_click_enables_sound(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    host = _setup(browser, live_server, errors)
    host.evaluate("window.__block = true")
    host.evaluate(SEND, ["n904", 0, "This clip is held back.", URLS[0]])
    host.wait_for_selector("[data-testid=sound-gate]:visible", timeout=20000)
    assert host.locator("[data-testid=banner] button").count() == 0
    host.wait_for_function(
        "() => document.body.textContent.includes('This clip is held back.')", timeout=20000
    )
    host.evaluate("window.__block = false")
    host.click("[data-testid=sound-gate-button]")
    host.wait_for_selector("[data-testid=sound-gate]", state="hidden")
    host.evaluate(SEND, ["n904", 1, "Now the sound works.", URLS[1]])
    assert host.evaluate(STATE)["playing"] == URLS[1]
    assert errors == []


def test_phones_are_always_silent_even_without_a_screen(
    browser: Browser, live_server: LiveServer
) -> None:
    """M16.2 owner rule: only the screen plays sound, so a phone is always muted."""
    errors: list[str] = []
    _screen, host, _guest = start_with_screen(browser, live_server.base, errors)
    host.evaluate(FAKE_AUDIO)
    host.evaluate(
        """() => {
        const snap = window.aidm.store.get().snapshot;
        window.aidm.store.update({ snapshot: { ...snap, state: { ...snap.state, screens: 0 } } });
    }"""
    )
    assert host.evaluate(STATE)["muted"] is True
    go_tab(host, "more")
    host.click("[data-testid=open-settings]")
    host.wait_for_selector("[data-testid=settings][open]")
    assert host.locator("[data-testid=set-mute]").count() == 0
    assert host.locator("[data-testid=set-volume]").count() == 0
    assert errors == []
