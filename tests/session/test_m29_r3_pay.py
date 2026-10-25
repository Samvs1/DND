"""M29.9a T17: paying an NPC is a real engine action (docs/playtests/M29_round3.md), reproduced
from the r3-full save (tests/session/playtest_saves.py)."""

import random

import pytest

from aidm.dm.precheck import precheck
from aidm.dm.tool_context import ToolContext, tool_registries
from aidm.dm.tool_exec_quests import run_offer_favour
from aidm.dm.tools import FavourKind, OfferFavourArgs
from aidm.models.events import GoldChanged
from aidm.models.item_events import HandedOver
from aidm.models.quests import StepKind
from aidm.models.world_events import QuestUpdated
from aidm.rules.acts import PayIntent
from aidm.rules.paying import PayRefused, gold_for, pay_events
from aidm.rules.quest_steps import step_met
from aidm.session.reducer import apply
from tests.session.playtest_saves import replay_until

RUTTER = "rutter-the-gap"


def test_m29_hand_rutter_a_gold_piece_pays_him() -> None:
    """r3-full 468: "Brienne hands Rutter the Gap 1 gold piece" was refused as a thing not
    carried. It is a payment now: the coin leaves Brienne and Rutter holds it."""
    state = replay_until("r3-full", 468)
    text = "Brienne hands Rutter the Gap 1 gold piece for the crossing and boards the boat."
    intent = precheck(state, "pc-p2", text)
    assert isinstance(intent, PayIntent)
    assert intent == PayIntent("pc-p2", RUTTER, 1, "boards the boat")
    brienne = state.creatures["pc-p2"]
    assert brienne.pc is not None
    before = brienne.pc.gold
    events = pay_events(state, "pc-p2", RUTTER, intent.gold)
    assert [type(e) for e in events] == [GoldChanged, HandedOver]
    for event in events:
        apply(state, event)
    assert brienne.pc.gold == before - 1
    assert state.world.npcs[RUTTER].paid == 1


def test_m29_pay_phrases_and_silver_rounding() -> None:
    """r3-full 41 and 466: "pays Rutter the Gap for a crossing", "counts out four silver for
    Rutter". Silver rounds up to whole gold as the shop does (4 sp -> 1 gp)."""
    state = replay_until("r3-full", 41)
    cases = {
        "I pay Rutter the Gap for a crossing and ask him about the drowned girl.": 1,
        "Brienne counts out four silver for Rutter the Gap and asks him to row us out.": 1,
        "I pay Rutter 12 gold": 12,
        "I give Rutter 25 silver pieces": 3,
        "give 3 gp to Rutter the Gap": 3,
    }
    for text, gold in cases.items():
        intent = precheck(state, "pc-p2", text)
        assert isinstance(intent, PayIntent) and intent.npc_id == RUTTER, text
        assert intent.gold == gold, text
    assert gold_for(150, "copper") == 2
    assert precheck(state, "pc-p2", "I pay attention to the water") is None


def test_m29_pay_refused_only_without_the_gold() -> None:
    state = replay_until("r3-full", 41)
    brienne = state.creatures["pc-p2"]
    assert brienne.pc is not None
    with pytest.raises(PayRefused, match=f"has only {brienne.pc.gold} gold"):
        pay_events(state, "pc-p2", RUTTER, brienne.pc.gold + 1)


def test_m29_pay_favour_counts_new_coins_only() -> None:
    """A favour that asks for payment is a `pay` step: it waits for the price on top of what
    the NPC had already been paid, and a payment to that NPC meets it."""
    state = replay_until("r3-full", 41)
    for event in pay_events(state, "pc-p2", RUTTER, 2):  # an earlier payment never counts
        apply(state, event)
    args = OfferFavourArgs(
        npc=RUTTER,
        title="Coin for the crossing",
        kind=FavourKind.PAY,
        text="Pay Rutter 4 gold for the crossing",
        target_npc=RUTTER,
        gold=4,
    )
    ctx = ToolContext(actor_id="pc-p2")
    result = run_offer_favour(state, args, ctx, random.Random(1), tool_registries())
    quest = next(e.quest for e in result.events if isinstance(e, QuestUpdated))
    step = quest.steps[0]
    assert (step.kind, step.npc, step.gold) == (StepKind.PAY, RUTTER, 6)
    for event in result.events:
        apply(state, event)
    assert not step_met(state, step, quest.id)
    for event in pay_events(state, "pc-p2", RUTTER, 4):
        apply(state, event)
    assert step_met(state, step, quest.id)
