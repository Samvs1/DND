"""M38.4 cause A at the chooser: a pick naming a target its entry cannot act on (a not-offered
target, a standing hero for help_up, a waiting monster for talk) resolves to `other` with no
repair round (the repair was how the swapped target got in), and is never executed. FakeLLM
only, no network."""

import json
from pathlib import Path
from typing import Any

from aidm.dm.choice_tool import CHOOSE_TOOL, ChooseActionsArgs, choice_tool
from aidm.dm.chooser import choose
from aidm.dm.context import build_context, to_messages
from aidm.dm.context_text import ContextPurpose
from aidm.dm.fake_llm import fake_tool_call
from aidm.dm.llm_types import tool_param
from aidm.models.action_menu import MenuChoice, MenuStep
from aidm.rules.acts import OtherIntent
from aidm.rules.menu_steps import to_acts
from aidm.rules.menu_unoffered import with_unoffered
from tests.ai.chooser_fixtures import (
    FIGHT_SEQ,
    REGS,
    TYPED,
    chooser_client,
    menu_at,
    state_at,
)

CHIME = ("r2-p7", 868)
DOWNED = ("m32-r5-typed", 281)
TOLL = ("m32-r5-typed", 61)
VALE_LINE = "Brienne picks up the unfinished chime and carries it back toward Brother Vale."


def _pick(steps: list[dict[str, Any]], other: dict[str, Any] | None = None) -> Any:
    return fake_tool_call(CHOOSE_TOOL, {"steps": steps, "other": other, "colour": ""})


async def test_v1_m38_a_not_offered_pick_resolves_to_other(tmp_path: Path) -> None:
    state, menu = state_at(*CHIME), menu_at(*CHIME, "pc-p2")
    off = _pick([{"do": "hand:unfinished-chime", "to": ["brother-vale"], "qty": None}])
    client, fake = chooser_client(tmp_path, {CHOOSE_TOOL: [off]})
    choice = await choose(state, "pc-p2", VALE_LINE, menu, client)
    assert choice == MenuChoice(other=True)
    assert len(fake.requests) == 1  # no repair round: nothing was swapped in
    sent = json.dumps(fake.requests[0].messages)
    assert "NOT OFFERED (no entry acts on it): brother-vale (not here)" in sent


async def test_v1_m38_help_up_at_a_standing_hero_is_other(tmp_path: Path) -> None:
    """ "I help Rook up and look around": the help is the storyteller's, first; the look plays."""
    state, menu = state_at(*DOWNED), menu_at(*DOWNED, "pc-p2")
    steps = [{"do": "help_up", "to": ["pc-p6"], "qty": None}, {"do": "look", "to": [], "qty": None}]
    client, fake = chooser_client(tmp_path, {CHOOSE_TOOL: [_pick(steps)]})
    choice = await choose(state, "pc-p2", "I help Rook up and look around", menu, client)
    assert choice == MenuChoice(steps=(MenuStep(entry="look"),), other=True, other_first=True)
    assert len(fake.requests) == 1


async def test_v1_m38_talk_to_the_waiting_thug_is_other_not_the_tollman(tmp_path: Path) -> None:
    """ "Rook bows low to the thug" was talk to Reeve Hallick after the repair line."""
    state, menu = state_at(*TOLL), menu_at(*TOLL, "pc-p2")
    talk = _pick(
        [{"do": "talk", "to": ["foe:thug"], "qty": None}], {"text": "bows low", "first": False}
    )
    client, fake = chooser_client(tmp_path, {CHOOSE_TOOL: [talk]})
    choice = await choose(state, "pc-p2", "I bow low to the thug", menu, client)
    assert choice == MenuChoice(other=True, other_text="bows low")
    assert len(fake.requests) == 1


def test_v1_m38_a_not_offered_target_is_never_executed() -> None:
    """The validator lets the pick through, `to_choice` drops the step and `to_acts` plays only
    the storyteller's part: no act ever names Brother Vale or Rook."""
    state = state_at(*CHIME)
    menu = with_unoffered(state, menu_at(*CHIME, "pc-p2"), VALE_LINE)
    args = choice_tool(menu).args_model.model_validate(
        {
            "steps": [{"do": "hand:unfinished-chime", "to": ["brother-vale"], "qty": None}],
            "other": None,
            "colour": "",
        }
    )
    assert isinstance(args, ChooseActionsArgs)
    choice = args.to_choice()
    assert not choice.steps and choice.other
    acts = to_acts(state, menu, choice, REGS, VALE_LINE)
    assert acts == [OtherIntent("pc-p2", VALE_LINE)]
    raw = MenuChoice(steps=(MenuStep(entry="hand:unfinished-chime", targets=("brother-vale",)),))
    assert to_acts(state, menu, raw, REGS, VALE_LINE) == [OtherIntent("pc-p2", VALE_LINE)]


def test_the_schema_lists_the_not_offered_targets() -> None:
    state = state_at(*CHIME)
    menu = with_unoffered(state, menu_at(*CHIME, "pc-p2"), VALE_LINE)
    params = tool_param(choice_tool(menu))["function"]["parameters"]
    enum = params["properties"]["steps"]["items"]["properties"]["to"]["items"]["enum"]
    assert "brother-vale" in enum
    pack = build_context(state, ContextPurpose.CHOOSE, "pc-p2", VALE_LINE, menu=menu)
    assert "NOT OFFERED" in to_messages(pack)[1]["content"]
    assert "NOT OFFERED" in to_messages(pack)[0]["content"]  # rule 1 says what it means


async def test_an_area_aim_at_a_creature_is_still_repaired(tmp_path: Path) -> None:
    """A move (an area entry) named at a foe is repaired to the area, never sent to other."""
    state, menu = state_at(TYPED, FIGHT_SEQ), menu_at(TYPED, FIGHT_SEQ, "pc-p2")
    move = next(e for e in menu.entries if e.id == "move")
    foe = next(t.id for t in menu.targets if t.kind == "foe")
    bad = _pick([{"do": "move", "to": [foe], "qty": None}])
    good = _pick([{"do": "move", "to": [move.target_ids[0]], "qty": None}])
    client, fake = chooser_client(tmp_path, {CHOOSE_TOOL: [bad, good]})
    choice = await choose(state, "pc-p2", "I run over to the kobold", menu, client)
    assert choice == MenuChoice(steps=(MenuStep(entry="move", targets=(move.target_ids[0],)),))
    assert len(fake.requests) == 2
    assert "move takes one of" in str(fake.requests[1].messages[-1]["content"])
