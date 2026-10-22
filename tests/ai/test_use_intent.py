"""The deterministic gear precheck (M27.5, `aidm.dm.use_intent` through `aidm.dm.precheck`):
one test per common phrasing; anything unclear goes to the AI."""

from aidm.dm.precheck import ItemIntent, gear_intent, precheck
from aidm.dm.tool_context import ToolContext
from aidm.dm.use_intent import UseIntent
from aidm.models.encounter import Side
from aidm.models.state import GameState
from aidm.models.world_events import FeatureIntroduced
from aidm.rules.light import put_out
from tests.ai.tool_fixtures import add_npc, apply_result, run_tool
from tests.unit.rules.combat_fixtures import monster
from tests.unit.rules.item_fixtures import CAVE, DOCKS, at, gear_fight, hero, run, use

GEAR = [
    "torch",
    "lantern-hooded",
    "candle",
    "rope-hempen-50-feet",
    "thieves-tools",
    "oil-flask",
    "scroll-of-sleep",
    "herbalism-kit",
]


def _state(node: str = DOCKS) -> GameState:
    return at(node, hero(gear=GEAR))


def _intent(state: GameState, text: str) -> UseIntent | None:
    found = precheck(state, "hero", text)
    assert found is None or isinstance(found, UseIntent), found
    return found


def _chest(state: GameState) -> str:
    result = run_tool(
        state,
        "introduce_feature",
        ctx=ToolContext(actor_id="hero"),
        kind="container",
        name="Iron chest",
        lock_tier="easy",
    )
    apply_result(state, result)
    (event,) = result.events
    assert isinstance(event, FeatureIntroduced)
    return event.feature.id


def test_light_my_torch() -> None:
    state = _state(CAVE)
    assert _intent(state, "I light my torch.") == UseIntent("hero", "torch", verb="light")
    assert _intent(state, "ignite the lantern") == UseIntent(
        "hero", "lantern-hooded", verb="ignite"
    )
    assert _intent(state, "light a candle") == UseIntent("hero", "candle", verb="light")
    assert _intent(at(CAVE, hero()), "light my torch") is None  # carries none


def test_put_out_my_torch_douse_extinguish() -> None:
    state = _state(CAVE)
    run(state, use(state, "torch"))
    for text in ("put out my torch", "douse the torch", "put my torch out", "put out my light"):
        assert _intent(state, text) == UseIntent("hero", "torch", put_out=True), text
    run(state, put_out(state, "hero"))
    run(state, use(state, "lantern-hooded"))
    assert _intent(state, "extinguish the lantern") == UseIntent(
        "hero", "lantern-hooded", put_out=True
    )
    assert _intent(state, "snuff out the candle") == UseIntent("hero", "candle", put_out=True)
    assert _intent(state, "douse the bonfire") is None  # names nothing carried


def test_use_x_on_y() -> None:
    state = _state()
    fid = _chest(state)
    assert _intent(state, "use my thieves' tools on the iron chest") == UseIntent(
        "hero", "thieves-tools", target=fid
    )
    assert _intent(state, "use the rope on the cliff") == UseIntent(
        "hero", "rope-hempen-50-feet"
    )  # the cliff is not a known thing: no target
    assert _intent(state, "use the rope") == UseIntent("hero", "rope-hempen-50-feet")
    add_npc(state, "npc-snik", name="Snik the goblin", role="goblin")
    assert _intent(state, "use the rope on the goblin") is None  # the AI judges that one


def test_throw_the_oil_at_z() -> None:
    goblin = monster("goblin")
    fight = gear_fight(CAVE, hero(gear=GEAR), (goblin, Side.HOSTILE, "b"))
    assert gear_intent(fight, "hero", "I throw the oil at the goblin") == UseIntent(
        "hero", "oil-flask", target="b", verb="throw"
    )
    assert _intent(_state(), "throw the oil at the goblin") is None  # no fight: the AI decides


def test_read_the_scroll_of_x() -> None:
    state = _state()
    assert _intent(state, "read the scroll of sleep") == UseIntent(
        "hero", "scroll-of-sleep", verb="read"
    )
    assert _intent(state, "read the scroll") == UseIntent("hero", "scroll-of-sleep", verb="read")
    assert _intent(state, "read the scroll of fireball") is None  # not carried


def test_brew_a_poultice_is_a_long_rest_use() -> None:
    state = _state()
    expected = UseIntent("hero", "herbalism-kit", verb="brew", at_rest=True)
    assert _intent(state, "I brew a poultice") == expected
    assert _intent(state, "brew a poultice with my herbalism kit") == expected


def test_item_commands_still_win() -> None:
    state = _state()
    dropped = precheck(state, "hero", "drop my torch")
    assert isinstance(dropped, ItemIntent)
    assert precheck(state, "hero", "I tie up the goblin with my rope") is None
