"""M29.5b-2 engine findings G18 G19 G20 G13 G14 (docs/playtests/M29_round1.md), each reproduced
from its live save: XP is paid once per source, and the lines the storyteller gets say what the
engine did (a find on a failed check, a step met by an item already carried)."""

from collections import Counter

from aidm.dm.event_text import event_line, event_notes
from aidm.models.events import CheckResolved
from aidm.models.quest_events import QuestLead, QuestLeadAdded, QuestStepDone, RouteDiscovered
from aidm.models.world_events import ItemDiscovered, RewardGranted
from aidm.rules.milestones import clear_key, spoke_milestone_events, visit_key
from aidm.rules.quest_offers import LEAD_AGAIN, LEAD_TEXT, lead_events
from tests.session.playtest_saves import events_of, logged, replay_until
from tests.session.progression_fixtures import REGS


def test_m29_xp_visit_and_clear_are_two_milestones_paid_once() -> None:
    """G18 (p2 41/112, 173/230, 265/330): the "warning beat" 75 is the spoke's first-visit
    milestone and the victory 75 its clear milestone (RULES_DECISIONS M9.2; amounts by region
    tier since M29.6b): two rewards, each once. Kill XP (12, 25, 12) is the encounter's own
    award. Nothing pays twice."""
    sources = [
        e.event.source
        for e in events_of("p2")
        if isinstance(e.event, RewardGranted) and e.event.kind == "milestone"
    ]
    assert all(n == 1 for n in Counter(sources).values()), sources
    state = replay_until("p2", 10**6)
    assert state.campaign is not None
    amount = REGS.tiers.milestone_xp["1"].visit
    for node in ("mothyard-ruin", "bitter-well", "copse-of-thorns"):
        keys = (visit_key(node), clear_key(node))
        assert set(keys) <= set(state.campaign.milestones)
        for key in keys:
            assert spoke_milestone_events(state, key, amount, REGS.catalogue) == []


def test_m29_find_on_a_failed_search_is_told_as_found() -> None:
    """G19 (p2 129-134): Investigation 11 missed its goal (DC 15) but met the hidden items' own
    DC 10, so three items were found while the prose said nothing was. The line now says the
    search found the object even though the check missed its own goal."""
    check = logged("p2", 129).event
    assert isinstance(check, CheckResolved) and not check.result.success
    found = logged("p2", 131).event
    assert isinstance(found, ItemDiscovered)
    line = event_line(replay_until("p2", 133), found)
    assert line is not None
    assert "Hatched Moth, an object" in line and "even if the check missed" in line


def test_m29_step_met_on_accept_names_the_carried_item() -> None:
    """G20 (p2 704-706): accepting "The Moth's Small Fee" met its obtain step at once because
    Elowen had picked up the Hatched Moth at 145 (steps read the current state: work done before
    a quest is accepted counts). The narrator then told her plucking it. The line now says who
    already carries it and to tell no new deed."""
    step = logged("p2", 705).event
    assert isinstance(step, QuestStepDone) and step.step == 0
    line = event_line(replay_until("p2", 706), step)
    assert line is not None
    assert "Elowen already carries the Hatched Moth" in line and "no new deed" not in line
    assert "no new deed" in " ".join(event_notes(replay_until("p2", 706), [step]))


def test_m29_opening_routes_are_ways_known_not_found() -> None:
    """G13 (p1 24-25): the routes known at install were told as "The party found a way"."""
    route = logged("p2", 23).event
    assert isinstance(route, RouteDiscovered)
    line = event_line(replay_until("p2", 24), route)
    assert line is not None and "a way the party knows of" in line and "found" not in line


def test_m29_two_askers_in_one_place_get_two_lead_lines() -> None:
    """G14 (livecheck c-20261023-080351-0001 21-22): two quests at Tollgate Halt both read
    "Someone at Tollgate Halt may need help."; the second asker's lead now reads differently."""
    state = replay_until("p2", 26)
    (first,) = lead_events(state)
    assert isinstance(first, QuestLeadAdded)
    assert first.lead.text == LEAD_TEXT.format(place="Mothyard Ruin")
    state.world.leads = [QuestLead(quest_id="another-quest", text=first.lead.text)]
    (second,) = lead_events(state)
    assert isinstance(second, QuestLeadAdded)
    assert second.lead.text == LEAD_AGAIN.format(place="Mothyard Ruin")
