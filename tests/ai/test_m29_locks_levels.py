"""M29.7c round-2 findings R24 (an unpickable lock got a check) and R25 (the level-up offer and
the rule disagreed for a downed hero), from the full-campaign save (docs/playtests/M29_round2.md).
"""

from aidm.rules.leveling import can_level_up, level_up_refusal, xp_for_level
from scripts.agent.text import level_up_names
from tests.session.playtest_saves import replay_until


def test_m29_downed_hero_is_not_offered_a_level_up() -> None:
    """full 2286: `levelup` refused the unconscious Rook while `look` said LEVEL UP available."""
    state = replay_until("r2-full", 2000)
    rook = state.creatures["pc-p6"]
    assert rook.pc is not None
    rook.pc.xp = xp_for_level(rook.pc.level + 1)
    assert can_level_up(rook)
    rook.hp = 0
    assert not can_level_up(rook)
    assert level_up_refusal(rook) == "a downed hero must be back on their feet to level up"
    party = {
        "party": [{"id": rook.id, "name": rook.name, "level": rook.pc.level, "xp": rook.pc.xp}]
    }
    assert level_up_names(party | {"party": [party["party"][0] | {"hp": 0}]}) == []
    assert level_up_names({"party": [party["party"][0] | {"hp": 5}]}) == [rook.name]
