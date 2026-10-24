"""M31.1b V10-V12 (docs/playtests/M31_round4.md): a fight start fields the waiting offer's foes,
a master parley before the peaceful route keeps the way on honest, and the region line tells
what the gate still needs, on the real round-4 states."""

import random

from aidm.dm.arrival import offer_data
from aidm.dm.campaign_text import CAMPAIGN_EVENT_LINES, CAMPAIGN_TEMPLATE_LINES
from aidm.dm.tool_context import ToolContext, tool_registries
from aidm.dm.tool_exec_rewards import run_start_encounter
from aidm.dm.tools import StartEncounterArgs
from aidm.models.campaign_events import OfferResolved, RegionResolved
from aidm.models.campaign_state import OfferChoice
from aidm.models.events import AnyEvent, CreatureAdded
from aidm.models.state import GameState
from aidm.rules.encounter_offer import arrival_offer_events
from aidm.rules.offer_answer import answer_offer
from aidm.session.reducer import apply
from tests.session.playtest_saves import events_of, logged, replay_until

TYPED = "m31-r4-typed"
FULL = "m31-r4-full"


def _start(state: GameState, args: StartEncounterArgs) -> list[AnyEvent]:
    ctx = ToolContext(actor_id="pc-p2", confirm_hostile=True)
    result = run_start_encounter(state, args, ctx, random.Random(3), tool_registries())
    return list(result.events)


def _fielded(events: list[AnyEvent]) -> list[str]:
    return sorted(e.creature.monster_index or "" for e in events if isinstance(e, CreatureAdded))


def test_m31_typed_attack_fields_every_foe_of_the_offer() -> None:
    """V10, typed 119-123: "I stab the zombie" fielded the zombie but not the cultist."""
    state = replay_until(TYPED, 120)
    offer = state.campaign.offer if state.campaign is not None else None
    assert offer is not None and offer.monster_ids == ("zombie", "cultist")
    events = _start(state, StartEncounterArgs(monster_ids=["zombie"]))
    closed = [e for e in events if isinstance(e, OfferResolved)]
    assert [(e.offer_id, e.choice) for e in closed] == [(offer.id, OfferChoice.FIGHT)]
    assert _fielded(events) == ["cultist", "zombie"]


def test_m31_typed_charge_fields_the_stirge_too() -> None:
    """V10, typed 334-337: a charge at the sahuagin left the stirge out of the fight."""
    state = replay_until(TYPED, 335)
    events = _start(state, StartEncounterArgs(monster_ids=["sahuagin"]))
    assert _fielded(events) == ["sahuagin", "stirge"]


def test_m31_attack_on_the_master_fields_his_company() -> None:
    """V10, full 633-652: an attack on Brother Mallow while his offer waits fields the cultist."""
    state = replay_until(FULL, 638)
    boss = "boss-the-rotwood-verge"
    events = _start(state, StartEncounterArgs(against_npcs=[boss], opening_strike_on=boss))
    added = [e.creature for e in events if isinstance(e, CreatureAdded)]
    assert sorted(c.monster_index or "" for c in added) == ["cultist", "ghoul"]
    assert [c.npc_id for c in added if c.npc_id is not None] == [boss]
    for event in events:
        state = apply(state, event)
    assert state.campaign is not None and state.campaign.offer is None


def test_m31_master_parley_before_the_route_says_the_way_is_shut() -> None:
    """V11, full 638-650: a won parley with Brother Mallow before the peaceful route was done
    said only "no fight" and left the party stuck; now the line says what is still needed and
    the master's offer comes back on the next arrival."""
    state = replay_until(FULL, 639)
    events = answer_offer(
        state, OfferChoice.PARLEY, offer_data(tool_registries()), random.Random(5), actor_id="pc-p4"
    )
    closed = next(e for e in events if isinstance(e, OfferResolved))
    assert closed.success is True
    line = CAMPAIGN_EVENT_LINES[OfferResolved](state, closed) or ""
    assert "not yet open" in line and "Brother Mallow" in line
    for event in events:
        state = apply(state, event)
    again = arrival_offer_events(state, offer_data(tool_registries()), "mireford-bridge")
    assert again, "the master's offer comes back on the next arrival"


def test_m31_region_line_matches_the_gate() -> None:
    """V12, typed 284 vs 551: "the way to the next region is open" while the Sluice Gate still
    wanted Mossbarrow Copse."""
    resolved = next(
        e for e in events_of(TYPED) if isinstance(e.event, RegionResolved) and e.seq < 300
    )
    state = replay_until(TYPED, resolved.seq + 1)
    event = logged(TYPED, resolved.seq).event
    assert isinstance(event, RegionResolved)
    fact = CAMPAIGN_EVENT_LINES[RegionResolved](state, event) or ""
    story = CAMPAIGN_TEMPLATE_LINES[RegionResolved](state, event) or ""
    for line in (fact, story):
        assert "The Sluice Gate stays shut" in line and "Mossbarrow Copse" in line
        assert "is open" not in line and "opens" not in line
