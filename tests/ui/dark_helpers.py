"""Shared bits of the M27.8 UI tests: a dark place, a bearer and a darkvision hero in the store."""

from pathlib import Path

from playwright.sync_api import Page

from tests.ui.conftest import SHOTS

OUT = SHOTS / "m27_8"

# cfg: {light: bool, boons: [...], gear: bool}. The hero's token moves to a zone without foes
# (when the map has one) so the lit zone differs from the foes' zones; darkvision stays as the
# server sent it (from race data).
DARKEN = (Path(__file__).parent / "js" / "darken.js").read_text(encoding="utf-8")


def darken(
    page: Page,
    light: bool = False,
    boons: tuple[str, ...] = (),
    gear: bool = True,
    me: str | None = None,
    features: list[dict[str, str]] | None = None,
) -> str:
    cfg = {"light": light, "boons": list(boons), "gear": gear, "me": me, "features": features}
    return page.evaluate(DARKEN, cfg)


def shot(page: Page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.wait_for_function("[...document.images].every((i) => i.complete)")
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / f"{name}.png"))
