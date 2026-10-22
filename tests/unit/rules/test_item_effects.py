"""Every handled item-use effect kind (M27.3): boon, surface, condition, supplies, stabilize,
craft, reveal_map; plus the alerted place that blocks the party's surprise."""

import random

from aidm.data.item_uses import ConditionUse, ItemUse, item_use_data
from aidm.data.srd import srd
from aidm.data.surface_defs import surface_defs
from aidm.models.combat_events import ZoneSurfaceAdded
from aidm.models.encounter import Side, SurpriseKind
from aidm.models.events import (
    AnyEvent,
    CampSuppliesChanged,
    CheckResolved,
    ConditionApplied,
    InventoryChanged,
    Stabilized,
)
from aidm.models.item_events import BoonGained, ItemUsed, PlaceAlerted, PlacesCharted
from aidm.models.state import Creature, GameState
from aidm.rules.encounter import party_surprise, start_encounter
from aidm.rules.item_effects import FORAGE_DC, UseCtx, effect_events
from aidm.session.views import public_map
from tests.unit.rules.combat_fixtures import ScriptedRng, monster
from tests.unit.rules.encounter_fixtures import setup_for
from tests.unit.rules.item_fixtures import (
    CAVE,
    DOCKS,
    SHRINE,
    at,
    gear_fight,
    hero,
    qty,
    refusal,
    run,
    use,
)

CALTROPS_DC = 15  # SRD 5.1 Adventuring Gear, Caltrops: DC 15 Dexterity saving throw
BALL_BEARINGS_DC = 10  # SRD 5.1 Adventuring Gear, Ball Bearings: DC 10 Dexterity saving throw


def _boons(events: list[AnyEvent]) -> list[BoonGained]:
    return [e for e in events if isinstance(e, BoonGained)]


def test_magnifying_glass_gives_a_named_place_boon() -> None:
    state = at(DOCKS, hero(gear=["magnifying-glass"]))
    (gained,) = _boons(use(state, "magnifying-glass"))
    boon = gained.boon
    assert (boon.name, boon.skills, boon.scope, boon.node, boon.tool) == (
        "Magnifying glass",
        ("investigation",),
        "place",
        DOCKS,
        None,
    )


def test_a_second_identical_boon_is_refused() -> None:
    state = at(DOCKS, hero(gear=["rope-hempen-50-feet", "grappling-hook", "spyglass"]))
    run(state, use(state, "rope-hempen-50-feet"))
    assert "changes nothing" in refusal(use(state, "rope-hempen-50-feet"))
    assert "changes nothing" in refusal(use(state, "grappling-hook"))  # athletics again
    assert _boons(use(state, "spyglass"))  # perception is new


def test_tool_boon_names_its_tool() -> None:
    state = at(DOCKS, hero(gear=["disguise-kit"]))
    (gained,) = _boons(use(state, "disguise-kit"))
    assert gained.boon.tool == "disguise-kit"


def test_antitoxin_lasts_until_the_long_rest_and_costs_a_bonus_action_in_a_fight() -> None:
    state = gear_fight(CAVE, hero(gear=["antitoxin-vial"]))
    events = use(state, "antitoxin-vial")
    (gained,) = _boons(events)
    assert (gained.boon.saves_against, gained.boon.scope, gained.boon.node) == (
        ("poison",),
        "until_long_rest",
        None,
    )
    run(state, events)
    assert qty(state, "hero", "antitoxin-vial") == 0
    assert state.encounter is not None
    assert not state.encounter.combatant("hero").economy.bonus_action


def test_oil_and_caltrops_make_surfaces_in_reach() -> None:
    state = gear_fight(CAVE, hero(gear=["oil-flask", ("caltrops", 1)]))
    added = [e for e in use(state, "oil-flask", "b") if isinstance(e, ZoneSurfaceAdded)]
    assert [(e.zone_id, e.surface.kind, e.surface.source_id) for e in added] == [
        ("b", "oil", "hero")
    ]
    assert "too far" in refusal(use(state, "oil-flask", "c"))
    assert "Name the zone" in refusal(use(state, "oil-flask"))
    caltrops = [e for e in use(state, "caltrops", "a") if isinstance(e, ZoneSurfaceAdded)]
    assert caltrops[0].surface.kind == "caltrops"


def test_surface_dcs_are_the_srd_ones() -> None:
    assert surface_defs().get("caltrops").dc == CALTROPS_DC
    assert surface_defs().get("ball-bearings").dc == BALL_BEARINGS_DC


def _condition_ctx(state: GameState, actor: Creature, target: str) -> UseCtx:
    use_def = ItemUse(
        id="test-net",
        item="net",
        verbs=("throw",),
        when="fight",
        label="Throw the net",
        effect=ConditionUse(kind="condition", condition="restrained", rounds=1),
        cost="action",
        consumes=True,
    )
    pc = actor.pc
    assert pc is not None
    return UseCtx(state, actor, pc.inventory[0], use_def, target, random.Random(1), False)


def test_condition_effect_applies_and_refuses_when_nothing_changes() -> None:
    me = hero(gear=["net"])
    state = gear_fight(CAVE, me, (monster("gob"), Side.HOSTILE, "b"))
    events = effect_events(_condition_ctx(state, me, "gob"))
    assert isinstance(events, list)
    applied = [e for e in events if isinstance(e, ConditionApplied)]
    assert applied[0].condition.name == "restrained"
    run(state, events)
    assert "already restrained" in str(effect_events(_condition_ctx(state, me, "gob")))
    far = gear_fight(CAVE, me, (monster("gob"), Side.HOSTILE, "c"))
    assert "out of reach" in str(effect_events(_condition_ctx(far, me, "gob")))
    assert "Name a living creature" in str(effect_events(_condition_ctx(far, me, "nobody")))


def test_fishing_at_water_gives_supplies_once_per_place() -> None:
    state = at(DOCKS, hero(gear=["fishing-tackle"]))
    state.camp_supplies = 3
    events = use(state, "fishing-tackle", rng=ScriptedRng(15))
    check = next(e for e in events if isinstance(e, CheckResolved))
    assert (check.result.dc, check.result.success) == (FORAGE_DC, True)
    gain = next(e for e in events if isinstance(e, CampSuppliesChanged))
    assert (gain.delta, gain.camp_supplies) == (2, 5)
    assert next(e for e in events if isinstance(e, ItemUsed)).forage
    run(state, events)
    assert state.world.foraged == [DOCKS]
    assert "already given" in refusal(use(state, "fishing-tackle"))


def test_a_failed_hunt_gives_nothing_but_spends_the_place() -> None:
    state = at(SHRINE, hero(gear=["hunting-trap"]))
    events = use(state, "hunting-trap", rng=ScriptedRng(2))
    assert not any(isinstance(e, CampSuppliesChanged) for e in events)
    run(state, events)
    assert state.world.foraged == [SHRINE]
    assert qty(state, "hero", "hunting-trap") == 1


def test_healers_kit_stabilizes_a_dying_ally_without_a_check() -> None:
    down = hero("ally")
    down.hp = 0
    state = at(DOCKS, hero(gear=["healers-kit"]), down)
    events = use(state, "healers-kit", "ally")
    assert any(isinstance(e, Stabilized) for e in events)
    assert not any(isinstance(e, CheckResolved) for e in events)
    healthy = at(DOCKS, hero(gear=["healers-kit"]), hero("ally"))
    assert "not a dying ally" in refusal(use(healthy, "healers-kit", "ally"))


def test_healers_kit_in_a_fight_needs_the_ally_in_your_zone() -> None:
    down = hero("ally")
    down.hp = 0
    state = gear_fight(CAVE, hero(gear=["healers-kit"]), (down, Side.PARTY, "b"))
    assert "out of reach" in refusal(use(state, "healers-kit", "ally"))
    foe = monster("gob")
    foe.hp = 0
    state = gear_fight(CAVE, hero(gear=["healers-kit"]), (foe, Side.HOSTILE, "a"))
    assert "not a dying ally" in refusal(use(state, "healers-kit", "gob"))


def test_herbalism_crafts_a_poultice_at_a_long_rest_with_the_proficiency() -> None:
    state = at(DOCKS, hero(gear=["herbalism-kit"], tools=["herbalism-kit"]))
    state.camp_supplies = 3
    events = use(state, "herbalism-kit", resting=True)
    spent = next(e for e in events if isinstance(e, CampSuppliesChanged))
    made = next(e for e in events if isinstance(e, InventoryChanged))
    assert (spent.delta, spent.camp_supplies) == (-2, 1)
    assert (made.item, made.delta, made.qty) == ("herbal-poultice", 1, 1)
    untrained = at(DOCKS, hero(gear=["herbalism-kit"]))
    untrained.camp_supplies = 3
    assert "proficiency" in refusal(use(untrained, "herbalism-kit", resting=True))
    state.camp_supplies = 1
    assert "camp supplies" in refusal(use(state, "herbalism-kit", resting=True))


def test_cartographers_tools_chart_the_ways_out() -> None:
    state = at(DOCKS, hero(gear=["cartographers-tools"]))
    unknown = [n for n in state.world.neighbours[DOCKS] if n not in state.world.visited]
    events = use(state, "cartographers-tools")
    charted = next(e for e in events if isinstance(e, PlacesCharted))
    assert list(charted.nodes) == unknown
    run(state, events)
    shown = public_map(state)
    assert shown is not None
    names = {n.id: n.name for n in shown.nodes}
    assert all(names[n] != "Unexplored" for n in unknown)
    assert "already known" in refusal(use(state, "cartographers-tools"))


def test_alerted_place_blocks_the_party_s_surprise() -> None:
    state = at(CAVE, hero(gear=["torch"]))
    run(state, use(state, "torch"))
    assert state.world.alerted == CAVE
    assert party_surprise(state, SurpriseKind.HOSTILE) is SurpriseKind.NONE
    assert party_surprise(state, SurpriseKind.PARTY) is SurpriseKind.PARTY
    setup = setup_for(["hero"], ["goblin"], SurpriseKind.HOSTILE)
    events = start_encounter(random.Random(1), state, setup, srd().monsters)
    assert not any(isinstance(e, ConditionApplied) for e in events)


def test_surprise_still_works_at_a_quiet_place() -> None:
    state = at(CAVE, hero())
    setup = setup_for(["hero"], ["goblin"], SurpriseKind.HOSTILE)
    events = start_encounter(random.Random(1), state, setup, srd().monsters)
    assert any(isinstance(e, ConditionApplied) for e in events)


def test_every_shipped_effect_kind_is_dispatched() -> None:
    kinds = {u.effect.kind for u in item_use_data().uses}
    assert kinds <= {
        "light_place",
        "boon",
        "surface",
        "damage",
        "unlock",
        "supplies",
        "stabilize",
        "craft",
        "cast_spell",
        "reveal_map",
        "condition",
        "ignite",
    }
    assert not any(
        isinstance(e, PlaceAlerted) for e in use(at(DOCKS, hero(gear=["spyglass"])), "spyglass")
    )
