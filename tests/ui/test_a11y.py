"""Accessibility checks (M8.4): names, dialogs, focus, live regions, text size, motion."""

from pathlib import Path

from playwright.sync_api import Browser, Page

from tests.ui.conftest import LiveServer
from tests.ui.kb_helpers import FOCUSED, activate, tab_to
from tests.ui.table_helpers import WIDE, snap, start_table

# A small axe-like audit run inside the page: images, controls, dialogs and duplicate ids.
AUDIT = """() => {
  const name = (el) => {
    const by = el.getAttribute('aria-labelledby');
    const parts = [el.getAttribute('aria-label'), el.getAttribute('title'), el.textContent];
    if (by) parts.push(...by.split(' ').map((id) => document.getElementById(id)?.textContent));
    if (el.id) {
      const labels = document.querySelectorAll(`label[for="${el.id}"]`);
      parts.push(...[...labels].map((l) => l.textContent));
    }
    if (el.closest('label')) parts.push(el.closest('label').textContent);
    parts.push(...[...el.querySelectorAll('img[alt]')].map((i) => i.getAttribute('alt')));
    return parts.filter(Boolean).join(' ').trim();
  };
  const problems = [];
  for (const img of document.images) {
    if (!img.hasAttribute('alt')) problems.push('img without alt: ' + img.src);
  }
  const controls = 'button, select, textarea, input:not([type=hidden]), a[href], [role=button]';
  for (const el of document.querySelectorAll(controls)) {
    if (el.closest('dialog:not([open])')) continue;  // closed panels are audited when they open
    if (!name(el)) problems.push('unnamed control: ' + el.outerHTML.slice(0, 100));
  }
  for (const d of document.querySelectorAll('dialog')) {
    if (!d.getAttribute('aria-labelledby') && !d.getAttribute('aria-label')) {
      problems.push('unnamed dialog: ' + (d.dataset.testid || ''));
    }
  }
  const seen = new Set();
  for (const el of document.querySelectorAll('[id]')) {
    if (seen.has(el.id)) problems.push('duplicate id: ' + el.id);
    seen.add(el.id);
  }
  if (document.documentElement.lang === '') problems.push('no html lang');
  return problems;
}"""
PANELS = ("journal", "map", "shop", "host", "settings")


def _audit(page: Page, label: str) -> None:
    assert page.evaluate(AUDIT) == [], label


def test_lobby_and_wizard_have_names_and_labels(browser: Browser, live_server: LiveServer) -> None:
    page = browser.new_context(viewport=WIDE).new_page()
    page.goto(f"{live_server.base}/play")
    page.wait_for_selector("#join-name")
    _audit(page, "join")
    page.fill("#join-name", "Ann")
    page.click("button[type=submit]")
    page.wait_for_selector("[data-testid=wizard-body] .wz-card")
    _audit(page, "wizard")


def test_table_panels_dialogs_focus_and_live_regions(
    browser: Browser, combat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, _guest = start_table(browser, combat_server.base, WIDE, errors)
    _audit(host, "table")
    # The feed is silent while it types; a finished paragraph is announced once in its own region.
    assert host.get_attribute("[data-testid=feed]", "aria-live") == "off"
    host.fill("[data-testid=action-input]", "I look around the room")
    host.click("[data-testid=action-send]")
    host.wait_for_function(
        "document.querySelector('[data-testid=narration-live]').textContent.trim().length > 20",
        timeout=30000,
    )
    host.wait_for_function("!document.querySelector('[data-testid=action-input]').disabled")
    # Escape closes each panel, focus returns to its button and the dialog traps Tab.
    for panel in PANELS:
        button = f"[data-testid=open-{panel}]"
        activate(host, button)
        dialog = f"[data-testid={panel}][open]"
        host.wait_for_selector(dialog)
        _audit(host, panel)
        for _ in range(40):
            host.keyboard.press("Tab")
            # Native modal dialogs make the page inert: focus stays inside or leaves (body).
            assert host.evaluate(
                f"(() => {{ const a = document.activeElement;"
                f" return a === document.body"
                f" || document.querySelector('{dialog}').contains(a); }})()"
            )
        host.keyboard.press("Escape")
        host.wait_for_selector(f"[data-testid={panel}]:not([open])", state="attached")
        assert host.evaluate(FOCUSED, button), f"focus not restored after {panel}"
    # Focus rings are drawn on keyboard focus.
    tab_to(host, "[data-testid=open-journal]")
    outline = host.evaluate(
        "(() => { const s = getComputedStyle(document.activeElement);"
        " return [s.outlineStyle, parseFloat(s.outlineWidth)]; })()"
    )
    assert outline == ["solid", 3]
    # The fight: the hotbar documents its number keys.
    host.fill("[data-testid=action-input]", "I ambush the goblins from the shadows")
    host.click("[data-testid=action-send]")
    host.wait_for_selector("[data-testid=board]:not([hidden])", timeout=30000)
    _audit(host, "combat")
    host.wait_for_function(
        "document.querySelector('[data-testid=hotbar-keys]') "
        "|| document.querySelector('[data-testid=hotbar-wait]')",
        timeout=30000,
    )
    keys = host.locator("[data-testid=hotbar-keys]")
    if keys.count():
        assert "1-9" in keys.inner_text()
        assert host.locator("[data-key='1'][aria-keyshortcuts='1']").count() == 1
    snap(host, shots_dir, "a11y_combat", 1280)
    assert errors == []


def test_text_size_and_reduced_motion_settings(browser: Browser, live_server: LiveServer) -> None:
    errors: list[str] = []
    host, _guest = start_table(browser, live_server.base, WIDE, errors)
    base = host.evaluate("parseFloat(getComputedStyle(document.documentElement).fontSize)")
    activate(host, "[data-testid=open-settings]")
    host.select_option("[data-testid=set-size]", "xlarge")
    assert host.evaluate("document.documentElement.style.getPropertyValue('--text-scale')") == "1.3"
    grown = host.evaluate("parseFloat(getComputedStyle(document.documentElement).fontSize)")
    assert round(grown / base, 2) == 1.3
    assert host.locator("[data-testid=set-keys]").inner_text().count("\n") >= 2
    host.check("[data-testid=set-motion]")
    assert host.evaluate("document.documentElement.dataset.motion") == "reduced"
    assert host.evaluate("window.matchMedia('(prefers-reduced-motion: reduce)').matches") is False
    host.evaluate(
        "window.aidm.dispatch({type: 'narration_chunk', id: 'n900', index: 0,"
        " text: 'The wind turns over the quay.', tone: 'exploration'})"
    )
    host.wait_for_function(
        "[...document.querySelectorAll('[data-id=n900] .sentence')]"
        ".some((s) => s.textContent.includes('quay'))",
        timeout=1000,  # reduced motion shows the sentence at once, no typewriter
    )
    assert errors == []


def test_device_reduced_motion_is_respected(browser: Browser, live_server: LiveServer) -> None:
    context = browser.new_context(viewport=WIDE, reduced_motion="reduce")
    page = context.new_page()
    page.goto(f"{live_server.base}/play")
    page.wait_for_selector("#join-name")
    assert page.evaluate("window.matchMedia('(prefers-reduced-motion: reduce)').matches")
    assert page.evaluate("getComputedStyle(document.body).transitionDuration") in ("0s", "1e-06s")
