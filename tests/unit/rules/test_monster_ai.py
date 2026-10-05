"""Monster AI (M3.10): value-based targeting, area avoidance, range keeping, morale, legendary."""

from __future__ import annotations

import random

from aidm.models.commands import (
    AnyCommand,
    EndTurnCommand,
    FleeCommand,
    MonsterActionCommand,
    MoveCommand,
)
from aidm.models.conditions import Concentration
from aidm.models.encounter import EncounterStatus, Side, WithdrawReason
from aidm.models.state import Creature, GameState
from aidm.models.zones import Zone, ZoneEdge, ZoneMap
from aidm.rules.encounter import encounter_outcome
from aidm.rules.monster_ai import (
    choose_legendary_action,
    choose_monster_turn,
    is_broken,
    next_monster_command,
)
from aidm.rules.monster_legendary import legendary_ready
from aidm.rules.turns import end_turn
from aidm.session.reducer import apply
from tests.unit.rules.combat_fixtures import REGS, Placement, do, fight
from tests.unit.rules.encounter_fixtures import make_pc
from tests.unit.rules.monster_fixtures import srd_monster


def line_map() -> ZoneMap:
    """a - b - c, 30 ft hops, no high ground or cover anywhere."""
    zones = [Zone(id=z, name=z.upper()) for z in ("a", "b", "c")]
    return ZoneMap(
        zones=zones, edges=[ZoneEdge(a="a", b="b", feet=30), ZoneEdge(a="b", b="c", feet=30)]
    )


def hub_map() -> ZoneMap:
    """hub linked to left and right (30 ft each): two symmetric choices."""
    zones = [Zone(id=z, name=z.title()) for z in ("hub", "left", "right")]
    edges = [ZoneEdge(a="hub", b="left", feet=30), ZoneEdge(a="hub", b="right", feet=30)]
    return ZoneMap(zones=zones, edges=edges)


def with_xp(state: GameState) -> GameState:
    """Set each monster combatant's kill XP from its stat block, as start_encounter does."""
    assert state.encounter is not None
    for cid, combatant in state.encounter.combatants.items():
        index = state.creatures[cid].monster_index
        if index is not None:
            combatant.xp = REGS.monsters.get(index).xp
    return state


def plan(state: GameState, cid: str, seed: int = 1) -> list[AnyCommand]:
    return choose_monster_turn(state, cid, REGS, random.Random(seed))


def actions(commands: list[AnyCommand]) -> list[MonsterActionCommand]:
    return [c for c in commands if isinstance(c, MonsterActionCommand)]


def play_turn(state: GameState, cid: str, seed: int = 3) -> list[AnyCommand]:
    """Execute the AI's commands one at a time (re-planning after each) until the turn ends."""
    rng, done = random.Random(seed), list[AnyCommand]()
    for _ in range(20):
        command = next_monster_command(state, cid, REGS, rng)
        assert command is not None
        do(state, command, rng)
        done.append(command)
        if isinstance(command, EndTurnCommand):
            return done
    raise AssertionError("turn did not end")


def test_plan_is_deterministic_for_a_seed() -> None:
    placements: list[Placement] = [
        (srd_monster("scout", "scout-1"), Side.HOSTILE, "a"),
        (make_pc("pa"), Side.PARTY, "a"),
        (make_pc("pb", class_index="wizard"), Side.PARTY, "c"),
    ]
    first = plan(fight(placements, line_map()), "scout-1", seed=9)
    again = plan(fight(placements, line_map()), "scout-1", seed=9)
    assert first == again
    assert isinstance(first[-1], EndTurnCommand)


def test_targets_the_concentrating_caster_when_values_are_close() -> None:
    plain, caster = make_pc("pa"), make_pc("pb")
    plain.ac = caster.ac - 1  # the plain target is even slightly easier to hit
    caster.concentrating_on = Concentration(spell_id="bless")
    placements: list[Placement] = [
        (srd_monster("orc", "orc-1"), Side.HOSTILE, "a"),
        (plain, Side.PARTY, "a"),
        (caster, Side.PARTY, "a"),
    ]
    commands = plan(fight(placements, line_map()), "orc-1")
    assert actions(commands)[0].target_ids == ("pb",)


def test_kill_chance_beats_a_fresh_target() -> None:
    hurt, fresh = make_pc("pa"), make_pc("pb")
    hurt.hp = 2
    placements: list[Placement] = [
        (srd_monster("orc", "orc-1"), Side.HOSTILE, "a"),
        (fresh, Side.PARTY, "a"),
        (hurt, Side.PARTY, "a"),
    ]
    assert actions(plan(fight(placements, line_map()), "orc-1"))[0].target_ids == ("pa",)


def _breath_fight(with_ally: bool) -> GameState:
    pcs = [make_pc(f"p{i}") for i in range(4)]
    placements: list[Placement] = [
        (srd_monster("red-dragon-wyrmling", "drake"), Side.HOSTILE, "hub"),
        (pcs[0], Side.PARTY, "left"),
        (pcs[1], Side.PARTY, "left"),
        (pcs[2], Side.PARTY, "right"),
        (pcs[3], Side.PARTY, "right"),
    ]
    if with_ally:
        placements.append((srd_monster("orc", "orc-1"), Side.HOSTILE, "left"))
    return fight(placements, hub_map())


def test_breath_weapon_avoids_allies() -> None:
    commands = plan(_breath_fight(with_ally=True), "drake")
    assert commands[0] == MoveCommand(actor_id="drake", zone_id="right")
    assert actions(commands)[0].action == "fire-breath"


def test_breath_weapon_hits_the_crowd_without_allies() -> None:
    commands = plan(_breath_fight(with_ally=False), "drake")
    assert isinstance(commands[0], MoveCommand)
    assert actions(commands)[0].action == "fire-breath"


def test_ranged_monster_keeps_distance() -> None:
    placements: list[Placement] = [
        (srd_monster("scout", "scout-1"), Side.HOSTILE, "a"),
        (make_pc("pa"), Side.PARTY, "a"),
    ]
    state = fight(placements, line_map())
    played = play_turn(state, "scout-1")
    assert isinstance(played[0], MoveCommand)
    assert actions(played)[0].action == "multiattack"
    enc = state.encounter
    assert enc is not None and enc.combatant("scout-1").zone_id != "a"


def test_brute_closes_in() -> None:
    placements: list[Placement] = [
        (srd_monster("ogre", "ogre-1"), Side.HOSTILE, "a"),
        (make_pc("pa"), Side.PARTY, "b"),
    ]
    state = fight(placements, line_map())
    played = play_turn(state, "ogre-1")
    assert played[0] == MoveCommand(actor_id="ogre-1", zone_id="b")
    enc = state.encounter
    assert enc is not None and enc.combatant("ogre-1").zone_id == "b"


def _goblins(hp: int, goblin_zone: str) -> GameState:
    weak = srd_monster("goblin", "goblin-1").model_copy(update={"hp": hp})
    placements: list[Placement] = [
        (weak, Side.HOSTILE, goblin_zone),
        (srd_monster("goblin", "goblin-2"), Side.HOSTILE, "c"),
        (make_pc("pa"), Side.PARTY, "a"),
    ]
    return with_xp(fight(placements, line_map()))


def test_broken_monster_flees_when_no_enemy_is_near() -> None:
    state = _goblins(1, "c")
    assert is_broken(state, "goblin-1")
    assert plan(state, "goblin-1") == [
        FleeCommand(actor_id="goblin-1"),
        EndTurnCommand(actor_id="goblin-1"),
    ]
    play_turn(state, "goblin-1")
    enc = state.encounter
    assert enc is not None and enc.combatant("goblin-1").withdrawn is WithdrawReason.FLED


def test_broken_monster_moves_away_then_flees() -> None:
    state = _goblins(1, "a")
    played = play_turn(state, "goblin-1")
    assert isinstance(played[0], MoveCommand) and played[0].zone_id != "a"
    assert FleeCommand(actor_id="goblin-1") in played


def test_healthy_monster_does_not_flee() -> None:
    assert not is_broken(_goblins(5, "c"), "goblin-1")


def test_leaders_undead_and_lone_monsters_never_flee() -> None:
    orc = srd_monster("orc", "orc-1").model_copy(update={"hp": 1})
    skeleton = srd_monster("skeleton", "skeleton-1").model_copy(update={"hp": 1})
    placements: list[Placement] = [
        (orc, Side.HOSTILE, "c"),
        (skeleton, Side.HOSTILE, "c"),
        (srd_monster("goblin", "goblin-1"), Side.HOSTILE, "c"),
        (make_pc("pa"), Side.PARTY, "a"),
    ]
    state = with_xp(fight(placements, line_map()))
    assert not is_broken(state, "orc-1")  # the leader: worth the most XP on its side
    assert not is_broken(state, "skeleton-1")  # undead
    lone = srd_monster("goblin", "goblin-9").model_copy(update={"hp": 1})
    alone = fight([(lone, Side.HOSTILE, "c"), (make_pc("pa"), Side.PARTY, "a")], line_map())
    assert not is_broken(alone, "goblin-9")


def test_last_hostile_fleeing_ends_the_fight_in_victory() -> None:
    weak = srd_monster("goblin", "goblin-1").model_copy(update={"hp": 1})
    placements: list[Placement] = [
        (weak, Side.HOSTILE, "c"),
        (
            srd_monster("goblin", "goblin-2").model_copy(update={"hp": 0, "dead": True}),
            Side.HOSTILE,
            "c",
        ),
        (make_pc("pa"), Side.PARTY, "a"),
    ]
    state = fight(placements, line_map())
    play_turn(state, "goblin-1")
    assert encounter_outcome(state) is EncounterStatus.VICTORY


def test_caster_monster_casts_from_its_kit() -> None:
    placements: list[Placement] = [
        (srd_monster("mage", "mage-1"), Side.HOSTILE, "c"),
        (make_pc("pa"), Side.PARTY, "a"),
        (make_pc("pb"), Side.PARTY, "a"),
    ]
    used = actions(plan(fight(placements, line_map()), "mage-1"))
    assert used and used[0].action.startswith("spell:")


def _end(state: GameState, rng: random.Random) -> None:
    for event in end_turn(rng, state):
        apply(state, event)


def test_legendary_action_after_another_turn() -> None:
    placements: list[Placement] = [
        (make_pc("pa"), Side.PARTY, "a"),
        (srd_monster("unicorn", "unicorn-1"), Side.HOSTILE, "a"),
    ]
    state = fight(placements, line_map())
    _end(state, random.Random(1))
    assert legendary_ready(state) == ["unicorn-1"]
    pick = choose_legendary_action(state, "unicorn-1", REGS)
    assert pick is not None and pick.action == "hooves" and pick.target_ids == ("pa",)


def test_no_legendary_pick_without_targets_in_reach() -> None:
    far: list[Placement] = [
        (make_pc("pa"), Side.PARTY, "a"),
        (srd_monster("unicorn", "unicorn-1"), Side.HOSTILE, "c"),
    ]
    state = fight(far, line_map())
    _end(state, random.Random(1))
    assert choose_legendary_action(state, "unicorn-1", REGS) is None


def test_not_its_turn_plans_nothing() -> None:
    placements: list[Placement] = [
        (make_pc("pa"), Side.PARTY, "a"),
        (srd_monster("orc", "orc-1"), Side.HOSTILE, "a"),
    ]
    state = fight(placements, line_map())
    assert plan(state, "orc-1") == []


def test_plain_creature_without_stat_block_still_acts() -> None:
    from tests.unit.rules.combat_fixtures import monster

    blob: Creature = monster("blob")
    state = fight([(blob, Side.HOSTILE, "a"), (make_pc("pa"), Side.PARTY, "c")], line_map())
    played = play_turn(state, "blob")
    assert isinstance(played[-1], EndTurnCommand)


def test_flee_is_refused_next_to_an_enemy() -> None:
    import pytest

    from aidm.models.commands import RefusalCode
    from aidm.rules.command_checks import CommandRefused
    from aidm.rules.commands import execute_command

    state = _goblins(1, "a")
    with pytest.raises(CommandRefused) as refused:
        execute_command(state, FleeCommand(actor_id="goblin-1"), REGS, random.Random(1))
    assert refused.value.code is RefusalCode.ENGAGED
