"""M23.5 the AI follows the quests: the QUESTS section of the ONE context builder, the closed
list of quests in the rules, and the route hint in the hint NPC's private voice data."""

from aidm.dm.context import SectionKey, build_context
from aidm.dm.context_quests import FREE_NOTE, quest_lines, route_hint_lines
from aidm.dm.context_text import ContextPurpose, system_text
from aidm.models.character import Keepsake
from aidm.models.state import GameState
from aidm.models.world_events import QuestUpdated
from aidm.rules.quest_plan import main_world_quest, side_world_quest
from tests.session.progression_fixtures import apply_all, campaign_state, plan
from tests.session.quest_offer_fixtures import accept, fresh, settle, slendee_in_act_two

MAIN = "main-gullmere-quay"
PEACE_TITLE = "Turn Gorran against the Choir"
TIDE = "qi-main-gullmere-quay-the-tide-orders-0-0"


def _quests(state: GameState, purpose: ContextPurpose = ContextPurpose.ADJUDICATE) -> str:
    section = build_context(state, purpose).section(SectionKey.QUESTS)
    assert section is not None
    return section.text()


def _main_only() -> GameState:
    """Installed with only the act-1 main quest (Force known), nobody met yet."""
    _, state, log = campaign_state(offered=False)
    apply_all(state, [QuestUpdated(quest=main_world_quest(plan(), 1))], log)
    return state


def test_main_objective_and_the_force_route_current_step() -> None:
    text = _quests(_main_only())
    assert "Main quest: Fog on the Quay [main-gullmere-quay]: Learn who is dousing" in text
    assert "Known way: Defeat Gorran Hookhand [force]: now: Explore every corner of" in text
    assert "(0/3), step 1 of 2" in text


def test_never_an_undiscovered_route() -> None:
    state = _main_only()
    for purpose in ContextPurpose:
        assert PEACE_TITLE not in build_context(state, purpose).text()
        assert "tide-orders" not in build_context(state, purpose).text()


def test_a_discovered_route_shows_its_step_and_where_its_item_is() -> None:
    _, state, _ = fresh()  # Dessa Orrin (the Peace hint) stands at the arrival: route known
    text = _quests(state)
    assert f"Known way: {PEACE_TITLE} [the-tide-orders]: now: Find the Choir tide-orders" in text
    assert "Choir tide-orders: not found yet" in text  # hidden: never its place
    assert "lies at" not in text
    state.world.items[TIDE].hidden = False
    assert "Choir tide-orders: lies at Saltcellar Tunnels" in _quests(state)
    item = state.world.items.pop(TIDE)
    pc = state.creatures["rogue"].pc
    assert pc is not None
    pc.keepsakes.append(Keepsake(id=item.id, name=item.name, quest_id=item.quest_id))
    assert "Choir tide-orders: carried by" in _quests(state)


def test_the_card_offers_and_an_active_side_quest() -> None:
    _, state, log = fresh()
    text = _quests(state)
    assert "Tobin Marrow is asking now: The Missing Ledger" in text
    assert "Offered (not accepted): The Missing Ledger" not in text  # the card says it once
    accept(state, "missing-ledger", log)
    text = _quests(state)
    line = next(ln for ln in text.splitlines() if "The Missing Ledger" in ln)
    assert line.startswith("- Active side quest: The Missing Ledger [missing-ledger]")
    assert "for Tobin Marrow: Recover the harbour ledger" in line
    assert "now: Win the fight at Saltcellar Tunnels, step 1 of 2" in line


def test_offered_quest_names_its_giver_and_where_they_are() -> None:
    _, state, log = fresh()
    accept(state, "missing-ledger", log)
    planned = next(q for q in plan().quests if q.id == "douse-the-choir")
    apply_all(state, [QuestUpdated(quest=side_world_quest(plan(), planned))], log)
    text = _quests(state, ContextPurpose.NARRATE)
    assert (
        "Offered (not accepted): Break the Smugglers, given by Harbourmaster Odalys Prend" in text
    )
    assert "at Gullmere Quay" in text
    assert "[douse-the-choir]" not in text  # the narrator sees no ids


def test_free_step_is_marked_for_the_adjudicator_only() -> None:
    _, state, log, _ = slendee_in_act_two()
    settle(state, log[-1:], log)
    accept(state, "the-man-in-the-runnel", log)  # old save: [free(objective), meet(giver)]
    lines = quest_lines(state, show_ids=True)
    runnel = next(ln for ln in lines if "[the-man-in-the-runnel]" in ln)
    assert runnel.endswith(FREE_NOTE)
    assert not any(FREE_NOTE in ln for ln in quest_lines(state, show_ids=False))


def test_left_behind_and_finished_quests_are_not_listed() -> None:
    _, state, log, _ = slendee_in_act_two()
    settle(state, log[-1:], log)
    text = _quests(state)
    assert "[main-gloomfen-wetlands]" in text  # the act-2 main quest
    for gone in ("main-thornveil-marches", "a-bell-s-false-tongue", "the-knight-s-penance"):
        assert f"[{gone}]" not in text  # completed, left behind, giver left behind


def test_rules_say_quests_are_a_closed_list() -> None:
    for purpose in ContextPurpose:
        if purpose is ContextPurpose.CHOOSE:  # M36.5: picks menu ids only, never a DM prompt
            continue
        rules = system_text(purpose)
        assert "never invent a task, a reward or a quest item" in rules
        assert "offer_favour" in rules
        assert "next step unless they ask" in rules


def test_hint_npc_voice_knows_the_route() -> None:
    state = _main_only()
    hint = route_hint_lines(state, "dessa-orrin")
    assert len(hint) == 1 and PEACE_TITLE in hint[0] and "tide-orders" in hint[0]
    assert route_hint_lines(state, "tobin-marrow") == []
    voice = build_context(state, ContextPurpose.NPC_VOICE, npc_id="dessa-orrin")
    private = voice.section(SectionKey.NPC_PRIVATE)
    assert private is not None and PEACE_TITLE in private.text()
    other = build_context(state, ContextPurpose.NPC_VOICE, npc_id="tobin-marrow")
    assert PEACE_TITLE not in other.text()
