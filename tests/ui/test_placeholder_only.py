"""The game is fully playable on placeholders alone (Addendum A.5, A3).

The server runs from a temp copy of aidm/web with `static/img` (every real portrait and icon)
removed. Join, character creation, an action with narration and a fight with the hotbar must all
render with no broken image and no failed image request, using generated placeholder SVGs.
"""

import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, Response

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import HAS_TEXT, ROGUE, WIDE, snap
from tests.ui.wizard_helpers import HeroSpec, complete_wizard, fill_wizard, join

MAIN = "[data-testid=slot-attack-main_hand]"
WAIT = "[data-testid=hotbar-wait]"
IMAGES = """() => [...document.images].map((i) => ({
  src: i.currentSrc || i.src, ok: i.complete && i.naturalWidth > 0,
}))"""


class Probe:
    """Collects page errors and every failed or non-2xx image/static request of one context."""

    def __init__(self, context: BrowserContext, errors: list[str]) -> None:
        self.bad: list[str] = []
        self.placeholders = 0
        self._errors = errors
        context.on("response", self._on_response)
        context.on("requestfailed", lambda req: self._fail(req.url, req.resource_type))
        context.on("page", lambda page: page.on("pageerror", lambda e: errors.append(str(e))))

    def _fail(self, url: str, kind: str) -> None:
        if kind == "image" or "/static/img" in url:
            self.bad.append(url)

    def _on_response(self, response: Response) -> None:
        url = response.url
        if "/assets/placeholder/" in url and response.ok:
            self.placeholders += 1
        if (response.request.resource_type == "image" or "/static/img" in url) and not response.ok:
            self.bad.append(f"{response.status} {url}")


def _page(browser: Browser, errors: list[str]) -> tuple[Page, Probe]:
    context = browser.new_context(viewport=WIDE)
    probe = Probe(context, errors)
    page = context.new_page()
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    return page, probe


def _assert_no_broken_images(page: Page, label: str) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_function("[...document.images].every((i) => i.complete)", timeout=15000)
    images = page.evaluate(IMAGES)
    broken = [i["src"] for i in images if not i["ok"]]
    assert broken == [], f"{label}: broken images {broken}"
    real = [i["src"] for i in images if "/static/img" in i["src"]]
    assert real == [], f"{label}: real art leaked into the page {real}"


def test_art_is_really_hidden(artless_server: LiveServer) -> None:
    url = f"{artless_server.base}/static/img/portraits/Cleric_p_icon.png"
    try:
        urllib.request.urlopen(url)
    except urllib.error.HTTPError as err:
        assert err.code == 404
    else:
        raise AssertionError("real art is still served")


def test_join_create_act_and_fight_on_placeholders_only(
    browser: Browser, artless_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, host_probe = _page(browser, errors)
    guest, guest_probe = _page(browser, errors)
    join(host, artless_server.base, "Ann")
    _assert_no_broken_images(host, "wizard")
    snap(host, shots_dir, "placeholder_wizard", 1280)
    fill_wizard(host, HeroSpec(name="Brienne"))
    _assert_no_broken_images(host, "wizard review")
    snap(host, shots_dir, "placeholder_wizard_review", 1280)
    host.click("[data-testid=create-hero]")
    host.wait_for_selector("[data-testid=sheet-summary]")
    host.click("[data-testid=hero-ready]")
    host.wait_for_selector("[data-testid=roster]")
    join(guest, artless_server.base, "Bo")
    complete_wizard(guest, ROGUE)
    host.wait_for_function(
        "document.querySelectorAll('[data-testid=hero-state].ready').length === 2"
    )
    _assert_no_broken_images(host, "lobby")
    snap(host, shots_dir, "placeholder_lobby", 1280)
    host.click("[data-testid=start]")
    for page in (host, guest):
        page.wait_for_selector("[data-testid=feed]", timeout=20000)
        page.wait_for_function(HAS_TEXT, timeout=20000)
    _assert_no_broken_images(host, "table")
    snap(host, shots_dir, "placeholder_table", 1280)
    host.fill("[data-testid=action-input]", "I ambush the goblins from the shadows")
    host.click("[data-testid=action-send]")
    for page in (host, guest):
        page.wait_for_selector("[data-testid=board]:not([hidden])", timeout=30000)
        page.wait_for_selector(f"{MAIN}, {WAIT}", timeout=30000)
    for _ in range(150):  # the hotbar belongs to whoever has the turn (the rogue may pass first)
        if host.locator(MAIN).count() or guest.locator(MAIN).count():
            break
        host.wait_for_timeout(200)
    assert host.locator(MAIN).count() + guest.locator(MAIN).count() == 1
    for label, page in (("host combat", host), ("guest combat", guest)):
        _assert_no_broken_images(page, label)
    assert host.locator("[data-testid=token]").count() >= 4
    snap(host, shots_dir, "placeholder_combat", 1280)
    snap(guest, shots_dir, "placeholder_combat_guest", 1280)
    assert host_probe.bad + guest_probe.bad == []
    assert host_probe.placeholders > 0 and guest_probe.placeholders > 0
    assert errors == []
