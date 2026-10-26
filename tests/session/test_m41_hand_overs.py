"""M41.1 (docs/playtests/M39_round7.md Z3, Z4, Z8): gold to another hero, a sum over the purse and
a counted hand-over, on the real round-7 state (fixture m39-r7-typed = r7b-typed), the chooser's
pick scripted (FakeLLM) and the storyteller down, so only the engine's own paths act.

Causes found (the menu the chooser saw, rebuilt at each seq): Z3 the hero-to-hero gold entry
`hand:gold` sat in the `hand:<item>` group (gold one of the ITEMS) while the only gold line was
`pay = Pay gold to someone here -> <the person>`: "gives Elowen 3 gold" read as a pay at a hero,
which no entry took, so `other`. Z4 the gold entry was marked "up to 60", read as a cap: 500 was
sent as 60. Z8 the count of an ITEMS item is written on the ITEMS line, and rule 10 asked for a
qty only on an entry marked "up to N"."""

from pathlib import Path

from aidm.dm.choice_tool import choice_tool
from aidm.dm.chooser_menu import COIN_QTY, menu_lines
from aidm.dm.chooser_prompt import choose_system
from aidm.models.events import AnyEvent, GoldChanged
from aidm.models.impossible import ActionImpossible
from aidm.models.item_events import HandedOver
from tests.ai.chooser_fixtures import menu_at
from tests.session.m32_play import play
from tests.session.table_fixtures import pick

TYPED = "m39-r7-typed"
WREN = "cornet-wren"


def _gold(played_events: list[AnyEvent]) -> list[tuple[str, int]]:
    return [(e.creature_id, e.delta) for e in played_events if isinstance(e, GoldChanged)]


def test_v1_m41_one_gold_entry_takes_every_receiver() -> None:
    """r7b-typed 36 "Brienne gives Elowen 3 gold": one gold entry for the person and the heroes,
    shown on its own line, gold no longer one of the ITEMS."""
    menu = menu_at(TYPED, 36, "pc-p2")
    gold = [e for e in menu.entries if e.id == "pay"]
    assert [e.id for e in menu.entries if e.id == "hand:gold"] == []
    assert len(gold) == 1 and set(gold[0].target_ids) == {"warden-pike", "pc-p4", "pc-p6", "pc-p8"}
    lines = menu_lines(menu)
    assert any(ln.startswith("pay = Pay or hand gold") and COIN_QTY in ln for ln in lines)
    assert not any("gold (up to" in ln or "except gold" in ln for ln in lines)


async def test_v1_m41_gold_to_a_hero_moves(tmp_path: Path) -> None:
    """r7b-typed 36: the pick at the hero hands the coins over (it moved nothing in round 7)."""
    played = await play(tmp_path, TYPED, 36, picks=[pick(("pay", ["pc-p4"], 3))])
    assert _gold(played.events) == [("pc-p2", -3), ("pc-p4", 3)]
    assert [(e.to_id, e.gold) for e in played.of(HandedOver)] == [("pc-p4", 3)]


async def test_v1_m41_paying_a_hero_is_a_hand_over(tmp_path: Path) -> None:
    """r7b-typed 147 "Elowen pays Brienne 7 gold" (while Oza's shop was open)."""
    played = await play(tmp_path, TYPED, 147, picks=[pick(("pay", ["pc-p2"], 7))])
    assert _gold(played.events) == [("pc-p4", -7), ("pc-p2", 7)]


def test_v1_m41_a_sum_over_the_purse_passes_the_tool() -> None:
    """r7b-typed 1249 "Elowen pays Wren 500 gold" with 60 carried: the tool takes 500 as said
    (the rules answer it), the menu never asks for a cap."""
    menu = menu_at(TYPED, 1249, "pc-p4")
    args = choice_tool(menu).args_model.model_validate(
        {"steps": [{"do": "pay", "to": [WREN], "qty": 500}], "other": None, "colour": ""}
    )
    assert args.model_dump()["steps"][0]["qty"] == 500
    assert any(ln.startswith("pay = ") and "up to" not in ln for ln in menu_lines(menu))


async def test_v1_m41_paying_more_than_carried_is_refused_with_the_reason(tmp_path: Path) -> None:
    """r7b-typed 1249-1251 took all 60: now nothing moves and the story tells the reason."""
    played = await play(tmp_path, TYPED, 1249, picks=[pick(("pay", [WREN], 500))])
    assert not played.of(GoldChanged) and not played.of(HandedOver)
    assert [e.reason for e in played.of(ActionImpossible)] == ["Elowen has only 60 gold."]
    assert "Elowen has only 60 gold" in played.told()
    elowen = played.state.creatures["pc-p4"]
    assert elowen.pc is not None and elowen.pc.gold == 60


async def test_v1_m41_handing_a_hero_more_than_carried_is_told(tmp_path: Path) -> None:
    """r7b-typed 38 "Brienne gives Elowen 50 gold" with 15 carried."""
    played = await play(tmp_path, TYPED, 38, picks=[pick(("pay", ["pc-p4"], 50))])
    assert not played.of(GoldChanged)
    assert [e.reason for e in played.of(ActionImpossible)] == ["Brienne has only 15 gold."]
    assert "Brienne has only 15 gold" in played.told()


async def test_v1_m41_a_counted_hand_over_moves_the_count(tmp_path: Path) -> None:
    """Z8 (aborted r7-full 32 "two of the camp rations" moved 1) on a committed line of the
    same shape, r7b-typed 42 "Brienne hands Rook two of her torches": the count moves."""
    played = await play(tmp_path, TYPED, 42, picks=[pick(("hand:torch", ["pc-p6"], 2))])
    assert [(e.to_id, e.item, e.qty) for e in played.of(HandedOver)] == [("pc-p6", "torch", 2)]


def test_v1_m41_rule_ten_asks_the_count_of_an_items_item() -> None:
    """Z8: the count of a grouped item is written on the ITEMS line, so rule 10 names it."""
    assert 'qty only for an entry or item marked "up to N"' in choose_system("player_action")
