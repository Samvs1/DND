"""M31.1a V5 and V8 (docs/playtests/M31_round4.md): a surrender demand of foes that never yield,
and a typed answer to a waiting quest offer, on the real round-4 states."""

import random
from collections.abc import Sequence
from pathlib import Path

from aidm.dm.fake_llm import FakeStep
from aidm.dm.tool_context import tool_registries
from aidm.models.abilities import Skill
from aidm.models.campaign_events import OfferResolved
from aidm.models.campaign_state import OfferChoice
from aidm.models.events import AnyEvent, CheckResolved, ConditionApplied
from aidm.models.protocol_client import CancelHostile, ConfirmHostile, SubmitAction
from aidm.models.protocol_server import Notice, PendingConfirmationMsg
from aidm.models.state import GameState
from aidm.models.world import QuestState
from aidm.rules.surrender import NoneYield, demand_surrender, never_yield_line
from aidm.session import combat_flow
from aidm.session.held import PARLEY_ASK, PARLEY_STAY
from tests.session.playtest_saves import logged, replay_until
from tests.session.table_fixtures import (
    assert_replays,
    disabled_llm,
    join,
    menu_down,
    menu_llm,
    pick,
    running,
)

TYPED = "m31-r4-typed"
QUESTS = "m31-r4-quests"


def _typed(run: str, seq: int) -> tuple[str, str]:
    event = logged(run, seq).event
    assert event.type == "action_declared"
    return event.creature_id, event.text


async def _send(
    tmp_path: Path,
    state: GameState,
    actor: str,
    text: str,
    *,
    fight: bool = False,
    picks: Sequence[FakeStep] | None = None,
) -> tuple[list[AnyEvent], GameState, list[str]]:
    """M36.10a: `picks` plays at the menu interpreter (the chooser's readings scripted, every
    other AI call failing as with no key)."""
    llm = disabled_llm(tmp_path)
    if picks is not None:
        llm = menu_llm(tmp_path, *picks, storyteller_down=True)[0]
    async with running(llm, state) as (table, _):
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
    demand = pick(("surrender:intimidation", [], None))  # the menu chooser's (M36.10b)
    state = replay_until(TYPED, 1143)
    events, after, notes = await _send(tmp_path, state, actor, text, fight=True, picks=[demand])
    assert [e.type for e in events] == ["action_declared"]  # the words only: no roll, no cost
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


async def test_m31_typed_acceptance_makes_the_quest_active(tmp_path: Path) -> None:
    actor, text = _typed(TYPED, 62)
    accept = pick(("quest:accept", [], None))  # the quest card's Accept, read from the menu
    _, after, _ = await _send(tmp_path, replay_until(TYPED, 62), actor, text, picks=[accept])
    assert after.world.quests["the-settled-ledger"].state is QuestState.ACTIVE
    assert after.world.quest_ask is None


PERSUADE = pick(("offer:parley:persuasion", [], None))


async def test_m31_typed_parley_asks_before_the_roll(tmp_path: Path) -> None:
    actor, text = _typed(TYPED, 113)
    parley = menu_down(tmp_path, PERSUADE)  # the menu chooser's (M36.10b)
    async with running(parley, replay_until(TYPED, 113)) as (table, _):
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
    parley = menu_down(tmp_path, PERSUADE)  # the menu chooser's (M36.10b)
    async with running(parley, replay_until(QUESTS, 373)) as (table, _):
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
