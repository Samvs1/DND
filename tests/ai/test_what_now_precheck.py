"""M23.8 in the dm layer: the typed What now? pre-check (the help-up pre-check still wins), a typed
move to a locked exit is a `BarredIntent` with the world reason, `move_party` refuses with that
reason, and the context's exit list says why a way is locked."""

from aidm.dm.context_sections import manifest_lines
from aidm.models.state import GameState
from aidm.rules.scene import current_scene
from tests.ai.tool_fixtures import run_tool
from tests.session.quest_offer_fixtures import fresh

SHUT = "The Sunken Vestry stays shut while Gullmere Quay still hides places you have not seen"


def _at_the_boathouse() -> GameState:
    _, state, _ = fresh()
    state.world.current_node = "rotting-boathouse"
    state.world.visited.append("rotting-boathouse")
    return state


def test_move_party_refusal_carries_the_world_reason() -> None:
    state = _at_the_boathouse()
    result = run_tool(state, "move_party", node_id="sunken-vestry")
    assert not result.ok and result.error is not None
    assert SHUT in result.error


def test_context_exit_label_says_why_it_is_locked() -> None:
    state = _at_the_boathouse()
    exits = next(
        line
        for line in manifest_lines(state, current_scene(state), show_ids=False)
        if line.startswith("Exits:")
    )
    assert "The Sunken Vestry (locked until every place of Gullmere Quay is seen, 2 left)" in exits
