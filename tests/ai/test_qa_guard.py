"""Guard regressions from the adversarial QA report (docs/QA_REPORT.md QA-03, QA-10; M9.5)."""

import pytest

from aidm.dm.guard import check_prose, prose_checker
from aidm.dm.guard_types import ViolationKind
from aidm.models.state import GameState
from tests.ai.guard_fixtures import add_dead, inn_state


def _kinds(text: str, state: GameState) -> set[ViolationKind]:
    return {v.kind for v in check_prose(text, state).violations}


@pytest.mark.parametrize(
    "text",
    [
        "Brannoc staggers. By the time Aria reaches him, he is gone, still and cold.",
        "Brannoc sinks to his knees without a word. He is gone, the stillness of him terrible.",
        "Brannoc clutches his chest, and he breathes his last.",
        "Mira sways behind the bar. She dies without a sound.",
        "Brannoc is gone, still and cold on the boards.",
    ],
)
def test_qa_03_pronoun_death_claim_about_a_living_hero_is_blocked(text: str) -> None:
    assert ViolationKind.LIVING_DECLARED_DEAD in _kinds(text, inn_state())


def test_qa_03_pronoun_resolves_across_sentences_of_one_narration() -> None:
    check = prose_checker(inn_state())
    assert check("Brannoc sinks to his knees without a word.").ok
    report = check("He breathes his last on the wet boards.")
    assert ViolationKind.LIVING_DECLARED_DEAD in {v.kind for v in report.violations}


@pytest.mark.parametrize(
    "text",
    [
        "When you look back at the door, he is gone.",
        "Brannoc slips out into the night; by morning he is gone.",
        "Hobb walks the length of the smoky common room, and at last he kneels by the old corpse.",
        "Brannoc swears he will not die in this inn tonight.",
        "If he dies out there, Mira says, nobody will sing for him.",
        "The ogre crashes to the floor. He breathes his last with a long rattle.",
        "Aria is cold and wet, but she is gone from the doorway before you can call to her.",
    ],
)
def test_qa_03_clean_pronoun_prose_passes(text: str) -> None:
    state = inn_state()
    add_dead(state, "ogre-1", "Ogre")
    report = check_prose(text, state)
    assert report.ok, [(v.kind.value, v.span, v.detail) for v in report.violations]


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        (
            "You leave the inn behind and arrive at the Old Crypt, where the dead wait.",
            ViolationKind.FALSE_TRAVEL,
        ),
        ("You step into Whisperwood.", ViolationKind.FALSE_TRAVEL),
        (
            "Mira presses a purse of fifty gold coins into Aria's hand.",
            ViolationKind.UNEARNED_REWARD,
        ),
        ("Hobb hands Brannoc a gleaming sword.", ViolationKind.UNEARNED_REWARD),
        (
            "A one-eyed sea captain steps out of the fog and offers to join you.",
            ViolationKind.INVENTED_STRANGER,
        ),
        ("An old hermit approaches the bar.", ViolationKind.INVENTED_STRANGER),
    ],
)
def test_qa_10_false_travel_rewards_and_strangers_are_blocked(
    text: str, kind: ViolationKind
) -> None:
    assert kind in _kinds(text, inn_state())


@pytest.mark.parametrize(
    "text",
    [
        "You arrive at the long oak bar of the Lantern Inn and shake off the rain.",
        "From the doorway you can see the road that leads to Whisperwood.",
        "You talk of heading for the Old Crypt at dawn.",
        "Aria hands Mira three silver coins for the room.",
        "Mira hands Aria a pouch of bread and dried apples.",
        "A guard approaches the bar; Hobb nods at you.",
        "Mira tells you of a stranger who once walked these roads.",
        "A cold wind slips under the door as you step into the common room.",
    ],
)
def test_qa_10_clean_prose_passes(text: str) -> None:
    report = check_prose(text, inn_state())
    assert report.ok, [(v.kind.value, v.span, v.detail) for v in report.violations]
