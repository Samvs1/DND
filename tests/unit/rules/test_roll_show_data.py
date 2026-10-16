"""M26.2 roll data for the dice show: named bonuses, advantage reasons, kinds, targets, sources.

Golden numbers come from SRD 5.1 (CC-BY-4.0): "Proficiency Bonus", "Using Ability Scores"
(modifier = (score - 10) // 2), Rogue "Expertise" (double proficiency), Conditions "Poisoned".
"""

from __future__ import annotations

import random

from hypothesis import given
from hypothesis import strategies as st

from aidm.models.abilities import Ability, Skill
from aidm.models.checks import CheckKind, DcTier
from aidm.models.combat_events import AttackRolled
from aidm.models.commands import AttackCommand
from aidm.models.dice import AdvState, RollKind, RollPart
from aidm.models.encounter import Side
from aidm.models.events import AnyEvent, CheckResolved, DiceRolled
from aidm.models.state import Creature, CreatureKind
from aidm.rules.checks import (
    ability_check,
    check_parts,
    difficulty_word,
    saving_throw,
    skill_check,
)
from aidm.rules.condition_timing import new_condition
from aidm.rules.conditions import save_with_conditions, skill_check_with_conditions
from aidm.rules.d20 import SITUATION, adv_reasons
from tests.unit.rules.combat_fixtures import ScriptedRng, do, fight, monster
from tests.unit.rules.encounter_fixtures import make_pc
from tests.unit.rules.spell_fixtures import cast, caster


def _rogue(**update: object) -> Creature:
    # A level 1 rogue: DEX 16 (+3), proficiency bonus +2 (SRD 5.1 level 1), Stealth proficient.
    base = Creature(
        id="r",
        name="Rogue",
        kind=CreatureKind.PC,
        abilities={Ability.STR: 8, Ability.DEX: 16, Ability.CON: 12,
                   Ability.INT: 10, Ability.WIS: 10, Ability.CHA: 14},
        max_hp=9,
        hp=9,
        proficiency_bonus=2,
        skill_proficiencies=[Skill.STEALTH],
        save_proficiencies=[Ability.DEX, Ability.INT],
    )  # fmt: skip
    return base.model_copy(update=update)


def _of[T](events: list[AnyEvent], kind: type[T]) -> list[T]:
    return [e for e in events if isinstance(e, kind)]


def test_golden_parts_rogue_stealth_dex_and_prof() -> None:
    result = skill_check(random.Random(1), _rogue(), Skill.STEALTH, 15)
    assert result.parts == (RollPart(name="DEX", value=3), RollPart(name="PROF", value=2))
    assert result.roll.modifier == 5


def test_golden_parts_expertise_doubles_proficiency() -> None:
    rogue = _rogue(skill_expertise=[Skill.STEALTH])
    result = skill_check(random.Random(1), rogue, Skill.STEALTH, 15)
    assert result.parts == (RollPart(name="DEX", value=3), RollPart(name="EXPERTISE", value=4))


def test_golden_parts_situational_bonus_becomes_bonus() -> None:
    # Guidance-style +2 from the caller is the one BONUS remainder.
    result = skill_check(random.Random(1), _rogue(), Skill.STEALTH, 15, bonus=2)
    assert [(p.name, p.value) for p in result.parts] == [("DEX", 3), ("PROF", 2), ("BONUS", 2)]


def test_golden_parts_save_and_plain_ability_check() -> None:
    save = saving_throw(random.Random(1), _rogue(), Ability.DEX, 12)
    assert [(p.name, p.value) for p in save.parts] == [("DEX", 3), ("PROF", 2)]
    plain = ability_check(random.Random(1), _rogue(), Ability.STR, 10)
    assert [(p.name, p.value) for p in plain.parts] == [("STR", -1)]
    assert plain.adv_why == () and plain.tier is None


@given(
    score=st.integers(1, 30),
    pb=st.integers(0, 6),
    proficient=st.booleans(),
    expert=st.booleans(),
    bonus=st.integers(-10, 10),
    kind=st.sampled_from(list(CheckKind)),
)
def test_parts_always_sum_to_the_modifier(
    score: int, pb: int, proficient: bool, expert: bool, bonus: int, kind: CheckKind
) -> None:
    rogue = _rogue(
        abilities={**_rogue().abilities, Ability.DEX: score},
        proficiency_bonus=pb,
        skill_proficiencies=[Skill.ACROBATICS] if proficient else [],
        skill_expertise=[Skill.ACROBATICS] if expert else [],
        save_proficiencies=[Ability.DEX] if proficient else [],
    )
    rng = random.Random(score)
    if kind is CheckKind.SKILL:
        result = skill_check(rng, rogue, Skill.ACROBATICS, 10, bonus=bonus)
    elif kind is CheckKind.SAVE:
        result = saving_throw(rng, rogue, Ability.DEX, 10, bonus=bonus)
    else:
        result = ability_check(rng, rogue, Ability.DEX, 10, bonus=bonus)
    assert sum(p.value for p in result.parts) == result.roll.modifier
    assert result.parts[0].name == "DEX"
    modifier = result.roll.modifier
    assert check_parts(rogue, kind, Ability.DEX, result.skill, modifier) == result.parts


def test_adv_why_poisoned_gives_disadvantage_on_a_check() -> None:
    # SRD 5.1 Poisoned: disadvantage on attack rolls and ability checks.
    rogue = _rogue(conditions=[new_condition("poisoned")])
    result = skill_check_with_conditions(random.Random(2), rogue, Skill.STEALTH, 15)
    assert result.roll.adv is AdvState.DISADVANTAGE
    assert result.adv_why == ("Poisoned",)


def test_adv_why_dm_advantage_is_the_situation_and_cancels_with_poison() -> None:
    plain = skill_check_with_conditions(
        random.Random(2), _rogue(), Skill.STEALTH, 15, adv_sources=1
    )
    assert plain.roll.adv is AdvState.ADVANTAGE and plain.adv_why == (SITUATION,)
    poisoned = _rogue(conditions=[new_condition("poisoned")])
    both = skill_check_with_conditions(random.Random(2), poisoned, Skill.STEALTH, 15, adv_sources=1)
    assert both.roll.adv is AdvState.NORMAL and both.adv_why == ()
    named = save_with_conditions(
        random.Random(2), _rogue(), Ability.WIS, 12, adv_sources=1, source_names=["Magic Res"]
    )
    assert named.adv_why == ("Magic Res",)


def test_adv_reasons_dedupes_and_falls_back() -> None:
    assert adv_reasons(AdvState.NORMAL, ["Prone"], ["Poisoned"]) == ()
    assert adv_reasons(AdvState.ADVANTAGE, ["Prone", "Prone"], []) == ("Prone",)
    assert adv_reasons(AdvState.DISADVANTAGE, ["Prone"], []) == (SITUATION,)


def test_difficulty_word_from_a_tier() -> None:
    assert difficulty_word(DcTier.MEDIUM) == "medium"
    assert difficulty_word(DcTier.VERY_HARD) == "very hard"


def test_attack_and_its_damage_rolls_name_kind_target_and_readable_rider() -> None:
    # Rogue dagger 1d4+3 with advantage (prone target) adds Sneak Attack 1d6 (SRD 5.1 Rogue).
    state = fight(
        [
            (make_pc("a", class_index="rogue"), Side.PARTY, "gate"),
            (monster("gob", hp=40, ac=12), Side.HOSTILE, "gate"),
        ]
    )
    state.creatures["gob"].conditions.append(new_condition("prone"))
    cmd = AttackCommand(actor_id="a", target_id="gob", option="main_hand")
    events = do(state, cmd, ScriptedRng(15, 2, 3, 4))
    attack = _of(events, AttackRolled)[0]
    assert attack.target_id == "gob" and attack.adv_why == ("Prone",)
    rolls = _of(events, DiceRolled)
    assert [(r.kind, r.target_id) for r in rolls] == [(RollKind.DAMAGE, "gob")] * 2
    assert rolls[1].label == "Sneak Attack"
    assert all("-" not in r.label for r in rolls)


def test_monster_save_against_a_heros_spell_names_the_caster() -> None:
    # Sacred Flame: DEX save vs the cleric's DC 13 (8 + WIS 3 + PB 2, SRD 5.1 Spellcasting).
    # The goblin's Magic Resistance gives advantage: d20s 5 and 4 keep 5 -> fails; 1d8 = 6.
    cleric = caster("c", "cleric", cantrips=["sacred-flame"])
    gob = monster("gob", hp=30)
    gob.traits = ["magic-resistance"]
    state = fight([(cleric, Side.PARTY, "gate"), (gob, Side.HOSTILE, "yard")])
    events = cast(state, "c", "sacred-flame", ScriptedRng(5, 4, 6), targets=["gob"])
    save = _of(events, CheckResolved)[0]
    assert (save.creature_id, save.source_id, save.result.success) == ("gob", "c", False)
    assert save.result.adv_why == ("Magic Resistance",)
    assert save.result.tier is None  # a spell save DC is not a tier
    damage = _of(events, DiceRolled)[0]
    assert (damage.kind, damage.target_id, damage.label) == (RollKind.DAMAGE, "gob", "Sacred Flame")
