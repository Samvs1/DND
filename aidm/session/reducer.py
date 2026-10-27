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
  `aidm.session.encounter_apply`, world events by `aidm.session.world_apply`, campaign events by
  `aidm.session.campaign_apply` (which also derives travel locks, DECISIONS M5.4).

Semantics: every event increments `state.event_count` (log-only events included) and then does
plain assignment of the resolved values it carries. The reducer never rolls dice, reads data or
re-derives rules, so replay is exact. Payload objects are copied on insert, so later mutation of
state never changes a logged event. Exhaustiveness: a new `AnyEvent` member without a `case` here
fails pyright via `assert_never`.
M40.4: before each event the reducer reads its story keys (`aidm.rules.story_keys`: a foe died,
a quest changed state, an item changed holder...) and after it marks `World.changed[key] = seq`,
so a story record made earlier can be told apart from the present (`aidm.rules.story_records`).
M43.3 (D1): an `ActionImpossible` is kept in `Memory.untold` until the next `NarrationRecorded`.
"""

from collections.abc import Iterable
from typing import TypeIs, assert_never

from aidm.models.character import InventoryItem, PcData
from aidm.models.combat_events import (
    AttackRolled,
    CombatantMoved,
    CreatureRevived,
    FeatureUsed,
    MonsterActionUsed,
    SpellCast,
    ZoneSurfaceAdded,
    ZoneSurfaceRemoved,
    ZoneSurfaceTicked,
)
from aidm.models.defeat import DefeatState, PartyDefeated
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
from aidm.models.impossible import ActionImpossible, LineRead
from aidm.models.memory import MAX_UNTOLD
from aidm.models.scribe import CharacterRewritten
from aidm.models.state import ActiveCondition, Creature, GameState
from aidm.rules.story_keys import quest_changes, quest_status, story_keys
from aidm.session.campaign_apply import CAMPAIGN_EVENT_TYPES, CampaignEvent, apply_campaign_event
from aidm.session.encounter_apply import apply_encounter_event
from aidm.session.reducer_errors import ReducerError
from aidm.session.world_apply import WORLD_EVENT_TYPES, WorldEvent, apply_world_event


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
        charges = next((row.charges for row in pc.inventory if row.item == item), None)
        kept.insert(position, InventoryItem(item=item, qty=qty, charges=charges))
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
    state: GameState,
    event: DeathSaveRolled | DeathSavesSet | Stabilized | CreatureDied | CreatureRevived,
) -> None:
    target = _creature(state, event.creature_id)
    _npc_fate(state, event)
    match event:
        case CreatureRevived():
            target.dead = False
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


def _npc_fate(
    state: GameState,
    event: DeathSaveRolled | DeathSavesSet | Stabilized | CreatureDied | CreatureRevived,
) -> None:
    """M20.5: a world NPC's fight creature dying (or coming back) is the NPC's own fate. Saves
    from before M20.5 carry no `npc_id`: the one NPC with exactly the creature's name."""
    if not isinstance(event, CreatureDied | CreatureRevived):
        return
    creature = state.creatures[event.creature_id]
    if creature.pc is not None:
        return
    if creature.npc_id is not None:
        npc = state.world.npcs.get(creature.npc_id)
    else:
        named = [n for n in state.world.npcs.values() if n.name == creature.name]
        npc = named[0] if len(named) == 1 else None
    if npc is not None:
        npc.dead = isinstance(event, CreatureDied)


def _apply_party_event(
    state: GameState, event: PartyDefeated | CharacterRewritten | ActionImpossible
) -> None:
    match event:
        case ActionImpossible():  # M43.3 (D1): kept for the next telling
            state.memory.untold = [*state.memory.untold, event][-MAX_UNTOLD:]
        case PartyDefeated(text=text, source=source, place=place):
            state.defeat = DefeatState(text=text, source=source, place=place)
        case CharacterRewritten(target_id=tid, hp=hp):
            # M13.1: the Scribe rewrites a fallen hero (alive, `hp`, death saves reset)
            target = _creature(state, tid)
            target.dead = False
            target.stable = False
            target.death_save_successes = 0
            target.death_save_failures = 0
            target.hp = hp


def _set_concentration(target: Creature, event: ConcentrationStarted | ConcentrationEnded) -> None:
    started = isinstance(event, ConcentrationStarted)
    target.concentrating_on = event.concentration if started else None


def _apply_rest_event(
    state: GameState, event: CampSuppliesChanged | ShortRestTaken | LongRestTaken
) -> None:
    match event:
        case CampSuppliesChanged(camp_supplies=supplies):
            state.camp_supplies = supplies
        case ShortRestTaken(short_rests_used=used):
            state.short_rests_used = used
        case LongRestTaken(camp_supplies=supplies):
            state.camp_supplies = supplies
            state.short_rests_used = 0


def _is_registry_event(event: AnyEvent) -> TypeIs[WorldEvent | CampaignEvent]:
    return isinstance(event, WORLD_EVENT_TYPES + CAMPAIGN_EVENT_TYPES)


def _apply_registry_event(state: GameState, event: WorldEvent | CampaignEvent) -> None:
    if isinstance(event, CAMPAIGN_EVENT_TYPES):
        apply_campaign_event(state, event)
    else:
        apply_world_event(state, event)


def apply(state: GameState, event: AnyEvent) -> GameState:
    seq = state.event_count
    keys = story_keys(state, event)
    quests = quest_status(state) if _is_registry_event(event) else None
    _apply(state, event)
    changed = state.world.changed
    for key in keys:
        changed[key] = seq
    if quests is not None:
        for key in quest_changes(quests, quest_status(state), state):
            changed[key] = seq
    return state


def _apply(state: GameState, event: AnyEvent) -> None:
    if _is_registry_event(event):
        _apply_registry_event(state, event)
        state.event_count += 1
        return
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
        case ConcentrationStarted() | ConcentrationEnded():
            _set_concentration(_creature(state, event.creature_id), event)
        case (
            DeathSaveRolled() | DeathSavesSet() | Stabilized() | CreatureDied() | CreatureRevived()
        ):
            _apply_death_event(state, event)
        case ResourceSet(creature_id=cid, key=key, resource=resource):
            _creature(state, cid).resources[key] = resource
        case ResourceRemoved(creature_id=cid, key=key):
            _remove_resource(_creature(state, cid), key)
        case CampSuppliesChanged() | ShortRestTaken() | LongRestTaken():
            _apply_rest_event(state, event)
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
            | ZoneSurfaceRemoved()
            | ZoneSurfaceTicked()
        ):
            apply_encounter_event(state, event)
        case DiceRolled() | CheckResolved() | DamageTaken() | LineRead():
            pass
        case AttackRolled() | SpellCast() | MonsterActionUsed() | FeatureUsed():
            pass
        case PartyDefeated() | CharacterRewritten() | ActionImpossible():
            _apply_party_event(state, event)
        case _:
            assert_never(event)
    state.event_count += 1


def replay(initial: GameState, events: Iterable[AnyEvent]) -> GameState:
    state = initial.model_copy(deep=True)
    for event in events:
        apply(state, event)
    return state
