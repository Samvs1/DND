"""M38.4 cause A at the chooser, as fixed after M38.5 live pass 1: a pick at a NOT OFFERED target
resolves to `other` with no repair round; a pick at a named being its entry cannot take (a
standing hero for help_up, a hero for give, a waiting monster for talk, the hero's own area for
move) gets a repair line that names the entries that do take it and says the part is `other`,
never another target; such a step is never executed. FakeLLM only, no network."""

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

LOCKET = ("m31-r4-full", 638)
CROWBAR = ("r2-p7", 68)
POULTICE = ("r2-p7", 64)
DOWNED = ("m32-r5-typed", 281)
TOLL = ("m32-r5-typed", 61)
LOCKET_LINE = "Elowen holds up the Sister's Locket and calls softly to Brother Mallow"
NO_SWAP = "is other, never another target"


def _pick(steps: list[dict[str, Any]], other: dict[str, Any] | None = None) -> Any:
    return fake_tool_call(CHOOSE_TOOL, {"steps": steps, "other": other, "colour": ""})


def _step(entry: str, *targets: str) -> dict[str, Any]:
    return {"do": entry, "to": list(targets), "qty": None}


def _feedback(fake: Any) -> str:
    return str(fake.requests[1].messages[-1]["content"])


async def test_v1_m38_a_not_offered_pick_resolves_to_other(tmp_path: Path) -> None:
    state, menu = state_at(*LOCKET), menu_at(*LOCKET, "pc-p4")
    off = _pick([_step("talk", "sister-s-locket")])
    client, fake = chooser_client(tmp_path, {CHOOSE_TOOL: [off]})
    choice = await choose(state, "pc-p4", LOCKET_LINE, menu, client)
    assert choice == MenuChoice(other=True)
    assert len(fake.requests) == 1  # no repair round: nothing could be swapped in
    sent = json.dumps(fake.requests[0].messages)
    assert "NOT OFFERED (no entry acts on it): sister-s-locket (Rook carries it)" in sent


async def test_v1_m38_help_up_at_a_standing_hero_is_repaired_towards_other(
    tmp_path: Path,
) -> None:
    """ "I help Rook up" (Rook stands): the repair line no longer lists Elowen as the stand-in."""
    state, menu = state_at(*DOWNED), menu_at(*DOWNED, "pc-p2")
    bad = _pick([_step("help_up", "pc-p6")])
    good = _pick([], {"text": "help Rook up", "first": False})
    client, fake = chooser_client(tmp_path, {CHOOSE_TOOL: [bad, good]})
    choice = await choose(state, "pc-p2", "I help Rook up", menu, client)
    assert choice == MenuChoice(other=True, other_text="help Rook up")
    feedback = _feedback(fake)
    assert "help_up cannot take pc-p6" in feedback and NO_SWAP in feedback
    assert "takes one of" not in feedback


async def test_v1_m38_give_to_a_hero_is_repaired_to_the_hand_over(tmp_path: Path) -> None:
    """M38.5 pass 1 regression m29-r2-p7:68 "Brienne gives the spare crowbar to Elowen": the
    give at a hero went to other; the repair now points at hand:crowbar."""
    state, menu = state_at(*CROWBAR), menu_at(*CROWBAR, "pc-p2")
    bad = _pick([_step("give:crowbar", "pc-p4")])
    good = _pick([_step("hand:crowbar", "pc-p4")])
    client, fake = chooser_client(tmp_path, {CHOOSE_TOOL: [bad, good]})
    choice = await choose(
        state, "pc-p2", "Brienne gives the spare crowbar to Elowen.", menu, client
    )
    assert choice == MenuChoice(steps=(MenuStep(entry="hand:crowbar", targets=("pc-p4",)),))
    assert "pc-p4 is taken by hand:crowbar" in _feedback(fake)


async def test_v1_m38_words_to_a_hero_after_a_hand_over_are_not_other(tmp_path: Path) -> None:
    """M38.5 pass 1 regression m29-r2-p7:64 "hands the Herbal Poultice to Elowen and tells her
    to keep it": the talk at a hero was dropped to other; it is repaired, the hand-over kept."""
    state, menu = state_at(*POULTICE), menu_at(*POULTICE, "pc-p2")
    hand = _step("hand:herbal-poultice", "pc-p4")
    bad = _pick([hand, _step("talk", "pc-p4")])
    good = _pick([hand])
    client, fake = chooser_client(tmp_path, {CHOOSE_TOOL: [bad, good]})
    line = "Brienne hands the Herbal Poultice to Elowen and tells her to keep it for emergencies."
    choice = await choose(state, "pc-p2", line, menu, client)
    assert choice == MenuChoice(steps=(MenuStep(entry="hand:herbal-poultice", targets=("pc-p4",)),))
    assert "talk cannot take pc-p4" in _feedback(fake)


async def test_v1_m38_talk_to_the_waiting_thug_never_becomes_the_tollman(tmp_path: Path) -> None:
    state, menu = state_at(*TOLL), menu_at(*TOLL, "pc-p2")
    bad = _pick([_step("talk", "foe:thug")])
    good = _pick([], {"text": "bow low to the thug", "first": False})
    client, fake = chooser_client(tmp_path, {CHOOSE_TOOL: [bad, good]})
    choice = await choose(state, "pc-p2", "I bow low to the thug", menu, client)
    assert choice == MenuChoice(other=True, other_text="bow low to the thug")
    assert "talk cannot take foe:thug" in _feedback(fake)
    assert "reeve-hallick" not in _feedback(fake)


def test_v1_m38_an_off_target_is_never_executed() -> None:
    """The NOT OFFERED pick passes the validator and `to_choice` drops it; a raw step at an off
    target that reached `to_acts` plays only the storyteller's part."""
    state = state_at(*LOCKET)
    menu = with_unoffered(state, menu_at(*LOCKET, "pc-p4"), LOCKET_LINE)
    args = choice_tool(menu).args_model.model_validate(
        {"steps": [_step("talk", "sister-s-locket")], "other": None, "colour": ""}
    )
    assert isinstance(args, ChooseActionsArgs)
    choice = args.to_choice()
    assert not choice.steps and choice.other
    assert to_acts(state, menu, choice, REGS, LOCKET_LINE) == [OtherIntent("pc-p4", LOCKET_LINE)]
    downed = menu_at(*DOWNED, "pc-p2")
    raw = MenuChoice(steps=(MenuStep(entry="help_up", targets=("pc-p6",)),))
    acts = to_acts(state_at(*DOWNED), downed, raw, REGS, "I help Rook up")
    assert acts == [OtherIntent("pc-p2", "I help Rook up")]


def test_the_schema_lists_the_not_offered_targets_and_rule_one_names_them() -> None:
    state = state_at(*LOCKET)
    menu = with_unoffered(state, menu_at(*LOCKET, "pc-p4"), LOCKET_LINE)
    params = tool_param(choice_tool(menu))["function"]["parameters"]
    enum = params["properties"]["steps"]["items"]["properties"]["to"]["items"]["enum"]
    assert "sister-s-locket" in enum
    pack = build_context(state, ContextPurpose.CHOOSE, "pc-p4", LOCKET_LINE, menu=menu)
    system, user = (m["content"] for m in to_messages(pack))
    assert "NOT OFFERED" in user
    assert "A named person, hero or item no entry takes, or NOT OFFERED, is other." in system
    assert "even if the entry does not list it" not in system  # M38.5 fix: no target stuffing


async def test_an_area_aim_at_a_creature_is_still_repaired(tmp_path: Path) -> None:
    """A move (an area entry) named at a foe is repaired to the area, never sent to other."""
    state, menu = state_at(TYPED, FIGHT_SEQ), menu_at(TYPED, FIGHT_SEQ, "pc-p2")
    move = next(e for e in menu.entries if e.id == "move")
    foe = next(t.id for t in menu.targets if t.kind == "foe")
    bad = _pick([_step("move", foe)])
    good = _pick([_step("move", move.target_ids[0])])
    client, fake = chooser_client(tmp_path, {CHOOSE_TOOL: [bad, good]})
    choice = await choose(state, "pc-p2", "I run over to the kobold", menu, client)
    assert choice == MenuChoice(steps=(MenuStep(entry="move", targets=(move.target_ids[0],)),))
    assert "move takes one of" in _feedback(fake)


async def test_v1_m38_a_move_to_the_heros_own_area_ends_in_other(tmp_path: Path) -> None:
    """syn:goblin_fight:8 "I move to the Gorse Patch" (where the hero stands) insisted on that
    area through every repair and failed; the repair says other, and an answer that never fits
    goes to the storyteller instead of a failure notice."""
    state, menu = state_at(TYPED, FIGHT_SEQ), menu_at(TYPED, FIGHT_SEQ, "pc-p2")
    enc = state.encounter
    assert enc is not None
    here = enc.combatant("pc-p2").zone_id
    insist = [_pick([_step("move", here)]) for _ in range(3)]
    client, fake = chooser_client(tmp_path, {CHOOSE_TOOL: insist})
    choice = await choose(state, "pc-p2", "I move to where I stand", menu, client)
    assert choice == MenuChoice(other=True)
    assert f"move cannot take {here}" in _feedback(fake)


async def test_v1_m38_a_step_written_as_other_is_the_other_part(tmp_path: Path) -> None:
    """syn:ferry_casters:6 "I give Old Renn 25 silver pieces": the model wrote {"do": "other"}."""
    state, menu = state_at(*TOLL), menu_at(*TOLL, "pc-p2")
    pick = _pick([_step("other"), _step("talk", "reeve-hallick")])
    client, fake = chooser_client(tmp_path, {CHOOSE_TOOL: [pick]})
    choice = await choose(state, "pc-p2", "I give Reeve Hallick 25 silver pieces", menu, client)
    assert choice == MenuChoice(
        steps=(MenuStep(entry="talk", targets=("reeve-hallick",)),), other=True, other_first=True
    )
    assert len(fake.requests) == 1
