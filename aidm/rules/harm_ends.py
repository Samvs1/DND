"""Charms that end when the charmer's side does harm (M29.7d, round 2 R20). Pure, events only.

SRD 5.1 Animal Friendship and Charm Person: "if you or your companions" harm the target, the
spell ends. Data-driven: a condition whose `ConditionDef.ends_on_source_side_harm` is set (the
"befriended" condition of those spells) ends when its bearer takes damage from the creature that
applied it or from anyone on that creature's side. Sides come from the active fight; outside a
fight every hero (and only a hero) stands on the party side.

Public API:
- `side_of(state, creature_id) -> Side | None`.
- `harm_ended_events(state, taken) -> list[AnyEvent]`: `ConditionRemoved` for each such instance
  on the damaged creature, after any damage above 0 (call it after the damage events applied).
- `befriended_by_party(state, creature_id) -> bool`: the creature bears such a condition applied
  by a party-side creature (it does not keep a fight going: `rules.encounter`).
"""

from aidm.models.encounter import EncounterStatus, Side
from aidm.models.events import AnyEvent, ConditionRemoved, DamageTaken
from aidm.models.state import GameState
from aidm.rules.conditions import condition_def


def side_of(state: GameState, creature_id: str) -> Side | None:
    enc = state.encounter
    if enc is not None and enc.status is EncounterStatus.ACTIVE and creature_id in enc.combatants:
        return enc.combatant(creature_id).side
    creature = state.creatures.get(creature_id)
    return Side.PARTY if creature is not None and creature.pc is not None else None


def _same_side(state: GameState, a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return False
    if a == b:
        return True
    side = side_of(state, a)
    return side is not None and side == side_of(state, b)


def harm_ended_events(state: GameState, taken: DamageTaken) -> list[AnyEvent]:
    bearer = state.creatures.get(taken.creature_id)
    if bearer is None or taken.total <= 0:
        return []
    return [
        ConditionRemoved(
            creature_id=bearer.id, name=c.name, source_id=c.source_id, exact_source=True
        )
        for c in bearer.conditions
        if condition_def(c.name).ends_on_source_side_harm
        and _same_side(state, c.source_id, taken.source_id)
    ]


def befriended_by_party(state: GameState, creature_id: str) -> bool:
    creature = state.creatures.get(creature_id)
    if creature is None:
        return False
    return any(
        condition_def(c.name).ends_on_source_side_harm
        and c.source_id is not None
        and side_of(state, c.source_id) is Side.PARTY
        for c in creature.conditions
    )
