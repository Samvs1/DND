"""Contract rules C1-C4 (generated quests) on real saves: each violating case is a quest a
round-1..8 table really registered; the passing case is a round-7 save with none."""

from scripts.contractlib.quest_rules import QuestRules
from tests.unit.contract.helpers import fixture, rules, run

CLEAN = "m39-r7-quests"


def _found(name: str, rule: str) -> list[str]:
    return [f.reason for f in rules(run(fixture(name), QuestRules()), rule)]


def test_contract_c_rules_pass_on_a_clean_save() -> None:
    found = run(fixture(CLEAN), QuestRules())
    assert found == []


def test_contract_c1_a_friend_as_the_target_is_found() -> None:
    """m39-r7-full 436: Straighten the River sends the party against Isca Murkline, a friend."""
    assert any("isca-murkline is a friend" in r for r in _found("m39-r7-full", "C1"))


def test_contract_c1_one_person_two_records_is_found() -> None:
    """m29-p3 event 22: a boss and a resident with the name Regent Varek."""
    assert any("Regent Varek" in r for r in _found("m29-p3", "C1"))


def test_contract_c2_a_free_step_is_found() -> None:
    """m29-r2-p8 774: A Name for the Road has a step the engine cannot check."""
    assert any("a-name-for-the-road" in r and "free step" in r for r in _found("m29-r2-p8", "C2"))


def test_contract_c3_a_step_done_without_the_check_is_found() -> None:
    """m39-r7-full 444: the fight at the Grey Bog counted the moment the quest was accepted."""
    assert any("straighten-the-river: step 0 (clear)" in r for r in _found("m39-r7-full", "C3"))


def test_contract_c4_find_three_hand_over_one_is_found() -> None:
    """m32-r5-full 602: Salt for the Elders finds 3 and hands over 1."""
    assert any("find 3 x Free-Given Salt, hand over 1" in r for r in _found("m32-r5-full", "C4"))


def test_contract_c4_the_reward_is_the_item_asked_is_found() -> None:
    """m29-p3 install: the reward of The Last Egg is the Brood-egg it asks for."""
    assert any("Brood-egg" in r for r in _found("m29-p3", "C4"))
