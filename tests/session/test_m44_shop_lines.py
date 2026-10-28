"""M44.3 round-9 shop and gold lines (docs/playtests/M43_round9.md BB2, BB3, BB12; contract rules
B1, B2): one typed buy is one payment; a stocked item a line names is bought, or refused by the
shop's own rules with the reason, never the storyteller's; a sum of gold the hero cannot pay is
refused first and moves no attitude. Real round-9 lines on fixtures m43-r9-typed and
m43-r9-quests (the seq cited is the line's `line_read`; the play starts at its
`action_declared`, the seq after). FakeLLM picks only, as the save's `line_read` read it."""

from pathlib import Path

from aidm.dm.chooser_menu import menu_lines
from aidm.models.events import GoldChanged
from aidm.models.impossible import ActionImpossible
from aidm.models.item_events import HandedOver
from aidm.models.trade_events import ItemsTraded
from aidm.models.world_events import AttitudeChanged, ShopOpened
from tests.ai.chooser_fixtures import menu_at
from tests.session.menu_play import MenuPlayed, menu_play
from tests.session.table_fixtures import pick

TYPED, QUESTS = "m43-r9-typed", "m43-r9-quests"
BRIENNE, ELOWEN, ROOK, TAMSIN = "pc-p2", "pc-p4", "pc-p6", "pc-p8"
WREN, SUNK = "wrenmarch-village-peddler", "the-sunk-stair-peddler"


def _reasons(played: MenuPlayed) -> list[str]:
    return [e.reason for e in played.of(ActionImpossible)]


def _told(played: MenuPlayed) -> list[object]:
    """The storyteller's rulings on the line (a creative action or talk), the chooser aside."""
    return [r for r in played.fake.requests if r.tools and r.tool_choice != "choose_actions"]


def _gold(played: MenuPlayed) -> list[int]:
    return [e.delta for e in played.of(GoldChanged)]


def _bought(played: MenuPlayed) -> list[tuple[str, int]]:
    return [(e.item, e.qty) for e in played.of(ItemsTraded) if not e.sold]


async def test_v1_m44_buy_and_pay_at_the_peddler_is_one_payment(tmp_path: Path) -> None:
    """r9-quests 618 "Tamsin buys a potion of healing from the peddler for fifty gold" read
    `[buy:potion-of-healing, pay>waspwood-reach-peddler]` and took 50 twice (620, 623-624)."""
    keeper = "waspwood-reach-peddler"
    choice = pick(("buy:potion-of-healing", [], None), ("pay", [keeper], 50))
    played = await menu_play(tmp_path, QUESTS, 619, choice)
    assert _gold(played) == [-50] and _bought(played) == [("potion-of-healing", 1)]
    assert not played.of(HandedOver) and not _reasons(played)
    sheet = played.state.creatures[TAMSIN].pc
    assert sheet is not None and sheet.gold == 54


async def test_v1_m44_pays_the_peddler_for_a_potion_is_one_payment(tmp_path: Path) -> None:
    """r9-typed 285 "Brienne pays the peddler 50 gold for a Potion of Healing" read `buy` +
    `pay>peddler`; the second payment was refused only for lack of gold (290)."""
    choice = pick(("buy:potion-of-healing", [], None), ("pay", [WREN], 50))
    played = await menu_play(tmp_path, TYPED, 286, choice)
    assert _gold(played) == [-50] and _bought(played) == [("potion-of-healing", 1)]
    assert not played.of(HandedOver) and not _reasons(played)


async def test_v1_m44_pays_five_gold_for_a_healers_kit_buys_the_kit(tmp_path: Path) -> None:
    """r9-typed 91 "Tamsin pays the peddler 5 gold for one Healer's Kit" (from Brienne's seat,
    the shop open) read `pay>wrenmarch-village-peddler` + other: 5 gold handed over, no kit."""
    choice = pick(("pay", [WREN], 5), other="for one Healer's Kit")
    played = await menu_play(tmp_path, TYPED, 92, choice)
    assert _gold(played) == [-5] and _bought(played) == [("healers-kit", 1)]
    assert not played.of(HandedOver) and not _told(played)


def _shown_for_sale(seq: int, actor: str, item: str) -> bool:
    """M44.3b: the ware is an ordinary buy entry (no "not enough gold" note) on the menu."""
    entry = next(e for e in menu_at(TYPED, seq, actor).entries if e.id == f"buy:{item}")
    return not entry.note and f"not enough gold: {item}" not in " ".join(
        menu_lines(menu_at(TYPED, seq, actor))
    )


async def test_v1_m44_greater_healing_too_dear_is_no_sale(tmp_path: Path) -> None:
    """r9-typed 1006 "Brienne buys a Potion of Greater Healing" (stocked at 150, Brienne 31 gp,
    the shop open) read `other`: the menu listed it under "not enough gold", the storyteller
    denied the stock and nothing was refused. Now it is an ordinary buy entry; the pick of it is
    refused by the shop's rules with the reason."""
    assert _shown_for_sale(1006, BRIENNE, "potion-of-healing-greater")
    choice = pick(("buy:potion-of-healing-greater", [], None))
    played = await menu_play(tmp_path, TYPED, 1007, choice)
    assert _reasons(played) == ["No sale: 150 gp needed, 31 gp carried."]
    assert not played.of(GoldChanged) and not _told(played)


async def test_v1_m44_scroll_of_revivify_too_dear_is_no_sale(tmp_path: Path) -> None:
    """r9-typed 1546 "Elowen buys a Scroll of Revivify" (stocked at 300 at Ashfall Keep Court,
    Elowen 266 gp) read `other`; told there was no such scroll."""
    assert _shown_for_sale(1546, ELOWEN, "scroll-of-revivify")
    played = await menu_play(tmp_path, TYPED, 1547, pick(("buy:scroll-of-revivify", [], None)))
    assert _reasons(played) == ["No sale: 300 gp needed, 266 gp carried."]
    assert not played.of(GoldChanged) and not _told(played)


async def test_v1_m44_a_stunt_at_a_dear_ware_is_not_refused(tmp_path: Path) -> None:
    """Owner rule (never refuse the possible): at r9-typed 1546 a theft of the Scroll of Revivify
    Elowen cannot afford is a stunt for the storyteller, never a "No sale" refusal."""
    line = "I slip the Scroll of Revivify into my sleeve"
    played = await menu_play(tmp_path, TYPED, 1547, pick(other=line), text=line)
    assert not any(r.startswith("No sale") for r in _reasons(played))
    assert not played.of(GoldChanged) and _told(played)


async def test_v1_m44_buy_at_a_closed_shop_opens_it_then_buys(tmp_path: Path) -> None:
    """r9-typed 1351 "Brienne buys 1 Potion of Greater Healing" (334 gp, the shop closed) read
    `shop>the-sunk-stair-peddler` + other: the shop opened and the buy was lost."""
    line = "Brienne buys 1 Potion of Greater Healing"
    played = await menu_play(tmp_path, TYPED, 1352, pick(("shop", [SUNK], None), other=line))
    assert played.of(ShopOpened)
    assert _gold(played) == [-150] and _bought(played) == [("potion-of-healing-greater", 1)]
    assert not _reasons(played) and not _told(played)


async def test_v1_m44_potion_from_the_closed_peddler_is_bought(tmp_path: Path) -> None:
    """r9-typed 279 "Brienne buys a Potion of Healing from the peddler" (65 gp, the shop
    closed) read `shop>` + other: no buy, the storyteller told an untouched bottle (284)."""
    line = "Brienne buys a Potion of Healing from the peddler"
    played = await menu_play(tmp_path, TYPED, 280, pick(("shop", [WREN], None), other=line))
    assert _gold(played) == [-50] and _bought(played) == [("potion-of-healing", 1)]
    assert not _told(played)


async def test_v1_m44_ten_camp_rations_at_the_closed_shop_are_bought(tmp_path: Path) -> None:
    """r9-typed 938 "Rook buys 10 Camp Rations" read `shop>` + other; the rest was re-sent at
    944. The count said before the ware's name is the count bought."""
    played = await menu_play(
        tmp_path, TYPED, 939, pick(("shop", [WREN], None), other="Rook buys 10 Camp Rations")
    )
    assert _bought(played) == [("camp-ration", 10)] and _gold(played) == [-5]


async def test_v1_m44_unpaid_bribe_moves_no_attitude(tmp_path: Path) -> None:
    """r9-typed 1325 "Elowen offers Nimble Kav 500 gold for what he knows about the barrows"
    (Elowen 43 gp) read talk + other: attitude +10 "offered a large bribe" (1327) and his reply
    (1328) came before the refusal (1329). The refusal comes first and nothing moves."""
    words = "offers Nimble Kav 500 gold for what he knows about the barrows"
    played = await menu_play(
        tmp_path, TYPED, 1326, pick(("talk", ["nimble-kav"], None), other=words)
    )
    assert _reasons(played)[0] == "500 gold: Elowen has only 43 gold."
    assert not played.of(AttitudeChanged) and not played.of(GoldChanged) and not _told(played)
