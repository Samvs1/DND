"""Shared helpers for combat command tests: a scripted RNG, monsters, and a fight in progress."""

from __future__ import annotations

import random
from collections.abc import Sequence

from aidm.data.combat_data import combat_registries
from aidm.models.abilities import Ability
from aidm.models.commands import AnyCommand
from aidm.models.encounter import Combatant, Encounter, InitiativeEntry, Side, TurnEconomy
from aidm.models.encounter_events import EncounterStarted, TurnStarted
from aidm.models.events import AnyEvent
from aidm.models.state import Creature, CreatureKind, GameState
from aidm.models.zones import ZoneMap
from aidm.rules.commands import execute_command
from aidm.rules.turns import fresh_economy
from aidm.session.reducer import apply
from tests.unit.rules.encounter_fixtures import small_map

REGS = combat_registries()


class ScriptedRng:
    """An Rng that returns the scripted values in order (each must fit the asked range)."""

    def __init__(self, *values: int) -> None:
        self.values = list(values)

    def randint(self, a: int, b: int, /) -> int:
        if not self.values:
            raise AssertionError(f"rng exhausted (asked {a}..{b})")
        value = self.values.pop(0)
        if not a <= value <= b:
            raise AssertionError(f"scripted {value} outside {a}..{b}")
        return value


def monster(cid: str = "gob", *, hp: int = 10, ac: int = 15, **abilities: int) -> Creature:
    scores = dict.fromkeys(Ability, 10)
    for key, value in abilities.items():
        scores[Ability(key)] = value
    return Creature(
        id=cid,
        name=cid.title(),
        kind=CreatureKind.MONSTER,
        max_hp=hp,
        hp=hp,
        ac=ac,
        abilities=scores,
    )


type Placement = tuple[Creature, Side, str]


def fight(placements: Sequence[Placement], zone_map: ZoneMap | None = None) -> GameState:
    """A started fight where the FIRST placement's turn is open (initiative in given order)."""
    state = GameState(campaign_id="cmd", seed=1)
    for creature, _, _ in placements:
        state.creatures[creature.id] = creature
    encounter = Encounter(
        id="f1",
        zone_map=zone_map or small_map(),
        combatants={
            c.id: Combatant(creature_id=c.id, side=side, zone_id=zone)
            for c, side, zone in placements
        },
        initiative=[
            InitiativeEntry(creature_id=c.id, roll=1, modifier=0, total=20 - i, dex=10)
            for i, (c, _, _) in enumerate(placements)
        ],
    )
    apply(state, EncounterStarted(encounter=encounter))
    first = placements[0][0]
    apply(
        state,
        TurnStarted(creature_id=first.id, round=1, active_index=0, economy=fresh_economy(first)),
    )
    return state


def do(state: GameState, command: AnyCommand, rng: random.Random | ScriptedRng) -> list[AnyEvent]:
    """Execute a command and apply its events; returns the events."""
    events = execute_command(state, command, REGS, rng)
    for event in events:
        apply(state, event)
    return events


def economy(state: GameState, cid: str) -> TurnEconomy:
    assert state.encounter is not None
    return state.encounter.combatant(cid).economy
