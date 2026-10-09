"""M16.2 owner rule: only the screen plays sound and shows the Scribe.

Phones create no audio element and no popup; /screen has a sound gate; the Scribe is skipped from
the Host panel or on the screen's own overlay."""

from pathlib import Path

from playwright.sync_api import Browser

from tests.ui.conftest import LiveServer, open_screen
from tests.ui.table_helpers import PHONE, WIDE, go_tab, snap, start_fight, start_table

FAKE = """() => {
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
LINE = """(id) => window.aidm.dispatch({ type: 'scribe_line', line_id: id, group: 'welcome_first',
  text: 'Welcome, travellers, to the ledger.', audio_url: '/scribe/' + id + '.mp3',
  to_player_id: null })"""
CARD = "[data-testid=screen-scribe]"
GATE = "[data-testid=sound-gate]"


def test_phone_creates_no_audio_and_no_scribe_popup(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    _screen, host, _guest = start_fight(browser, combat_server.base, errors)
    host.evaluate(FAKE)
    host.evaluate(
        "() => window.aidm.dispatch({ type: 'narration_chunk', id: 'n1', index: 0,"
        " text: 'A quiet phone line.', audio_url: '/tts/" + "a" * 40 + ".mp3', tone: 'combat' })"
    )
    host.evaluate(LINE, "welcome_x")
    host.evaluate(  # the fight music would start on a change of the snapshot
        "() => { const s = window.aidm.store.get().snapshot;"
        " window.aidm.store.update({ snapshot: { ...s, state: { ...s.state, combat: null } } });"
        " window.aidm.store.update({ snapshot: s }); }"
    )
    host.wait_for_timeout(600)
    assert host.evaluate("window.__clips.length") == 0
    assert host.evaluate("window.aidm.audio.state().muted") is True
    go_tab(host, "more")
    snap(host, shots_dir, "phone_more_silent", 390)
    assert host.locator(".sc-banner, [data-testid=controller-scribe-line]").count() == 0
    assert host.locator(f"{CARD}, {GATE}").count() == 0
    assert errors == []


def test_screen_gate_at_load_blocked_narration_and_blocked_scribe(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.add_init_script(f"({FAKE})()")
    page.goto(f"{live_server.base}/screen")
    page.wait_for_selector(f"{GATE}:visible")
    assert page.get_attribute(GATE, "role") == "dialog"
    snap(page, shots_dir, "screen_sound_gate", 1280)
    page.click("[data-testid=sound-gate-button]")
    page.wait_for_selector(GATE, state="hidden")
    # A clip the browser rejects brings the gate back; a click resumes.
    page.evaluate("window.__block = true")
    page.evaluate("window.aidm.audio.enqueue('/tts/" + "b" * 40 + ".mp3', () => {})")
    page.wait_for_selector(f"{GATE}:visible")
    page.evaluate("window.__block = false")
    page.click("[data-testid=sound-gate-button]")
    page.wait_for_selector(GATE, state="hidden")
    # A blocked Scribe line keeps his subtitle, and his clip starts again after the click.
    page.evaluate("window.__block = true; window.__clips.length = 0")
    page.evaluate(LINE, "blocked1")
    page.wait_for_selector(f"{GATE}:visible")
    assert page.locator(CARD).is_visible()
    page.evaluate("window.__block = false")
    page.keyboard.press("Enter")
    page.wait_for_selector(GATE, state="hidden")
    page.wait_for_function(
        "window.__clips.some((c) => c.url.includes('blocked1') && !c.paused)", timeout=5000
    )
    assert page.locator(CARD).is_visible()
    assert errors == []


def test_host_panel_skip_and_screen_overlay_skip(browser: Browser, live_server: LiveServer) -> None:
    errors: list[str] = []
    screen = open_screen(browser, live_server.base, errors, WIDE, f"({FAKE})()")
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    screen.wait_for_selector(f"{CARD}:not([hidden])", timeout=20000)  # his real welcome
    go_tab(host, "more")
    host.click("[data-testid=open-host]")
    host.click("[data-testid=host-scribe-skip]")
    screen.wait_for_selector(CARD, state="hidden", timeout=10000)
    screen.evaluate(LINE, "skipme2")
    screen.wait_for_selector(f"{CARD}:not([hidden])")
    screen.click("[data-testid=screen-scribe-skip]")
    screen.wait_for_selector(CARD, state="hidden", timeout=10000)
    assert errors == []
