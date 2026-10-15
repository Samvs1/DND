"""Property (M23.1): any valid run of quest events replays to the live state, also through JSON."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from aidm.data.character_data import character_registries
from aidm.models.character import Keepsake
from aidm.models.events import AnyEvent, event_adapter
from aidm.models.quest_events import KeepsakeGiven, QuestLeadAdded, QuestStepDone, RouteDiscovered
from aidm.models.quests import MAX_STEPS, QuestKind, QuestStep, StepKind
from aidm.models.state import GameState
from aidm.models.world import Quest, QuestLead, QuestState, RouteProgress, WorldNpc
from aidm.models.world_events import KeepsakeGained, NpcIntroduced, QuestUpdated
from aidm.rules.creation import build_character
from aidm.session.reducer import apply, replay
from tests.unit.rules.creation_fixtures import default_choices

ROUTES = ("force", "peace", "cunning")
NPCS = ("yeva", "vess")
LINES = st.sampled_from(["", "The bell is muffled.", "A keystone found."])


def _start() -> tuple[GameState, list[AnyEvent]]:
    state = GameState(campaign_id="quest-prop", seed=1)
    hero = build_character(
        default_choices("fighter", "human", None), character_registries(), "hero"
    )
    state.creatures[hero.id] = hero
    npcs: list[AnyEvent] = [
        NpcIntroduced(npc=WorldNpc(id=n, name=n.title(), archetype_id="commoner")) for n in NPCS
    ]
    return state, npcs


def _new_quest(data: st.DataObject, i: int) -> AnyEvent:
    if data.draw(st.booleans()):
        main = Quest(
            id=f"main-{i}",
            title="Main",
            kind=QuestKind.MAIN,
            routes=(RouteProgress(route_id="force"),),
        )
        return QuestUpdated(quest=main)
    steps = tuple(
        QuestStep(kind=StepKind.FREE, text=f"step {n}") for n in range(data.draw(st.integers(1, 4)))
    )
    state = data.draw(st.sampled_from([QuestState.OFFERED, QuestState.ACTIVE]))
    return QuestUpdated(
        quest=Quest(id=f"side-{i}", title="Side", state=state, kind=QuestKind.SIDE, steps=steps)
    )


def _step(data: st.DataObject, state: GameState) -> AnyEvent | None:
    options: list[QuestStepDone] = []
    for q in state.world.quests.values():
        if q.steps_done < len(q.steps):
            options.append(QuestStepDone(quest_id=q.id, step=q.steps_done))
        options += [
            QuestStepDone(quest_id=q.id, route_id=r.route_id, step=r.steps_done)
            for r in q.routes
            if r.steps_done < MAX_STEPS
        ]
    if not options:
        return None
    chosen = data.draw(st.sampled_from(options))
    return chosen.model_copy(update={"log_line": data.draw(LINES)})


def _route(data: st.DataObject, state: GameState) -> AnyEvent | None:
    options = [
        RouteDiscovered(quest_id=q.id, route_id=r)
        for q in state.world.quests.values()
        if q.kind is QuestKind.MAIN
        for r in ROUTES
        if q.route(r) is None
    ]
    return data.draw(st.sampled_from(options)) if options else None


def _keepsake(data: st.DataObject, state: GameState, i: int) -> AnyEvent:
    pc = state.creatures["hero"].pc
    assert pc is not None
    if pc.keepsakes and data.draw(st.booleans()):
        keepsake = data.draw(st.sampled_from(pc.keepsakes))
        return KeepsakeGiven(
            creature_id="hero", keepsake_id=keepsake.id, npc_id=data.draw(st.sampled_from(NPCS))
        )
    quest_id = data.draw(st.sampled_from([None, "side-0"]))
    return KeepsakeGained(
        creature_id="hero", keepsake=Keepsake(id=f"k{i}", name="Keystone", quest_id=quest_id)
    )


def _draw(data: st.DataObject, state: GameState, i: int) -> AnyEvent:
    pick = data.draw(st.integers(0, 4))
    event: AnyEvent | None = None
    if pick == 1:
        event = _step(data, state)
    elif pick == 2:
        event = _route(data, state)
    elif pick == 3:
        event = QuestLeadAdded(lead=QuestLead(quest_id=f"lead-{i}", text="Someone may need help"))
    elif pick == 4:
        event = _keepsake(data, state, i)
    return event if event is not None else _new_quest(data, i)


@settings(max_examples=120)
@given(st.data())
def test_quest_events_replay_equals_live(data: st.DataObject) -> None:
    initial, events = _start()
    live = initial.model_copy(deep=True)
    for event in events:
        apply(live, event)
    for i in range(data.draw(st.integers(0, 30))):
        event = _draw(data, live, i)
        apply(live, event)
        events.append(event)
    dumps = [e.model_dump() for e in events]
    decoded = [event_adapter.validate_json(e.model_dump_json()) for e in events]
    assert decoded == events
    assert replay(initial, decoded).model_dump() == live.model_dump()
    assert GameState.model_validate_json(live.model_dump_json()) == live
    assert [e.model_dump() for e in events] == dumps
