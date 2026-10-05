"""Helpers for monster action tests: SRD monsters as creatures, plain targets, monster commands."""

from __future__ import annotations

from collections.abc import Sequence

from aidm.models.commands import MonsterActionCommand
from aidm.models.events import AnyEvent
from aidm.models.state import Creature, GameState
from aidm.rules.monster_stats import creature_from_monster
from aidm.rules.turns import begin_turn, end_turn
from aidm.session.reducer import apply
from tests.unit.rules.combat_fixtures import REGS, ScriptedRng, do, monster


def srd_monster(index: str, cid: str) -> Creature:
    return creature_from_monster(REGS.monsters.get(index), cid)


def dummy(cid: str, *, hp: int = 100, ac: int = 12, **abilities: int) -> Creature:
    """A plain target: all scores 10 unless given (save modifier +0), no proficiencies."""
    return monster(cid, hp=hp, ac=ac, **abilities)


def act(
    state: GameState,
    actor: str,
    action: str,
    rng: ScriptedRng,
    *,
    targets: Sequence[str] = (),
    zone: str | None = None,
    option: int | None = None,
) -> list[AnyEvent]:
    cmd = MonsterActionCommand(
        actor_id=actor, action=action, target_ids=tuple(targets), target_zone=zone, option=option
    )
    return do(state, cmd, rng)


def advance(state: GameState, rng: ScriptedRng) -> list[AnyEvent]:
    """End the open turn and begin the next one; returns the begin_turn events."""
    for event in end_turn(rng, state):
        apply(state, event)
    started = begin_turn(rng, state)
    for event in started:
        apply(state, event)
    return started


def hp(state: GameState, cid: str) -> int:
    return state.creatures[cid].hp


def resource(state: GameState, cid: str, key: str) -> int:
    pool = state.creatures[cid].resources.get(key)
    return 0 if pool is None else pool.current
