"""Property: spell-slot conservation across random casts and rests (SPEC 7.4, 13).

For every slot pool: spent + remaining == maximum, remaining is never negative, a short rest
refills exactly the pact pools and a long rest refills every pool.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from aidm.data.character_data import character_registries
from aidm.models.events import AnyEvent, CreatureAdded, ResourceSet
from aidm.models.state import GameState
from aidm.rules.creation import build_character
from aidm.rules.rests import RestRefused, long_rest, short_rest
from aidm.rules.spellcasting import (
    SlotError,
    SlotKind,
    can_cast,
    slot_maximum_events,
    slot_pools,
    spend_slot,
)
from aidm.session.reducer import apply
from tests.unit.rules.creation_fixtures import default_choices

CASTERS = ["wizard", "cleric", "warlock", "ranger"]
OPS = st.one_of(
    st.tuples(st.just("cast"), st.integers(0, 5), st.one_of(st.none(), st.integers(1, 5))),
    st.tuples(st.just("short"), st.just(0), st.none()),
    st.tuples(st.just("long"), st.just(0), st.none()),
)


def _apply_all(state: GameState, events: list[AnyEvent]) -> None:
    for event in events:
        apply(state, event)


def _setup(cls: str, level: int) -> GameState:
    regs = character_registries()
    pc = build_character(default_choices(cls, "human", None), regs, "pc")
    state = GameState(campaign_id="p", seed=0, camp_supplies=10_000)
    apply(state, CreatureAdded(creature=pc))
    _apply_all(state, slot_maximum_events(state.creatures["pc"], regs.classes.get(cls), level))
    return state


def _check_pools(state: GameState, spent: dict[str, int]) -> None:
    for ref, pool in slot_pools(state.creatures["pc"]):
        assert pool.current >= 0
        assert pool.current + spent.get(ref.key, 0) == pool.maximum


def _cast(state: GameState, spent: dict[str, int], spell: int, slot: int | None) -> None:
    pc = state.creatures["pc"]
    allowed = can_cast(pc, spell, slot)
    try:
        events = spend_slot(pc, spell, slot)
    except SlotError:
        assert not allowed
        return
    assert allowed
    assert len(events) == (0 if spell == 0 and slot is None else 1)
    for event in events:
        assert isinstance(event, ResourceSet)
        spent[event.key] = spent.get(event.key, 0) + 1
    _apply_all(state, events)


def _rest(state: GameState, spent: dict[str, int], short: bool) -> None:
    try:
        _apply_all(state, short_rest(state) if short else long_rest(state))
    except RestRefused:
        assert short  # only the 2-per-long-rest limit can refuse here
        return
    for ref, _ in slot_pools(state.creatures["pc"]):
        if not short or ref.kind is SlotKind.PACT:
            spent[ref.key] = 0


@settings(max_examples=150)
@given(
    st.sampled_from(CASTERS),
    st.integers(1, 5),
    st.lists(OPS, max_size=30),
)
def test_slot_conservation(cls: str, level: int, ops: list[tuple[str, int, int | None]]) -> None:
    state = _setup(cls, level)
    spent: dict[str, int] = {}
    _check_pools(state, spent)
    for op, spell, slot in ops:
        if op == "cast":
            _cast(state, spent, spell, slot)
        else:
            _rest(state, spent, short=op == "short")
        _check_pools(state, spent)
