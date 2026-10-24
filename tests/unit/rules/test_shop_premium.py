"""M31.2c premium shop stock: tier 1 shelves unchanged, tier 2-3 shelves hold the dearest goods."""

from __future__ import annotations

import random

from aidm.data.shop_defs import ShopKind, ShopTable
from aidm.rules.shop import shop_stock
from tests.unit.rules.economy_fixtures import CAT, TABLE


def _plain() -> ShopTable:
    kinds = {
        n: ShopKind.model_validate({**k.model_dump(), "premium": {}, "premium_categories": ()})
        for n, k in TABLE.kinds.items()
    }
    return TABLE.model_copy(update={"kinds": kinds})


def _stock(table: ShopTable, kind: str, tier: int, seed: int) -> tuple[str, ...]:
    return tuple(e.item for e in shop_stock(CAT, table, kind, tier, random.Random(seed)))


def test_tier1_stock_is_unchanged() -> None:
    for kind in TABLE.kinds:
        for seed in range(10):
            assert _stock(TABLE, kind, 1, seed) == _stock(_plain(), kind, 1, seed)


def test_tier2_and_3_shops_offer_premium_stock() -> None:
    for kind in ("general", "smith", "alchemist", "scribe"):
        shape = TABLE.kinds[kind]
        for tier in (2, 3):
            for seed in range(10):
                items = [CAT.get(i) for i in _stock(TABLE, kind, tier, seed)]
                dear = [i for i in items if i.tier >= 2]
                assert len(dear) >= shape.premium_picks(tier), (kind, tier, seed)
                assert all(i.tier <= tier for i in items)


def test_golden_armour_prices_srd() -> None:
    # SRD 5.1 Armor table: breastplate 400 gp, half plate 750 gp, splint 200 gp, plate 1500 gp.
    assert CAT.get("breastplate").value_gp == 400
    assert CAT.get("half-plate-armor").value_gp == 750
    assert CAT.get("splint-armor").value_gp == 200
    assert CAT.get("plate-armor").value_gp == 1500


def test_golden_healing_potion_prices() -> None:
    # SRD 5.1 Potion of Healing 50 gp; greater 150, superior 500 (DMG guide).
    assert CAT.get("potion-of-healing").value_gp == 50
    assert CAT.get("potion-of-healing-greater").value_gp == 150
    assert CAT.get("potion-of-healing-superior").value_gp == 500
