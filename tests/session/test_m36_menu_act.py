"""The client's `MenuAct` at a real table (M36.11, SPEC 6.2): a button's pick of a menu entry is
played with no model call, checked against the live menu, and keeps the typed line's turn rules.
"""

from pathlib import Path

from aidm.dm.llm_types import LlmMode
from aidm.models.item_events import LightEnded
from aidm.models.protocol_client import MenuAct
from aidm.models.protocol_server import NoticeKind, VoteOpen, WhatNowAnswer
from aidm.models.world_events import ActionDeclared
from aidm.session.fight_text import NOT_YOUR_TURN
from aidm.session.menu_act import NOT_ON_MENU
from tests.session.menu_play import TYPED, menu_play


async def test_menu_act_travel_plays_with_no_model_call(tmp_path: Path) -> None:
    act = MenuAct(entry="travel", targets=("lamplighters-rest",))
    played = await menu_play(tmp_path, TYPED, 770, send=act, also=("pc-p4",), mode=LlmMode.DISABLED)
    votes = [m for m in played.msgs if isinstance(m, VoteOpen)]
    assert votes and "Lamplighters" in votes[0].detail
    assert not played.fake.requests
    declared = [e.text for e in played.of(ActionDeclared)]
    assert declared and declared[0].startswith("Travel to a place")


async def test_menu_act_unknown_entry_is_a_soft_refusal(tmp_path: Path) -> None:
    played = await menu_play(tmp_path, TYPED, 770, send=MenuAct(entry="no-such-entry"))
    assert NOT_ON_MENU in played.notices()
    assert NoticeKind.REFUSED in played.kinds()
    assert not played.events and not played.fake.requests


async def test_menu_act_unknown_target_spends_no_turn(tmp_path: Path) -> None:
    act = MenuAct(entry="travel", targets=("nowhere-at-all",))
    played = await menu_play(tmp_path, TYPED, 770, send=act, also=("pc-p4",))
    assert NOT_ON_MENU in played.notices()
    assert not played.events and not played.fake.requests
    assert not [m for m in played.msgs if isinstance(m, VoteOpen)]


async def test_menu_act_put_out_on_the_turn_in_a_fight(tmp_path: Path) -> None:
    played = await menu_play(tmp_path, TYPED, 435, send=MenuAct(entry="put_out"))
    assert any(e.creature_id == "pc-p2" for e in played.of(LightEnded))
    assert not played.fake.requests


async def test_menu_act_off_turn_in_a_fight_is_not_your_turn(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path, TYPED, 435, send=MenuAct(entry="travel"), actor="pc-p4", also=("pc-p2",)
    )
    assert NOT_YOUR_TURN in played.notices()
    assert not played.events and not played.fake.requests


async def test_menu_act_free_put_out_off_turn_plays(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path, TYPED, 435, send=MenuAct(entry="what_now"), actor="pc-p4", also=("pc-p2",)
    )
    assert any(isinstance(m, WhatNowAnswer) for m in played.msgs)
    assert not played.fake.requests
