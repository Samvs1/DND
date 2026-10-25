"""M31.1b V13-V16 (docs/playtests/M31_round4.md): learning from talk, reports to the giver,
favour places that stay near, and no unchecked step kinds, on the real round-4 states."""

import random
from pathlib import Path

from aidm.dm.quest_text import FAVOUR_ASK_NOTE, QUEST_EVENT_NOTES
from aidm.dm.tool_context import ToolContext, tool_registries
from aidm.dm.tool_exec_quests import run_offer_favour
from aidm.dm.tools import OfferFavourArgs
from aidm.models.campaign import Act, CampaignPlan
from aidm.models.events import AnyEvent
from aidm.models.protocol_client import SubmitAction
from aidm.models.quest_events import LoreLearned, QuestAsked, QuestStepDone
from aidm.models.quests import QuestStep, StepKind
from aidm.models.state import GameState
from aidm.models.world_events import QuestUpdated, SecretRevealed
from aidm.rules.lore import place_lore_events
from aidm.rules.lore_talk import ask_events
from aidm.rules.plan_repair import repair_plan
from aidm.rules.plan_satisfy import unsatisfiable
from aidm.rules.plan_steps import map_steps
from aidm.rules.quest_steps import step_met
from aidm.rules.secrets import fact_words
from aidm.session.reducer import apply
from tests.session.playtest_saves import events_of, logged, replay_until
from tests.session.table_fixtures import assert_replays, join, menu_llm, pick, running

QUESTS = "m31-r4-quests"
FULL = "m31-r4-full"
TYPED = "m31-r4-typed"
ROUND_FOUR = (QUESTS, FULL, TYPED)


def _typed(run: str, seq: int) -> tuple[str, str]:
    event = logged(run, seq).event
    assert event.type == "action_declared"
    return event.creature_id, event.text


async def _send(
    tmp_path: Path, state: GameState, actor: str, text: str, person: str | None = None
) -> list[AnyEvent]:
    """The menu chooser reads the line as talking to `person` (M36.10a; none: a menu label, read
    with no call); the AI is otherwise down."""
    talk = () if person is None else (pick(("talk", [person], None)),)
    llm = menu_llm(tmp_path, *talk, storyteller_down=True)[0]
    async with running(llm, state) as (table, _):
        seat = await join(table, "Ann", actor)
        seat.drain()
        start = table.state.event_count
        seat.send(SubmitAction(text=text))
        await table.settle()
        assert_replays(table)
        return [e.event for e in table.log if e.seq >= start]


def _plan(run: str) -> CampaignPlan:
    return next(e.event.plan for e in events_of(run) if e.event.type == "campaign_installed")


async def test_m31_asking_the_giver_teaches_the_favour(tmp_path: Path) -> None:
    """V13a, quests 225-228: Bramble said what he carries; the model recorded a fact tagged
    `bramble-grief` and the learn step stayed open. Now the ask records the lesson."""
    actor, text = _typed(QUESTS, 227)
    state = replay_until(QUESTS, 227)
    events = await _send(tmp_path, state, actor, text, "bramble-the-kinless")
    learned = [e for e in events if isinstance(e, LoreLearned)]
    assert [(e.tag, e.npc_id) for e in learned] == [("bramble-grief", "bramble-the-kinless")]
    done = [e for e in events if isinstance(e, QuestStepDone) and e.quest_id == "favour-1"]
    assert [e.step for e in done] == [0]


def test_m31_model_fact_tags_never_teach() -> None:
    """V13a, quests 228: the model's fact tagged `bramble-grief` alone does not count."""
    state = replay_until(QUESTS, 230)
    assert any("bramble-grief" in f.tags for f in state.world.facts)
    favour = state.world.quests["favour-1"]
    assert favour.steps_done == 0 and not step_met(state, favour.steps[0], "favour-1")


async def test_m31_friendly_sister_reveals_and_teaches(tmp_path: Path) -> None:
    """V13b, full 543-545: Sister Thena was friendly at deeds 20, yet her secret about Brother
    Mallow stayed hidden and "Learn about mallow" never moved."""
    actor, text = _typed(FULL, 545)
    events = await _send(tmp_path, replay_until(FULL, 545), actor, text, "sister-thena")
    revealed = [e for e in events if isinstance(e, SecretRevealed)]
    assert [e.secret_id for e in revealed] == ["sister-thena-secret-1"]
    learned = [e for e in events if isinstance(e, LoreLearned)]
    assert [(e.tag, e.npc_id) for e in learned] == [("mallow", "sister-thena")]
    route = [e for e in events if isinstance(e, QuestStepDone) and e.quest_id.startswith("main-")]
    assert [(e.route_id, e.step) for e in route][0] == ("the-lullaby-s-leash", 0)


def test_m31_mallow_tells_his_own_story() -> None:
    """V13a, full 643: "Tell us your story, Brother. Who were you?" to Brother Mallow counts."""
    actor, text = _typed(FULL, 643)
    state = replay_until(FULL, 643)
    events = ask_events(state, actor, "boss-the-rotwood-verge", fact_words(text))
    assert [(type(e), getattr(e, "tag", None)) for e in events] == [(LoreLearned, "mallow")]


def _steps(plan: CampaignPlan) -> list[QuestStep]:
    out: list[QuestStep] = []

    def keep(act: Act, owner: str, steps: tuple[QuestStep, ...]) -> tuple[QuestStep, ...]:
        out.extend(steps)
        return steps

    map_steps(plan, keep)
    return out


def test_m31_a_learn_step_only_a_place_teaches_is_a_visit() -> None:
    """V13c, quests 832-834: "Learn about ashword" closed on the arrival at Ashword Priory; its
    only source is the place, so it is now "Go to Ashword Priory"."""
    raw = [s for s in _steps(_plan(QUESTS)) if s.tag == "ashword"]
    assert raw and all(s.kind is StepKind.LEARN for s in raw)
    fixed = [s for s in _steps(repair_plan(_plan(QUESTS), [])) if "ashword-priory" in s.nodes]
    visits = [s for s in fixed if s.kind is StepKind.VISIT]
    assert len(visits) >= len(raw) and {s.text for s in visits} == {"Go to Ashword Priory"}
    assert not [s for s in _steps(repair_plan(_plan(QUESTS), [])) if s.tag == "ashword"]


def test_m31_a_place_teaches_on_a_look_not_on_the_arrival() -> None:
    """V13c, quests 42-52: "Learn about tithing" (taught by The Tithing Shed and by Mirelle's
    secret) closed on the mere arrival. Now the arrival teaches nothing; a look there does."""
    state = replay_until(QUESTS, 46)
    assert state.world.current_node == "the-tithing-shed"
    quest = state.world.quests["the-village-s-next-night"]
    assert not step_met(state, quest.steps[0], quest.id)
    lore = place_lore_events(state, "pc-p2")
    assert lore == [LoreLearned(creature_id="pc-p2", item="The Tithing Shed", tag="tithing")]


def test_m31_come_back_quests_end_with_the_giver() -> None:
    """V14, full 482: "Recover Hallow's ledger" closed on pickup; it now ends with Hallow."""
    fixed = repair_plan(_plan(FULL), [])
    ledger = next(q for q in fixed.quests if q.id == "ledger-of-the-empty-houses")
    assert [(s.kind, s.npc) for s in ledger.steps] == [
        (StepKind.OBTAIN, None),
        (StepKind.MEET, "hallow-draven"),
    ]
    assert ledger.steps[-1].text == "Meet Hallow Draven"


def _favour(state: GameState, **args: object) -> tuple[list[AnyEvent], str | None]:
    model = OfferFavourArgs.model_validate(args)
    result = run_offer_favour(state, model, ToolContext(), random.Random(1), tool_registries())
    return list(result.events), result.summary


def test_m31_a_favour_ends_with_a_report_and_promises_nothing() -> None:
    """V14, quests 817-835: Kreel's "go to the Priory and come back with word" closed on
    arrival, and Kreel promised coin."""
    state = replay_until(QUESTS, 818)
    events, _ = _favour(
        state,
        npc="kreel-the-hunch",
        title="Word of the Priory",
        kind="visit",
        text="Go to Ashword Priory and come back with word of whether its bell still rings.",
        place="ashword-priory",
    )
    quest = next(e for e in events if isinstance(e, QuestUpdated)).quest
    assert [(s.kind, s.nodes, s.npc) for s in quest.steps] == [
        (StepKind.VISIT, ("ashword-priory",), None),
        (StepKind.MEET, (), "kreel-the-hunch"),
    ]
    asked = next(e for e in events if isinstance(e, QuestAsked))
    for event in events:
        state = apply(state, event)
    note = QUEST_EVENT_NOTES[QuestAsked](state, asked)
    assert note == FAVOUR_ASK_NOTE and "no coin" in note


def test_m31_a_favour_never_moves_to_an_unrelated_place() -> None:
    """V15, quests 925-928: "what the ash left in the priory depths" became "Go to Cinder
    Cairn". The words name the priory, where the party stands: the favour is the report."""
    state = replay_until(QUESTS, 925)
    events, _ = _favour(
        state,
        npc="brother-cinder",
        title="Keep the Last Flame Alight",
        kind="visit",
        text="Bring word of what the ash left behind in the priory depths before the dark eats it.",
        place="cinder-cairn",
    )
    quest = next(e for e in events if isinstance(e, QuestUpdated)).quest
    assert [(s.kind, s.npc) for s in quest.steps] == [(StepKind.MEET, "brother-cinder")]


def test_m31_round_four_plans_have_no_unchecked_steps() -> None:
    """V16, quests 694: "Open the unfinished mirror ..." was a `free` step nothing checks."""
    assert "free_step" in {p.code for p in unsatisfiable(_plan(QUESTS))}
    for run in ROUND_FOUR:
        fixed = repair_plan(_plan(run), [])
        assert unsatisfiable(fixed) == [], run
        assert StepKind.FREE not in {s.kind for s in _steps(fixed)}, run
        assert all(q.steps for q in fixed.quests), run


async def test_m31_looking_around_the_place_teaches_it(tmp_path: Path) -> None:
    """V13c: at The Tithing Shed a look around records "tithing" for the quests that ask it."""
    events = await _send(tmp_path, replay_until(QUESTS, 46), "pc-p2", "look around")
    assert [e.tag for e in events if isinstance(e, LoreLearned)] == ["tithing"]
    done = {e.quest_id for e in events if isinstance(e, QuestStepDone)}
    assert "the-village-s-next-night" in done
