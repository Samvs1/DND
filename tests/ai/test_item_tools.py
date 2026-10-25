"""M19.3 (owner playtest 2026-10-10): items lying here can be picked up for real, and story finds
(a note, a key) become keepsakes the hero carries."""

import pytest

from aidm.dm.context import build_context
from aidm.dm.context_text import ContextPurpose
from aidm.dm.guard import check_prose
from aidm.dm.precheck import precheck
from aidm.dm.tool_exec_items import MAX_KEEPSAKES
from aidm.models.character import Keepsake
from aidm.models.events import InventoryChanged
from aidm.models.state import GameState
from aidm.models.world import WorldItem
from aidm.models.world_events import ItemRemoved, KeepsakeGained
from aidm.rules.acts import TakeIntent
from aidm.rules.equipment import EquipRefused, take_events
from aidm.rules.item_grants import carried_qty
from tests.ai.tool_fixtures import apply_result, party_state, run_tool


def _place(state: GameState, item_id: str, name: str, catalog: str | None, **kw: object) -> None:
    node = kw.pop("node_id", state.world.current_node)
    hidden = bool(kw.pop("hidden", False))
    state.world.items[item_id] = WorldItem(
        id=item_id, name=name, catalog_id=catalog, node_id=str(node), hidden=hidden
    )


def test_taking_a_catalogue_item_moves_it_into_the_inventory() -> None:
    state = party_state()
    hero = state.creatures["fighter"]
    before = carried_qty(hero, "pouch")
    _place(state, "dropped-pouch-27", "Pouch", "pouch")
    events = take_events(state, hero, "dropped-pouch-27")
    assert isinstance(events[0], ItemRemoved) and isinstance(events[1], InventoryChanged)
    assert events[1].delta == 1 and events[1].qty == before + 1


def test_taking_a_story_object_makes_a_keepsake() -> None:
    state = party_state()
    _place(state, "oilcloth", "Oilcloth Scrap", None)
    events = take_events(state, state.creatures["fighter"], "oilcloth")
    gained = events[1]
    assert isinstance(gained, KeepsakeGained) and gained.keepsake.name == "Oilcloth Scrap"


@pytest.mark.parametrize("where", [{"node_id": "forest"}, {"hidden": True}])
def test_nothing_is_taken_from_elsewhere_or_hidden(where: dict[str, object]) -> None:
    state = party_state()
    _place(state, "coin", "Silver Coin", None, **where)
    with pytest.raises(EquipRefused):
        take_events(state, state.creatures["fighter"], "coin")


def test_take_item_tool_and_keepsake_tool() -> None:
    state = party_state()
    _place(state, "dropped-pouch-27", "Pouch", "pouch")
    taken = run_tool(state, "take_item", item_id="dropped-pouch-27")
    assert taken.ok and "picks up the Pouch" in taken.summary
    apply_result(state, taken)
    assert "dropped-pouch-27" not in state.world.items
    note = run_tool(state, "give_keepsake", name="Oilcloth scrap", description="A charcoal map.")
    assert note.ok
    apply_result(state, note)
    hero = state.creatures["fighter"]
    assert hero.pc is not None and [k.name for k in hero.pc.keepsakes] == ["Oilcloth scrap"]
    again = run_tool(state, "give_keepsake", name="oilcloth SCRAP")
    assert not again.ok  # the same thing twice


def test_keepsakes_are_capped() -> None:
    state = party_state()
    hero = state.creatures["fighter"]
    assert hero.pc is not None
    hero.pc.keepsakes = [Keepsake(id=f"k{i}", name=f"Token {i}") for i in range(MAX_KEEPSAKES)]
    assert not run_tool(state, "give_keepsake", name="One too many").ok


@pytest.mark.parametrize(
    "text",
    ["I pick up the pouch.", "I take the spilled pouch", "grab pouch", "I pick the pouch up"],
)
def test_typed_pick_ups_need_no_model(text: str) -> None:
    state = party_state()
    _place(state, "dropped-pouch-27", "Pouch", "pouch")
    assert precheck(state, "fighter", text) == TakeIntent("fighter", "dropped-pouch-27")


@pytest.mark.parametrize("text", ["I take a short rest", "I take off my armor", "I get going"])
def test_other_take_phrases_are_not_pick_ups(text: str) -> None:
    state = party_state()
    _place(state, "dropped-pouch-27", "Pouch", "pouch")
    assert not isinstance(precheck(state, "fighter", text), TakeIntent)


def test_keepsakes_reach_the_dm_and_the_guard() -> None:
    state = party_state()
    hero = state.creatures["fighter"]
    assert hero.pc is not None
    hero.pc.keepsakes = [Keepsake(id="k1", name="Oilcloth Scrap")]
    text = "\n".join(
        s.text() for s in build_context(state, ContextPurpose.NARRATE, "fighter").sections
    )
    assert "keepsakes: Oilcloth Scrap" in text
    assert check_prose(f"{hero.name} unfolds the oilcloth scrap again.", state).ok
