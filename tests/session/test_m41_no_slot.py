"""M41.2 round 7 Z5 at the table: "Tamsin sends a guiding bolt at the armor" with no slot of 1st
level or higher left (r7b-typed 1277) casts nothing, never Sacred Flame in its place: the model's
pick of the not-offered spell is `other`, and the storyteller rules on the line with the slots
left on Tamsin's sheet. Fixture m39-r7-typed; FakeLLM only."""

import json
from pathlib import Path

from aidm.models.combat_events import SpellCast
from aidm.models.world_events import ActionDeclared
from tests.session.menu_play import menu_play
from tests.session.table_fixtures import pick

R7, BOLT_SEQ = "m39-r7-typed", 1277
ARMOR = "animated-armor-1"


async def test_v1_m41_a_spell_with_no_slot_is_the_storytellers(tmp_path: Path) -> None:
    aimed = pick(("cast:guiding-bolt", [ARMOR], None))
    played = await menu_play(tmp_path, R7, BOLT_SEQ, aimed)
    assert not played.of(SpellCast)
    slots = played.state.creatures["pc-p8"].resources
    assert slots["spell-slot-1"].current == slots["spell-slot-2"].current == 0
    told = [r for r in played.fake.requests if r.tools and r.tool_choice != "choose_actions"]
    assert played.choose_calls() == 1 and told  # the storyteller ruled on the line
    assert "spell slots left: level 1 0 of 4" in json.dumps(told[0].messages)
    assert [d.text for d in played.of(ActionDeclared)] == [
        "Tamsin sends a guiding bolt at the armor"
    ]
