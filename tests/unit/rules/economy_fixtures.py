"""Fixtures for the shop, loot, reward and quest tests: a level-1 party with a shopkeeper."""

from __future__ import annotations

from aidm.data.item_catalogue import item_catalogue
from aidm.data.loot_defs import loot_tables
from aidm.data.shop_defs import shop_table
from aidm.models.events import AnyEvent, GoldChanged
from aidm.models.state import GameState
from aidm.models.world_events import ShopOpened
from aidm.session.reducer import apply
from tests.ai.tool_fixtures import add_npc, party_state

CAT = item_catalogue()
TABLE = shop_table()
LOOT = loot_tables()
PARTY_IDS = ("fighter", "rogue", "wizard", "cleric")


def apply_events(state: GameState, events: list[AnyEvent]) -> GameState:
    for event in events:
        apply(state, event)
    return state


def shop_state(
    gold: int = 500, role: str = "general merchant", open_shop: bool = True
) -> GameState:
    state = party_state(1)
    add_npc(state, "npc-mira", name="Mira", role=role)
    if open_shop:
        apply(state, ShopOpened(npc_id="npc-mira"))
    for pc_id in PARTY_IDS:
        apply(state, GoldChanged(creature_id=pc_id, delta=gold, gold=gold))
    return state


def gold_of(state: GameState, pc_id: str = "fighter") -> int:
    pc = state.creatures[pc_id].pc
    assert pc is not None
    return pc.gold


def carried(state: GameState, item: str, pc_id: str = "fighter") -> int:
    pc = state.creatures[pc_id].pc
    assert pc is not None
    return sum(r.qty for r in pc.inventory if r.item == item)
