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

M36.4: `explore_feature_events(state, actor_id, feature_id, regs, rng)` uses a feature out of a
fight with the same hook, resource and heal (no turn economy) when `usable_out_of_fight(hook)`:
a healing bonus action (Second Wind); Action Surge and the zone-aimed abilities need a fight.

Public API: `feature_action_command`, `explore_feature_events`, `usable_out_of_fight`,
`resolve_feature_id` (a short id such as `action-surge` to the full one),
`ability_spell(hook, feature_id) -> SpellDef`, `PSEUDO_SCHOOL`.
"""

from aidm.data.combat_data import CombatRegistries
from aidm.data.feature_defs import FeatureDef
from aidm.data.feature_hooks import ActiveAbilityHook, BonusActionHook, ExtraActionHook
from aidm.data.registry import Registry
from aidm.data.spell_defs import SpellDef
from aidm.models.abilities import Ability
from aidm.models.combat_events import FeatureUsed
from aidm.models.commands import FeatureActionCommand, RefusalCode
from aidm.models.dice import RollKind
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent, DiceRolled
from aidm.models.state import Creature, GameState
from aidm.rules.abilities import ability_modifier
from aidm.rules.command_checks import Actor, CommandRefused, acting, changed, spend
from aidm.rules.conditions import can_take_actions
from aidm.rules.damage import resolve_healing
from aidm.rules.dice import Rng, roll
from aidm.rules.features import (
    LEVEL_PLACEHOLDER,
    CommandHook,
    character_level,
    command_hook,
    creature_hooks,
)
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
    _not_full(me)
    economy = spend(state, me.id, bonus_action=True, reason=cmd.feature_id)
    return [changed(me.id, economy, cmd.feature_id), *_healed(me, cmd, hook, name, rng)]


def _not_full(me: Creature) -> None:
    if me.hp >= me.max_hp:
        raise CommandRefused(RefusalCode.FULL_HP, "You are already at full health.")


def _healed(
    me: Creature, cmd: FeatureActionCommand, hook: BonusActionHook, name: str, rng: Rng
) -> list[AnyEvent]:
    """The resource, the use and the heal dice on the user ("LEVEL" = character level)."""
    dice = (hook.heal or "0").replace(LEVEL_PLACEHOLDER, str(character_level(me)))
    healed = roll(dice, rng)
    return [
        *(spend_resource(me, hook.resource) if hook.resource else []),
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


def resolve_feature_id(creature: Creature, feats: Registry[FeatureDef], feature_id: str) -> str:
    """The full feature id for a short one (M32.1d X17): an exact id stays; else the one id of the
    creature's command features that starts with `feature_id + "-"` (`action-surge` for
    `action-surge-1-use`). Several or none: the id unchanged."""
    owners = {o for o, h in creature_hooks(creature, feats) if _has_command(h)}
    if feature_id in owners:
        return feature_id
    near = [o for o in owners if o.startswith(feature_id + "-")]
    return near[0] if len(near) == 1 else feature_id


def _has_command(hook: object) -> bool:
    if isinstance(hook, (ExtraActionHook, ActiveAbilityHook)):
        return True
    return isinstance(hook, BonusActionHook) and bool(hook.heal)


def feature_action_command(
    state: GameState, cmd: FeatureActionCommand, regs: CombatRegistries, rng: Rng
) -> list[AnyEvent]:
    actor = acting(state, cmd.actor_id)
    full = resolve_feature_id(actor.creature, regs.chars.features, cmd.feature_id)
    cmd = cmd.model_copy(update={"feature_id": full})
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


def usable_out_of_fight(hook: CommandHook) -> bool:
    """M36.4: a feature whose use needs no turn, zone or initiative: a healing bonus action
    (Second Wind). Action Surge (a turn's action) and the active abilities, which aim at the
    fight's zones (Turn Undead, Breath Weapon), need a fight."""
    return isinstance(hook, BonusActionHook) and bool(hook.heal)


def _explorer(state: GameState, actor_id: str) -> Creature:
    me = state.creatures.get(actor_id)
    if me is None or me.pc is None or me.dead or me.hp <= 0 or not can_take_actions(me):
        raise CommandRefused(RefusalCode.CANNOT_ACT, "You cannot act right now.")
    enc = state.encounter
    if enc is not None and enc.status is EncounterStatus.ACTIVE and actor_id in enc.combatants:
        raise CommandRefused(RefusalCode.NOT_YOUR_TURN, "In a fight, use it on your turn.")
    return me


def explore_feature_events(
    state: GameState, actor_id: str, feature_id: str, regs: CombatRegistries, rng: Rng
) -> list[AnyEvent]:
    """A feature used out of a fight (M36.4): the same hook, resource and heal as in a fight,
    with no turn economy. Refused plainly: no such feature, a spent one, one that needs a fight
    (`usable_out_of_fight`), full health."""
    me = _explorer(state, actor_id)
    feats = regs.chars.features
    full = resolve_feature_id(me, feats, feature_id)
    hook = command_hook(me, feats, full)
    if hook is None:
        raise CommandRefused(RefusalCode.NO_FEATURE, "You have no such ability to use.")
    name = feats.get(full).name
    if not isinstance(hook, BonusActionHook) or not usable_out_of_fight(hook):
        raise CommandRefused(RefusalCode.NOT_IN_COMBAT, f"{name} is only of use in a fight.")
    if hook.resource is not None and resource_left(me, hook.resource) < 1:
        raise CommandRefused(RefusalCode.ABILITY_SPENT, "That ability is spent until you rest.")
    _not_full(me)
    cmd = FeatureActionCommand(actor_id=actor_id, feature_id=full)
    return _healed(me, cmd, hook, name, rng)
