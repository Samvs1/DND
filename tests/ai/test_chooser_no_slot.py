"""M41.2 round 7 Z5 at the chooser: "Tamsin sends a guiding bolt at the armor" with no slot of 1st
level or higher left (r7b-typed 1277) shows Guiding Bolt as NOT OFFERED with the reason, and a
pick of it, by entry id or as a target, is `other` with no repair round (a repair would list
the cantrips, the stand-ins). The storyteller's party sheet tells the slots left. FakeLLM only."""

import json
from pathlib import Path
from typing import Any

from aidm.dm.choice_tool import CHOOSE_TOOL
from aidm.dm.chooser import choose
from aidm.dm.context import build_context, to_messages
from aidm.dm.context_text import ContextPurpose
from aidm.dm.fake_llm import fake_tool_call
from aidm.models.action_menu import MenuChoice
from tests.ai.chooser_fixtures import chooser_client, menu_at, state_at

R7, BOLT_SEQ = "m39-r7-typed", 1277
TAMSIN, ARMOR = "pc-p8", "animated-armor-1"
LINE = "Tamsin sends a guiding bolt at the armor"


def _pick(entry: str, *targets: str) -> Any:
    step = {"do": entry, "to": list(targets), "qty": None}
    return fake_tool_call(CHOOSE_TOOL, {"steps": [step], "other": None, "colour": ""})


async def _choose(tmp_path: Path, answer: Any) -> tuple[MenuChoice, int, str]:
    state, menu = state_at(R7, BOLT_SEQ), menu_at(R7, BOLT_SEQ, TAMSIN)
    client, fake = chooser_client(tmp_path, {CHOOSE_TOOL: [answer]})
    choice = await choose(state, TAMSIN, LINE, menu, client)
    assert isinstance(choice, MenuChoice)
    return choice, len(fake.requests), json.dumps(fake.requests[0].messages)


async def test_v1_m41_a_no_slot_spell_pick_is_other(tmp_path: Path) -> None:
    choice, calls, sent = await _choose(tmp_path, _pick("cast:guiding-bolt", ARMOR))
    assert choice == MenuChoice(other=True)
    assert calls == 1  # no repair round that lists the cantrips
    reason = "guiding-bolt (Tamsin has no slot of 1st level or higher left)"
    assert f"NOT OFFERED (no entry acts on it): {reason}" in sent


async def test_a_cantrip_aimed_at_the_spell_is_other_too(tmp_path: Path) -> None:
    choice, calls, _ = await _choose(tmp_path, _pick("cast:sacred-flame", "guiding-bolt"))
    assert (choice, calls) == (MenuChoice(other=True), 1)


async def test_a_cantrip_named_plays_as_before(tmp_path: Path) -> None:
    choice, _, _ = await _choose(tmp_path, _pick("cast:sacred-flame", ARMOR))
    assert [s.entry for s in choice.steps] == ["cast:sacred-flame"] and not choice.other


def test_the_storytellers_party_sheet_tells_the_slots_left() -> None:
    state = state_at(R7, BOLT_SEQ)
    pack = build_context(state, ContextPurpose.ADJUDICATE, TAMSIN, LINE)
    text = json.dumps(to_messages(pack))
    assert "spell slots left: level 1 0 of 4, level 2 0 of 2" in text
