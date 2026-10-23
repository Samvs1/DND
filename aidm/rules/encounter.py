"""Encounter lifecycle: start, outcome detection, withdrawal and end (SPEC 7.2, 9).

Turn flow (begin/end turn) and the action economy live in `aidm.rules.turns`. The session drives
a fight as: `start_encounter` -> apply -> loop { `begin_turn` -> apply -> commands -> `end_turn`
-> apply; after every applied batch `encounter_outcome(state)`; when it is not None,
`end_encounter(state, outcome)` -> apply }. Rules never apply events themselves.

Public API:
- `EncounterRefusal`, `EncounterRefused(reason, detail)`: typed refusals; nothing is emitted.
- `active_encounter(state) -> Encounter`: the ACTIVE encounter, else refused.
- `start_encounter(rng, state, setup, monsters) -> list[AnyEvent]`: `monsters` is the SRD
  monster registry (an argument). Validates first (no active encounter, known zones, existing
  living party creatures placed once, known monster indexes, at least one combatant). Emits one
  `CreatureAdded` per spawn (ids `<monster>-<n>`, n = the first free number from 1, stats from
  `rules.monster_stats.creature_from_monster`; spawns of one fight that share a name get letters
  in spawn order, "Goblin A", "Goblin B", M20.7), then `EncounterStarted` (combatants, sorted
  initiative, round 1, no turn open), then a "surprised" condition (data-driven: no actions,
  movement or reactions until the end of the creature's first turn) on every creature of the
  surprised side. Foes at a place the party alerted are never surprised (`party_surprise`).
  M29.9a T8: this is the one door every fight start goes through, so a waiting encounter offer
  at the current place is resolved here (`OfferResolved`, choice fight) unless the setup says
  it answers that offer; the encounter records the place (`Encounter.node_id`).
- `party_surprise(state, surprise) -> SurpriseKind` (M27.3): HOSTILE becomes NONE when the
  current place is `World.alerted` (a noisy gear use, or arriving there with a carried light).
- `roll_initiative(rng, creatures) -> list[InitiativeEntry]`: BG3 1d4 + DEX modifier per
  creature, rolled in the given order, sorted by total, then DEX score, both descending, then
  creature id ascending (deterministic ties).
- `is_standing(state, combatant) -> bool`: in state, alive, above 0 HP and not withdrawn.
- `encounter_outcome(state) -> EncounterStatus | None` (None while the fight goes on):
  no PARTY-side combatant standing -> FLED if a party member withdrew by fleeing and is still up
  (alive, HP > 0), else DEFEAT (party wipe: everyone dead, dying or stable at 0 HP);
  otherwise no HOSTILE combatant standing -> VICTORY. NEUTRAL combatants never decide it, nor
  does a hostile befriended by the party (M29.7d, `rules.harm_ends`): when only such foes are
  left the fight ends as a victory; they are not defeated (no kill XP, no loot from them).
  M29.9a: a foe that surrendered to the party (`surrendered`, `rules.surrender`) ends the fight
  the same way and DOES count as defeated (`harm_ends.yielded_to_party`: kill XP and loot).
- `withdraw_combatant(state, creature_id, reason) -> list[AnyEvent]`: fled or surrendered.
- `defeated_hostiles(state) -> list[Combatant]`: the HOSTILE combatants that count as defeated
  (loot and kill XP use it).
- `kill_xp(state) -> int`: SRD XP of every HOSTILE combatant that is defeated (dead, at 0 HP or
  surrendered; fled enemies give nothing).
- `end_encounter(state, status) -> list[AnyEvent]`: `EncounterEnded` (kill XP split evenly,
  rounded down, among the living PCs of the party side), `combat_end_events` (ROUNDS conditions
  expire, everything else persists), then `XpGained` per recipient. Refused for status ACTIVE.
"""

from collections import Counter
from collections.abc import Sequence
from enum import StrEnum
from string import ascii_uppercase

from aidm.data.registry import Registry
from aidm.data.srd_monsters import SrdMonster
from aidm.models.abilities import Ability
from aidm.models.campaign_events import OfferResolved
from aidm.models.campaign_state import OfferChoice
from aidm.models.encounter import (
    Combatant,
    Encounter,
    EncounterSetup,
    EncounterStatus,
    InitiativeEntry,
    Side,
    SurpriseKind,
    TurnEconomy,
    WithdrawReason,
)
from aidm.models.encounter_events import CombatantWithdrew, EncounterEnded, EncounterStarted
from aidm.models.events import AnyEvent, CreatureAdded
from aidm.models.state import Creature, CreatureKind, GameState
from aidm.rules.abilities import ability_modifier
from aidm.rules.condition_timing import apply_condition, combat_end_events, new_condition
from aidm.rules.conditions import can_take_reactions
from aidm.rules.dice import Rng, roll
from aidm.rules.difficulty import scale_spawn
from aidm.rules.harm_ends import befriended_by_party, yielded_to_party
from aidm.rules.leveling import gain_xp
from aidm.rules.monster_stats import creature_from_monster

INITIATIVE_DIE = "1d4"
SURPRISED = "surprised"
SURPRISE_SOURCE = "surprise"

type _Spawn = tuple[Creature, Side, str, int]


class EncounterRefusal(StrEnum):
    ALREADY_ACTIVE = "already_active"
    NO_ACTIVE_ENCOUNTER = "no_active_encounter"
    UNKNOWN_ZONE = "unknown_zone"
    UNKNOWN_CREATURE = "unknown_creature"
    CREATURE_DOWN = "creature_down"
    DUPLICATE_PLACEMENT = "duplicate_placement"
    UNKNOWN_MONSTER = "unknown_monster"
    NO_COMBATANTS = "no_combatants"
    NOT_IN_ENCOUNTER = "not_in_encounter"
    INVALID_STATUS = "invalid_status"
    TURN_ALREADY_OPEN = "turn_already_open"
    NO_OPEN_TURN = "no_open_turn"
    NO_ONE_CAN_ACT = "no_one_can_act"


class EncounterRefused(ValueError):
    """An encounter operation the rules do not allow right now; `reason` says why."""

    def __init__(self, reason: EncounterRefusal, detail: str) -> None:
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason


def active_encounter(state: GameState) -> Encounter:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        raise EncounterRefused(EncounterRefusal.NO_ACTIVE_ENCOUNTER, "no fight is going on")
    return enc


def _validate(state: GameState, setup: EncounterSetup, monsters: Registry[SrdMonster]) -> None:
    if state.encounter is not None and state.encounter.status is EncounterStatus.ACTIVE:
        raise EncounterRefused(EncounterRefusal.ALREADY_ACTIVE, state.encounter.id)
    placements = [*setup.party, *setup.monsters]
    if not placements:
        raise EncounterRefused(EncounterRefusal.NO_COMBATANTS, "nobody to fight")
    for p in placements:
        if not setup.zone_map.has_zone(p.zone_id):
            raise EncounterRefused(EncounterRefusal.UNKNOWN_ZONE, p.zone_id)
    seen: set[str] = set()
    for p in setup.party:
        creature = state.creatures.get(p.creature_id)
        if creature is None:
            raise EncounterRefused(EncounterRefusal.UNKNOWN_CREATURE, p.creature_id)
        if creature.dead:
            raise EncounterRefused(EncounterRefusal.CREATURE_DOWN, p.creature_id)
        if p.creature_id in seen:
            raise EncounterRefused(EncounterRefusal.DUPLICATE_PLACEMENT, p.creature_id)
        seen.add(p.creature_id)
    for spawn in setup.monsters:
        if spawn.monster not in monsters:
            raise EncounterRefused(EncounterRefusal.UNKNOWN_MONSTER, spawn.monster)


def _spawn_id(taken: set[str], monster: str) -> str:
    n = 1
    while f"{monster}-{n}" in taken:
        n += 1
    taken.add(f"{monster}-{n}")
    return f"{monster}-{n}"


def _lettered(spawned: list[_Spawn]) -> list[_Spawn]:
    counts = Counter(c.name for c, *_ in spawned)
    seen: Counter[str] = Counter()
    out: list[_Spawn] = []
    for creature, side, zone_id, xp in spawned:
        if counts[creature.name] > 1:
            letter = ascii_uppercase[seen[creature.name] % len(ascii_uppercase)]
            seen[creature.name] += 1
            creature = creature.model_copy(update={"name": f"{creature.name} {letter}"})
        out.append((creature, side, zone_id, xp))
    return out


def roll_initiative(rng: Rng, creatures: Sequence[Creature]) -> list[InitiativeEntry]:
    entries: list[InitiativeEntry] = []
    for c in creatures:
        dex = c.abilities[Ability.DEX]
        mod = ability_modifier(dex)
        d4 = roll(INITIATIVE_DIE, rng).total
        entries.append(
            InitiativeEntry(creature_id=c.id, roll=d4, modifier=mod, total=d4 + mod, dex=dex)
        )
    return sorted(entries, key=lambda e: (-e.total, -e.dex, e.creature_id))


def party_surprise(state: GameState, surprise: SurpriseKind) -> SurpriseKind:
    """Foes met at a place the party alerted (noisy gear, a carried light) cannot be surprised."""
    world = state.world
    alerted = world.alerted is not None and world.alerted == world.current_node
    return SurpriseKind.NONE if alerted and surprise is SurpriseKind.HOSTILE else surprise


def _surprised(side: Side, surprise: SurpriseKind) -> bool:
    return (surprise is SurpriseKind.PARTY and side is Side.PARTY) or (
        surprise is SurpriseKind.HOSTILE and side is Side.HOSTILE
    )


def _offer_closed_by_fight(state: GameState, setup: EncounterSetup) -> list[AnyEvent]:
    """M29.9a T8: a fight started at a place whose offer still waits answers that offer."""
    offer = state.campaign.offer if state.campaign is not None else None
    if offer is None or offer.id == setup.offer_id or offer.node_id != state.world.current_node:
        return []
    detail = "the fight starts"
    return [OfferResolved(offer_id=offer.id, choice=OfferChoice.FIGHT, success=None, detail=detail)]


def start_encounter(
    rng: Rng, state: GameState, setup: EncounterSetup, monsters: Registry[SrdMonster]
) -> list[AnyEvent]:
    _validate(state, setup, monsters)
    closed = _offer_closed_by_fight(state, setup)
    taken = set(state.creatures)
    spawned: list[_Spawn] = []
    for spawn in setup.monsters:
        block = monsters.get(spawn.monster)
        creature = creature_from_monster(block, _spawn_id(taken, spawn.monster), name=spawn.name)
        if spawn.npc_id is not None:  # M20.5: this creature IS that world NPC
            creature = creature.model_copy(update={"npc_id": spawn.npc_id})
        if spawn.side is Side.HOSTILE:
            creature = scale_spawn(creature, state.difficulty.monster_hp * spawn.hp_scale)
        spawned.append((creature, spawn.side, spawn.zone_id, block.xp))
    spawned = _lettered(spawned)
    joined = [(state.creatures[p.creature_id], p.side, p.zone_id, 0) for p in setup.party]
    everyone = joined + spawned
    combatants: dict[str, Combatant] = {}
    surprise_events: list[AnyEvent] = []
    surprise = party_surprise(state, setup.surprise)
    for creature, side, zone_id, xp in everyone:
        surprised = _surprised(side, surprise)
        reaction = not surprised and can_take_reactions(creature)
        combatants[creature.id] = Combatant(
            creature_id=creature.id,
            side=side,
            zone_id=zone_id,
            economy=TurnEconomy(reaction=reaction),
            xp=xp,
            surprised=surprised,
        )
        if surprised:
            mark = new_condition(SURPRISED, source_id=SURPRISE_SOURCE)
            surprise_events.extend(apply_condition(creature, mark))
    encounter = Encounter(
        id=setup.encounter_id,
        zone_map=setup.zone_map.model_copy(deep=True),
        combatants=combatants,
        initiative=roll_initiative(rng, [c for c, *_ in everyone]),
        node_id=state.world.current_node,
    )
    added: list[AnyEvent] = [CreatureAdded(creature=c) for c, *_ in spawned]
    return [*closed, *added, EncounterStarted(encounter=encounter), *surprise_events]


def is_standing(state: GameState, combatant: Combatant) -> bool:
    creature = state.creatures.get(combatant.creature_id)
    if creature is None or creature.dead or creature.hp <= 0:
        return False
    return combatant.withdrawn is None


def _fled_and_up(state: GameState, combatant: Combatant) -> bool:
    creature = state.creatures.get(combatant.creature_id)
    alive = creature is not None and not creature.dead and creature.hp > 0
    return alive and combatant.withdrawn is WithdrawReason.FLED


def encounter_outcome(state: GameState) -> EncounterStatus | None:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        return None
    party = [c for c in enc.combatants.values() if c.side is Side.PARTY]
    hostile = [c for c in enc.combatants.values() if c.side is Side.HOSTILE]
    if not any(is_standing(state, c) for c in party):
        if any(_fled_and_up(state, c) for c in party):
            return EncounterStatus.FLED
        return EncounterStatus.DEFEAT
    fighting = [c for c in hostile if not befriended_by_party(state, c.creature_id)]
    if not any(is_standing(state, c) for c in fighting):
        return EncounterStatus.VICTORY
    return None


def withdraw_combatant(
    state: GameState, creature_id: str, reason: WithdrawReason
) -> list[AnyEvent]:
    enc = active_encounter(state)
    if creature_id not in enc.combatants:
        raise EncounterRefused(EncounterRefusal.NOT_IN_ENCOUNTER, creature_id)
    return [CombatantWithdrew(creature_id=creature_id, reason=reason)]


def _defeated(state: GameState, combatant: Combatant) -> bool:
    if combatant.withdrawn is WithdrawReason.SURRENDERED:
        return True
    if yielded_to_party(state, combatant.creature_id):  # M29.9a: surrendered to the party
        return True
    creature = state.creatures.get(combatant.creature_id)
    if creature is None or combatant.withdrawn is WithdrawReason.FLED:
        return False
    return creature.dead or creature.hp == 0


def defeated_hostiles(state: GameState) -> list[Combatant]:
    enc = active_encounter(state)
    hostile = [c for c in enc.combatants.values() if c.side is Side.HOSTILE]
    return [c for c in hostile if _defeated(state, c)]


def kill_xp(state: GameState) -> int:
    return sum(c.xp for c in defeated_hostiles(state))


def _xp_recipients(state: GameState, enc: Encounter) -> list[Creature]:
    found: list[Creature] = []
    for cid in sorted(enc.combatants):
        creature = state.creatures.get(cid)
        if creature is None or creature.dead or creature.kind is not CreatureKind.PC:
            continue
        if enc.combatants[cid].side is Side.PARTY and creature.pc is not None:
            found.append(creature)
    return found


def end_encounter(state: GameState, status: EncounterStatus) -> list[AnyEvent]:
    enc = active_encounter(state)
    if status is EncounterStatus.ACTIVE:
        raise EncounterRefused(EncounterRefusal.INVALID_STATUS, "an ending needs a final status")
    total = kill_xp(state)
    recipients = _xp_recipients(state, enc)
    each = total // len(recipients) if recipients else 0
    ended = EncounterEnded(
        status=status,
        xp_total=total,
        xp_each=each,
        recipients=tuple(c.id for c in recipients),
    )
    events: list[AnyEvent] = [ended, *combat_end_events(state)]
    if each:
        for creature in recipients:
            events.extend(gain_xp(creature, each))
    return events
