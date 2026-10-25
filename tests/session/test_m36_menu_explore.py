"""Typed lines out of a fight read by the menu chooser at a real table (M36.6, SPEC 6.2; round 6
Y12, Y13, Y14, Y15): the menu chooser, the chooser's pick scripted (FakeLLM
by_tool), the acts run through the button and router runners, every play replayed equal.
"""

import json
from collections.abc import Sequence
from pathlib import Path

from aidm.dm.chooser import CHOOSE_KIND
from aidm.dm.llm_types import LlmMode
from aidm.models.events import CheckResolved, GoldChanged, HpChanged, InventoryChanged
from aidm.models.item_events import HandedOver
from aidm.models.protocol_server import NoticeKind, VoteOpen, WhatNowAnswer
from aidm.models.world_events import (
    ActionDeclared,
    EquipmentChanged,
    ItemRemoved,
    NarrationRecorded,
    QuestUpdated,
    ShopOpened,
)
from aidm.session.menu_pick import NOT_DONE, STOPPED
from aidm.session.session_log import MemoryLog
from tests.session.menu_play import FULL, QUESTS, TYPED, menu_play
from tests.session.table_fixtures import pick

WIDOW, PEDDLER = "widow-cabrelle", "halan-s-rest-peddler"
INCENSE = "block-of-incense"


def _moved(events: Sequence[object], hero: str, item: str) -> list[int]:
    return [
        e.delta
        for e in events
        if isinstance(e, InventoryChanged) and e.creature_id == hero and e.item == item
    ]


async def test_v1_y13_menu_gives_the_widow_a_block_of_incense(tmp_path: Path) -> None:
    """quests 563 "Brienne gives Widow Cabrelle a block of incense ..." (refused in round 6)."""
    played = await menu_play(tmp_path, QUESTS, 563, pick((f"give:{INCENSE}", [WIDOW], None)))
    assert _moved(played.events, "pc-p2", INCENSE) == [-1]
    assert len(played.of(ActionDeclared)) == 1 and played.choose_calls() == 1


async def test_menu_counted_give_then_talk_in_order(tmp_path: Path) -> None:
    line = "I give her three blocks of incense and ask about the bell"
    played = await menu_play(
        tmp_path,
        QUESTS,
        563,
        pick((f"give:{INCENSE}", [WIDOW], 3), ("talk", [WIDOW], None)),
        text=line,
    )
    assert sum(_moved(played.events, "pc-p2", INCENSE)) == -3
    assert [d.text for d in played.of(ActionDeclared)] == [line]


async def test_v1_y12_menu_picks_up_the_three_lumps(tmp_path: Path) -> None:
    """quests 297 "Tamsin picks up the three lumps of Softening Resin": all three, not one."""
    played = await menu_play(tmp_path, QUESTS, 297, pick(("take:softening-resin", [], 3)))
    assert len(played.of(ItemRemoved)) == 3


async def test_v1_y12_menu_draw_sword_and_strap_shield_both_happen(tmp_path: Path) -> None:
    """typed 37 "I draw my sword again and strap the shield back onto my arm"."""
    played = await menu_play(
        tmp_path, TYPED, 37, pick(("equip:longsword", [], None), ("equip:shield", [], None))
    )
    changed = played.of(EquipmentChanged)
    assert len(changed) == 2, played.notices()


async def test_v1_y14_menu_takes_from_tamsins_pack(tmp_path: Path) -> None:
    """full 469: Tamsin is down; her pack's gold and incense can be taken (never refused)."""
    played = await menu_play(
        tmp_path,
        FULL,
        469,
        pick(("loot:gold", ["pc-p8"], 10), (f"loot:{INCENSE}", ["pc-p8"], 2)),
        text="I take ten gold and two blocks of incense from Tamsin's pack",
    )
    handed = played.of(HandedOver)
    assert len(handed) == 2 and all(h.taken for h in handed), played.notices()


async def test_v1_y15_menu_travel_to_where_you_are(tmp_path: Path) -> None:
    """typed 797 "I travel to Lamplighters' Rest" while standing in it: said plainly, no vote."""
    played = await menu_play(tmp_path, TYPED, 797, pick(("travel", ["lamplighters-rest"], None)))
    assert "You are already at Lamplighters' Rest." in played.notices()
    assert not [m for m in played.msgs if isinstance(m, VoteOpen)]


async def test_menu_travel_next_door_opens_the_vote(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path, TYPED, 770, pick(("travel", ["lamplighters-rest"], None)), also=("pc-p4",)
    )
    votes = [m for m in played.msgs if isinstance(m, VoteOpen)]
    assert votes and "Lamplighters" in votes[0].detail


async def test_menu_rest_and_shop_open_votes(tmp_path: Path) -> None:
    rest = await menu_play(tmp_path, QUESTS, 563, pick(("rest:short", [], None)), also=("pc-p4",))
    assert [m for m in rest.msgs if isinstance(m, VoteOpen)]
    shop = await menu_play(tmp_path, QUESTS, 563, pick(("shop", [PEDDLER], None)))
    assert shop.of(ShopOpened) or [m for m in shop.msgs if isinstance(m, VoteOpen)]


async def test_menu_buy_and_sell_at_the_open_shop(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path,
        QUESTS,
        563,
        pick(("buy:herbal-poultice", [], 2), ("sell:crowbar", [], None)),
        text="I buy two poultices and sell my crowbar",
    )
    assert _moved(played.events, "pc-p2", "herbal-poultice") == [2]
    assert _moved(played.events, "pc-p2", "crowbar") == [-1]


async def test_menu_pay_hand_and_lift(tmp_path: Path) -> None:
    pay = await menu_play(tmp_path, QUESTS, 563, pick(("pay", [WIDOW], 5)), text="I pay her 5")
    assert [g.delta for g in pay.of(GoldChanged) if g.creature_id == "pc-p2"] == [-5]
    hand = await menu_play(tmp_path, QUESTS, 563, pick(("hand:torch", ["pc-p4"], 2)))
    assert _moved(hand.events, "pc-p4", "torch") == [2]
    lift = await menu_play(
        tmp_path, QUESTS, 563, pick(("lift:qi-the-swallowed-candle-own-0-0", [WIDOW], None))
    )
    assert [c.creature_id for c in lift.of(CheckResolved)] == ["pc-p2"]  # taking it back: a check


async def test_menu_unequip_and_drop(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path,
        QUESTS,
        563,
        pick(("unequip:shield", [], None), ("drop:piton", [], 2)),
        text="I sling my shield and drop two pitons",
    )
    assert played.of(EquipmentChanged)
    assert sum(_moved(played.events, "pc-p2", "piton")) == -2


async def test_menu_look_search_inventory_and_what_now(tmp_path: Path) -> None:
    look = await menu_play(tmp_path, QUESTS, 563, text="Look around", mode=LlmMode.DISABLED)
    assert look.of(ActionDeclared) and look.choose_calls() == 0
    search = await menu_play(tmp_path, QUESTS, 563, pick(("search:investigation", [], None)))
    assert search.of(ActionDeclared) and search.of(NarrationRecorded)  # nothing hidden here
    pack = await menu_play(tmp_path, QUESTS, 563, pick(("inventory", [], None)), text="my bag?")
    assert any("carries" in n for n in pack.notices()) and not pack.of(ActionDeclared)
    asked = await menu_play(tmp_path, QUESTS, 563, pick(("what_now", [], None)), text="now?")
    assert [m for m in asked.msgs if isinstance(m, WhatNowAnswer)]


async def test_menu_quest_card_and_help_up(tmp_path: Path) -> None:
    """typed 31: the quest card's Accept; full 469: Brienne helps Tamsin up."""
    quest = await menu_play(tmp_path, TYPED, 31, pick(("quest:accept", [], None)))
    assert [u.quest.id for u in quest.of(QuestUpdated)] == ["missing-ledger"]
    up = await menu_play(
        tmp_path, FULL, 469, pick(("help_up", ["pc-p8"], None)), text="I help Tamsin up"
    )
    assert [h.creature_id for h in up.of(HpChanged)] == ["pc-p8"]


async def test_menu_other_out_of_a_fight_is_the_storyteller(tmp_path: Path) -> None:
    line = "I juggle three apples for the widow"
    played = await menu_play(tmp_path, QUESTS, 563, pick(other=line), text=line)
    assert [d.text for d in played.of(ActionDeclared)] == [line]
    assert played.choose_calls() == 1 and len(played.fake.requests) > 1  # then the storyteller


async def test_menu_refused_step_stops_the_rest_out_of_a_fight(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path,
        QUESTS,
        563,
        pick(("pay", [WIDOW], 8), ("pay", [PEDDLER], 5), ("look", [], None)),
        text="I pay the widow eight, the peddler five and look around",
        prep=lambda s: setattr(s.creatures["pc-p2"].pc, "gold", 10),
    )
    assert STOPPED.format(why=NOT_DONE) in played.notices()
    assert [g.delta for g in played.of(GoldChanged)] == [-8]


async def test_menu_chooser_failure_out_of_a_fight_is_the_fallback(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path, QUESTS, 563, text="I ponder the meaning of the bell", mode=LlmMode.DISABLED
    )
    assert NoticeKind.FALLBACK in played.kinds()
    assert not played.events


async def test_menu_chooser_call_is_logged_with_its_kind(tmp_path: Path) -> None:
    await menu_play(tmp_path, QUESTS, 563, pick(("look", [], None)), text="what is here?")
    rows = [json.loads(line) for line in (tmp_path / "llm.jsonl").read_text("utf-8").splitlines()]
    assert [r["kind"] for r in rows].count(CHOOSE_KIND) == 1


async def test_menu_fake_mode_default_pick_is_the_storyteller(tmp_path: Path) -> None:
    """AIDM_FAKE_LLM: with no script FakeLLM's choose_actions default is `other` = the line."""
    line = "I hum an old sea shanty"
    played = await menu_play(tmp_path, QUESTS, 563, text=line)
    assert [d.text for d in played.of(ActionDeclared)] == [line]
    assert played.of(NarrationRecorded) and played.choose_calls() == 1


async def test_menu_colour_is_logged_and_plays_nothing(tmp_path: Path) -> None:
    """M36.9: "kneels before her and gives the widow a block of incense": the give alone plays;
    the colour goes to the menu_choice session line only, never to an act or the storyteller."""
    log = MemoryLog()
    line = "Brienne kneels before her and gives the widow a block of incense"
    played = await menu_play(
        tmp_path,
        QUESTS,
        563,
        pick((f"give:{INCENSE}", [WIDOW], None), colour="kneels before her"),
        text=line,
        log=log,
    )
    assert _moved(played.events, "pc-p2", INCENSE) == [-1]
    adjudicated = [r for r in played.fake.requests if r.tools and r.tool_choice != "choose_actions"]
    assert played.choose_calls() == 1 and not adjudicated  # no storyteller ruling
    rows = log.records("menu_choice")
    assert [(r["steps"], r["other"], r["colour"]) for r in rows] == [
        ([f"give:{INCENSE}"], False, "kneels before her")
    ]
