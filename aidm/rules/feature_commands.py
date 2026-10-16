"""Class and race feature actions (M7.5b, SPEC 7.2 / 7.4): ONE executor driven by the feature hooks.

`feature_action_command(state, cmd, regs, rng)` runs a `FeatureActionCommand` (dispatched by
`rules.commands.execute_command`) on the hook `rules.features.command_hook` finds for
`cmd.feature_id`. It branches on the hook KIND only, never on a feature id:
- `bonus_action` with `heal` (Second Wind): the bonus action and the resource, then the heal
  dice on the user ("LEVEL" = character level). Refused at full HP (nothing spent).
- `extra_action` (Action Surge): free; the resource, then the action is ready again (attacks
  left over from the first Attack action are kept). Refused while the action is still unused.
- `active_ability` (Breath Weapon, Turn Undead): the hook's pseudo spell (range, targeting,
  effects) through `spell_targets.resolve_targets` and `spells.run_cast`, save DC 8 +
  proficiency + the `dc_ability` modifier; spends the action or the bonus action. An area with
  nobody in it is refused (the use would be wasted).
Everything is validated before any event, so a refusal consumes nothing: the actor's open turn,
the feature at its level (NO_FEATURE), its resource (ABILITY_SPENT), the economy and targets.
Events: `EconomyChanged` (Action Surge: the restored action), the resource `ResourceSet`,
`FeatureUsed`, then the effect events.

Public API: `feature_action_command`, `ability_spell(hook, feature_id) -> SpellDef`,
`PSEUDO_SCHOOL`.
"""

from aidm.data.combat_data import CombatRegistries
from aidm.data.feature_hooks import ActiveAbilityHook, BonusActionHook, ExtraActionHook
from aidm.data.spell_defs import SpellDef
from aidm.models.abilities import Ability
from aidm.models.combat_events import FeatureUsed
from aidm.models.commands import FeatureActionCommand, RefusalCode
from aidm.models.dice import RollKind
from aidm.models.events import AnyEvent, DiceRolled
from aidm.models.state import GameState
from aidm.rules.abilities import ability_modifier
from aidm.rules.command_checks import Actor, CommandRefused, acting, changed, spend
from aidm.rules.conditions import can_take_actions
from aidm.rules.damage import resolve_healing
from aidm.rules.dice import Rng, roll
from aidm.rules.features import LEVEL_PLACEHOLDER, character_level, command_hook
from aidm.rules.projection import project_state
from aidm.rules.resources import resource_left, spend_resource
from aidm.rules.spell_context import CastContext
from aidm.rules.spell_targets import CasterNumbers, resolve_targets
from aidm.rules.spells import run_cast

PSEUDO_SCHOOL = "feature"
BASE_DC = 8


def ability_spell(hook: ActiveAbilityHook, feature_id: str) -> SpellDef:
    return SpellDef(
        index=feature_id,
        level=0,
        school=PSEUDO_SCHOOL,
        classes=(PSEUDO_SCHOOL,),
        range=hook.range,
        targeting=hook.targeting,
        effects=hook.effects,
    )


def _self_only(cmd: FeatureActionCommand) -> None:
    if any(t != cmd.actor_id for t in cmd.target_ids) or cmd.target_zone is not None:
        raise CommandRefused(RefusalCode.BAD_TARGETS, "That ability only affects you.")


def _used(cmd: FeatureActionCommand, name: str, targets: tuple[str, ...] = ()) -> FeatureUsed:
    return FeatureUsed(
        creature_id=cmd.actor_id,
        feature=cmd.feature_id,
        name=name,
        target_ids=targets,
        target_zone=cmd.target_zone,
    )


def _paid(actor: Actor, resource: str | None) -> list[AnyEvent]:
    return spend_resource(actor.creature, resource) if resource else []


def _heal(
    state: GameState,
    actor: Actor,
    cmd: FeatureActionCommand,
    hook: BonusActionHook,
    name: str,
    rng: Rng,
) -> list[AnyEvent]:
    me = actor.creature
    _self_only(cmd)
    if me.hp >= me.max_hp:
        raise CommandRefused(RefusalCode.FULL_HP, "You are already at full health.")
    economy = spend(state, me.id, bonus_action=True, reason=cmd.feature_id)
    dice = (hook.heal or "0").replace(LEVEL_PLACEHOLDER, str(character_level(me)))
    healed = roll(dice, rng)
    return [
        changed(me.id, economy, cmd.feature_id),
        *_paid(actor, hook.resource),
        _used(cmd, name, (me.id,)),
        DiceRolled(roll=healed, roller_id=me.id, label=name, kind=RollKind.HEAL, target_id=me.id),
        *resolve_healing(me, max(0, healed.total)),
    ]


def _surge(
    actor: Actor, cmd: FeatureActionCommand, hook: ExtraActionHook, name: str
) -> list[AnyEvent]:
    _self_only(cmd)
    if not can_take_actions(actor.creature):
        raise CommandRefused(RefusalCode.CANNOT_ACT, "You cannot act right now.")
    economy = actor.combatant.economy
    if economy.action:
        raise CommandRefused(RefusalCode.ACTION_UNUSED, "You still have your action: use it first.")
    restored = economy.model_copy(update={"action": True})
    return [
        changed(cmd.actor_id, restored, cmd.feature_id),
        *_paid(actor, hook.resource),
        _used(cmd, name),
    ]


def _ability(
    state: GameState,
    actor: Actor,
    cmd: FeatureActionCommand,
    hook: ActiveAbilityHook,
    regs: CombatRegistries,
    rng: Rng,
) -> list[AnyEvent]:
    me = actor.creature
    spell = ability_spell(hook, cmd.feature_id)
    level = character_level(me)
    targets = resolve_targets(state, me.id, spell, 0, level, cmd.target_ids, cmd.target_zone)
    if not targets.instances:
        raise CommandRefused(RefusalCode.BAD_TARGETS, f"No one there for {hook.name} to affect.")
    bonus = hook.activation == "bonus_action"
    economy = spend(state, me.id, action=not bonus, bonus_action=bonus, reason=cmd.feature_id)
    head = [
        changed(me.id, economy, cmd.feature_id),
        *_paid(actor, hook.resource),
        _used(cmd, hook.name, tuple(dict.fromkeys(targets.instances))),
    ]
    dc = BASE_DC + me.proficiency_bonus + ability_modifier(me.abilities[Ability(hook.dc_ability)])
    ctx = CastContext(
        rng=rng,
        spell=spell,
        caster_id=me.id,
        cast_level=0,
        numbers=CasterNumbers(save_dc=dc, attack_bonus=0, modifier=0),
        char_level=level,
        feats=regs.chars.features,
        state=project_state(state, head),
        name=hook.name,
        target_zone=targets.zone,
        magical=hook.magical,
        events=list(head),
    )
    return run_cast(ctx, targets)


def feature_action_command(
    state: GameState, cmd: FeatureActionCommand, regs: CombatRegistries, rng: Rng
) -> list[AnyEvent]:
    actor = acting(state, cmd.actor_id)
    hook = command_hook(actor.creature, regs.chars.features, cmd.feature_id)
    if hook is None:
        raise CommandRefused(RefusalCode.NO_FEATURE, "You have no such ability to use.")
    if hook.resource is not None and resource_left(actor.creature, hook.resource) < 1:
        raise CommandRefused(RefusalCode.ABILITY_SPENT, "That ability is spent until you rest.")
    name = regs.chars.features.get(cmd.feature_id).name
    if isinstance(hook, BonusActionHook):
        return _heal(state, actor, cmd, hook, name, rng)
    if isinstance(hook, ExtraActionHook):
        return _surge(actor, cmd, hook, name)
    return _ability(state, actor, cmd, hook, regs, rng)
