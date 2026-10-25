"""M29.7a R9 / R17 (docs/playtests/M29_round2.md): typed equip phrases and light phrases, from
the round-2 saves (p4 rogues, p7 economy). The engine equips, lights and puts out for real, or
says why not in an engine line; a compound sentence does both of its acts."""

from pathlib import Path

from aidm.dm.fake_llm import FakeStep
from aidm.models.item_events import LightEnded, LightLit
from aidm.models.protocol_client import SubmitAction
from aidm.models.state import GameState
from aidm.models.world_events import EquipmentChanged, NarrationRecorded
from tests.session.playtest_saves import replay_until
from tests.session.table_fixtures import assert_replays, join, menu_llm, pick, running


async def _typed(
    tmp_path: Path, state: GameState, hero: str, text: str, choice: FakeStep
) -> list[object]:
    """`choice`: the menu chooser's reading (M36.10a); the AI is otherwise down."""
    llm = menu_llm(tmp_path, choice, storyteller_down=True)[0]
    async with running(llm, state) as (table, _):
        seat = await join(table, "Ann", hero)
        start = table.state.event_count
        seat.send(SubmitAction(text=text))
        await table.settle()
        assert_replays(table)
        return [e.event for e in table.log if e.seq >= start]


def _told(events: list[object]) -> str:
    return " ".join(e.text for e in events if isinstance(e, NarrationRecorded))


async def test_m29_typed_put_on_and_wield_equip(tmp_path: Path) -> None:
    """p4 1199 and p7 393: "put on the studded leather armor in place of my leather armor" and
    "Elowen unhooks her mace and wields the new warhammer instead" equipped nothing."""
    text = "I put on the studded leather armor in place of my leather armor"
    wear = pick(("equip:studded-leather-armor", [], None))
    events = await _typed(tmp_path, replay_until("r2-p4", 1199), "pc-p2", text, wear)
    worn = [e.equipped.armor for e in events if isinstance(e, EquipmentChanged)]
    assert worn == ["studded-leather-armor"]
    text = "Elowen unhooks her mace and wields the new warhammer instead."
    wield = pick(("equip:warhammer", [], None))
    events = await _typed(tmp_path, replay_until("r2-p7", 393), "pc-p4", text, wield)
    held = [e.equipped.main_hand for e in events if isinstance(e, EquipmentChanged)]
    assert held == ["warhammer"]


async def test_m29_light_a_candle_then_look_lights_it(tmp_path: Path) -> None:
    """p4 210-212: the candle was never lit and the prose said it "stays dark"."""
    state = replay_until("r2-p4", 210)
    state.world.lights = []  # no lantern burning: the candle can be lit
    text = "I light a candle to see, then look around the dark wharf for the counterfeit bell"
    light_then_look = pick(("use:candle-light", [], None), ("look", [], None))
    events = await _typed(tmp_path, state, "pc-p2", text, light_then_look)
    assert [e.item for e in events if isinstance(e, LightLit)] == ["candle"]


async def test_m29_lighting_a_lit_torch_says_already_lit(tmp_path: Path) -> None:
    """p4 213-214: Rook's torch burned since 105, yet "the flame will not come"."""
    state = replay_until("r2-p4", 213)
    for text in ("I light my torch", "I light my torch and hold it high to see the wharf"):
        events = await _typed(tmp_path, state, "pc-p6", text, pick(("use:torch-light", [], None)))
        assert not any(isinstance(e, LightLit) for e in events)
        assert "it is already lit" in _told(events)


async def test_m29_pinch_out_the_candle_puts_it_out(tmp_path: Path) -> None:
    """p4 243-245: "I pinch out the candle flame and we crouch low" made no light event, and the
    surprise then failed on the light."""
    text = "I pinch out the candle flame and we crouch low in the shadows"
    put_out = pick(("put_out", [], None), colour="we crouch low in the shadows")
    events = await _typed(tmp_path, replay_until("r2-p4", 243), "pc-p2", text, put_out)
    assert [e.item for e in events if isinstance(e, LightEnded)] == ["candle"]
