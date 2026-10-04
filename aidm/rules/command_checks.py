"""Shared validation for combat commands: typed refusals, the acting combatant, targets, economy.

Every check raises `CommandRefused(code, reason)` BEFORE any event exists, so an invalid
command never consumes anything (SPEC 13 v1 regression "invalid input never consumes a turn").
`reason` is player-facing wording (shown in the UI, read to the DM); `code` is a stable
`RefusalCode` for tools and tests.

Public API:
- `CommandRefused(ValueError)` with `.code` and `.reason`; `refusal_from(error)` converts an
  `EconomyRefused` / `EncounterRefused` / `ZoneError` raised by lower rules.
- `Actor(enc, combatant, creature)`; `acting(state, actor_id) -> Actor`: an active fight, the
  actor is a combatant and it is the actor's open turn.
- `combat_target(state, actor, target_id, *, allow_self=False) -> Creature`: a living,
  non-withdrawn combatant of the fight.
- `spend(state, actor_id, *, action=False, bonus_action=False, movement=0, reason) ->
  TurnEconomy`: the economy after a validated spend (no event yet: commands adjust it, then
  emit ONE `EconomyChanged`).
- `spend_action_or_feature(state, actor, feats, name, *, bonus_action) -> TurnEconomy`: the
  action, or a bonus action when a feature offers `name` as one (Cunning Action).
- `changed(actor_id, economy, reason) -> EconomyChanged`.
- `opponents(state, actor) -> list[Creature]`: standing, non-incapacitated creatures of the
  opposing side (PARTY vs HOSTILE; NEUTRAL has none).
"""

from dataclasses import dataclass

from aidm.data.feature_defs import FeatureDef
from aidm.data.registry import Registry
from aidm.models.commands import RefusalCode
from aidm.models.encounter import Combatant, Encounter, EncounterStatus, Side, TurnEconomy
from aidm.models.encounter_events import EconomyChanged
from aidm.models.features import ActionEconomy
from aidm.models.state import Creature, GameState
from aidm.rules.conditions import is_incapacitated
from aidm.rules.encounter import EncounterRefusal, EncounterRefused
from aidm.rules.features import feature_actions
from aidm.rules.turns import EconomyRefusal, EconomyRefused, spend_economy
from aidm.rules.zones import ZoneError


class CommandRefused(ValueError):
    """A command the rules do not allow now. Nothing was emitted or consumed."""

    def __init__(self, code: RefusalCode, reason: str) -> None:
        super().__init__(f"{code.value}: {reason}")
        self.code = code
        self.reason = reason


_ECONOMY: dict[EconomyRefusal, tuple[RefusalCode, str]] = {
    EconomyRefusal.NOT_IN_ENCOUNTER: (RefusalCode.NOT_IN_COMBAT, "You are not in this fight."),
    EconomyRefusal.NOT_YOUR_TURN: (RefusalCode.NOT_YOUR_TURN, "It is not your turn."),
    EconomyRefusal.ACTION_USED: (RefusalCode.NO_ACTION, "You have already used your action."),
    EconomyRefusal.BONUS_ACTION_USED: (
        RefusalCode.NO_BONUS_ACTION,
        "You have already used your bonus action.",
    ),
    EconomyRefusal.CANNOT_ACT: (RefusalCode.CANNOT_ACT, "You cannot act right now."),
    EconomyRefusal.CANNOT_MOVE: (RefusalCode.CANNOT_MOVE, "You cannot move right now."),
    EconomyRefusal.NOT_ENOUGH_MOVEMENT: (
        RefusalCode.NOT_ENOUGH_MOVEMENT,
        "You do not have enough movement left.",
    ),
}
_OPPOSED = {Side.PARTY: Side.HOSTILE, Side.HOSTILE: Side.PARTY}


def refusal_from(error: EconomyRefused | EncounterRefused | ZoneError) -> CommandRefused:
    if isinstance(error, EconomyRefused):
        code, reason = _ECONOMY.get(
            error.reason, (RefusalCode.CANNOT_ACT, "You cannot do that right now.")
        )
        return CommandRefused(code, reason)
    if isinstance(error, EncounterRefused) and error.reason is EncounterRefusal.NO_OPEN_TURN:
        return CommandRefused(RefusalCode.NOT_YOUR_TURN, "It is not your turn.")
    if isinstance(error, ZoneError):
        return CommandRefused(RefusalCode.UNKNOWN_ZONE, "There is no such place here.")
    return CommandRefused(RefusalCode.NOT_IN_COMBAT, "There is no fight going on.")


@dataclass(frozen=True)
class Actor:
    enc: Encounter
    combatant: Combatant
    creature: Creature


def acting(state: GameState, actor_id: str) -> Actor:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        raise CommandRefused(RefusalCode.NOT_IN_COMBAT, "There is no fight going on.")
    combatant, creature = enc.combatants.get(actor_id), state.creatures.get(actor_id)
    if combatant is None or creature is None:
        raise CommandRefused(RefusalCode.NOT_IN_COMBAT, "You are not in this fight.")
    if enc.active_id() != actor_id:
        raise CommandRefused(RefusalCode.NOT_YOUR_TURN, "It is not your turn.")
    return Actor(enc=enc, combatant=combatant, creature=creature)


def combat_target(
    state: GameState, actor: Actor, target_id: str, *, allow_self: bool = False
) -> Creature:
    combatant, creature = actor.enc.combatants.get(target_id), state.creatures.get(target_id)
    if combatant is None or creature is None:
        raise CommandRefused(RefusalCode.UNKNOWN_TARGET, "That target is not in this fight.")
    if target_id == actor.creature.id and not allow_self:
        raise CommandRefused(RefusalCode.INVALID_TARGET, "You cannot target yourself with that.")
    if creature.dead or combatant.withdrawn is not None:
        raise CommandRefused(RefusalCode.INVALID_TARGET, f"{creature.name} is out of the fight.")
    return creature


def spend(
    state: GameState,
    actor_id: str,
    *,
    action: bool = False,
    bonus_action: bool = False,
    movement: int = 0,
    reason: str = "",
) -> TurnEconomy:
    try:
        events = spend_economy(
            state,
            actor_id,
            action=action,
            bonus_action=bonus_action,
            movement=movement,
            reason=reason,
        )
    except EconomyRefused as error:
        raise refusal_from(error) from None
    event = events[0]
    if not isinstance(event, EconomyChanged):
        raise TypeError("spend_economy must return one EconomyChanged")
    return event.economy


def spend_action_or_feature(
    state: GameState, actor: Actor, feats: Registry[FeatureDef], name: str, *, bonus_action: bool
) -> TurnEconomy:
    if not bonus_action:
        return spend(state, actor.creature.id, action=True, reason=name)
    offered = any(
        option.action == name and option.economy is ActionEconomy.BONUS_ACTION and option.available
        for option in feature_actions(actor.creature, feats)
    )
    if not offered:
        raise CommandRefused(
            RefusalCode.NO_FEATURE, f"You have no feature that lets you {name} as a bonus action."
        )
    return spend(state, actor.creature.id, bonus_action=True, reason=name)


def changed(actor_id: str, economy: TurnEconomy, reason: str) -> EconomyChanged:
    return EconomyChanged(creature_id=actor_id, economy=economy, reason=reason)


def opponents(state: GameState, actor: Actor) -> list[Creature]:
    side = _OPPOSED.get(actor.combatant.side)
    found: list[Creature] = []
    for cid, combatant in actor.enc.combatants.items():
        creature = state.creatures.get(cid)
        if creature is None or combatant.side is not side or combatant.withdrawn is not None:
            continue
        if not creature.dead and creature.hp > 0 and not is_incapacitated(creature):
            found.append(creature)
    return found
