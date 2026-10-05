"""Property: `rules.projection.project_state` agrees with the reducer on every covered event."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from aidm.models.combat_events import (
    CombatantMoved,
    CreatureRevived,
    ZoneSurfaceAdded,
    ZoneSurfaceRemoved,
    ZoneSurfaceTicked,
)
from aidm.models.encounter_events import EconomyChanged
from aidm.models.events import (
    AnyEvent,
    ConcentrationEnded,
    ConcentrationStarted,
    ConditionApplied,
    ConditionRemoved,
    ConditionTicked,
    CreatureDied,
    DeathSaveRolled,
    DeathSavesSet,
    HpChanged,
    ResourceSet,
    Stabilized,
    TempHpSet,
)
from aidm.models.state import GameState
from aidm.rules.projection import project_state
from aidm.session.reducer import apply
from tests.property.encounter_strategies import draw_encounter_event
from tests.property.event_strategies import TARGETED, draw_creature

COVERED = (
    HpChanged,
    TempHpSet,
    ConditionApplied,
    ConditionRemoved,
    ConditionTicked,
    ConcentrationStarted,
    ConcentrationEnded,
    DeathSaveRolled,
    DeathSavesSet,
    Stabilized,
    CreatureDied,
    CreatureRevived,
    ResourceSet,
)


@settings(max_examples=150)
@given(st.data())
def test_projection_matches_reducer(data: st.DataObject) -> None:
    initial = GameState(campaign_id="proj", seed=1)
    for i in range(data.draw(st.integers(1, 3))):
        creature = draw_creature(data, f"c{i}")
        initial.creatures[creature.id] = creature
    live = initial.model_copy(deep=True)
    events: list[AnyEvent] = []
    for _ in range(data.draw(st.integers(0, 25))):
        target = live.creatures[data.draw(st.sampled_from(sorted(live.creatures)))]
        event = data.draw(st.sampled_from(TARGETED))(data, target)
        if not isinstance(event, COVERED):
            continue
        apply(live, event)
        events.append(event)
    before = initial.model_dump()
    projected = project_state(initial, events)
    assert initial.model_dump() == before
    for cid, creature in live.creatures.items():
        assert projected.creatures[cid].model_dump() == creature.model_dump()


ENCOUNTER_COVERED = (EconomyChanged, CombatantMoved, ZoneSurfaceAdded, ZoneSurfaceRemoved)
ENCOUNTER_COVERED += (ZoneSurfaceTicked,)


@settings(max_examples=100)
@given(st.data())
def test_projection_matches_reducer_on_encounter_events(data: st.DataObject) -> None:
    initial = GameState(campaign_id="proj", seed=1)
    for i in range(data.draw(st.integers(1, 3))):
        creature = draw_creature(data, f"c{i}")
        initial.creatures[creature.id] = creature
    apply(initial, draw_encounter_event(data, initial))
    live = initial.model_copy(deep=True)
    events: list[AnyEvent] = []
    for _ in range(data.draw(st.integers(0, 20))):
        event = draw_encounter_event(data, live)
        if not isinstance(event, ENCOUNTER_COVERED):
            continue
        apply(live, event)
        events.append(event)
    before = initial.model_dump()
    projected = project_state(initial, events)
    assert initial.model_dump() == before
    assert projected.encounter is not None and live.encounter is not None
    assert projected.encounter.model_dump() == live.encounter.model_dump()
