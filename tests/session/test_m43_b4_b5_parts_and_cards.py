"""M43.2 contract rules B4 and B5 at the table (docs/next/M43_CONTRACT.md).
B4: every part of a line plays in order, or the dropped part is told, as a refusal with the
reason (`action_impossible`). B5: a waiting card is answered only by a line that picks one of
its choices (a bare "yes" at an offer with no card up plays as read: owner 2026-10-27, a
player's slip). Real round-8 lines on fixture m42-r8-typed; FakeLLM picks only, never the
network."""

from pathlib import Path

from aidm.models.campaign_events import OfferResolved
from aidm.models.impossible import ActionImpossible
from aidm.models.protocol_client import SubmitAction
from aidm.models.world_events import PartyMoved, QuestUpdated
from aidm.rules.menu_card import CARD_YES
from aidm.session.menu_pick import NOT_DONE, STOPPED
from tests.session.menu_play import menu_play
from tests.session.table_fixtures import pick

R8 = "m42-r8-typed"


async def test_v1_m43_both_parts_of_a_walk_and_search_play_in_order(tmp_path: Path) -> None:
    """round 8 AA8 (round 7 Z6): r8-typed 373 "We walk back to Saltmere Landing and then I
    search the walls and the planks": the walk, then the search at the place it reached."""
    steps = (("travel", ["saltmere-landing"], None), ("search:investigation", [], None))
    played = await menu_play(tmp_path, R8, 373, pick(*steps))
    assert played.state.world.current_node == "saltmere-landing"
    moved = next(i for i, e in enumerate(played.events) if isinstance(e, PartyMoved))
    assert played.events[-1].type == "narration_recorded" and len(played.events) > moved + 1
    assert not played.of(ActionImpossible)  # nothing dropped


async def test_v1_m43_the_part_after_a_refused_one_is_told_as_a_refusal(tmp_path: Path) -> None:
    """B4: r8-typed 261 (AA3) as a two-part line: the cast is refused (no slot), so the dodge
    after it is not played, and that is logged with the reason, never dropped silently."""
    steps = (("cast:magic-missile", ["bandit-2"], None), ("dodge", [], None))
    played = await menu_play(
        tmp_path, R8, 261, pick(*steps), text="Rook casts magic missile at Bandit B and dodges"
    )
    assert [e.reason for e in played.of(ActionImpossible)] == [
        "Magic Missile: Rook has no 1st-level slot left.",
        STOPPED.format(why=NOT_DONE),
    ]


async def test_v1_m43_a_line_naming_the_answer_still_answers(tmp_path: Path) -> None:
    """r8-typed 119 "We fight the crocodile": the answer named, the fight starts."""
    played = await menu_play(tmp_path, R8, 119, pick(("offer:fight", [], None)))
    assert [e.choice.value for e in played.of(OfferResolved)] == ["fight"]


async def test_v1_m43_a_bare_yes_at_a_two_choice_card_answers_it(tmp_path: Path) -> None:
    """r8-typed 381 "Yes, go ahead, we will take it" at Brenn's quest card (accept or not now)."""
    played = await menu_play(tmp_path, R8, 381, pick(("quest:accept", [], None)))
    assert [q.quest.state.value for q in played.of(QuestUpdated)][:1] == ["active"]
    assert not played.of(ActionImpossible)


async def test_v1_m43_a_line_that_picks_no_choice_leaves_the_card_waiting(tmp_path: Path) -> None:
    """B5 (round 8 Z1 family, r8-typed 601-602): with the parley card up, a line that picks
    something else plays as itself and the card waits; its own yes then answers it."""
    parley = pick(("offer:parley:persuasion", [], None))
    look = pick(("look", [], None))
    yes = pick((CARD_YES, [], None))
    played = await menu_play(
        tmp_path,
        R8,
        601,
        parley,
        look,
        yes,
        then=(SubmitAction(text="I look around"), SubmitAction(text="Yes, go ahead")),
    )
    resolved = played.of(OfferResolved)
    assert len(resolved) == 1 and resolved[0].choice.value == "parley"
