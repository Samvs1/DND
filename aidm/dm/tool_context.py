"""Inputs and outputs of the DM tool executors (SPEC 6.1 step 2, 6.3).

Public API:
- `ToolRegistries(combat, tiers, encounter_monsters, encounter_tables, terrains)`: the data the
  executors read, passed in (`tool_registries()` builds the default bundle once).
- `ToolContext(actor_id, confirm_hostile)`: who is acting, and whether that player explicitly
  confirmed a hostile act against non-hostile NPCs (the point of no return; the session sets
  it after the confirm dialog).
- `PendingConfirmation(actor_id, npc_ids, tool, prompt)`: a hostile act that waits for the
  player's confirmation; nothing was executed.
- `ToolResult(events, summary, error, pending)`: what one tool call produced. `summary` is the
  short text fed back to the model; `error` (no events) is a validation refusal returned to
  the model as a tool error; `pending` marks a point-of-no-return stop. `ok` is True when the
  tool executed.
- `ToolRefused(message)`: raised inside executors, turned into `ToolResult(error=...)`.
"""

import functools
from dataclasses import dataclass

from aidm.data.combat_data import CombatRegistries, combat_registries
from aidm.data.dm_tiers import DmTiers, dm_tiers
from aidm.data.encounter_monsters import EncounterMonster, encounter_monsters
from aidm.data.encounter_tables import EncounterTables, encounter_tables
from aidm.data.registry import Registry
from aidm.data.zone_templates import TerrainTemplate, zone_templates
from aidm.models.events import AnyEvent


@dataclass(frozen=True)
class ToolRegistries:
    combat: CombatRegistries
    tiers: DmTiers
    encounter_monsters: Registry[EncounterMonster]
    encounter_tables: EncounterTables
    terrains: Registry[TerrainTemplate]


@functools.cache
def tool_registries() -> ToolRegistries:
    return ToolRegistries(
        combat=combat_registries(),
        tiers=dm_tiers(),
        encounter_monsters=encounter_monsters(),
        encounter_tables=encounter_tables(),
        terrains=zone_templates(),
    )


@dataclass(frozen=True)
class ToolContext:
    actor_id: str | None = None
    confirm_hostile: bool = False


@dataclass(frozen=True)
class PendingConfirmation:
    actor_id: str | None
    npc_ids: tuple[str, ...]
    tool: str
    prompt: str


@dataclass(frozen=True)
class ToolResult:
    events: tuple[AnyEvent, ...] = ()
    summary: str = ""
    error: str | None = None
    pending: PendingConfirmation | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.pending is None


class ToolRefused(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
