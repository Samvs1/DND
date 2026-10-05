"""Keyboard-only helpers: every interaction is Tab, typing, Enter, Space or Escape (no mouse)."""

from playwright.sync_api import Page

FOCUSED = "(css) => Boolean(document.activeElement && document.activeElement.matches(css))"
NEXT = "[data-testid=wizard-next]"
BODY = "[data-testid=wizard-body]"
DETAILS = f"{BODY} .wz-details"
PICKS = (
    f"{DETAILS} .wz-card[aria-pressed=false]:not([disabled]), "
    f"{DETAILS} .wz-chip[aria-pressed=false]:not([disabled])"
)
SKILLS = f"{BODY} .wz-chip:not(.locked)[aria-pressed=false]:not([disabled])"


def tab_to(page: Page, css: str, limit: int = 500) -> None:
    """Press Tab until the focused element matches `css`."""
    for _ in range(limit):
        if page.evaluate(FOCUSED, css):
            return
        page.keyboard.press("Tab")
    raise AssertionError(f"Tab never reached {css}")


def activate(page: Page, css: str, key: str = "Enter") -> None:
    tab_to(page, css)
    page.keyboard.press(key)


def type_into(page: Page, css: str, text: str) -> None:
    tab_to(page, css)
    page.keyboard.type(text)


def _next_enabled(page: Page) -> bool:
    return page.evaluate(f"!document.querySelector('{NEXT}').disabled")


def pick_until_next(page: Page, picks: str = PICKS) -> None:
    for _ in range(60):
        if _next_enabled(page):
            return
        if not page.evaluate("(css) => document.querySelectorAll(css).length > 0", picks):
            return
        activate(page, picks, "Space")


def next_step(page: Page) -> None:
    page.wait_for_function(f"!document.querySelector('{NEXT}').disabled")
    activate(page, NEXT)


def keyboard_wizard(page: Page, name: str) -> None:
    """A level 1 human fighter built with the keyboard alone, ending on the lobby (ready)."""
    activate(page, "[data-key=race-human]", "Space")
    pick_until_next(page)
    next_step(page)
    activate(page, "[data-key=class-fighter]", "Space")
    pick_until_next(page)
    next_step(page)
    activate(page, "[data-key=bg-soldier]", "Space")
    next_step(page)
    activate(page, "[data-key=method-point_buy]", "Space")
    next_step(page)
    pick_until_next(page, SKILLS)
    next_step(page)
    pick_until_next(page, f"{BODY} .wz-block .wz-card[aria-pressed=false]")  # equipment
    next_step(page)
    activate(page, "[data-key^=portrait-]", "Space")
    next_step(page)
    type_into(page, "[data-testid=hero-name]", name)
    type_into(page, "[data-testid=hero-pronouns]", "they/them")
    type_into(page, "[data-testid=hero-backstory]", "Raised by lighthouse keepers.")
    next_step(page)
    activate(page, "[data-testid=create-hero]")
    page.wait_for_selector("[data-testid=sheet-summary]")
    activate(page, "[data-testid=hero-ready]")
    page.wait_for_selector("[data-testid=roster]")
