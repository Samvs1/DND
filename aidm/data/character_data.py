"""The registries character creation, spellcasting and level-up need, bundled for the rules.

Rules never load data (SPEC 5): the session or a test builds one `CharacterRegistries` and passes
it to `aidm.rules.creation` and friends as an argument.

Public API:
- `CharacterRegistries(classes, races, backgrounds, equipment, spells, languages)`: frozen bundle
  of the M2.1 overlays (data/bg3) and the SRD registries they reference (data/srd).
- `character_registries() -> CharacterRegistries`: the default files, built once per process.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass

from aidm.data.background_defs import BackgroundDef, background_defs
from aidm.data.class_defs import ClassDef, class_defs
from aidm.data.race_defs import RaceDef, race_defs
from aidm.data.registry import Registry
from aidm.data.srd import srd
from aidm.data.srd_characters import SrdLanguage
from aidm.data.srd_equipment import SrdEquipment
from aidm.data.srd_spells import SrdSpell


@dataclass(frozen=True)
class CharacterRegistries:
    classes: Registry[ClassDef]
    races: Registry[RaceDef]
    backgrounds: Registry[BackgroundDef]
    equipment: Registry[SrdEquipment]
    spells: Registry[SrdSpell]
    languages: Registry[SrdLanguage]


@functools.cache
def character_registries() -> CharacterRegistries:
    data = srd()
    return CharacterRegistries(
        classes=class_defs(),
        races=race_defs(),
        backgrounds=background_defs(),
        equipment=data.equipment,
        spells=data.spells,
        languages=data.languages,
    )
