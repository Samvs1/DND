"""Shared Playwright helpers for table-level UI tests: a /screen plus phone controllers."""

from pathlib import Path

from playwright.sync_api import Browser, Locator, Page, ViewportSize

from tests.ui.conftest import open_screen
from tests.ui.wizard_helpers import HeroSpec, complete_wizard, join

WIDE = ViewportSize(width=1280, height=800)
PHONE = ViewportSize(width=390, height=844)
HD = ViewportSize(width=1920, height=1080)
ROGUE = HeroSpec(name="Mira", race="elf", cls="rogue", background="criminal")
PHONE_TEXT = "document.querySelector('[data-testid=last-line]').textContent.trim().length > 20"
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
    """Two phone controllers (host Ann, guest Bo) with heroes, started; both show the first line."""
    host = player(browser, base, "Ann", specs[0], size, errors)
    guest = player(browser, base, "Bo", specs[1], size, errors)
    ready = "document.querySelectorAll('[data-testid=hero-state].ready').length === 2"
    host.wait_for_function(ready)
    host.click("[data-testid=start]")
    for page in (host, guest):
        page.wait_for_selector("[data-testid=controller]", timeout=20000)
        page.wait_for_function(PHONE_TEXT, timeout=20000)
    return host, guest


def start_with_screen(
    browser: Browser,
    base: str,
    errors: list[str],
    size: ViewportSize = PHONE,
    screen_size: ViewportSize = WIDE,
    specs: tuple[HeroSpec, HeroSpec] = (HeroSpec(name="Brienne"), ROGUE),
) -> tuple[Page, Page, Page]:
    """(screen, host phone, guest phone) against the same server; the screen shows the opening."""
    screen = open_screen(browser, base, errors, screen_size)
    host, guest = start_table(browser, base, size, errors, specs)
    screen.wait_for_selector("[data-testid=screen-table]:not([hidden])", timeout=20000)
    screen.wait_for_function(HAS_TEXT, timeout=20000)
    return screen, host, guest


MAIN = "[data-testid=slot-attack-main_hand]"
WAIT = "[data-testid=hotbar-wait]"
BOARD = "[data-testid=board]:not([hidden])"
AMBUSH = "I ambush the goblins from the shadows"
COMBAT_POS = (
    "(() => { const c = window.aidm.store.get().snapshot.state.combat;"
    " return c ? [c.round, c.active_id] : null; })()"
)


def start_fight(
    browser: Browser,
    base: str,
    errors: list[str],
    size: ViewportSize = PHONE,
    screen_size: ViewportSize = WIDE,
) -> tuple[Page, Page, Page]:
    """(screen, host phone, guest phone) in a fight: board on the screen, hotbar on a phone."""
    screen, host, guest = start_with_screen(browser, base, errors, size, screen_size)
    host.fill("[data-testid=action-input]", AMBUSH)
    host.click("[data-testid=action-send]")
    screen.wait_for_selector(BOARD, timeout=30000)
    for page in (host, guest):
        page.wait_for_selector(f"{MAIN}, {WAIT}", timeout=30000)
    return screen, host, guest


def split_turn(host: Page, guest: Page) -> tuple[Page, Page]:
    """(active phone, other phone); waits until one of them has the attack hotbar."""
    for _ in range(150):
        if host.locator(MAIN).count():
            return host, guest
        if guest.locator(MAIN).count():
            return guest, host
        host.wait_for_timeout(200)
    raise AssertionError("nobody got the hotbar")


def has_hit_chance(page: Page) -> Locator:
    """Wait for the previews; return an attack slot that shows a percentage (in range)."""
    page.wait_for_function(
        "[...document.querySelectorAll('[data-testid^=slot-attack-] [data-testid=slot-sub]')]"
        ".some((n) => n.textContent.includes('%'))",
        timeout=20000,
    )
    return page.locator("[data-testid^=slot-attack-]", has_text="%").first


def go_tab(page: Page, name: str) -> None:
    """Open a tab of the phone controller (play, hero, journal, more)."""
    page.click(f"[data-testid=ct-tab-{name}]")
    page.wait_for_selector(f"[data-testid=pane-{name}]:not([hidden])")


def snap(page: Page, shots: Path, name: str, width: int) -> None:
    """Wait for images and motion to settle, then save artifacts/ui/<name>_<width>.png."""
    page.wait_for_load_state("networkidle")
    page.wait_for_function("[...document.images].every((i) => i.complete)")
    page.wait_for_timeout(700)
    page.screenshot(path=str(shots / f"{name}_{width}.png"))
