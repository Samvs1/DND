"""M31.1a V1 and V3 (docs/playtests/M31_round4.md): typed casts and weapon phrasings in a fight,
each on the real round-4 state where the line was typed (tests/session/playtest_saves.py)."""

import random
from pathlib import Path

from aidm.dm.fake_llm import FakeStep
from aidm.dm.tool_context import ToolContext, tool_registries
from aidm.dm.tool_exec_creative import run_creative_effect
from aidm.dm.tools import CreativeEffectArgs
from aidm.models.combat_events import AttackRolled, FeatureUsed, SpellCast
from aidm.models.damage import DamageType
from aidm.models.dm_tiers import EffectKind
from aidm.models.events import CheckResolved, DiceRolled, ResourceSet
from aidm.models.protocol_client import SubmitAction
from aidm.models.protocol_server import ErrorMsg
from aidm.session import combat_flow
from tests.session.playtest_saves import logged, replay_until
from tests.session.table_fixtures import assert_replays, join, menu_down, pick, running

RUN = "m31-r4-typed"


def _typed(seq: int) -> tuple[str, str]:
    event = logged(RUN, seq).event
    assert event.type == "action_declared"
    return event.creature_id, event.text


async def _fight_turn(
    tmp_path: Path, seq: int, text: str, actor: str, chosen: FakeStep
) -> list[object]:
    """`chosen`: the menu chooser's scripted reading of `text` (M36.10b)."""
    async with running(menu_down(tmp_path, chosen), replay_until(RUN, seq)) as (table, _):
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
    bolt = pick(("cast:guiding-bolt", ["sahuagin-1"], None))
    events = await _fight_turn(tmp_path, 357, text, actor, bolt)
    cast = [e for e in events if isinstance(e, SpellCast)]
    assert [(e.spell_id, e.target_ids) for e in cast] == [("guiding-bolt", ("sahuagin-1",))]
    assert any(isinstance(e, ResourceSet) and e.key == "spell-slot-1" for e in events)
    rolled = [e for e in events if isinstance(e, AttackRolled) and e.attacker_id == actor]
    assert [e.attack for e in rolled] == ["Guiding Bolt"]


async def test_m31_typed_sacred_flame_saves_at_the_real_dc(tmp_path: Path) -> None:
    """V1, typed 127: the model asked DC 15; the engine's DC is 8 + 2 + WIS 2 = 12."""
    actor, text = _typed(127)
    flame = pick(("cast:sacred-flame", ["zombie-1"], None))
    events = await _fight_turn(tmp_path, 127, text, actor, flame)
    saves = [e for e in events if isinstance(e, CheckResolved) and e.creature_id == "zombie-1"]
    assert [e.result.dc for e in saves] == [12]
    assert not any(isinstance(e, DiceRolled) and e.label == "Creative action" for e in events)


async def test_m31_typed_turn_undead_uses_channel_divinity(tmp_path: Path) -> None:
    actor, text = _typed(931)
    turn = pick(("feature:turn-undead", [], None))
    events = await _fight_turn(tmp_path, 931, text, actor, turn)
    assert [e.name for e in events if isinstance(e, FeatureUsed)] == ["Turn Undead"]
    assert any(isinstance(e, ResourceSet) and e.key == "channel-divinity" for e in events)


async def test_m31_typed_cast_with_no_target_spends_nothing(tmp_path: Path) -> None:
    aimless = pick(("cast:fire-bolt", [], None))  # the chooser names no target (M36.10b)
    async with running(menu_down(tmp_path, aimless), replay_until(RUN, 161)) as (table, _):
        table.in_combat = True
        seat = await join(table, "Ann", "pc-p6")
        table.schedule(lambda: combat_flow.advance(table))
        await table.settle()
        start = table.state.event_count
        seat.send(SubmitAction(text="I cast fire bolt"))
        await table.settle()
        events = [e.event for e in table.log if e.seq >= start]
        refused = [m.refusal for m in seat.drain() if isinstance(m, ErrorMsg)]
    assert [e.type for e in events] == ["line_read", "action_declared"]  # no spend
    assert refused == ["bad_targets"]  # the rules' own plain "Choose a target." (M36.10b)


def test_m31_creative_damage_with_a_weapon_is_the_attack() -> None:
    """V3, typed 640-644: a creative 2d6 from a sword killed the spider with no attack roll.
    Creative damage leaning on a weapon (the tool's `item`) is the engine's attack with it."""
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
