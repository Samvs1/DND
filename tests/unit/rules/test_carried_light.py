"""Carried light (M27.12, docs/next/GOAL_ITEMS.md "Light and darkness" and "Risk"): a light
belongs to its bearer, travels with the party until the long rest, and gives a dark place away."""

import random

from aidm.data.srd import srd
from aidm.models.abilities import Skill
from aidm.models.encounter import Side, SurpriseKind
from aidm.models.events import AnyEvent, ConditionApplied
from aidm.models.item_events import LightEnded, LightLit, PlaceAlerted
from aidm.models.state import GameState
from aidm.models.world_events import PartyMoved
from aidm.models.zones import Zone, ZoneEdge, ZoneMap
from aidm.rules.boons import long_rest_light_events
from aidm.rules.encounter import party_surprise, start_encounter
from aidm.rules.light import DARKNESS, arrival_events, hero_light, lit_zones, sight_darkness
from aidm.rules.rests import long_rest
from tests.unit.rules.combat_fixtures import fight, monster
from tests.unit.rules.encounter_fixtures import setup_for
from tests.unit.rules.item_fixtures import CAVE, DOCKS, at, gear_fight, hero, qty, refusal, run, use

CRYPT = "sunken-vestry"  # ruins, crypt: dark, next to CAVE


def _travel(state: GameState, to_node: str) -> list[AnyEvent]:
    """What the move resolver emits: PartyMoved, then the carried light's arrival events."""
    world = state.world
    moved = PartyMoved(
        from_node=world.current_node, to_node=to_node, scene_index=world.scene_index + 1
    )
    events: list[AnyEvent] = [moved, *arrival_events(state, to_node)]
    run(state, events)
    return events


def _row() -> ZoneMap:
    """Four zones in a row, 15 ft hops: a - b - c - d."""
    zones = [Zone(id=z, name=z.upper()) for z in "abcd"]
    edges = [ZoneEdge(a=x, b=y, feet=15) for x, y in ("ab", "bc", "cd")]
    return ZoneMap(zones=zones, edges=edges)


def test_a_torch_lit_in_one_dark_place_lights_the_next() -> None:
    state = at(CAVE, hero(gear=[("torch", 2)]))
    run(state, use(state, "torch"))
    assert qty(state, "hero", "torch") == 1
    _travel(state, CRYPT)
    assert sight_darkness(state, Skill.PERCEPTION) == ()
    assert qty(state, "hero", "torch") == 1  # no second torch spent
    assert "already carries a lit torch" in refusal(use(state, "torch"))


def test_relighting_is_refused_and_consumes_nothing() -> None:
    state = at(CAVE, hero(gear=[("torch", 2), "lantern-hooded"]))
    run(state, use(state, "torch"))
    assert "already carries a lit torch" in refusal(use(state, "torch"))
    assert "already carries a lit torch" in refusal(use(state, "lantern-hooded"))
    assert qty(state, "hero", "torch") == 1


def test_lighting_in_a_daylit_place_is_allowed_even_in_a_fight() -> None:
    # owner 2026-10-22: a light is carried, so lighting it in daylight is never refused
    calm = at(DOCKS, hero(gear=["torch"]))
    events = use(calm, "torch")
    assert any(isinstance(e, LightLit) for e in events)
    assert not any(isinstance(e, PlaceAlerted) for e in events)  # daylight gives nothing away
    state = gear_fight(DOCKS, hero(gear=["torch"]))
    run(state, use(state, "torch"))
    assert qty(state, "hero", "torch") == 0
    assert state.encounter is not None
    assert state.encounter.combatant("hero").economy.bonus_action is False


def test_torch_lit_in_daylight_is_carried_into_the_cave() -> None:
    state = at(DOCKS, hero(gear=["torch"]))
    run(state, use(state, "torch"))
    assert state.world.alerted is None
    events = _travel(state, CAVE)
    assert any(isinstance(e, PlaceAlerted) and e.reason == "light" for e in events)
    assert hero_light(state, "hero") is not None
    assert state.world.alerted == CAVE


def test_two_bearers_in_a_fight_light_two_zones() -> None:
    placements = [
        (hero(), Side.PARTY, "a"),
        (hero("ally"), Side.PARTY, "d"),
        (monster("gob"), Side.HOSTILE, "c"),
    ]
    state = fight(placements, _row(), base=at(CRYPT))
    run(state, [LightLit(creature_id="hero", item="candle", reach="zone")])
    run(state, [LightLit(creature_id="ally", item="candle", reach="zone")])
    assert lit_zones(state) == frozenset("ad")


def test_in_a_fight_a_second_light_may_light_no_new_zone() -> None:
    near = gear_fight(CAVE, hero(gear=["torch"]), (hero("ally"), Side.PARTY, "a"))
    run(near, [LightLit(creature_id="ally", item="torch")])  # lights a and b already
    run(near, use(near, "torch"))  # owner 2026-10-22: allowed, the bonus action is spent
    assert qty(near, "hero", "torch") == 0
    assert lit_zones(near) == frozenset("ab")
    candle = gear_fight(CAVE, hero(gear=["torch"]), (hero("ally"), Side.PARTY, "a"))
    run(candle, [LightLit(creature_id="ally", item="candle", reach="zone")])  # lights a only
    run(candle, use(candle, "torch"))
    assert lit_zones(candle) == frozenset("ab")


def test_the_long_rest_ends_every_light() -> None:
    state = at(DOCKS, hero(), hero("ally"))
    run(state, [LightLit(creature_id="hero", item="torch")])
    run(state, [LightLit(creature_id="ally", item="lantern-hooded")])
    assert long_rest_light_events(state) == [
        LightEnded(creature_id="hero", reason="long rest"),
        LightEnded(creature_id="ally", reason="long rest"),
    ]
    state.camp_supplies = 100
    run(state, long_rest(state))
    assert state.world.lights == []


def test_arriving_in_a_dark_place_with_a_light_alerts_it() -> None:
    state = at(DOCKS, hero())
    run(state, [LightLit(creature_id="hero", item="torch")])
    assert [type(e) for e in _travel(state, CAVE)] == [PartyMoved, PlaceAlerted]
    assert state.world.alerted == CAVE
    assert party_surprise(state, SurpriseKind.HOSTILE) is SurpriseKind.NONE
    setup = setup_for(["hero"], ["goblin"], SurpriseKind.HOSTILE)
    events = start_encounter(random.Random(1), state, setup, srd().monsters)
    assert not any(isinstance(e, ConditionApplied) for e in events)


def test_arrival_without_a_light_or_into_daylight_stays_quiet() -> None:
    dark = at(DOCKS, hero())
    assert [type(e) for e in _travel(dark, CAVE)] == [PartyMoved]
    assert party_surprise(dark, SurpriseKind.HOSTILE) is SurpriseKind.HOSTILE
    lit = at(CAVE, hero())
    run(lit, [LightLit(creature_id="hero", item="torch")])
    assert [type(e) for e in _travel(lit, DOCKS)] == [PartyMoved]
    assert lit.world.alerted is None and len(lit.world.lights) == 1


def test_a_dead_bearer_s_light_ends_when_the_party_moves_on() -> None:
    state = at(CAVE, hero(), hero("ally"))
    run(state, [LightLit(creature_id="ally", item="torch")])
    state.creatures["ally"].dead = True
    assert sight_darkness(state, Skill.PERCEPTION) == ()  # it still lies here, lit
    events = _travel(state, CRYPT)
    assert events[1:] == [LightEnded(creature_id="ally", reason="left behind")]
    assert state.world.lights == []
    assert sight_darkness(state, Skill.PERCEPTION) == (DARKNESS,)
