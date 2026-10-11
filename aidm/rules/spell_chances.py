"""Attack-roll spells as hit-chance options (M20.4, owner playtest 3: the phone said "Out of range"
on a foe the warlock's Eldritch Blast could reach, because only weapons were previewed).

`spell_attack_options(creature, chars, spells)` lists one `AttackProfile` per spell with an
attack roll the hero can cast right now: a ready cantrip, or a ready leveled spell with a slot of
its level or higher left. The key is `spell:<index>`; the profile is the one the cast uses
(`spell_context.spell_profile`).

Public API: `SPELL_OPTION_PREFIX`, `spell_attack_options(creature, chars, spells)`.
"""

from collections.abc import Iterable

from aidm.data.character_data import CharacterRegistries
from aidm.data.registry import Registry
from aidm.data.spell_defs import AttackRollEffect, Effect, MultiTargetEffect, SpellDef
from aidm.models.combat import AttackProfile
from aidm.models.sheet import SpellcastingBlock, SpellLine
from aidm.models.state import Creature
from aidm.rules.sheet_spells import spellcasting_block
from aidm.rules.spell_context import spell_profile

SPELL_OPTION_PREFIX = "spell:"


def _rolls_to_hit(effects: Iterable[Effect]) -> bool:
    for effect in effects:
        if isinstance(effect, AttackRollEffect):
            return True
        if isinstance(effect, MultiTargetEffect) and _rolls_to_hit(effect.effects):
            return True
    return False


def _ready(block: SpellcastingBlock) -> list[SpellLine]:
    open_levels = [g.level for g in block.levels if any(s.current > 0 for s in g.slots)]
    top = max(open_levels, default=0)
    leveled = [s for g in block.levels for s in g.spells if s.level <= top]
    return [s for s in (*block.cantrips, *leveled) if s.prepared]


def spell_attack_options(
    creature: Creature, chars: CharacterRegistries, spells: Registry[SpellDef]
) -> list[AttackProfile]:
    block = spellcasting_block(creature, chars)
    if block is None:
        return []
    out: list[AttackProfile] = []
    for line in _ready(block):
        spell = spells.find(line.index)
        if spell is not None and _rolls_to_hit(spell.effects):
            key = f"{SPELL_OPTION_PREFIX}{spell.index}"
            out.append(spell_profile(spell, line.name, block.attack_bonus, key))
    return out
