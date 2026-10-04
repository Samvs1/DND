"""Character creation: validate a `CreationChoices` and build a level-1 PC (SPEC 8, 7.5).

The data (class, race, background overlays and the SRD registries) arrives as a
`CharacterRegistries` argument; nothing here loads files.

Public API:
- `CREATION_LEVEL` (1).
- `validate_creation(choices, regs) -> list[CreationError]`: every problem, typed; [] = valid.
  Unknown race/subrace/class/background stops the checks there (the rest depends on them).
- `spell_pick_errors(choices, refs, regs) -> list[CreationError]`: cantrips (class count from
  the level-1 row, SRD class list), racial cantrips (`cantrip_choices` from `cantrip_class`),
  spells (known/pact: `spells_known`; a spellbook caster: `spellbook_start`; others none) and
  prepared spells (prepared casters only, from the spellbook or the class list; at most
  `aidm.rules.spellcasting.prepared_spell_limit` with the final scores, PREPARED_OVER_LIMIT).
- `CreationInvalid(ValueError)`: `build_character` was handed choices that do not validate;
  `.errors` lists why (callers must validate first, so this is an engine bug).
- `auto_equip(inventory, equipment, abilities) -> Equipped`: best-AC body armor, a shield, a
  melee main hand (one-handed when a shield is worn), a light off-hand when both hands hold light
  weapons and there is no shield, and the first ranged weapon.
- `build_character(choices, regs, creature_id) -> Creature`: the level-1 PC (kind PC, `pc` set):
  abilities with racial bonuses, HP (hit die max + CON), proficiency bonus, saves, skills,
  speed, size, darkvision, languages, proficiencies, inventory (class fixed + picked packages +
  background gear), equipment and AC (via `aidm.rules.defense`), level-1 features, the subclass
  when its level is 1, race traits, the spell picks and full spell-slot pools
  (`aidm.rules.spellcasting.slot_resources`). Feature hooks (`aidm.rules.feature_build`) add
  picked options (`feature_choices`, validated with the rest), expertise, resistances, HP per
  level, speed, darkvision, proficiencies, feature resources and the Defense AC bonus; a
  patron's expanded spells are learnable.
"""

from collections.abc import Mapping, Sequence

from aidm.data.character_data import CharacterRegistries
from aidm.data.registry import Registry
from aidm.data.srd_equipment import SrdEquipment
from aidm.models.abilities import Ability, Skill
from aidm.models.character import Equipped, InventoryItem, PcData, Size
from aidm.models.creation import CreationChoices, CreationError, CreationErrorCode
from aidm.models.state import Creature, CreatureKind
from aidm.rules.abilities import ability_modifier, proficiency_bonus
from aidm.rules.ability_gen import ability_score_errors, apply_bonuses, racial_bonuses
from aidm.rules.creation_checks import (
    CreationRefs,
    class_choice_errors,
    class_spell_indexes,
    equipment_errors,
    granted_languages,
    granted_skills,
    granted_tools,
    pick_errors,
    resolve_refs,
    skill_tool_language_errors,
    text_errors,
)
from aidm.rules.defense import SHIELD_CATEGORY, armor_class
from aidm.rules.feature_build import (
    expanded_spell_indexes,
    expertise_picks,
    feature_choice_errors,
    feature_effects,
    feature_resources,
    with_picks,
)
from aidm.rules.features import feature_ac_bonus
from aidm.rules.hp import max_hp_at_level
from aidm.rules.spellcasting import (
    cantrips_known_count,
    max_spell_level,
    prepared_spell_limit,
    slot_resources,
    spells_known_count,
)

CREATION_LEVEL = 1
_MELEE = "Melee"
_RANGED = "Ranged"


class CreationInvalid(ValueError):
    """Choices that fail `validate_creation` were passed to `build_character`."""

    def __init__(self, errors: list[CreationError]) -> None:
        super().__init__("; ".join(f"{e.field}: {e.code.value}" for e in errors))
        self.errors = errors


def _spell_count(refs: CreationRefs) -> int:
    casting = refs.cls.spellcasting
    if casting is None or casting.first_level > CREATION_LEVEL:
        return 0
    if casting.kind == "prepared":
        return casting.spellbook_start
    return spells_known_count(refs.cls, CREATION_LEVEL)


def _prepared_pool(choices: CreationChoices, refs: CreationRefs, levelled: set[str]) -> set[str]:
    casting = refs.cls.spellcasting
    if casting is None or casting.kind != "prepared" or casting.first_level > CREATION_LEVEL:
        return set()
    return set(choices.spells) & levelled if casting.spellbook_start else levelled


def _expanded(refs: CreationRefs, regs: CharacterRegistries, top: int) -> set[str]:
    features, _, subclass = _base_feature_ids(refs)
    expanded = expanded_spell_indexes(features, CREATION_LEVEL, subclass, regs.features)
    return {s for s in expanded if (spell := regs.spells.find(s)) and 1 <= spell.level <= top}


def spell_pick_errors(
    choices: CreationChoices, refs: CreationRefs, regs: CharacterRegistries
) -> list[CreationError]:
    cls_index = refs.cls.index
    cantrips = class_spell_indexes(regs.spells, cls_index, 0, 0)
    count = cantrips_known_count(refs.cls, CREATION_LEVEL)
    errors = pick_errors("cantrips", choices.cantrips, count=count, allowed=cantrips)
    race_class = refs.race.cantrip_class or (refs.subrace.cantrip_class if refs.subrace else None)
    race_count = refs.race.cantrip_choices + (refs.subrace.cantrip_choices if refs.subrace else 0)
    race_pool = class_spell_indexes(regs.spells, race_class, 0, 0) if race_class else set[str]()
    errors += pick_errors(
        "race_cantrips",
        choices.race_cantrips,
        count=race_count,
        allowed=race_pool,
        taken=choices.cantrips,
    )
    top = max_spell_level(refs.cls, CREATION_LEVEL)
    levelled = class_spell_indexes(regs.spells, cls_index, 1, top)
    levelled |= _expanded(refs, regs, top)
    errors += pick_errors("spells", choices.spells, count=_spell_count(refs), allowed=levelled)
    pool = _prepared_pool(choices, refs, levelled)
    errors += pick_errors("prepared", choices.prepared, count=None, allowed=pool)
    return errors


def _final_abilities(choices: CreationChoices, refs: CreationRefs) -> dict[Ability, int]:
    bonuses = racial_bonuses(refs.race, refs.subrace, choices.ability_choice_picks)
    return apply_bonuses(choices.base_scores, bonuses)


def _prepared_limit_errors(choices: CreationChoices, refs: CreationRefs) -> list[CreationError]:
    limit = prepared_spell_limit(refs.cls, CREATION_LEVEL, _final_abilities(choices, refs))
    if limit == 0 or len(choices.prepared) <= limit:
        return []  # non-prepared casters are refused by spell_pick_errors
    detail = f"{len(choices.prepared)} prepared, the limit is {limit}"
    return [
        CreationError(code=CreationErrorCode.PREPARED_OVER_LIMIT, field="prepared", detail=detail)
    ]


def _base_feature_ids(refs: CreationRefs) -> tuple[list[str], list[str], str | None]:
    features = list(refs.cls.level(CREATION_LEVEL).features)
    subclass = refs.cls.subclass_index if refs.cls.subclass_level <= CREATION_LEVEL else None
    if subclass is not None:
        for row in refs.cls.subclass_features:
            if row.level <= CREATION_LEVEL:
                features.extend(row.features)
    sub = refs.subrace
    traits = [*refs.race.traits, *(sub.traits if sub else ())]
    return list(dict.fromkeys(features)), list(dict.fromkeys(traits)), subclass


def _proficient_skills(
    choices: CreationChoices, refs: CreationRefs, extra: Sequence[str]
) -> list[str]:
    granted = granted_skills(refs) + choices.class_skills + choices.race_skills
    return list(dict.fromkeys([*granted, *extra]))


def _feature_pick_errors(
    choices: CreationChoices, refs: CreationRefs, regs: CharacterRegistries
) -> list[CreationError]:
    features, traits, _ = _base_feature_ids(refs)
    ids = features + traits
    effects = feature_effects(ids, CREATION_LEVEL, regs.features)
    proficient = _proficient_skills(choices, refs, effects.skills)
    return feature_choice_errors(ids, choices.feature_choices, regs.features, proficient)


def validate_creation(choices: CreationChoices, regs: CharacterRegistries) -> list[CreationError]:
    errors = text_errors(choices) + ability_score_errors(choices)
    refs, ref_errors = resolve_refs(choices, regs)
    if refs is None:
        return errors + ref_errors
    allowed = refs.race.ability_choice.options if refs.race.ability_choice else ()
    count = refs.race.ability_choice.choose if refs.race.ability_choice else 0
    picks = [a.value for a in choices.ability_choice_picks]
    errors += pick_errors("ability_choice_picks", picks, count=count, allowed=allowed)
    errors += skill_tool_language_errors(choices, refs, regs)
    errors += equipment_errors(choices, refs)
    errors += class_choice_errors(choices, refs, CREATION_LEVEL)
    errors += _feature_pick_errors(choices, refs, regs)
    errors += spell_pick_errors(choices, refs, regs)
    if not ability_score_errors(choices):
        errors += _prepared_limit_errors(choices, refs)
    return errors


def _inventory(choices: CreationChoices, refs: CreationRefs) -> list[InventoryItem]:
    counts: dict[str, int] = {}
    entries = list(refs.cls.equipment.fixed)
    for choice in refs.cls.equipment.choices:
        entries.extend(choice.options[choices.equipment_picks[choice.id]])
    entries.extend(refs.background.gear)
    for entry in entries:
        counts[entry.item] = counts.get(entry.item, 0) + entry.qty
    return [InventoryItem(item=item, qty=qty) for item, qty in counts.items()]


def _has_property(item: SrdEquipment, prop: str) -> bool:
    return any(p.index == prop for p in item.properties)


def _pick_hands(
    melee: Sequence[tuple[SrdEquipment, int]], shield: str | None
) -> tuple[str | None, str | None]:
    usable = [pair for pair in melee if not (shield and _has_property(pair[0], "two-handed"))]
    if not usable:
        return None, None
    main, qty = usable[0]
    if shield or not _has_property(main, "light"):
        return main.index, None
    if qty > 1:
        return main.index, main.index
    spare = [pair[0] for pair in usable[1:] if _has_property(pair[0], "light")]
    return main.index, spare[0].index if spare else None


def auto_equip(
    inventory: Sequence[InventoryItem],
    equipment: Registry[SrdEquipment],
    abilities: Mapping[Ability, int],
) -> Equipped:
    held = [(e, row.qty) for row in inventory if (e := equipment.find(row.item)) is not None]
    body = [e for e, _ in held if e.armor_class and e.armor_category not in (None, SHIELD_CATEGORY)]
    shield = next((e.index for e, _ in held if e.armor_category == SHIELD_CATEGORY), None)
    armor = max(body, key=lambda a: armor_class(abilities, armor=a), default=None)
    melee = [(e, q) for e, q in held if e.damage and e.weapon_range == _MELEE]
    main, off = _pick_hands(melee, shield)
    ranged = next((e.index for e, _ in held if e.damage and e.weapon_range == _RANGED), None)
    return Equipped(
        armor=armor.index if armor else None,
        shield=shield,
        main_hand=main,
        off_hand=off,
        ranged=ranged,
    )


def _features(
    choices: CreationChoices, refs: CreationRefs, regs: CharacterRegistries
) -> tuple[list[str], list[str], str | None]:
    features, traits, subclass = _base_feature_ids(refs)
    for choice in refs.cls.choices:
        if choice.level <= CREATION_LEVEL:
            features.extend(choices.class_choices.get(choice.id, []))
    picks, feats = choices.feature_choices, regs.features
    return with_picks(features, picks, feats), with_picks(traits, picks, feats), subclass


def _uses_spellbook(refs: CreationRefs) -> bool:
    casting = refs.cls.spellcasting
    return casting is not None and casting.spellbook_start > 0


def _pc_data(
    choices: CreationChoices,
    refs: CreationRefs,
    abilities: Mapping[Ability, int],
    regs: CharacterRegistries,
) -> PcData:
    inventory = _inventory(choices, refs)
    features, traits, subclass = _features(choices, refs, regs)
    effects = feature_effects(features + traits, CREATION_LEVEL, regs.features)
    sub = refs.subrace
    return PcData(
        race=refs.race.index,
        subrace=sub.index if sub else None,
        class_index=refs.cls.index,
        level=CREATION_LEVEL,
        subclass=subclass,
        background=refs.background.index,
        base_abilities=dict(choices.base_scores),
        armor_proficiencies=list(dict.fromkeys([*refs.cls.armor, *effects.armor])),
        weapon_proficiencies=list(
            dict.fromkeys(
                [*refs.cls.weapons, *refs.race.weapon_proficiencies]
                + (list(sub.weapon_proficiencies) if sub else [])
                + list(effects.weapons)
            )
        ),
        tool_proficiencies=list(
            dict.fromkeys(granted_tools(refs) + list(choices.tool_picks) + list(effects.tools))
        ),
        languages=granted_languages(refs) + list(choices.language_picks),
        features=features,
        traits=traits,
        class_choices={k: list(v) for k, v in choices.class_choices.items()},
        feature_choices={k: list(v) for k, v in choices.feature_choices.items()},
        inventory=inventory,
        equipped=auto_equip(inventory, regs.equipment, abilities),
        portrait_id=choices.portrait_id,
        pronouns=choices.pronouns,
        backstory=choices.backstory,
        cantrips=list(choices.cantrips),
        race_cantrips=list(choices.race_cantrips),
        spells_known=[] if _uses_spellbook(refs) else list(choices.spells),
        spellbook=list(choices.spells) if _uses_spellbook(refs) else [],
        prepared=list(choices.prepared),
    )


def _ac(pc: PcData, equipment: Registry[SrdEquipment], abilities: Mapping[Ability, int]) -> int:
    armor = equipment.get(pc.equipped.armor) if pc.equipped.armor else None
    shield = equipment.get(pc.equipped.shield) if pc.equipped.shield else None
    return armor_class(abilities, armor=armor, shield=shield)


def build_character(
    choices: CreationChoices, regs: CharacterRegistries, creature_id: str
) -> Creature:
    errors = validate_creation(choices, regs)
    refs, _ = resolve_refs(choices, regs)
    if errors or refs is None:
        raise CreationInvalid(errors)
    abilities = _final_abilities(choices, refs)
    pc = _pc_data(choices, refs, abilities, regs)
    ids, feats = pc.features + pc.traits, regs.features
    effects = feature_effects(ids, CREATION_LEVEL, feats)
    con_mod = ability_modifier(abilities[Ability.CON])
    max_hp = max_hp_at_level(refs.cls.hit_die, con_mod, CREATION_LEVEL)
    max_hp += effects.hp_per_level * CREATION_LEVEL
    skills = _proficient_skills(choices, refs, effects.skills)
    creature = Creature(
        id=creature_id,
        name=choices.name.strip(),
        kind=CreatureKind.PC,
        abilities=abilities,
        max_hp=max_hp,
        hp=max_hp,
        ac=_ac(pc, regs.equipment, abilities),
        proficiency_bonus=proficiency_bonus(CREATION_LEVEL),
        save_proficiencies=[Ability(a) for a in refs.cls.saving_throws],
        skill_proficiencies=[Skill(s) for s in skills],
        skill_expertise=expertise_picks(ids, choices.feature_choices, feats),
        resistances=list(effects.resistances),
        speed=refs.race.speed + effects.speed,
        size=Size(refs.race.size),
        darkvision=max(refs.race.darkvision, effects.darkvision),
        resources={
            **slot_resources(refs.cls, CREATION_LEVEL),
            **feature_resources(ids, CREATION_LEVEL, feats),
        },
        pc=pc,
    )
    bonus = feature_ac_bonus(creature, feats, armored=pc.equipped.armor is not None)
    return creature.model_copy(update={"ac": creature.ac + bonus}) if bonus else creature
