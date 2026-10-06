"""Character creation pipeline: every class x race builds; typed errors for bad input (SPEC 8).

Goldens cite SRD 5.1: class "Hit Points at 1st Level", "Armor and Shields", race traits.
"""

from __future__ import annotations

import pytest

from aidm.data.character_data import character_registries
from aidm.models.abilities import Ability, Skill
from aidm.models.character import Size
from aidm.models.creation import CreationChoices, CreationErrorCode
from aidm.models.events import CreatureAdded, event_adapter
from aidm.models.state import CreatureKind, GameState
from aidm.rules.abilities import ability_modifier
from aidm.rules.creation import CreationInvalid, build_character, validate_creation
from aidm.session.reducer import apply, replay
from tests.unit.rules.creation_fixtures import default_choices, race_combos

E = CreationErrorCode
REGS = character_registries()
CLASSES = [c.index for c in REGS.classes.all()]
COMBOS = race_combos()


def _codes(choices: CreationChoices) -> list[tuple[CreationErrorCode, str]]:
    return [(e.code, e.field) for e in validate_creation(choices, REGS)]


def _with(choices: CreationChoices, **update: object) -> CreationChoices:
    return CreationChoices.model_validate({**choices.model_dump(), **update})


@pytest.mark.parametrize("class_index", CLASSES)
@pytest.mark.parametrize(("race", "subrace"), COMBOS)
def test_default_choices_build(class_index: str, race: str, subrace: str | None) -> None:
    choices = default_choices(class_index, race, subrace)
    assert validate_creation(choices, REGS) == []
    pc = build_character(choices, REGS, "pc1")
    cls = REGS.classes.get(class_index)
    assert pc.kind is CreatureKind.PC and pc.pc is not None
    toughness = 1 if subrace == "hill-dwarf" else 0  # SRD Dwarven Toughness: +1 HP per level
    con_mod = ability_modifier(pc.abilities[Ability.CON])
    assert pc.max_hp == pc.hp == cls.hit_die + con_mod + toughness
    assert pc.proficiency_bonus == 2
    assert [a.value for a in pc.save_proficiencies] == list(cls.saving_throws)
    assert set(choices.class_skills) <= {s.value for s in pc.skill_proficiencies}
    assert pc.speed == REGS.races.get(race).speed
    assert pc.pc.level == 1 and pc.pc.class_index == class_index
    assert (pc.pc.subclass is not None) == (cls.subclass_level == 1)
    assert set(cls.level(1).features) <= set(pc.pc.features)
    assert pc.pc.equipped.main_hand is not None


def test_pc_creature_added_replays() -> None:
    pc = build_character(default_choices("wizard", "elf", "high-elf"), REGS, "pc1")
    event = CreatureAdded(creature=pc)
    assert event_adapter.validate_json(event.model_dump_json()) == event
    initial = GameState(campaign_id="c", seed=1)
    live = apply(initial.model_copy(deep=True), event)
    assert replay(initial, [event]) == live
    assert GameState.model_validate_json(live.model_dump_json()) == live
    assert live.creatures["pc1"].pc == pc.pc


def test_golden_hill_dwarf_fighter() -> None:
    # Standard array STR 15 DEX 14 CON 13 INT 12 WIS 10 CHA 8; dwarf CON +2, hill dwarf WIS +1.
    # HP: d10 max 10 + CON +2 + Dwarven Toughness 1 = 13. AC: chain mail 16 + shield 2 = 18.
    pc = build_character(default_choices("fighter", "dwarf", "hill-dwarf"), REGS, "f1")
    assert pc.abilities[Ability.CON] == 15 and pc.abilities[Ability.WIS] == 11
    assert (pc.max_hp, pc.ac, pc.speed, pc.darkvision, pc.size) == (13, 18, 25, 60, Size.MEDIUM)
    assert pc.pc is not None
    assert pc.pc.equipped.armor == "chain-mail" and pc.pc.equipped.shield == "shield"
    assert pc.pc.languages == ["common", "dwarvish"]
    assert "smiths-tools" in pc.pc.tool_proficiencies
    assert "battleaxes" in pc.pc.weapon_proficiencies
    assert "fighter-fighting-style-archery" in pc.pc.features
    assert {Skill.INSIGHT, Skill.RELIGION} <= set(pc.skill_proficiencies)  # acolyte


def test_golden_background_starting_gold() -> None:
    # M9.2: equipment packages plus the background purse (PHB backgrounds: acolyte 15 gp,
    # soldier 10 gp, noble 25 gp); no class starting wealth (that is the alternative to packages).
    purse = {b.index: b.gold for b in REGS.backgrounds.all()}
    assert (purse["acolyte"], purse["soldier"], purse["noble"]) == (15, 10, 25)
    assert all(10 <= gold <= 25 for gold in purse.values())
    pc = build_character(default_choices("fighter", "dwarf", "hill-dwarf"), REGS, "f1")
    assert pc.pc is not None and pc.pc.background == "acolyte" and pc.pc.gold == 15


def test_golden_high_elf_wizard() -> None:
    # DEX 14 + 2 = 16, INT 12 + 1 = 13, CON 13. HP d6 6 + 1 = 7. AC 10 + 3 = 13 (no armor).
    pc = build_character(default_choices("wizard", "elf", "high-elf"), REGS, "w1")
    assert (pc.abilities[Ability.DEX], pc.abilities[Ability.INT]) == (16, 13)
    assert (pc.max_hp, pc.ac) == (7, 13)
    assert pc.pc is not None
    assert len(pc.pc.cantrips) == 3 and len(pc.pc.race_cantrips) == 1
    assert len(pc.pc.spellbook) == 6 and pc.pc.spells_known == []
    assert Skill.PERCEPTION in pc.skill_proficiencies  # elf Keen Senses
    assert pc.pc.subclass is None  # Arcane Tradition at level 2


def test_golden_lightfoot_halfling_rogue_small() -> None:
    pc = build_character(default_choices("rogue", "halfling", "lightfoot-halfling"), REGS, "r1")
    assert pc.size is Size.SMALL and pc.speed == 25
    assert pc.pc is not None and "thieves-tools" in pc.pc.tool_proficiencies
    assert pc.pc.equipped.off_hand is not None  # two light weapons, no shield


def test_unknown_race_class_background() -> None:
    base = default_choices("fighter", "human", None)
    assert _codes(_with(base, race="orcish-giant")) == [(E.UNKNOWN_RACE, "race")]
    assert _codes(_with(base, class_index="bard")) == [(E.UNKNOWN_CLASS, "class_index")]
    assert _codes(_with(base, background="pirate")) == [(E.UNKNOWN_BACKGROUND, "background")]


def test_subrace_required_and_unknown() -> None:
    base = default_choices("fighter", "dwarf", "hill-dwarf")
    assert _codes(_with(base, subrace=None)) == [(E.SUBRACE_REQUIRED, "subrace")]
    assert _codes(_with(base, subrace="high-elf")) == [(E.UNKNOWN_SUBRACE, "subrace")]


def test_point_buy_overspend_through_validate() -> None:
    base = default_choices("fighter", "human", None)
    bad = _with(base, ability_method="point_buy", base_scores=dict.fromkeys(Ability, 15))
    assert _codes(bad) == [(E.POINT_BUY_OVERSPEND, "base_scores")]


def test_standard_array_duplicate_through_validate() -> None:
    base = default_choices("fighter", "human", None)
    scores = dict(zip(Ability, [15, 15, 13, 12, 10, 8], strict=True))
    assert _codes(_with(base, base_scores=scores)) == [(E.STANDARD_ARRAY_MISMATCH, "base_scores")]


def test_too_many_skills() -> None:
    base = default_choices("fighter", "human", None)
    bad = _with(base, class_skills=["acrobatics", "animal-handling", "athletics"])
    assert _codes(bad) == [(E.PICK_COUNT, "class_skills")]


def test_skill_not_in_class_list() -> None:
    base = default_choices("wizard", "human", None)
    bad = _with(base, class_skills=["arcana", "stealth"])
    assert _codes(bad) == [(E.PICK_NOT_ALLOWED, "class_skills")]


def test_skill_already_granted_by_background() -> None:
    base = default_choices("cleric", "human", None)  # acolyte grants insight and religion
    bad = _with(base, class_skills=["history", "religion"])
    assert _codes(bad) == [(E.PICK_DUPLICATE, "class_skills")]


def test_backstory_and_name_limits() -> None:
    base = default_choices("fighter", "human", None)
    assert _codes(_with(base, backstory="x" * 400)) == []
    assert _codes(_with(base, backstory="x" * 401)) == [(E.TEXT_TOO_LONG, "backstory")]
    assert _codes(_with(base, name="   ")) == [(E.NAME_INVALID, "name")]


def test_half_elf_ability_choices() -> None:
    base = default_choices("fighter", "half-elf", None)
    assert _codes(_with(base, ability_choice_picks=["cha", "str"])) == [
        (E.PICK_NOT_ALLOWED, "ability_choice_picks")
    ]
    assert _codes(_with(base, ability_choice_picks=["str", "str"])) == [
        (E.PICK_DUPLICATE, "ability_choice_picks")
    ]
    assert _codes(_with(base, ability_choice_picks=["str"])) == [
        (E.PICK_COUNT, "ability_choice_picks")
    ]


def test_tool_and_language_picks() -> None:
    dwarf = default_choices("fighter", "dwarf", "hill-dwarf")
    assert _codes(_with(dwarf, tool_picks=["lute"])) == [(E.PICK_NOT_ALLOWED, "tool_picks")]
    human = default_choices("fighter", "human", None)
    assert _codes(_with(human, language_picks=["common"])) == [(E.PICK_DUPLICATE, "language_picks")]
    assert _codes(_with(human, language_picks=["klingon"])) == [
        (E.PICK_NOT_ALLOWED, "language_picks")
    ]


def test_equipment_picks() -> None:
    base = default_choices("fighter", "human", None)
    missing = dict(base.equipment_picks)
    missing.pop("armor")
    assert _codes(_with(base, equipment_picks=missing)) == [
        (E.EQUIPMENT_MISSING, "equipment_picks.armor")
    ]
    assert _codes(_with(base, equipment_picks={**base.equipment_picks, "armor": 5})) == [
        (E.EQUIPMENT_INVALID, "equipment_picks.armor")
    ]
    assert _codes(_with(base, equipment_picks={**base.equipment_picks, "mount": 0})) == [
        (E.EQUIPMENT_INVALID, "equipment_picks.mount")
    ]


def test_equipment_package_choice_changes_gear() -> None:
    base = default_choices("fighter", "human", None)
    archer = _with(base, equipment_picks={**base.equipment_picks, "armor": 1})
    pc = build_character(archer, REGS, "f2")
    assert pc.pc is not None and pc.pc.equipped.armor == "leather-armor"
    assert pc.pc.equipped.ranged in {"longbow", "crossbow-light"}


def test_fighting_style_required() -> None:
    base = default_choices("fighter", "human", None)
    assert _codes(_with(base, class_choices={})) == [(E.PICK_COUNT, "class_choices.fighting-style")]
    ranger = default_choices("ranger", "human", None)
    bad = _with(ranger, class_choices={"fighting-style": ["ranger-fighting-style-archery"]})
    assert _codes(bad) == [(E.PICK_NOT_ALLOWED, "class_choices.fighting-style")]


def test_spell_picks() -> None:
    wizard = default_choices("wizard", "human", None)
    assert _codes(_with(wizard, cantrips=wizard.cantrips[:2])) == [(E.PICK_COUNT, "cantrips")]
    assert _codes(_with(wizard, cantrips=[*wizard.cantrips[:2], "sacred-flame"])) == [
        (E.PICK_NOT_ALLOWED, "cantrips")
    ]
    assert _codes(_with(wizard, spells=[*wizard.spells[:5], "fireball"])) == [
        (E.PICK_NOT_ALLOWED, "spells")
    ]
    assert _codes(_with(wizard, prepared=["cure-wounds"])) == [(E.PICK_NOT_ALLOWED, "prepared")]
    fighter = default_choices("fighter", "human", None)
    assert _codes(_with(fighter, cantrips=["light"])) == [
        (E.PICK_COUNT, "cantrips"),
        (E.PICK_NOT_ALLOWED, "cantrips"),
    ]
    warlock = default_choices("warlock", "human", None)
    assert _codes(_with(warlock, prepared=warlock.spells[:1])) == [(E.PICK_NOT_ALLOWED, "prepared")]


def test_build_rejects_invalid_choices() -> None:
    base = default_choices("fighter", "human", None)
    with pytest.raises(CreationInvalid) as info:
        build_character(_with(base, race="nope"), REGS, "x")
    assert [e.code for e in info.value.errors] == [E.UNKNOWN_RACE]
