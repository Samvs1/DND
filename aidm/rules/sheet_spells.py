"""The spellcasting part of the derived sheet: DC, attack, slots and spells grouped by level.

Spells shown: class cantrips, picked race cantrips, feature-granted spells (domain spells always
prepared, racial innate spells with their resource), and the class list for the caster kind:
known/pact casters their known spells, a wizard the whole spellbook (prepared flagged), a
cleric the prepared list. Levels with neither slots nor spells are omitted.

Public API: `spellcasting_block(creature, regs) -> SpellcastingBlock | None` (None for a
creature with no class casting and no granted spells).
"""

from aidm.data.character_data import CharacterRegistries
from aidm.data.feature_hooks import GrantedSpell
from aidm.data.spell_defs import spell_defs
from aidm.models.abilities import Ability
from aidm.models.character import PcData
from aidm.models.sheet import SlotLine, SpellcastingBlock, SpellLevelGroup, SpellLine
from aidm.models.state import Creature
from aidm.rules.abilities import ability_modifier
from aidm.rules.feature_build import granted_spells, innate_casting_ability
from aidm.rules.spellcasting import (
    SPELL_DC_BASE,
    SlotKind,
    prepared_spell_limit,
    slot_pools,
)


def _targeting(index: str, level: int) -> dict[str, object]:
    """How the hotbar targets a shipped spell (None of it for a spell the DSL does not ship)."""
    spell = spell_defs().find(index)
    if spell is None:
        return {}
    aim, count = spell.targeting, spell.targeting.count
    for floor, value in sorted(aim.count_by_character_level.items()):
        if floor <= level:
            count = value
    return {
        "casting_time": spell.casting_time,
        "target_kind": aim.kind,
        "target_count": count,
        "count_per_slot": aim.count_per_slot,
        "range_kind": spell.range.kind,
        "range_feet": spell.range.feet,
        "area_shape": aim.shape.kind if aim.shape is not None else None,
        "area_feet": aim.shape.feet if aim.shape is not None else None,
        "concentration": spell.concentration,
    }


def _line(regs: CharacterRegistries, index: str, level: int, **kw: object) -> SpellLine:
    spell = regs.spells.get(index)
    return SpellLine.model_validate(
        {"index": index, "name": spell.name, "level": spell.level, **_targeting(index, level), **kw}
    )


def _class_spells(pc: PcData, regs: CharacterRegistries) -> list[SpellLine]:
    casting = regs.classes.get(pc.class_index).spellcasting
    if casting is None:
        return []
    if casting.kind != "prepared":
        return [_line(regs, s, pc.level, prepared=True) for s in pc.spells_known]
    if casting.spellbook_start:
        return [_line(regs, s, pc.level, prepared=s in pc.prepared) for s in pc.spellbook]
    return [_line(regs, s, pc.level, prepared=True) for s in pc.prepared]


def _granted_lines(
    granted: list[GrantedSpell], regs: CharacterRegistries, level: int
) -> list[SpellLine]:
    lines: list[SpellLine] = []
    for grant in granted:
        if grant.mode == "expanded":
            continue
        always = grant.mode == "always_prepared"
        lines.append(
            _line(
                regs,
                grant.spell,
                level,
                prepared=True,
                always_prepared=always,
                source="feature",
                resource=grant.resource,
            )
        )
    return lines


def _all_spells(pc: PcData, regs: CharacterRegistries) -> list[SpellLine]:
    ids = [*pc.features, *pc.traits]
    granted = _granted_lines(
        granted_spells(ids, pc.level, pc.subclass, regs.features), regs, pc.level
    )
    lines = [
        *(_line(regs, s, pc.level, prepared=True) for s in pc.cantrips),
        *(_line(regs, s, pc.level, prepared=True, source="race") for s in pc.race_cantrips),
        *granted,
        *_class_spells(pc, regs),
    ]
    merged: dict[str, SpellLine] = {}
    for line in lines:
        if line.index not in merged or line.always_prepared:
            merged[line.index] = line
    return list(merged.values())


def _ability(pc: PcData, regs: CharacterRegistries) -> Ability | None:
    casting = regs.classes.get(pc.class_index).spellcasting
    if casting is not None:
        return Ability(casting.ability)
    return innate_casting_ability([*pc.features, *pc.traits], pc.level, regs.features)


def _groups(creature: Creature, spells: list[SpellLine]) -> list[SpellLevelGroup]:
    slots: dict[int, list[SlotLine]] = {}
    for ref, pool in slot_pools(creature):
        kind = "pact" if ref.kind is SlotKind.PACT else "standard"
        line = SlotLine(kind=kind, current=pool.current, maximum=pool.maximum)
        slots.setdefault(ref.level, []).append(line)
    levels = sorted(set(slots) | {s.level for s in spells if s.level > 0})
    return [
        SpellLevelGroup(
            level=level,
            slots=slots.get(level, []),
            spells=sorted((s for s in spells if s.level == level), key=lambda s: s.name),
        )
        for level in levels
    ]


def spellcasting_block(creature: Creature, regs: CharacterRegistries) -> SpellcastingBlock | None:
    pc = creature.pc
    if pc is None:
        return None
    spells = _all_spells(pc, regs)
    ability = _ability(pc, regs)
    if ability is None or (not spells and not slot_pools(creature)):
        return None
    mod = ability_modifier(creature.abilities[ability])
    limit = prepared_spell_limit(regs.classes.get(pc.class_index), pc.level, creature.abilities)
    return SpellcastingBlock(
        ability=ability,
        save_dc=SPELL_DC_BASE + creature.proficiency_bonus + mod,
        attack_bonus=creature.proficiency_bonus + mod,
        prepared_limit=limit or None,
        cantrips=sorted((s for s in spells if s.level == 0), key=lambda s: s.name),
        levels=_groups(creature, spells),
    )
