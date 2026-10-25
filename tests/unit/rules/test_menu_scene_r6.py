"""The out-of-fight menu on replayed round-6 states (M36.3, docs/playtests/M34_round6.md Y9, Y13,
Y15). Each state is the table exactly before the typed line of the finding: the menu must offer
the entry the player meant, with the target and the count they named.
"""

from functools import cache

import pytest
from pydantic import ValidationError

from aidm.data.combat_data import combat_registries
from aidm.data.item_catalogue import item_catalogue
from aidm.data.shop_defs import shop_table
from aidm.models.action_menu import ActionKind, ActionMenu, MenuEntry, MenuScope
from aidm.models.world_events import ActionDeclared
from aidm.rules.action_menu import build_menu
from aidm.rules.menu_trade import TradeData
from tests.session.playtest_saves import logged, replay_until

REGS = combat_registries()
TRADE = TradeData(item_catalogue(), shop_table())
TYPED, QUESTS, FULL = "m35-r6-typed", "m35-r6-quests", "m35-r6-full"


@cache
def _menu(run: str, seq: int, actor_id: str) -> ActionMenu:
    return build_menu(replay_until(run, seq), actor_id, REGS, TRADE)


def _entry(menu: ActionMenu, entry_id: str) -> MenuEntry:
    return next(e for e in menu.entries if e.id == entry_id)


def _label(menu: ActionMenu, target_id: str) -> str:
    return next(t.label for t in menu.targets if t.id == target_id)


def test_v1_r6_scene_fixture_lines_are_the_findings() -> None:
    lines = {
        (QUESTS, 563): "Brienne gives Widow Cabrelle a block of incense as a gift for the shrine,"
        " to show respect for her grief.",
        (TYPED, 378): "I cast Sleep on the kobolds behind the spur",
        (TYPED, 750): "Now we go on to the Sunken Vestry door",
        (TYPED, 770): "We leave the vestry and head on to Lamplighters' Rest",
        (TYPED, 797): "I travel to Lamplighters' Rest",
    }
    for (run, seq), text in lines.items():
        event = logged(run, seq).event
        assert isinstance(event, ActionDeclared) and event.text == text


def test_v1_y13_block_of_incense_is_offered_to_the_widow() -> None:
    menu = _menu(QUESTS, 563, "pc-p2")
    assert menu.scope is MenuScope.EXPLORE
    give = _entry(menu, "give:block-of-incense")
    assert give.kind is ActionKind.GIVE and give.item == "block-of-incense"
    assert give.qty_max == 5 and give.max_targets == 1
    assert "widow-cabrelle" in give.target_ids
    assert _label(menu, "widow-cabrelle") == "Widow Cabrelle (Silent keeper of the inn)"


def test_v1_y15_lamplighters_rest_is_a_destination_from_the_vestry() -> None:
    menu = _menu(TYPED, 770, "pc-p2")
    travel = _entry(menu, "travel")
    assert travel.kind is ActionKind.TRAVEL and "lamplighters-rest" in travel.target_ids
    assert _label(menu, "lamplighters-rest") == "Lamplighters' Rest, next door"
    assert "lamplighters-rest" not in travel.target_notes
    assert travel.target_notes["sunken-vestry"] == "you are here"


def test_v1_y15_travel_to_where_the_party_stands_is_you_are_here() -> None:
    rest = _menu(TYPED, 797, "pc-p2")
    assert _entry(rest, "travel").target_notes["lamplighters-rest"] == "you are here"
    assert _label(rest, "lamplighters-rest") == "Lamplighters' Rest, you are here"
    vestry = _menu(TYPED, 750, "pc-p2")
    assert vestry.scope is MenuScope.OFFER
    travel = _entry(vestry, "travel")
    assert travel.target_notes["sunken-vestry"] == "you are here"
    assert travel.target_notes["gullmere-quay-docks"].startswith("the waiting encounter")


def test_menu_locked_way_carries_the_world_reason() -> None:
    travel = _entry(_menu(TYPED, 750, "pc-p2"), "travel")
    assert travel.target_notes["lamplighters-rest"].startswith("The way on")


def test_v1_y9_sleep_strikes_the_waiting_kobolds() -> None:
    menu = _menu(TYPED, 378, "pc-p6")
    assert menu.scope is MenuScope.OFFER
    sleep = _entry(menu, "cast:sleep")
    assert sleep.kind is ActionKind.CAST and sleep.starts_fight
    assert "foe:kobold" in sleep.target_ids and sleep.slot_level == 1
    assert _label(menu, "foe:kobold") == "Kobold x2"
    assert not any(e.id == "cast:sleep" and not e.starts_fight for e in menu.entries)


def test_menu_offer_answers_and_strikes() -> None:
    menu = _menu(TYPED, 750, "pc-p2")
    ids = {e.id for e in menu.entries}
    assert {"offer:fight", "offer:surprise", "offer:escape", "offer:parley:persuasion"} <= ids
    sword = _entry(menu, "attack:longsword")
    assert sword.starts_fight and set(sword.target_ids) == {"boss-gullmere-quay", "foe:cultist"}
    assert _entry(menu, "surrender").skill == "intimidation"
    assert {"search:perception", "search:investigation"} <= ids  # M36.8c: search while foes wait
    assert _entry(menu, "rest:long").note.startswith("a foe waits: it strikes first")


def test_menu_quest_card_answers() -> None:
    menu = _menu(TYPED, 31, "pc-p2")
    accept = _entry(menu, "quest:accept")
    assert accept.quest_id == "missing-ledger" and accept.option == "accept"
    assert "The Missing Ledger" in accept.label and "Tobin Marrow" in accept.label
    assert _entry(menu, "quest:decline").option == "decline"


def test_menu_downed_ally_can_be_helped_up() -> None:
    menu = _menu(FULL, 469, "pc-p2")
    help_up = _entry(menu, "help_up")
    assert help_up.target_ids == ("pc-p8",)
    assert _label(menu, "pc-p8") == "Tamsin, down"
    assert _entry(menu, "put_out").item == "torch"


def test_menu_shop_buy_and_sell_with_counts() -> None:
    menu = _menu(QUESTS, 563, "pc-p2")
    assert _entry(menu, "shop").target_ids == ("halan-s-rest-peddler",)
    potion = _entry(menu, "buy:potion-of-healing")
    assert potion.qty_max == 1 and potion.note == "not enough gold"
    assert _entry(menu, "buy:herbal-poultice").qty_max == 4
    assert _entry(menu, "sell:longsword").note == "unequip it first"
    assert _entry(menu, "pay").qty_max == 45


def test_menu_entry_validators_for_strikes_and_quests() -> None:
    with pytest.raises(ValidationError):
        MenuEntry(id="look", kind=ActionKind.LOOK, label="Look", starts_fight=True)
    with pytest.raises(ValidationError):
        MenuEntry(id="quest:accept", kind=ActionKind.QUEST, label="Accept")
    with pytest.raises(ValidationError):
        MenuEntry(id="talk", kind=ActionKind.TALK, label="Talk", quest_id="q")
