"""M29.5b offers, quests and rests from playtest round 1 (docs/playtests/M29_round1.md, G29 G30
G34), each reproduced from its live save (tests/session/playtest_saves.py)."""

import random

from aidm.dm.arrival import offer_data
from aidm.dm.give_intent import give_intent
from aidm.dm.tool_context import tool_registries
from aidm.models.campaign_events import OfferResolved, RegionResolved
from aidm.models.campaign_state import OfferChoice
from aidm.models.encounter_events import EncounterStarted
from aidm.models.world_events import AttitudeChanged
from aidm.rules.offer_answer import answer_offer, sure_parley
from aidm.rules.progression import region_resolution_events
from aidm.rules.rests import RestRefused, long_rest, rest_refused_text
from aidm.session.reducer import apply
from tests.session.playtest_saves import logged, replay_until

P3_BOSS = "boss-bracken-march"


def test_m29_alliance_leaves_the_boss_offer_for_the_player() -> None:
    """p3 857-860: Varek is won over while his offer is open. M29.9a T15: the alliance no longer
    closes the offer by itself; it waits as a sure parley and the answer closes it peacefully."""
    state = replay_until("p3", 860)
    assert state.campaign is not None and state.campaign.offer is not None
    events = region_resolution_events(state)
    assert isinstance(events[0], RegionResolved) and events[0].how.value == "alliance"
    assert not any(isinstance(e, OfferResolved) for e in events)
    for event in events:
        apply(state, event)
    offer = state.campaign.offer
    assert offer is not None and offer.id == "offer-849" and sure_parley(state, offer)
    answer = answer_offer(
        state, OfferChoice.PARLEY, offer_data(tool_registries()), random.Random(1)
    )
    assert [(e.offer_id, e.choice, e.success) for e in answer if isinstance(e, OfferResolved)] == [
        ("offer-849", OfferChoice.PARLEY, True)
    ]
    apply(state, answer[0])
    assert state.campaign.offer is None
    assert not state.world.npcs[P3_BOSS].hostile


def test_m29_stale_boss_offer_never_turns_an_ally_hostile() -> None:
    """p3 882-884: in the old save the offer stayed open and a failed parley started the fight.
    Every answer to such an offer now closes it peacefully."""
    data = offer_data(tool_registries())
    for choice in (OfferChoice.PARLEY, OfferChoice.FIGHT, OfferChoice.SURPRISE):
        state = replay_until("p3", 882)
        assert state.campaign is not None and "bracken-march" in state.campaign.resolved
        events = answer_offer(state, choice, data, random.Random(1), actor_id="pc-p4")
        assert [type(e) for e in events] == [OfferResolved]
        assert not any(isinstance(e, AttitudeChanged | EncounterStarted) for e in events)
        apply(state, events[0])
        assert state.campaign.offer is None and not state.world.npcs[P3_BOSS].hostile


def test_m29_give_by_name_reaches_the_quest_receiver() -> None:
    """p3 420-421: "give the Receipt-scroll to Ranna" went to the boss twin; the side quest's
    deliver step names the cast record, so the give goes there."""
    state = replay_until("p3", 421)
    assert logged("p3", 421).event.model_dump()["npc_id"] == "boss-pale-creek-reaches"
    intent = give_intent(state, "pc-p6", "give the receipt-scroll to ranna")
    assert intent is not None and intent.npc_id == "ranna-the-brine-widow"


def test_m29_rest_refusal_names_the_supplies_short() -> None:
    state = replay_until("p3", 860)
    state.camp_supplies = 5
    try:
        long_rest(state)
    except RestRefused as refused:
        text = rest_refused_text(refused)
    else:
        raise AssertionError("the long rest should be refused")
    assert "35 camp supplies short" in text and "needs 40" in text and "hour" not in text
