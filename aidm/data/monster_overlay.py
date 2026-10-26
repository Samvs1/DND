"""Monster action overlay: data/bg3/monster_actions.json, the mechanics the SRD stat block keeps
only in prose (M3.8).

The SRD JSON stores attack bonuses, DCs, damage, usage and multiattack parts, but a rider such
as the ghoul's paralyzing claws or a dragon's prone-inducing wing beat lives in the description.
An overlay entry adds those mechanics as spell DSL effects (`aidm.data.spell_defs.Effect`), read
by the same interpreter as spells. Keys: "<monster index>/<action slug>" for one monster, or the
bare action slug for every monster with that action ("wing-attack"); the specific key wins.

`ActionOverlay` fields:
- `dc`: the save DC for `on_hit` riders when the stat block gives none.
- `on_hit`: effects run on the target after an attack hits (a `save` effect uses `dc`).
- `on_fail`: effects appended to a save action's failed-save effects (after its damage).
- `exempt_types`: creature types or PC races the `on_hit` riders skip ("undead", "elf").
- `targeting` / `range`: replace the area and range read from the description.

Public API: `ActionOverlay`, `MonsterOverlay(actions)` with `for_action(monster, key)`,
`load_monster_overlay(path=None)`, `monster_overlay()` (default file, cached).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from aidm.data.spell_defs import Effect, SpellRange, Targeting

DEFAULT_MONSTER_OVERLAY = (
    Path(__file__).resolve().parents[2] / "data" / "bg3" / "monster_actions.json"
)


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ActionOverlay(_Strict):
    dc: int | None = Field(default=None, ge=1, le=30)
    on_hit: tuple[Effect, ...] = ()
    on_fail: tuple[Effect, ...] = ()
    exempt_types: tuple[str, ...] = ()
    targeting: Targeting | None = None
    range: SpellRange | None = None


class MonsterOverlay(_Strict):
    actions: dict[str, ActionOverlay] = Field(default_factory=dict[str, ActionOverlay])

    def for_action(self, monster: str, key: str) -> ActionOverlay | None:
        return self.actions.get(f"{monster}/{key}") or self.actions.get(key)


def load_monster_overlay(path: Path | None = None) -> MonsterOverlay:
    target = path if path is not None else DEFAULT_MONSTER_OVERLAY
    return MonsterOverlay.model_validate(json.loads(target.read_text(encoding="utf-8")))


@functools.cache
def monster_overlay() -> MonsterOverlay:
    return load_monster_overlay()
