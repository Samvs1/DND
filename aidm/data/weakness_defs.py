"""Substance weaknesses: the schema of data/bg3/weaknesses.json and its validating loader (M27.6).

A hand-written table, not a parse of SRD prose: monster id -> substance -> effect. ONE pure rule
(`aidm.rules.weaknesses`) applies a row whenever a hit delivers a substance the target is weak to
(the item's `substances` in data/bg3/item_uses.json). Damage-type vulnerabilities and resistances
are not here: they stay in the damage path.

`WeaknessEffect(trait, amount, damage_type, source)`: the monster's special trait that grants it
(checked against the SRD stat block), a flat damage amount per delivery, its damage type and the
SRD citation.

Public API: `WeaknessEffect`, `WeaknessTable` (monster id -> substance -> effect),
`WeaknessError` (names the bad entry), `load_weakness_defs(path=None)`, `weakness_defs()`
(cached), `weaknesses_of(monster_index) -> dict[substance, WeaknessEffect]`.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from aidm.data.condition_defs import DamageKey
from aidm.data.item_uses import Substance
from aidm.data.srd import srd

DEFAULT_WEAKNESSES = Path(__file__).resolve().parents[2] / "data" / "bg3" / "weaknesses.json"


class WeaknessEffect(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trait: str = Field(min_length=1)
    amount: int = Field(ge=1)
    damage_type: DamageKey
    source: str = Field(min_length=1)


type WeaknessTable = dict[str, dict[Substance, WeaknessEffect]]

_TABLE: TypeAdapter[dict[str, dict[Substance, WeaknessEffect]]] = TypeAdapter(
    dict[str, dict[Substance, WeaknessEffect]]
)


class WeaknessError(ValueError):
    """A bad weaknesses.json entry; `entry` is the monster id (or "file")."""

    def __init__(self, entry: str, problem: str) -> None:
        super().__init__(f"weakness {entry!r}: {problem}")
        self.entry = entry
        self.problem = problem


def _check(table: WeaknessTable) -> None:
    monsters = srd().monsters
    for monster_id, rows in table.items():
        block = monsters.find(monster_id)
        if block is None:
            raise WeaknessError(monster_id, "unknown monster id")
        traits = {a.name for a in block.special_abilities}
        for substance, effect in rows.items():
            if effect.trait not in traits:
                raise WeaknessError(monster_id, f"{substance}: no trait {effect.trait!r}")


def load_weakness_defs(path: Path | None = None) -> WeaknessTable:
    target = path if path is not None else DEFAULT_WEAKNESSES
    raw = json.loads(target.read_text(encoding="utf-8"))
    try:
        table = _TABLE.validate_python(raw)
    except ValidationError as error:
        loc = error.errors()[0]["loc"]
        entry = str(loc[0]) if loc else "file"
        raise WeaknessError(entry, str(error.errors()[0]["msg"])) from error
    _check(table)
    return table


@functools.cache
def weakness_defs() -> WeaknessTable:
    return load_weakness_defs()


def weaknesses_of(monster_index: str | None) -> dict[Substance, WeaknessEffect]:
    return weakness_defs().get(monster_index or "", {})
