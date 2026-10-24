"""M23.9 the epilogue tells the finale and the routes: the facts carry the chosen ending (the
question, its title and text) and how each region was resolved by which route; side quests end
completed / left behind / never taken up; the template mentions the chosen ending; the narrator
context at the finale has the question and no ending text before the choice."""

from aidm.dm.context import SectionKey, build_context
from aidm.dm.context_text import ContextPurpose
from aidm.dm.epilogue import epilogue_checker
from aidm.dm.epilogue_facts import epilogue_facts, template_epilogue
from aidm.dm.event_text import event_line, event_notes
from aidm.dm.narration_templates import template_line
from aidm.models.campaign_events import FinaleChosen, RegionResolved
from aidm.models.campaign_state import RegionResolution
from aidm.models.state import GameState
from aidm.models.world import ClosedReason, QuestState, RouteProgress
from aidm.models.world_events import QuestUpdated
from aidm.rules.quest_plan import main_world_quest, side_world_quest
from tests.ai.epilogue_fixtures import finished_campaign
from tests.session.progression_fixtures import apply_all, campaign_state, plan

SILENCE_TEXT = "Break the Choir's last hymn; the coast is safe, and the old wardens' memory dies"
LET_TEXT = "Let the song end on its own"


def _finale_question() -> str:
    finale = plan().finale
    assert finale is not None
    return finale.question


def _routes_walked() -> GameState:
    """Act 1 won over by its Peace route, act 2 defeated after its Cunning route, one side quest
    completed, one left behind, one never taken up."""
    _, state, log = campaign_state(offered=False)
    acts, quests = plan().acts, {q.id: q for q in plan().quests}
    peace = main_world_quest(plan(), 1).model_copy(
        update={
            "state": QuestState.COMPLETED,
            "routes": (
                RouteProgress(route_id="force"),
                RouteProgress(route_id="the-tide-orders", steps_done=2),
            ),
        }
    )
    cunning = main_world_quest(plan(), 2).model_copy(
        update={
            "state": QuestState.COMPLETED,
            "routes": (
                RouteProgress(route_id="force", steps_done=2),
                RouteProgress(route_id="the-back-stair", steps_done=2),
            ),
        }
    )
    done = side_world_quest(plan(), quests["missing-ledger"]).model_copy(
        update={"state": QuestState.COMPLETED}
    )
    behind = side_world_quest(plan(), quests["douse-the-choir"]).model_copy(
        update={"state": QuestState.FAILED, "closed_reason": ClosedReason.LEFT_BEHIND}
    )
    asked = side_world_quest(plan(), quests["wardens-signet"])
    apply_all(
        state,
        [
            *(QuestUpdated(quest=q) for q in (peace, cunning, done, behind, asked)),
            RegionResolved(region_id=acts[0].region.id, how=RegionResolution.ALLIANCE),
            RegionResolved(region_id=acts[1].region.id, how=RegionResolution.DEFEAT),
        ],
        log,
    )
    return state


def test_facts_carry_the_chosen_ending_after_the_regions() -> None:
    _, state, _, _ = finished_campaign()
    lines = epilogue_facts(state).lines()
    text = "\n".join(lines)
    assert f"The final choice: {_finale_question()}" in lines
    assert f"The party chose: Silence the song. {SILENCE_TEXT}" in text
    assert LET_TEXT not in text  # the ending not chosen never reaches the epilogue
    assert text.count("was defeated by force.") == 3


def test_facts_tell_each_region_route_and_how_the_side_quests_ended() -> None:
    facts = epilogue_facts(_routes_walked())
    text = "\n".join(facts.lines())
    assert (  # M29.9b T21: an ally sided with the party; the route told by its deeds
        "In Gullmere Quay, Gorran Hookhand was won over and sided with the party, after the"
        " party found the Choir tide-orders at Saltcellar Tunnels, then gave the Choir"
        " tide-orders to Gorran Hookhand." in text
    )
    assert (
        "In The Kelpglass Reach, Cantor Ashmere Voll was defeated by force. Cunning paved the"
        " way first: the party won the fight at Harrowmere Bridge, then met Old Marek"
        " Thistlewood." in text
    )
    assert "joined the party" not in text and "Take the tower unseen" not in text
    assert "Tallow Point was never resolved." in text
    assert "Quest The Missing Ledger: completed." in text
    assert "Quest Break the Smugglers: left behind." in text
    assert "Quest The Warden's Signet: never taken up." in text
    assert "Quest Fog on the Quay: completed." in text  # M29.9b T21: main quests listed too
    assert facts.finale is None


def test_template_epilogue_tells_the_chosen_ending_and_passes_the_guard() -> None:
    _, state, _, _ = finished_campaign()
    facts = epilogue_facts(state)
    text = " ".join(template_epilogue(facts))
    assert f"At the last, the party faced a choice: {_finale_question()}" in text
    assert f"They chose: Silence the song. {SILENCE_TEXT}" in text
    assert not epilogue_checker(state, facts)(text).violations
    sides = " ".join(template_epilogue(epilogue_facts(_routes_walked())))
    # M31.1c V20: the main quests on their own line, then the other quests by outcome
    assert "Main quests: Fog on the Quay (completed), The Kelpglass Reach (completed)." in sides
    assert "Completed quests: The Missing Ledger." in sides
    assert "Left behind: Break the Smugglers." in sides
    assert "Never taken up: The Warden's Signet." in sides


def _quests(state: GameState) -> str:
    section = build_context(state, ContextPurpose.NARRATE).section(SectionKey.QUESTS)
    assert section is not None
    return section.text()


def test_narrator_context_has_the_question_and_no_ending_before_the_choice() -> None:
    _, state, log, _ = finished_campaign(ending=None)
    text = _quests(state)
    assert _finale_question() in text and "never choose for them" in text
    assert '"Silence the song" or "Let the last verse be sung"' in text
    assert SILENCE_TEXT not in text and LET_TEXT not in text
    apply_all(state, [FinaleChosen(option_id="silence-the-song")], log)
    text = _quests(state)
    assert SILENCE_TEXT in text and LET_TEXT not in text


def test_final_resolution_line_ends_on_the_question_and_the_choice_tells_the_ending() -> None:
    _, state, log, _ = finished_campaign(ending=None)
    final = next(e for e in reversed(log) if isinstance(e, RegionResolved))
    fact = event_line(state, final) or ""
    assert "must now choose" in fact and _finale_question() in fact
    assert SILENCE_TEXT not in fact and "do not" not in fact.lower()  # M29.5c G36: facts only
    assert "do not choose for them" in " ".join(event_notes(state, [final]))
    story = template_line(state, final) or ""
    assert story.endswith(_finale_question())
    chosen = FinaleChosen(option_id="silence-the-song")
    apply_all(state, [chosen], log)
    assert SILENCE_TEXT in (event_line(state, chosen) or "")
    assert (template_line(state, chosen) or "").startswith("Silence the song. Break")
