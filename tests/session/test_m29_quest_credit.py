"""M29.7c quest credit (docs/playtests/M29_round2.md R1): a learn step needs a fact the party
learned for it, and a step met by earlier play names what met it. From the live saves."""

from aidm.dm.quest_text import QUEST_EVENT_LINES
from aidm.models.quest_events import QuestStepDone
from aidm.models.quests import QuestStep, StepKind
from aidm.rules.quest_learn import learn_source
from aidm.rules.quest_steps import step_met
from tests.session.playtest_saves import logged, replay_until

LEARN_ASHMEDE = QuestStep(kind=StepKind.LEARN, text="Learn how", tag="ashmede")


def test_m29_learn_step_needs_its_own_fact_p5_ashmede() -> None:
    """p5 242-243: "Learn how the acolytes carry fire between the shrines" (tag ashmede) completed
    at Gallowroot Copse from the party's visit to Ashmede Mill long before."""
    state = replay_until("r2-p5", 243)
    assert "ashmede-mill" in state.world.visited
    assert state.world.current_node == "gallowroot-copse"
    assert learn_source(state, "ashmede") is None
    assert not step_met(state, LEARN_ASHMEDE, "main-hollowhymn-vale")
    state.world.current_node = "ashmede-mill"
    # M31.1b V13c: standing there no longer teaches it; a look around there records it
    assert learn_source(state, "ashmede") is None
    assert not step_met(state, LEARN_ASHMEDE, "main-hollowhymn-vale")
    state.world.learned["ashmede"] = state.event_count
    assert step_met(state, LEARN_ASHMEDE, "main-hollowhymn-vale")


def test_m29_learn_step_old_visit_never_counts_p4_faces() -> None:
    """p4 1654: "Learn which face the Saltwright sold" (tag faces) completed in the Drowned
    Counting House from a visit to the Grotto of Sold Faces earlier."""
    state = replay_until("r2-p4", 1654)
    assert "grotto-of-sold-faces" in state.world.visited
    assert learn_source(state, "faces") is None


def test_m29_met_step_names_what_met_it_p4_accepted_quest() -> None:
    """p4 437-440: accepting A Lighter Chain for the Road completed it at once; the storyteller
    is now told what met each step (a fight won earlier, Farran standing right there)."""
    state = replay_until("r2-p4", 441)
    first, second = logged("r2-p4", 438).event, logged("r2-p4", 439).event
    assert isinstance(first, QuestStepDone) and isinstance(second, QuestStepDone)
    line_one = QUEST_EVENT_LINES[QuestStepDone](state, first)
    line_two = QUEST_EVENT_LINES[QuestStepDone](state, second)
    assert line_one is not None and "the fight at Mock Bell Wharf was won" in line_one
    assert line_two is not None and "the party stands with Farran Dell" in line_two
