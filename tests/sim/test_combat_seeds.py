"""Headless combat sim (M3.11, SPEC 13/14 M3): 50 seeded fights, both sides played by the AI.

Each seed: a fighter, rogue, wizard and cleric at level 1-5 (built and levelled by the real
pipelines, one healing potion each), a zone map from random terrain tags, a medium or hard
CR-budget encounter of encounter-ready monsters, started by `start_encounter` and run by
`aidm.session.combat_runner.CombatRunner` (monster AI for hostiles, autoplay for PCs).
Checked after EVERY applied event: HP within [0, max], temp HP >= 0, every resource (spell
slots included) within [0, max], at most one concentration per creature (no second
ConcentrationStarted without a ConcentrationEnded), dead or withdrawn creatures never start a
turn. Per fight: it ends before 50 rounds, the AI drivers had no refused command and no forced
turn end, and replay(initial, events) equals the final state. Across the seeds both victories
and defeats occur (balance sanity).
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field

from aidm.models.encounter import EncounterStatus
from aidm.models.encounter_events import TurnStarted
from aidm.models.events import AnyEvent, ConcentrationEnded, ConcentrationStarted
from aidm.models.state import GameState
from aidm.rules.encounter import start_encounter
from aidm.session.combat_runner import CombatRunner
from aidm.session.reducer import replay
from tests.sim.sim_setup import REGS, apply_all, setup_fight

SEEDS = range(50)
MAX_ROUNDS = 50


@dataclass
class Invariants:
    concentrating: set[str] = field(default_factory=set[str])
    violations: list[str] = field(default_factory=list[str])

    def check(self, state: GameState, event: AnyEvent) -> None:
        for creature in state.creatures.values():
            if not 0 <= creature.hp <= creature.max_hp or creature.temp_hp < 0:
                self.violations.append(f"hp {creature.id} {creature.hp}/{creature.max_hp}")
            for key, pool in creature.resources.items():
                if not 0 <= pool.current <= pool.maximum:
                    self.violations.append(f"resource {creature.id} {key} {pool.current}")
        if isinstance(event, ConcentrationStarted):
            if event.creature_id in self.concentrating:
                self.violations.append(f"double concentration {event.creature_id}")
            self.concentrating.add(event.creature_id)
        elif isinstance(event, ConcentrationEnded):
            self.concentrating.discard(event.creature_id)
        elif isinstance(event, TurnStarted):
            self._turn(state, event.creature_id)

    def _turn(self, state: GameState, creature_id: str) -> None:
        enc = state.encounter
        creature = state.creatures[creature_id]
        withdrawn = enc is not None and enc.combatant(creature_id).withdrawn is not None
        if creature.dead or withdrawn:
            self.violations.append(f"turn for out-of-fight {creature_id}")


@dataclass(frozen=True)
class FightResult:
    status: EncounterStatus
    rounds: int
    events: int


def run_seed(seed: int) -> FightResult:
    state, setup, rng, level, difficulty = setup_fight(seed)
    initial = state.model_copy(deep=True)
    log: list[AnyEvent] = []
    apply_all(state, start_encounter(rng, state, setup, REGS.monsters), log)
    invariants = Invariants()
    runner = CombatRunner(state, REGS, rng, invariants.check)
    status = runner.run(MAX_ROUNDS)
    label = f"seed {seed} level {level} {difficulty.value} {[m.monster for m in setup.monsters]}"
    assert status is not EncounterStatus.ACTIVE, f"{label}: no end in {MAX_ROUNDS} rounds"
    assert invariants.violations == [], f"{label}: {invariants.violations[:5]}"
    assert runner.stats.refused == 0, f"{label}: {runner.stats}"
    assert runner.stats.forced_ends == 0, f"{label}: {runner.stats}"
    log.extend(runner.log)
    assert replay(initial, log).model_dump() == state.model_dump(), f"{label}: replay differs"
    enc = state.encounter
    assert enc is not None
    return FightResult(status, enc.round, len(log))


def test_combat_sim_50_seeds() -> None:
    results = [run_seed(seed) for seed in SEEDS]
    outcomes = Counter(r.status for r in results)
    rounds = sum(r.rounds for r in results) / len(results)
    sys.stdout.write(
        f"COMBAT SIM OK seeds={len(results)} victories={outcomes[EncounterStatus.VICTORY]} "
        f"defeats={outcomes[EncounterStatus.DEFEAT]} fled={outcomes[EncounterStatus.FLED]} "
        f"avg_rounds={rounds:.1f} events={sum(r.events for r in results)}\n"
    )
    assert outcomes[EncounterStatus.VICTORY] > 0
    assert outcomes[EncounterStatus.DEFEAT] > 0


def test_combat_sim_is_deterministic() -> None:
    assert run_seed(7) == run_seed(7)
