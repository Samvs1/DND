"""Browser tests of the character wizard (Playwright, FakeLLM server, M7.2)."""

from pathlib import Path

from playwright.sync_api import Browser, Page, ViewportSize

from tests.ui.conftest import LiveServer
from tests.ui.wizard_helpers import HeroSpec, complete_wizard, fill_wizard, join, shot

WIDE = ViewportSize(width=1280, height=900)
PHONE = ViewportSize(width=390, height=844)


def _new_page(browser: Browser, size: ViewportSize) -> tuple[Page, list[str]]:
    page = browser.new_context(viewport=size).new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    return page, errors


def _no_overflow(page: Page) -> bool:
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def _hero_state(page: Page) -> str:
    return page.locator("[data-testid=hero-state]").first.inner_text()


def test_fighter_point_buy_reaches_ready(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    page, errors = _new_page(browser, WIDE)
    join(page, live_server.base, "Ann")
    shot(page, shots_dir, "race", 1280)
    complete_wizard(page, HeroSpec(name="Brienne"), shots=shots_dir)
    assert "Brienne" in _hero_state(page)
    assert "Fighter" in _hero_state(page)
    assert page.locator("[data-testid=start]").is_enabled()
    assert errors == []


def test_wizard_caster_roll_path_reaches_ready(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    page, errors = _new_page(browser, WIDE)
    join(page, live_server.base, "Wyn")
    spec = HeroSpec(name="Elowen", race="elf", cls="wizard", background="sage", method="roll_4d6")
    complete_wizard(page, spec, shots=shots_dir)
    assert "Elowen" in _hero_state(page)
    assert "Wizard" in _hero_state(page)
    assert errors == []


def test_rogue_standard_array_with_expertise(browser: Browser, live_server: LiveServer) -> None:
    page, errors = _new_page(browser, WIDE)
    join(page, live_server.base, "Rae")
    spec = HeroSpec(
        name="Sable", race="half-elf", cls="rogue", background="criminal", method="standard_array"
    )
    complete_wizard(page, spec)
    assert "Sable" in _hero_state(page)
    assert errors == []


def test_phone_width_has_no_horizontal_overflow(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    page, errors = _new_page(browser, PHONE)
    join(page, live_server.base, "Pip")
    shot(page, shots_dir, "race", 390)
    assert _no_overflow(page)
    spec = HeroSpec(name="Tamsin", race="elf", cls="wizard", background="sage", method="roll_4d6")
    complete_wizard(page, spec, shots=shots_dir, width=390)
    assert "Tamsin" in _hero_state(page)
    assert _no_overflow(page)
    assert errors == []


def test_next_is_disabled_until_the_step_is_done(browser: Browser, live_server: LiveServer) -> None:
    page, _ = _new_page(browser, WIDE)
    join(page, live_server.base, "Cal")
    assert page.locator("[data-testid=wizard-next]").is_disabled()
    assert page.locator("[data-testid=wizard-hint]").inner_text() != ""
    page.click("[data-key=race-human]")
    assert page.locator("[data-testid=wizard-next]").is_disabled()
    page.click("[data-key^=lang-]")
    assert page.locator("[data-testid=wizard-next]").is_enabled()
    assert page.locator("[data-testid=step-abilities]").is_disabled()


def test_backstory_counter_and_limit(browser: Browser, live_server: LiveServer) -> None:
    page, _ = _new_page(browser, WIDE)
    join(page, live_server.base, "Dot")
    fill_wizard(page, HeroSpec(name="Dot"))
    page.click("[data-testid=step-identity]")
    page.fill("[data-testid=hero-backstory]", "x" * 500)
    assert page.locator("[data-testid=story-count]").inner_text() == "400 / 400"


def test_server_errors_are_mapped_to_friendly_text_per_step(
    browser: Browser, live_server: LiveServer
) -> None:
    page, _ = _new_page(browser, WIDE)
    join(page, live_server.base, "Eve")
    fill_wizard(page, HeroSpec(name="Eve"))
    page.evaluate(
        """() => window.aidm.store.emit('creation_result', {
            type: 'creation_result', ok: false, sheet: null, errors: [
              {code: 'point_buy_overspend', field: 'base_scores', detail: 'RAW-DETAIL'},
              {code: 'name_invalid', field: 'name', detail: 'RAW-DETAIL'}]})"""
    )
    box = page.locator("[data-testid=creation-errors]")
    box.wait_for()
    text = box.inner_text()
    assert "RAW-DETAIL" not in text and "point_buy" not in text
    assert "more than 27 points" in text and "1 to 40 characters" in text
    box.get_by_role("button", name="Abilities").click()
    assert page.locator("[data-testid=points-left]").is_visible()


def test_host_start_waits_until_everyone_has_a_hero(
    browser: Browser, live_server: LiveServer
) -> None:
    host, _ = _new_page(browser, WIDE)
    join(host, live_server.base, "Hosta")
    complete_wizard(host, HeroSpec(name="Aldric"))
    guest, _ = _new_page(browser, WIDE)
    join(guest, live_server.base, "Guesto")
    host.wait_for_function("document.querySelectorAll('[data-testid=roster] li').length >= 2")
    assert host.locator("[data-testid=start]").is_disabled()
    assert host.locator("[data-testid=wait-heroes]").is_visible()
    complete_wizard(guest, HeroSpec(name="Mira", race="elf", cls="rogue", background="criminal"))
    host.wait_for_function(
        "document.querySelectorAll('[data-testid=hero-state].ready').length === 2"
    )
    assert host.locator("[data-testid=start]").is_enabled()
    assert host.locator("[data-testid=wait-heroes]").is_hidden()
