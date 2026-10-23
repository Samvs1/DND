"""Harm from conditions over time (M27.6: burning from alchemist's fire).

Data-driven (data/bg3/conditions.json via `aidm.data.condition_defs`), never per condition:
- `turn_start_condition_damage(rng, state, creature_id)`: at the start of the bearer's turn each
  of its conditions with `turn_start_damage` rolls once (a `DiceRolled` of kind DAMAGE labelled
  with the condition's name) and goes through the damage choke point (resistances, immunities,
  temp HP, 0 HP) with the instance's source as the damage source, then the concentration check.
- `turn_end_condition_damage(rng, state, creature_id)` (M29.9a): the same for `turn_end_damage`
  at the end of the bearer's turn, before the turn-end ticks (Acid Arrow's later acid).
Ending a condition by its `end_check` (an action) is `rules.combat_actions.end_condition_command`.

Public API: `turn_start_condition_damage`, `turn_end_condition_damage`.
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


def _harm_dice(name: str, at_end: bool) -> tuple[str, str] | None:
    cdef = condition_def(name)
    dice = cdef.turn_end_damage if at_end else cdef.turn_start_damage
    kind = cdef.turn_end_damage_type if at_end else cdef.turn_start_damage_type
    return (dice, kind) if dice is not None and kind is not None else None


def _condition_damage(rng: Rng, state: GameState, creature_id: str, at_end: bool) -> list[AnyEvent]:
    events: list[AnyEvent] = []
    bearer = state.creatures.get(creature_id)
    if bearer is None or bearer.dead:
        return events
    for condition in bearer.conditions:
        harm = _harm_dice(condition.name, at_end)
        if harm is None:
            continue
        now = project_state(state, events).creatures[creature_id]
        if now.dead:
            break
        rolled = roll(harm[0], rng)
        source = condition.source_id
        events.append(
            DiceRolled(
                roll=rolled,
                roller_id=source or creature_id,
                label=condition_def(condition.name).name,
                kind=RollKind.DAMAGE,
                target_id=creature_id,
            )
        )
        packet = DamagePacket(amount=max(0, rolled.total), damage_type=DamageType(harm[1]))
        hurt = resolve_damage(now, [packet], source_id=source)
        events.extend(hurt)
        if hurt and isinstance(hurt[0], DamageTaken):
            after = project_state(state, events)
            events.extend(concentration_after_damage(rng, after, hurt[0]))
            events.extend(harm_ended_events(after, hurt[0], direct=False))
    return events


def turn_start_condition_damage(rng: Rng, state: GameState, creature_id: str) -> list[AnyEvent]:
    return _condition_damage(rng, state, creature_id, at_end=False)


def turn_end_condition_damage(rng: Rng, state: GameState, creature_id: str) -> list[AnyEvent]:
    return _condition_damage(rng, state, creature_id, at_end=True)
