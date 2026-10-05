"""The registries combat commands need, bundled for the rules (rules never load data, SPEC 5).

Public API:
- `CombatRegistries(chars, consumables, spells, monsters, monster_overlay)`: frozen bundle of the
  character registries (classes, features, equipment, SRD spells), the consumable item effects,
  the spell effect DSL entries (`aidm.data.spell_defs`; a spell missing here cannot be cast),
  the SRD monster stat blocks (a monster creature's actions are derived from its block) and the
  monster action overlay (`aidm.data.monster_overlay`).
- `combat_registries() -> CombatRegistries`: the default files, built once per process.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass

from aidm.data.character_data import CharacterRegistries, character_registries
from aidm.data.consumable_defs import ConsumableDef, consumable_defs
from aidm.data.monster_overlay import MonsterOverlay, monster_overlay
from aidm.data.registry import Registry
from aidm.data.spell_defs import SpellDef, spell_defs
from aidm.data.srd import srd
from aidm.data.srd_monsters import SrdMonster


@dataclass(frozen=True)
class CombatRegistries:
    chars: CharacterRegistries
    consumables: Registry[ConsumableDef]
    spells: Registry[SpellDef]
    monsters: Registry[SrdMonster]
    monster_overlay: MonsterOverlay


@functools.cache
def combat_registries() -> CombatRegistries:
    return CombatRegistries(
        chars=character_registries(),
        consumables=consumable_defs(),
        spells=spell_defs(),
        monsters=srd().monsters,
        monster_overlay=monster_overlay(),
    )
