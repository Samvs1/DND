"""Spell coverage: every in-scope SRD spell is shipped as DSL data or listed as unsupported.

In scope (SPEC 7.4): cantrips and levels up to MAX_LEVEL on the wizard, cleric and warlock SRD
lists, plus ranger spells up to level 2 (rangers have 2nd-level slots at character level 5).
The unsupported list lives in docs/RULES_DECISIONS.md under "Unsupported spells (hidden from
pickers)", one `- <srd-index> (L<n>) | reason` line each.
"""

from __future__ import annotations

import re
from pathlib import Path

from aidm.data.spell_defs import spell_defs
from aidm.data.srd import srd

MAX_LEVEL = 1
RANGER_MAX_LEVEL = 2
FULL_CASTERS = {"wizard", "cleric", "warlock"}
DOC = Path(__file__).resolve().parents[3] / "docs" / "RULES_DECISIONS.md"
HEADER = "## Unsupported spells (hidden from pickers)"
LINE = re.compile(r"^- ([a-z0-9-]+) \(L(\d)\) \| (\S.*)$")


def _unsupported() -> dict[str, int]:
    text = DOC.read_text(encoding="utf-8")
    section = text.split(HEADER, 1)[1]
    found: dict[str, int] = {}
    for line in section.splitlines():
        match = LINE.match(line)
        if match:
            found[match.group(1)] = int(match.group(2))
    return found


def _in_scope() -> dict[str, int]:
    scope: dict[str, int] = {}
    for spell in srd().spells.all():
        classes = {c.index for c in spell.classes}
        if classes & FULL_CASTERS and spell.level <= MAX_LEVEL:
            scope[spell.index] = spell.level
        elif "ranger" in classes and spell.level <= min(MAX_LEVEL, RANGER_MAX_LEVEL):
            scope[spell.index] = spell.level
    return scope


def test_every_in_scope_spell_is_shipped_or_listed_unsupported() -> None:
    shipped = {s.index for s in spell_defs().all()}
    unsupported = set(_unsupported())
    scope = _in_scope()
    assert not (shipped & unsupported), sorted(shipped & unsupported)
    assert not set(scope) - shipped - unsupported, sorted(set(scope) - shipped - unsupported)


def test_unsupported_list_names_real_spells_at_their_level() -> None:
    for index, level in _unsupported().items():
        assert srd().spells.get(index).level == level, index
