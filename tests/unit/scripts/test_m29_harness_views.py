"""M29.5b-2 harness views (docs/playtests/M29_round1.md G23 G24 G12), from the p2 / p1 saves:
stable foe numbers for a whole fight, every hero that can level flagged, an honest no-fight line."""

from typing import Any

import pytest

from scripts.agent.commands import UsageError, target_of
from scripts.agent.text import foe_list, look_text, no_fight_text, option_lines

Msg = dict[str, Any]


def _token(cid: str, name: str, side: str, **extra: Any) -> Msg:
    base = {"creature_id": cid, "name": name, "side": side, "hp": 11, "max_hp": 11}
    return {**base, "zone_id": "z1", "dead": False, "withdrawn": False, **extra}


def _wolves(fled: bool, dead: bool) -> Msg:
    """p2 enc-277: Wolf A fled at 293, Wolf B died at 321 (tokens sorted by creature id)."""
    return {
        "round": 1,
        "active_id": "pc-p2",
        "turn_of": "pc-p2",
        "zones": [{"id": "z1", "name": "Knoll"}],
        "tokens": [
            _token("pc-p2", "Brienne", "party"),
            _token("wolf-1", "Wolf A", "hostile", hp=2, withdrawn=fled),
            _token("wolf-2", "Wolf B", "hostile", dead=dead),
        ],
        "economy": {"action": True, "bonus_action": True, "attacks_left": 1, "movement_left": 30},
    }


def test_m29_foe_numbers_stay_put_and_fled_foes_are_no_targets() -> None:
    """G23 (p2 293, 313): after Wolf A fled, "attack 1" hit Wolf B (the numbers shifted)."""
    before = foe_list(_wolves(False, False), "pc-p2")
    after = foe_list(_wolves(True, False), "pc-p2")
    assert [f["creature_id"] for f in before] == [f["creature_id"] for f in after]
    assert target_of("2", after) == "wolf-2"
    with pytest.raises(UsageError, match="fled"):
        target_of("1", after)
    with pytest.raises(UsageError, match="dead"):
        target_of("2", foe_list(_wolves(True, True), "pc-p2"))
    lines = option_lines(_wolves(True, False), "pc-p2", None)
    assert any(line.startswith("do attack 2   (Wolf B") for line in lines)
    assert not any(line.startswith("do attack 1") for line in lines)
    text = look_text(_state(combat=_wolves(True, False)), 313, "pc-p2")
    assert "foe 1: wolf-1 Wolf A (hostile) 2/11hp (fled: not a target)" in text
    assert "foe 2: wolf-2 Wolf B" in text


def _hero(cid: str, name: str, level: int, xp: int, **extra: Any) -> Msg:
    return {"id": cid, "name": name, "hp": 10, "max_hp": 10, "level": level, "xp": xp, **extra}


def _state(**extra: Any) -> Msg:
    party = [
        _hero("pc-p2", "Brienne", 1, 337),
        _hero("pc-p4", "Elowen", 1, 337),
        _hero("pc-p6", "Rook", 2, 337),
        _hero("pc-p8", "Tamsin", 1, 337, dead=True),
    ]
    base: Msg = {"campaign_id": "c-1", "phase": "play", "party": party, "scene": None}
    return {**base, **extra}


def test_m29_level_up_flags_every_eligible_hero() -> None:
    """G24 (p2 231-238): all four heroes reached 337 XP (level 2 at 300) but `look` flagged only
    the hero whose seat asked. Now every living hero below the level its XP reached is named."""
    text = look_text(_state(), 240, "pc-p2", level_up=True)
    assert "LEVEL UP available for Brienne, Elowen: run `levelup --as <name>`." in text


def test_m29_do_after_a_defeat_says_the_fight_is_over() -> None:
    """G12 (p1 517): `do` after a wipe answered "There is no fight: use act."."""
    fallen = no_fight_text({"defeat": {"reason": "wiped"}, "checkpoint": True})
    assert fallen.startswith("The fight is over: the party has fallen.") and "retry" in fallen
    assert "fight is over" in no_fight_text({})
