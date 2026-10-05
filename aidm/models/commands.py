"""Structured combat commands (SPEC 6.1): what the UI hotbar and the session send on a turn.

Combat turns never parse free text for standard actions; the client sends one of these models
and `aidm.rules.commands.execute_command` validates and resolves it into events. Every command
names its `actor_id` (the creature acting; the session checks the player owns it) plus its
parameters. An invalid command is refused with a `RefusalCode` and a player-facing reason and
emits nothing (nothing is consumed).

Public API:
- Commands (frozen, `type` tag): `AttackCommand(actor_id, target_id, option)` (`option` is an
  attack option key: "main_hand", "off_hand" (bonus action), "ranged", "unarmed"),
  `CastCommand(actor_id, spell_id, slot_level, target_ids, target_zone)` (`slot_level` None =
  the lowest usable slot; `target_ids` may repeat a creature for multi-target spells),
  `MoveCommand(actor_id, zone_id)` (moving to the own zone while prone = standing up),
  `DashCommand`, `DisengageCommand`, `HideCommand` (`bonus_action` True uses a feature bonus
  action such as Cunning Action), `ShoveCommand(actor_id, target_id, mode, to_zone)` (mode
  "push" needs `to_zone`, "prone" knocks the target down), `JumpCommand(actor_id, zone_id)`,
  `ThrowCommand(actor_id, target_id, item)` (`item` None = an improvised object),
  `UseItemCommand(actor_id, item, target_id)` (`target_id` None = the actor),
  `HelpCommand(actor_id, target_id)`, `DodgeCommand(actor_id)`, `EndTurnCommand(actor_id)`,
  `MonsterActionCommand(actor_id, action, target_ids, target_zone, option, slot_level)` (M3.8: a
  monster's catalog option key, `aidm.rules.monster_catalog`; `option` picks a multiattack
  routine (None = the first one valid for the targets); `target_ids` are spread round-robin
  over a multiattack's attacks; a "spell:<index>" key casts from the monster's spell kit).
- `AnyCommand` (plain union), `Command` (annotated with the `type` discriminator),
  `command_adapter` (`TypeAdapter` for validating client JSON).
- `RefusalCode`: the typed reason a command was refused (stable strings for the UI and tools).
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class RefusalCode(StrEnum):
    NOT_IN_COMBAT = "not_in_combat"
    NOT_YOUR_TURN = "not_your_turn"
    CANNOT_ACT = "cannot_act"
    NO_ACTION = "no_action"
    NO_BONUS_ACTION = "no_bonus_action"
    CANNOT_MOVE = "cannot_move"
    NOT_ENOUGH_MOVEMENT = "not_enough_movement"
    UNKNOWN_TARGET = "unknown_target"
    INVALID_TARGET = "invalid_target"
    OUT_OF_RANGE = "out_of_range"
    UNKNOWN_ZONE = "unknown_zone"
    NOT_ADJACENT = "not_adjacent"
    UNKNOWN_OPTION = "unknown_option"
    NO_FEATURE = "no_feature"
    UNKNOWN_ITEM = "unknown_item"
    ITEM_NOT_OWNED = "item_not_owned"
    FULL_HP = "full_hp"
    TOO_LARGE = "too_large"
    ALREADY_HIDDEN = "already_hidden"
    UNKNOWN_SPELL = "unknown_spell"
    SPELL_NOT_READY = "spell_not_ready"
    NO_SLOT = "no_slot"
    BAD_TARGETS = "bad_targets"
    NOT_A_CASTER = "not_a_caster"
    NOT_A_MONSTER = "not_a_monster"
    ABILITY_SPENT = "ability_spent"
    NO_LEGENDARY = "no_legendary_action"


class _Command(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    actor_id: str = Field(min_length=1)


class AttackCommand(_Command):
    type: Literal["attack"] = "attack"
    target_id: str = Field(min_length=1)
    option: str = Field(default="main_hand", min_length=1)


class CastCommand(_Command):
    type: Literal["cast"] = "cast"
    spell_id: str = Field(min_length=1)
    slot_level: int | None = Field(default=None, ge=1, le=9)
    target_ids: tuple[str, ...] = ()
    target_zone: str | None = None


class MoveCommand(_Command):
    type: Literal["move"] = "move"
    zone_id: str = Field(min_length=1)


class DashCommand(_Command):
    type: Literal["dash"] = "dash"
    bonus_action: bool = False


class DisengageCommand(_Command):
    type: Literal["disengage"] = "disengage"
    bonus_action: bool = False


class HideCommand(_Command):
    type: Literal["hide"] = "hide"
    bonus_action: bool = False


class ShoveCommand(_Command):
    type: Literal["shove"] = "shove"
    target_id: str = Field(min_length=1)
    mode: Literal["push", "prone"] = "prone"
    to_zone: str | None = None


class JumpCommand(_Command):
    type: Literal["jump"] = "jump"
    zone_id: str = Field(min_length=1)


class ThrowCommand(_Command):
    type: Literal["throw"] = "throw"
    target_id: str = Field(min_length=1)
    item: str | None = None


class UseItemCommand(_Command):
    type: Literal["use_item"] = "use_item"
    item: str = Field(min_length=1)
    target_id: str | None = None


class HelpCommand(_Command):
    type: Literal["help"] = "help"
    target_id: str = Field(min_length=1)


class DodgeCommand(_Command):
    type: Literal["dodge"] = "dodge"


class EndTurnCommand(_Command):
    type: Literal["end_turn"] = "end_turn"


class MonsterActionCommand(_Command):
    type: Literal["monster_action"] = "monster_action"
    action: str = Field(min_length=1)
    target_ids: tuple[str, ...] = ()
    target_zone: str | None = None
    option: int | None = Field(default=None, ge=0)
    slot_level: int | None = Field(default=None, ge=1, le=9)


type AnyCommand = (
    AttackCommand
    | CastCommand
    | MoveCommand
    | DashCommand
    | DisengageCommand
    | HideCommand
    | ShoveCommand
    | JumpCommand
    | ThrowCommand
    | UseItemCommand
    | HelpCommand
    | DodgeCommand
    | EndTurnCommand
    | MonsterActionCommand
)

Command = Annotated[AnyCommand, Field(discriminator="type")]

command_adapter: TypeAdapter[AnyCommand] = TypeAdapter(Command)
