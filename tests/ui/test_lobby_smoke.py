"""Browser smoke test of the lobby (Playwright chromium, FakeLLM server, M7.1)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

from tests.asset_helpers import image_placeholder, live_manifest
from tests.ui.conftest import LiveServer


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as pw:
        chromium = pw.chromium.launch()
        yield chromium
        chromium.close()


def _join(page: Page, base: str, name: str) -> None:
    page.goto(f"{base}/play")
    page.fill("#join-name", name)
    page.click("button[type=submit]")
    page.click("[data-testid=wizard-close]")
    page.wait_for_selector("[data-testid=roster] li[data-player]")


def test_lobby_join_roster_qr_and_screenshot(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    _join(page, live_server.base, "Ann")
    assert page.locator("[data-testid=roster]").inner_text().startswith("Ann")
    assert page.locator("[data-testid=start]").is_visible()
    assert page.locator("[data-testid=lan-url]").inner_text().startswith("http://192.168.1.20")
    page.wait_for_function("document.querySelector('img.qr').naturalWidth > 0")
    page.screenshot(path=str(shots_dir / "lobby.png"))
    narrow = browser.new_page(viewport={"width": 390, "height": 800})
    _join(narrow, live_server.base, "Bea")
    narrow.screenshot(path=str(shots_dir / "lobby_390.png"))
    overflow = narrow.evaluate("document.documentElement.scrollWidth > window.innerWidth")
    assert overflow is False
    assert errors == []


def test_second_player_sees_roster_and_no_start_button(
    browser: Browser, live_server: LiveServer
) -> None:
    host = browser.new_page()
    _join(host, live_server.base, "Host")
    guest = browser.new_page()
    _join(guest, live_server.base, "Guest")
    guest.wait_for_function("document.querySelectorAll('[data-testid=roster] li').length >= 2")
    assert guest.locator("[data-testid=start]").is_hidden()
    assert guest.locator("[data-testid=wait]").is_visible()


def test_start_is_disabled_without_a_hero_and_server_refusal_is_friendly(
    browser: Browser, live_server: LiveServer
) -> None:
    page = browser.new_page()
    _join(page, live_server.base, "Solo")
    assert page.locator("[data-testid=start]").is_disabled()
    assert page.locator("[data-testid=wait-heroes]").is_visible()
    page.evaluate("window.aidm.client.send('host_start', {theme: null})")
    banner = page.locator("[data-testid=banner]")
    banner.wait_for(timeout=5000)
    text = banner.inner_text()
    assert "Traceback" not in text and "no_character" not in text


def test_assets_helper_resolves_real_placeholder_and_silence(
    browser: Browser, live_server: LiveServer
) -> None:
    manifest = live_manifest()
    key = image_placeholder(manifest)
    page = browser.new_page()
    page.goto(f"{live_server.base}/play")
    page.wait_for_selector("[data-testid=join-form]")
    result = page.evaluate(
        """async (key) => {
            const a = await import('/web/js/assets.js');
            const placeholder = a.assetUrl(key);
            const probe = new Image();
            probe.src = placeholder;
            await probe.decode();
            return {
                real: a.assetUrl('portrait.class.fighter'),
                placeholder,
                width: probe.naturalWidth,
                silence: a.assetUrl('music.social'),
                fallback: a.assetUrl([key, 'spell_icon.school.fire']),
            };
        }""",
        key,
    )
    assert result["real"].startswith("/static/")
    assert result["placeholder"].startswith(f"/assets/placeholder/{manifest[key]['kind']}/")
    assert result["width"] > 0
    assert result["silence"] == ""
    assert result["fallback"] == "/static/" + manifest["spell_icon.school.fire"]["file"]
