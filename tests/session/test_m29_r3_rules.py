"""M29.9a rules findings from playtest round 3 (docs/playtests/M29_round3.md T1 T18 T19),
reproduced from the live saves (tests/session/playtest_saves.py)."""

import random

from aidm.dm.tool_context import tool_registries
from aidm.models.combat_events import FeatureUsed
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.events import ConditionApplied, HpChanged
from aidm.rules.damage import resolve_damage
from aidm.rules.spells import cast_spell
from tests.session.playtest_saves import replay_until


def test_m29_sleep_never_reaches_the_zombies() -> None:
    """r3-casters 353-355: Brienne's Sleep put zombie-1 to sleep. Undead are not affected."""
    state = replay_until("r3-casters", 351)
    regs = tool_registries().combat
    sleep = regs.spells.get("sleep")
    events = cast_spell(state, "pc-p2", sleep, 1, [], "rubble", random.Random(7), regs)
    assert state.creatures["zombie-1"].creature_type == "undead"  # both foes in the rubble
    assert [e.creature_id for e in events if isinstance(e, ConditionApplied)] == []


def test_m29_relentless_endurance_keeps_tamsin_up() -> None:
    """r3-full 211: Tamsin (half-orc, Relentless Endurance 1/1) took 6 piercing at 3 HP and
    dropped to 0. The feature keeps her at 1 HP now."""
    state = replay_until("r3-full", 211)
    tamsin = state.creatures["pc-p8"]
    assert tamsin.hp == 3 and tamsin.resources["relentless-endurance"].current == 1
    packet = DamagePacket(amount=6, damage_type=DamageType.PIERCING)
    events = resolve_damage(tamsin, [packet], source_id="sahuagin-1")
    assert [e.new_hp for e in events if isinstance(e, HpChanged)] == [1]
    assert any(isinstance(e, FeatureUsed) for e in events)
