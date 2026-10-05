"""Party-side AI (M3.10): the timeout safe default (SPEC 10) and the simple autoplay."""

from __future__ import annotations

import random

from aidm.models.character import InventoryItem
from aidm.models.commands import (
    AnyCommand,
    AttackCommand,
    CastCommand,
    DashCommand,
    DodgeCommand,
    EndTurnCommand,
    MoveCommand,
    UseItemCommand,
)
from aidm.models.encounter import Side
from aidm.models.state import Creature, GameState
from aidm.rules.party_ai import auto_pc_turn, next_pc_command, safe_default_turn
from tests.unit.rules.combat_fixtures import REGS, Placement, do, fight
from tests.unit.rules.encounter_fixtures import make_pc, small_map
from tests.unit.rules.monster_fixtures import srd_monster


def run_plan(state: GameState, commands: list[AnyCommand]) -> None:
    rng = random.Random(4)
    for command in commands:
        do(state, command, rng)


def play_pc(state: GameState, cid: str) -> list[AnyCommand]:
    rng, done = random.Random(2), list[AnyCommand]()
    for _ in range(20):
        command = next_pc_command(state, cid, REGS, rng)
        assert command is not None
        do(state, command, rng)
        done.append(command)
        if isinstance(command, EndTurnCommand):
            return done
    raise AssertionError("turn did not end")


def test_safe_default_dashes_toward_separated_allies() -> None:
    placements: list[Placement] = [
        (make_pc("pa"), Side.PARTY, "gate"),
        (make_pc("pb"), Side.PARTY, "wall"),
        (srd_monster("goblin", "goblin-1"), Side.HOSTILE, "yard"),
    ]
    state = fight(placements)
    commands = safe_default_turn(state, "pa")
    assert commands == [
        DashCommand(actor_id="pa"),
        MoveCommand(actor_id="pa", zone_id="wall"),
        EndTurnCommand(actor_id="pa"),
    ]
    run_plan(state, commands)
    assert state.encounter is not None and state.encounter.combatant("pa").zone_id == "wall"


def test_safe_default_dodges_next_to_allies() -> None:
    placements: list[Placement] = [
        (make_pc("pa"), Side.PARTY, "gate"),
        (make_pc("pb"), Side.PARTY, "gate"),
        (srd_monster("goblin", "goblin-1"), Side.HOSTILE, "yard"),
    ]
    state = fight(placements)
    commands = safe_default_turn(state, "pa")
    assert commands == [DodgeCommand(actor_id="pa"), EndTurnCommand(actor_id="pa")]
    run_plan(state, commands)


def test_safe_default_without_an_action_just_ends() -> None:
    down = make_pc("pa")
    down.hp = 0
    state = fight([(down, Side.PARTY, "gate"), (make_pc("pb"), Side.PARTY, "wall")])
    assert safe_default_turn(state, "pa") == [EndTurnCommand(actor_id="pa")]
    assert safe_default_turn(state, "pb") == []  # not its turn


def test_autoplay_finishes_the_wounded_enemy() -> None:
    hurt = srd_monster("goblin", "goblin-2").model_copy(update={"hp": 1})
    placements: list[Placement] = [
        (make_pc("pa"), Side.PARTY, "yard"),
        (srd_monster("goblin", "goblin-1"), Side.HOSTILE, "yard"),
        (hurt, Side.HOSTILE, "yard"),
    ]
    state = fight(placements)
    attacks = [c for c in play_pc(state, "pa") if isinstance(c, AttackCommand)]
    assert attacks[0].target_id == "goblin-2"


def _cleric(cid: str, prepared: list[str]) -> Creature:
    cleric = make_pc(cid, class_index="cleric")
    assert cleric.pc is not None
    cleric.pc.prepared = prepared
    return cleric


def _dying(cid: str) -> Creature:
    ally = make_pc(cid)
    ally.hp = 0
    return ally


def test_autoplay_heals_a_dying_ally_with_healing_word() -> None:
    placements: list[Placement] = [
        (_cleric("cl", ["healing-word"]), Side.PARTY, "gate"),
        (_dying("pb"), Side.PARTY, "yard"),
        (srd_monster("goblin", "goblin-1"), Side.HOSTILE, "wall"),
    ]
    state = fight(placements)
    commands = auto_pc_turn(state, "cl", REGS, random.Random(1))
    heal = next(c for c in commands if isinstance(c, CastCommand))
    assert heal.spell_id == "healing-word" and heal.target_ids == ("pb",)
    play_pc(state, "cl")
    assert state.creatures["pb"].hp > 0


def test_autoplay_hands_a_potion_to_a_dying_ally() -> None:
    fighter = make_pc("pa")
    assert fighter.pc is not None
    fighter.pc.inventory.append(InventoryItem(item="potion-of-healing", qty=1))
    placements: list[Placement] = [
        (fighter, Side.PARTY, "gate"),
        (_dying("pb"), Side.PARTY, "gate"),
        (srd_monster("goblin", "goblin-1"), Side.HOSTILE, "wall"),
    ]
    state = fight(placements)
    played = play_pc(state, "pa")
    assert UseItemCommand(actor_id="pa", item="potion-of-healing", target_id="pb") in played
    assert state.creatures["pb"].hp > 0


def test_autoplay_plan_is_deterministic_and_ends() -> None:
    placements: list[Placement] = [
        (make_pc("wz", class_index="wizard"), Side.PARTY, "gate"),
        (srd_monster("orc", "orc-1"), Side.HOSTILE, "wall"),
        (srd_monster("goblin", "goblin-1"), Side.HOSTILE, "yard"),
    ]
    first = auto_pc_turn(fight(placements, small_map()), "wz", REGS, random.Random(5))
    again = auto_pc_turn(fight(placements, small_map()), "wz", REGS, random.Random(5))
    assert first == again and isinstance(first[-1], EndTurnCommand)
