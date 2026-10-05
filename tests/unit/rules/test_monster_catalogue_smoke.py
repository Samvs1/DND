"""Every encounter-ready monster (data/bg3/encounter_monsters.json) fights a level-3 fighter (M3.9).

Smoke test: instantiate it, start an encounter with a seeded rng, take its first catalog option
against the fighter through execute_command, and check the events replay to the same state.
"""

from __future__ import annotations

import random

import pytest

from aidm.data.encounter_monsters import EncounterMonster, encounter_monsters
from aidm.data.srd import srd
from aidm.models.combat_events import MonsterActionUsed
from aidm.models.commands import MonsterActionCommand
from aidm.models.encounter import EncounterSetup, MonsterSpawn, PartyPlacement
from aidm.models.events import AnyEvent
from aidm.models.state import CreatureKind, GameState
from aidm.rules.encounter import start_encounter
from aidm.rules.monster_actions import monster_catalog_of
from aidm.rules.monster_stats import creature_from_monster
from aidm.rules.turns import begin_turn, end_turn
from aidm.session.reducer import apply, replay
from tests.unit.rules.combat_fixtures import REGS, do
from tests.unit.rules.encounter_fixtures import party_state, small_map
from tests.unit.rules.golden_builds import golden_levels

ENTRIES = encounter_monsters().all()


def _open_monster_turn(state: GameState, rng: random.Random, log: list[AnyEvent]) -> str:
    """Advance from the opening of the encounter until a hostile creature's turn is open."""
    for _ in range(6):
        enc = state.encounter
        assert enc is not None
        active = enc.active_id()
        if active is not None and enc.combatant(active).side.value == "hostile":
            return active
        events = [*end_turn(rng, state)] if active is not None else []
        for event in events:
            apply(state, event)
        log.extend(events)
        started = begin_turn(rng, state)
        for event in started:
            apply(state, event)
        log.extend(started)
    raise AssertionError("the monster never got a turn")


@pytest.mark.parametrize("entry", ENTRIES, ids=[e.index for e in ENTRIES])
def test_catalogue_monster_acts_against_a_level_3_fighter(entry: EncounterMonster) -> None:
    block = srd().monsters.get(entry.index)
    assert creature_from_monster(block, "probe").kind is CreatureKind.MONSTER
    fighter = golden_levels("fighter")[3].model_copy(deep=True)
    state = party_state(fighter)
    initial = state.model_copy(deep=True)
    rng = random.Random(7)
    setup = EncounterSetup(
        encounter_id="smoke",
        zone_map=small_map(),
        party=(PartyPlacement(creature_id="pc1", zone_id="gate"),),
        monsters=(MonsterSpawn(monster=entry.index, zone_id="gate"),),
    )
    log = list(start_encounter(rng, state, setup, srd().monsters))
    for event in log:
        apply(state, event)
    monster_id = _open_monster_turn(state, rng, log)
    catalog = monster_catalog_of(state.creatures[monster_id], REGS)
    assert catalog.options
    first = catalog.options[0]
    command = MonsterActionCommand(
        actor_id=monster_id,
        action=first.key,
        target_ids=("pc1",),
        target_zone="gate" if first.shape == "save" else None,
    )
    acted = do(state, command, rng)
    log.extend(acted)
    assert any(isinstance(e, MonsterActionUsed) for e in acted)
    assert replay(initial, log) == state
