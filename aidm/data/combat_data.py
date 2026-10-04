"""The registries combat commands need, bundled for the rules (rules never load data, SPEC 5).

Public API:
- `CombatRegistries(chars, consumables, spells)`: frozen bundle of the character registries
  (classes, features, equipment, SRD spells), the consumable item effects and the spell effect
  DSL entries (`aidm.data.spell_defs`; a spell missing here cannot be cast).
- `combat_registries() -> CombatRegistries`: the default files, built once per process.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass

from aidm.data.character_data import CharacterRegistries, character_registries
from aidm.data.consumable_defs import ConsumableDef, consumable_defs
from aidm.data.registry import Registry
from aidm.data.spell_defs import SpellDef, spell_defs


@dataclass(frozen=True)
class CombatRegistries:
    chars: CharacterRegistries
    consumables: Registry[ConsumableDef]
    spells: Registry[SpellDef]


@functools.cache
def combat_registries() -> CombatRegistries:
    return CombatRegistries(
        chars=character_registries(), consumables=consumable_defs(), spells=spell_defs()
    )
