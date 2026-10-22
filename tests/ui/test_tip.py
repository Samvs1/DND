"""The ? tooltip (M28.2): open, flip, one at a time, close, focus, switch, no long press."""

from pathlib import Path

from playwright.sync_api import Browser, Page

from tests.ui.conftest import SHOTS, LiveServer
from tests.ui.table_helpers import go_tab, start_table
from tests.ui.test_panels import PHONE

OUT = SHOTS / "m28_2"
BTN = "[data-testid=settings] [data-testid=tip-btn]"
POP = "[data-testid=tip-pop]"
SETTINGS = "[data-testid=settings][open]"
ADD = """async () => {
  const { tipButton } = await import('/web/js/ui/tip.js');
  const dlg = document.querySelector('[data-testid=settings]');
  for (const [id, pos] of [['a', 'right:2px;bottom:2px'], ['b', 'right:2px;top:200px']]) {
    const b = tipButton('sheet:hp');
    b.dataset.pos = id;
    b.style.cssText = 'position:fixed;' + pos;
    dlg.append(b);
  }
}"""


def _open_settings(page: Page) -> None:
    go_tab(page, "more")
    page.click("[data-testid=open-settings]")
    page.wait_for_selector(SETTINGS)
    page.wait_for_selector(f"{BTN}:not([hidden])")


def _table(browser: Browser, base: str) -> tuple[Page, list[str]]:
    errors: list[str] = []
    host, _guest = start_table(browser, base, PHONE, errors)
    return host, errors


def _focused(page: Page) -> str:
    return str(page.evaluate("document.activeElement.dataset.testid"))


def test_tip_opens_on_tap_and_shows_text(browser: Browser, live_server: LiveServer) -> None:
    host, errors = _table(browser, live_server.base)
    _open_settings(host)
    assert host.get_attribute(BTN, "aria-label") == "What is Tooltips?"
    box = host.locator(BTN).bounding_box()
    assert box is not None and box["width"] >= 24 and box["height"] >= 24
    host.click(BTN)
    host.wait_for_selector(POP)
    assert "Tap a ? to see what a thing means" in host.inner_text(POP)
    assert _focused(host) == "tip-pop"
    OUT.mkdir(parents=True, exist_ok=True)
    host.screenshot(path=str(OUT / "open_settings.png"))
    assert errors == []


def test_tip_closes_on_x_outside_and_esc_and_focus_returns(
    browser: Browser, live_server: LiveServer
) -> None:
    host, _errors = _table(browser, live_server.base)
    _open_settings(host)
    host.click(BTN)
    host.click("[data-testid=tip-close]")
    assert host.locator(POP).count() == 0
    assert _focused(host) == "tip-btn"
    host.click(BTN)
    host.keyboard.press("Escape")
    assert host.locator(POP).count() == 0
    assert _focused(host) == "tip-btn"
    assert host.locator(SETTINGS).count() == 1  # Esc closed only the tip
    host.click(BTN)
    host.click("[data-testid=set-speed]")
    assert host.locator(POP).count() == 0


def test_tip_flips_at_the_edges_and_only_one_is_open(
    browser: Browser, live_server: LiveServer
) -> None:
    host, _errors = _table(browser, live_server.base)
    _open_settings(host)
    host.evaluate(ADD)
    host.wait_for_selector("[data-pos=a]:not([hidden])")
    OUT.mkdir(parents=True, exist_ok=True)
    names = {"a": "flip_bottom_right", "b": "flip_right_edge"}
    for pos in ("a", "b"):
        host.click(f"[data-pos={pos}]")
        box = host.locator(POP).bounding_box()
        assert box is not None
        assert box["x"] >= 0 and box["x"] + box["width"] <= PHONE["width"]
        assert box["y"] >= 0 and box["y"] + box["height"] <= PHONE["height"]
        assert host.locator(POP).count() == 1
        host.screenshot(path=str(OUT / f"{names[pos]}.png"))
    host.locator(f"{BTN}:not([data-pos])").dispatch_event("click")
    assert host.locator(POP).count() == 1
    assert "Tooltips" in host.inner_text(POP)


def test_tooltips_switch_hides_every_question_mark_and_survives_reload(
    browser: Browser, live_server: LiveServer
) -> None:
    host, _errors = _table(browser, live_server.base)
    _open_settings(host)
    host.uncheck("[data-testid=set-tooltips]")
    assert host.locator(f"{BTN}:not([hidden])").count() == 0
    host.reload()
    host.wait_for_selector("[data-testid=controller]", timeout=20000)
    go_tab(host, "more")
    host.click("[data-testid=open-settings]")
    host.wait_for_selector(SETTINGS)
    assert host.is_checked("[data-testid=set-tooltips]") is False
    assert host.locator(f"{BTN}:not([hidden])").count() == 0
    host.check("[data-testid=set-tooltips]")
    host.wait_for_selector(f"{BTN}:not([hidden])")


def test_no_long_press_handler_is_registered() -> None:
    source = (
        Path(__file__).resolve().parents[2] / "aidm" / "web" / "js" / "ui" / "tip.js"
    ).read_text(encoding="utf-8")
    for word in ("contextmenu", "touchstart", "setTimeout", "longpress"):
        assert word not in source


def test_failed_tips_show_no_question_mark_and_no_error(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    context = browser.new_context(viewport=PHONE)
    context.route("**/api/tips", lambda route: route.fulfill(status=500, body="boom"))
    page = context.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live_server.base)
    page.evaluate(
        """async () => { const m = await import('/web/js/ui/tip.js');
          const b = m.tipButton('word:tooltips'); document.body.append(b); await m.loadTips(); }"""
    )
    assert page.locator("[data-testid=tip-btn]:not([hidden])").count() == 0
    assert errors == []
    context.close()
