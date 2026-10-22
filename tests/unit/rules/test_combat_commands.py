"""Hide, help, dodge, use_item (BG3 bonus action), end turn, refusals and v1 regressions."""

from __future__ import annotations

import random

import pytest

from aidm.models.character import InventoryItem
from aidm.models.combat_events import AttackRolled
from aidm.models.commands import (
    AnyCommand,
    AttackCommand,
    CastCommand,
    DashCommand,
    DodgeCommand,
    EndTurnCommand,
    HelpCommand,
    HideCommand,
    JumpCommand,
    MoveCommand,
    RefusalCode,
    ShoveCommand,
    ThrowCommand,
    UseItemCommand,
    command_adapter,
)
from aidm.models.encounter import Side
from aidm.models.encounter_events import TurnEnded
from aidm.models.events import AnyEvent, InventoryChanged
from aidm.models.item_events import ItemUsed
from aidm.models.state import GameState
from aidm.rules.command_checks import CommandRefused
from aidm.rules.condition_timing import new_condition
from aidm.rules.items import use_item_events
from aidm.rules.turns import begin_turn
from aidm.session.reducer import apply, replay
from tests.unit.rules.combat_fixtures import REGS, ScriptedRng, do, economy, fight, monster
from tests.unit.rules.encounter_fixtures import make_pc

POTION = "potion-of-healing"


def _party() -> GameState:
    a, b = make_pc("a"), make_pc("b")
    assert a.pc is not None
    a.pc.inventory.append(InventoryItem(item=POTION, qty=2))
    return fight(
        [
            (a, Side.PARTY, "gate"),
            (b, Side.PARTY, "gate"),
            (monster("gob", wis=12), Side.HOSTILE, "gate"),
            (make_pc("c"), Side.PARTY, "yard"),
        ]
    )


def _refused(state: GameState, cmd: AnyCommand, code: RefusalCode) -> None:
    with pytest.raises(CommandRefused) as refused:
        do(state, cmd, ScriptedRng())
    assert refused.value.code is code
    assert refused.value.reason


def _names(state: GameState, cid: str) -> list[str]:
    return [c.name for c in state.creatures[cid].conditions]


def test_hide_beats_passive_perception() -> None:
    # Goblin passive Perception 10 + WIS 1 = 11; fighter Stealth +1 rolls 10 -> 11 (meets it).
    state = _party()
    do(state, HideCommand(actor_id="a"), ScriptedRng(10))
    assert _names(state, "a") == ["hidden"]
    _refused(state, HideCommand(actor_id="a"), RefusalCode.ALREADY_HIDDEN)


def test_failed_hide_spends_the_action_without_hiding() -> None:
    state = _party()
    do(state, HideCommand(actor_id="a"), ScriptedRng(9))
    assert _names(state, "a") == [] and not economy(state, "a").action


def test_help_gives_advantage_once() -> None:
    state = _party()
    do(state, HelpCommand(actor_id="a", target_id="b"), ScriptedRng())
    assert _names(state, "b") == ["helped"]
    do(state, EndTurnCommand(actor_id="a"), ScriptedRng())
    for event in begin_turn(random.Random(1), state):
        apply(state, event)
    events = do(state, AttackCommand(actor_id="b", target_id="gob"), ScriptedRng(2, 12, 3))
    assert [e for e in events if isinstance(e, AttackRolled)][0].roll.rolls == (2, 12)
    assert "helped" not in _names(state, "b")


def test_help_raises_a_downed_ally_to_one_hp() -> None:
    state = _party()
    state.creatures["b"].hp = 0
    state.creatures["b"].conditions.append(new_condition("unconscious", source_id="zero_hp"))
    do(state, HelpCommand(actor_id="a", target_id="b"), ScriptedRng())
    assert state.creatures["b"].hp == 1 and _names(state, "b") == []


def test_help_needs_an_ally_in_the_same_zone() -> None:
    state = _party()
    _refused(state, HelpCommand(actor_id="a", target_id="gob"), RefusalCode.INVALID_TARGET)
    _refused(state, HelpCommand(actor_id="a", target_id="c"), RefusalCode.OUT_OF_RANGE)


def test_dodge_applies_dodging() -> None:
    state = _party()
    do(state, DodgeCommand(actor_id="a"), ScriptedRng())
    assert _names(state, "a") == ["dodging"] and not economy(state, "a").action


def test_golden_potion_is_a_bonus_action() -> None:
    # SRD 5.1 Potion of Healing: 2d4 + 2 -> 2 + 3 + 2 = 7.
    state = _party()
    state.creatures["a"].hp = 3
    do(state, UseItemCommand(actor_id="a", item=POTION), ScriptedRng(2, 3))
    assert state.creatures["a"].hp == 10
    eco = economy(state, "a")
    assert (eco.action, eco.bonus_action) == (True, False)
    pc = state.creatures["a"].pc
    assert pc is not None and [r.qty for r in pc.inventory if r.item == POTION] == [1]


def test_potion_can_be_given_to_an_adjacent_ally_only() -> None:
    state = _party()
    state.creatures["b"].hp = 1
    state.creatures["c"].hp = 1
    _refused(
        state, UseItemCommand(actor_id="a", item=POTION, target_id="c"), RefusalCode.OUT_OF_RANGE
    )
    _refused(
        state,
        UseItemCommand(actor_id="a", item=POTION, target_id="gob"),
        RefusalCode.INVALID_TARGET,
    )
    do(state, UseItemCommand(actor_id="a", item=POTION, target_id="b"), ScriptedRng(4, 4))
    assert state.creatures["b"].hp == 11


def test_v1_potion_full_hp_drunk_and_wasted() -> None:
    # Owner rule (2026-10-22, M27.7) supersedes the SPEC 13 refusal: data never forbids an
    # action. The v1 failure was a potion claimed gone while kept: here it is gone AND said so.
    state = _party()
    hp = state.creatures["a"].hp
    events = do(state, UseItemCommand(actor_id="a", item=POTION), ScriptedRng())
    used = [e for e in events if isinstance(e, ItemUsed)]
    assert len(used) == 1 and used[0].no_effect and used[0].use_id == "drink"
    assert state.creatures["a"].hp == hp
    pc = state.creatures["a"].pc
    assert pc is not None and [r.qty for r in pc.inventory if r.item == POTION] == [1]
    eco = economy(state, "a")
    assert (eco.action, eco.bonus_action) == (True, False)  # the bonus action is spent
    out = use_item_events(ScriptedRng(), state, "a", POTION, None, REGS)
    assert [type(e) for e in out] == [ItemUsed, InventoryChanged]


def test_item_refusals() -> None:
    state = _party()
    _refused(state, UseItemCommand(actor_id="b", item=POTION), RefusalCode.NOT_YOUR_TURN)
    _refused(
        state,
        UseItemCommand(actor_id="a", item="potion-of-healing-greater"),
        RefusalCode.ITEM_NOT_OWNED,
    )
    _refused(state, UseItemCommand(actor_id="a", item="longsword"), RefusalCode.UNKNOWN_ITEM)


def test_end_turn_command_closes_the_turn() -> None:
    state = _party()
    events = do(state, EndTurnCommand(actor_id="a"), ScriptedRng())
    assert isinstance(events[-1], TurnEnded)
    _refused(state, EndTurnCommand(actor_id="a"), RefusalCode.NOT_YOUR_TURN)


def test_commands_parse_from_client_json() -> None:
    cmd = command_adapter.validate_json('{"type": "shove", "actor_id": "a", "target_id": "gob"}')
    assert cmd == ShoveCommand(actor_id="a", target_id="gob", mode="prone")


def test_v1_invalid_input_never_consumes_turn() -> None:
    state = _party()
    invalid: list[tuple[AnyCommand, RefusalCode]] = [
        (AttackCommand(actor_id="a", target_id="nobody"), RefusalCode.UNKNOWN_TARGET),
        (AttackCommand(actor_id="a", target_id="c"), RefusalCode.OUT_OF_RANGE),
        (AttackCommand(actor_id="a", target_id="gob", option="claw"), RefusalCode.UNKNOWN_OPTION),
        (AttackCommand(actor_id="a", target_id="a"), RefusalCode.INVALID_TARGET),
        (AttackCommand(actor_id="b", target_id="gob"), RefusalCode.NOT_YOUR_TURN),
        (MoveCommand(actor_id="a", zone_id="moon"), RefusalCode.UNKNOWN_ZONE),
        (MoveCommand(actor_id="a", zone_id="wall"), RefusalCode.NOT_ENOUGH_MOVEMENT),
        (JumpCommand(actor_id="a", zone_id="wall"), RefusalCode.NOT_ADJACENT),
        (ShoveCommand(actor_id="a", target_id="c"), RefusalCode.OUT_OF_RANGE),
        (DashCommand(actor_id="a", bonus_action=True), RefusalCode.NO_FEATURE),
        (ThrowCommand(actor_id="a", target_id="gob", item="greataxe"), RefusalCode.ITEM_NOT_OWNED),
        (
            UseItemCommand(actor_id="a", item="potion-of-healing-greater"),
            RefusalCode.ITEM_NOT_OWNED,
        ),
        (HelpCommand(actor_id="a", target_id="gob"), RefusalCode.INVALID_TARGET),
        (CastCommand(actor_id="a", spell_id="no-such-spell"), RefusalCode.UNKNOWN_SPELL),
    ]
    before = state.model_dump()
    for cmd, code in invalid:
        _refused(state, cmd, code)
    assert state.model_dump() == before
    eco = economy(state, "a")
    assert (eco.action, eco.bonus_action, eco.movement_left) == (True, True, 30)


def test_command_events_replay_to_the_same_state() -> None:
    state = _party()
    state.creatures["c"].hp = 2
    initial = state.model_copy(deep=True)
    log: list[AnyEvent] = []
    log += do(state, MoveCommand(actor_id="a", zone_id="yard"), ScriptedRng())
    log += do(state, UseItemCommand(actor_id="a", item=POTION, target_id="c"), ScriptedRng(1, 1))
    log += do(state, AttackCommand(actor_id="a", target_id="c", option="unarmed"), ScriptedRng(1))
    assert replay(initial, log).model_dump() == state.model_dump()
