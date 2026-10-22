"""The item-use interpreter (M27.3, docs/next/GOAL_ITEMS.md "Design"): carried catalogue gear,
the situation, one use per action, the fight cost, consume vs charges, every refusal."""

from aidm.models.encounter import Side
from aidm.models.encounter_events import EconomyChanged
from aidm.models.events import InventoryChanged, Stabilized
from aidm.models.item_events import BoonGained, ItemUsed, LightEnded, LightLit, PlaceAlerted
from aidm.models.state import GameState
from aidm.models.world import CarriedLight
from tests.unit.rules.combat_fixtures import economy
from tests.unit.rules.item_fixtures import (
    CAVE,
    DOCKS,
    at,
    gear_fight,
    hero,
    qty,
    refusal,
    run,
    use,
)

HEALERS_KIT_USES = 10  # SRD 5.1 Adventuring Gear, Healer's Kit: "This kit ... has ten uses."


def test_torch_lights_a_dark_place_is_consumed_and_alerts_it() -> None:
    state = at(CAVE, hero(gear=[("torch", 2)]))
    events = use(state, "torch")
    assert [type(e) for e in events] == [ItemUsed, LightLit, InventoryChanged, PlaceAlerted]
    run(state, events)
    assert state.world.lights == [CarriedLight(creature_id="hero", item="torch", reach="touching")]
    assert qty(state, "hero", "torch") == 1
    assert state.world.alerted == CAVE


def test_candle_lights_its_own_zone_only_and_a_lantern_is_kept() -> None:
    state = at(CAVE, hero(gear=["candle", "lantern-hooded"]))
    lit = [e for e in use(state, "candle") if isinstance(e, LightLit)]
    assert lit[0].reach == "zone"
    events = use(state, "Lantern, hooded")  # by catalogue name
    assert not any(isinstance(e, InventoryChanged) for e in events)
    run(state, events)
    assert qty(state, "hero", "lantern-hooded") == 1


def test_bullseye_lantern_lights_and_gives_investigation_as_long_as_its_light() -> None:
    # M27.12: the light lasts until the long rest, and so does its Investigation boon.
    state = at(CAVE, hero(gear=["lantern-bullseye"]))
    boons = [e.boon for e in use(state, "lantern-bullseye") if isinstance(e, BoonGained)]
    assert [(b.name, b.skills, b.scope, b.node) for b in boons] == [
        ("Lantern", ("investigation",), "until_long_rest", None)
    ]


def test_torch_in_daylight_is_refused_and_consumes_nothing() -> None:
    state = at(DOCKS, hero(gear=["torch"]))
    assert "not dark" in refusal(use(state, "torch"))
    assert qty(state, "hero", "torch") == 1


def test_torch_in_a_lit_place_is_refused() -> None:
    state = at(CAVE, hero(gear=[("torch", 2)]), hero("ally", gear=["torch"]))
    run(state, use(state, "torch"))
    assert "already lit by Hero" in refusal(use(state, "torch", actor="ally"))
    assert qty(state, "ally", "torch") == 1


def test_gear_not_carried_is_refused() -> None:
    state = at(CAVE, hero())
    assert "does not carry torch" in refusal(use(state, "torch"))


def test_keepsake_named_rope_never_counts() -> None:
    state = at(DOCKS, hero(gear=["rope-hempen-50-feet"], keepsakes=["Rope"]))
    assert "keepsake" in refusal(use(state, "Rope"))
    assert "keepsake" in refusal(use(at(DOCKS, hero(keepsakes=["Rope"])), "rope"))
    assert any(isinstance(e, BoonGained) for e in use(state, "rope-hempen-50-feet"))


def test_flavour_gear_has_no_use() -> None:
    state = at(CAVE, hero(gear=["longsword"]))
    assert "no use here" in refusal(use(state, "longsword"))


def test_wrong_situation_is_refused() -> None:
    state = gear_fight(CAVE, hero(gear=["magnifying-glass"]))
    assert "during a fight" in refusal(use(state, "magnifying-glass"))
    calm = at(CAVE, hero(gear=["oil-flask", "fishing-tackle", "herbalism-kit"]))
    assert "for a fight" in refusal(use(calm, "oil-flask"))
    assert "needs a place with water" in refusal(use(calm, "fishing-tackle"))
    assert "long rest" in refusal(use(calm, "herbalism-kit"))


def test_one_item_use_per_action() -> None:
    state = at(DOCKS, hero(gear=["magnifying-glass", "spyglass"]))
    first = use(state, "magnifying-glass")
    assert "One item use per action" in refusal(use(state, "spyglass", prior=first))
    other = [e for e in first if not isinstance(e, ItemUsed)]
    assert any(isinstance(e, BoonGained) for e in use(state, "spyglass", prior=other))


def test_fight_cost_is_spent_through_the_action_economy() -> None:
    state = gear_fight(CAVE, hero(gear=["torch", "oil-flask", "caltrops"]))
    events = use(state, "torch")
    assert isinstance(events[0], EconomyChanged)
    run(state, events)
    assert not economy(state, "hero").bonus_action
    assert economy(state, "hero").action
    run(state, use(state, "oil-flask", "b"))
    assert "already used your action" in refusal(use(state, "caltrops", "a"))
    assert qty(state, "hero", "caltrops") == 1


def test_not_yet_wired_effects_are_refused_plainly() -> None:
    calm = at(CAVE, hero(gear=["crowbar", "thieves-tools", "scroll-of-sleep"]))
    assert "nothing locked" in refusal(use(calm, "crowbar"))
    assert "nothing locked" in refusal(use(calm, "thieves-tools"))
    assert "scrolls" in refusal(use(calm, "scroll-of-sleep"))
    state = gear_fight(CAVE, hero(gear=["alchemists-fire-flask", "acid-vial"]))
    assert "Throwing" in refusal(use(state, "alchemists-fire-flask", "gob"))
    assert qty(state, "hero", "alchemists-fire-flask") == 1
    assert economy(state, "hero").action


def test_healers_kit_spends_a_charge_and_is_not_consumed() -> None:
    down = hero("ally")
    down.hp = 0
    state = at(DOCKS, hero(gear=["healers-kit"]), down)
    events = use(state, "healers-kit", "ally")
    assert [type(e) for e in events] == [ItemUsed, Stabilized]
    used = events[0]
    assert isinstance(used, ItemUsed)
    assert used.spends_charge and used.charges_left == HEALERS_KIT_USES - 1
    run(state, events)
    pc = state.creatures["hero"].pc
    assert pc is not None and pc.inventory[0].charges == HEALERS_KIT_USES - 1


def _kit_state(charges: int, kits: int = 1) -> GameState:
    down = hero("ally")
    down.hp = 0
    state = at(DOCKS, hero(gear=[("healers-kit", kits)]), down)
    pc = state.creatures["hero"].pc
    assert pc is not None
    pc.inventory[0].charges = charges
    return state


def test_last_charge_uses_the_kit_up_and_a_spare_starts_full() -> None:
    last = _kit_state(1)
    run(last, use(last, "healers-kit", "ally"))
    assert qty(last, "hero", "healers-kit") == 0
    spare = _kit_state(1, kits=2)
    run(spare, use(spare, "healers-kit", "ally"))
    pc = spare.creatures["hero"].pc
    assert pc is not None and (pc.inventory[0].qty, pc.inventory[0].charges) == (1, None)


def test_out_of_charges_is_refused() -> None:
    state = _kit_state(0)
    assert "used up" in refusal(use(state, "healers-kit", "ally"))
    assert state.creatures["ally"].stable is False


def test_noise_alerts_a_place_once() -> None:
    state = at(CAVE, hero(gear=["torch"]), hero("ally", gear=["lantern-hooded"]))
    run(state, use(state, "torch"))
    run(state, [LightEnded(creature_id="hero", reason="long rest")])
    assert not any(isinstance(e, PlaceAlerted) for e in use(state, "lantern-hooded", actor="ally"))


def test_fight_uses_need_the_hero_s_turn() -> None:
    state = gear_fight(CAVE, hero(gear=["torch"]), (hero("ally", gear=["torch"]), Side.PARTY, "a"))
    assert "not your turn" in refusal(use(state, "torch", actor="ally"))
