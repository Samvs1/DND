"""The danger word of a world-pulled fight (M29.6b area blasts, M29.7d round damage and cover).

The word shown on the warning card is the highest of: the SRD XP rating, each foe's area-blast
rating (`rules.encounter_danger.area_rating`), each foe's round-damage rating
(`rules.encounter_threat.round_rating`), then raised by `EncounterTables.cover_rating_step` when a
foe that shoots fights from a zone with that cover. It only labels: which monsters a spoke picks
is still the XP budget's call (docs/DECISIONS.md M29.7d).

Public API:
- `LabelContext(tables, overlay, spells, hero_hp, hero_ac, cover)`.
- `heroes_ac(state) -> int`: the living heroes' average AC (rounded; 10 with none).
- `danger_label(rated, foes, ctx, extra_attacks=()) -> Difficulty | None`: M31.1d
  `extra_attacks[i]` is how many more single attacks a round foe i makes on average (a master's
  turn).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from aidm.data.encounter_tables import EncounterTables
from aidm.data.monster_overlay import MonsterOverlay
from aidm.data.registry import Registry
from aidm.data.spell_defs import SpellDef
from aidm.data.srd_monsters import SrdMonster
from aidm.models.encounter import Difficulty
from aidm.models.state import GameState
from aidm.models.zones import CoverLevel
from aidm.rules.encounter_danger import area_rating, harder
from aidm.rules.encounter_threat import (
    attack_damage,
    round_damage,
    round_rating,
    shoots,
    stepped,
)
from aidm.rules.monster_catalog import monster_catalog


@dataclass(frozen=True)
class LabelContext:
    tables: EncounterTables
    overlay: MonsterOverlay
    spells: Registry[SpellDef] | None
    hero_hp: float
    hero_ac: int
    cover: CoverLevel = CoverLevel.NONE


def heroes_ac(state: GameState) -> int:
    acs = [c.ac for c in state.creatures.values() if c.pc is not None and not c.dead]
    return round(sum(acs) / len(acs)) if acs else 10


def danger_label(
    rated: Difficulty | None,
    foes: Sequence[SrdMonster],
    ctx: LabelContext,
    extra_attacks: Sequence[float] = (),
) -> Difficulty | None:
    shooter = False
    shipped = ctx.spells if ctx.spells is not None else ()
    for i, foe in enumerate(foes):
        catalog = monster_catalog(foe, ctx.overlay, shipped)
        rated = harder(rated, area_rating(foe, ctx.hero_hp, ctx.tables))
        damage = round_damage(catalog, ctx.spells, ctx.hero_ac)
        if i < len(extra_attacks) and extra_attacks[i] > 0:
            damage += extra_attacks[i] * attack_damage(catalog, ctx.hero_ac)
        rated = harder(rated, round_rating(damage, ctx.hero_hp, ctx.tables))
        shooter = shooter or shoots(catalog, ctx.spells)
    steps = ctx.tables.cover_rating_step.get(ctx.cover.value, 0) if shooter else 0
    return stepped(rated, steps)
