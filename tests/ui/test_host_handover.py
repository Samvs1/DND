"""M17.1: the host role follows the table, and a page from an earlier server run joins again.

Owner request: "I want the host to be the one who connects first". An old page with a saved token
used to take a seat (and the host role) by itself after a server restart.
"""

from playwright.sync_api import Browser, Page

from tests.ui.conftest import LiveServer

HOST_FORM = "form.host-controls"


def _join(page: Page, base: str, name: str) -> None:
    page.goto(f"{base}/play")
    page.fill("#join-name", name)
    page.click("button[type=submit]")
    page.click("[data-testid=wizard-close]")
    page.wait_for_selector("[data-testid=roster] li[data-player]")


def test_host_leaves_the_lobby_and_the_next_player_becomes_host(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    first = browser.new_context()
    ann = first.new_page()
    ann.on("pageerror", lambda exc: errors.append(str(exc)))
    _join(ann, live_server.base, "Ann")
    assert ann.locator(HOST_FORM).is_visible()
    bo = browser.new_page()
    bo.on("pageerror", lambda exc: errors.append(str(exc)))
    _join(bo, live_server.base, "Bo")
    assert not bo.locator(HOST_FORM).is_visible()
    first.close()  # the host's page goes away while still in the lobby
    bo.locator(HOST_FORM).wait_for(state="visible", timeout=5000)
    host_row = bo.locator("[data-testid=roster] li[data-player]", has=bo.locator(".tag-host"))
    assert "Bo" in host_row.inner_text()
    assert errors == []


def test_a_page_from_an_earlier_server_run_shows_the_join_form(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    page = browser.new_page()
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(f"{live_server.base}/play")
    page.wait_for_selector("[data-testid=join-form]")
    page.evaluate(
        "() => { localStorage.setItem('aidm.token', 'from-an-earlier-run');"
        " localStorage.setItem('aidm.name', 'Slender'); }"
    )
    page.reload()  # the page auto-joins with the stale token, as after a server restart
    page.locator("[data-testid=join-note]").wait_for(state="visible", timeout=5000)
    assert page.locator("[data-testid=join-form]").is_visible()
    assert page.input_value("#join-name") == "Slender"
    assert page.evaluate("() => localStorage.getItem('aidm.token')") is None
    page.click("button[type=submit]")  # joining again seats a fresh player: the first, so host
    page.click("[data-testid=wizard-close]")
    page.wait_for_selector("[data-testid=roster] li[data-player]")
    assert page.locator(HOST_FORM).is_visible()
    assert page.locator("[data-testid=roster] li[data-player]").count() == 1
    assert errors == []
