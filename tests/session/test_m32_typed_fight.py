"""M32.1a X1, X2 and X6 (docs/playtests/M31_round5.md): typed weapon lines, a spell said as a
strike, and compound lines in a fight, on the real round-5 states (tests/session/playtest_saves.py,
fixture m32-r5-typed)."""

import random
from pathlib import Path

from aidm.dm.intent_router import fight_intent
from aidm.dm.tool_context import ToolContext, tool_registries
from aidm.dm.tool_exec_creative import run_creative_effect
from aidm.dm.tools import CreativeEffectArgs
from aidm.models.combat_events import AttackRolled, CombatantMoved, SpellCast
from aidm.models.commands import AttackCommand, CastCommand
from aidm.models.damage import DamageType
from aidm.models.dm_tiers import EffectKind
from aidm.models.events import AnyEvent, CheckResolved, DiceRolled
from aidm.models.protocol_client import SubmitAction
from aidm.session import combat_flow
from tests.session.playtest_saves import logged, replay_until
from tests.session.table_fixtures import assert_replays, disabled_llm, join, running

RUN = "m32-r5-typed"


def _typed(seq: int) -> tuple[str, str]:
    event = logged(RUN, seq).event
    assert event.type == "action_declared"
    return event.creature_id, event.text


def _routed(seq: int) -> object:
    actor, text = _typed(seq)
    return fight_intent(replay_until(RUN, seq), actor, text)


async def _fight_turn(tmp_path: Path, seq: int) -> list[AnyEvent]:
    actor, text = _typed(seq)
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


def test_v1_m32_weapon_lines_are_the_weapon_attack() -> None:
    """X1: any verb, a weapon (one of the hero's or a weapon kind) and a present foe."""
    expected = {
        171: ("pc-p2", "thug-1", "main_hand"),  # slash at the thug's knees with my longsword
        215: ("pc-p2", "thug-1", "main_hand"),  # run the thug through with my longsword
        354: ("pc-p4", "violet-fungus-1", "ranged"),  # lets fly with her shortbow at the fungus
        443: ("pc-p4", "zombie-1", "ranged"),  # put an arrow in the zombie's chest
        749: ("pc-p2", "bugbear-1", "main_hand"),  # hammer the Duke again with my longsword
    }
    for seq, (actor, foe, option) in expected.items():
        assert _routed(seq) == AttackCommand(actor_id=actor, target_id=foe, option=option), seq


def test_v1_m32_weapon_line_stunts_stay_creative() -> None:
    """X1: a shove, a trip, a throw, a weapon shown or put away is not a weapon blow."""
    state = replay_until(RUN, 215)
    for text in (
        "I trip the thug with my longsword",
        "I shove the thug off the steps with my shield and longsword",
        "I throw my longsword at the thug",
        "I wipe the thug's blood off my longsword",
        "I sheathe my longsword and glare at the thug",
    ):
        assert fight_intent(state, "pc-p2", text) is None, text


async def test_v1_m32_typed_weapon_line_rolls_against_armour(tmp_path: Path) -> None:
    """X1, typed 215-217: the run-through was a bare Athletics check told as a kill (the thug
    lived at 2/32). Now it is the longsword's attack roll against AC, no check, no flat damage."""
    events = await _fight_turn(tmp_path, 215)
    rolled = [e for e in events if isinstance(e, AttackRolled) and e.attacker_id == "pc-p2"]
    assert [(e.attack, e.target_id) for e in rolled] == [("Longsword", "thug-1")]
    assert not any(isinstance(e, CheckResolved) and e.creature_id == "pc-p2" for e in events)
    assert not any(isinstance(e, DiceRolled) and e.label == "Creative action" for e in events)


def test_v1_m32_creative_arrow_damage_is_the_bow_attack() -> None:
    """X1, typed 444-448: creative damage from "an arrow in the zombie's chest" was a flat 2d6;
    the creative weapon rule now rolls the ranged option against armour."""
    state = replay_until(RUN, 443)
    args = CreativeEffectArgs(
        actor="pc-p4",
        target="zombie-1",
        effect_kind=EffectKind.MINOR_DAMAGE,
        damage_type=DamageType.PIERCING,
    )
    ctx = ToolContext(actor_id="pc-p4", player_text="I put an arrow in the zombie's chest")
    result = run_creative_effect(state, args, ctx, random.Random(3), tool_registries())
    rolled = [e for e in result.events if isinstance(e, AttackRolled)]
    assert [(e.attack, e.target_id) for e in rolled] == [("Shortbow", "zombie-1")]
    assert not any(
        isinstance(e, DiceRolled) and e.label == "Creative action" for e in result.events
    )


def test_v1_m32_spell_said_as_a_strike_is_the_cast() -> None:
    """X2, typed 497: "Tamsin hits the zombie with a Guiding Bolt" was a melee attack refused as
    out of reach; a spell name wins over a strike verb."""
    found = _routed(496)
    assert found == CastCommand(actor_id="pc-p8", spell_id="guiding-bolt", target_ids=("zombie-1",))


async def test_v1_m32_spell_said_as_a_strike_casts_it(tmp_path: Path) -> None:
    events = await _fight_turn(tmp_path, 496)
    cast = [e for e in events if isinstance(e, SpellCast)]
    assert [(e.spell_id, e.target_ids) for e in cast] == [("guiding-bolt", ("zombie-1",))]
    assert not any(isinstance(e, CombatantMoved) for e in events)
