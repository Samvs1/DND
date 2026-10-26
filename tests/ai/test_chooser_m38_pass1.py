"""The M38.5 live pass 1 regression rows, pinned offline (no model): each row's own label is a
valid pick on its menu as the chooser sends it, takes no repair, gains no NOT OFFERED name and is
never turned into `other`; the stray readings the model made are repaired, never dropped to
`other` by a place or a thing named as colour. FakeLLM is not needed: the validator decides."""

from typing import Any

import pytest

from aidm.dm.choice_tool import ChooseActionsArgs, choice_tool
from aidm.models.action_menu import ActionMenu, MenuChoice
from aidm.rules.menu_unoffered import with_unoffered
from tests.ai.chooser_fixtures import menu_at, state_at

ROWS: tuple[tuple[str, int, str, str, list[dict[str, Any]]], ...] = (
    (
        "r2-p4",
        294,
        "pc-p2",
        "I ask Farran Dell to give the link back, I only meant to show it",
        [{"do": "talk", "to": ["farran-dell"], "qty": None}],
    ),
    (
        "r2-p5",
        201,
        "pc-p2",
        "I move slowly through the copse and look for any sign",
        [{"do": "search:perception", "to": [], "qty": None}],
    ),
    (
        "r2-p7",
        64,
        "pc-p2",
        "Brienne hands the Herbal Poultice to Elowen and tells her",
        [{"do": "hand:herbal-poultice", "to": ["pc-p4"], "qty": None}],
    ),
    (
        "r2-p7",
        68,
        "pc-p2",
        "Brienne gives the spare crowbar to Elowen.",
        [{"do": "hand:crowbar", "to": ["pc-p4"], "qty": None}],
    ),
    (
        "m31-r4-typed",
        651,
        "pc-p6",
        "Rook casts burning hands on the violet fungus",
        [{"do": "cast:burning-hands", "to": ["hummock"], "qty": None}],
    ),
    (
        "m31-r4-typed",
        1345,
        "pc-p6",
        "I cast thunderwave out over the black water",
        [{"do": "cast:thunderwave", "to": [], "qty": None}],
    ),
    (
        "m32-r5-typed",
        42,
        "pc-p6",
        "I cast Burning Hands at the damp ferns by the road",
        [{"do": "cast:burning-hands", "to": [], "qty": None}],
    ),
    (
        "m32-r5-typed",
        588,
        "pc-p6",
        "With coin in our pockets we head back to Bramble Pike's stall",
        [{"do": "travel", "to": ["the-briar-vein"], "qty": None}],
    ),
    (
        "m32-r5-quests",
        631,
        "pc-p2",
        "Brienne asks Calyx Morn for work or a favour",
        [{"do": "talk", "to": ["calyx-morn"], "qty": None}],
    ),
    (
        "m35-r6-typed",
        378,
        "pc-p6",
        "I cast Sleep on the kobolds behind the spur",
        [{"do": "cast:sleep", "to": ["foe:kobold"], "qty": None}],
    ),
    (
        "m35-r6-typed",
        797,
        "pc-p2",
        "I travel to Lamplighters' Rest",
        [{"do": "travel", "to": ["lamplighters-rest"], "qty": None}],
    ),
    (
        "m32-r5-typed",
        419,
        "pc-p2",
        "Drop your weapons and yield!",
        [{"do": "surrender", "to": [], "qty": None}],
    ),
)


def _menu(run: str, seq: int, actor: str, text: str) -> ActionMenu:
    return with_unoffered(state_at(run, seq), menu_at(run, seq, actor), text)


def _choice(menu: ActionMenu, steps: list[dict[str, Any]]) -> MenuChoice:
    args = choice_tool(menu).args_model.model_validate(
        {"steps": steps, "other": None, "colour": ""}
    )
    assert isinstance(args, ChooseActionsArgs)
    return args.to_choice()


@pytest.mark.parametrize(("run", "seq", "actor", "text", "steps"), ROWS)
def test_v1_m38_pass1_row_label_is_a_clean_pick(
    run: str, seq: int, actor: str, text: str, steps: list[dict[str, Any]]
) -> None:
    menu = _menu(run, seq, actor, text)
    assert menu.unoffered == ()
    choice = _choice(menu, steps)
    assert not choice.other and [s.entry for s in choice.steps] == [s["do"] for s in steps]


def test_v1_m38_a_creature_named_for_burning_hands_is_the_area_repair() -> None:
    """m31-r4-typed:651 became a fire bolt: the cone at the fungus is repaired to an area."""
    menu = _menu("m31-r4-typed", 651, "pc-p6", "Rook casts burning hands on the violet fungus")
    with pytest.raises(ValueError, match="cast:burning-hands takes one of"):
        _choice(menu, [{"do": "cast:burning-hands", "to": ["violet-fungus-1"], "qty": None}])


def test_v1_m38_a_target_on_search_is_the_plain_repair() -> None:
    """m29-r2-p5:201: a target given to search is dropped by the repair, never made other."""
    menu = _menu("r2-p5", 201, "pc-p2", "I look for any sign of the harvest-house")
    place = next(t.id for t in menu.targets if t.kind == "place")
    with pytest.raises(ValueError, match="search:perception takes no target"):
        _choice(menu, [{"do": "search:perception", "to": [place], "qty": None}])
