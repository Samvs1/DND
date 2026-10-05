"""A named party in a small inn scene for the prose guard tests (M4.6).

Party: Aria (fighter), Brannoc (rogue), Celes (wizard), Doran (cleric); each carries a potion of
healing. At the Lantern Inn ("town"): Mira the innkeeper and Hobb the guard. Elsewhere (the
forest): Captain Voss. Lore allow-list: Aurelion (a god), Emberfall (a city). A discovered
"rusted lever" and an undiscovered "concealed hatch" are at the inn.
"""

from aidm.models.state import Creature, CreatureKind, GameState
from aidm.models.world import FeatureKind, WorldFeature
from aidm.models.world_events import FeatureIntroduced
from aidm.session.reducer import apply
from tests.ai.tool_fixtures import add_npc, party_state

NAMES = {"fighter": "Aria", "rogue": "Brannoc", "wizard": "Celes", "cleric": "Doran"}


def _feature(fid: str, name: str, kind: FeatureKind, *, hidden: bool) -> WorldFeature:
    return WorldFeature(
        id=fid,
        kind=kind,
        name=name,
        node_id="town",
        hidden=hidden,
        discover_dc=12 if hidden else None,
        discovered=False,
    )


def inn_state() -> GameState:
    state = party_state()
    for cid, name in NAMES.items():
        state.creatures[cid].name = name
    world = state.world
    world.node_names = {"town": "Lantern Inn", "forest": "Whisperwood", "crypt": "Old Crypt"}
    world.descriptions = {"town": "A smoky common room with a long oak bar and a stone hearth."}
    world.lore_names = ["Aurelion", "Emberfall"]
    add_npc(state, "npc-mira", name="Mira", role="innkeeper")
    add_npc(state, "npc-hobb", name="Hobb", role="guard", archetype="guard")
    add_npc(state, "npc-voss", name="Captain Voss", role="guard captain", node_id="forest")
    apply(
        state,
        FeatureIntroduced(
            feature=_feature("feat-lever", "rusted lever", FeatureKind.LEVER, hidden=False)
        ),
    )
    apply(
        state,
        FeatureIntroduced(
            feature=_feature("feat-hatch", "concealed hatch", FeatureKind.DOOR, hidden=True)
        ),
    )
    return state


def add_dead(state: GameState, cid: str, name: str, *, dead: bool = True) -> Creature:
    creature = Creature(
        id=cid,
        name=name,
        kind=CreatureKind.MONSTER,
        max_hp=40,
        hp=0 if dead else 40,
        dead=dead,
    )
    state.creatures[cid] = creature
    return creature


def empty_scene(state: GameState) -> GameState:
    state.world.current_node = "crypt"
    return state
