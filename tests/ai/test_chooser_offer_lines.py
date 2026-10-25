"""M36.9 iteration 2: the offer answers are shown with what they do (grouped, the model saw only
`offer:<item>: fight, ..., parley:persuasion`), neighbouring entries that differ only inside their
bracket share one line, and the Persuasion surrender reads as an offer of mercy. FakeLLM only."""

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
        "offer:parley:persuasion, offer:parley:intimidation, offer:parley:deception = Parley to"
        " end it without a fight (Persuasion: plead, reason, bargain; Intimidation: threaten;"
        " Deception: bluff or lie)"
    ) in lines


def test_a_parley_answer_label_is_its_own_fast_path_key() -> None:
    menu = menu_at(OFFER_RUN, OFFER_SEQ, "pc-p2")
    line = "Parley to end it without a fight (Deception: bluff or lie)"
    wanted = MenuChoice(steps=(MenuStep(entry="offer:parley:deception"),))
    assert exact_choice(menu, line) == wanted
    assert exact_choice(menu, "Parley to end it without a fight") is None  # shared: never a guess


def test_entries_with_notes_or_no_bracket_keep_their_own_lines() -> None:
    lines = menu_lines(menu_at(OFFER_RUN, OFFER_SEQ, "pc-p2"))
    assert sum(1 for line in lines if line.startswith("rest:")) == 2
    assert any(line.startswith("search:perception = ") for line in lines)
    assert any(line.startswith("search:investigation = ") for line in lines)


def test_fight_surrender_by_persuasion_offers_mercy() -> None:
    labels = {e.id: e.label for e in menu_at(FIGHT_RUN, FIGHT_SEQ, "pc-p6").entries}
    assert labels["surrender:persuasion"].startswith("Call on the foes to yield and be spared (")
    assert labels["surrender:intimidation"].startswith("Demand the foes surrender (")
