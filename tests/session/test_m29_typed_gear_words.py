"""M29.7a R9 / R17 (docs/playtests/M29_round2.md): typed equip phrases and light phrases, from
the round-2 saves (p4 rogues, p7 economy). The engine equips, lights and puts out for real, or
says why not in an engine line; a compound sentence does both of its acts."""

from pathlib import Path

from aidm.dm.precheck import precheck
from aidm.models.item_events import LightEnded, LightLit
from aidm.models.protocol_client import SubmitAction
from aidm.models.state import GameState
from aidm.models.world_events import EquipmentChanged, NarrationRecorded
from aidm.rules.acts import UseIntent
from tests.session.playtest_saves import replay_until
from tests.session.table_fixtures import assert_replays, disabled_llm, join, running


async def _typed(tmp_path: Path, state: GameState, hero: str, text: str) -> list[object]:
    async with running(disabled_llm(tmp_path), state) as (table, _):
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
    events = await _typed(tmp_path, replay_until("r2-p4", 1199), "pc-p2", text)
    worn = [e.equipped.armor for e in events if isinstance(e, EquipmentChanged)]
    assert worn == ["studded-leather-armor"]
    text = "Elowen unhooks her mace and wields the new warhammer instead."
    events = await _typed(tmp_path, replay_until("r2-p7", 393), "pc-p4", text)
    held = [e.equipped.main_hand for e in events if isinstance(e, EquipmentChanged)]
    assert held == ["warhammer"]


def test_m29_light_compound_sentences_light_first() -> None:
    state = replay_until("r2-p4", 210)
    text = "I light a candle to see, then look around the dark wharf for the counterfeit bell"
    intent = precheck(state, "pc-p2", text)
    assert isinstance(intent, UseIntent) and intent.item == "candle" and intent.verb == "light"
    assert intent.rest == "look around the dark wharf for the counterfeit bell"
    intent = precheck(replay_until("r2-p4", 243), "pc-p2", "Brienne pinches out the candle")
    assert isinstance(intent, UseIntent) and intent.put_out and intent.rest is None


async def test_m29_light_a_candle_then_look_lights_it(tmp_path: Path) -> None:
    """p4 210-212: the candle was never lit and the prose said it "stays dark"."""
    state = replay_until("r2-p4", 210)
    state.world.lights = []  # no lantern burning: the candle can be lit
    text = "I light a candle to see, then look around the dark wharf for the counterfeit bell"
    events = await _typed(tmp_path, state, "pc-p2", text)
    assert [e.item for e in events if isinstance(e, LightLit)] == ["candle"]


async def test_m29_lighting_a_lit_torch_says_already_lit(tmp_path: Path) -> None:
    """p4 213-214: Rook's torch burned since 105, yet "the flame will not come"."""
    state = replay_until("r2-p4", 213)
    for text in ("I light my torch", "I light my torch and hold it high to see the wharf"):
        events = await _typed(tmp_path, state, "pc-p6", text)
        assert not any(isinstance(e, LightLit) for e in events)
        assert "it is already lit" in _told(events)


async def test_m29_pinch_out_the_candle_puts_it_out(tmp_path: Path) -> None:
    """p4 243-245: "I pinch out the candle flame and we crouch low" made no light event, and the
    surprise then failed on the light."""
    text = "I pinch out the candle flame and we crouch low in the shadows"
    events = await _typed(tmp_path, replay_until("r2-p4", 243), "pc-p2", text)
    assert [e.item for e in events if isinstance(e, LightEnded)] == ["candle"]
    for text in ("snuff the candle", "blow out my candle", "douse the light so we can creep"):
        intent = precheck(replay_until("r2-p4", 243), "pc-p2", text)
        assert isinstance(intent, UseIntent) and intent.put_out
