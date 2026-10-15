"""M23.3 quest items on the AI side: `give_keepsake` never makes a lookalike of a placed quest item,
typed "give X to Y" is a deterministic pre-check, and the narrator can tell a hand-over."""

from aidm.dm.event_text import event_line
from aidm.dm.give_intent import GiveIntent
from aidm.dm.narration_templates import template_line
from aidm.dm.precheck import precheck
from aidm.models.character import Keepsake
from aidm.models.quest_events import KeepsakeGiven
from aidm.models.state import GameState
from aidm.models.world_events import ItemDiscovered, ItemPlaced, KeepsakeGained, PartyMoved
from aidm.rules.plan_ids import boss_npc_id, main_quest_id, quest_item_id
from aidm.rules.sheet import build_sheet
from aidm.session.sheet_view import quest_titles
from tests.ai.tool_fixtures import REGS, run_tool
from tests.session.progression_fixtures import apply_all, campaign_state, plan

R1 = plan().acts[0].region
MAIN = main_quest_id(R1)
BOSS = boss_npc_id(R1)
ORDERS = quest_item_id(MAIN, "the-tide-orders", 0, 0)
TUNNELS = "saltcellar-tunnels"


def _at(state: GameState, node: str) -> None:
    world = state.world
    moved = PartyMoved(
        from_node=world.current_node, to_node=node, scene_index=world.scene_index + 1
    )
    apply_all(state, [moved])


def _fighter_keepsakes(state: GameState) -> list[Keepsake]:
    pc = state.creatures["fighter"].pc
    assert pc is not None
    return list(pc.keepsakes)


def test_give_keepsake_refuses_a_lookalike_of_a_quest_item_elsewhere() -> None:
    _, state, _ = campaign_state()
    refused = run_tool(state, "give_keepsake", name="Choir tide-orders")
    assert not refused.ok and refused.error is not None
    assert "quest item" in refused.error and "not here" in refused.error
    _at(state, TUNNELS)
    hidden = run_tool(state, "give_keepsake", name="the tide-orders of the Choir")
    assert not hidden.ok and hidden.error is not None and "search" in hidden.error


def test_give_keepsake_hands_the_real_quest_item_lying_here() -> None:
    _, state, _ = campaign_state()
    _at(state, TUNNELS)
    apply_all(state, [ItemDiscovered(item_id=ORDERS, creature_id="fighter")])
    result = run_tool(state, "give_keepsake", name="Choir tide-orders")
    assert result.ok, result.error
    apply_all(state, list(result.events))
    assert ORDERS not in state.world.items
    (orders,) = _fighter_keepsakes(state)
    assert (orders.id, orders.quest_id) == (ORDERS, MAIN)
    again = run_tool(state, "give_keepsake", name="Choir tide-orders")
    assert again.error is not None and "already carried" in again.error


def test_give_keepsake_still_makes_flavour_keepsakes() -> None:
    _, state, _ = campaign_state()
    result = run_tool(state, "give_keepsake", name="Spiral shell")
    assert result.ok
    apply_all(state, list(result.events))
    (shell,) = _fighter_keepsakes(state)
    assert shell.quest_id is None


def test_typed_give_is_a_precheck() -> None:
    _, state, _ = campaign_state()
    shell = Keepsake(id="shell", name="Spiral shell")
    apply_all(state, [KeepsakeGained(creature_id="fighter", keepsake=shell)])
    assert precheck(state, "fighter", "I give the spiral shell to Dessa.") == GiveIntent(
        "fighter", "dessa-orrin", "shell"
    )
    assert precheck(state, "fighter", "hand over the shell to dessa orrin") == GiveIntent(
        "fighter", "dessa-orrin", "shell"
    )
    assert precheck(state, "fighter", "give dessa the shell") == GiveIntent(
        "fighter", "dessa-orrin", "shell"
    )
    # someone known but not here: the rules refuse in plain words later
    assert precheck(state, "fighter", "give the shell to gorran") == GiveIntent(
        "fighter", BOSS, "shell"
    )
    assert precheck(state, "fighter", "give my thanks to dessa") is None  # roleplay
    assert precheck(state, "fighter", "give the shell to the gulls") is None


def test_typed_give_names_an_inventory_item_too() -> None:
    _, state, _ = campaign_state()
    pc = state.creatures["fighter"].pc
    assert pc is not None
    item = pc.inventory[-1].item
    said = f"give the {item.replace('-', ' ')} to dessa"
    assert precheck(state, "fighter", said) == GiveIntent("fighter", "dessa-orrin", item)


def test_hand_over_and_found_lines_for_model_and_templates() -> None:
    _, state, _ = campaign_state()
    shell = Keepsake(id="shell", name="Spiral shell")
    given = KeepsakeGiven(creature_id="fighter", keepsake_id="shell", npc_id="dessa-orrin")
    apply_all(state, [KeepsakeGained(creature_id="fighter", keepsake=shell), given])
    hero = state.creatures["fighter"].name
    line = f"{hero} hands the Spiral shell to Dessa Orrin."
    assert event_line(state, given) == line and template_line(state, given) == line
    _at(state, TUNNELS)
    found = ItemDiscovered(item_id=ORDERS, creature_id="fighter")
    apply_all(state, [found])
    assert event_line(state, found) == f"{hero} found Choir tide-orders."
    assert template_line(state, found) == f"{hero} finds Choir tide-orders."


def test_items_placed_elsewhere_are_not_told_as_lying_here() -> None:
    _, state, _ = campaign_state()
    item = state.world.items[ORDERS].model_copy(update={"hidden": False})
    placed = ItemPlaced(item=item)
    assert event_line(state, placed) is None and template_line(state, placed) is None
    here = ItemPlaced(item=item.model_copy(update={"node_id": state.world.current_node}))
    assert event_line(state, here) == "Choir tide-orders lies here."


def test_sheet_names_the_quest_of_a_quest_item() -> None:
    _, state, _ = campaign_state()
    orders = Keepsake(id=ORDERS, name="Choir tide-orders", quest_id="missing-ledger")
    shell = Keepsake(id="shell", name="Spiral shell")
    gained = [KeepsakeGained(creature_id="fighter", keepsake=k) for k in (orders, shell)]
    apply_all(state, list(gained))
    sheet = build_sheet(state.creatures["fighter"], REGS.combat.chars, quest_titles(state))
    titles = [(k.name, k.quest_title) for k in sheet.keepsakes]
    assert titles == [("Choir tide-orders", "The Missing Ledger"), ("Spiral shell", None)]
