"""NPC attitude formula (rules/social.py): capped and floored talk, uncapped deeds."""

from hypothesis import given
from hypothesis import strategies as st

from aidm.models.dm_tiers import AttitudeBand, DeltaTier
from aidm.models.world import WorldNpc
from aidm.models.world_events import AttitudeChanged
from aidm.rules.social import (
    ALLY_BAR,
    SOCIAL_FLOOR,
    attitude_band,
    attitude_score,
    deed_attitude_events,
    hostile_attitude_events,
    npc_is_hostile,
    social_attitude_events,
)


def _npc(base: int = 0) -> WorldNpc:
    return WorldNpc(id="npc-a", name="A", archetype_id="commoner", base=base)


def _talk(npc: WorldNpc, delta: DeltaTier, times: int) -> WorldNpc:
    for _ in range(times):
        for event in social_attitude_events(npc, delta, "talk"):
            assert isinstance(event, AttitudeChanged)
            npc = npc.model_copy(update={"social": event.social, "deeds": event.deeds})
    return npc


def test_v1_social_score_floor() -> None:
    # v1: failed social checks drove the relationship unboundedly negative.
    npc = _talk(_npc(), DeltaTier.WORSEN_MAJOR, 50)
    assert npc.social == SOCIAL_FLOOR
    assert attitude_score(npc) == SOCIAL_FLOOR
    assert attitude_band(attitude_score(npc)) is AttitudeBand.UNFRIENDLY
    assert not npc_is_hostile(npc)
    assert social_attitude_events(npc, DeltaTier.WORSEN, "again") == []
    # SPEC 9: "floored so failed rolls cannot spiral": recovery is never buried under failures.
    recovered = _talk(npc, DeltaTier.IMPROVE, 1)
    assert attitude_score(recovered) == SOCIAL_FLOOR + 10
    deed = deed_attitude_events(npc, 20, "saved her shop")[0]
    assert isinstance(deed, AttitudeChanged)
    assert attitude_score(npc.model_copy(update={"deeds": deed.deeds})) == SOCIAL_FLOOR + 20


def test_v1_talk_caps_below_ally_bar() -> None:
    npc = _talk(_npc(base=20), DeltaTier.IMPROVE_MAJOR, 50)
    assert attitude_score(npc) == ALLY_BAR - 1
    assert attitude_band(attitude_score(npc)) is AttitudeBand.FRIENDLY


def test_deeds_cross_the_ally_bar() -> None:
    npc = _talk(_npc(), DeltaTier.IMPROVE_MAJOR, 10)
    event = deed_attitude_events(npc, 20, "saved her brother")[0]
    assert isinstance(event, AttitudeChanged)
    after = npc.model_copy(update={"deeds": event.deeds})
    assert attitude_band(attitude_score(after)) is AttitudeBand.ALLY


def test_hostile_flag() -> None:
    npc = _npc()
    event = hostile_attitude_events(npc, "attacked")[0]
    assert isinstance(event, AttitudeChanged) and event.hostile
    assert npc_is_hostile(npc.model_copy(update={"hostile": True}))
    assert npc_is_hostile(_npc(base=-80))


@given(st.lists(st.sampled_from(list(DeltaTier)), max_size=40), st.integers(-30, 30))
def test_talk_never_leaves_bounds(deltas: list[DeltaTier], base: int) -> None:
    npc = _npc(base=base)
    for delta in deltas:
        npc = _talk(npc, delta, 1)
    score = attitude_score(npc)
    assert base + SOCIAL_FLOOR <= score < max(base + 1, ALLY_BAR)
