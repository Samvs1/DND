"""Combat AI properties (M3.10): across random fights the planner never issues a refused command.

Every random state: a generated zone map, 1-3 encounter-ready monsters and 1-3 PCs of random
classes in random zones, random HP (PCs may be dying), some creatures prone, a random creature's
turn open. The AI for that creature (monster AI or party autoplay) then plays the whole turn one
command at a time; `execute_command` must accept every command and the turn must end.
"""

from __future__ import annotations

import random

from hypothesis import given, settings
from hypothesis import strategies as st

from aidm.data.encounter_monsters import encounter_monsters
from aidm.data.zone_templates import zone_templates
from aidm.models.commands import AnyCommand, EndTurnCommand
from aidm.models.encounter import Side
from aidm.models.state import ActiveCondition, Creature, GameState
from aidm.rules.commands import execute_command
from aidm.rules.monster_ai import choose_monster_turn
from aidm.rules.zone_gen import generate_zone_map
from aidm.session.combat_runner import ai_command
from aidm.session.reducer import apply
from tests.unit.rules.combat_fixtures import REGS, Placement, fight
from tests.unit.rules.encounter_fixtures import make_pc
from tests.unit.rules.monster_fixtures import srd_monster

CLASSES = ("fighter", "rogue", "wizard", "cleric", "ranger", "warlock")
MONSTERS = sorted(m.index for m in encounter_monsters().all())
TERRAINS = sorted(t.index for t in zone_templates().all())


def _wounded(rng: random.Random, creature: Creature, can_drop: bool) -> Creature:
    low = 0 if can_drop else 1
    hp = rng.randint(low, creature.max_hp)
    conditions = [ActiveCondition(name="prone")] if rng.random() < 0.2 and hp > 0 else []
    return creature.model_copy(update={"hp": hp, "conditions": conditions})


def random_fight(seed: int) -> tuple[GameState, str]:
    rng = random.Random(seed)
    zone_map = generate_zone_map(rng, rng.sample(TERRAINS, 2), zone_templates())
    zones = [z.id for z in zone_map.zones]
    placements: list[Placement] = []
    for i in range(rng.randint(1, 3)):
        monster = srd_monster(rng.choice(MONSTERS), f"m{i}")
        placements.append((_wounded(rng, monster, False), Side.HOSTILE, rng.choice(zones)))
    for i in range(rng.randint(1, 3)):
        pc = make_pc(f"p{i}", class_index=rng.choice(CLASSES))
        placements.append((_wounded(rng, pc, True), Side.PARTY, rng.choice(zones)))
    rng.shuffle(placements)
    return fight(placements, zone_map), placements[0][0].id


def play_turn(state: GameState, cid: str, seed: int) -> list[AnyCommand]:
    rng = random.Random(seed)
    done: list[AnyCommand] = []
    for _ in range(20):
        command = ai_command(state, cid, REGS, rng)
        assert command is not None
        for event in execute_command(state, command, REGS, rng):  # CommandRefused fails here
            apply(state, event)
        done.append(command)
        if isinstance(command, EndTurnCommand):
            return done
    raise AssertionError(f"turn of {cid} did not end: {done}")


@settings(max_examples=60, deadline=None)
@given(st.integers(min_value=0, max_value=1_000_000))
def test_ai_never_issues_a_refused_command(seed: int) -> None:
    state, active = random_fight(seed)
    played = play_turn(state, active, seed)
    assert isinstance(played[-1], EndTurnCommand)


@settings(max_examples=25, deadline=None)
@given(st.integers(min_value=0, max_value=1_000_000))
def test_first_planned_command_is_valid_and_plan_is_deterministic(seed: int) -> None:
    state, active = random_fight(seed)
    if state.creatures[active].pc is not None:
        return
    plan = choose_monster_turn(state, active, REGS, random.Random(seed))
    assert plan == choose_monster_turn(state, active, REGS, random.Random(seed))
    assert isinstance(plan[-1], EndTurnCommand)
    execute_command(state, plan[0], REGS, random.Random(seed))
