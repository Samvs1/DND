"""Shops (aidm.rules.shop): deterministic stock, buying, selling at half, typed refusals."""

from __future__ import annotations

import random
from collections.abc import Callable

import pytest

from aidm.models.events import AnyEvent, CampSuppliesChanged, GoldChanged, InventoryChanged
from aidm.models.trade_events import ItemsTraded
from aidm.rules.shop import (
    ShopRefusal,
    ShopRefused,
    buy_events,
    buy_price,
    npc_shop_stock,
    sell_events,
    sell_price,
    shop_kind,
    shop_stock,
)
from tests.unit.rules.economy_fixtures import (
    CAT,
    TABLE,
    apply_events,
    carried,
    gold_of,
    shop_state,
)


def _refusal(call: Callable[[], list[AnyEvent]]) -> ShopRefusal:
    with pytest.raises(ShopRefused) as caught:
        call()
    return caught.value.reason


def test_prices_round_up_for_buying_and_down_for_selling() -> None:
    assert buy_price(0.5, 1, TABLE) == 1
    assert buy_price(15, 2, TABLE) == 30
    assert sell_price(15, 1, TABLE) == 7
    assert sell_price(50, 1, TABLE) == 25
    assert sell_price(0.5, 1, TABLE) == 0


def test_shop_kind_follows_the_role() -> None:
    state = shop_state(role="travelling alchemist")
    assert shop_kind(state.world.npcs["npc-mira"], TABLE) == "alchemist"
    state = shop_state(role="mysterious stranger")
    assert shop_kind(state.world.npcs["npc-mira"], TABLE) == TABLE.default_kind


@pytest.mark.parametrize("kind", sorted(TABLE.kinds))
@pytest.mark.parametrize("tier", [1, 2, 3])
def test_stock_is_deterministic_and_within_the_tier(kind: str, tier: int) -> None:
    first = shop_stock(CAT, TABLE, kind, tier, random.Random("a"))
    again = shop_stock(CAT, TABLE, kind, tier, random.Random("a"))
    assert first == again and first
    assert len({e.item for e in first}) == len(first)
    for entry in first:
        assert entry.price_gp >= 1
        assert CAT.get(entry.item).tier <= tier or entry.item in TABLE.kinds[kind].always


def test_stock_differs_between_seeds() -> None:
    a = shop_stock(CAT, TABLE, "smith", 1, random.Random("a"))
    b = shop_stock(CAT, TABLE, "smith", 1, random.Random("b"))
    assert a != b


def test_npc_stock_is_stable_for_a_campaign() -> None:
    state = shop_state()
    first = npc_shop_stock(state, "npc-mira", CAT, TABLE)
    assert first == npc_shop_stock(state, "npc-mira", CAT, TABLE)


def test_buying_spends_gold_and_adds_the_item() -> None:
    state = shop_state(gold=100)
    before = carried(state, "potion-of-healing")
    events = buy_events(state, "fighter", "npc-mira", "potion-of-healing", 1, CAT, TABLE)
    assert [type(e) for e in events] == [GoldChanged, InventoryChanged, ItemsTraded]
    apply_events(state, events)
    assert gold_of(state) == 50 and carried(state, "potion-of-healing") == before + 1


def test_camp_supplies_are_purchasable_into_the_pool() -> None:
    state = shop_state(gold=100)
    events = buy_events(state, "fighter", "npc-mira", "camp-meal-basket", 2, CAT, TABLE)
    assert any(isinstance(e, CampSuppliesChanged) for e in events)
    apply_events(state, events)
    assert state.camp_supplies == 6 and gold_of(state) == 97
    assert carried(state, "camp-meal-basket") == 0


def test_buying_refusals_are_typed_and_spend_nothing() -> None:
    state = shop_state(gold=10)

    def buy(item: str, qty: int = 1) -> list[AnyEvent]:
        return buy_events(state, "fighter", "npc-mira", item, qty, CAT, TABLE)

    assert _refusal(lambda: buy("potion-of-healing")) is ShopRefusal.NOT_ENOUGH_GOLD
    assert _refusal(lambda: buy("nope")) is ShopRefusal.UNKNOWN_ITEM
    assert _refusal(lambda: buy("potion-of-healing", 0)) is ShopRefusal.BAD_QTY
    stock = {e.item for e in npc_shop_stock(state, "npc-mira", CAT, TABLE)}
    missing = next(i.id for i in CAT.all() if i.id not in stock)
    assert _refusal(lambda: buy(missing)) is ShopRefusal.NOT_IN_STOCK
    assert gold_of(state) == 10


def test_a_closed_or_hostile_shop_refuses() -> None:
    closed = shop_state(open_shop=False)
    assert _refusal(
        lambda: buy_events(closed, "fighter", "npc-mira", "camp-ration", 1, CAT, TABLE)
    ) is (ShopRefusal.CLOSED)
    hostile = shop_state()
    hostile.world.npcs["npc-mira"].hostile = True
    assert _refusal(
        lambda: buy_events(hostile, "fighter", "npc-mira", "camp-ration", 1, CAT, TABLE)
    ) is (ShopRefusal.CLOSED)


def test_selling_pays_half_the_value() -> None:
    state = shop_state(gold=0)
    gain = InventoryChanged(creature_id="fighter", item="restorative-draught", delta=1, qty=1)
    apply_events(state, [gain])
    events = sell_events(state, "fighter", "npc-mira", "restorative-draught", 1, CAT, TABLE)
    apply_events(state, events)
    assert gold_of(state) == 50 and carried(state, "restorative-draught") == 0
    trade = events[-1]
    assert isinstance(trade, ItemsTraded) and trade.sold and trade.gold == 50


def test_selling_refusals() -> None:
    state = shop_state()

    def sell(item: str) -> list[AnyEvent]:
        return sell_events(state, "fighter", "npc-mira", item, 1, CAT, TABLE)

    assert _refusal(lambda: sell("iron-key")) is ShopRefusal.NOT_CARRIED
    assert _refusal(lambda: sell("longsword")) is ShopRefusal.EQUIPPED
    for item in ("plot-gem", "candle"):
        gain = InventoryChanged(creature_id="fighter", item=item, delta=1, qty=1)
        apply_events(state, [gain])
    assert _refusal(lambda: sell("plot-gem")) is ShopRefusal.NOT_TRADABLE
    assert _refusal(lambda: sell("candle")) is ShopRefusal.WORTHLESS
