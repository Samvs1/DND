"""M32.1b X9 (docs/playtests/M31_round5.md, quests 393-400): the Velde Landing peddler asked the
party to learn "what the fog leaves standing", then taught it herself while saying she had never
gone in to look, and the step read "Learn about fog-leaves-standing". On the real round-5 state:
the asker never teaches their own favour (unless it is their own story), a learn favour needs
another source in the region, and step text shows world words, never a slug."""

from pathlib import Path
from typing import Any

from aidm.dm.event_text import event_line
from aidm.models.quest_events import LoreLearned, QuestStepDone
from aidm.models.quests import QuestStep, StepKind
from aidm.rules.lore_talk import ask_events
from aidm.rules.progression import region_of
from aidm.rules.secrets import fact_words, item_key
from aidm.rules.step_text import state_names, step_text
from tests.ai.tool_fixtures import run_tool
from tests.session.m32_play import QUESTS, play, typed
from tests.session.playtest_saves import replay_until

PEDDLER = "velde-landing-peddler"
FAVOUR: dict[str, Any] = {
    "npc": PEDDLER,
    "title": "What the Fog Leaves Standing",
    "kind": "learn",
    "text": "Go into the Briar-Marches and report back what the fog leaves standing.",
    "tag": "fog-leaves-standing",
}


def test_v1_m32_favour_asker_never_teaches_it() -> None:
    """quests 398-400: asking the peddler herself recorded the lesson and closed the step."""
    actor, text = typed(QUESTS, 398)
    events = ask_events(replay_until(QUESTS, 398), actor, PEDDLER, fact_words(text))
    assert not [e for e in events if isinstance(e, LoreLearned)]


async def test_v1_m32_favour_asker_never_teaches_it_at_the_table(tmp_path: Path) -> None:
    played = await play(tmp_path, QUESTS, 398)
    assert not played.of(LoreLearned)
    assert not [e for e in played.of(QuestStepDone) if e.quest_id == "favour-1"]
    assert played.state.world.quests["favour-1"].steps_done == 0


def test_v1_m32_learn_favour_needs_another_source() -> None:
    """quests 393: nothing in the Briar-Marches but the peddler's word could teach the tag, so
    the favour is refused in words the model can act on; a tag a place holds is fine."""
    state = replay_until(QUESTS, 393)
    refused = run_tool(state, "offer_favour", **FAVOUR)
    assert not refused.ok and "own word" in (refused.error or "")
    region = region_of(state, state.world.current_node)
    assert region is not None
    place = next(n for n in region.nodes() if n.id != state.world.current_node)
    ok = run_tool(state, "offer_favour", **{**FAVOUR, "tag": item_key(place.name)})
    assert ok.ok, ok.error


def test_v1_m32_learn_step_text_in_world_words() -> None:
    state = replay_until(QUESTS, 393)
    names = state_names(state)
    step = QuestStep(kind=StepKind.LEARN, text="-", tag="fog-leaves-standing")
    assert step_text(step, names) == "Learn about fog leaves standing"
    region = region_of(state, state.world.current_node)
    assert region is not None
    place = region.nodes()[1]
    named = QuestStep(kind=StepKind.LEARN, text="-", tag=item_key(place.name))
    assert step_text(named, names) == f"Learn about {place.name}"
    lesson = LoreLearned(creature_id="pc-p6", item="a map", tag="fog-leaves-standing")
    line = event_line(state, lesson)
    assert line is not None and "fog leaves standing" in line and "fog-leaves" not in line
