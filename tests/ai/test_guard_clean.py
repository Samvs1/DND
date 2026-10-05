"""Guard false positives (M4.6, SPEC 6.5): realistic clean narration must pass untouched."""

import pytest

from aidm.dm.guard import check_prose
from aidm.models.state import GameState
from tests.ai.guard_fixtures import add_dead, empty_scene, inn_state

INN_PARAGRAPHS = (
    "You push through the door of the Lantern Inn, and warmth from the stone hearth rolls over"
    " you. Mira looks up from the long oak bar and smiles. Hobb, leaning on his spear, nods once.",
    'Mira sets four mugs down. "Road from Emberfall treat you well?" she asks. Aria laughs and'
    " says it was quiet, too quiet. Celes the wizard is already reading by the fire.",
    "Brannoc runs a thumb along the rusted lever by the hearth. It groans but holds. Doran"
    " murmurs a prayer to Aurelion and tells him to leave it be.",
    "The smoky common room hums with the crackle of the fire. Your potion of healing sits"
    " unbroken in your pack, and Aria's shield leans against the bench, scratched but whole.",
    "Hobb's eyes narrow as Brannoc counts his coins. The guard says nothing, but his hand"
    " drifts to his spear. Mira clears her throat, and the moment passes.",
    "Celes speaks a few words in Elvish, and a tiny light dances above her palm. Mira gasps,"
    " delighted, while Doran shakes his head with a fond smile.",
    "You search the walls by the hearth but find no hidden door, only soot and old stone. The"
    " rusted lever is the only thing out of place here.",
    "Aria's chest tightens as she remembers the road. Mira, wiping a mug, tells you that Captain"
    " Voss warned travellers about the woods to the north.",
    "Doran, the cleric, lays a hand on Aria's arm. Light flows from his fingers, and her bruises"
    " fade. Hobb watches the glow with wide eyes.",
    "Night settles over the Lantern Inn. Brannoc keeps watch by the window, dagger in hand,"
    " while the others sleep. Nothing stirs outside but the wind.",
    "At dawn, Mira hands Aria a pouch of bread and dried apples. The Lantern Inn's door creaks"
    " shut behind you as you set out toward Whisperwood, 2.5 miles of mud ahead.",
)

FIGHT_PARAGRAPHS = (
    "The goblin shrieks and lunges at Aria, but her longsword turns the blow aside. Brannoc"
    " darts in behind it, dagger flashing.",
    "Goblins pour from the shadows. Celes raises her quarterstaff, and fire blooms across the"
    " floor as the fighter braces her shield.",
    "The fallen goblin lies still, its blade broken beneath it. The other one snarls and backs"
    " toward the wall.",
)

EMPTY_PARAGRAPHS = (
    "The Old Crypt is silent. Dust drifts in the light of Celes's spell, and the air tastes"
    " of stone. You are alone with your own breathing.",
    "Doran kneels by a cracked sarcophagus and whispers to Aurelion. You think of Mira's warm"
    " hearth back at the inn and press on.",
)


def _assert_clean(text: str, state: GameState) -> None:
    report = check_prose(text, state)
    assert report.ok, [(v.kind.value, v.span, v.detail) for v in report.violations]


@pytest.mark.parametrize("text", INN_PARAGRAPHS)
def test_clean_inn_narration_passes(text: str) -> None:
    _assert_clean(text, inn_state())


@pytest.mark.parametrize("text", FIGHT_PARAGRAPHS)
def test_clean_fight_narration_passes(text: str) -> None:
    state = inn_state()
    add_dead(state, "goblin-1", "Goblin")
    add_dead(state, "goblin-2", "Goblin", dead=False)
    _assert_clean(text, state)


@pytest.mark.parametrize("text", EMPTY_PARAGRAPHS)
def test_clean_empty_scene_narration_passes(text: str) -> None:
    _assert_clean(text, empty_scene(inn_state()))


def test_at_least_ten_clean_paragraphs() -> None:
    assert len(INN_PARAGRAPHS) + len(FIGHT_PARAGRAPHS) + len(EMPTY_PARAGRAPHS) >= 10
