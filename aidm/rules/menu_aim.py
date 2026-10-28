"""Where a fight step aimed at areas lands: the zone that holds what the line named (M43.2, M44.2;
SPEC 6.2, docs/next/M43_CONTRACT.md rule B3). Pure.

The fight menu lists for an area spell only the zones its cone, cube or sphere reaches, so a line
naming a foe out of reach has no fitting zone and the model picks one that is listed. The cast
is aimed at the named creature's zone instead, reached or not, and the cast's own rule
(`spell_targets.area_zones`, the one the button meets) answers: "The 15-ft cone does not reach
Tumbled Stones, 25 ft away." Never a stand-in zone (round 8 AA1 = round 2 R26, round 9 BB1).
- `area_aim(state, entry, step)` (M43.2): a step at a creature is aimed at the zone it stands in;
  a zone the step named wins.
- `line_aim(state, menu, entry, step, text)` (M44.2): a step at a zone that holds none of the
  creatures the line names (whole words, `menu_unoffered.named_creatures`; the hero aside), when
  it names one, is aimed at the first-named creature's zone. A line that names no creature, or
  one standing in the chosen zone, keeps the pick. Allies in the area are the spell's own (SRD).
- `zones_held(state, entry, pool, creature_ids)`: for an entry aimed at areas, the zones the
  creatures stand in, in that order (None for any other entry).

Public API: `area_aim`, `line_aim`, `zones_held`.
"""

from collections.abc import Sequence

from aidm.models.action_menu import ActionMenu, MenuEntry, MenuScope, MenuStep
from aidm.models.state import GameState
from aidm.rules.menu_unoffered import named_creatures


def zones_held(
    state: GameState, entry: MenuEntry, pool: set[str], creature_ids: Sequence[str]
) -> list[str] | None:
    if not entry.target_ids or not set(entry.target_ids) <= pool:
        return None
    enc = state.encounter
    if enc is None:
        return []
    return [enc.combatants[c].zone_id for c in creature_ids if c in enc.combatants]


def _zones(state: GameState) -> set[str]:
    enc = state.encounter
    return {z.id for z in enc.zone_map.zones} if enc is not None else set()


def area_aim(state: GameState, entry: MenuEntry, step: MenuStep) -> MenuStep:
    zones = _zones(state)
    held = zones_held(state, entry, zones, step.targets) if zones else None
    if held is None:
        return step
    aim = ([t for t in step.targets if t in zones] or held)[:1]
    return step.model_copy(update={"targets": tuple(aim)}) if aim else step


def line_aim(
    state: GameState, menu: ActionMenu, entry: MenuEntry, step: MenuStep, text: str
) -> MenuStep:
    zones = _zones(state)
    if menu.scope is not MenuScope.FIGHT or not text or len(step.targets) != 1:
        return step
    if step.targets[0] not in zones:
        return step
    held = zones_held(state, entry, zones, named_creatures(menu, text))
    if not held or step.targets[0] in held:
        return step
    return step.model_copy(update={"targets": (held[0],)})
