"""Surfaces lite (M3.7, SPEC 7.2): data, interactions, enter and turn-start triggers, durations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aidm.data.surface_defs import load_surface_data, surface_data
from aidm.models.combat_events import ZoneSurfaceAdded, ZoneSurfaceRemoved
from aidm.models.commands import EndTurnCommand, JumpCommand, MoveCommand, RefusalCode, ShoveCommand
from aidm.models.encounter import Side
from aidm.models.events import AnyEvent, CheckResolved, DamageTaken
from aidm.models.state import GameState
from aidm.models.zones import ZoneSurface
from aidm.rules.command_checks import CommandRefused
from aidm.rules.concentration import end_concentration
from aidm.rules.surfaces import place_surface_events, zone_damage_events
from aidm.rules.turns import begin_turn
from aidm.rules.zones import zone_path
from aidm.session.reducer import apply
from tests.unit.rules.combat_fixtures import ScriptedRng, do, fight, monster
from tests.unit.rules.encounter_fixtures import make_pc
from tests.unit.rules.spell_fixtures import battle, cast, caster, conditions_of, of


def _state() -> GameState:
    """p (party) acts first at the gate; gob and gob2 (hostile, 30 HP, all 10s) in the yard."""
    return fight(
        [
            (make_pc("p"), Side.PARTY, "gate"),
            (monster("gob", hp=30), Side.HOSTILE, "yard"),
            (monster("gob2", hp=30), Side.HOSTILE, "yard"),
        ]
    )


def _run(state: GameState, events: list[AnyEvent]) -> list[AnyEvent]:
    for event in events:
        apply(state, event)
    return events


def _lay(state: GameState, zone: str, kind: str, **extra: object) -> None:
    surface = ZoneSurface.model_validate({"kind": kind, **extra})
    apply(state, ZoneSurfaceAdded(zone_id=zone, surface=surface))


def _kinds(state: GameState, zone: str) -> list[str]:
    assert state.encounter is not None
    return [s.kind for s in state.encounter.zone_map.zone(zone).surfaces]


def _hp(state: GameState, *ids: str) -> tuple[int, ...]:
    return tuple(state.creatures[cid].hp for cid in ids)


def _next_turn(state: GameState, rng: ScriptedRng) -> list[AnyEvent]:
    """End the open turn, then open the next one (its turn-start events are returned)."""
    enc = state.encounter
    assert enc is not None
    active = enc.active_id()
    assert active is not None
    do(state, EndTurnCommand(actor_id=active), rng)
    return _run(state, begin_turn(rng, state))


def test_surface_data_loads_and_references_are_checked(tmp_path: Path) -> None:
    kinds = {s.index for s in surface_data().surfaces}
    assert {"fire", "oil", "grease", "water", "ice", "poison-cloud", "steam"} <= kinds
    raw = json.loads(json.dumps(surface_data().model_dump(mode="json")))
    raw["interactions"].append({"surfaces": ["fire", "lava"], "consumes": ["fire"]})
    bad = tmp_path / "surfaces.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown surfaces"):
        load_surface_data(bad)
    raw["interactions"].pop()
    raw["surfaces"][0]["harms"] = [{"condition": "on-fire"}]
    bad.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown condition"):
        load_surface_data(bad)


def test_fire_placed_on_oil_burns_with_a_burst() -> None:
    # fire + oil: the oil is consumed, the fire stays, everyone in the zone saves DEX 12 vs 2d6.
    state = _state()
    _lay(state, "yard", "oil")
    rng = ScriptedRng(5, 3, 4, 15)  # gob fails (5), 2d6 = 7, gob2 succeeds (15): half = 3
    events = _run(state, place_surface_events(rng, state, "yard", ZoneSurface(kind="fire")))
    assert _kinds(state, "yard") == ["fire"]
    assert [c.result.dc for c in of(events, CheckResolved)] == [12, 12]
    assert _hp(state, "gob", "gob2") == (23, 27)


def test_fire_damage_into_oil_ignites_it() -> None:
    state = _state()
    _lay(state, "yard", "oil")
    rng = ScriptedRng(20, 1, 1, 20)  # both save, 2d6 = 2: 1 each
    events = _run(state, zone_damage_events(rng, state, "yard", "fire"))
    assert _kinds(state, "yard") == ["fire"]
    assert of(events, ZoneSurfaceRemoved)[0].kind == "oil"
    assert _hp(state, "gob", "gob2") == (29, 29)
    assert zone_damage_events(ScriptedRng(), state, "yard", "fire") == []


def test_fire_bolt_on_a_creature_in_grease_ignites_the_zone() -> None:
    # The spell hook: damage dealt to a creature hits its zone (once per zone and type).
    state = battle(caster("w", "wizard", cantrips=["fire-bolt"]), ("gob", "yard"))
    _lay(state, "yard", "grease")
    cast(state, "w", "fire-bolt", ScriptedRng(15, 4, 5, 2, 2), targets=["gob"])
    assert _kinds(state, "yard") == ["fire"]
    assert state.creatures["gob"].hp == 30 - 4 - 4  # 1d10 = 4, burst 2d6 = 4 (failed DEX 5)


def test_water_and_lightning_shocks_everyone_in_it() -> None:
    state = _state()
    _lay(state, "yard", "water")
    rng = ScriptedRng(4, 3, 20)  # gob fails CON 12 (4), 1d4 = 3; gob2 succeeds
    _run(state, zone_damage_events(rng, state, "yard", "lightning"))
    assert _kinds(state, "yard") == ["water"]
    assert conditions_of(state, "gob") == ["shocked"] and conditions_of(state, "gob2") == []
    assert _hp(state, "gob", "gob2") == (27, 30)


def test_water_and_cold_freezes_into_ice() -> None:
    state = _state()
    _lay(state, "yard", "water")
    _run(state, zone_damage_events(ScriptedRng(), state, "yard", "cold"))
    assert _kinds(state, "yard") == ["ice"]


@pytest.mark.parametrize("cleared", ["water", "ice"])
def test_fire_clears_water_and_ice_into_steam(cleared: str) -> None:
    state = _state()
    _lay(state, "yard", cleared)
    _run(state, place_surface_events(ScriptedRng(), state, "yard", ZoneSurface(kind="fire")))
    assert _kinds(state, "yard") == ["steam"]
    state = _state()
    _lay(state, "yard", cleared)
    _run(state, zone_damage_events(ScriptedRng(), state, "yard", "fire"))
    assert _kinds(state, "yard") == ["steam"]


def test_same_kind_replaces_and_unknown_kind_is_inert() -> None:
    state = _state()
    _lay(state, "yard", "fire", rounds_left=1)
    _run(state, place_surface_events(ScriptedRng(), state, "yard", ZoneSurface(kind="fire")))
    assert state.encounter is not None
    assert state.encounter.zone_map.zone("yard").surfaces == [ZoneSurface(kind="fire")]
    _run(state, place_surface_events(ScriptedRng(), state, "gate", ZoneSurface(kind="glitter")))
    assert _kinds(state, "gate") == ["glitter"]


def test_entering_fire_burns_and_grease_is_difficult_terrain() -> None:
    state = _state()
    _lay(state, "yard", "fire")
    do(state, MoveCommand(actor_id="p", zone_id="yard"), ScriptedRng(3))
    assert state.creatures["p"].hp == state.creatures["p"].max_hp - 3
    state = _state()
    _lay(state, "yard", "grease")
    assert state.encounter is not None
    assert zone_path(state.encounter.zone_map, "gate", "yard").feet == 60
    with pytest.raises(CommandRefused) as refused:
        do(state, MoveCommand(actor_id="p", zone_id="yard"), ScriptedRng())
    assert refused.value.code is RefusalCode.NOT_ENOUGH_MOVEMENT


def test_jumping_into_ice_saves_or_falls_prone() -> None:
    state = _state()
    _lay(state, "yard", "ice")
    events = do(state, JumpCommand(actor_id="p", zone_id="yard"), ScriptedRng(2))
    assert of(events, CheckResolved)[0].result.dc == 10
    assert conditions_of(state, "p") == ["prone"]


def test_being_shoved_into_fire_burns() -> None:
    state = _state()
    state.creatures["p"].conditions.clear()
    _lay(state, "wall", "fire")
    apply(state, ZoneSurfaceAdded(zone_id="gate", surface=ZoneSurface(kind="water")))
    do(state, MoveCommand(actor_id="p", zone_id="yard"), ScriptedRng())
    shove = ShoveCommand(actor_id="p", target_id="gob", mode="push", to_zone="wall")
    do(state, shove, ScriptedRng(1, 20, 4))  # gob resists with 1, p rolls 20, fire 1d4 = 4
    assert state.creatures["gob"].hp == 26


def test_turn_start_in_a_poison_cloud() -> None:
    state = _state()
    _lay(state, "yard", "poison-cloud")
    events = _next_turn(state, ScriptedRng(5, 6))  # gob starts its turn: CON 5 fails, 1d6 = 6
    assert of(events, DamageTaken)[0].total == 6
    assert conditions_of(state, "gob") == ["poisoned"]


def test_surface_durations_tick_per_round_and_expire() -> None:
    state = _state()
    _lay(state, "gate", "steam", rounds_left=2)
    rng = ScriptedRng()
    for _ in range(2):
        _next_turn(state, rng)
    assert _kinds(state, "gate") == ["steam"]
    _next_turn(state, rng)  # round 2 begins: 2 -> 1
    assert state.encounter is not None
    assert state.encounter.zone_map.zone("gate").surfaces[0].rounds_left == 1
    for _ in range(3):
        _next_turn(state, rng)  # round 3 begins: expired
    assert _kinds(state, "gate") == []


def test_fog_blinds_while_inside_only() -> None:
    state = _state()
    events = place_surface_events(ScriptedRng(), state, "yard", ZoneSurface(kind="fog"))
    _run(state, events)
    assert conditions_of(state, "gob") == ["blinded"] and conditions_of(state, "gob2") == [
        "blinded"
    ]
    do(state, MoveCommand(actor_id="p", zone_id="yard"), ScriptedRng())
    assert conditions_of(state, "p") == ["blinded"]
    _next_turn(state, ScriptedRng())  # gob's turn start: ticks off, then re-applied inside
    assert conditions_of(state, "gob") == ["blinded"]
    do(state, MoveCommand(actor_id="gob", zone_id="gate"), ScriptedRng())
    assert conditions_of(state, "gob") == []
    _run(state, zone_damage_events(ScriptedRng(), state, "yard", "fire"))
    assert conditions_of(state, "p") == ["blinded"]


def test_concentration_end_removes_its_surfaces_and_their_conditions() -> None:
    state = battle(caster("w", "wizard", spells=["web"], slots={2: 1}), ("gob", "yard"))
    cast(state, "w", "web", ScriptedRng(3), zone="yard")
    assert conditions_of(state, "gob") == ["restrained"]
    _run(state, end_concentration(state, "w", "test"))
    assert _kinds(state, "yard") == [] and conditions_of(state, "gob") == []


def test_burning_web_frees_the_restrained() -> None:
    state = _state()
    _run(state, place_surface_events(ScriptedRng(1, 20), state, "yard", ZoneSurface(kind="web")))
    assert conditions_of(state, "gob") == ["restrained"]
    _run(state, zone_damage_events(ScriptedRng(2, 2), state, "yard", "fire"))
    assert _kinds(state, "yard") == [] and conditions_of(state, "gob") == []
    assert _hp(state, "gob", "gob2") == (26, 26)


def test_aura_follows_its_source_and_spares_its_side() -> None:
    state = fight(
        [
            (make_pc("p"), Side.PARTY, "gate"),
            (monster("gob", hp=30), Side.HOSTILE, "yard"),
            (make_pc("ally"), Side.PARTY, "yard"),
        ]
    )
    _lay(state, "gate", "spirit-guardians", source_id="p", dc=13, upcast=1)
    do(state, MoveCommand(actor_id="p", zone_id="yard"), ScriptedRng())
    assert _kinds(state, "gate") == [] and _kinds(state, "yard") == ["spirit-guardians"]
    events = _next_turn(state, ScriptedRng(4, 1, 1, 1, 1))  # gob: WIS 4 fails; 4d8 = 4
    assert of(events, CheckResolved)[0].result.dc == 13
    assert state.creatures["gob"].hp == 26
    hp = state.creatures["ally"].hp
    assert of(_next_turn(state, ScriptedRng()), CheckResolved) == []  # the ally's turn
    assert state.creatures["ally"].hp == hp


def test_area_spell_into_an_empty_oil_zone_ignites_it() -> None:
    wiz = caster("w", "wizard", spells=["fireball"], level=5, slots={3: 1})
    state = battle(wiz, ("gob", "yard"))
    _lay(state, "wall", "oil")
    events = cast(state, "w", "fireball", ScriptedRng(*[1] * 8), zone="wall")
    assert _kinds(state, "wall") == ["fire"]
    assert of(events, DamageTaken) == []
