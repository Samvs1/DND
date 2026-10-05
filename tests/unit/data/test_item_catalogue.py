"""The item catalogue (SPEC 7.4: >= 80 entries), shop tables and loot tables validate against it."""

from __future__ import annotations

from aidm.data.item_catalogue import (
    ItemCategory,
    item_catalogue,
    key_defs,
    tier_for_value,
)
from aidm.data.loot_defs import loot_tables
from aidm.data.shop_defs import shop_table
from aidm.data.spell_defs import spell_defs
from aidm.dm.tool_context import tool_registries
from aidm.dm.tool_exec_rewards import catalog_value_gp
from aidm.models.dm_tiers import XpTier
from aidm.models.world import FeatureKind
from aidm.rules.scrolls import scroll_item_index, scroll_spell_index

REGS = tool_registries()


def test_item_catalogue_has_at_least_80_entries() -> None:
    assert len(item_catalogue()) >= 80


def test_item_catalogue_covers_every_category() -> None:
    found = {item.category for item in item_catalogue().all()}
    assert found == set(ItemCategory)


def test_item_catalogue_entries_are_well_formed() -> None:
    for item in item_catalogue().all():
        assert item.id == item.index and item.name
        assert item.value_gp >= 0 and item.weight >= 0
        assert item.tier == tier_for_value(item.value_gp)


def test_golden_item_values() -> None:
    # SRD 5.1 Equipment: longsword 15 gp, chain mail 75 gp, plate 1500 gp; Potion of Healing 50 gp.
    cat = item_catalogue()
    assert cat.get("longsword").value_gp == 15
    assert cat.get("chain-mail").value_gp == 75
    assert cat.get("plate-armor").value_gp == 1500
    assert cat.get("potion-of-healing").value_gp == 50
    assert cat.get("potion-of-healing-greater").heal == "4d4+4"


def test_every_entry_is_grantable_by_value() -> None:
    cap = max(REGS.tiers.item_value_cap_gp.values())
    for item in item_catalogue().all():
        value = catalog_value_gp(REGS, item.id)
        assert value is not None and value == item.value_gp
        assert value <= cap, item.id


def test_every_shipped_spell_has_a_scroll() -> None:
    cat = item_catalogue()
    for spell in spell_defs().all():
        item = cat.get(scroll_item_index(spell.index))
        assert item.category is ItemCategory.SCROLL
        assert scroll_spell_index(item.id) == spell.index


def test_camp_supplies_carry_a_supply_value() -> None:
    items = item_catalogue().all()
    supplies = [i for i in items if i.category is ItemCategory.SUPPLY]
    assert len(supplies) >= 3
    assert all(i.supply >= 1 for i in supplies)
    assert all(i.supply == 0 for i in items if i.category is not ItemCategory.SUPPLY)


def test_keys_are_bound_to_feature_kinds() -> None:
    kinds = {k.value for k in FeatureKind}
    assert len(key_defs()) >= 10
    for key in key_defs().all():
        assert set(key.opens) <= kinds
        assert item_catalogue().get(key.index).opens == key.opens


def test_shop_tables_reference_catalogue_items() -> None:
    cat = item_catalogue()
    for kind in shop_table().kinds.values():
        assert all(item in cat for item in kind.always)


def test_loot_tables_reference_catalogue_items() -> None:
    cat = item_catalogue()
    for kinds in loot_tables().tiers.values():
        for table in kinds.values():
            assert all(entry.item in cat for entry in table.items)


def test_quest_gold_covers_every_reward_tier() -> None:
    tiers = REGS.tiers
    for row in tiers.quest_gold_gp.values():
        assert {t.value for t in XpTier} == set(row)
