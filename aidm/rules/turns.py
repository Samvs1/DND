"""Turn flow and the BG3 action economy (SPEC 7.2: action, bonus action, movement, reaction).

Turn flow (events only; the session applies them between calls):
- `next_turn(state) -> (index, round) | None`: the next initiative entry after the active one
  whose creature still exists, is not dead and has not withdrawn. Wrapping past the last entry
  starts the next round. Dying and stable PCs keep their turns (death saves); dead creatures are
  skipped. None: nobody can take a turn.
- `begin_turn(rng, state) -> list[AnyEvent]`: opens the next turn: `TurnStarted` with a fresh
  `TurnEconomy`, then (when a new round begins) the zone surface duration ticks, the creature's
  turn-start recharges (`resources.turn_recharge_events`: Recharge 5-6 rolls, legendary
  points), the start-of-turn condition ticks (`condition_timing.turn_start_events`), the
  turn-start harms of the surfaces in the creature's zone (`rules.surfaces`), then a death
  saving throw when the creature is (still) dying (SRD: at the start of each of its turns).
  The economy reflects those consequences (a natural 20 on the death save wakes the creature
  up with its full economy; a surprised creature gets no action, bonus action, movement or
  reaction). Refused when a turn is already open or nobody can act.
- `end_turn(rng, state) -> list[AnyEvent]`: the end-of-turn ticks and save-ends rolls
  (`condition_timing.turn_end_events`) then `TurnEnded`. Refused when no turn is open.
- `fresh_economy(creature) -> TurnEconomy`: action and bonus action when conditions allow
  actions; movement = `conditions.effective_speed` (speed x the condition factor rounded down,
  plus condition speed bonuses; 0 at 0 HP); reaction
  when conditions allow reactions.

Economy spending (`EconomyRefused(reason, detail)` on invalid input, nothing is emitted, so an
invalid command never consumes anything):
- `spend_economy(state, creature_id, *, action=False, bonus_action=False, movement=0,
  reaction=False, reason="") -> list[AnyEvent]`: one validated `EconomyChanged`. Action, bonus
  action and movement need the creature's own open turn; a reaction may be spent on any turn
  (it refreshes at the start of the creature's own turn). Conditions applied mid-turn are
  re-checked (no action while incapacitated, no movement at speed 0).
- `spend_action`, `spend_bonus_action`, `spend_movement(state, cid, feet)`, `spend_reaction`:
  single-resource wrappers.
"""

from enum import StrEnum

from aidm.models.encounter import Combatant, Encounter, TurnEconomy
from aidm.models.encounter_events import EconomyChanged, TurnEnded, TurnStarted
from aidm.models.events import AnyEvent
from aidm.models.state import Creature, GameState
from aidm.rules.condition_timing import turn_end_events, turn_start_events
from aidm.rules.conditions import (
    can_take_actions,
    can_take_reactions,
    effective_speed,
    speed_multiplier,
)
from aidm.rules.death import is_dying, roll_death_save
from aidm.rules.dice import Rng
from aidm.rules.encounter import EncounterRefusal, EncounterRefused, active_encounter
from aidm.rules.projection import project_creature, project_state
from aidm.rules.resources import turn_recharge_events
from aidm.rules.surface_state import surface_round_events
from aidm.rules.surfaces import turn_start_surface_events


class EconomyRefusal(StrEnum):
    NOT_IN_ENCOUNTER = "not_in_encounter"
    NOT_YOUR_TURN = "not_your_turn"
    ACTION_USED = "action_used"
    BONUS_ACTION_USED = "bonus_action_used"
    REACTION_USED = "reaction_used"
    CANNOT_ACT = "cannot_act"
    CANNOT_REACT = "cannot_react"
    CANNOT_MOVE = "cannot_move"
    NOT_ENOUGH_MOVEMENT = "not_enough_movement"
    INVALID_AMOUNT = "invalid_amount"


class EconomyRefused(ValueError):
    """A spend the economy does not allow; `reason` says why. Nothing was consumed."""

    def __init__(self, reason: EconomyRefusal, detail: str) -> None:
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason


def _can_take_turn(state: GameState, enc: Encounter, index: int) -> bool:
    cid = enc.initiative[index].creature_id
    creature = state.creatures.get(cid)
    combatant = enc.combatants.get(cid)
    if creature is None or combatant is None:
        return False
    return not creature.dead and combatant.withdrawn is None


def next_turn(state: GameState) -> tuple[int, int] | None:
    enc = active_encounter(state)
    count = len(enc.initiative)
    for step in range(1, count + 1):
        index = enc.active_index + step
        round_no = enc.round
        if index >= count:
            index -= count
            round_no += 1
        if _can_take_turn(state, enc, index):
            return index, round_no
    return None


def fresh_economy(creature: Creature) -> TurnEconomy:
    can_act = can_take_actions(creature)
    movement = effective_speed(creature)
    return TurnEconomy(
        action=can_act,
        bonus_action=can_act,
        movement_left=movement,
        reaction=can_take_reactions(creature),
    )


def begin_turn(rng: Rng, state: GameState) -> list[AnyEvent]:
    enc = active_encounter(state)
    if enc.turn_open:
        raise EncounterRefused(EncounterRefusal.TURN_ALREADY_OPEN, str(enc.active_id()))
    upcoming = next_turn(state)
    if upcoming is None:
        raise EncounterRefused(EncounterRefusal.NO_ONE_CAN_ACT, enc.id)
    index, round_no = upcoming
    creature = state.creatures[enc.initiative[index].creature_id]
    consequences = surface_round_events(state) if round_no > enc.round else []
    consequences.extend(turn_recharge_events(rng, creature))
    consequences.extend(turn_start_events(state, creature.id))
    after = project_state(state, consequences)
    consequences.extend(turn_start_surface_events(rng, after, creature.id))
    now = project_creature(creature, consequences)
    if is_dying(creature) and is_dying(now):
        consequences.extend(roll_death_save(rng, now))
    economy = fresh_economy(project_creature(creature, consequences))
    started = TurnStarted(
        creature_id=creature.id, round=round_no, active_index=index, economy=economy
    )
    return [started, *consequences]


def end_turn(rng: Rng, state: GameState) -> list[AnyEvent]:
    enc = active_encounter(state)
    cid = enc.active_id()
    if cid is None:
        raise EncounterRefused(EncounterRefusal.NO_OPEN_TURN, enc.id)
    return [*turn_end_events(rng, state, cid), TurnEnded(creature_id=cid)]


def _spender(state: GameState, creature_id: str, own_turn: bool) -> tuple[Combatant, Creature]:
    enc = active_encounter(state)
    combatant = enc.combatants.get(creature_id)
    creature = state.creatures.get(creature_id)
    if combatant is None or creature is None:
        raise EconomyRefused(EconomyRefusal.NOT_IN_ENCOUNTER, creature_id)
    if own_turn and enc.active_id() != creature_id:
        raise EconomyRefused(EconomyRefusal.NOT_YOUR_TURN, creature_id)
    return combatant, creature


def _check_turn_costs(
    economy: TurnEconomy, creature: Creature, action: bool, bonus_action: bool, movement: int
) -> None:
    if (action or bonus_action) and not can_take_actions(creature):
        raise EconomyRefused(EconomyRefusal.CANNOT_ACT, creature.id)
    if action and not economy.action:
        raise EconomyRefused(EconomyRefusal.ACTION_USED, creature.id)
    if bonus_action and not economy.bonus_action:
        raise EconomyRefused(EconomyRefusal.BONUS_ACTION_USED, creature.id)
    if movement and speed_multiplier(creature) <= 0:
        raise EconomyRefused(EconomyRefusal.CANNOT_MOVE, creature.id)
    if movement > economy.movement_left:
        detail = f"{movement} ft wanted, {economy.movement_left} ft left"
        raise EconomyRefused(EconomyRefusal.NOT_ENOUGH_MOVEMENT, detail)


def spend_economy(
    state: GameState,
    creature_id: str,
    *,
    action: bool = False,
    bonus_action: bool = False,
    movement: int = 0,
    reaction: bool = False,
    reason: str = "",
) -> list[AnyEvent]:
    if movement < 0 or not (action or bonus_action or movement or reaction):
        raise EconomyRefused(EconomyRefusal.INVALID_AMOUNT, f"nothing valid to spend ({movement})")
    own_turn = action or bonus_action or movement > 0
    combatant, creature = _spender(state, creature_id, own_turn)
    economy = combatant.economy
    _check_turn_costs(economy, creature, action, bonus_action, movement)
    if reaction and not can_take_reactions(creature):
        raise EconomyRefused(EconomyRefusal.CANNOT_REACT, creature_id)
    if reaction and not economy.reaction:
        raise EconomyRefused(EconomyRefusal.REACTION_USED, creature_id)
    spent = economy.model_copy(
        update={
            "action": economy.action and not action,
            "bonus_action": economy.bonus_action and not bonus_action,
            "movement_left": economy.movement_left - movement,
            "reaction": economy.reaction and not reaction,
        }
    )
    return [EconomyChanged(creature_id=creature_id, economy=spent, reason=reason)]


def spend_action(state: GameState, creature_id: str, reason: str = "action") -> list[AnyEvent]:
    return spend_economy(state, creature_id, action=True, reason=reason)


def spend_bonus_action(
    state: GameState, creature_id: str, reason: str = "bonus action"
) -> list[AnyEvent]:
    return spend_economy(state, creature_id, bonus_action=True, reason=reason)


def spend_movement(
    state: GameState, creature_id: str, feet: int, reason: str = "move"
) -> list[AnyEvent]:
    if feet <= 0:
        raise EconomyRefused(EconomyRefusal.INVALID_AMOUNT, f"{feet} ft")
    return spend_economy(state, creature_id, movement=feet, reason=reason)


def spend_reaction(state: GameState, creature_id: str, reason: str = "reaction") -> list[AnyEvent]:
    return spend_economy(state, creature_id, reaction=True, reason=reason)
