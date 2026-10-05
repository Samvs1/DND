"""The headless combat driver (M3.11): legendary actions, refusal accounting, replay."""

from __future__ import annotations

import random

import pytest

from aidm.models.commands import AnyCommand, AttackCommand
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.session import combat_runner
from aidm.session.combat_runner import CombatRunner
from aidm.session.reducer import replay
from tests.unit.rules.combat_fixtures import REGS
from tests.unit.rules.encounter_fixtures import make_pc, started


def _fight(
    seed: int, monsters: list[str]
) -> tuple[GameState, GameState, list[AnyEvent], random.Random]:
    pcs = [make_pc("pa"), make_pc("pb"), make_pc("pc", class_index="cleric")]
    log: list[AnyEvent] = []
    initial = GameState(campaign_id="enc", seed=1)
    for pc in pcs:
        initial.creatures[pc.id] = pc.model_copy(deep=True)
    state, rng = started(seed, pcs, monsters, log=log)
    return initial, state, log, rng


def test_runner_plays_legendary_actions_and_replays() -> None:
    initial, state, log, rng = _fight(3, ["unicorn"])
    runner = CombatRunner(state, REGS, rng)
    status = runner.run()
    assert status in (EncounterStatus.VICTORY, EncounterStatus.DEFEAT)
    assert runner.stats.legendary > 0
    assert runner.stats.refused == 0 and runner.stats.forced_ends == 0
    assert replay(initial, [*log, *runner.log]).model_dump() == state.model_dump()


def test_refused_command_is_counted_and_the_turn_ends(monkeypatch: pytest.MonkeyPatch) -> None:
    _, state, _, rng = _fight(1, ["goblin"])

    def bad(state: GameState, cid: str, regs: object, rng: object) -> AnyCommand:
        return AttackCommand(actor_id=cid, target_id="nobody")

    monkeypatch.setattr(combat_runner, "ai_command", bad)
    runner = CombatRunner(state, REGS, rng)
    assert runner.run(max_rounds=2) is EncounterStatus.ACTIVE
    assert runner.stats.refused == runner.stats.turns > 0
