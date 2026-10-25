"""M29.9a offer findings from playtest round 3 (docs/playtests/M29_round3.md T8 T15 T16), each
reproduced from its live save (tests/session/playtest_saves.py)."""

import random

from aidm.dm.arrival import offer_data
from aidm.dm.precheck import precheck
from aidm.dm.tool_context import tool_registries
from aidm.models.campaign_events import OfferResolved, RegionResolved
from aidm.models.campaign_state import OfferChoice
from aidm.models.encounter import EncounterSetup, MonsterSpawn, PartyPlacement
from aidm.models.encounter_events import EncounterStarted
from aidm.models.events import CreatureAdded
from aidm.rules.acts import ParleyIntent
from aidm.rules.encounter import start_encounter
from aidm.rules.encounter_offer import fight_map
from aidm.rules.offer_answer import answer_offer, foes_gone, sure_parley
from aidm.rules.progression import node_plan, region_resolution_events
from aidm.session.reducer import apply
from tests.session.playtest_saves import replay_until

OSSUARY = "the-glass-ossuary"


def test_m29_typed_fight_resolves_the_waiting_offer() -> None:
    """r3-items 817-819: "I draw my longsword and charge the ice mephit" started a fight while
    offer-804 waited. Every fight start now answers the place's offer (choice fight)."""
    state = replay_until("r3-items", 818)
    assert state.campaign is not None and state.campaign.offer is not None
    assert state.campaign.offer.id == "offer-804"
    regs = tool_registries()
    zone_map = fight_map(state, node_plan(state, OSSUARY), "typed", regs.terrains)
    pcs = sorted(c.id for c in state.creatures.values() if c.pc is not None and not c.dead)
    setup = EncounterSetup(
        encounter_id="enc-typed",
        zone_map=zone_map,
        party=tuple(PartyPlacement(creature_id=pc, zone_id=zone_map.zones[0].id) for pc in pcs),
        monsters=(MonsterSpawn(monster="ice-mephit", zone_id=zone_map.zones[1].id),),
    )
    events = start_encounter(random.Random(1), state, setup, regs.combat.monsters)
    first = events[0]
    assert isinstance(first, OfferResolved)
    assert (first.offer_id, first.choice) == ("offer-804", OfferChoice.FIGHT)
    for event in events:
        apply(state, event)
    assert state.campaign.offer is None
    assert state.encounter is not None and state.encounter.node_id == OSSUARY


def test_m29_offer_answer_fight_resolves_only_once() -> None:
    """The offer's own fight answers it once: start_encounter adds no second OfferResolved."""
    state = replay_until("r3-items", 818)
    events = answer_offer(state, OfferChoice.FIGHT, offer_data(tool_registries()), random.Random(2))
    assert [e.offer_id for e in events if isinstance(e, OfferResolved)] == ["offer-804"]
    for event in events:
        apply(state, event)
    assert state.encounter is not None and state.encounter.node_id == OSSUARY


def test_m29_offer_with_dead_foes_never_respawns() -> None:
    """r3-items 963-969: after the mephit died, `answer escape` failed into a fresh ice-mephit-2
    that paid XP and loot again. An offer whose foes are all down closes with no fight."""
    state = replay_until("r3-items", 963)
    assert state.campaign is not None and state.campaign.offer is not None
    assert state.encounter is not None and state.world.current_node == OSSUARY
    state.encounter.node_id = OSSUARY  # the old save predates Encounter.node_id
    offer = state.campaign.offer
    assert foes_gone(state, offer)
    data = offer_data(tool_registries())
    for choice in (OfferChoice.ESCAPE, OfferChoice.FIGHT, OfferChoice.SURPRISE):
        events = answer_offer(state, choice, data, random.Random(3))
        assert [type(e) for e in events] == [OfferResolved]
        assert not any(isinstance(e, CreatureAdded | EncounterStarted) for e in events)


def test_m29_hand_over_leaves_the_master_offer_waiting() -> None:
    """r3-full 1068-1074: the seal hand-over finished Ulva's peace route and her offer resolved
    as a parley nobody answered. The alliance now leaves the offer for the player, shown sure."""
    state = replay_until("r3-full", 1068)
    assert state.campaign is not None and state.campaign.offer is not None
    events = region_resolution_events(state)
    assert any(isinstance(e, RegionResolved) and e.how.value == "alliance" for e in events)
    assert not any(isinstance(e, OfferResolved) for e in events)
    for event in events:
        apply(state, event)
    offer = state.campaign.offer
    assert offer is not None and offer.id == "offer-1038"
    assert sure_parley(state, offer)
    answer = answer_offer(
        state, OfferChoice.PARLEY, offer_data(tool_registries()), random.Random(4)
    )
    assert [(type(e), getattr(e, "success", None)) for e in answer] == [(OfferResolved, True)]


def test_m29_question_to_a_bystander_is_not_a_parley() -> None:
    """r3-full 1440-1442: "Brienne asks Dreda Flint who she is ..." while an ogre offer waited
    was read as a parley and failed into the fight. Words to another NPC are a talk turn."""
    state = replay_until("r3-full", 1440)
    assert state.campaign is not None and state.campaign.offer is not None
    text = "Brienne asks Dreda Flint who she is, what happens at the forge, and where Sera Vask is."
    assert not isinstance(precheck(state, "pc-p2", text), ParleyIntent)
    aimed = precheck(state, "pc-p2", "I tell the ogre to turn back and leave us be")
    assert isinstance(aimed, ParleyIntent)
    plain = precheck(state, "pc-p2", "I call out and ask whether we may pass in peace")
    assert isinstance(plain, ParleyIntent)
