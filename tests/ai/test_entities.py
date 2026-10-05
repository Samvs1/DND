"""Entity name registry and scene view (M4.3): the names the guard will check against."""

from aidm.dm.entities import display_name, entity_registry
from aidm.models.world import FeatureKind, WorldFeature, WorldItem
from aidm.models.world_events import FeatureDiscovered, FeatureIntroduced, ItemPlaced
from aidm.rules.scene import current_scene
from aidm.session.reducer import apply
from tests.ai.tool_fixtures import add_npc, party_state


def _feature(fid: str, name: str, hidden: bool) -> WorldFeature:
    return WorldFeature(
        id=fid,
        kind=FeatureKind.DOOR,
        name=name,
        node_id="town",
        hidden=hidden,
        discover_dc=12 if hidden else None,
    )


def test_display_name() -> None:
    assert display_name("chain-mail") == "Chain Mail"
    assert display_name("crossbow_light") == "Crossbow Light"


def test_registry_lists_every_known_name() -> None:
    state = party_state()
    add_npc(state)
    state.world.lore_names = ["The Drowned King"]
    state.world.node_names = {"forest": "Whisperwood"}
    apply(state, ItemPlaced(item=WorldItem(id="it-1", name="silver key", node_id="town")))
    reg = entity_registry(state)
    assert {"Fighter", "Wizard"} <= reg.party
    assert reg.npcs == {"Mira"}
    assert "Longsword" in reg.items and "silver key" in reg.items
    assert {"Whisperwood", "Town", "Crypt"} <= reg.places
    assert reg.is_known("the drowned king") and reg.is_known("MIRA")
    assert not reg.is_known("Sister Kelene")


def test_hidden_feature_not_visible_until_discovered() -> None:
    state = party_state()
    apply(state, FeatureIntroduced(feature=_feature("feat-door", "secret door", True)))
    apply(state, FeatureIntroduced(feature=_feature("feat-gate", "iron gate", False)))
    reg = entity_registry(state)
    assert not reg.is_known("secret door") and "secret door" in reg.all_names
    assert reg.is_known("iron gate")
    assert current_scene(state).feature_ids == ("feat-gate",)
    apply(state, FeatureDiscovered(feature_id="feat-door"))
    assert entity_registry(state).is_known("secret door")
    assert current_scene(state).feature_ids == ("feat-door", "feat-gate")


def test_dead_creatures_not_visible() -> None:
    state = party_state()
    state.creatures["wizard"].dead = True
    reg = entity_registry(state)
    assert "Wizard" in reg.dead
    assert "wizard" not in current_scene(state).party_ids


def test_scene_view_exits_and_turn() -> None:
    state = party_state()
    scene = current_scene(state)
    assert scene.exits == ("forest", "crypt") and scene.locked_exits == ("crypt",)
    assert scene.node_name == "Town" and scene.turn == 0
