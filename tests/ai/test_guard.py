"""Prose guard checks (M4.6, SPEC 6.5, 13): one test per v1 hallucination class."""

from collections.abc import Sequence

from aidm.dm.guard import check_prose
from aidm.dm.guard_types import ViolationKind
from aidm.models.events import AnyEvent, InventoryChanged
from aidm.models.state import GameState
from aidm.models.world_events import FeatureDiscovered
from aidm.session.reducer import apply
from tests.ai.guard_fixtures import add_dead, empty_scene, inn_state

K = ViolationKind


def _kinds(text: str, state: GameState, events: Sequence[AnyEvent] = ()) -> set[ViolationKind]:
    return {v.kind for v in check_prose(text, state, events=events).violations}


def _spans(text: str, state: GameState) -> list[str]:
    return [v.span for v in check_prose(text, state).violations]


def test_v1_hidden_door_synonyms() -> None:
    state = inn_state()
    claims = (
        "A section of granite shifts, revealing a hidden seam in the wall.",
        "Behind the tapestry you spot a secret door.",
        "A concealed passage yawns beneath the stairs.",
        "The bookshelf slides aside, revealing a narrow stairway.",
        "A pressure plate clicks under your boot.",
        "Brannoc notices a tripwire stretched across the hall.",
        "An iron-bound chest waits in the corner.",
        "A trapdoor is set into the floorboards.",
        "There is a false wall here, cleverly disguised.",
    )
    for text in claims:
        assert K.UNLISTED_FEATURE in _kinds(text, state), text


def test_listed_and_negated_features_are_fine() -> None:
    state = inn_state()
    assert _kinds("Aria pulls the rusted lever and it groans.", state) == set()
    assert _kinds("There is no hidden door here, only solid stone.", state) == set()
    assert _kinds("Brannoc finds no secret passage behind the hearth.", state) == set()
    assert _kinds("You step through the door of the inn.", state) == set()
    assert _kinds("The arrow strikes his chest.", state) == set()
    assert K.UNLISTED_FEATURE in _kinds("A concealed hatch creaks open.", state)
    apply(state, FeatureDiscovered(feature_id="feat-hatch", creature_id="rogue"))
    assert _kinds("The concealed hatch creaks open.", state) == set()


def test_v1_unbroken_not_flagged() -> None:
    state = inn_state()
    for text in (
        "Your potion of healing is unbroken.",
        "The vial is not broken.",
        "Aria's shield remains unbroken despite the blow.",
        "The flask never shatters; you catch it in time.",
        "Celes grips her quarterstaff, unharmed.",
    ):
        assert _kinds(text, state) == set(), text


def test_destroyed_items_flagged_unless_an_event_says_so() -> None:
    state = inn_state()
    smash = "The vial slips from your fingers, and wet glass shards scatter."
    assert _kinds(smash, state) == {K.ITEM_DESTROYED}
    assert _kinds("Aria's longsword snaps in two.", state) == {K.ITEM_DESTROYED}
    assert _kinds("The goblin's blade shatters against the stone.", state) == set()
    drank: list[AnyEvent] = []
    for cid in ("fighter", "rogue", "wizard", "cleric"):
        event = InventoryChanged(creature_id=cid, item="potion-of-healing", delta=-1, qty=0)
        apply(state, event)
        drank.append(event)
    assert _kinds(smash, state, drank) == set()


def test_v1_dead_boss_never_described_alive() -> None:
    state = inn_state()
    add_dead(state, "boss", "Gorrak")
    for text in (
        "Gorrak rises and roars at you.",
        "Gorrak doesn't even slow as he charges.",
        "With a snarl, Gorrak lunges at Aria.",
        "Gorrak still stands in the doorway.",
    ):
        assert K.DEAD_ACTING in _kinds(text, state), text
    for text in (
        "Gorrak's lifeless body lies across the threshold.",
        "The corpse of Gorrak is cold.",
        "You step past where Gorrak fell.",
    ):
        assert K.DEAD_ACTING not in _kinds(text, state), text


def test_one_of_two_same_named_creatures_dead_is_not_flagged() -> None:
    state = inn_state()
    add_dead(state, "goblin-1", "Goblin")
    add_dead(state, "goblin-2", "Goblin", dead=False)
    assert K.DEAD_ACTING not in _kinds("The goblin lunges at Doran.", state)


def test_v1_crowd_pluralisation() -> None:
    state = inn_state()
    assert _kinds("The guards watch you closely from the door.", state) == set()
    assert _kinds("Captain Voss and the guards block the stair.", state) == {K.ABSENT_NPC}
    assert _spans("Voss barks an order at the guards.", state) == ["Voss"]
    lone = inn_state()
    apply(lone, _move_npc(lone, "npc-hobb"))
    assert K.INVENTED_CROWD in _kinds("A throng of onlookers murmurs as you enter.", lone)
    assert _kinds("No crowd gathers; only Mira watches.", lone) == set()


def _move_npc(state: GameState, npc_id: str) -> AnyEvent:
    from aidm.models.world_events import NpcIntroduced

    npc = state.world.npcs.pop(npc_id).model_copy(update={"node_id": "forest"})
    return NpcIntroduced(npc=npc)


def test_v1_empty_scene_absent_npcs() -> None:
    state = empty_scene(inn_state())
    assert _kinds("Mira waves to you from the shadows.", state) == {K.ABSENT_NPC}
    assert K.ABSENT_NPC in _kinds("The innkeeper smiles at you.", state)
    assert _kinds("You remember Mira's warning about the road.", state) == set()
    assert _kinds("The crypt is silent and cold.", state) == set()


def test_v1_erasing_present_npcs() -> None:
    state = inn_state()
    assert K.ERASED_PRESENT in _kinds("The vast hall holds only you.", state)
    assert K.ERASED_PRESENT not in _kinds("You are alone.", empty_scene(inn_state()))


def test_v1_wrong_class() -> None:
    state = inn_state()
    assert _kinds("Aria the wizard raises her sword.", state) == {K.WRONG_IDENTITY}
    assert _kinds("The young cleric Celes mutters a spell.", state) == {K.WRONG_IDENTITY}
    assert _kinds("The ranger nocks an arrow.", state) == {K.WRONG_IDENTITY}
    assert _kinds("Celes the wizard mutters a spell.", state) == set()
    assert _kinds("The cleric whispers a prayer to Aurelion.", state) == set()


def test_v1_misnamed_party_member() -> None:
    state = inn_state()
    assert _kinds("Aira swings her longsword.", state) == {K.WRONG_IDENTITY}
    assert _kinds("Behind you, Branoc readies his rapier.", state) == {K.WRONG_IDENTITY}


def test_v1_invented_npc_name() -> None:
    state = inn_state()
    assert _spans("Sister Kelene and her grizzled sergeant step out of the shadows.", state) == [
        "Kelene"
    ]
    assert _spans("Brother-Captain Serev salutes the party.", state) == ["Serev"]
    assert _spans("Kelene says nothing.", state) == ["Kelene"]
    assert _spans("Kelene's lantern flickers.", state) == ["Kelene"]
    assert _spans("Mr. Ash watches from the bar.", state) == ["Ash"]
    assert _spans("Miranda pours you a drink.", state) == ["Miranda"]


def test_possessives_plurals_and_lore_are_known() -> None:
    state = inn_state()
    add_dead(state, "goblin-1", "Goblin", dead=False)
    for text in (
        "Mira's smile widens as Hobb's spear dips.",
        "Goblins pour through the breach, and Brannoc's dagger flashes.",
        "Doran calls on Aurelion, and the light of Emberfall's temples fills his mind.",
        "On Monday, the Lantern Inn fills with travellers from Whisperwood.",
        "Celes speaks in Elvish to the old guard.",
    ):
        assert _kinds(text, state) == set(), text
