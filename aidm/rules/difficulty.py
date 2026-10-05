"""Difficulty multipliers applied by the rules (M6.5, `GameState.difficulty`).

Public API:
- `scale_spawn(creature, mult) -> Creature`: a freshly spawned hostile monster with max and
  current hit points multiplied (rounded half up, at least 1).
- `scale_damage(state, attacker_id, packets) -> Sequence[DamagePacket]`: the packets a hostile
  monster deals multiplied by `state.difficulty.monster_damage` (positive amounts stay >= 1);
  everyone else's damage and the default 1.0 return the packets unchanged.
"""

from collections.abc import Sequence

from aidm.models.damage import DamagePacket
from aidm.models.encounter import Side
from aidm.models.state import Creature, CreatureKind, GameState


def _scaled(value: int, mult: float) -> int:
    return max(1, int(value * mult + 0.5)) if value > 0 else value


def scale_spawn(creature: Creature, mult: float) -> Creature:
    if mult == 1.0:
        return creature
    hp = _scaled(creature.max_hp, mult)
    return creature.model_copy(update={"max_hp": hp, "hp": hp})


def scale_damage(
    state: GameState, attacker_id: str, packets: Sequence[DamagePacket]
) -> Sequence[DamagePacket]:
    mult = state.difficulty.monster_damage
    attacker = state.creatures.get(attacker_id)
    enc = state.encounter
    if mult == 1.0 or attacker is None or attacker.kind is not CreatureKind.MONSTER:
        return packets
    seat = enc.combatants.get(attacker_id) if enc is not None else None
    if seat is None or seat.side is not Side.HOSTILE:
        return packets
    return [p.model_copy(update={"amount": _scaled(p.amount, mult)}) for p in packets]
