"""Gear boons and tool proficiency in checks (M27.3): `rules.gear_checks`, `rules.checks`,
`rules.boons`; boons named in `adv_why`, advantage never stacks, PROF once for tool OR skill."""

import random
from typing import get_args

from aidm.data.item_uses import BoonScope as DataBoonScope
from aidm.models.abilities import Ability, Skill
from aidm.models.commands import CastCommand
from aidm.models.dice import AdvState
from aidm.models.events import CheckResolved
from aidm.models.item_events import BoonEnded
from aidm.models.state import Creature
from aidm.models.world import ActiveBoon, BoonScope
from aidm.models.world_events import PartyMoved
from aidm.rules.abilities import ability_modifier
from aidm.rules.boons import long_rest_boon_events, save_boon_names
from aidm.rules.checks import PROF_PART, ability_check, skill_check
from aidm.rules.gear_checks import TOOL_AND_SKILL, gear_check
from aidm.rules.light import DARKNESS
from aidm.rules.rests import long_rest
from aidm.session.reducer import apply
from tests.unit.rules.combat_fixtures import do
from tests.unit.rules.item_fixtures import CAVE, DOCKS, at, hero
from tests.unit.rules.spell_fixtures import battle, caster


def _boon(name: str, skills: tuple[str, ...] = (), **extra: object) -> ActiveBoon:
    fields: dict[str, object] = {
        "creature_id": "hero",
        "use_id": f"{name.lower()}-use",
        "name": name,
        "skills": skills,
        "node": DOCKS,
        **extra,
    }
    return ActiveBoon.model_validate(fields)


def _skilled(skills: list[Skill], tools: list[str]) -> Creature:
    creature = hero(tools=tools)
    creature.skill_proficiencies = skills
    creature.skill_expertise = []
    return creature


def _prof_parts(creature: Creature, skill: Skill, tool: str | None) -> list[int]:
    result = skill_check(random.Random(1), creature, skill, 10, tool=tool)
    return [p.value for p in result.parts if p.name == PROF_PART]


def test_tool_or_skill_proficiency_adds_prof_once() -> None:
    pb = hero().proficiency_bonus
    assert _prof_parts(_skilled([], ["disguise-kit"]), Skill.DECEPTION, "disguise-kit") == [pb]
    assert _prof_parts(_skilled([Skill.DECEPTION], []), Skill.DECEPTION, "disguise-kit") == [pb]
    both = _skilled([Skill.DECEPTION], ["disguise-kit"])
    assert _prof_parts(both, Skill.DECEPTION, "disguise-kit") == [pb]
    assert _prof_parts(_skilled([], []), Skill.DECEPTION, "disguise-kit") == []
    assert _prof_parts(_skilled([], ["disguise-kit"]), Skill.DECEPTION, None) == []


def test_tool_proficiency_on_an_ability_check() -> None:
    thief = _skilled([], ["thieves-tools"])
    dex = ability_modifier(thief.abilities[Ability.DEX])
    result = ability_check(random.Random(1), thief, Ability.DEX, 10, tool="thieves-tools")
    assert result.roll.modifier == dex + thief.proficiency_bonus
    assert sum(p.value for p in result.parts) == result.roll.modifier


def test_proficient_in_tool_and_skill_gives_advantage() -> None:
    both = _skilled([Skill.DECEPTION], ["disguise-kit"])
    state = at(DOCKS, both)
    result = gear_check(random.Random(1), state, both, Skill.DECEPTION, 10, tool="disguise-kit")
    assert result.roll.adv is AdvState.ADVANTAGE
    assert result.adv_why == (TOOL_AND_SKILL,)
    one = _skilled([], ["disguise-kit"])
    plain = gear_check(
        random.Random(1), at(DOCKS, one), one, Skill.DECEPTION, 10, tool="disguise-kit"
    )
    assert plain.roll.adv is AdvState.NORMAL


def test_a_tool_boon_makes_the_check_with_that_tool() -> None:
    trained = _skilled([], ["disguise-kit"])
    state = at(DOCKS, trained)
    state.world.boons = [_boon("Disguise Kit", ("deception",), tool="disguise-kit")]
    result = gear_check(random.Random(1), state, trained, Skill.DECEPTION, 10)
    assert [p.name for p in result.parts].count(PROF_PART) == 1
    assert result.adv_why == ("Disguise Kit",)


def test_boon_is_named_in_adv_why_and_never_stacks() -> None:
    me = hero()
    state = at(DOCKS, me)
    state.world.boons = [
        _boon("Magnifying glass", ("investigation",)),
        _boon("Lantern", ("investigation",)),
    ]
    result = gear_check(random.Random(1), state, me, Skill.INVESTIGATION, 10)
    assert result.roll.adv is AdvState.ADVANTAGE
    assert len(result.roll.rolls) == 2  # SRD 5.1: two d20s however many sources
    assert result.adv_why == ("Magnifying glass", "Lantern")
    asked = gear_check(random.Random(1), state, me, Skill.INVESTIGATION, 10, adv_sources=1)
    assert len(asked.roll.rolls) == 2
    other = gear_check(random.Random(1), state, me, Skill.PERCEPTION, 10)
    assert other.roll.adv is AdvState.NORMAL


def test_boon_and_darkness_cancel() -> None:
    me = hero()
    state = at(CAVE, me)
    state.world.boons = [_boon("Magnifying glass", ("investigation",), node=CAVE)]
    result = gear_check(random.Random(1), state, me, Skill.INVESTIGATION, 10)
    assert result.roll.adv is AdvState.NORMAL  # SRD 5.1: one of each cancels
    assert DARKNESS not in result.adv_why


def test_a_place_boon_counts_only_where_it_was_gained() -> None:
    me = hero()
    state = at(DOCKS, me)
    state.world.boons = [_boon("Spyglass", ("perception",), node=CAVE)]
    result = gear_check(random.Random(1), state, me, Skill.PERCEPTION, 10)
    assert result.roll.adv is AdvState.NORMAL


def test_long_rest_ends_until_long_rest_boons() -> None:
    state = at(DOCKS, hero())
    antitoxin = _boon("Antitoxin", saves_against=("poison",), scope="until_long_rest", node=None)
    state.world.boons = [antitoxin, _boon("Spyglass", ("perception",))]
    assert long_rest_boon_events(state) == [
        BoonEnded(creature_id="hero", use_id="antitoxin-use", reason="long rest")
    ]
    state.camp_supplies = 10
    assert any(isinstance(e, BoonEnded) for e in long_rest(state))


def test_antitoxin_gives_advantage_on_a_poison_save() -> None:
    state = battle(caster("w", "wizard", cantrips=["poison-spray"]), ("pal", "gate"))
    antitoxin = _boon("Antitoxin", saves_against=("poison",), scope="until_long_rest", node=None)
    state.world.boons = [antitoxin.model_copy(update={"creature_id": "pal"})]
    assert save_boon_names(state, "pal", {"poison"}) == ("Antitoxin",)
    assert save_boon_names(state, "pal", {"fire"}) == ()
    cmd = CastCommand(actor_id="w", spell_id="poison-spray", target_ids=("pal",))
    saves = [e for e in do(state, cmd, random.Random(3)) if isinstance(e, CheckResolved)]
    assert saves[0].result.roll.adv is AdvState.ADVANTAGE
    assert saves[0].result.adv_why == ("Antitoxin",)


def test_boons_follow_the_hero_s_place() -> None:
    state = at(DOCKS, hero())
    state.world.boons = [_boon("Spyglass", ("perception",))]
    apply(state, PartyMoved(from_node=DOCKS, to_node=CAVE, scene_index=2))
    assert state.world.boons == []


def test_boon_scope_mirrors_the_data_schema() -> None:
    assert get_args(BoonScope.__value__) == get_args(DataBoonScope.__value__)
