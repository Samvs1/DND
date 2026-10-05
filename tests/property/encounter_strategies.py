"""Hypothesis helpers: raw encounter events valid for the current state (replay properties)."""

from __future__ import annotations

from hypothesis import strategies as st

from aidm.models.combat_events import ZoneSurfaceAdded, ZoneSurfaceRemoved, ZoneSurfaceTicked
from aidm.models.encounter import (
    Combatant,
    Encounter,
    EncounterStatus,
    InitiativeEntry,
    Side,
    TurnEconomy,
    WithdrawReason,
)
from aidm.models.encounter_events import (
    CombatantWithdrew,
    EconomyChanged,
    EncounterEnded,
    EncounterStarted,
    TurnEnded,
    TurnStarted,
)
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.models.zones import Zone, ZoneEdge, ZoneMap, ZoneSurface

ZONES = ZoneMap(
    zones=[Zone(id="a", name="A"), Zone(id="b", name="B", high_ground=True)],
    edges=[ZoneEdge(a="a", b="b", feet=30)],
)
ENDINGS = [s for s in EncounterStatus if s is not EncounterStatus.ACTIVE]


def _economy(data: st.DataObject) -> TurnEconomy:
    return TurnEconomy(
        action=data.draw(st.booleans()),
        bonus_action=data.draw(st.booleans()),
        movement_left=data.draw(st.integers(0, 60)),
        reaction=data.draw(st.booleans()),
        dashed=data.draw(st.booleans()),
        disengaged=data.draw(st.booleans()),
    )


def _start(data: st.DataObject, state: GameState) -> AnyEvent:
    ids = data.draw(st.lists(st.sampled_from(sorted(state.creatures)), min_size=1, unique=True))
    combatants = {
        cid: Combatant(
            creature_id=cid,
            side=data.draw(st.sampled_from(list(Side))),
            zone_id=data.draw(st.sampled_from(["a", "b"])),
            economy=_economy(data),
            xp=data.draw(st.integers(0, 450)),
        )
        for cid in ids
    }
    initiative = [
        InitiativeEntry(creature_id=cid, roll=d4, modifier=0, total=d4, dex=10)
        for cid in ids
        for d4 in [data.draw(st.integers(1, 4))]
    ]
    encounter = Encounter(
        id="prop",
        zone_map=ZONES.model_copy(deep=True),
        combatants=combatants,
        initiative=initiative,
    )
    return EncounterStarted(encounter=encounter)


SURFACE_KINDS = ["fire", "oil", "water", "fog"]


def _surface_events(data: st.DataObject, enc: Encounter) -> list[AnyEvent]:
    zone = data.draw(st.sampled_from(["a", "b"]))
    surface = ZoneSurface(
        kind=data.draw(st.sampled_from(SURFACE_KINDS)),
        rounds_left=data.draw(st.none() | st.integers(1, 10)),
        source_id=data.draw(st.none() | st.sampled_from(sorted(enc.combatants))),
        dc=data.draw(st.none() | st.integers(8, 18)),
        upcast=data.draw(st.integers(0, 2)),
        concentration=data.draw(st.booleans()),
    )
    found: list[AnyEvent] = [ZoneSurfaceAdded(zone_id=zone, surface=surface)]
    for present in enc.zone_map.zone(zone).surfaces:
        found.append(ZoneSurfaceRemoved(zone_id=zone, kind=present.kind, reason="prop"))
        left = data.draw(st.integers(1, 9))
        found.append(ZoneSurfaceTicked(zone_id=zone, kind=present.kind, rounds_left=left))
    return found


def draw_encounter_event(data: st.DataObject, state: GameState) -> AnyEvent:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        return _start(data, state)
    cid = data.draw(st.sampled_from(sorted(enc.combatants)))
    active = enc.active_id()
    if active is not None and data.draw(st.booleans()):
        return TurnEnded(creature_id=active)
    index = data.draw(st.integers(0, len(enc.initiative) - 1))
    options: list[AnyEvent] = [
        TurnStarted(
            creature_id=enc.initiative[index].creature_id,
            round=enc.round + data.draw(st.integers(0, 1)),
            active_index=index,
            economy=_economy(data),
        ),
        EconomyChanged(creature_id=cid, economy=_economy(data), reason="prop"),
        CombatantWithdrew(creature_id=cid, reason=data.draw(st.sampled_from(list(WithdrawReason)))),
        EncounterEnded(status=data.draw(st.sampled_from(ENDINGS)), xp_total=50, xp_each=25),
        *_surface_events(data, enc),
    ]
    return data.draw(st.sampled_from(options))
