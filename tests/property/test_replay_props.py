"""Property: replaying the event log reproduces the live state exactly (SPEC 2.5, 13)."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from aidm.models.events import AnyEvent, LoggedEvent, event_adapter
from aidm.models.state import GameState
from aidm.session.reducer import apply, replay
from tests.property.event_strategies import draw_event


def _build(data: st.DataObject) -> tuple[GameState, GameState, list[AnyEvent]]:
    initial = GameState(campaign_id="prop", seed=data.draw(st.integers(0, 2**31)))
    live = initial.model_copy(deep=True)
    events: list[AnyEvent] = []
    for i in range(data.draw(st.integers(min_value=0, max_value=40))):
        event = draw_event(data, live, i)
        apply(live, event)
        events.append(event)
    return initial, live, events


@settings(max_examples=150)
@given(st.data())
def test_replay_equals_incremental(data: st.DataObject) -> None:
    initial, live, events = _build(data)
    dumps_before = [e.model_dump() for e in events]
    final = replay(initial, events)
    assert final.model_dump() == live.model_dump()
    assert final.event_count == len(events)
    assert initial.event_count == 0
    assert initial.creatures == {}
    # Applying events must never alias state into logged payloads.
    assert [e.model_dump() for e in events] == dumps_before


@settings(max_examples=100)
@given(st.data())
def test_event_json_round_trip_and_replay(data: st.DataObject) -> None:
    initial, live, events = _build(data)
    decoded: list[AnyEvent] = []
    for seq, event in enumerate(events):
        back = event_adapter.validate_json(event.model_dump_json())
        assert back == event
        assert type(back) is type(event)
        logged = LoggedEvent.model_validate_json(
            LoggedEvent(seq=seq, event=event).model_dump_json()
        )
        assert logged.event == event
        decoded.append(back)
    assert replay(initial, decoded).model_dump() == live.model_dump()


@settings(max_examples=100)
@given(st.data())
def test_snapshot_json_round_trip(data: st.DataObject) -> None:
    _, live, _ = _build(data)
    assert GameState.model_validate_json(live.model_dump_json()) == live
