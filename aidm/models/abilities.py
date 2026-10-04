"""Ability identifiers shared by every layer.

Public API:
- `Ability`: StrEnum of the six abilities. Values equal the SRD `ability_scores` index
  ("str", "dex", "con", "int", "wis", "cha"), so `Ability("dex")` parses SRD references directly.
- `ABILITIES`: the six abilities in canonical sheet order (STR, DEX, CON, INT, WIS, CHA).

The arithmetic (modifier, proficiency bonus) lives in `aidm.rules.abilities`.
"""

from enum import StrEnum


class Ability(StrEnum):
    STR = "str"
    DEX = "dex"
    CON = "con"
    INT = "int"
    WIS = "wis"
    CHA = "cha"


ABILITIES: tuple[Ability, ...] = tuple(Ability)
