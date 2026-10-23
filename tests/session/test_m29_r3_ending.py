"""M29.9b T21 epilogue facts, T2 clear steps and T13 reading a clue, on the round-3 saves
(docs/playtests/M29_round3.md; tests/session/playtest_saves.py)."""

import random

from aidm.dm.epilogue_facts import epilogue_facts, template_epilogue
from aidm.dm.precheck import precheck
from aidm.dm.use_intent import UseIntent
from aidm.models.character import Keepsake
from aidm.models.quest_events import LoreLearned
from aidm.models.quests import StepKind
from aidm.models.world import WorldItem
from aidm.models.world_events import KeepsakeGained
from aidm.rules.item_use import use_item
from aidm.rules.plan_repair import repair_plan
from aidm.rules.quest_plan import main_quest
from aidm.rules.quest_steps import step_met
from aidm.session.reducer import apply
from tests.ai.tool_fixtures import party_state, run_tool
from tests.session.playtest_saves import replay_until


def test_m29_ending_tells_engine_facts_full() -> None:
    """r3-full 1735: Voss and Ulva "joined the party" (allies; the party stayed four), "Cunning
    paved the way first: Drown the Furnace" named the model's route title (the deed was the
    Slag Warren fight), and the three main quests were missing from "Completed quests"."""
    state = replay_until("r3-full", 1735)
    facts = epilogue_facts(state)
    text = " ".join(template_epilogue(facts))
    told = "\n".join(facts.lines())
    for written in (text, told):
        assert "joined the party" not in written
        assert "Drown the Furnace" not in written
    assert "High Lector Orlan Voss was won over and sided with the party" in text
    assert "Legion-Captain Ulva the Guilted was won over and sided with the party" in text
    assert "Cunning paved the way first: the party won the fight at The Slag Warren." in text
    assert (
        "Completed quests: The Shard in the Mud, The Shard in the Thorns, The Shard in the Ash,"
        " The Widow of the Deep" in text
    )
    assert "Quest The Shard in the Ash: completed." in told


def test_m29_clear_steps_never_name_foes_casters() -> None:
    """r3-casters 4, 821, 938: "Win the fight at Weeping Bastion (wight, ghast)" while a bugbear
    stand-in was fielded; who is there comes only from the actual offer."""
    state = replay_until("r3-casters", 40)
    assert state.campaign is not None
    plan = repair_plan(state.campaign.plan, [])
    route = main_quest(plan, 2).route("starving-the-choir")
    assert route is not None
    assert [s.text for s in route.steps] == [
        "Win the fight at Weeping Bastion",
        "Win the fight at Saltmere Cellars",
    ]
    clears = [
        s
        for a in plan.acts
        for r in (a.main.routes if a.main else ())
        for s in r.steps
        if s.kind is StepKind.CLEAR
    ]
    assert clears and all("(" not in s.text for s in clears)


def test_m29_reading_a_clue_records_the_lesson_items() -> None:
    """r3-items 729: "I read the Spore-Ink Note carefully and say aloud what it says" went to a
    plain check. Reading a clue the hero carries is a use of it (the ONE item interpreter):
    one `LoreLearned`, and the rest of the sentence goes on to the storyteller."""
    state = replay_until("r3-items", 729)
    elowen = state.creatures["pc-p4"]
    assert elowen.pc is not None
    note = next(k for k in elowen.pc.keepsakes if k.name == "Spore-Ink Note")
    elowen.pc.keepsakes[elowen.pc.keepsakes.index(note)] = Keepsake(
        id=note.id, name=note.name, description=note.description, teaches="blackpine"
    )
    text = "I read the Spore-Ink Note carefully and say aloud what it says"
    intent = precheck(state, "pc-p4", text)
    assert isinstance(intent, UseIntent)
    assert intent == UseIntent("pc-p4", note.name, verb="read", rest="say aloud what it says")
    events = use_item(state, "pc-p4", intent.item, rng=random.Random(1))
    assert events == [LoreLearned(creature_id="pc-p4", item="Spore-Ink Note", tag="blackpine")]
    elowen.pc.keepsakes.clear()  # handed over later (745): the recorded lesson stays
    quest = state.world.quests["the-archivist-is-missing"]
    learn = quest.steps[1]
    assert not step_met(state, learn, quest.id)
    for event in events:
        apply(state, event)
    assert state.world.learned["blackpine"] == state.event_count - 1
    assert step_met(state, learn, quest.id)
    assert not isinstance(precheck(state, "pc-p4", text), UseIntent)  # no clue carried now


def test_m29_taking_up_a_placed_clue_records_the_lesson() -> None:
    """A plan clue (`WorldItem.teaches`) picked up becomes a clue keepsake: one `LoreLearned`."""
    state = party_state()
    state.world.items["clue"] = WorldItem(
        id="clue", name="Notes on Thaw", node_id="town", quest_id="q", teaches="thaw"
    )
    result = run_tool(state, "take_item", item_id="clue")
    assert result.error is None
    assert result.events[-1] == LoreLearned(creature_id="fighter", item="Notes on Thaw", tag="thaw")
    gained = next(e for e in result.events if isinstance(e, KeepsakeGained))
    assert gained.keepsake.teaches == "thaw"
