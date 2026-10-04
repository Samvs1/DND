"""Load the vendored SRD JSON (data/srd) into typed, immutable registries.

Layering: `aidm.data` does all file I/O. `aidm.rules` receives entries or
registries as ARGUMENTS and must never call `load_srd` or `srd` itself.
Higher layers (dm, session, server) call `srd()` once and pass data down.
"""

from __future__ import annotations

import functools
import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from aidm.data.registry import Registry
from aidm.data.srd_characters import (
    SrdBackground,
    SrdClass,
    SrdCondition,
    SrdDamageType,
    SrdFeature,
    SrdLanguage,
    SrdLevel,
    SrdProficiency,
    SrdRace,
    SrdSkill,
    SrdSubclass,
    SrdSubrace,
    SrdTrait,
)
from aidm.data.srd_equipment import SrdEquipment
from aidm.data.srd_monsters import SrdMonster
from aidm.data.srd_spells import SrdSpell

DEFAULT_SRD_ROOT = Path(__file__).resolve().parents[2] / "data" / "srd"


@dataclass(frozen=True)
class SrdData:
    """One registry per SRD kind."""

    spells: Registry[SrdSpell]
    equipment: Registry[SrdEquipment]
    races: Registry[SrdRace]
    subraces: Registry[SrdSubrace]
    classes: Registry[SrdClass]
    levels: Registry[SrdLevel]
    subclasses: Registry[SrdSubclass]
    features: Registry[SrdFeature]
    traits: Registry[SrdTrait]
    conditions: Registry[SrdCondition]
    skills: Registry[SrdSkill]
    damage_types: Registry[SrdDamageType]
    proficiencies: Registry[SrdProficiency]
    backgrounds: Registry[SrdBackground]
    monsters: Registry[SrdMonster]
    languages: Registry[SrdLanguage]


def _load[M: BaseModel](path: Path, model: type[M]) -> list[M]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [model.model_validate(item) for item in raw]


def load_srd(root: Path | None = None) -> SrdData:
    """Read and validate every SRD file under `root` (default: repo data/srd)."""
    base = root if root is not None else DEFAULT_SRD_ROOT
    return SrdData(
        spells=Registry(_load(base / "spells.json", SrdSpell)),
        equipment=Registry(_load(base / "equipment.json", SrdEquipment)),
        races=Registry(_load(base / "races.json", SrdRace)),
        subraces=Registry(_load(base / "subraces.json", SrdSubrace)),
        classes=Registry(_load(base / "classes.json", SrdClass)),
        levels=Registry(_load(base / "levels.json", SrdLevel)),
        subclasses=Registry(_load(base / "subclasses.json", SrdSubclass)),
        features=Registry(_load(base / "features.json", SrdFeature)),
        traits=Registry(_load(base / "traits.json", SrdTrait)),
        conditions=Registry(_load(base / "conditions.json", SrdCondition)),
        skills=Registry(_load(base / "skills.json", SrdSkill)),
        damage_types=Registry(_load(base / "damage_types.json", SrdDamageType)),
        proficiencies=Registry(_load(base / "proficiencies.json", SrdProficiency)),
        backgrounds=Registry(_load(base / "backgrounds.json", SrdBackground)),
        monsters=Registry(_load(base / "monsters.json", SrdMonster)),
        languages=Registry(_load(base / "languages.json", SrdLanguage)),
    )


@functools.cache
def srd() -> SrdData:
    """The default-root SRD, loaded once per process."""
    return load_srd()
