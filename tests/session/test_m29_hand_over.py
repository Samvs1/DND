"""M29.7a R7 / R8 (docs/playtests/M29_round2.md): handing things and coin to another hero, from
the round-2 economy save (p7). A hand-over moves the thing; it is never a use or prose only."""

from pathlib import Path

import pytest

from aidm.data.combat_data import combat_registries
from aidm.dm.fake_llm import FakeStep
from aidm.models.character import Keepsake, PcData
from aidm.models.events import GoldChanged, InventoryChanged
from aidm.models.item_events import HandedOver, ItemUsed
from aidm.models.protocol import AnyClientMsg
from aidm.models.protocol_client import HandOver, SubmitAction
from aidm.models.protocol_server import ErrorMsg
from aidm.models.state import GameState
from aidm.rules.hero_handing import HandRefused, hand_events
from aidm.session.reducer import apply, replay
from tests.session.playtest_saves import replay_until
from tests.session.table_fixtures import (
    assert_replays,
    join,
    menu_llm,
    of_type,
    pick,
    running,
)


async def _typed(
    tmp_path: Path, state: GameState, hero: str, msg: AnyClientMsg, *picks: FakeStep
) -> list[object]:
    """`picks`: the menu chooser's readings of a typed line (M36.10a); the AI is otherwise down."""
    llm = menu_llm(tmp_path, *picks, storyteller_down=True)[0]
    async with running(llm, state) as (table, _):
        seat = await join(table, "Ann", hero)
        start = table.state.event_count
        seat.send(msg)
        await table.settle()
        assert_replays(table)
        errors = of_type(seat.drain(), ErrorMsg)
        return [*errors, *(e.event for e in table.log if e.seq >= start)]


def _pc(state: GameState, hero: str) -> PcData:
    pc = state.creatures[hero].pc
    assert pc is not None
    return pc


def _moved(events: list[object]) -> list[tuple[str, str, int]]:
    return [(e.creature_id, e.item, e.delta) for e in events if isinstance(e, InventoryChanged)]


async def test_m29_hand_poultice_to_a_hero_is_a_hand_over(tmp_path: Path) -> None:
    """p7 64-66: "Brienne hands the Herbal Poultice to Elowen and tells her to keep it" spent it
    on Elowen (full HP, no effect)."""
    text = "Brienne hands the Herbal Poultice to Elowen and tells her to keep it for emergencies."
    hand = pick(("hand:herbal-poultice", ["pc-p4"], 1))
    events = await _typed(
        tmp_path, replay_until("r2-p7", 64), "pc-p2", SubmitAction(text=text), hand
    )
    assert not any(isinstance(e, ItemUsed) for e in events)
    assert _moved(events) == [("pc-p2", "herbal-poultice", -1), ("pc-p4", "herbal-poultice", 1)]


async def test_m29_hand_crowbar_and_gold_between_heroes(tmp_path: Path) -> None:
    """p7 68-69 (the crowbar was prose only) and 289 (no way to pass coin to a friend)."""
    state = replay_until("r2-p7", 68)
    text = "Brienne gives the spare crowbar to Elowen."
    hand = pick(("hand:crowbar", ["pc-p4"], 1))
    events = await _typed(tmp_path, state, "pc-p2", SubmitAction(text=text), hand)
    assert _moved(events) == [("pc-p2", "crowbar", -1), ("pc-p4", "crowbar", 1)]
    state = replay_until("r2-p7", 289)
    have = _pc(state, "pc-p2").gold
    coins = pick(("pay", ["pc-p4"], 5))  # M41.1: the one gold entry
    events = await _typed(
        tmp_path, state, "pc-p2", SubmitAction(text="I give Elowen 5 gold"), coins
    )
    gold = [(e.creature_id, e.delta) for e in events if isinstance(e, GoldChanged)]
    assert gold == [("pc-p2", -5), ("pc-p4", 5)] and have >= 5
    too_much = HandOver(to_id="pc-p4", gold=have + 1000)
    events = await _typed(tmp_path, state, "pc-p2", too_much)
    assert isinstance(events[0], ErrorMsg) and "gold" in events[0].text


async def test_m29_hand_over_message_moves_a_keepsake(tmp_path: Path) -> None:
    state = replay_until("r2-p7", 68)
    brienne = state.creatures["pc-p2"]
    assert brienne.pc is not None
    brienne.pc.keepsakes.append(Keepsake(id="ks-1", name="Old Map"))
    events = await _typed(tmp_path, state, "pc-p2", HandOver(to_id="pc-p4", item_id="ks-1"))
    assert [e.keepsake_id for e in events if isinstance(e, HandedOver)] == ["ks-1"]


def test_m29_hand_over_refuses_only_the_impossible() -> None:
    state = replay_until("r2-p7", 68)
    chars = combat_registries().chars
    events = hand_events(state, "pc-p2", "pc-p4", chars, thing="longsword")
    after = replay(state, events)
    assert _pc(after, "pc-p2").equipped.main_hand is None
    assert any(i.item == "longsword" for i in _pc(after, "pc-p4").inventory)
    dead = state.model_copy(deep=True)
    dead.creatures["pc-p4"].dead = True
    with pytest.raises(HandRefused, match="dead"):
        hand_events(dead, "pc-p2", "pc-p4", chars, thing="crowbar")
    with pytest.raises(HandRefused, match="does not carry"):
        hand_events(state, "pc-p2", "pc-p4", chars, thing="warhammer")
    for event in hand_events(state, "pc-p2", "pc-p4", chars, gold=1):
        apply(state, event)
    assert _pc(state, "pc-p4").gold == 16
