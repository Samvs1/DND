"""Turn flow and the action economy."""

from __future__ import annotations

import random

import pytest

from aidm.models.encounter import SurpriseKind, TurnEconomy, WithdrawReason
from aidm.models.encounter_events import TurnStarted
from aidm.models.events import (
    AnyEvent,
    ConditionApplied,
    CreatureDied,
    DeathSaveRolled,
    HpChanged,
)
from aidm.models.state import GameState
from aidm.rules.condition_timing import new_condition
from aidm.rules.damage import UNCONSCIOUS, ZERO_HP_SOURCE
from aidm.rules.encounter import EncounterRefusal, EncounterRefused, withdraw_combatant
from aidm.rules.turns import (
    EconomyRefusal,
    EconomyRefused,
    begin_turn,
    end_turn,
    fresh_economy,
    next_turn,
    spend_action,
    spend_bonus_action,
    spend_economy,
    spend_movement,
    spend_reaction,
)
from tests.unit.rules.encounter_fixtures import make_pc, run, started


def _order(state: GameState) -> list[str]:
    assert state.encounter is not None
    return [e.creature_id for e in state.encounter.initiative]


def _cycle(state: GameState, rng: random.Random, turns: int) -> list[tuple[str, int]]:
    seen: list[tuple[str, int]] = []
    for _ in range(turns):
        run(state, begin_turn(rng, state))
        assert state.encounter is not None
        seen.append((str(state.encounter.active_id()), state.encounter.round))
        run(state, end_turn(rng, state))
    return seen


def test_turns_follow_initiative_and_rounds_wrap() -> None:
    state, rng = started(1, [make_pc("ana"), make_pc("bo")], ["goblin"])
    order = _order(state)
    seen = _cycle(state, rng, 7)
    assert [cid for cid, _ in seen] == (order * 3)[:7]
    assert [r for _, r in seen] == [1, 1, 1, 2, 2, 2, 3]


def test_dead_and_withdrawn_creatures_are_skipped() -> None:
    state, rng = started(2, [make_pc("ana"), make_pc("bo")], ["goblin", "goblin"])
    run(state, [HpChanged(creature_id="goblin-1", delta=-7, new_hp=0)])
    run(state, [CreatureDied(creature_id="goblin-1")])
    run(state, withdraw_combatant(state, "goblin-2", WithdrawReason.FLED))
    seen = _cycle(state, rng, 4)
    assert {cid for cid, _ in seen} == {"ana", "bo"}


def test_first_turn_of_a_surprised_creature_is_empty_then_normal() -> None:
    state, rng = started(3, [make_pc("ana")], ["goblin"], SurpriseKind.PARTY)
    events: list[AnyEvent] = []
    for _ in range(4):
        opened = begin_turn(rng, state)
        run(state, opened)
        events.extend(opened)
        run(state, end_turn(rng, state))
    starts = [e for e in events if isinstance(e, TurnStarted) and e.creature_id == "ana"]
    assert starts[0].economy == TurnEconomy(reaction=False)  # no action, bonus, move, reaction
    assert starts[1].economy == TurnEconomy(
        action=True, bonus_action=True, movement_left=30, reaction=True
    )
    assert state.creatures["ana"].conditions == []


def test_dying_pc_rolls_a_death_save_at_turn_start() -> None:
    state, rng = started(4, [make_pc("ana"), make_pc("bo")], ["goblin"])
    unconscious = new_condition(UNCONSCIOUS, source_id=ZERO_HP_SOURCE)
    run(state, [HpChanged(creature_id="ana", delta=-12, new_hp=0)])
    run(state, [ConditionApplied(creature_id="ana", condition=unconscious)])
    for _ in range(3):
        opened = begin_turn(rng, state)
        start = opened[0]
        assert isinstance(start, TurnStarted)
        rolled = [e for e in opened if isinstance(e, DeathSaveRolled)]
        if start.creature_id == "ana":
            assert len(rolled) == 1 and rolled[0].roll.natural != 20
            assert start.economy == TurnEconomy(reaction=False)
        else:
            assert rolled == []
        run(state, opened)
        run(state, end_turn(rng, state))
    assert state.creatures["ana"].death_save_successes + state.creatures["ana"].death_save_failures


class _Nat20:
    def randint(self, a: int, b: int) -> int:
        return b


def test_nat20_death_save_wakes_with_a_full_economy() -> None:
    state, _ = started(5, [make_pc("ana", dex=20)], ["zombie"])
    run(state, [HpChanged(creature_id="ana", delta=-12, new_hp=0)])
    zero = new_condition(UNCONSCIOUS, source_id=ZERO_HP_SOURCE)
    run(state, [ConditionApplied(creature_id="ana", condition=zero)])
    assert state.encounter is not None
    assert state.encounter.initiative[0].creature_id == "ana"  # DEX 20 vs zombie DEX 6
    opened = begin_turn(_Nat20(), state)
    start = opened[0]
    assert isinstance(start, TurnStarted)
    assert start.economy.action and start.economy.movement_left == 30
    run(state, opened)
    assert state.creatures["ana"].hp == 1


def test_begin_and_end_refusals() -> None:
    state, rng = started(6, [make_pc("ana")], ["goblin"])
    with pytest.raises(EncounterRefused) as err:
        end_turn(rng, state)
    assert err.value.reason is EncounterRefusal.NO_OPEN_TURN
    run(state, begin_turn(rng, state))
    with pytest.raises(EncounterRefused) as err:
        begin_turn(rng, state)
    assert err.value.reason is EncounterRefusal.TURN_ALREADY_OPEN


def test_nobody_left_to_act() -> None:
    state, _ = started(7, [make_pc("ana")], ["goblin"])
    for cid in ("ana", "goblin-1"):
        run(state, [CreatureDied(creature_id=cid)])
    assert next_turn(state) is None
    with pytest.raises(EncounterRefused) as err:
        begin_turn(random.Random(1), state)
    assert err.value.reason is EncounterRefusal.NO_ONE_CAN_ACT


def _open_turn_of(state: GameState, rng: random.Random, cid: str) -> None:
    for _ in range(10):
        run(state, begin_turn(rng, state))
        assert state.encounter is not None
        if state.encounter.active_id() == cid:
            return
        run(state, end_turn(rng, state))
    raise AssertionError(f"{cid} never got a turn")


def test_spending_the_economy() -> None:
    state, rng = started(8, [make_pc("ana"), make_pc("bo")], ["goblin"])
    _open_turn_of(state, rng, "ana")
    run(state, spend_action(state, "ana"))
    run(state, spend_bonus_action(state, "ana"))
    run(state, spend_movement(state, "ana", 20))
    assert state.encounter is not None
    eco = state.encounter.combatant("ana").economy
    assert (eco.action, eco.bonus_action, eco.movement_left, eco.reaction) == (
        False,
        False,
        10,
        True,
    )
    run(state, spend_reaction(state, "bo"))  # reactions work off-turn
    assert not state.encounter.combatant("bo").economy.reaction


@pytest.mark.parametrize(
    ("spend", "reason"),
    [
        (lambda s: spend_action(s, "bo"), EconomyRefusal.NOT_YOUR_TURN),
        (lambda s: spend_movement(s, "ana", 35), EconomyRefusal.NOT_ENOUGH_MOVEMENT),
        (lambda s: spend_movement(s, "ana", 0), EconomyRefusal.INVALID_AMOUNT),
        (lambda s: spend_economy(s, "ana"), EconomyRefusal.INVALID_AMOUNT),
        (lambda s: spend_action(s, "nobody"), EconomyRefusal.NOT_IN_ENCOUNTER),
    ],
)
def test_invalid_spends_never_consume(spend: object, reason: EconomyRefusal) -> None:
    state, rng = started(9, [make_pc("ana"), make_pc("bo")], ["goblin"])
    _open_turn_of(state, rng, "ana")
    before = state.model_dump()
    with pytest.raises(EconomyRefused) as err:
        assert callable(spend)
        spend(state)
    assert err.value.reason is reason
    assert state.model_dump() == before


def test_used_resources_and_conditions_refuse() -> None:
    state, rng = started(10, [make_pc("ana"), make_pc("bo")], ["goblin"])
    _open_turn_of(state, rng, "ana")
    run(state, spend_action(state, "ana"))
    with pytest.raises(EconomyRefused) as err:
        spend_action(state, "ana")
    assert err.value.reason is EconomyRefusal.ACTION_USED
    run(state, spend_reaction(state, "bo"))
    with pytest.raises(EconomyRefused) as err:
        spend_reaction(state, "bo")
    assert err.value.reason is EconomyRefusal.REACTION_USED
    run(state, [ConditionApplied(creature_id="ana", condition=new_condition("grappled"))])
    with pytest.raises(EconomyRefused) as err:
        spend_movement(state, "ana", 5)
    assert err.value.reason is EconomyRefusal.CANNOT_MOVE
    run(state, [ConditionApplied(creature_id="ana", condition=new_condition("stunned"))])
    with pytest.raises(EconomyRefused) as err:
        spend_bonus_action(state, "ana")
    assert err.value.reason is EconomyRefusal.CANNOT_ACT


def test_fresh_economy_follows_conditions() -> None:
    pc = make_pc("ana")
    assert fresh_economy(pc) == TurnEconomy(
        action=True, bonus_action=True, movement_left=30, reaction=True
    )
    pc.conditions.append(new_condition("grappled"))
    assert fresh_economy(pc).movement_left == 0
    pc.conditions.append(new_condition("paralyzed"))
    assert fresh_economy(pc) == TurnEconomy(reaction=False)
