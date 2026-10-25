"""Deterministic pre-checks (M4.4, SPEC 6.2): clear commands map to intents, the rest to None."""

import pytest

from aidm.dm.precheck import precheck
from aidm.dm.scene_text import look_around_text
from aidm.models.state import GameState
from aidm.models.world import FeatureKind, WorldFeature, WorldItem
from aidm.models.world_events import FeatureIntroduced, ItemPlaced, NodeDescribed
from aidm.rules.acts import (
    BarredIntent,
    InventoryIntent,
    ItemAction,
    ItemIntent,
    LookIntent,
    RestIntent,
    RestKind,
    ShopIntent,
    TravelIntent,
)
from aidm.session.reducer import apply
from tests.ai.tool_fixtures import add_npc, apply_result, party_state, run_tool


def _state() -> GameState:
    state = party_state()
    state.world.node_names = {"forest": "Whispering Woods"}
    return state


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("short rest", RestKind.SHORT),
        ("I take a short rest.", RestKind.SHORT),
        ("We'll have a short rest", RestKind.SHORT),
        ("let's catch our breath", RestKind.SHORT),
        ("Long rest", RestKind.LONG),
        ("we make camp for the night", RestKind.LONG),
        ("Let us set up camp!", RestKind.LONG),
        ("I want to take a long rest please", RestKind.LONG),
    ],
)
def test_rest_positive(text: str, kind: RestKind) -> None:
    assert precheck(_state(), "fighter", text) == RestIntent(kind)


@pytest.mark.parametrize(
    "text",
    [
        "I rest my hand on the hilt",
        "we rest",
        "I ask the innkeeper about a long rest",
        "the long rest of the road",
        "short rest while I keep watch on the door",
    ],
)
def test_rest_negative(text: str) -> None:
    assert precheck(_state(), "fighter", text) is None


@pytest.mark.parametrize(
    ("text", "node"),
    [
        ("go to the forest", "forest"),
        ("We travel to Whispering Woods.", "forest"),
        ("let's head back to the crypt", "crypt"),
        ("I walk towards whispering woods", "forest"),
    ],
)
def test_travel_positive(text: str, node: str) -> None:
    state = _state()
    state.world.locked_nodes = []
    assert precheck(state, "fighter", text) == TravelIntent(node)


def test_travel_to_a_locked_exit_says_it_is_barred() -> None:
    state = _state()
    assert "crypt" in state.world.locked_nodes
    intent = precheck(state, "fighter", "let's head back to the crypt")
    assert intent == BarredIntent("The way to Crypt is barred for now.")  # M23.8: no model call


@pytest.mark.parametrize(
    "text",
    ["go to the castle", "I go to the bar and order a drink", "head to the market", "go north"],
)
def test_travel_negative(text: str) -> None:
    assert precheck(_state(), "fighter", text) is None


def test_shop_needs_a_present_shopkeeper() -> None:
    state = _state()
    assert precheck(state, "fighter", "I browse the wares") is None
    add_npc(state, "npc-tam", name="Tam", role="blacksmith")
    add_npc(state)  # Mira the innkeeper does not sell
    assert precheck(state, "fighter", "I browse the wares") == ShopIntent("npc-tam")
    assert precheck(state, "fighter", "trade with Tam") == ShopIntent("npc-tam")
    assert precheck(state, "fighter", "buy from the blacksmith") == ShopIntent("npc-tam")
    assert precheck(state, "fighter", "trade with Mira") is None
    assert precheck(state, "fighter", "I buy Tam a drink") is None


def test_shop_npc_elsewhere_is_not_a_shop() -> None:
    state = _state()
    add_npc(state, "npc-tam", name="Tam", role="merchant", node_id="forest")
    assert precheck(state, "fighter", "shop") is None


@pytest.mark.parametrize(
    ("text", "action", "item"),
    [
        ("equip my longsword", ItemAction.EQUIP, "longsword"),
        ("I wield the light crossbow", ItemAction.EQUIP, "crossbow-light"),
        ("unequip shield", ItemAction.UNEQUIP, "shield"),
        ("I take off my chain mail", ItemAction.UNEQUIP, "chain-mail"),
        ("drop the longsword", ItemAction.DROP, "longsword"),
    ],
)
def test_item_positive(text: str, action: ItemAction, item: str) -> None:
    assert precheck(_state(), "fighter", text) == ItemIntent("fighter", action, item)


@pytest.mark.parametrize(
    "text",
    [
        "equip the vorpal sword",
        "draw a map",
        "drop the act",
        "I drop the longsword on the goblin's head",
        "remove the trap",
        "unequip my dagger",
    ],
)
def test_item_negative(text: str) -> None:
    assert precheck(_state(), "fighter", text) is None


@pytest.mark.parametrize(
    "text", ["inventory", "Check my inventory.", "what am I carrying?", "open my backpack"]
)
def test_inventory_positive(text: str) -> None:
    assert precheck(_state(), "rogue", text) == InventoryIntent("rogue")


@pytest.mark.parametrize(
    "text", ["look around", "I look around.", "What do we see?", "survey the area", "look"]
)
def test_look_positive(text: str) -> None:
    intent = precheck(_state(), "fighter", text)
    assert isinstance(intent, LookIntent) and intent.text.startswith("You are at Town.")


@pytest.mark.parametrize(
    "text",
    ["look around for traps", "look at the statue", "I look Mira in the eye", "look for a way out"],
)
def test_look_negative(text: str) -> None:
    assert precheck(_state(), "fighter", text) is None


def test_nothing_matches_during_a_fight() -> None:
    state = _state()
    apply_result(state, run_tool(state, "start_encounter", monster_ids=["goblin"]))
    assert state.encounter is not None
    assert precheck(state, "fighter", "look around") is None


def test_look_around_is_served_from_the_manifest() -> None:
    state = _state()
    add_npc(state)
    apply(state, NodeDescribed(node_id="town", text="A muddy square under grey skies."))
    hidden = WorldFeature(
        id="feat-h",
        kind=FeatureKind.DOOR,
        name="hidden door",
        node_id="town",
        hidden=True,
        discover_dc=15,
    )
    lever = WorldFeature(id="feat-l", kind=FeatureKind.LEVER, name="rusted lever", node_id="town")
    apply(state, FeatureIntroduced(feature=hidden))
    apply(state, FeatureIntroduced(feature=lever))
    apply(state, ItemPlaced(item=WorldItem(id="it-1", name="silver key", node_id="town")))
    text = look_around_text(state)
    assert text == (
        "You are at Town. A muddy square under grey skies. Here with you: Mira (innkeeper)."
        " You notice: rusted lever. Lying here: silver key."
        " Ways on: Whispering Woods and Crypt (locked)."
    )
    assert "hidden door" not in text
    assert look_around_text(state) == text


def test_empty_scene_says_nobody_is_here() -> None:
    assert "Nobody else is here." in look_around_text(_state())
