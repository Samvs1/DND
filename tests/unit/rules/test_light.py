"""Light and darkness (M27.2, carried M27.12; GOAL_ITEMS "Light and darkness"): rules/light.py."""

from __future__ import annotations

import functools
from typing import get_args

from aidm.data.character_data import character_registries
from aidm.data.item_uses import LightPlace, LightReachKey, item_use_data
from aidm.dm.campaign_sample import load_sample_campaign
from aidm.models.abilities import Ability, Skill
from aidm.models.combat_events import CombatantMoved
from aidm.models.dice import AdvState
from aidm.models.encounter import Side
from aidm.models.events import AnyEvent
from aidm.models.item_events import LightEnded, LightLit
from aidm.models.state import Creature, GameState
from aidm.models.world import LightReach
from aidm.models.world_events import PartyMoved
from aidm.models.zones import Zone, ZoneEdge, ZoneMap, ZoneSurface
from aidm.rules.attack_profiles import find_option
from aidm.rules.campaign_install import install_campaign
from aidm.rules.condition_timing import new_condition
from aidm.rules.conditions import ability_check_with_conditions, skill_check_with_conditions
from aidm.rules.creation import build_character
from aidm.rules.hit_chance import AttackSituation, attack_situation
from aidm.rules.light import (
    DARKNESS,
    attack_darkness,
    lit_zones,
    place_dark,
    sight_darkness,
    zone_lit,
)
from aidm.session.reducer import apply
from tests.unit.rules.combat_fixtures import REGS, ScriptedRng, fight, monster
from tests.unit.rules.creation_fixtures import default_choices
from tests.unit.rules.encounter_fixtures import make_pc

CAVE = "saltcellar-tunnels"  # sample campaign: terrain tags cave, crypt
CRYPT = "sunken-vestry"  # ruins, crypt: a crypt among ruins is dark too
DOCKS = "gullmere-quay-docks"  # village, bridge: never dark


@functools.cache
def _install() -> tuple[AnyEvent, ...]:
    return tuple(
        install_campaign(GameState(campaign_id="light", seed=1), load_sample_campaign(), 1)
    )


def _at(node: str) -> GameState:
    state = GameState(campaign_id="light", seed=1)
    for event in _install():
        apply(state, event)
    apply(state, PartyMoved(from_node=state.world.current_node, to_node=node, scene_index=1))
    return state


def _dwarf(cid: str) -> Creature:
    template = build_character(
        default_choices("fighter", "dwarf", "hill-dwarf"), character_registries(), cid
    )
    return template.model_copy(update={"id": cid, "name": cid.title()}, deep=True)


def _chain(*surfaces: tuple[str, str]) -> ZoneMap:
    """Four zones in a row, 15 ft hops: a - b - c - d; `surfaces` = (zone, kind) pairs."""
    lying = dict(surfaces)
    zones = [
        Zone(id=z, name=z.upper(), surfaces=[ZoneSurface(kind=lying[z])] if z in lying else [])
        for z in "abcd"
    ]
    edges = [ZoneEdge(a=x, b=y, feet=15) for x, y in ("ab", "bc", "cd")]
    return ZoneMap(zones=zones, edges=edges)


def _crypt_fight(attacker: Creature, foe_zone: str, zone_map: ZoneMap | None = None) -> GameState:
    placements = [(attacker, Side.PARTY, "a"), (monster("gob"), Side.HOSTILE, foe_zone)]
    return fight(placements, zone_map or _chain(), base=_at(CRYPT))


def _situation(state: GameState, attacker: str = "hero", target: str = "gob") -> AttackSituation:
    profile = find_option(state.creatures[attacker], REGS.chars, "ranged")
    assert profile is not None
    return attack_situation(state, attacker, target, profile, REGS.chars.features)


def test_places_are_dark_by_their_terrain() -> None:
    assert place_dark(_at(CAVE)) and place_dark(_at(CRYPT))
    assert not place_dark(_at(DOCKS))
    assert not place_dark(GameState(campaign_id="old", seed=1))  # no plan: an old save


def test_golden_search_in_a_cave_rolls_at_disadvantage() -> None:
    # GOAL_ITEMS: a dark unlit place puts every sight and search check at disadvantage.
    # SRD 5.1 Advantage and Disadvantage: roll two d20s and keep the lower (15, 4 -> 4).
    state = _at(CAVE)
    pc = make_pc("hero")
    dark = sight_darkness(state, Skill.PERCEPTION)
    result = skill_check_with_conditions(
        ScriptedRng(15, 4), pc, Skill.PERCEPTION, 10, dis_names=dark
    )
    assert dark == (DARKNESS,)
    assert result.roll.adv is AdvState.DISADVANTAGE and result.roll.natural == 4
    assert result.adv_why == ("Darkness",)


def test_every_search_check_is_dark_but_not_other_checks() -> None:
    state = _at(CAVE)
    assert sight_darkness(state, Skill.INVESTIGATION) == (DARKNESS,)
    assert sight_darkness(state, Ability.WIS) == (DARKNESS,)
    assert sight_darkness(state, Ability.INT) == (DARKNESS,)
    assert sight_darkness(state, Skill.ATHLETICS) == ()
    assert sight_darkness(state, Ability.STR) == ()
    assert sight_darkness(_at(DOCKS), Skill.PERCEPTION) == ()


def test_darkvision_keeps_the_perception_disadvantage() -> None:
    # SRD 5.1 Darkvision: darkness counts as dim light, which still gives disadvantage on
    # Wisdom (Perception) checks relying on sight.
    state = _at(CAVE)
    dwarf = _dwarf("dwarf")
    assert dwarf.darkvision == 60
    dark = sight_darkness(state, Ability.WIS)
    result = ability_check_with_conditions(
        ScriptedRng(3, 18), dwarf, Ability.WIS, 10, dis_names=dark
    )
    assert result.roll.adv is AdvState.DISADVANTAGE and result.adv_why == (DARKNESS,)


def test_ai_advantage_cancels_darkness() -> None:
    # SRD 5.1: one advantage and one disadvantage source cancel (never stack).
    result = skill_check_with_conditions(
        ScriptedRng(9), make_pc("hero"), Skill.PERCEPTION, 10, adv_sources=1, dis_names=(DARKNESS,)
    )
    assert result.roll.adv is AdvState.NORMAL and result.adv_why == ()


def test_a_carried_light_lights_every_dark_place_until_it_ends() -> None:
    # M27.12: the light travels with its bearer; PartyMoved keeps it, LightEnded ends it.
    state = _at(CAVE)
    state.creatures["hero"] = make_pc("hero")
    apply(state, LightLit(creature_id="hero", item="torch"))
    assert sight_darkness(state, Skill.PERCEPTION) == () and zone_lit(state, "any")
    apply(state, PartyMoved(from_node=CAVE, to_node=CRYPT, scene_index=2))
    assert sight_darkness(state, Skill.PERCEPTION) == () and zone_lit(state, "any")
    apply(state, LightEnded(creature_id="hero", reason="long rest"))
    assert sight_darkness(state, Skill.PERCEPTION) == (DARKNESS,) and not zone_lit(state, "any")


def test_a_light_whose_bearer_is_gone_does_not_count() -> None:
    state = _at(CAVE)
    state.creatures["hero"] = make_pc("hero")
    apply(state, LightLit(creature_id="hero", item="torch"))
    del state.creatures["hero"]
    assert sight_darkness(state, Skill.PERCEPTION) == (DARKNESS,)


def test_golden_crypt_fight_human_vs_dwarf() -> None:
    # GOAL_ITEMS: a hero WITHOUT darkvision attacks a target in a dark zone at disadvantage.
    human = _situation(_crypt_fight(make_pc("hero"), "b"))
    assert human.adv is AdvState.DISADVANTAGE and human.adv_why == (DARKNESS,)
    dwarf = _situation(_crypt_fight(_dwarf("hero"), "b"))
    assert dwarf.adv is AdvState.NORMAL and dwarf.adv_why == ()


def test_monsters_see_in_the_dark() -> None:
    state = _crypt_fight(make_pc("hero"), "a")
    assert not zone_lit(state, "a")
    assert attack_darkness(state, "gob", "a") == 0
    assert attack_darkness(state, "hero", "a") == 1


def test_no_darkness_in_a_fight_in_a_lit_terrain() -> None:
    placements = [(make_pc("hero"), Side.PARTY, "a"), (monster("gob"), Side.HOSTILE, "b")]
    state = fight(placements, _chain(), base=_at(DOCKS))
    assert _situation(state).adv is AdvState.NORMAL
    assert lit_zones(state) == frozenset("abcd")


def test_advantage_cancels_darkness_in_a_fight() -> None:
    state = _crypt_fight(make_pc("hero"), "b")
    state.creatures["hero"].conditions.append(new_condition("hidden"))
    assert _situation(state).adv is AdvState.NORMAL


def test_the_light_moves_with_its_bearer() -> None:
    # A torch: 20 ft bright light covers the bearer's zone and the next 15 ft hop (SRD 5.1).
    state = _crypt_fight(make_pc("hero"), "c")
    apply(state, LightLit(creature_id="hero", item="torch"))
    assert lit_zones(state) == frozenset("ab")
    assert _situation(state).adv is AdvState.DISADVANTAGE
    apply(state, CombatantMoved(creature_id="hero", from_zone="a", to_zone="b", feet=15))
    assert lit_zones(state) == frozenset("abc")
    assert _situation(state).adv is AdvState.NORMAL
    apply(state, CombatantMoved(creature_id="hero", from_zone="b", to_zone="d", feet=30))
    assert lit_zones(state) == frozenset("cd") and zone_lit(state, "c")
    assert not zone_lit(state, "a")


def test_a_candle_lights_only_its_own_zone() -> None:
    state = _crypt_fight(make_pc("hero"), "b")
    apply(state, LightLit(creature_id="hero", item="candle", reach="zone"))
    assert lit_zones(state) == frozenset("a")
    assert _situation(state).adv is AdvState.DISADVANTAGE


def test_a_fire_surface_lights_its_zone() -> None:
    state = _crypt_fight(make_pc("hero"), "c", _chain(("c", "fire"), ("b", "oil")))
    assert lit_zones(state) == frozenset("c")
    assert _situation(state).adv is AdvState.NORMAL


def test_light_reach_comes_from_data() -> None:
    assert get_args(LightReach.__value__) == get_args(LightReachKey.__value__)
    reach = {
        use.item: use.effect.reach
        for use in item_use_data().uses
        if isinstance(use.effect, LightPlace)
    }
    assert reach["candle"] == "zone"
    assert reach["torch"] == "touching" and reach["lantern-hooded"] == "touching"
