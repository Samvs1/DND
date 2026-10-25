"""M32.1a X1, X2 and X6 (docs/playtests/M31_round5.md): typed weapon lines, a spell said as a
strike, and compound lines in a fight, on the real round-5 states (tests/session/playtest_saves.py,
fixture m32-r5-typed)."""

from pathlib import Path

from aidm.dm.fake_llm import FakeStep
from aidm.models.combat_events import AttackRolled, CombatantMoved, SpellCast
from aidm.models.events import AnyEvent, CheckResolved, DiceRolled
from aidm.models.protocol_client import SubmitAction
from aidm.session import combat_flow
from tests.session.playtest_saves import logged, replay_until
from tests.session.table_fixtures import assert_replays, join, menu_down, pick, running

RUN = "m32-r5-typed"


def _typed(seq: int) -> tuple[str, str]:
    event = logged(RUN, seq).event
    assert event.type == "action_declared"
    return event.creature_id, event.text


async def _fight_turn(tmp_path: Path, seq: int, chosen: FakeStep) -> list[AnyEvent]:
    """`chosen`: the menu chooser's scripted reading of the typed line (M36.10b)."""
    actor, text = _typed(seq)
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


async def test_v1_m32_typed_weapon_line_rolls_against_armour(tmp_path: Path) -> None:
    """X1, typed 215-217: the run-through was a bare Athletics check told as a kill (the thug
    lived at 2/32). Now it is the longsword's attack roll against AC, no check, no flat damage."""
    events = await _fight_turn(tmp_path, 215, pick(("attack:longsword", ["thug-1"], None)))
    rolled = [e for e in events if isinstance(e, AttackRolled) and e.attacker_id == "pc-p2"]
    assert [(e.attack, e.target_id) for e in rolled] == [("Longsword", "thug-1")]
    assert not any(isinstance(e, CheckResolved) and e.creature_id == "pc-p2" for e in events)
    assert not any(isinstance(e, DiceRolled) and e.label == "Creative action" for e in events)


async def test_v1_m32_spell_said_as_a_strike_casts_it(tmp_path: Path) -> None:
    events = await _fight_turn(tmp_path, 496, pick(("cast:guiding-bolt", ["zombie-1"], None)))
    cast = [e for e in events if isinstance(e, SpellCast)]
    assert [(e.spell_id, e.target_ids) for e in cast] == [("guiding-bolt", ("zombie-1",))]
    assert not any(isinstance(e, CombatantMoved) for e in events)
