"""The reducer: the ONLY code that mutates `GameState` (SPEC 2.5, 5).

Public API:
- `apply(state, event) -> GameState`: applies one event IN PLACE and returns the same `state`
  object (for chaining). In-place mutation is deliberate: the table actor owns its state
  exclusively, and combat sims apply many thousands of events, so copying per event is too slow.
  Callers that need the old value must `state.model_copy(deep=True)` first.
- `replay(initial, events) -> GameState`: deep-copies `initial` and applies every event in order.
  `initial` is never modified. `replay(s0, log)` must equal the live state (tested).
- `ReducerError(ValueError)` (defined in `reducer_errors`): the event does not fit the state
  (unknown creature id, duplicate id, no active encounter). This is always an engine bug: rules
  must only emit events valid for the current state. Encounter events are applied by
  `aidm.session.encounter_apply`.

Semantics: every event increments `state.event_count` (log-only events included) and then does
plain assignment of the resolved values it carries. The reducer never rolls dice, reads data or
re-derives rules, so replay is exact. Payload objects are copied on insert, so later mutation of
state never changes a logged event. Exhaustiveness: a new `AnyEvent` member without a `case` here
fails pyright via `assert_never`.
"""

from collections.abc import Iterable
from typing import assert_never

from aidm.models.character import InventoryItem, PcData
from aidm.models.combat_events import AttackRolled, CombatantMoved, SpellCast, ZoneSurfaceAdded
from aidm.models.encounter_events import (
    CombatantWithdrew,
    EconomyChanged,
    EncounterEnded,
    EncounterStarted,
    TurnEnded,
    TurnStarted,
)
from aidm.models.events import (
    AnyEvent,
    CampSuppliesChanged,
    CheckResolved,
    ConcentrationEnded,
    ConcentrationStarted,
    ConditionApplied,
    ConditionRemoved,
    ConditionTicked,
    CreatureAdded,
    CreatureDied,
    CreatureRemoved,
    DamageTaken,
    DeathSaveRolled,
    DeathSavesSet,
    DiceRolled,
    GoldChanged,
    HpChanged,
    InventoryChanged,
    LevelGained,
    LongRestTaken,
    ResourceRemoved,
    ResourceSet,
    ShortRestTaken,
    SpellbookChanged,
    Stabilized,
    TempHpSet,
    XpGained,
)
from aidm.models.state import ActiveCondition, Creature, GameState
from aidm.session.encounter_apply import apply_encounter_event
from aidm.session.reducer_errors import ReducerError


def _creature(state: GameState, creature_id: str) -> Creature:
    try:
        return state.creatures[creature_id]
    except KeyError:
        raise ReducerError(f"unknown creature id {creature_id!r}") from None


def _add_creature(state: GameState, creature: Creature) -> None:
    if creature.id in state.creatures:
        raise ReducerError(f"duplicate creature id {creature.id!r}")
    state.creatures[creature.id] = creature.model_copy(deep=True)


def _apply_condition(creature: Creature, condition: ActiveCondition) -> None:
    kept = [
        c
        for c in creature.conditions
        if (c.name, c.source_id) != (condition.name, condition.source_id)
    ]
    kept.append(condition)
    creature.conditions = kept


def _remove_condition(creature: Creature, event: ConditionRemoved) -> None:
    name, source_id = event.name, event.source_id
    if event.exact_source:
        creature.conditions = [
            c for c in creature.conditions if (c.name, c.source_id) != (name, source_id)
        ]
        return
    creature.conditions = [
        c
        for c in creature.conditions
        if c.name != name or (source_id is not None and c.source_id != source_id)
    ]


def _tick_condition(creature: Creature, event: ConditionTicked) -> None:
    key = (event.name, event.source_id)
    for i, c in enumerate(creature.conditions):
        if (c.name, c.source_id) == key and c.rounds_left is not None:
            creature.conditions[i] = c.model_copy(update={"rounds_left": event.rounds_left})
            return
    raise ReducerError(f"{creature.id!r} has no ROUNDS condition {key!r} to tick")


def _remove_resource(creature: Creature, key: str) -> None:
    if key not in creature.resources:
        raise ReducerError(f"{creature.id!r} has no resource {key!r} to remove")
    del creature.resources[key]


def _pc(creature: Creature) -> PcData:
    if creature.pc is None:
        raise ReducerError(f"{creature.id!r} is not a player character")
    return creature.pc


def _level_gained(creature: Creature, event: LevelGained) -> None:
    _pc(creature)
    creature.max_hp = event.max_hp
    creature.hp = event.hp
    creature.proficiency_bonus = event.proficiency_bonus
    creature.abilities = dict(event.abilities)
    creature.skill_proficiencies = list(event.skill_proficiencies)
    creature.skill_expertise = list(event.skill_expertise)
    creature.resistances = list(event.resistances)
    creature.speed = event.speed
    creature.darkvision = event.darkvision
    creature.pc = event.pc.model_copy(deep=True)
    if event.ac is not None:
        creature.ac = event.ac


def _set_item(pc: PcData, item: str, qty: int) -> None:
    kept = [row for row in pc.inventory if row.item != item]
    if qty > 0:
        position = next((i for i, row in enumerate(pc.inventory) if row.item == item), len(kept))
        kept.insert(position, InventoryItem(item=item, qty=qty))
    pc.inventory = kept


def _apply_pc_event(
    state: GameState, event: XpGained | SpellbookChanged | GoldChanged | InventoryChanged
) -> None:
    pc = _pc(_creature(state, event.creature_id))
    match event:
        case XpGained(xp=xp):
            pc.xp = xp
        case SpellbookChanged(spellbook=spellbook):
            pc.spellbook = list(spellbook)
        case GoldChanged(gold=gold):
            pc.gold = gold
        case InventoryChanged(item=item, qty=qty):
            _set_item(pc, item, qty)


def _apply_death_event(
    target: Creature, event: DeathSaveRolled | DeathSavesSet | Stabilized | CreatureDied
) -> None:
    match event:
        case DeathSaveRolled(successes=successes, failures=failures):
            target.death_save_successes = successes
            target.death_save_failures = failures
        case DeathSavesSet(successes=successes, failures=failures, stable=stable):
            target.death_save_successes = successes
            target.death_save_failures = failures
            target.stable = stable
        case Stabilized():
            target.stable = True
            target.death_save_successes = 0
            target.death_save_failures = 0
        case CreatureDied():
            target.dead = True
            target.stable = False


def apply(state: GameState, event: AnyEvent) -> GameState:
    match event:
        case CreatureAdded(creature=creature):
            _add_creature(state, creature)
        case CreatureRemoved(creature_id=cid):
            _creature(state, cid)
            del state.creatures[cid]
        case HpChanged(creature_id=cid, new_hp=new_hp):
            _creature(state, cid).hp = new_hp
        case TempHpSet(creature_id=cid, temp_hp=temp_hp):
            _creature(state, cid).temp_hp = temp_hp
        case ConditionApplied(creature_id=cid, condition=condition):
            _apply_condition(_creature(state, cid), condition)
        case ConditionRemoved(creature_id=cid):
            _remove_condition(_creature(state, cid), event)
        case ConditionTicked(creature_id=cid):
            _tick_condition(_creature(state, cid), event)
        case ConcentrationStarted(creature_id=cid, concentration=concentration):
            _creature(state, cid).concentrating_on = concentration
        case ConcentrationEnded(creature_id=cid):
            _creature(state, cid).concentrating_on = None
        case DeathSaveRolled() | DeathSavesSet() | Stabilized() | CreatureDied():
            _apply_death_event(_creature(state, event.creature_id), event)
        case ResourceSet(creature_id=cid, key=key, resource=resource):
            _creature(state, cid).resources[key] = resource
        case ResourceRemoved(creature_id=cid, key=key):
            _remove_resource(_creature(state, cid), key)
        case CampSuppliesChanged(camp_supplies=supplies):
            state.camp_supplies = supplies
        case ShortRestTaken(short_rests_used=used):
            state.short_rests_used = used
        case LongRestTaken(camp_supplies=supplies):
            state.camp_supplies = supplies
            state.short_rests_used = 0
        case LevelGained(creature_id=cid):
            _level_gained(_creature(state, cid), event)
        case XpGained() | SpellbookChanged() | GoldChanged() | InventoryChanged():
            _apply_pc_event(state, event)
        case (
            EncounterStarted()
            | TurnStarted()
            | TurnEnded()
            | EconomyChanged()
            | CombatantWithdrew()
            | EncounterEnded()
            | CombatantMoved()
            | ZoneSurfaceAdded()
        ):
            apply_encounter_event(state, event)
        case DiceRolled() | CheckResolved() | DamageTaken() | AttackRolled() | SpellCast():
            pass
        case _:
            assert_never(event)
    state.event_count += 1
    return state


def replay(initial: GameState, events: Iterable[AnyEvent]) -> GameState:
    state = initial.model_copy(deep=True)
    for event in events:
        apply(state, event)
    return state
