"""M14.1: the player manual on the phone (More tab, 390 px) and as the /manual page (1920 px)."""

from pathlib import Path

from playwright.sync_api import Browser, ViewportSize

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import PHONE, go_tab, quiet_scribe, snap, start_table

TV = ViewportSize(width=1920, height=1080)
SECTIONS = "document.querySelectorAll('[data-testid=manual-body] section').length"
NO_SIDEWAYS = "document.documentElement.scrollWidth <= document.documentElement.clientWidth"


def test_more_tab_opens_the_manual_on_a_phone(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    quiet_scribe(host)
    go_tab(host, "more")
    host.click("[data-testid=open-manual]")
    host.wait_for_selector("[data-testid=manual-view] [data-testid=manual-toc-link]")
    assert host.evaluate(NO_SIDEWAYS)
    titles = host.locator("[data-testid=manual-toc-link]").all_inner_texts()
    for part in ("Getting started", "Your hero", "Combat", "The Scribe", "For the host"):
        assert any(part in title for title in titles), part
    # a generated table renders: the Scribe prices
    host.wait_for_selector("[data-testid=manual-body] table")
    assert host.locator("[data-testid=manual-body] td", has_text="125 gp").count() >= 1
    # search filters the sections
    before = host.locator("[data-testid=manual-body] section").count()
    host.fill("[data-testid=manual-search]", "death saves")
    host.wait_for_function(f"(n) => {SECTIONS} < n", arg=before)
    assert host.locator("[data-testid=manual-body]", has_text="death save").count() == 1
    host.fill("[data-testid=manual-search]", "zzzzqqqq")
    assert host.locator("[data-testid=manual-body] section").count() == 0
    host.fill("[data-testid=manual-search]", "")
    host.wait_for_function(f"(n) => {SECTIONS} === n", arg=before)
    host.fill("[data-testid=manual-search]", "Scribe")
    host.wait_for_selector("[data-testid=manual-body] table")
    snap(host, shots_dir, "manual", 390)
    assert errors == []


def test_manual_page_on_a_tv(browser: Browser, live_server: LiveServer, shots_dir: Path) -> None:
    errors: list[str] = []
    page = browser.new_context(viewport=TV).new_page()
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(f"{live_server.base}/manual")
    page.wait_for_selector("[data-testid=manual-view] [data-testid=manual-toc-link]")
    assert page.evaluate(NO_SIDEWAYS)
    assert page.locator("[data-testid=manual-toc-link]").count() >= 9
    page.fill("[data-testid=manual-search]", "point buy")
    page.wait_for_selector("[data-testid=manual-body] section")
    assert page.locator("[data-testid=manual-body]", has_text="27 points").count() == 1
    page.fill("[data-testid=manual-search]", "")
    page.click("[data-testid=manual-toc-link] >> text=The Scribe")
    snap(page, shots_dir, "manual", 1920)
    assert errors == []
