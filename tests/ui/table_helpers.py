"""Shared Playwright helpers for table-level UI tests: two players join, create heroes, start."""

from pathlib import Path

from playwright.sync_api import Browser, Page, ViewportSize

from tests.ui.wizard_helpers import HeroSpec, complete_wizard, join

WIDE = ViewportSize(width=1280, height=800)
PHONE = ViewportSize(width=390, height=844)
ROGUE = HeroSpec(name="Mira", race="elf", cls="rogue", background="criminal")
HAS_TEXT = (
    "[...document.querySelectorAll('[data-testid=narration]')]"
    ".some(n => n.textContent.trim().length > 20)"
)


def player(
    browser: Browser, base: str, name: str, spec: HeroSpec, size: ViewportSize, errors: list[str]
) -> Page:
    context = browser.new_context(viewport=size)
    page = context.new_page()
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    join(page, base, name)
    complete_wizard(page, spec)
    return page


def start_table(
    browser: Browser,
    base: str,
    size: ViewportSize,
    errors: list[str],
    specs: tuple[HeroSpec, HeroSpec] = (HeroSpec(name="Brienne"), ROGUE),
) -> tuple[Page, Page]:
    host = player(browser, base, "Ann", specs[0], size, errors)
    guest = player(browser, base, "Bo", specs[1], size, errors)
    ready = "document.querySelectorAll('[data-testid=hero-state].ready').length === 2"
    host.wait_for_function(ready)
    host.click("[data-testid=start]")
    for page in (host, guest):
        page.wait_for_selector("[data-testid=feed]", timeout=20000)
        page.wait_for_function(HAS_TEXT, timeout=20000)
    return host, guest


def snap(page: Page, shots: Path, name: str, width: int) -> None:
    """Wait for images and motion to settle, then save artifacts/ui/<name>_<width>.png."""
    page.wait_for_load_state("networkidle")
    page.wait_for_function("[...document.images].every((i) => i.complete)")
    page.wait_for_timeout(700)
    page.screenshot(path=str(shots / f"{name}_{width}.png"))
