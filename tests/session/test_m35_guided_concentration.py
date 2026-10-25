"""M35.3 round-6 Y2 and Y3 (docs/playtests/M34_round6.md) on the real r6-typed state
(fixture m35-r6-typed, the whole log; tests/session/playtest_saves.py)."""

import random
from pathlib import Path

from aidm.data.combat_data import combat_registries
from aidm.models.combat_events import AttackRolled
from aidm.models.commands import AttackCommand
from aidm.models.encounter import EncounterStatus
from aidm.models.events import ConcentrationEnded, ConditionRemoved
from aidm.rules.attack_profiles import find_option
from aidm.rules.commands import execute_command
from aidm.rules.concentration import orphaned_concentration_events
from aidm.rules.hit_chance import attack_situation
from aidm.session.combat_runner import CombatRunner
from aidm.session.reducer import apply
from tests.session.playtest_saves import logged, replay_until
from tests.session.table_fixtures import assert_replays, disabled_llm, running

TYPED = "m35-r6-typed"
REGS = combat_registries()


def test_v1_m35_guided_advantage_is_used_by_the_dagger_not_the_longsword() -> None:
    """Y2, typed 1260-1293: Elowen's dagger (1276) and Brienne's longsword (1286) both rolled
    with Guiding Bolt's advantage. The dagger uses it up; the longsword rolls without it."""
    assert logged(TYPED, 1260).event.type == "condition_applied"
    state = replay_until(TYPED, 1275)  # Elowen's turn, before her action is spent
    stab = AttackCommand(actor_id="pc-p4", target_id="wight-1", option="main_hand")
    events = execute_command(state, stab, REGS, random.Random(5))
    rolled = next(e for e in events if isinstance(e, AttackRolled))
    assert rolled.attack == "Dagger" and "Guided" in rolled.adv_why
    used = [e for e in events if isinstance(e, ConditionRemoved)]
    assert [(e.creature_id, e.name) for e in used] == [("wight-1", "guided")]
    for event in events:
        apply(state, event)
    assert not state.creatures["wight-1"].conditions
    longsword = find_option(state.creatures["pc-p2"], REGS.chars, "main_hand")
    assert longsword is not None and longsword.name == "Longsword"
    after = attack_situation(state, "pc-p2", "wight-1", longsword, REGS.chars.features)
    assert "Guided" not in after.adv_why


def test_v1_m35_fight_end_ends_tamsins_empty_concentration() -> None:
    """Y3, typed 262-313, 405: Guidance on Elowen ended with the crocodile fight (313) and Tamsin
    kept concentrating on nothing, rolling Constitution saves when hit (401)."""
    stale = replay_until(TYPED, 314)  # the log as played: concentration left behind
    held = stale.creatures["pc-p8"].concentrating_on
    assert held is not None and held.spell_id == "guidance"
    state = replay_until(TYPED, 312)  # the crocodile is dead, the fight not yet ended
    runner = CombatRunner(state, REGS, random.Random(1))
    assert runner.run() is EncounterStatus.VICTORY
    names = [type(e).__name__ for e in runner.log]
    gone = names.index("ConditionRemoved")
    ended = [e for e in runner.log if isinstance(e, ConcentrationEnded)]
    assert [(e.creature_id, e.spell_id) for e in ended] == [("pc-p8", "guidance")]
    assert names.index("ConcentrationEnded") == gone + 1
    assert state.creatures["pc-p8"].concentrating_on is None
    assert orphaned_concentration_events(state) == []


async def test_v1_m35_table_ends_concentration_when_guidance_is_removed(tmp_path: Path) -> None:
    """Y3 on the table's own mutation path (exploration, tools): removing the last linked
    condition logs a ConcentrationEnded right after it, and the log still replays."""
    state = replay_until(TYPED, 264)  # Guidance on Elowen, out of combat
    async with running(disabled_llm(tmp_path), state) as (table, _clock):
        table.apply(
            ConditionRemoved(
                creature_id="pc-p4", name="guidance", source_id="pc-p8", exact_source=True
            )
        )
        kinds = [type(entry.event).__name__ for entry in table.log]
        assert kinds[-2:] == ["ConditionRemoved", "ConcentrationEnded"]
        assert table.state.creatures["pc-p8"].concentrating_on is None
        assert_replays(table)
