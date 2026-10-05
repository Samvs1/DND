"""Domain events: the ONLY way game state changes (SPEC 2.5).

Rules and AI code return events; `aidm.session.reducer.apply` applies them. Every event is a small
frozen pydantic model with a `type` literal tag; `Event` is their discriminated union.

Design rules (binding for every new event):
- Events carry RESOLVED results, not requests. E.g. `HpChanged` carries both the `delta` (for audit
  and narration) and the resulting `new_hp` (authoritative for replay). The reducer never rolls
  dice, reads data or re-derives rules; replay is plain assignment, so it is trivially exact.
- `seq` is NOT part of an event payload. The session wraps persisted events in
  `LoggedEvent(seq, event)` where `seq == state.event_count` before the event is applied (0-based).
- New fields need defaults; renamed/removed tags need a migration. Old logs must keep replaying.
- Add the class to `AnyEvent` and handle it in the reducer `match` (pyright enforces this via
  `assert_never`).

Public API:
- Events: `CreatureAdded`, `CreatureRemoved`, `HpChanged`, `TempHpSet`, `ConditionApplied`,
  `ConditionRemoved`, `DeathSaveRolled`, `Stabilized`, `CreatureDied`, `DiceRolled`,
  `CheckResolved`, `DamageTaken`, `DeathSavesSet`, `ConditionTicked`, `ConcentrationStarted`,
  `ConcentrationEnded`, `ResourceSet`, `ResourceRemoved`, `CampSuppliesChanged`,
  `ShortRestTaken`, `LongRestTaken`, `XpGained`, `LevelGained`, `SpellbookChanged`,
  `GoldChanged`, `InventoryChanged`, and the encounter events of `aidm.models.encounter_events`
  (`EncounterStarted`, `TurnStarted`, `TurnEnded`, `EconomyChanged`, `CombatantWithdrew`,
  `EncounterEnded`), and the combat events of `aidm.models.combat_events` (`AttackRolled`,
  `CombatantMoved`, `SpellCast`, `ZoneSurfaceAdded`, `ZoneSurfaceRemoved`, `ZoneSurfaceTicked`,
  `CreatureRevived`, `MonsterActionUsed`), and the world events of `aidm.models.world_events`.
- `AnyEvent` (plain union), `Event` (union annotated with the `type` discriminator),
  `EVENT_TYPES` (every event class, derived from the union), `event_adapter` (`TypeAdapter`
  for validate/dump of `Event`).
- `LoggedEvent(seq, event)`: the persisted envelope (events.jsonl line).
"""

from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from aidm.models import world_events as we
from aidm.models.abilities import Ability, Skill
from aidm.models.character import PcData
from aidm.models.checks import CheckResult
from aidm.models.combat_events import (
    AttackRolled,
    CombatantMoved,
    CreatureRevived,
    MonsterActionUsed,
    SpellCast,
    ZoneSurfaceAdded,
    ZoneSurfaceRemoved,
    ZoneSurfaceTicked,
)
from aidm.models.conditions import Concentration
from aidm.models.damage import DamagePart, DamageType
from aidm.models.dice import D20Roll, Roll
from aidm.models.encounter_events import (
    CombatantWithdrew,
    EconomyChanged,
    EncounterEnded,
    EncounterStarted,
    TurnEnded,
    TurnStarted,
)
from aidm.models.state import ActiveCondition, Creature, Resource


class _EventBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CreatureAdded(_EventBase):
    """Register a creature (full snapshot). Its id must be new."""

    type: Literal["creature_added"] = "creature_added"
    creature: Creature


class CreatureRemoved(_EventBase):
    """Remove a creature from play entirely (despawn, fled the map). Death is `CreatureDied`."""

    type: Literal["creature_removed"] = "creature_removed"
    creature_id: str


class HpChanged(_EventBase):
    """Hit points changed by `delta`; `new_hp` is the authoritative result (already clamped)."""

    type: Literal["hp_changed"] = "hp_changed"
    creature_id: str
    delta: int
    new_hp: int = Field(ge=0)


class TempHpSet(_EventBase):
    """Temporary hit points become exactly `temp_hp` (they never stack; 0 clears them)."""

    type: Literal["temp_hp_set"] = "temp_hp_set"
    creature_id: str
    temp_hp: int = Field(ge=0)


class ConditionApplied(_EventBase):
    """Add a condition; replaces an existing instance with the same name and source."""

    type: Literal["condition_applied"] = "condition_applied"
    creature_id: str
    condition: ActiveCondition


class ConditionRemoved(_EventBase):
    """Remove instances of `name`; only those from `source_id` when it is given.

    With `exact_source=True` only the instance whose source equals `source_id` (None included) is
    removed: duration expiry and save-ends remove exactly one instance.
    """

    type: Literal["condition_removed"] = "condition_removed"
    creature_id: str
    name: str
    source_id: str | None = None
    exact_source: bool = False


class ConditionTicked(_EventBase):
    """The (name, source_id) instance's ROUNDS duration counted down to `rounds_left` (>= 1)."""

    type: Literal["condition_ticked"] = "condition_ticked"
    creature_id: str
    name: str
    source_id: str | None = None
    rounds_left: int = Field(ge=1)


class ConcentrationStarted(_EventBase):
    """The creature now concentrates on `concentration` (any previous one already ended)."""

    type: Literal["concentration_started"] = "concentration_started"
    creature_id: str
    concentration: Concentration


class ConcentrationEnded(_EventBase):
    """The creature's concentration ended; its linked conditions were removed by earlier events."""

    type: Literal["concentration_ended"] = "concentration_ended"
    creature_id: str
    spell_id: str
    reason: str = ""


class DeathSaveRolled(_EventBase):
    """A death saving throw and the resulting success/failure counters."""

    type: Literal["death_save_rolled"] = "death_save_rolled"
    creature_id: str
    roll: D20Roll
    successes: int = Field(ge=0, le=3)
    failures: int = Field(ge=0, le=3)


class Stabilized(_EventBase):
    """The creature is stable: `stable=True` and both death save counters reset to 0."""

    type: Literal["stabilized"] = "stabilized"
    creature_id: str


class CreatureDied(_EventBase):
    """The creature is dead (`dead=True`, `stable=False`). It stays in state for the narrator."""

    type: Literal["creature_died"] = "creature_died"
    creature_id: str


class DiceRolled(_EventBase):
    """Pure log event (dice tray, audit). Changes nothing but `GameState.event_count`."""

    type: Literal["dice_rolled"] = "dice_rolled"
    roll: Roll
    roller_id: str | None = None
    label: str = ""


class CheckResolved(_EventBase):
    """Pure log event: an ability check, skill check or saving throw and its outcome.

    Rules return a `CheckResult`; whoever asked for the test (tool executor, spell interpreter)
    logs it with this event so the dice tray, narrator and audit see the d20 and the DC. The
    consequences of the test are separate events. Changes nothing but `GameState.event_count`.
    """

    type: Literal["check_resolved"] = "check_resolved"
    creature_id: str
    result: CheckResult
    reason: str = ""


class DamageTaken(_EventBase):
    """Pure log event: one hit/source of damage resolved by `rules.damage.resolve_damage`.

    `parts` holds each typed packet after immunity/resistance/vulnerability; `total` is their sum
    (the damage TAKEN, before temp HP absorb it): the concentration hook (M1.5) uses it for the
    Constitution save DC. `temp_absorbed` and `hp_lost` split it; the state changes themselves are
    the `TempHpSet` / `HpChanged` events that follow. Changes nothing but `event_count`.
    """

    type: Literal["damage_taken"] = "damage_taken"
    creature_id: str
    parts: tuple[DamagePart, ...] = ()
    total: int = Field(ge=0)
    temp_absorbed: int = Field(default=0, ge=0)
    hp_lost: int = Field(default=0, ge=0)
    crit: bool = False
    source_id: str | None = None


class DeathSavesSet(_EventBase):
    """Death-save state becomes exactly these values (damage at 0 HP, healed from 0 HP)."""

    type: Literal["death_saves_set"] = "death_saves_set"
    creature_id: str
    successes: int = Field(default=0, ge=0, le=3)
    failures: int = Field(default=0, ge=0, le=3)
    stable: bool = False


class ResourceSet(_EventBase):
    """The creature's resource `key` becomes exactly `resource` (defined, spent or restored)."""

    type: Literal["resource_set"] = "resource_set"
    creature_id: str
    key: str = Field(min_length=1)
    resource: Resource


class ResourceRemoved(_EventBase):
    """The creature's resource `key` no longer exists (a pact slot pool moved to a new level)."""

    type: Literal["resource_removed"] = "resource_removed"
    creature_id: str
    key: str = Field(min_length=1)


class CampSuppliesChanged(_EventBase):
    """The party supply pool changed by `delta` (loot, purchase); `camp_supplies` is the result."""

    type: Literal["camp_supplies_changed"] = "camp_supplies_changed"
    delta: int
    camp_supplies: int = Field(ge=0)


class ShortRestTaken(_EventBase):
    """The party took a short rest; `short_rests_used` is the new count since the long rest."""

    type: Literal["short_rest_taken"] = "short_rest_taken"
    short_rests_used: int = Field(ge=1)


class LongRestTaken(_EventBase):
    """The party long-rested: `supplies_spent` paid, pool is now `camp_supplies`, counter reset.

    The per-member effects (HP, resources, conditions) are the separate events that follow.
    """

    type: Literal["long_rest_taken"] = "long_rest_taken"
    supplies_spent: int = Field(ge=0)
    camp_supplies: int = Field(ge=0)


class XpGained(_EventBase):
    """The PC earned `amount` experience points; `xp` is its new total."""

    type: Literal["xp_gained"] = "xp_gained"
    creature_id: str
    amount: int = Field(ge=0)
    xp: int = Field(ge=0)


class LevelGained(_EventBase):
    """The PC gained a level: every changed sheet value, resolved (`pc` is the new PcData).

    `ac` is the AC after the ASI (None leaves it unchanged). Resource maxima (spell slots,
    feature pools) change through the `ResourceSet` / `ResourceRemoved` events that follow it.
    """

    type: Literal["level_gained"] = "level_gained"
    creature_id: str
    max_hp: int = Field(ge=1)
    hp: int = Field(ge=0)
    proficiency_bonus: int = Field(ge=0, le=10)
    abilities: dict[Ability, int]
    skill_proficiencies: list[Skill] = Field(default_factory=list[Skill])
    skill_expertise: list[Skill] = Field(default_factory=list[Skill])
    resistances: list[DamageType] = Field(default_factory=list[DamageType])
    speed: int = Field(ge=0)
    darkvision: int = Field(ge=0)
    pc: PcData
    ac: int | None = Field(default=None, ge=0)  # None keeps the current AC


class SpellbookChanged(_EventBase):
    """The PC's spellbook is now exactly `spellbook` (a scroll was copied into it)."""

    type: Literal["spellbook_changed"] = "spellbook_changed"
    creature_id: str
    spellbook: list[str]


class GoldChanged(_EventBase):
    """The PC's gold changed by `delta`; `gold` is the new amount."""

    type: Literal["gold_changed"] = "gold_changed"
    creature_id: str
    delta: int
    gold: int = Field(ge=0)


class InventoryChanged(_EventBase):
    """The PC's stack of `item` changed by `delta`; `qty` is the new count (0 removes it)."""

    type: Literal["inventory_changed"] = "inventory_changed"
    creature_id: str
    item: str = Field(min_length=1)
    delta: int
    qty: int = Field(ge=0)


type AnyEvent = (
    CreatureAdded
    | CreatureRemoved
    | HpChanged
    | TempHpSet
    | ConditionApplied
    | ConditionRemoved
    | DeathSaveRolled
    | Stabilized
    | CreatureDied
    | DiceRolled
    | CheckResolved
    | DamageTaken
    | DeathSavesSet
    | ConditionTicked
    | ConcentrationStarted
    | ConcentrationEnded
    | ResourceSet
    | ResourceRemoved
    | CampSuppliesChanged
    | ShortRestTaken
    | LongRestTaken
    | XpGained
    | LevelGained
    | SpellbookChanged
    | GoldChanged
    | InventoryChanged
    | EncounterStarted
    | TurnStarted
    | TurnEnded
    | EconomyChanged
    | CombatantWithdrew
    | EncounterEnded
    | AttackRolled
    | CombatantMoved
    | SpellCast
    | ZoneSurfaceAdded
    | ZoneSurfaceRemoved
    | ZoneSurfaceTicked
    | CreatureRevived
    | MonsterActionUsed
    | we.NpcIntroduced
    | we.FeatureIntroduced
    | we.AttitudeChanged
    | we.SecretRevealed
    | we.PartyMoved
    | we.QuestUpdated
    | we.FactRecorded
    | we.ShopOpened
    | we.HostileActPending
)

Event = Annotated[AnyEvent, Field(discriminator="type")]

EVENT_TYPES: tuple[type[BaseModel], ...] = get_args(AnyEvent.__value__)

event_adapter: TypeAdapter[AnyEvent] = TypeAdapter(Event)


class LoggedEvent(BaseModel):
    """One persisted event-log entry: `seq` is the 0-based position in the log."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int = Field(ge=0)
    event: Event
