"""A chosen fight-menu step as the commands the hotbar sends (M36.4, SPEC 6.2). Pure.

`fight_step_acts(state, actor_id, entry, step, regs)` turns one step of the fight menu into the
acts `session.fight_text` already plays: a move list (`MoveCommands`), a hotbar command
(`AttackCommand`, `CastCommand`, `FeatureActionCommand`, `UseItemCommand`, `ThrowCommand`, ...),
`DrawAttack`, `SurrenderIntent` or a plain `RefusedIntent`. Engine meaning, never wording:
- a strike at a creature out of reach (the real command refuses it for range, probed on
  `menu_probe.ready_state`) walks first: the moves `rules.approach.plan_into_band` plans with the
  movement left (no Dash), then the strike; when no walk this turn reaches, a plain "out of reach
  this turn" and nothing spent. Never a swap to another weapon or to ranged (round 6 Y10);
- a stowed weapon is drawn first (`DrawAttack`), and its reach is the drawn weapon's;
- a spell or feature aimed at a zone sends `target_zone`, at creatures `target_ids`;
- `shove:push` takes the zone to push into as its second target;
- a spent action or bonus action is still sent: the rules answer it plainly.
The free answers (pack, "what now", putting out the light) are `menu_steps_scene.free_acts`.

Public API: `FightAct`, `COMMAND_TYPES` (the commands these steps send),
`fight_step_acts(state, actor_id, entry, step, regs)`, `out_of_reach(state, actor_id, target_id)`.
"""

from aidm.data.combat_data import CombatRegistries
from aidm.data.feature_hooks import ActiveAbilityHook
from aidm.models.abilities import Skill
from aidm.models.action_menu import ActionKind, MenuEntry, MenuStep
from aidm.models.commands import (
    AnyCommand,
    AttackCommand,
    CastCommand,
    DashCommand,
    DisengageCommand,
    DodgeCommand,
    EndConditionCommand,
    EndTurnCommand,
    FeatureActionCommand,
    FleeCommand,
    HelpCommand,
    HideCommand,
    JumpCommand,
    MoveCommand,
    RefusalCode,
    ShoveCommand,
    ThrowCommand,
    UseItemCommand,
)
from aidm.models.state import GameState
from aidm.models.zones import RangeBand
from aidm.rules.acts import RefusedIntent
from aidm.rules.acts_fight import DrawAttack, MoveCommands, SurrenderIntent
from aidm.rules.approach import plan_into_band, profile_band
from aidm.rules.attack_profiles import find_option
from aidm.rules.feature_commands import ability_spell
from aidm.rules.features import command_hook
from aidm.rules.menu_attacks import drawn_state
from aidm.rules.menu_probe import ready_state, refusal
from aidm.rules.spell_targets import spell_band
from aidm.rules.zones import MELEE_BAND

type FightAct = MoveCommands | AnyCommand | DrawAttack | SurrenderIntent | RefusedIntent
COMMAND_TYPES = (
    AttackCommand,
    CastCommand,
    DashCommand,
    DisengageCommand,
    DodgeCommand,
    EndConditionCommand,
    EndTurnCommand,
    FeatureActionCommand,
    FleeCommand,
    HelpCommand,
    HideCommand,
    JumpCommand,
    MoveCommand,
    ShoveCommand,
    ThrowCommand,
    UseItemCommand,
)
NO_TARGET = "Say who or where for: {label}."


def out_of_reach(state: GameState, actor_id: str, target_id: str) -> RefusedIntent:
    creature = state.creatures.get(target_id)
    name = creature.name if creature is not None else "That target"
    return RefusedIntent(actor_id, f"{name} is out of reach this turn.")


def _zones(state: GameState) -> set[str]:
    enc = state.encounter
    return {z.id for z in enc.zone_map.zones} if enc is not None else set()


def _reach_first(
    state: GameState,
    actor_id: str,
    target_id: str,
    command: AnyCommand,
    band: RangeBand,
    regs: CombatRegistries,
) -> MoveCommands | None:
    """[] when the command reaches now (or the rules refuse it for another reason, which they
    say), the moves that bring the target in reach this turn, or None (out of reach)."""
    if refusal(ready_state(state, actor_id), command, regs) is not RefusalCode.OUT_OF_RANGE:
        return []
    plan = plan_into_band(state, actor_id, target_id, band, regs)
    if plan is None or not plan.moves:
        return None
    moves: MoveCommands = [*plan.moves]
    return moves


def _approached(
    state: GameState,
    actor_id: str,
    target_id: str,
    command: AnyCommand,
    band: RangeBand,
    regs: CombatRegistries,
    act: FightAct | None = None,
) -> list[FightAct]:
    moves = _reach_first(state, actor_id, target_id, command, band, regs)
    if moves is None:
        return [out_of_reach(state, actor_id, target_id)]
    done: FightAct = act if act is not None else command
    return [moves, done] if moves else [done]


def _attack(
    state: GameState, actor_id: str, entry: MenuEntry, target: str, regs: CombatRegistries
) -> list[FightAct]:
    option = entry.option or "main_hand"
    command = AttackCommand(actor_id=actor_id, target_id=target, option=option)
    if target in entry.far:
        return [out_of_reach(state, actor_id, target)]
    strike = state
    if entry.draw is not None:
        strike = drawn_state(state, actor_id, entry.draw, regs.chars) or state
    profile = find_option(strike.creatures[actor_id], regs.chars, option)
    band = profile_band(profile) if profile is not None else MELEE_BAND
    act: FightAct = DrawAttack(entry.draw, command) if entry.draw is not None else command
    return _approached(strike, actor_id, target, command, band, regs, act)


def _aimed(
    entry: MenuEntry, step: MenuStep, state: GameState
) -> tuple[tuple[str, ...], str | None]:
    """(creature targets, zone) of a cast or feature step."""
    zones = _zones(state)
    zone = next((t for t in step.targets if t in zones), None)
    creatures = tuple(t for t in step.targets if t not in zones)[: max(1, entry.max_targets)]
    return creatures, zone


def _cast(
    state: GameState, actor_id: str, entry: MenuEntry, step: MenuStep, regs: CombatRegistries
) -> list[FightAct]:
    creatures, zone = _aimed(entry, step, state)
    spell_id = entry.spell_id or ""
    command = CastCommand(
        actor_id=actor_id,
        spell_id=spell_id,
        slot_level=entry.slot_level,
        target_ids=creatures,
        target_zone=zone,
    )
    spell = regs.spells.find(spell_id)
    if len(creatures) != 1 or spell is None:
        return [command]
    return _approached(state, actor_id, creatures[0], command, spell_band(spell), regs)


def _feature(
    state: GameState, actor_id: str, entry: MenuEntry, step: MenuStep, regs: CombatRegistries
) -> list[FightAct]:
    creatures, zone = _aimed(entry, step, state) if step.targets else ((), None)
    feature_id = entry.feature_id or ""
    command = FeatureActionCommand(
        actor_id=actor_id, feature_id=feature_id, target_ids=creatures, target_zone=zone
    )
    hook = command_hook(state.creatures[actor_id], regs.chars.features, feature_id)
    if len(creatures) != 1 or not isinstance(hook, ActiveAbilityHook):
        return [command]
    band = spell_band(ability_spell(hook, feature_id))
    return _approached(state, actor_id, creatures[0], command, band, regs)


def _gear(state: GameState, actor_id: str, entry: MenuEntry, target: str | None) -> FightAct:
    zone = target if target is not None and target in _zones(state) else None
    return UseItemCommand(
        actor_id=actor_id,
        item=entry.item or "",
        use_id=entry.use_id,
        target_id=target if zone is None else None,
        target_zone=zone,
    )


def _touch(
    state: GameState, actor_id: str, entry: MenuEntry, step: MenuStep, regs: CombatRegistries
) -> list[FightAct]:
    target = step.targets[0]
    if target in entry.far:
        return [out_of_reach(state, actor_id, target)]
    command: AnyCommand
    if entry.kind is ActionKind.HELP:
        command = HelpCommand(actor_id=actor_id, target_id=target)
    elif entry.kind is ActionKind.ITEM:
        command = UseItemCommand(actor_id=actor_id, item=entry.item or "", target_id=target)
    else:
        push = bool(entry.zone_ids)
        to_zone = next((t for t in step.targets[1:] if t in entry.zone_ids), None)
        mode = "push" if push else "prone"
        command = ShoveCommand(actor_id=actor_id, target_id=target, mode=mode, to_zone=to_zone)
    return _approached(state, actor_id, target, command, MELEE_BAND, regs)


def _standard(state: GameState, actor_id: str, entry: MenuEntry, target: str | None) -> FightAct:
    bonus = entry.cost == "bonus"
    match entry.kind:
        case ActionKind.MOVE | ActionKind.STAND:
            here = state.encounter.combatant(actor_id).zone_id if state.encounter else ""
            return [MoveCommand(actor_id=actor_id, zone_id=target or here)]
        case ActionKind.DASH:
            return DashCommand(actor_id=actor_id, bonus_action=bonus)
        case ActionKind.DISENGAGE:
            return DisengageCommand(actor_id=actor_id, bonus_action=bonus)
        case ActionKind.HIDE:
            return HideCommand(actor_id=actor_id, bonus_action=bonus)
        case ActionKind.DODGE:
            return DodgeCommand(actor_id=actor_id)
        case ActionKind.JUMP:
            return JumpCommand(actor_id=actor_id, zone_id=target or "")
        case ActionKind.END_CONDITION:
            return EndConditionCommand(actor_id=actor_id, condition=entry.condition or "")
        case ActionKind.FLEE:
            return FleeCommand(actor_id=actor_id)
        case ActionKind.SURRENDER:
            return SurrenderIntent(actor_id, Skill(entry.skill or Skill.INTIMIDATION.value))
        case ActionKind.END_TURN:
            return EndTurnCommand(actor_id=actor_id)
        case _:
            return RefusedIntent(actor_id, f"{entry.label}: not something to do in a fight.")


_AIMED = frozenset({ActionKind.ATTACK, ActionKind.THROW, ActionKind.HELP, ActionKind.SHOVE})
_AIMED_TOO = frozenset({ActionKind.ITEM, ActionKind.MOVE, ActionKind.JUMP})


def fight_step_acts(
    state: GameState, actor_id: str, entry: MenuEntry, step: MenuStep, regs: CombatRegistries
) -> list[FightAct]:
    target = step.targets[0] if step.targets else None
    if target is None and entry.kind is ActionKind.ITEM:
        target = actor_id  # a draught with no one named: the hero drinks it
    elif target is None and len(entry.target_ids) == 1:
        target = entry.target_ids[0]
    if target is not None and not step.targets:
        step = step.model_copy(update={"targets": (target,)})
    if target is None and entry.kind in _AIMED | _AIMED_TOO:
        return [RefusedIntent(actor_id, NO_TARGET.format(label=entry.label))]
    match entry.kind:
        case ActionKind.ATTACK:
            return _attack(state, actor_id, entry, target or "", regs)
        case ActionKind.THROW:
            return [ThrowCommand(actor_id=actor_id, target_id=target or "", item=entry.item)]
        case ActionKind.CAST:
            return _cast(state, actor_id, entry, step, regs)
        case ActionKind.FEATURE:
            return _feature(state, actor_id, entry, step, regs)
        case ActionKind.GEAR:
            return [_gear(state, actor_id, entry, target)]
        case ActionKind.ITEM | ActionKind.HELP | ActionKind.SHOVE:
            return _touch(state, actor_id, entry, step, regs)
        case _:
            return [_standard(state, actor_id, entry, target)]
