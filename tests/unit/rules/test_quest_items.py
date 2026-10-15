"""M23.3 quest items: placed in the world per act (visible or hidden), idempotent, found by search,
picked up as keepsakes with their quest, never sold or dropped, handed over through ONE path."""

import pytest

from aidm.dm.tool_context import tool_registries
from aidm.models.abilities import Ability, Skill
from aidm.models.character import Keepsake
from aidm.models.checks import CheckKind, CheckResult
from aidm.models.dice import AdvState, D20Roll
from aidm.models.events import AnyEvent, InventoryChanged
from aidm.models.quest_events import KeepsakeGiven
from aidm.models.state import GameState
from aidm.models.world_events import (
    AttitudeChanged,
    ItemDiscovered,
    ItemPlaced,
    KeepsakeGained,
    PartyMoved,
)
from aidm.rules.equipment import EquipRefusal, EquipRefused, drop_events, take_events
from aidm.rules.handing import GiveRefusal, GiveRefused, give_events
from aidm.rules.plan_ids import boss_npc_id, main_quest_id, quest_item_id
from aidm.rules.quest_items import (
    Spot,
    act_quest_items,
    quest_item_events,
    quest_item_named,
    same_item,
)
from aidm.rules.scene import discovery_events
from aidm.rules.secrets import item_key
from aidm.rules.shop import ShopRefusal, ShopRefused, sell_events
from tests.session.progression_fixtures import apply_all, campaign_state, plan
from tests.unit.rules.economy_fixtures import CAT, TABLE, shop_state

REGS = tool_registries()
R1 = plan().acts[0].region
MAIN = main_quest_id(R1)
ORDERS = quest_item_id(MAIN, "the-tide-orders", 0, 0)
TUNNELS = "saltcellar-tunnels"


def _search(total: int) -> CheckResult:
    roll = D20Roll(rolls=(total,), adv=AdvState.NORMAL, natural=total, modifier=0, total=total)
    return CheckResult(
        kind=CheckKind.SKILL,
        ability=Ability.WIS,
        skill=Skill.PERCEPTION,
        roll=roll,
        dc=10,
        success=total >= 10,
        margin=total - 10,
    )


def _at(state: GameState, node: str) -> None:
    world = state.world
    moved = PartyMoved(
        from_node=world.current_node, to_node=node, scene_index=world.scene_index + 1
    )
    apply_all(state, [moved])


def _carry(state: GameState, keepsake: Keepsake, pc: str = "fighter") -> None:
    apply_all(state, [KeepsakeGained(creature_id=pc, keepsake=keepsake)])


def test_golden_sample_act_items() -> None:
    # sample campaign act 1: Peace route "the-tide-orders" obtains the orders, hidden in the
    # Saltcellar Tunnels; hidden items are found at DC 10 (SRD 5.1 "easy" DC tier).
    (orders,) = act_quest_items(plan(), 1)
    assert (orders.id, orders.name, orders.node_id) == (ORDERS, "Choir tide-orders", TUNNELS)
    assert orders.hidden and orders.discover_dc == 10 and orders.quest_id == MAIN
    assert orders.catalog_id is None
    act3 = act_quest_items(plan(), 3)
    stones = [i for i in act3 if i.quest_id == "kindle-the-stair"]
    assert [i.node_id for i in stones] == [
        "cistern-of-echoes",
        "keepers-barracks",
        "wreckers-gallery",
    ]
    assert {i.name for i in stones} == {"Ember-stone"} and not any(i.hidden for i in stones)
    letter = next(i for i in act3 if i.quest_id == main_quest_id(plan().acts[2].region))
    assert letter.hidden and letter.name == "Salt-stained letter"


def test_install_places_act_one_items_once() -> None:
    _, state, log = campaign_state()
    placed = [e.item.id for e in log if isinstance(e, ItemPlaced)]
    assert placed == [ORDERS]
    assert quest_item_events(state, plan(), 1) == []


def test_picked_up_or_handed_over_items_are_never_placed_again() -> None:
    _, state, _ = campaign_state()
    _at(state, TUNNELS)
    apply_all(state, [ItemDiscovered(item_id=ORDERS, creature_id="fighter")])
    taken = take_events(state, state.creatures["fighter"], ORDERS)
    apply_all(state, taken)
    keepsake = taken[1]
    assert isinstance(keepsake, KeepsakeGained) and keepsake.keepsake.quest_id == MAIN
    assert quest_item_events(state, plan(), 1) == []
    apply_all(
        state, [KeepsakeGiven(creature_id="fighter", keepsake_id=ORDERS, npc_id="dessa-orrin")]
    )
    assert quest_item_events(state, plan(), 1) == []


def test_search_finds_a_hidden_item_here_only_at_its_dc() -> None:
    _, state, _ = campaign_state()
    assert discovery_events(state, "fighter", _search(20)) == []  # it lies in the tunnels
    _at(state, TUNNELS)
    assert discovery_events(state, "fighter", _search(9)) == []
    found = discovery_events(state, "fighter", _search(10))
    assert found == [ItemDiscovered(item_id=ORDERS, creature_id="fighter")]
    with pytest.raises(EquipRefused):
        take_events(state, state.creatures["fighter"], ORDERS)  # not found yet
    apply_all(state, list(found))
    assert not state.world.items[ORDERS].hidden


def test_quest_items_cannot_be_sold_or_dropped() -> None:
    state = shop_state()
    _carry(state, Keepsake(id=ORDERS, name="Choir tide-orders", quest_id=MAIN))
    for name in (ORDERS, item_key("Choir tide-orders")):
        with pytest.raises(ShopRefused) as sold:
            sell_events(state, "fighter", "npc-mira", name, 1, CAT, TABLE)
        assert sold.value.reason is ShopRefusal.NOT_CARRIED
        with pytest.raises(EquipRefused) as dropped:
            drop_events(state, state.creatures["fighter"], name, REGS.combat.chars)
        assert dropped.value.reason is EquipRefusal.NOT_CARRIED


def test_handing_a_keepsake_moves_it_and_gives_no_deed() -> None:
    _, state, _ = campaign_state()
    _carry(state, Keepsake(id="shell", name="Spiral shell"))
    events = give_events(state, "fighter", "dessa-orrin", "shell", REGS.tiers)
    assert events == [
        KeepsakeGiven(creature_id="fighter", keepsake_id="shell", npc_id="dessa-orrin")
    ]
    apply_all(state, events)
    assert [k.id for k in state.world.npcs["dessa-orrin"].keepsakes] == ["shell"]


def test_handing_an_inventory_item_is_the_existing_gift() -> None:
    _, state, _ = campaign_state()
    hero = state.creatures["fighter"]
    assert hero.pc is not None
    item = hero.pc.inventory[-1].item
    events: list[AnyEvent] = give_events(state, "fighter", "dessa-orrin", item, REGS.tiers)
    assert isinstance(events[0], InventoryChanged) and events[0].delta == -1
    assert any(isinstance(e, AttitudeChanged) for e in events)


def _refusal(state: GameState, npc_id: str, thing: str) -> GiveRefusal:
    with pytest.raises(GiveRefused) as caught:
        give_events(state, "fighter", npc_id, thing, REGS.tiers)
    assert caught.value.detail  # player-safe words
    return caught.value.reason


def test_give_refusals_are_typed() -> None:
    _, state, _ = campaign_state()
    _carry(state, Keepsake(id="shell", name="Spiral shell"))
    assert _refusal(state, "dessa-orrin", "no-such-thing") is GiveRefusal.NOT_CARRIED
    assert _refusal(state, boss_npc_id(R1), "shell") is GiveRefusal.NOT_HERE
    assert _refusal(state, "nobody", "shell") is GiveRefusal.NOT_HERE
    hostile = state.world.npcs["dessa-orrin"].model_copy(update={"hostile": True})
    state.world.npcs["dessa-orrin"] = hostile
    assert _refusal(state, "dessa-orrin", "shell") is GiveRefusal.HOSTILE


def test_lookalike_names() -> None:
    assert same_item("Bell-Tongue", "False Bell-Tongue")
    assert same_item("the Choir tide-orders", "Choir tide-orders")
    assert same_item("Ember-stones", "Ember-stone")
    assert not same_item("ring", "Drowned King's Ring")
    assert not same_item("Spiral shell", "Choir tide-orders")


def test_quest_item_named_prefers_a_visible_copy_here() -> None:
    _, state, _ = campaign_state()
    spot = quest_item_named(state, "tide-orders of the Choir")
    assert spot is not None and spot.spot is Spot.ELSEWHERE
    _at(state, TUNNELS)
    hidden = quest_item_named(state, "Choir tide-orders")
    assert hidden is not None and hidden.spot is Spot.HIDDEN_HERE
    apply_all(state, [ItemDiscovered(item_id=ORDERS)])
    here = quest_item_named(state, "Choir tide-orders")
    assert here is not None and (here.spot, here.item_id) == (Spot.HERE, ORDERS)
    assert quest_item_named(state, "Spiral shell") is None
