"""The derived character sheet (SPEC 8): one pure function from a PC to `CharacterSheet`.

Every number is computed by the rules that own it (checks, weapon attacks, spellcasting, feature
hooks); this module only assembles them. Initiative shows the +DEX bonus (BG3 rolls 1d4 + DEX).

Public API: `build_sheet(creature, regs) -> CharacterSheet` (ValueError for a non-PC).
"""

from aidm.data.character_data import CharacterRegistries
from aidm.models.abilities import ABILITIES, SKILL_ABILITY, Ability, Skill
from aidm.models.character import PcData
from aidm.models.sheet import (
    AbilityLine,
    CharacterSheet,
    ConditionLine,
    DeathSaveLine,
    FeatureLine,
    InventoryLine,
    ResourceLine,
    SkillLine,
)
from aidm.models.state import Creature
from aidm.rules.abilities import ability_modifier
from aidm.rules.checks import passive_score, save_bonus, skill_bonus
from aidm.rules.features import attacks_per_action
from aidm.rules.leveling import MAX_LEVEL, xp_for_level
from aidm.rules.sheet_spells import spellcasting_block
from aidm.rules.spellcasting import parse_slot_key
from aidm.rules.weapon_attacks import attack_lines


def _abilities(creature: Creature) -> list[AbilityLine]:
    return [
        AbilityLine(
            ability=a,
            score=creature.abilities[a],
            modifier=ability_modifier(creature.abilities[a]),
            save_bonus=save_bonus(creature, a),
            save_proficient=a in creature.save_proficiencies,
        )
        for a in ABILITIES
    ]


def _skills(creature: Creature) -> list[SkillLine]:
    return [
        SkillLine(
            skill=s,
            ability=SKILL_ABILITY[s],
            bonus=skill_bonus(creature, s),
            proficient=s in creature.skill_proficiencies or s in creature.skill_expertise,
            expertise=s in creature.skill_expertise,
        )
        for s in Skill
    ]


def _features(pc: PcData, regs: CharacterRegistries) -> list[FeatureLine]:
    lines: list[FeatureLine] = []
    for ids, source in ((pc.features, "class"), (pc.traits, "race")):
        for index in ids:
            entry = regs.features.get(index)
            lines.append(
                FeatureLine.model_validate(
                    {"index": index, "name": entry.name, "summary": entry.summary, "source": source}
                )
            )
    return lines


def _resources(creature: Creature) -> list[ResourceLine]:
    return [
        ResourceLine(key=key, current=r.current, maximum=r.maximum, recharge=r.recharge.value)
        for key, r in sorted(creature.resources.items())
        if parse_slot_key(key) is None
    ]


def _inventory(pc: PcData, regs: CharacterRegistries) -> list[InventoryLine]:
    worn = {
        slot: index for slot, index in pc.equipped.model_dump().items() if isinstance(index, str)
    }
    lines: list[InventoryLine] = []
    for row in pc.inventory:
        entry = regs.equipment.find(row.item)
        slot = next((s for s, index in worn.items() if index == row.item), None)
        name = entry.name if entry is not None else row.item
        lines.append(InventoryLine(item=row.item, name=name, qty=row.qty, equipped_slot=slot))
    return lines


def build_sheet(creature: Creature, regs: CharacterRegistries) -> CharacterSheet:
    pc = creature.pc
    if pc is None:
        raise ValueError(f"{creature.id!r} has no character sheet")
    return CharacterSheet(
        id=creature.id,
        name=creature.name,
        race=pc.race,
        subrace=pc.subrace,
        class_index=pc.class_index,
        subclass=pc.subclass,
        level=pc.level,
        background=pc.background,
        xp=pc.xp,
        xp_next=xp_for_level(pc.level + 1) if pc.level < MAX_LEVEL else None,
        abilities=_abilities(creature),
        skills=_skills(creature),
        passive_perception=passive_score(creature, Skill.PERCEPTION),
        proficiency_bonus=creature.proficiency_bonus,
        ac=creature.ac,
        hp=creature.hp,
        temp_hp=creature.temp_hp,
        max_hp=creature.max_hp,
        speed=creature.speed,
        initiative_bonus=ability_modifier(creature.abilities[Ability.DEX]),
        attacks=attack_lines(creature, regs),
        attacks_per_action=attacks_per_action(creature, regs.features),
        spellcasting=spellcasting_block(creature, regs),
        features=_features(pc, regs),
        resources=_resources(creature),
        armor_proficiencies=list(pc.armor_proficiencies),
        weapon_proficiencies=list(pc.weapon_proficiencies),
        tool_proficiencies=list(pc.tool_proficiencies),
        languages=list(pc.languages),
        resistances=list(creature.resistances),
        inventory=_inventory(pc, regs),
        gold=pc.gold,
        conditions=[
            ConditionLine(name=c.name, rounds_left=c.rounds_left) for c in creature.conditions
        ],
        death_saves=DeathSaveLine(
            successes=creature.death_save_successes,
            failures=creature.death_save_failures,
            stable=creature.stable,
            dead=creature.dead,
        ),
    )
