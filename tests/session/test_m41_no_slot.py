"""M41.2 round 7 Z5 at the table: "Tamsin sends a guiding bolt at the armor" with no slot of 1st
level or higher left (r7b-typed 1277) casts nothing, never Sacred Flame in its place. M43.2 B2
(round 8 AA3, the same line told as a kill): the model's pick of the not-offered spell is refused
with the reason, logged as an `action_impossible`; no creative ruling (it was `other` before).
Fixture m39-r7-typed; FakeLLM only."""

from pathlib import Path

from aidm.models.combat_events import SpellCast
from aidm.models.impossible import ActionImpossible
from aidm.models.world_events import ActionDeclared
from tests.session.menu_play import menu_play
from tests.session.table_fixtures import pick

R7, BOLT_SEQ = "m39-r7-typed", 1277
ARMOR = "animated-armor-1"


async def test_v1_m41_a_spell_with_no_slot_is_refused_with_the_reason(tmp_path: Path) -> None:
    aimed = pick(("cast:guiding-bolt", [ARMOR], None))
    played = await menu_play(tmp_path, R7, BOLT_SEQ, aimed)
    assert not played.of(SpellCast)
    slots = played.state.creatures["pc-p8"].resources
    assert slots["spell-slot-1"].current == slots["spell-slot-2"].current == 0
    why = "Guiding Bolt: Tamsin has no slot of 1st level or higher left."
    assert [e.reason for e in played.of(ActionImpossible)] == [why]
    told = [r for r in played.fake.requests if r.tools and r.tool_choice != "choose_actions"]
    assert played.choose_calls() == 1 and not told  # no creative ruling on a named spell
    assert [d.text for d in played.of(ActionDeclared)] == [
        "Tamsin sends a guiding bolt at the armor"
    ]
