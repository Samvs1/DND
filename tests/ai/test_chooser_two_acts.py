"""M41.3 (docs/playtests/M39_round7.md Z6, Z7): what the chooser sees for a line with two acts and
for a line that gives a search or a pickup to another hero, on the round-7 states; the plan's
cut part; the fight telling after one hero fled. No model call."""

import pytest

from aidm.dm.choice_tool import ChooseActionsArgs, choice_tool, menu_schema
from aidm.dm.chooser_menu import menu_lines
from aidm.dm.fight_ledger import fight_ledger, fight_lines
from aidm.models.action_menu import MenuChoice, MenuStep
from aidm.rules.menu_scene import TRAVEL_LABEL
from aidm.rules.menu_steps import CANNOT_NOW, plan_line, refit, step_actor
from aidm.rules.menu_unoffered import with_unoffered
from tests.ai.chooser_fixtures import REGS, menu_at, state_at
from tests.session.playtest_saves import events_of

TYPED, QUESTS, FULL = "m39-r7-typed", "m39-r7-quests", "m39-r7-full"
SEARCH = "Tamsin searches the Tolltree Bridge carefully for the Brass Watch"


def _step(menu_id: str, by: str | None = None) -> dict[str, object]:
    return {"do": menu_id, "to": [], "qty": None, "by": by}


def test_v1_m41_travel_says_where_the_next_steps_happen() -> None:
    """r7b-typed 541: the menu is built for the place the hero stands in; the travel entry says
    the steps after it happen at the place reached."""
    lines = menu_lines(menu_at(TYPED, 541, "pc-p4"))
    assert any(ln.startswith(f"travel = {TRAVEL_LABEL}") for ln in lines)


def test_v1_m41_the_rest_after_a_travel_is_kept_and_refitted() -> None:
    menu = menu_at(TYPED, 541, "pc-p4")
    travel = MenuStep(entry="travel", targets=("the-rust-chapel",))
    search, talk = MenuStep(entry="search:investigation"), MenuStep(entry="talk")
    choice = MenuChoice(steps=(travel, search))
    plan = plan_line(state_at(TYPED, 541), menu, choice, REGS)
    assert [g[0] for g in plan.groups] == [travel]
    assert plan.rest == MenuChoice(steps=(search,)) and plan.why == "the party travels first"
    talk_oza = talk.model_copy(update={"targets": ("thurible-merchant-oza",)})
    there = menu_at(TYPED, 543, "pc-p4")  # at the Rust Chapel, no Oza there
    kept, why = refit(there, menu, MenuChoice(steps=(search, talk_oza)))
    assert kept == MenuChoice(steps=(search,))
    assert why == CANNOT_NOW.format(what="Talk to someone here")
    assert refit(there, menu, MenuChoice(steps=(search,))) == (MenuChoice(steps=(search,)), "")


def test_v1_m41_a_named_hero_is_a_helper_only_when_named() -> None:
    """r7b-quests 114: the line names Tamsin, so only Tamsin may do the shared steps; a line
    naming no other hero gets no `by` at all (its prompt and schema are as before)."""
    menu = menu_at(QUESTS, 114, "pc-p2")
    assert set(menu.helpers) == {"pc-p4", "pc-p6", "pc-p8"}
    named = with_unoffered(state_at(QUESTS, 114), menu, SEARCH)
    assert named.helpers == ("pc-p8",)
    assert menu_lines(named)[-1].startswith("by = who does a search: step")
    step = menu_schema(named)["properties"]["steps"]["items"]["properties"]
    assert step["by"]["anyOf"][0]["enum"] == ["pc-p8"]
    plain = with_unoffered(state_at(QUESTS, 114), menu, "I search the bridge")
    assert (
        plain.helpers == ()
        and "by" not in menu_schema(plain)["properties"]["steps"]["items"]["properties"]
    )
    assert not any(ln.startswith("by =") for ln in menu_lines(plain))


def test_v1_m41_by_is_checked_against_the_menu() -> None:
    named = with_unoffered(state_at(QUESTS, 114), menu_at(QUESTS, 114, "pc-p2"), SEARCH)
    model = choice_tool(named).args_model

    def read(steps: list[dict[str, object]]) -> MenuChoice:
        args = model.model_validate({"steps": steps})
        assert isinstance(args, ChooseActionsArgs)
        return args.to_choice()

    choice = read([_step("search:investigation", "pc-p8")])
    assert choice.steps[0].by == "pc-p8" and step_actor(named, choice.steps[0]) == "pc-p8"
    with pytest.raises(ValueError, match="by takes one of: pc-p8"):
        model.model_validate({"steps": [_step("search:investigation", "pc-p6")]})
    with pytest.raises(ValueError, match="done by the acting hero only"):
        model.model_validate({"steps": [_step("look", "pc-p8")]})
    own = read([_step("search:investigation", "pc-p2")])
    assert own.steps[0].by is None  # the sender named as by is the sender


def test_v1_m41_the_fight_tells_who_is_still_in_it() -> None:
    """r7b-quests 913-915 "Elowen calls out and the party flees": a flee is one hero's own act on
    their turn; the telling's facts name the heroes still in the fight."""
    state = state_at(QUESTS, 916)
    events = [e.event for e in events_of(QUESTS) if 914 <= e.seq <= 915]
    lines = fight_lines(state, fight_ledger(state, events), events)
    stay = [ln for ln in lines if "still in the fight" in ln]
    assert len(stay) == 1 and "Elowen" not in stay[0]
    assert all(name in stay[0] for name in ("Brienne", "Rook", "Tamsin"))
