"""M20.7 readable lines (playtest 3, D9 and D10): an engine statement sits on its own line on the
screen and in the phone's story box, prose stays one paragraph, and an NPC's reply reads once as
`Name: "..."`, also after a reload (story_history keeps the breaks as newlines)."""

from pathlib import Path

from playwright.sync_api import Browser, Page

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import HD, go_tab, snap, start_with_screen

PROSE = ("The ferry creaks against the jetty.", "Fog curls over the black water.")
LINES = ("Slendee gains True Strike.", "2 Giant Rats are surprised.")
SPEECH = ("Leave the lantern.", "The water remembers.")
WARDEN = "Warden Sellen Ost"
SAID = f'{WARDEN}: "Leave the lantern. The water remembers."'

SEND = """([prose, lines, speech, who]) => {
  const d = window.aidm.dispatch;
  const chunk = (id, index, text, more) => d({type: 'narration_chunk', id, index, text, ...more});
  let i = 0;
  for (const text of prose) chunk('rl1', i++, text, {tone: 'combat'});
  for (const text of lines) chunk('rl1', i++, text, {tone: 'combat', line: true});
  d({type: 'narration_done', id: 'rl1'});
  i = 0;
  for (const text of speech) chunk('rl2', i++, text, {tone: 'social', speaker: who});
  d({type: 'narration_done', id: 'rl2'});
}"""
READY = "document.querySelectorAll('[data-testid=narration].done').length >= 2"


def _send(page: Page) -> None:
    page.evaluate(SEND, [list(PROSE), list(LINES), list(SPEECH), WARDEN])


def _tops(page: Page, selector: str) -> list[float]:
    return page.eval_on_selector_all(
        selector, "els => els.map((e) => e.getBoundingClientRect().top)"
    )


def test_screen_puts_each_statement_on_its_own_line(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, _host, _guest = start_with_screen(browser, live_server.base, errors, screen_size=HD)
    _send(screen)
    screen.wait_for_function(READY, timeout=15000)
    para = screen.locator("[data-testid=narration][data-id=rl1]")
    para.locator("[data-testid=narration-line]").first.wait_for()
    prose = _tops(screen, "[data-id=rl1] .sentence:not(.line)")
    lines = _tops(screen, "[data-id=rl1] [data-testid=narration-line]")
    assert prose[0] == prose[1], "prose stays one paragraph"
    assert prose[1] < lines[0] < lines[1], "each statement starts its own line"
    speech = screen.locator("[data-id=rl2] [data-testid=speech]")
    assert speech.count() == 1, "the reply is one speech block"
    assert speech.inner_text() == SAID
    snap(screen, shots_dir, "m20_readable_lines_screen", 1920)
    assert errors == []


def test_phone_story_and_reload_keep_the_lines(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    _screen, host, _guest = start_with_screen(browser, live_server.base, errors, screen_size=HD)
    _send(host)
    go_tab(host, "journal")
    host.click("[data-testid=jtab-story]")
    box = host.locator("[data-testid=last-line]")
    box.wait_for(state="visible")
    host.wait_for_function(
        "(said) => [...document.querySelectorAll('[data-testid=last-line] p')]"
        ".some((p) => p.textContent === said)",
        arg=SAID,
        timeout=10000,
    )
    texts = box.locator("p").all_inner_texts()
    assert " ".join(PROSE) in texts and LINES[0] in texts and LINES[1] in texts
    snap(host, shots_dir, "m20_readable_lines_phone", 390)
    # A reload restores the story from story_history: the breaks survive as newlines.
    host.evaluate(
        "(t) => window.aidm.dispatch({type: 'story_history', dice: [], entries: ["
        "{kind: 'narration', seq: 1, id: 'h1', tone: 'combat', text: t}]})",
        "\n".join([" ".join(PROSE), *LINES, SAID]),
    )
    host.wait_for_function(
        "() => [...document.querySelectorAll('[data-testid=last-line] p')].length === 4"
    )
    assert box.locator("p").all_inner_texts() == [" ".join(PROSE), *LINES, SAID]
    assert errors == []
