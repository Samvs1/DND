"""Taking from a fallen hero's pack (M36.4, round 6 Y14) and counted takes of a stack lying here
(round 6 Y12/B3): the rules' events, the menu entries and replay through the one reducer.
"""

import pytest

from aidm.data.combat_data import combat_registries
from aidm.models.action_menu import MenuChoice, MenuStep
from aidm.models.events import AnyEvent, GoldChanged, InventoryChanged, LoggedEvent, event_adapter
from aidm.models.item_events import HandedOver
from aidm.models.state import GameState
from aidm.models.world import WorldItem
from aidm.models.world_events import ItemPlaced, ItemRemoved
from aidm.rules.action_menu import build_menu
from aidm.rules.acts import LootIntent
from aidm.rules.equipment import take_events
from aidm.rules.hero_handing import HandRefused, loot_events
from aidm.rules.item_grants import carried_qty
from aidm.rules.menu_steps import to_acts
from aidm.session.persistence import replay_log
from aidm.session.reducer import apply
from aidm.session.reducer_errors import ReducerError
from tests.session.playtest_saves import replay_until

REGS = combat_registries()
FULL = "m35-r6-full"
POTION = "potion-of-healing"


def _downed_tamsin() -> GameState:
    """full 469: the fight is won, Tamsin is down at 0 HP, Brienne stands."""
    state = replay_until(FULL, 469)
    assert state.creatures["pc-p8"].hp == 0 and not state.creatures["pc-p8"].dead
    return state


def _replays(base: GameState, events: list[AnyEvent]) -> GameState:
    live = base.model_copy(deep=True)
    for event in events:
        apply(live, event)
    log = [
        LoggedEvent(seq=i, event=event_adapter.validate_json(e.model_dump_json()))
        for i, e in enumerate(events)
    ]
    snapshot = GameState.model_validate_json(live.model_dump_json())
    assert replay_log(base, log) == snapshot == live
    return live


def test_v1_y14_take_a_potion_from_downed_tamsin() -> None:
    base = _downed_tamsin()
    gift = InventoryChanged(creature_id="pc-p8", item=POTION, delta=1, qty=1)
    state = apply(base.model_copy(deep=True), gift)
    have = carried_qty(state.creatures["pc-p2"], POTION)
    events = loot_events(state, "pc-p2", "pc-p8", REGS.chars, thing=POTION)
    assert events[-1] == HandedOver(
        creature_id="pc-p8", to_id="pc-p2", item=POTION, qty=1, taken=True
    )
    live = _replays(base, [gift, *events])
    assert carried_qty(live.creatures["pc-p8"], POTION) == 0
    assert carried_qty(live.creatures["pc-p2"], POTION) == have + 1


def test_menu_loot_entries_and_steps_for_a_fallen_hero() -> None:
    state = _downed_tamsin()
    menu = build_menu(state, "pc-p2", REGS)
    incense = next(e for e in menu.entries if e.id == "loot:block-of-incense")
    assert incense.target_ids == ("pc-p8",) and incense.qty_max == 5
    assert incense.label == "Take Block of incense from Tamsin's pack (Tamsin carries 5)"
    gold = next(e for e in menu.entries if e.id == "loot:gold")
    assert gold.qty_max == 44
    steps = (MenuStep(entry=incense.id, qty=2), MenuStep(entry="loot:gold", qty=10))
    acts = to_acts(state, menu, MenuChoice(steps=steps), REGS)
    assert acts == [
        LootIntent("pc-p2", "pc-p8", "block-of-incense", qty=2),
        LootIntent("pc-p2", "pc-p8", None, gold=10),
    ]
    events = loot_events(state, "pc-p2", "pc-p8", REGS.chars, gold=10)
    assert [e.delta for e in events if isinstance(e, GoldChanged)] == [-10, 10]
    _replays(state, events)


def test_menu_loot_a_dead_heros_pack() -> None:
    base = _downed_tamsin()
    tamsin = base.creatures["pc-p8"].model_copy(update={"dead": True})
    state = base.model_copy(update={"creatures": {**base.creatures, "pc-p8": tamsin}})
    menu = build_menu(state, "pc-p2", REGS)
    assert next(t.label for t in menu.targets if t.id == "pc-p8") == "Tamsin, dead"
    assert any(e.id == "loot:quarterstaff" for e in menu.entries)
    assert not any(e.id == "help_up" for e in menu.entries)
    events = loot_events(state, "pc-p2", "pc-p8", REGS.chars, thing="quarterstaff")
    assert isinstance(events[-1], HandedOver) and events[-1].taken


def test_loot_refusals_are_plain() -> None:
    state = _downed_tamsin()
    with pytest.raises(HandRefused, match="awake"):
        loot_events(state, "pc-p4", "pc-p2", REGS.chars, thing="longsword")
    with pytest.raises(HandRefused, match="cannot take"):
        loot_events(state, "pc-p8", "pc-p2", REGS.chars, thing="longsword")
    with pytest.raises(HandRefused, match="only 5"):
        loot_events(state, "pc-p2", "pc-p8", REGS.chars, thing="block-of-incense", qty=9)
    with pytest.raises(HandRefused, match="does not carry"):
        loot_events(state, "pc-p2", "pc-p8", REGS.chars, thing=POTION)
    fight = replay_until("m35-r6-typed", 435)
    downed = fight.creatures["pc-p8"].model_copy(update={"hp": 0})
    fight = fight.model_copy(update={"creatures": {**fight.creatures, "pc-p8": downed}})
    with pytest.raises(HandRefused, match="fight"):
        loot_events(fight, "pc-p2", "pc-p8", REGS.chars, gold=1)


def test_counted_take_of_a_stack_leaves_the_rest() -> None:
    base = _downed_tamsin()
    here = base.world.current_node
    bolts = WorldItem(id="bolts", name="Crossbow Bolt", catalog_id="crossbow-bolt", qty=3)
    placed = ItemPlaced(item=bolts.model_copy(update={"node_id": here}))
    state = apply(base.model_copy(deep=True), placed)
    have = carried_qty(state.creatures["pc-p2"], "crossbow-bolt")
    one = take_events(state, state.creatures["pc-p2"], "bolts", 1)
    assert one[0] == ItemRemoved(item_id="bolts", qty=1)
    live = _replays(base, [placed, *one])
    assert live.world.items["bolts"].qty == 2
    assert carried_qty(live.creatures["pc-p2"], "crossbow-bolt") == have + 1
    rest = take_events(live, live.creatures["pc-p2"], "bolts")
    assert rest[0] == ItemRemoved(item_id="bolts")
    with pytest.raises(ReducerError):
        apply(live.model_copy(deep=True), ItemRemoved(item_id="bolts", qty=5))
