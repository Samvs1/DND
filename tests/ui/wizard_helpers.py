"""Playwright helpers that drive the character wizard (shared by the wizard and table tests)."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Page

BODY = "[data-testid=wizard-body]"
NEXT = "[data-testid=wizard-next]"
ABILITY_ORDER = ["str", "dex", "con", "int", "wis", "cha"]


@dataclass(frozen=True)
class HeroSpec:
    name: str
    race: str = "human"
    cls: str = "fighter"
    background: str = "soldier"
    method: str = "point_buy"  # point_buy | standard_array | roll_4d6


def join(page: Page, base: str, name: str) -> None:
    page.goto(f"{base}/play")
    page.fill("#join-name", name)
    page.click("button[type=submit]")
    page.wait_for_selector("[data-testid=wizard]")
    page.wait_for_selector(f"{BODY} .wz-card")


def shot(page: Page, shots: Path, name: str, width: int) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_function("[...document.images].every((i) => i.complete)")
    page.wait_for_timeout(250)
    page.screenshot(path=str(shots / f"wizard_{name}_{width}.png"), full_page=True)


def _click_unselected(page: Page, scope: str, selector: str) -> bool:
    parts = [f"{scope} {part.strip()}:not([disabled])" for part in selector.split(",")]
    target = page.locator(", ".join(parts)).first
    if target.count() == 0:
        return False
    target.click()
    return True


def _fill_until_next(page: Page, scope: str, selector: str) -> None:
    for _ in range(60):
        if page.locator(NEXT).is_enabled():
            return
        if not _click_unselected(page, scope, selector):
            return


def _next(page: Page) -> None:
    page.wait_for_function("!document.querySelector('[data-testid=wizard-next]').disabled")
    page.click(NEXT)


def _race(page: Page, spec: HeroSpec, snap: Callable[[], None]) -> None:
    page.click(f"[data-key=race-{spec.race}]")
    _fill_until_next(
        page, f"{BODY} .wz-details", ".wz-card[aria-pressed=false], .wz-chip[aria-pressed=false]"
    )
    snap()
    _next(page)


def _class(page: Page, spec: HeroSpec, snap: Callable[[], None]) -> None:
    page.click(f"[data-key=class-{spec.cls}]")
    _fill_until_next(page, f"{BODY} .wz-details", ".wz-chip[aria-pressed=false]")
    snap()
    _next(page)


def _abilities(page: Page, spec: HeroSpec) -> None:
    page.click(f"[data-key=method-{spec.method}]")
    if spec.method == "point_buy":
        for _ in range(3):
            page.click("[data-key=plus-str]")
        page.click("[data-key=plus-con]")
        assert page.locator("[data-testid=points-left]").inner_text().startswith("Points left: 23")
    else:
        if spec.method == "roll_4d6":
            page.click("[data-testid=roll-abilities]")
            page.wait_for_selector("[data-testid=ability-roll]")
            assert page.locator("[data-testid=ability-roll]").count() == 6
            assert page.locator(".die.dropped").count() == 6
        for index, ability in enumerate(ABILITY_ORDER):
            page.select_option(f"[data-key=sel-{ability}]", index=index + 1)
    _next(page)


def _skills(page: Page) -> None:
    _fill_until_next(page, BODY, ".wz-chip:not(.locked)[aria-pressed=false]")
    _next(page)


def _equipment(page: Page) -> None:
    blocks = page.locator(f"{BODY} .wz-block")
    for index in range(blocks.count()):
        cards = blocks.nth(index).locator(".wz-card")
        if cards.count():
            cards.first.click()
    _next(page)


def _spells(page: Page) -> None:
    _fill_until_next(page, BODY, ".wz-card[aria-pressed=false]")
    _next(page)


def _snap(page: Page, shots: Path | None, spec: HeroSpec, width: int) -> None:
    """Screenshot the step that is currently shown (named by its stepper entry)."""
    if shots is None:
        return
    current = page.locator("[aria-current=step]").get_attribute("data-testid") or "step-x"
    shot(page, shots, f"{spec.cls}_{current.removeprefix('step-')}", width)


def fill_wizard(page: Page, spec: HeroSpec, shots: Path | None = None, width: int = 1280) -> None:
    """Fill every step up to the review step."""
    _race(page, spec, lambda: _snap(page, shots, spec, width))
    _class(page, spec, lambda: _snap(page, shots, spec, width))
    page.click(f"[data-key=bg-{spec.background}]")
    _snap(page, shots, spec, width)
    _next(page)
    _snap(page, shots, spec, width)
    _abilities(page, spec)
    _snap(page, shots, spec, width)
    _skills(page)
    _snap(page, shots, spec, width)
    _equipment(page)
    if page.locator("[data-testid=step-spells]").count():
        _snap(page, shots, spec, width)
        _spells(page)
    _snap(page, shots, spec, width)
    page.click("[data-key^=portrait-]")
    _next(page)
    page.fill("[data-testid=hero-name]", spec.name)
    page.fill("[data-testid=hero-pronouns]", "they/them")
    page.fill(
        "[data-testid=hero-backstory]", "Raised by lighthouse keepers, restless for the open road."
    )
    _snap(page, shots, spec, width)
    _next(page)
    _snap(page, shots, spec, width)


def complete_wizard(
    page: Page, spec: HeroSpec, shots: Path | None = None, width: int = 1280
) -> None:
    """Fill every step, create the hero and press ready (the page ends on the lobby)."""
    fill_wizard(page, spec, shots, width)
    page.click("[data-testid=create-hero]")
    page.wait_for_selector("[data-testid=sheet-summary]")
    if shots:
        shot(page, shots, f"{spec.cls}_sheet", width)
    page.click("[data-testid=hero-ready]")
    page.wait_for_selector("[data-testid=roster]")
