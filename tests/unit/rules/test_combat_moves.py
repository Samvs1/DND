"""Movement commands: move, dash, disengage, jump (BG3 bonus action) and shove (bonus action)."""

from __future__ import annotations

import pytest

from aidm.models.character import Size
from aidm.models.combat_events import CombatantMoved
from aidm.models.commands import (
    AnyCommand,
    DashCommand,
    DisengageCommand,
    JumpCommand,
    MoveCommand,
    RefusalCode,
    ShoveCommand,
)
from aidm.models.encounter import Side
from aidm.models.state import GameState
from aidm.models.zones import Zone, ZoneEdge, ZoneMap
from aidm.rules.command_checks import CommandRefused
from aidm.rules.condition_timing import new_condition
from tests.unit.rules.combat_fixtures import ScriptedRng, do, economy, fight, monster
from tests.unit.rules.encounter_fixtures import make_pc


def _state(cls: str = "fighter", zmap: ZoneMap | None = None) -> GameState:
    return fight(
        [
            (make_pc("a", class_index=cls), Side.PARTY, "gate"),
            (monster("gob"), Side.HOSTILE, "gate"),
        ],
        zmap,
    )


def _zone(state: GameState, cid: str) -> str:
    assert state.encounter is not None
    return state.encounter.combatant(cid).zone_id


def _refused(state: GameState, cmd: AnyCommand, code: RefusalCode) -> None:
    with pytest.raises(CommandRefused) as refused:
        do(state, cmd, ScriptedRng())
    assert refused.value.code is code


def test_move_spends_path_feet() -> None:
    state = _state()
    events = do(state, MoveCommand(actor_id="a", zone_id="yard"), ScriptedRng())
    moved = [e for e in events if isinstance(e, CombatantMoved)][0]
    assert (moved.path, moved.feet) == (("gate", "yard"), 30)
    assert _zone(state, "a") == "yard"
    assert economy(state, "a").movement_left == 0


def test_move_beyond_movement_is_refused_then_dash_allows_it() -> None:
    state = _state()
    _refused(state, MoveCommand(actor_id="a", zone_id="wall"), RefusalCode.NOT_ENOUGH_MOVEMENT)
    do(state, DashCommand(actor_id="a"), ScriptedRng())
    assert economy(state, "a").movement_left == 60 and economy(state, "a").dashed
    do(state, MoveCommand(actor_id="a", zone_id="wall"), ScriptedRng())
    assert economy(state, "a").movement_left == 15
    assert _zone(state, "a") == "wall"


def test_bonus_action_dash_needs_a_feature() -> None:
    state = _state()
    _refused(state, DashCommand(actor_id="a", bonus_action=True), RefusalCode.NO_FEATURE)
    rogue = _state("rogue")
    pc = rogue.creatures["a"].pc
    assert pc is not None
    pc.level = 2
    pc.features.append("cunning-action")
    do(rogue, DashCommand(actor_id="a", bonus_action=True), ScriptedRng())
    assert economy(rogue, "a").action and not economy(rogue, "a").bonus_action


def test_disengage_sets_flag_and_spends_action() -> None:
    state = _state()
    do(state, DisengageCommand(actor_id="a"), ScriptedRng())
    assert economy(state, "a").disengaged and not economy(state, "a").action


def test_prone_creature_stands_for_half_speed() -> None:
    state = _state()
    state.creatures["a"].conditions.append(new_condition("prone"))
    do(state, MoveCommand(actor_id="a", zone_id="gate"), ScriptedRng())
    assert state.creatures["a"].conditions == []
    assert economy(state, "a").movement_left == 15


def test_jump_is_a_bonus_action_to_an_adjacent_zone_ignoring_difficult_terrain() -> None:
    zmap = ZoneMap(
        zones=[Zone(id="gate", name="Gate"), Zone(id="bog", name="Bog", difficult=True)],
        edges=[ZoneEdge(a="gate", b="bog", feet=30)],
    )
    state = _state(zmap=zmap)
    _refused(state, MoveCommand(actor_id="a", zone_id="bog"), RefusalCode.NOT_ENOUGH_MOVEMENT)
    do(state, JumpCommand(actor_id="a", zone_id="bog"), ScriptedRng())
    assert _zone(state, "a") == "bog"
    eco = economy(state, "a")
    assert (eco.bonus_action, eco.action, eco.movement_left) == (False, True, 0)


def test_jump_to_a_far_zone_is_refused() -> None:
    _refused(_state(), JumpCommand(actor_id="a", zone_id="wall"), RefusalCode.NOT_ADJACENT)


def test_golden_shove_prone() -> None:
    # SRD 5.1 Shoving: target (Athletics +0) rolls 5; fighter Athletics +3 (STR) rolls 6 -> 9.
    state = _state()
    do(state, ShoveCommand(actor_id="a", target_id="gob"), ScriptedRng(5, 6))
    assert [c.name for c in state.creatures["gob"].conditions] == ["prone"]
    assert not economy(state, "a").bonus_action and economy(state, "a").action


def test_shove_push_moves_target_and_tie_fails() -> None:
    state = _state()
    cmd = ShoveCommand(actor_id="a", target_id="gob", mode="push", to_zone="yard")
    do(state, cmd, ScriptedRng(10, 7))  # 10 vs 7 + 3: a tie keeps things as they are
    assert _zone(state, "gob") == "gate"
    state = _state()
    do(state, cmd, ScriptedRng(10, 8))
    assert _zone(state, "gob") == "yard"


def test_shove_refusals() -> None:
    state = _state()
    _refused(
        state,
        ShoveCommand(actor_id="a", target_id="gob", mode="push", to_zone="wall"),
        RefusalCode.NOT_ADJACENT,
    )
    state.creatures["gob"].size = Size.HUGE
    _refused(state, ShoveCommand(actor_id="a", target_id="gob"), RefusalCode.TOO_LARGE)
    assert economy(state, "a").bonus_action
