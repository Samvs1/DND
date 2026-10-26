"""M36.9 iteration 2: the offer answers are shown with what they do (grouped, the model saw only
`offer:<item>: fight, ..., parley:persuasion`), neighbouring entries that differ only inside their
bracket share one line, and the Persuasion surrender reads as an offer of mercy. M38.4: the labels
say what the entries do (who surrenders, a parley is words and a roll). FakeLLM only."""

from aidm.dm.chooser import exact_choice
from aidm.dm.chooser_menu import menu_lines
from aidm.models.action_menu import MenuChoice, MenuStep
from tests.ai.chooser_fixtures import menu_at

OFFER_RUN, OFFER_SEQ = "r2-p7", 773  # "Brienne lays the unfinished chime down before Hesk"
FIGHT_RUN, FIGHT_SEQ = "r3-items", 688  # "I accept Cultist C's surrender ... we spare him"


def test_offer_answers_are_listed_with_what_they_do() -> None:
    lines = menu_lines(menu_at(OFFER_RUN, OFFER_SEQ, "pc-p2"))
    assert not any(line.startswith("offer:<item>") for line in lines)
    assert "offer:fight = Fight them" in lines
    assert "offer:surprise = Sneak up and strike first (group Stealth, then the fight)" in lines
    assert "offer:escape = Slip away the way you came (group Stealth or Athletics)" in lines


def test_parley_answers_share_one_line() -> None:
    lines = menu_lines(menu_at(OFFER_RUN, OFFER_SEQ, "pc-p2"))
    assert (
        "offer:parley:persuasion, offer:parley:intimidation, offer:parley:deception = Speak to"
        " end it without a fight, one roll: a failure starts it (Persuasion: plead, reason,"
        " bargain; Intimidation: threaten; Deception: bluff or lie)"
    ) in lines


def test_a_parley_answer_label_is_its_own_fast_path_key() -> None:
    menu = menu_at(OFFER_RUN, OFFER_SEQ, "pc-p2")
    base = "Speak to end it without a fight, one roll: a failure starts it"
    wanted = MenuChoice(steps=(MenuStep(entry="offer:parley:deception"),))
    assert exact_choice(menu, f"{base} (Deception: bluff or lie)") == wanted
    assert exact_choice(menu, base) is None  # shared: never a guess


def test_entries_with_notes_or_no_bracket_keep_their_own_lines() -> None:
    lines = menu_lines(menu_at(OFFER_RUN, OFFER_SEQ, "pc-p2"))
    assert sum(1 for line in lines if line.startswith("rest:")) == 2
    assert any(line.startswith("search:perception = ") for line in lines)
    assert any(line.startswith("search:investigation = ") for line in lines)


def test_v1_m38_surrender_labels_say_the_foes_surrender_to_you() -> None:
    """M38.4 cause C: "I surrender" picked the Persuasion demand ("Call on the foes to yield and
    be spared"); both forms now say who surrenders, the Persuasion one still offers mercy, and
    the shared stem is no fast-path key (never a guess)."""
    menu = menu_at(FIGHT_RUN, FIGHT_SEQ, "pc-p6")
    labels = {e.id: e.label for e in menu.entries}
    assert labels["surrender:persuasion"].startswith("Make the foes surrender to you (Persuasion")
    assert labels["surrender:persuasion"].endswith(", action: offer mercy)")
    assert labels["surrender:intimidation"].startswith("Make the foes surrender to you (Intim")
    assert labels["surrender:intimidation"].endswith(", action: threaten)")
    assert exact_choice(menu, "Make the foes surrender to you") is None
    assert exact_choice(menu, "I surrender") is None


def test_v1_m38_parley_label_says_it_is_words_and_a_roll() -> None:
    """M38.4 cause C: "I bow to the thug" and "I won't attack the thug" picked the parley; its
    label now says it is spoken, one roll, and a failure starts the fight."""
    labels = {e.id: e.label for e in menu_at(OFFER_RUN, OFFER_SEQ, "pc-p2").entries}
    assert labels["offer:parley:persuasion"] == (
        "Speak to end it without a fight, one roll: a failure starts it"
        " (Persuasion: plead, reason, bargain)"
    )
    assert labels["surrender"] == "Make the foes surrender to you (Intimidation)"


def test_a_sure_parley_says_it_holds_without_a_roll() -> None:
    """The master whose peace route is done hears the party out (`sure_parley`): no roll."""
    menu = menu_at("m31-r4-full", 1150, "pc-p4")
    label = next(e.label for e in menu.entries if e.id == "offer:parley:persuasion")
    assert (
        label
        == "Speak to end it without a fight, sure to hold (Persuasion: plead, reason, bargain)"
    )
