"""The health word tips say the same cut-offs as the phone's healthState (M28.2)."""

import re
from pathlib import Path

from aidm.rules.explain import all_tips

MODEL = Path(__file__).resolve().parents[3] / "aidm" / "web" / "js" / "combat" / "model.js"
WORDS = {0.25: "A quarter", 0.5: "Half"}


def _const(name: str) -> float:
    match = re.search(rf"export const {name} = ([0-9.]+);", MODEL.read_text(encoding="utf-8"))
    assert match, name
    return float(match.group(1))


def _body(key: str) -> str:
    return all_tips()[key].text.split(". ", 1)[1]


def test_health_word_tips_match_the_phone_thresholds() -> None:
    assert _body("word:bloodied").startswith(WORDS[_const("BLOODIED_AT")])
    assert _body("word:wounded").startswith(WORDS[_const("WOUNDED_AT")])
