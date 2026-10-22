"""Where usable gear comes from (M27.10, found by the gear sims): a starting equipment pack is
opened into its SRD contents, and a general store always sells a healer's kit."""

import random

from aidm.data.character_data import character_registries
from aidm.data.item_catalogue import item_catalogue
from aidm.data.shop_defs import shop_table
from aidm.rules.creation import build_character
from aidm.rules.item_use import use_item
from aidm.rules.shop import shop_stock
from tests.unit.rules.creation_fixtures import default_choices
from tests.unit.rules.item_fixtures import CAVE, at, qty

PACKS = (
    "burglars-pack",
    "diplomats-pack",
    "dungeoneers-pack",
    "entertainers-pack",
    "explorers-pack",
    "priests-pack",
    "scholars-pack",
)


def test_m27_starting_pack_holds_its_gear() -> None:
    regs = character_registries()
    fighter = build_character(default_choices("fighter", "human", None), regs, "hero")
    pc = fighter.pc
    assert pc is not None
    held = {e.item: e.qty for e in pc.inventory}
    assert not set(PACKS) & set(held)  # the pack is opened, never carried closed
    # SRD 5.1 Equipment Packs, Dungeoneer's Pack: a backpack, a crowbar, a hammer, 10 pitons,
    # 10 torches, a tinderbox, 10 days of rations, a waterskin and 50 feet of hempen rope.
    assert held["torch"] == 10 and held["piton"] == 10 and held["rations-1-day"] == 10
    for item in ("backpack", "crowbar", "hammer", "tinderbox", "waterskin", "rope-hempen-50-feet"):
        assert held[item] == 1, item
    state = at(CAVE, fighter)  # the pack's torch is usable gear: lit in a dark place
    events = use_item(state, "hero", "torch", None, rng=random.Random(1))
    assert [e.type for e in events][:1] == ["item_used"], events


def test_m27_every_class_pack_opens_into_catalogue_gear() -> None:
    regs = character_registries()
    catalogue = item_catalogue()
    for cls in ("cleric", "rogue", "wizard"):
        hero = build_character(default_choices(cls, "human", None), regs, "hero")
        assert hero.pc is not None
        items = [e.item for e in hero.pc.inventory]
        assert not set(PACKS) & set(items), cls
        assert all(item in catalogue for item in items), cls
    rogue = build_character(default_choices("rogue", "human", None), regs, "hero")
    # SRD 5.1 Burglar's Pack: 2 flasks of oil, 5 candles, a hooded lantern, ball bearings.
    state = at(CAVE, rogue)
    assert qty(state, "hero", "oil-flask") == 2 and qty(state, "hero", "candle") == 5
    assert qty(state, "hero", "lantern-hooded") == 1
    assert qty(state, "hero", "ball-bearings-bag-of-1000") == 1


def test_m27_general_store_always_sells_a_healers_kit() -> None:
    for seed in range(20):
        stock = shop_stock(item_catalogue(), shop_table(), "general", 1, random.Random(seed))
        kit = [s for s in stock if s.item == "healers-kit"]
        assert [s.price_gp for s in kit] == [5], seed  # SRD 5.1 Healer's Kit: 5 gp
