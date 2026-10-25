"""M31.1a V1 and V3 (docs/playtests/M31_round4.md): typed casts and weapon phrasings in a fight,
each on the real round-4 state where the line was typed (tests/session/playtest_saves.py)."""

import random
from pathlib import Path

from aidm.dm.intent_router import fight_intent
from aidm.dm.tool_context import ToolContext, tool_registries
from aidm.dm.tool_exec_creative import run_creative_effect
from aidm.dm.tools import CreativeEffectArgs
from aidm.models.combat_events import AttackRolled, FeatureUsed, SpellCast
from aidm.models.commands import AttackCommand, CastCommand, FeatureActionCommand
from aidm.models.damage import DamageType
from aidm.models.dm_tiers import EffectKind
from aidm.models.events import CheckResolved, DiceRolled, ResourceSet
from aidm.models.protocol_client import SubmitAction
from aidm.models.protocol_server import Notice
from aidm.rules.acts import RefusedIntent
from aidm.session import combat_flow
from tests.session.playtest_saves import logged, replay_until
from tests.session.table_fixtures import assert_replays, disabled_llm, join, running

RUN = "m31-r4-typed"


def _typed(seq: int) -> tuple[str, str]:
    event = logged(RUN, seq).event
    assert event.type == "action_declared"
    return event.creature_id, event.text


def _routed(seq: int) -> object:
    actor, text = _typed(seq)
    return fight_intent(replay_until(RUN, seq), actor, text)


def test_m31_typed_casts_in_a_fight_are_the_cast_command() -> None:
    """V1: every round-4 cast line is the hotbar's CastCommand at the foe it names."""
    expected = {
        127: ("pc-p8", "sacred-flame", "zombie-1"),  # no cast word: a ready spell named
        161: ("pc-p6", "fire-bolt", "zombie-1"),
        347: ("pc-p6", "ray-of-frost", "sahuagin-1"),
        357: ("pc-p8", "guiding-bolt", "sahuagin-1"),
        392: ("pc-p6", "magic-missile", "sahuagin-1"),
        618: ("pc-p8", "inflict-wounds", "giant-wolf-spider-1"),
    }
    for seq, (actor, spell, foe) in expected.items():
        assert _routed(seq) == CastCommand(actor_id=actor, spell_id=spell, target_ids=(foe,))


def test_m31_typed_area_cast_aims_at_the_foes_zone() -> None:
    """V1, typed 651: "Rook casts burning hands on the violet fungus" aims at the fungus's zone
    (the rules then say plainly that the 15-ft cone does not reach it)."""
    state = replay_until(RUN, 651)
    found = _routed(651)
    enc = state.encounter
    assert enc is not None
    zone = enc.combatants["violet-fungus-1"].zone_id
    assert found == CastCommand(actor_id="pc-p6", spell_id="burning-hands", target_zone=zone)


def test_m31_typed_turn_undead_is_the_feature() -> None:
    """V1, typed 931: Turn Undead typed is the feature's command (its use, the real save)."""
    found = _routed(931)
    assert found == FeatureActionCommand(
        actor_id="pc-p8", feature_id="channel-divinity-turn-undead"
    )


def test_m31_typed_cast_with_no_target_is_refused_plainly() -> None:
    state = replay_until(RUN, 161)
    found = fight_intent(state, "pc-p6", "I cast fire bolt")
    assert isinstance(found, RefusedIntent) and "Fire Bolt" in found.text
    assert fight_intent(state, "pc-p6", "I ask about fire bolt") is None
    assert fight_intent(state, "pc-p6", "I cast a glance at the zombie") is None


async def _fight_turn(tmp_path: Path, seq: int, text: str, actor: str) -> list[object]:
    async with running(disabled_llm(tmp_path), replay_until(RUN, seq)) as (table, _):
        table.in_combat = True
        seat = await join(table, "Ann", actor)
        table.schedule(lambda: combat_flow.advance(table))
        await table.settle()
        start = table.state.event_count
        seat.send(SubmitAction(text=text))
        await table.settle()
        assert_replays(table)
        return [e.event for e in table.log if e.seq >= start]


async def test_m31_typed_guiding_bolt_spends_the_slot_and_rolls(tmp_path: Path) -> None:
    actor, text = _typed(357)
    events = await _fight_turn(tmp_path, 357, text, actor)
    cast = [e for e in events if isinstance(e, SpellCast)]
    assert [(e.spell_id, e.target_ids) for e in cast] == [("guiding-bolt", ("sahuagin-1",))]
    assert any(isinstance(e, ResourceSet) and e.key == "spell-slot-1" for e in events)
    rolled = [e for e in events if isinstance(e, AttackRolled) and e.attacker_id == actor]
    assert [e.attack for e in rolled] == ["Guiding Bolt"]


async def test_m31_typed_sacred_flame_saves_at_the_real_dc(tmp_path: Path) -> None:
    """V1, typed 127: the model asked DC 15; the engine's DC is 8 + 2 + WIS 2 = 12."""
    actor, text = _typed(127)
    events = await _fight_turn(tmp_path, 127, text, actor)
    saves = [e for e in events if isinstance(e, CheckResolved) and e.creature_id == "zombie-1"]
    assert [e.result.dc for e in saves] == [12]
    assert not any(isinstance(e, DiceRolled) and e.label == "Creative action" for e in events)


async def test_m31_typed_turn_undead_uses_channel_divinity(tmp_path: Path) -> None:
    actor, text = _typed(931)
    events = await _fight_turn(tmp_path, 931, text, actor)
    assert [e.name for e in events if isinstance(e, FeatureUsed)] == ["Turn Undead"]
    assert any(isinstance(e, ResourceSet) and e.key == "channel-divinity" for e in events)


async def test_m31_typed_cast_with_no_target_spends_nothing(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), replay_until(RUN, 161)) as (table, _):
        table.in_combat = True
        seat = await join(table, "Ann", "pc-p6")
        table.schedule(lambda: combat_flow.advance(table))
        await table.settle()
        start = table.state.event_count
        seat.send(SubmitAction(text="I cast fire bolt"))
        await table.settle()
        events = [e.event for e in table.log if e.seq >= start]
        notices = [m for m in seat.drain() if isinstance(m, Notice)]
    assert events == []
    assert any("Name who Fire Bolt is aimed at" in m.text for m in notices)


def test_m31_round4_weapon_phrasings_attack() -> None:
    """V3: the round-4 lines that became checks are the weapon's attack."""
    expected = {
        152: ("pc-p4", "zombie-1", "ranged"),  # loose an arrow at ... with my shortbow
        474: ("pc-p4", "sahuagin-1", "main_hand"),  # jab ... in the ribs with my rapier
        640: ("pc-p2", "giant-wolf-spider-1", "main_hand"),  # cut down the spider
        855: ("pc-p4", "ice-mephit-1", "ranged"),
        1383: ("pc-p2", "spy-1", "main_hand"),  # cut down Penn with my sword
    }
    for seq, (actor, foe, option) in expected.items():
        assert _routed(seq) == AttackCommand(actor_id=actor, target_id=foe, option=option)


def test_m31_creative_damage_with_a_weapon_is_the_attack() -> None:
    """V3, typed 640-644: a creative 2d6 from a sword killed the spider with no attack roll.
    Creative damage leaning on a weapon, or on a line that reads as a weapon attack, is the
    engine's attack with it."""
    state = replay_until(RUN, 640)
    args = CreativeEffectArgs(
        actor="pc-p2",
        target="giant-wolf-spider-1",
        effect_kind=EffectKind.MINOR_DAMAGE,
        damage_type=DamageType.SLASHING,
        item="longsword",
    )
    ctx = ToolContext(actor_id="pc-p2", player_text="I hack at the beast with all I have")
    result = run_creative_effect(state, args, ctx, random.Random(3), tool_registries())
    rolled = [e for e in result.events if isinstance(e, AttackRolled)]
    assert [(e.attack, e.target_id) for e in rolled] == [("Longsword", "giant-wolf-spider-1")]
    assert not any(
        isinstance(e, DiceRolled) and e.label == "Creative action" for e in result.events
    )
    plain = args.model_copy(update={"item": None})
    said = ToolContext(actor_id="pc-p2", player_text="I cut down the spider with my sword")
    again = run_creative_effect(state, plain, said, random.Random(3), tool_registries())
    assert any(isinstance(e, AttackRolled) for e in again.events)
