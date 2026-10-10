"""M19.4 (owner playtest 2026-10-10): typed moves in a fight become the Move list's commands."""

from aidm.dm.combat_intent import combat_move
from aidm.models.commands import DashCommand, MoveCommand
from aidm.models.state import GameState
from aidm.rules.zones import zone_neighbors
from tests.ai.tool_fixtures import apply_result, party_state, run_tool


def _fight() -> GameState:
    state = party_state()
    apply_result(state, run_tool(state, "start_encounter", monster_ids=["goblin"]))
    assert state.encounter is not None
    return state


def test_a_named_zone_is_a_move() -> None:
    state = _fight()
    enc = state.encounter
    assert enc is not None
    here = enc.combatants["fighter"].zone_id
    near, _feet = zone_neighbors(enc.zone_map, here)[0]
    name = next(z.name for z in enc.zone_map.zones if z.id == near)
    for text in (f"I move to the {name}.", f"run to {name.lower()}", f"I head towards the {name}"):
        assert combat_move(state, "fighter", text) == [
            MoveCommand(actor_id="fighter", zone_id=near)
        ]


def test_a_creature_name_moves_to_its_zone() -> None:
    state = _fight()
    enc = state.encounter
    assert enc is not None
    goblin = next(
        c for c in enc.combatants if c != "fighter" and state.creatures[c].kind.value == "monster"
    )
    zone = enc.combatants[goblin].zone_id
    name = state.creatures[goblin].name
    assert combat_move(state, "fighter", f"I charge at the {name}") == [
        MoveCommand(actor_id="fighter", zone_id=zone)
    ]


def test_dash_first_only_when_the_walk_needs_it() -> None:
    state = _fight()
    enc = state.encounter
    assert enc is not None
    me = enc.combatants["fighter"]
    me.economy = me.economy.model_copy(update={"movement_left": 5})
    near, _feet = zone_neighbors(enc.zone_map, me.zone_id)[0]
    name = next(z.name for z in enc.zone_map.zones if z.id == near)
    moves = combat_move(state, "fighter", f"I dash to the {name}")
    assert moves == [DashCommand(actor_id="fighter"), MoveCommand(actor_id="fighter", zone_id=near)]
    assert combat_move(state, "fighter", f"I walk to the {name}") == [
        MoveCommand(actor_id="fighter", zone_id=near)
    ]


def test_other_sentences_and_own_zone_are_not_moves() -> None:
    state = _fight()
    enc = state.encounter
    assert enc is not None
    here = next(z.name for z in enc.zone_map.zones if z.id == enc.combatants["fighter"].zone_id)
    assert combat_move(state, "fighter", "I swing my sword at the goblin") is None
    assert combat_move(state, "fighter", f"I move to the {here}") is None
    assert combat_move(party_state(), "fighter", "I move to the forest") is None  # no fight
