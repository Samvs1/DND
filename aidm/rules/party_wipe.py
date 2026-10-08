"""Party wipe detection (M11.1, DECISIONS M11.1). Pure: reads state, never mutates.

The party is wiped when every hero (a PC creature) is dead, or when no hero can act (dead or at
0 HP: dying and stable heroes are down) AND no ally can help: during an ACTIVE fight a standing
PARTY-side combatant (a summon or an allied NPC) keeps the fight going, so the downed heroes keep
rolling death saves through the normal turn machinery. Outside a fight nobody else can help.
A hero who fled or surrendered and is still up is not down, so a lost fight is not always a wipe.

Public API:
- `can_act(creature) -> bool`: alive and above 0 HP.
- `party_heroes(state) -> list[Creature]`: the PC creatures, sorted by id.
- `ally_standing(state) -> bool`: a non-hero PARTY-side combatant stands in an ACTIVE fight.
- `party_wiped(state) -> bool`: the rule above (False with no heroes at all, e.g. the lobby).
- `standing_foes(state) -> list[str]`: names of the HOSTILE combatants still standing in the
  current (or just ended) encounter, deduplicated, sorted (defeat text and checkpoint labels).
"""

from aidm.models.encounter import EncounterStatus, Side
from aidm.models.state import Creature, CreatureKind, GameState
from aidm.rules.encounter import is_standing


def can_act(creature: Creature) -> bool:
    return not creature.dead and creature.hp > 0


def party_heroes(state: GameState) -> list[Creature]:
    heroes = [c for c in state.creatures.values() if c.kind is CreatureKind.PC and c.pc is not None]
    return sorted(heroes, key=lambda c: c.id)


def ally_standing(state: GameState) -> bool:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        return False
    for combatant in enc.combatants.values():
        creature = state.creatures.get(combatant.creature_id)
        if combatant.side is not Side.PARTY or creature is None or creature.pc is not None:
            continue
        if is_standing(state, combatant):
            return True
    return False


def party_wiped(state: GameState) -> bool:
    heroes = party_heroes(state)
    if not heroes:
        return False
    if all(c.dead for c in heroes):
        return True
    if any(can_act(c) for c in heroes):
        return False
    return not ally_standing(state)


def standing_foes(state: GameState) -> list[str]:
    enc = state.encounter
    if enc is None:
        return []
    names: set[str] = set()
    for combatant in enc.combatants.values():
        creature = state.creatures.get(combatant.creature_id)
        hostile = combatant.side is Side.HOSTILE and combatant.withdrawn is None
        if hostile and creature is not None and can_act(creature):
            names.add(creature.name)
    return sorted(names)
