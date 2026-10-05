"""Movement commands: move, dash, disengage, jump and shove (SPEC 7.2, 7.3; BG3 economy).

- Move: to any zone along the cheapest path (`rules.zones.zone_path`), paying its feet from
  `movement_left`. A prone creature stands up first for half its speed (SRD 5.1 "Being
  Prone"); moving to its own zone while prone just stands up.
- Dash (action, or a bonus action with a feature such as Cunning Action): movement_left grows
  by the current speed (speed x condition factor); refused at speed 0. Disengage (same costs)
  only sets the `disengaged` flag: opportunity attacks are Tier 2 (reactions).
- Jump (BG3 bonus action): to an ADJACENT zone for the edge's plain feet from movement,
  ignoring difficult terrain; not while prone.
- Shove (BG3 bonus action): a target in the same zone, at most one size larger (SRD 5.1
  "Shoving a Creature"); the target rolls the better of Athletics and Acrobatics, then the
  shover rolls Athletics and wins only by beating that total (a tie changes nothing). Success
  pushes the target into `to_zone` (adjacent to the target's zone) or knocks it prone.
- Flee (M3.10, BG3 Flee; no action): a creature that can move and shares its zone with no
  standing, non-incapacitated enemy leaves the fight: its movement drops to 0 and it withdraws
  as FLED (`rules.encounter.withdraw_combatant`; out of the turn order, no kill XP). ENGAGED
  when an enemy stands in its zone. The caller then ends the turn.

Entering a zone (move, jump, being pushed) triggers its surfaces (`rules.surfaces.
enter_zone_events`): only the destination zone counts (zones are abstract; passing through an
intermediate zone triggers nothing).

Public API: `move_command`, `dash_command`, `disengage_command`, `jump_command`,
`shove_command`, `flee_command`; each `(state, command, regs[, rng]) -> list[AnyEvent]` or
`CommandRefused`.
"""

from aidm.data.combat_data import CombatRegistries
from aidm.models.abilities import Skill
from aidm.models.character import Size
from aidm.models.combat_events import CombatantMoved
from aidm.models.commands import (
    DashCommand,
    DisengageCommand,
    FleeCommand,
    JumpCommand,
    MoveCommand,
    RefusalCode,
    ShoveCommand,
)
from aidm.models.encounter import WithdrawReason
from aidm.models.events import AnyEvent, CheckResolved, ConditionRemoved
from aidm.models.state import Creature, GameState
from aidm.models.zones import ZoneMap
from aidm.rules.checks import skill_bonus
from aidm.rules.command_checks import (
    CommandRefused,
    acting,
    changed,
    combat_target,
    opponents,
    spend,
    spend_action_or_feature,
)
from aidm.rules.condition_timing import apply_condition, new_condition
from aidm.rules.conditions import effective_speed, skill_check_with_conditions
from aidm.rules.dice import Rng
from aidm.rules.encounter import withdraw_combatant
from aidm.rules.projection import project_state
from aidm.rules.surfaces import enter_zone_events
from aidm.rules.zones import zone_path

PRONE = "prone"
_SIZES = list(Size)


def _prone(creature: Creature) -> bool:
    return any(c.name == PRONE for c in creature.conditions)


def _known_zone(zmap: ZoneMap, zone_id: str) -> None:
    if not zmap.has_zone(zone_id):
        raise CommandRefused(RefusalCode.UNKNOWN_ZONE, "There is no such place here.")


def _entered(rng: Rng, state: GameState, events: list[AnyEvent]) -> list[AnyEvent]:
    """`events` plus the surface triggers of the zone the last `CombatantMoved` entered."""
    moved = next((e for e in reversed(events) if isinstance(e, CombatantMoved)), None)
    if moved is None:
        return events
    after = project_state(state, events)
    return [*events, *enter_zone_events(rng, after, moved.creature_id, moved.from_zone)]


def move_command(
    state: GameState, cmd: MoveCommand, regs: CombatRegistries, rng: Rng
) -> list[AnyEvent]:
    actor = acting(state, cmd.actor_id)
    zmap, start = actor.enc.zone_map, actor.combatant.zone_id
    _known_zone(zmap, cmd.zone_id)
    prone = _prone(actor.creature)
    if cmd.zone_id == start and not prone:
        raise CommandRefused(RefusalCode.INVALID_TARGET, "You are already there.")
    path = zone_path(zmap, start, cmd.zone_id)
    stand = actor.creature.speed // 2 if prone else 0
    economy = spend(state, cmd.actor_id, movement=path.feet + stand, reason="move")
    events: list[AnyEvent] = [changed(cmd.actor_id, economy, "move")]
    if prone:
        events.append(ConditionRemoved(creature_id=cmd.actor_id, name=PRONE))
    if cmd.zone_id != start:
        events.append(
            CombatantMoved(
                creature_id=cmd.actor_id,
                from_zone=start,
                to_zone=cmd.zone_id,
                path=path.zones,
                feet=path.feet,
            )
        )
    return _entered(rng, state, events)


def dash_command(state: GameState, cmd: DashCommand, regs: CombatRegistries) -> list[AnyEvent]:
    actor = acting(state, cmd.actor_id)
    speed = effective_speed(actor.creature)
    if speed <= 0:
        raise CommandRefused(RefusalCode.CANNOT_MOVE, "You cannot move right now.")
    feats = regs.chars.features
    economy = spend_action_or_feature(state, actor, feats, "dash", bonus_action=cmd.bonus_action)
    economy = economy.model_copy(
        update={"movement_left": economy.movement_left + speed, "dashed": True}
    )
    return [changed(cmd.actor_id, economy, "dash")]


def disengage_command(
    state: GameState, cmd: DisengageCommand, regs: CombatRegistries
) -> list[AnyEvent]:
    actor = acting(state, cmd.actor_id)
    feats = regs.chars.features
    economy = spend_action_or_feature(
        state, actor, feats, "disengage", bonus_action=cmd.bonus_action
    )
    return [changed(cmd.actor_id, economy.model_copy(update={"disengaged": True}), "disengage")]


def _edge_feet(zmap: ZoneMap, a: str, b: str) -> int | None:
    pair = frozenset((a, b))
    return next((e.feet for e in zmap.edges if e.key() == pair), None)


def jump_command(
    state: GameState, cmd: JumpCommand, regs: CombatRegistries, rng: Rng
) -> list[AnyEvent]:
    actor = acting(state, cmd.actor_id)
    zmap, start = actor.enc.zone_map, actor.combatant.zone_id
    _known_zone(zmap, cmd.zone_id)
    feet = _edge_feet(zmap, start, cmd.zone_id) if cmd.zone_id != start else None
    if feet is None:
        raise CommandRefused(RefusalCode.NOT_ADJACENT, "You can only jump to a neighbouring area.")
    if _prone(actor.creature):
        raise CommandRefused(RefusalCode.CANNOT_MOVE, "Stand up before you jump.")
    economy = spend(state, cmd.actor_id, bonus_action=True, movement=feet, reason="jump")
    moved = CombatantMoved(
        creature_id=cmd.actor_id,
        from_zone=start,
        to_zone=cmd.zone_id,
        path=(start, cmd.zone_id),
        feet=feet,
        reason="jump",
    )
    return _entered(rng, state, [changed(cmd.actor_id, economy, "jump"), moved])


def _shove_target(state: GameState, cmd: ShoveCommand) -> tuple[Creature, str]:
    actor = acting(state, cmd.actor_id)
    target = combat_target(state, actor, cmd.target_id)
    zone = actor.enc.combatant(target.id).zone_id
    if zone != actor.combatant.zone_id:
        raise CommandRefused(RefusalCode.OUT_OF_RANGE, f"{target.name} is not close enough.")
    if _SIZES.index(target.size) > _SIZES.index(actor.creature.size) + 1:
        raise CommandRefused(RefusalCode.TOO_LARGE, f"{target.name} is too large to shove.")
    if cmd.mode == "push":
        zmap = actor.enc.zone_map
        if cmd.to_zone is None:
            raise CommandRefused(RefusalCode.UNKNOWN_ZONE, "Choose where to push them.")
        _known_zone(zmap, cmd.to_zone)
        if cmd.to_zone == zone or _edge_feet(zmap, zone, cmd.to_zone) is None:
            raise CommandRefused(
                RefusalCode.NOT_ADJACENT, "You can only push into a neighbouring area."
            )
    return target, zone


def shove_command(
    state: GameState, cmd: ShoveCommand, regs: CombatRegistries, rng: Rng
) -> list[AnyEvent]:
    target, zone = _shove_target(state, cmd)
    actor = state.creatures[cmd.actor_id]
    economy = spend(state, cmd.actor_id, bonus_action=True, reason="shove")
    skill = max((Skill.ATHLETICS, Skill.ACROBATICS), key=lambda s: skill_bonus(target, s))
    defend = skill_check_with_conditions(rng, target, skill, 0)
    attack = skill_check_with_conditions(rng, actor, Skill.ATHLETICS, max(0, defend.roll.total + 1))
    events: list[AnyEvent] = [
        changed(cmd.actor_id, economy, "shove"),
        CheckResolved(creature_id=target.id, result=defend, reason="resist shove"),
        CheckResolved(creature_id=actor.id, result=attack, reason=f"shove {target.id}"),
    ]
    if not attack.success:
        return events
    if cmd.mode == "push" and cmd.to_zone is not None:
        moved = CombatantMoved(
            creature_id=target.id, from_zone=zone, to_zone=cmd.to_zone, reason="shoved"
        )
        return _entered(rng, state, [*events, moved])
    return [*events, *apply_condition(target, new_condition(PRONE, source_id=actor.id))]


def flee_command(state: GameState, cmd: FleeCommand, regs: CombatRegistries) -> list[AnyEvent]:
    actor = acting(state, cmd.actor_id)
    if actor.creature.hp <= 0 or effective_speed(actor.creature) <= 0:
        raise CommandRefused(RefusalCode.CANNOT_MOVE, "You cannot move right now.")
    zone = actor.combatant.zone_id
    if any(actor.enc.combatant(o.id).zone_id == zone for o in opponents(state, actor)):
        raise CommandRefused(RefusalCode.ENGAGED, "Enemies are too close to slip away.")
    economy = actor.combatant.economy.model_copy(update={"movement_left": 0})
    withdrew = withdraw_combatant(state, cmd.actor_id, WithdrawReason.FLED)
    return [changed(cmd.actor_id, economy, "flee"), *withdrew]
