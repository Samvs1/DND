"""Expected damage of a strike option (M29.7e H8): hit chance x average damage.

The `hit_chances` payload has the hit and crit chance per option (close combat disadvantage is
already inside it); the sheet's attack lines have the damage expression of each hand. Pure.

Public API: `avg_dice`, `expected_damage`, `pick_option`.
"""

import re
from typing import Any

Msg = dict[str, Any]
_DICE = re.compile(r"(\d+)d(\d+)")
_FLAT = re.compile(r"[+-]?\s*\d+")
UNKNOWN_AVG = 4.5


def avg_dice(expr: str) -> float:
    """Average of a dice expression such as `1d8+3` or `2d6` (a bare number is itself)."""
    total = sum(int(n) * (int(s) + 1) / 2 for n, s in _DICE.findall(expr))
    rest = _DICE.sub("", expr)
    return total + sum(int(x.replace(" ", "")) for x in _FLAT.findall(rest))


def _avg_of(option: str, attacks: list[Msg]) -> float:
    for a in attacks:
        if option in (a.get("hand"), a.get("item"), a.get("name")):
            return avg_dice(str(a.get("damage", ""))) or UNKNOWN_AVG
    return UNKNOWN_AVG


def expected_damage(chance: Msg, attacks: list[Msg]) -> float:
    """Hit chance x average damage, a crit adding one more set of the damage dice."""
    avg = _avg_of(str(chance["option"]), attacks)
    bonus = sum(avg_dice(d) for d in chance.get("bonus_dice", []))
    hit = float(chance["probability"])
    return hit * (avg + bonus) + float(chance.get("crit_chance", 0.0)) * avg / 2


def pick_option(chances: list[Msg], attacks: list[Msg]) -> str:
    """The weapon strike with the best expected damage among those in range."""
    weapons = [c for c in chances if not str(c["option"]).startswith("spell:")]
    pool = [c for c in weapons if c.get("in_range", True)] or weapons
    if not pool:
        return "main_hand"
    return str(max(pool, key=lambda c: expected_damage(c, attacks))["option"])
