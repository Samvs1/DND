"""M27.8: the public views carry light, darkness, boons and locks (GOAL_ITEMS, What players see)."""

from aidm.data.character_data import character_registries
from aidm.models.character import InventoryItem
from aidm.models.encounter import Side
from aidm.models.item_events import BoonGained, LightLit
from aidm.models.state import GameState
from aidm.models.world import ActiveBoon, FeatureKind, LockInfo, WorldFeature
from aidm.models.world_events import FeatureIntroduced, PartyMoved
from aidm.models.zones import Zone, ZoneEdge, ZoneMap
from aidm.rules.creation import build_character
from aidm.rules.sheet import build_sheet
from aidm.session.reducer import apply
from aidm.session.views import public_combat, public_creature, public_scene
from tests.unit.rules.combat_fixtures import REGS, fight, monster
from tests.unit.rules.creation_fixtures import default_choices
from tests.unit.rules.encounter_fixtures import make_pc
from tests.unit.rules.test_light import CAVE, DOCKS, _at, _dwarf


def _chain() -> ZoneMap:
    zones = [Zone(id=z, name=z.upper()) for z in "abcd"]
    return ZoneMap(zones=zones, edges=[ZoneEdge(a=x, b=y, feet=15) for x, y in ("ab", "bc", "cd")])


def _fight(base: GameState) -> GameState:
    placements = [(make_pc("hero"), Side.PARTY, "a"), (monster("gob"), Side.HOSTILE, "d")]
    return fight(placements, _chain(), base=base)


def test_scene_and_zones_say_when_it_is_dark() -> None:
    cave = _at(CAVE)
    cave.creatures["hero"] = make_pc("hero")
    scene = public_scene(cave)
    assert scene is not None and scene.dark
    docks = public_scene(_at(DOCKS))
    assert docks is not None and not docks.dark
    combat = public_combat(_fight(_at(CAVE)))
    assert combat is not None
    assert all(z.dark and not z.lit and z.lit_by == () for z in combat.zones)
    daylight = public_combat(_fight(_at(DOCKS)))
    assert daylight is not None and all(not z.dark and z.lit for z in daylight.zones)


def test_a_lit_bearer_lights_their_zone_and_the_next_one() -> None:
    state = _fight(_at(CAVE))
    apply(state, LightLit(creature_id="hero", item="torch"))
    combat = public_combat(state)
    assert combat is not None
    zones = {z.id: z for z in combat.zones}
    assert [zones[z].lit for z in "abcd"] == [True, True, False, False]  # a touching light
    assert zones["a"].lit_by == ("hero",) and zones["c"].lit_by == ()
    hero = public_creature(state.creatures["hero"], state)
    assert hero.light == "Torch"


def test_hero_view_has_darkvision_light_and_boons() -> None:
    state = _at(CAVE)
    dwarf = _dwarf("dwarf")
    state.creatures["dwarf"] = dwarf
    apply(state, LightLit(creature_id="dwarf", item="lantern-hooded"))
    boon = ActiveBoon(
        creature_id="dwarf",
        use_id="rope-hempen-climb",
        name="Rope",
        skills=("athletics", "sleight_of_hand"),
        scope="place",
    )
    apply(state, BoonGained(boon=boon.model_copy(update={"node": state.world.current_node})))
    view = public_creature(dwarf, state)
    assert (view.darkvision, view.light) == (60, "Lantern")
    assert [(b.name, b.helps) for b in view.boons] == [("Rope", ("Athletics", "Sleight Of Hand"))]
    plain = public_creature(dwarf)  # an old caller without state: the defaults
    assert (plain.darkvision, plain.light, plain.boons) == (0, "", ())
    apply(state, PartyMoved(from_node=CAVE, to_node=DOCKS, scene_index=2))
    assert public_creature(dwarf, state).boons == ()  # a place boon ends with the place


def test_a_locked_feature_shows_its_tier() -> None:
    state = _at(CAVE)
    node = state.world.current_node
    assert node is not None
    chest = WorldFeature(
        id="feat-chest",
        kind=FeatureKind.CACHE,
        name="Old chest",
        node_id=node,
        lock=LockInfo(opens=FeatureKind.CACHE),
    )
    apply(state, FeatureIntroduced(feature=chest))
    scene = public_scene(state)
    assert scene is not None
    assert {f.name: f.locked for f in scene.features}["Old chest"] == "medium"


def test_sheet_item_lines_list_their_uses_here() -> None:
    hero = make_pc("hero")
    assert hero.pc is not None
    for item in ("torch", "crowbar", "potion-of-healing"):
        hero.pc.inventory.append(InventoryItem(item=item, qty=1))
    lines = {i.item: i for i in build_sheet(hero, REGS.chars).inventory}
    torch = lines["torch"].uses
    assert [(u.use_id, u.when, u.verb) for u in torch] == [("torch-light", "dark_place", "light")]
    assert [u.when for u in lines["crowbar"].uses] == ["locked"]
    assert lines["potion-of-healing"].uses == []  # a fight use or none: never on the card


def test_darkvision_comes_from_the_race() -> None:
    # SRD 5.1: elves and dwarves have darkvision 60 ft; humans have none.
    regs = character_registries()
    elf = build_character(default_choices("rogue", "elf", "high-elf"), regs, "elf")
    human = build_character(default_choices("fighter", "human", None), regs, "human")
    assert public_creature(elf, _at(CAVE)).darkvision == 60
    assert public_creature(human, _at(CAVE)).darkvision == 0
