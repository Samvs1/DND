"""Generic per-creature resources that recharge on rests (the hook for slots and features).

Public API:
- `ResourceError(ValueError)`: unknown key or not enough left (a tool turns it into a refusal).
- `define_resource(creature, key, maximum, recharge) -> list[AnyEvent]`: `[ResourceSet]` with a
  full pool (`current = maximum`); re-defining replaces it (level-up raises the maximum).
- `resource_left(creature, key) -> int`: current amount, 0 for an unknown key.
- `spend_resource(creature, key, amount=1) -> list[AnyEvent]`: `[ResourceSet]` with
  `current - amount`. ResourceError when unknown or insufficient; ValueError for amount < 1.
- `restore_resources(creature, kinds) -> list[AnyEvent]`: one `ResourceSet` per resource whose
  recharge kind is in `kinds` and that is not already full (sorted by key, deterministic).
- `turn_recharge_events(rng, creature) -> list[AnyEvent]` (M3.8, called by `turns.begin_turn`):
  each spent pool with a `turn_recharge` (sorted by key) refills; a value above 1 first rolls a
  d6 (logged as `DiceRolled`, label "recharge <key>") and refills only on that value or more
  (SRD "Recharge 5-6"); 1 refills without a roll (legendary actions).
"""

from collections.abc import Collection

from aidm.models.events import AnyEvent, DiceRolled, ResourceSet
from aidm.models.state import Creature, RechargeKind, Resource
from aidm.rules.dice import Rng, roll

RECHARGE_DIE = "1d6"


class ResourceError(ValueError):
    """A resource that does not exist or has too little left."""


def define_resource(
    creature: Creature, key: str, maximum: int, recharge: RechargeKind
) -> list[AnyEvent]:
    resource = Resource(current=maximum, maximum=maximum, recharge=recharge)
    return [ResourceSet(creature_id=creature.id, key=key, resource=resource)]


def resource_left(creature: Creature, key: str) -> int:
    resource = creature.resources.get(key)
    return 0 if resource is None else resource.current


def spend_resource(creature: Creature, key: str, amount: int = 1) -> list[AnyEvent]:
    if amount < 1:
        raise ValueError("amount must be >= 1")
    resource = creature.resources.get(key)
    if resource is None:
        raise ResourceError(f"{creature.id!r} has no resource {key!r}")
    if resource.current < amount:
        raise ResourceError(f"{creature.id!r} has {resource.current} {key!r}, needs {amount}")
    spent = resource.model_copy(update={"current": resource.current - amount})
    return [ResourceSet(creature_id=creature.id, key=key, resource=spent)]


def restore_resources(creature: Creature, kinds: Collection[RechargeKind]) -> list[AnyEvent]:
    events: list[AnyEvent] = []
    for key in sorted(creature.resources):
        resource = creature.resources[key]
        if resource.recharge in kinds and resource.current < resource.maximum:
            full = resource.model_copy(update={"current": resource.maximum})
            events.append(ResourceSet(creature_id=creature.id, key=key, resource=full))
    return events


def turn_recharge_events(rng: Rng, creature: Creature) -> list[AnyEvent]:
    events: list[AnyEvent] = []
    for key in sorted(creature.resources):
        resource = creature.resources[key]
        need = resource.turn_recharge
        if need is None or resource.current >= resource.maximum:
            continue
        if need > 1:
            rolled = roll(RECHARGE_DIE, rng)
            events.append(DiceRolled(roll=rolled, roller_id=creature.id, label=f"recharge {key}"))
            if rolled.total < need:
                continue
        full = resource.model_copy(update={"current": resource.maximum})
        events.append(ResourceSet(creature_id=creature.id, key=key, resource=full))
    return events
