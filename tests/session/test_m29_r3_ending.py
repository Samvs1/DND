"""M29.9b T21 epilogue facts, T2 clear steps and T13 reading a clue, on the round-3 saves
(docs/playtests/M29_round3.md; tests/session/playtest_saves.py)."""

from aidm.dm.epilogue_facts import epilogue_facts, template_epilogue
from aidm.models.quest_events import LoreLearned
from aidm.models.world import WorldItem
from aidm.models.world_events import KeepsakeGained
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
    assert (  # M31.1c V20: the main quests on their own line
        "Main quests: The Shard in the Mud (completed), The Shard in the Thorns (completed),"
        " The Shard in the Ash (completed). Completed quests: The Widow of the Deep" in text
    )
    assert "Quest The Shard in the Ash: completed." in told


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
