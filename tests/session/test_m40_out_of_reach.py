"""M40.2 round 7 Z2 at the table: "We follow Sersha's trail to the Gear Nave" (r7b-typed 649, the
Gear Nave locked) goes to the storyteller and the party stays put, even when the model aims the
travel at the Gear Nave (a not-offered target: the step is `other`). Fixture m40-r7-typed;
FakeLLM only."""

from pathlib import Path

from aidm.models.world_events import ActionDeclared, PartyMoved
from tests.session.menu_play import menu_play
from tests.session.table_fixtures import pick

R7, TRAIL = "m40-r7-typed", 649


async def test_v1_m40_travel_to_a_known_locked_place_is_the_storytellers(tmp_path: Path) -> None:
    aimed = pick(("travel", ["the-gear-nave"], None))
    played = await menu_play(tmp_path, R7, TRAIL, aimed)
    assert not played.of(PartyMoved)
    assert played.state.world.current_node == "the-tide-stair"
    told = [r for r in played.fake.requests if r.tools and r.tool_choice != "choose_actions"]
    assert played.choose_calls() == 1 and told  # the storyteller ruled on the line
    assert [d.text for d in played.of(ActionDeclared)] == [
        "We follow Sersha's trail to the Gear Nave"
    ]
