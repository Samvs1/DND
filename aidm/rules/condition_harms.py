"""Harm from conditions over time (M27.6: burning from alchemist's fire).

Data-driven (data/bg3/conditions.json via `aidm.data.condition_defs`), never per condition:
- `turn_start_condition_damage(rng, state, creature_id)`: at the start of the bearer's turn each
  of its conditions with `turn_start_damage` rolls once (a `DiceRolled` of kind DAMAGE labelled
  with the condition's name) and goes through the damage choke point (resistances, immunities,
  temp HP, 0 HP) with the instance's source as the damage source, then the concentration check.
Ending a condition by its `end_check` (an action) is `rules.combat_actions.end_condition_command`.

Public API: `turn_start_condition_damage`.
"""

from aidm.models.damage import DamagePacket, DamageType
from aidm.models.dice import RollKind
from aidm.models.events import AnyEvent, DamageTaken, DiceRolled
from aidm.models.state import GameState
from aidm.rules.concentration import concentration_after_damage
from aidm.rules.conditions import condition_def
from aidm.rules.damage import resolve_damage
from aidm.rules.dice import Rng, roll
from aidm.rules.harm_ends import harm_ended_events
from aidm.rules.projection import project_state


def turn_start_condition_damage(rng: Rng, state: GameState, creature_id: str) -> list[AnyEvent]:
    events: list[AnyEvent] = []
    bearer = state.creatures.get(creature_id)
    if bearer is None or bearer.dead:
        return events
    for condition in bearer.conditions:
        cdef = condition_def(condition.name)
        if cdef.turn_start_damage is None or cdef.turn_start_damage_type is None:
            continue
        now = project_state(state, events).creatures[creature_id]
        if now.dead:
            break
        rolled = roll(cdef.turn_start_damage, rng)
        source = condition.source_id
        events.append(
            DiceRolled(
                roll=rolled,
                roller_id=source or creature_id,
                label=cdef.name,
                kind=RollKind.DAMAGE,
                target_id=creature_id,
            )
        )
        packet = DamagePacket(
            amount=max(0, rolled.total), damage_type=DamageType(cdef.turn_start_damage_type)
        )
        hurt = resolve_damage(now, [packet], source_id=source)
        events.extend(hurt)
        if hurt and isinstance(hurt[0], DamageTaken):
            after = project_state(state, events)
            events.extend(concentration_after_damage(rng, after, hurt[0]))
            events.extend(harm_ended_events(after, hurt[0]))
    return events
