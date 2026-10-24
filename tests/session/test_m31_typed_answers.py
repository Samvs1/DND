"""M31.1a V5 and V8 (docs/playtests/M31_round4.md): a surrender demand of foes that never yield,
and a typed answer to a waiting quest offer, on the real round-4 states."""

import random
from pathlib import Path

from aidm.dm.precheck import precheck
from aidm.dm.quest_answer_intent import QuestAnswerIntent
from aidm.dm.tool_context import tool_registries
from aidm.models.abilities import Skill
from aidm.models.events import AnyEvent, CheckResolved, ConditionApplied
from aidm.models.protocol_client import SubmitAction
from aidm.models.protocol_server import Notice
from aidm.models.state import GameState
from aidm.models.world import QuestState
from aidm.rules.surrender import NoneYield, demand_surrender, never_yield_line
from aidm.session import combat_flow
from tests.session.playtest_saves import logged, replay_until
from tests.session.table_fixtures import assert_replays, disabled_llm, join, running

TYPED = "m31-r4-typed"


def _typed(run: str, seq: int) -> tuple[str, str]:
    event = logged(run, seq).event
    assert event.type == "action_declared"
    return event.creature_id, event.text


async def _send(
    tmp_path: Path, state: GameState, actor: str, text: str, *, fight: bool = False
) -> tuple[list[AnyEvent], GameState, list[str]]:
    async with running(disabled_llm(tmp_path), state) as (table, _):
        seat = await join(table, "Ann", actor)
        if fight:
            table.in_combat = True
            table.schedule(lambda: combat_flow.advance(table))
            await table.settle()
        seat.drain()
        start = table.state.event_count
        seat.send(SubmitAction(text=text))
        await table.settle()
        assert_replays(table)
        events = [e.event for e in table.log if e.seq >= start]
        return events, table.state, [m.text for m in seat.drain() if isinstance(m, Notice)]


def test_m31_surrender_of_the_undead_rolls_nothing() -> None:
    """V5, typed 1143: a demand of the undead Tithekeeper rolled a natural 20 that did nothing."""
    state = replay_until(TYPED, 1143)
    tiers = tool_registries().tiers
    line = "The Tithekeeper will not yield: the dead do not surrender."
    assert never_yield_line(state, "pc-p2") == line
    try:
        demand_surrender(random.Random(1), state, "pc-p2", Skill.INTIMIDATION, tiers)
    except NoneYield as none:
        assert none.line == line
    else:
        raise AssertionError("a demand of the undead must roll nothing")


async def test_m31_surrender_of_the_undead_keeps_the_action(tmp_path: Path) -> None:
    actor, text = _typed(TYPED, 1143)
    events, after, notes = await _send(tmp_path, replay_until(TYPED, 1143), actor, text, fight=True)
    assert events == []
    enc = after.encounter
    assert enc is not None and enc.combatants[actor].economy.action
    assert "The Tithekeeper will not yield: the dead do not surrender." in notes


def test_m31_surrender_roll_covers_only_the_foes_that_can_yield() -> None:
    """r4-full 88: a zombie and a cultist; the roll can make only the cultist yield."""
    state = replay_until("m31-r4-full", 88)
    assert (
        never_yield_line(state, "pc-p6") == "The zombie will not yield: the dead do not surrender."
    )
    tiers = tool_registries().tiers
    for seed in range(40):
        events = demand_surrender(random.Random(seed), state, "pc-p6", Skill.PERSUASION, tiers)
        check = next(e for e in events if isinstance(e, CheckResolved))
        if check.result.success:
            held = [e.creature_id for e in events if isinstance(e, ConditionApplied)]
            assert held == ["cultist-1"]
            return
    raise AssertionError("no seed made the check")


def test_m31_typed_yes_accepts_the_quest_offer() -> None:
    """V8, typed 62 and 533: the typed acceptances did not accept; only `answer yes` did."""
    for seq, quest in ((62, "the-settled-ledger"), (533, "favour-1")):
        actor, text = _typed(TYPED, seq)
        found = precheck(replay_until(TYPED, seq), actor, text)
        assert found == QuestAnswerIntent(actor, quest, accept=True)
    state = replay_until(TYPED, 62)
    for line in ("No, we have other business first.", "Not now, Merre", "We'll pass on that"):
        assert precheck(state, "pc-p2", line) == QuestAnswerIntent(
            "pc-p2", "the-settled-ledger", accept=False
        )
    assert precheck(state, "pc-p2", "I ask Merre what the cairn holds") is None


def test_m31_typed_yes_waits_for_a_quest_offer_here() -> None:
    state = replay_until(TYPED, 70)  # the offer was answered at 64: nothing waits
    assert not isinstance(precheck(state, "pc-p2", "Yes, let's go"), QuestAnswerIntent)


async def test_m31_typed_acceptance_makes_the_quest_active(tmp_path: Path) -> None:
    actor, text = _typed(TYPED, 62)
    _, after, _ = await _send(tmp_path, replay_until(TYPED, 62), actor, text)
    assert after.world.quests["the-settled-ledger"].state is QuestState.ACTIVE
    assert after.world.quest_ask is None
