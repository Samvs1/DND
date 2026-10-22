"""grant_item / open_shop / grant_xp on the item catalogue (M5.6)."""

from __future__ import annotations

from aidm.data.item_catalogue import item_catalogue
from aidm.data.item_uses import uses_for_item
from aidm.models.events import CampSuppliesChanged, InventoryChanged, XpGained
from aidm.models.world import FeatureKind, WorldFeature
from aidm.models.world_events import LevelUpReady
from aidm.rules.item_grants import key_fits, party_key_for
from aidm.session.reducer import apply
from tests.ai.tool_fixtures import add_npc, apply_result, party_state, run_tool

CAT = item_catalogue()


def test_every_catalogue_entry_resolves_through_grant_item() -> None:
    """M27.5: every entry without a use is granted; usable gear never is (shops, loot, packs)."""
    state = party_state(1)
    state.world.region_tier = 3
    for item in CAT.all():
        result = run_tool(state, "grant_item", catalog_id=item.id, qty=1)
        if uses_for_item(item.id):
            assert result.error is not None and "usable gear" in result.error, item.id
            continue
        assert result.ok, (item.id, result.error)
        assert result.events


def test_grant_item_refuses_a_scroll_it_is_usable_gear() -> None:
    state = party_state(1)
    result = run_tool(state, "grant_item", catalog_id="scroll-of-fire-bolt", qty=1)
    assert result.error is not None and result.events == ()
    potion = run_tool(state, "grant_item", catalog_id="potion-of-healing", qty=1)
    event = potion.events[0]
    assert isinstance(event, InventoryChanged) and event.item == "potion-of-healing"


def test_grant_item_camp_supplies_feed_the_pool() -> None:
    state = party_state(1)
    result = run_tool(state, "grant_item", catalog_id="camp-meal-basket", qty=2)
    assert [type(e) for e in result.events] == [CampSuppliesChanged]
    apply_result(state, result)
    assert state.camp_supplies == 6


def test_grant_item_still_respects_the_tier_cap() -> None:
    state = party_state(1)
    refused = run_tool(state, "grant_item", catalog_id="plate-armor", qty=1)
    assert refused.error is not None and "cap" in refused.error


def test_open_shop_lists_the_stock_with_prices() -> None:
    state = party_state(1)
    add_npc(state, "npc-mira", name="Mira", role="apothecary")
    result = run_tool(state, "open_shop", npc="npc-mira")
    assert result.ok and "potion-of-healing (50 gp)" in result.summary
    apply_result(state, result)
    assert state.world.shop_npc_id == "npc-mira"


def test_grant_xp_flags_the_level_up() -> None:
    state = party_state(1)
    result = run_tool(state, "grant_xp", tier="major")
    assert [e.amount for e in result.events if isinstance(e, XpGained)] == [150] * 4
    assert not any(isinstance(e, LevelUpReady) for e in result.events)
    for pc_id in ("fighter", "rogue", "wizard", "cleric"):
        apply(state, XpGained(creature_id=pc_id, amount=200, xp=200))
    again = run_tool(state, "grant_xp", tier="major")
    ups = [e for e in again.events if isinstance(e, LevelUpReady)]
    assert len(ups) == 4 and all(e.level == 2 for e in ups)


def test_keys_fit_the_feature_kinds_they_are_bound_to() -> None:
    state = party_state(1)
    door = WorldFeature(id="feat-door", kind=FeatureKind.DOOR, name="Cellar door")
    chest = WorldFeature(id="feat-chest", kind=FeatureKind.CONTAINER, name="Sea chest")
    assert key_fits(CAT, "iron-key", door) and not key_fits(CAT, "iron-key", chest)
    assert key_fits(CAT, "skeleton-key", chest)
    assert not key_fits(CAT, "longsword", door)
    apply_result(state, run_tool(state, "grant_item", catalog_id="chest-key", qty=1))
    assert party_key_for(state, door, CAT) is None
    assert party_key_for(state, chest, CAT) == "chest-key"
