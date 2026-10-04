"""Shared helpers for encounter tests: PCs, a small zone map, and applying events."""

from __future__ import annotations

import functools
import random
from collections.abc import Sequence

from aidm.data.character_data import character_registries
from aidm.data.srd import srd
from aidm.models.abilities import Ability
from aidm.models.encounter import EncounterSetup, MonsterSpawn, PartyPlacement, SurpriseKind
from aidm.models.events import AnyEvent
from aidm.models.state import Creature, GameState
from aidm.models.zones import Zone, ZoneEdge, ZoneMap
from aidm.rules.creation import build_character
from aidm.rules.encounter import start_encounter
from aidm.session.reducer import apply
from tests.unit.rules.creation_fixtures import default_choices


@functools.cache
def _template(class_index: str) -> Creature:
    choices = default_choices(class_index, "human", None)
    return build_character(choices, character_registries(), "template")


def make_pc(cid: str, *, dex: int = 12, class_index: str = "fighter") -> Creature:
    pc = _template(class_index).model_copy(update={"id": cid, "name": cid.title()}, deep=True)
    pc.abilities[Ability.DEX] = dex
    return pc


def small_map() -> ZoneMap:
    return ZoneMap(
        zones=[
            Zone(id="gate", name="Gate"),
            Zone(id="yard", name="Yard"),
            Zone(id="wall", name="Wall", high_ground=True),
        ],
        edges=[ZoneEdge(a="gate", b="yard", feet=30), ZoneEdge(a="yard", b="wall", feet=15)],
    )


def party_state(*pcs: Creature) -> GameState:
    state = GameState(campaign_id="enc", seed=1)
    for pc in pcs:
        state.creatures[pc.id] = pc
    return state


def run(state: GameState, events: Sequence[AnyEvent], log: list[AnyEvent] | None = None) -> None:
    for event in events:
        apply(state, event)
        if log is not None:
            log.append(event)


def setup_for(
    pc_ids: Sequence[str],
    monsters: Sequence[str],
    surprise: SurpriseKind = SurpriseKind.NONE,
) -> EncounterSetup:
    return EncounterSetup(
        encounter_id="e1",
        zone_map=small_map(),
        party=tuple(PartyPlacement(creature_id=cid, zone_id="gate") for cid in pc_ids),
        monsters=tuple(MonsterSpawn(monster=m, zone_id="yard") for m in monsters),
        surprise=surprise,
    )


def started(
    seed: int,
    pcs: Sequence[Creature],
    monsters: Sequence[str],
    surprise: SurpriseKind = SurpriseKind.NONE,
    log: list[AnyEvent] | None = None,
) -> tuple[GameState, random.Random]:
    state = party_state(*pcs)
    rng = random.Random(seed)
    setup = setup_for([p.id for p in pcs], monsters, surprise)
    run(state, start_encounter(rng, state, setup, srd().monsters), log)
    return state, rng
