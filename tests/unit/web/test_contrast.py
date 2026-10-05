"""WCAG contrast of the theme.css colour tokens (M8.4): body text >= 4.5, large text and UI >= 3."""

import re
from pathlib import Path

import pytest

THEME = Path(__file__).resolve().parent.parent.parent.parent / "aidm" / "web" / "css" / "theme.css"
BACKGROUNDS = ["ink-0", "stone-0", "stone-1", "stone-2", "stone-3"]
TEXT = ["parchment", "parchment-dim", "muted", "gold", "blood-text", "moss-text", "focus"]
UI = ["gold-dim", "blood", "moss", "sapphire", "amethyst", "focus"]
# Text drawn on a coloured fill: (foreground, fill).
ON_FILL = [
    ("on-accent", "gold"),
    ("on-accent", "amethyst"),
    ("on-blood", "blood"),
]
HEX = re.compile(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;")


def tokens() -> dict[str, str]:
    return dict(HEX.findall(THEME.read_text(encoding="utf-8")))


def luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_ratio_matches_known_wcag_values() -> None:
    assert ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert ratio("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)  # the classic AA edge


def test_every_token_the_tests_use_exists() -> None:
    found = tokens()
    names = {*BACKGROUNDS, *TEXT, *UI, *[n for pair in ON_FILL for n in pair]}
    assert sorted(names - found.keys()) == []


@pytest.mark.parametrize("fg", TEXT)
@pytest.mark.parametrize("bg", BACKGROUNDS)
def test_body_text_tokens_reach_4_5_on_every_surface(fg: str, bg: str) -> None:
    found = tokens()
    assert ratio(found[fg], found[bg]) >= 4.5, f"{fg} on {bg}"


@pytest.mark.parametrize("fg", UI)
@pytest.mark.parametrize("bg", BACKGROUNDS)
def test_ui_and_border_tokens_reach_3_on_every_surface(fg: str, bg: str) -> None:
    found = tokens()
    assert ratio(found[fg], found[bg]) >= 3.0, f"{fg} on {bg}"


@pytest.mark.parametrize(("fg", "fill"), ON_FILL)
def test_text_on_a_coloured_fill_reaches_4_5(fg: str, fill: str) -> None:
    found = tokens()
    assert ratio(found[fg], found[fill]) >= 4.5, f"{fg} on {fill}"
