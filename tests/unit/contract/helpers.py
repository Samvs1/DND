"""Run contract rules on a real fixture save (M43.1)."""

from functools import cache
from pathlib import Path

from scripts.contractlib.save import Finding, Save, Visitor, load_save, walk

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "saves"


@cache
def fixture(name: str) -> Save:
    return load_save(FIXTURES / name)


def run(save: Save, *visitors: Visitor) -> list[Finding]:
    return walk(save, list(visitors))[1]


def rules(found: list[Finding], rule: str) -> list[Finding]:
    return [f for f in found if f.rule == rule]
