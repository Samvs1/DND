"""M31.1a V2, V6, V7 (docs/playtests/M31_round4.md): typed spells, drinks and gear lines out of a
fight, each on the real round-4 state where the line was typed."""

from pathlib import Path

from aidm.dm.cast_intent import CastIntent
from aidm.dm.equip_intent import ItemAction, ItemIntent, ItemIntents
from aidm.dm.heal_intent import HealIntent
from aidm.dm.precheck import precheck
from aidm.models.combat_events import SpellCast
from aidm.models.events import AnyEvent, HpChanged, ResourceSet
from aidm.models.protocol_client import SubmitAction
from aidm.models.protocol_server import Notice
from aidm.models.state import GameState
from aidm.models.world_events import EquipmentChanged
from tests.session.playtest_saves import logged, replay_until
from tests.session.table_fixtures import Seat, assert_replays, disabled_llm, join, running

RUN = "m31-r4-typed"


def _typed(seq: int) -> tuple[str, str]:
    event = logged(RUN, seq).event
    assert event.type == "action_declared"
    return event.creature_id, event.text


def _read(seq: int) -> object:
    actor, text = _typed(seq)
    return precheck(replay_until(RUN, seq), actor, text)


async def _turn(
    tmp_path: Path, state: GameState, actor: str, text: str
) -> tuple[list[AnyEvent], GameState, list[str]]:
    async with running(disabled_llm(tmp_path), state) as (table, _):
        seat: Seat = await join(table, "Ann", actor)
        seat.drain()
        start = table.state.event_count
        seat.send(SubmitAction(text=text))
        await table.settle()
        assert_replays(table)
        events = [e.event for e in table.log if e.seq >= start]
        notes = [m.text for m in seat.drain() if isinstance(m, Notice)]
        return events, table.state, notes


def test_m31_hostile_spell_at_scenery_is_a_scene_cast_with_people_near() -> None:
    """V2, typed 79 and 1345: NPCs stood near, so the M30.2b rule sent these to the model."""
    for seq, spell in ((79, "burning-hands"), (84, "burning-hands"), (1345, "thunderwave")):
        assert _read(seq) == CastIntent("pc-p6", spell, (), at_scene=True)


def test_m31_hostile_spell_aimed_at_a_person_here_stays_with_the_storyteller() -> None:
    state = replay_until(RUN, 79)  # Merre Wenslow and the Vossmoor peddler stand here
    for line in ("I cast burning hands at Merre", "I cast burning hands at the peddler"):
        assert precheck(state, "pc-p6", line) is None
    assert precheck(state, "pc-p6", "I cast burning hands at him") is None


async def test_m31_scene_cast_with_people_near_spends_the_slot(tmp_path: Path) -> None:
    actor, text = _typed(79)
    state = replay_until(RUN, 79)
    before = state.creatures[actor].resources["spell-slot-1"].current
    events, after, _ = await _turn(tmp_path, state, actor, text)
    cast = [e for e in events if isinstance(e, SpellCast)]
    assert [(e.spell_id, e.at_scene) for e in cast] == [("burning-hands", True)]
    assert after.creatures[actor].resources["spell-slot-1"].current == before - 1
    assert not any(isinstance(e, HpChanged) and e.creature_id == actor for e in events)


def test_m31_ready_spell_named_without_cast_is_cast() -> None:
    """V2, typed 86: "I murmur a healing word over Rook" was told as failing."""
    assert _read(86) == HealIntent("pc-p8", ("pc-p6",), spell="healing-word")
    state = replay_until(RUN, 86)
    assert precheck(state, "pc-p8", "I ask Merre about healing word") is None


async def test_m31_murmured_healing_word_heals_and_spends(tmp_path: Path) -> None:
    actor, text = _typed(86)
    events, _, _ = await _turn(tmp_path, replay_until(RUN, 86), actor, text)
    cast = [e for e in events if isinstance(e, SpellCast)]
    assert [(e.spell_id, e.target_ids) for e in cast] == [("healing-word", ("pc-p6",))]
    assert any(isinstance(e, ResourceSet) and e.key == "spell-slot-1" for e in events)


def test_m31_drink_targets_the_drinker() -> None:
    """V6, typed 1291: "I drink the herbal poultice Brienne gave me" aimed it at Brienne."""
    found = _read(1291)
    assert isinstance(found, HealIntent) and found.target_ids == ("pc-p6",)
    state = replay_until(RUN, 1291)
    helped = precheck(state, "pc-p6", "I help Brienne drink my potion of healing")
    assert isinstance(helped, HealIntent) and helped.target_ids == ("pc-p2",)


def test_m31_compound_gear_line_is_both_acts() -> None:
    """V7, typed 1333: "I sheathe my longsword and sling my shield on my back"."""
    stow = ItemAction.UNEQUIP
    assert _read(1333) == ItemIntents(
        (ItemIntent("pc-p2", stow, "longsword"), ItemIntent("pc-p2", stow, "shield"))
    )
    state = replay_until(RUN, 1333)
    for line in ("I holster my light crossbow", "Brienne slings her shield over her shoulder"):
        assert isinstance(precheck(state, "pc-p2", line), ItemIntent)


async def test_m31_compound_gear_line_keeps_the_valid_half(tmp_path: Path) -> None:
    actor, text = _typed(1333)
    state = replay_until(RUN, 1333)
    pc = state.creatures[actor].pc
    assert pc is not None
    pc.equipped = pc.equipped.model_copy(update={"main_hand": None})  # already sheathed
    events, after, notes = await _turn(tmp_path, state, actor, text)
    worn = after.creatures[actor].pc
    assert worn is not None and worn.equipped.shield is None
    assert any(isinstance(e, EquipmentChanged) for e in events)
    assert "Brienne's longsword is already put away." in notes
