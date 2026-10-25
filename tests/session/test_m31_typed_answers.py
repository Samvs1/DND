"""M31.1a V5 and V8 (docs/playtests/M31_round4.md): a surrender demand of foes that never yield,
and a typed answer to a waiting quest offer, on the real round-4 states."""

import random
from pathlib import Path

from aidm.dm.precheck import precheck
from aidm.dm.tool_context import tool_registries
from aidm.models.abilities import Skill
from aidm.models.campaign_events import OfferResolved
from aidm.models.campaign_state import OfferChoice
from aidm.models.events import AnyEvent, CheckResolved, ConditionApplied
from aidm.models.protocol_client import CancelHostile, ConfirmHostile, SubmitAction
from aidm.models.protocol_server import Notice, PendingConfirmationMsg
from aidm.models.state import GameState
from aidm.models.world import QuestState
from aidm.rules.acts import ParleyIntent, QuestAnswerIntent
from aidm.rules.surrender import NoneYield, demand_surrender, never_yield_line
from aidm.session import combat_flow
from aidm.session.held import PARLEY_ASK, PARLEY_STAY
from tests.session.playtest_saves import logged, replay_until
from tests.session.table_fixtures import assert_replays, disabled_llm, join, running

TYPED = "m31-r4-typed"
QUESTS = "m31-r4-quests"


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


def test_m31_peaceful_words_to_the_foes_are_a_parley() -> None:
    """V4, typed 113: "Easy now, friend in the robe ... we don't want a fight" got a model
    check and left the offer open."""
    actor, text = _typed(TYPED, 113)
    state = replay_until(TYPED, 113)
    assert precheck(state, actor, text) == ParleyIntent(actor, Skill.PERSUASION)
    # a bystander named (Sister Mareld, the shrine-warden) is talk, the offer keeps waiting (T16)
    for line in ("Easy now, Sister Mareld, we don't want a fight", "Mareld, what are those?"):
        assert precheck(state, actor, line) is None


def test_m31_question_to_the_named_master_is_a_parley() -> None:
    """V4, quests 373: a question to Grinner Voss, the master, answers the offer as parley."""
    actor, text = _typed(QUESTS, 373)
    state = replay_until(QUESTS, 373)
    assert precheck(state, actor, text) == ParleyIntent(actor, Skill.PERSUASION)
    asked = precheck(state, actor, "Grinner Voss, what does the Silent Company collect?")
    assert asked == ParleyIntent(actor, Skill.PERSUASION)


async def test_m31_typed_parley_asks_before_the_roll(tmp_path: Path) -> None:
    actor, text = _typed(TYPED, 113)
    async with running(disabled_llm(tmp_path), replay_until(TYPED, 113)) as (table, _):
        seat = await join(table, "Ann", actor)
        seat.drain()
        start = table.state.event_count
        seat.send(SubmitAction(text=text))
        await table.settle()
        asked = [m.prompt for m in seat.drain() if isinstance(m, PendingConfirmationMsg)]
        assert asked == [PARLEY_ASK]
        assert table.state.campaign is not None and table.state.campaign.offer is not None
        seat.send(ConfirmHostile())
        await table.settle()
        assert_replays(table)
        events = [e.event for e in table.log if e.seq >= start]
    resolved = [e.choice for e in events if isinstance(e, OfferResolved)]
    assert resolved == [OfferChoice.PARLEY]
    checks = [e for e in events if isinstance(e, CheckResolved)]
    assert [(c.reason, c.result.skill) for c in checks] == [("parley", "persuasion")]


async def test_m31_typed_parley_cancelled_leaves_the_offer(tmp_path: Path) -> None:
    actor, text = _typed(QUESTS, 373)
    async with running(disabled_llm(tmp_path), replay_until(QUESTS, 373)) as (table, _):
        seat = await join(table, "Ann", actor)
        seat.send(SubmitAction(text=text))
        await table.settle()
        seat.drain()
        seat.send(CancelHostile())
        await table.settle()
        notes = [m.text for m in seat.drain() if isinstance(m, Notice)]
        offer = table.state.campaign.offer if table.state.campaign is not None else None
        assert_replays(table)
    assert offer is not None and table.pending is None
    assert notes == [PARLEY_STAY]
