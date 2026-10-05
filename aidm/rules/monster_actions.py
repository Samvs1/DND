"""Monster actions (M3.8): the options of `rules.monster_catalog` executed through the same paths
as player characters (THE attack path, THE spell effect interpreter, the economy).

`monster_action_command(state, cmd, regs, rng)` runs a `MonsterActionCommand` (dispatched by
`rules.commands.execute_command`). Everything is validated before any event (nothing is
consumed by a refusal): the monster's open turn, a creature with a stat block, a known option,
its resource ready (Recharge 5-6, per day), valid targets in range (every attack of a
multiattack), and the unspent action.
- "attack": one target; the melee profile when it reaches, else the ranged one. On a hit the
  option's `on_hit` riders (a pseudo spell, DC `dc`) run on the target unless it is down or one
  of its tags (`monster_stats.creature_tags`) is in `exempt`.
- "save": the pseudo spell's targets (`spell_targets.resolve_targets`: own zone, a chosen zone
  in reach, or one creature) and `spells.run_cast`, not magical (no Magic Resistance).
- "multiattack": costs the action ONCE. `option` picks a routine; None picks the first routine
  whose every attack reaches its target. `target_ids` are dealt round-robin to the attacks; if a
  target drops during the sequence, its remaining attacks go to the next listed target still
  standing and in reach (else they are lost). Each attack is the attack option's own strike.
- "spell:<index>": delegated to `spells.cast_command` (the monster's kit numbers and slots).
Events: `EconomyChanged`, the resource spend, `MonsterActionUsed`, then the attack and effect
events.

Public API: `monster_action_command`, `monster_catalog_of(creature, regs) -> MonsterCatalog`
(NOT_A_MONSTER without a stat block; the AI reads options from it), and for
`rules.monster_legendary`: `MonsterPlan`, `plan_monster_option(state, actor, catalog, option,
cmd, regs) -> MonsterPlan` (all target validation) and `run_monster_option(rng, state, actor_id,
option, plan, regs, paid, *, legendary=False)` (the `MonsterActionUsed` log after `paid`, then the
option's events).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from aidm.data.combat_data import CombatRegistries
from aidm.data.spell_defs import SpellDef
from aidm.models.combat import AttackProfile
from aidm.models.combat_events import MonsterActionUsed
from aidm.models.commands import CastCommand, MonsterActionCommand, RefusalCode
from aidm.models.events import AnyEvent
from aidm.models.state import Creature, GameState
from aidm.rules.attacks import resolve_attack
from aidm.rules.combat_actions import check_attack_target
from aidm.rules.command_checks import Actor, CommandRefused, acting, changed, spend
from aidm.rules.dice import Rng
from aidm.rules.monster_catalog import (
    SPELL_PREFIX,
    MonsterCatalog,
    MonsterOption,
    MultiattackStep,
    StepMode,
    monster_catalog,
)
from aidm.rules.monster_stats import creature_tags
from aidm.rules.projection import project_state
from aidm.rules.resources import resource_left, spend_resource
from aidm.rules.spell_context import CastContext
from aidm.rules.spell_effects import run_effects
from aidm.rules.spell_targets import CasterNumbers, SpellTargets, resolve_targets
from aidm.rules.spells import cast_command, run_cast


@dataclass(frozen=True)
class _Strike:
    option: MonsterOption
    profile: AttackProfile
    target_id: str


@dataclass(frozen=True)
class MonsterPlan:
    strikes: tuple[_Strike, ...] = ()
    targets: SpellTargets | None = None
    pool: tuple[str, ...] = ()


def _refuse(code: RefusalCode, reason: str) -> CommandRefused:
    return CommandRefused(code, reason)


def monster_catalog_of(creature: Creature, regs: CombatRegistries) -> MonsterCatalog:
    block = regs.monsters.find(creature.monster_index) if creature.monster_index else None
    if block is None:
        raise _refuse(RefusalCode.NOT_A_MONSTER, "Only monsters use stat block actions.")
    return monster_catalog(block, regs.monster_overlay, regs.spells)


def _profiles(option: MonsterOption, mode: StepMode) -> list[AttackProfile]:
    both = [p for p in (option.melee, option.ranged) if p is not None]
    if mode == "any":
        return both
    return [p for p in both if p.ranged == (mode == "ranged")] or both


def _profile_for(
    state: GameState,
    actor: Actor,
    option: MonsterOption,
    target_id: str,
    mode: StepMode,
    regs: CombatRegistries,
) -> AttackProfile:
    error = _refuse(RefusalCode.UNKNOWN_OPTION, "You have no such attack.")
    for profile in _profiles(option, mode):
        try:
            check_attack_target(state, actor, target_id, profile, regs)
        except CommandRefused as refused:
            error = refused
            continue
        return profile
    raise error


def _routine_plan(
    state: GameState,
    actor: Actor,
    catalog: MonsterCatalog,
    routine: Sequence[MultiattackStep],
    target_ids: Sequence[str],
    regs: CombatRegistries,
) -> tuple[_Strike, ...]:
    strikes: list[_Strike] = []
    for i, step in enumerate(routine):
        option = catalog.option(step.action)
        if option is None:
            raise _refuse(RefusalCode.UNKNOWN_OPTION, "You have no such attack.")
        target = target_ids[i % len(target_ids)]
        strikes.append(
            _Strike(option, _profile_for(state, actor, option, target, step.mode, regs), target)
        )
    return tuple(strikes)


def _multi_plan(
    state: GameState,
    actor: Actor,
    catalog: MonsterCatalog,
    option: MonsterOption,
    target_ids: Sequence[str],
    choice: int | None,
    regs: CombatRegistries,
) -> tuple[_Strike, ...]:
    routines = list(option.routines)
    if choice is not None:
        if choice >= len(routines):
            raise _refuse(RefusalCode.UNKNOWN_OPTION, "There is no such attack routine.")
        routines = [routines[choice]]
    errors: list[CommandRefused] = []
    for routine in routines:
        try:
            return _routine_plan(state, actor, catalog, routine, target_ids, regs)
        except CommandRefused as refused:
            errors.append(refused)
    raise errors[0]


def plan_monster_option(
    state: GameState,
    actor: Actor,
    catalog: MonsterCatalog,
    option: MonsterOption,
    cmd: MonsterActionCommand,
    regs: CombatRegistries,
) -> MonsterPlan:
    targets = cmd.target_ids
    if option.shape == "save" and option.save is not None:
        cid = actor.creature.id
        chosen = resolve_targets(state, cid, option.save, 0, 1, targets, cmd.target_zone)
        return MonsterPlan(targets=chosen)
    if not targets:
        raise _refuse(RefusalCode.BAD_TARGETS, "Choose a target.")
    if option.shape == "multiattack":
        strikes = _multi_plan(state, actor, catalog, option, targets, cmd.option, regs)
        return MonsterPlan(strikes=strikes, pool=tuple(dict.fromkeys(targets)))
    if option.shape != "attack" or len(targets) != 1:
        raise _refuse(RefusalCode.BAD_TARGETS, "Choose one target.")
    profile = _profile_for(state, actor, option, targets[0], "any", regs)
    return MonsterPlan(strikes=(_Strike(option, profile, targets[0]),), pool=targets)


def _context(
    rng: Rng,
    state: GameState,
    actor_id: str,
    spell: SpellDef,
    option: MonsterOption,
    regs: CombatRegistries,
    zone: str | None = None,
) -> CastContext:
    return CastContext(
        rng=rng,
        spell=spell,
        caster_id=actor_id,
        cast_level=0,
        numbers=CasterNumbers(save_dc=option.dc, attack_bonus=0, modifier=0),
        char_level=1,
        feats=regs.chars.features,
        state=state,
        name=option.name,
        target_zone=zone,
        magical=False,
    )


def _riders(
    rng: Rng, state: GameState, actor_id: str, strike: _Strike, regs: CombatRegistries
) -> list[AnyEvent]:
    option, target = strike.option, state.creatures[strike.target_id]
    if option.on_hit is None or target.dead or target.hp == 0:
        return []
    if creature_tags(target) & set(option.exempt):
        return []
    ctx = _context(rng, state, actor_id, option.on_hit, option, regs)
    run_effects(ctx, option.on_hit.effects, strike.target_id)
    return ctx.events


def _aim(
    before: GameState,
    now: GameState,
    actor_id: str,
    strike: _Strike,
    plan: MonsterPlan,
    regs: CombatRegistries,
) -> _Strike | None:
    enc = now.encounter
    if enc is None:
        return None
    actor = Actor(enc=enc, combatant=enc.combatant(actor_id), creature=now.creatures[actor_id])
    target = now.creatures[strike.target_id]
    if not (target.dead or (target.hp == 0 and before.creatures[strike.target_id].hp > 0)):
        return strike
    mode: StepMode = "ranged" if strike.profile.ranged else "melee"
    for cid in plan.pool:
        other = now.creatures.get(cid)
        if other is None or other.dead or other.hp == 0:
            continue
        try:
            profile = _profile_for(now, actor, strike.option, cid, mode, regs)
        except CommandRefused:
            continue
        return _Strike(strike.option, profile, cid)
    return None


def _strikes(
    rng: Rng, state: GameState, actor_id: str, plan: MonsterPlan, regs: CombatRegistries
) -> list[AnyEvent]:
    events: list[AnyEvent] = []
    for planned in plan.strikes:
        now = project_state(state, events)
        strike = _aim(state, now, actor_id, planned, plan, regs)
        if strike is None:
            continue
        feats = regs.chars.features
        result = resolve_attack(rng, now, actor_id, strike.target_id, strike.profile, feats)
        events.extend(result.events)
        if result.hit:
            events.extend(_riders(rng, project_state(state, events), actor_id, strike, regs))
    return events


def _run(
    rng: Rng,
    state: GameState,
    actor_id: str,
    option: MonsterOption,
    plan: MonsterPlan,
    regs: CombatRegistries,
) -> list[AnyEvent]:
    if plan.targets is not None and option.save is not None:
        ctx = _context(rng, state, actor_id, option.save, option, regs, plan.targets.zone)
        return run_cast(ctx, plan.targets)
    return _strikes(rng, state, actor_id, plan, regs)


def _used(actor_id: str, option: MonsterOption, plan: MonsterPlan, legendary: bool) -> AnyEvent:
    chosen = plan.targets
    targets = chosen.instances if chosen is not None else tuple(s.target_id for s in plan.strikes)
    return MonsterActionUsed(
        creature_id=actor_id,
        action=option.key,
        name=option.name,
        target_ids=tuple(dict.fromkeys(targets)),
        target_zone=chosen.zone if chosen is not None else None,
        legendary=legendary,
    )


def run_monster_option(
    rng: Rng,
    state: GameState,
    actor_id: str,
    option: MonsterOption,
    plan: MonsterPlan,
    regs: CombatRegistries,
    paid: Sequence[AnyEvent],
    *,
    legendary: bool = False,
) -> list[AnyEvent]:
    head = [*paid, _used(actor_id, option, plan, legendary)]
    return [*head, *_run(rng, project_state(state, head), actor_id, option, plan, regs)]


def _ready_option(catalog: MonsterCatalog, creature: Creature, key: str) -> MonsterOption:
    option = catalog.option(key)
    if option is None or option.shape == "spell":
        raise _refuse(RefusalCode.UNKNOWN_OPTION, "You have no such action.")
    if option.resource is not None and resource_left(creature, option.resource) < 1:
        raise _refuse(RefusalCode.ABILITY_SPENT, f"{option.name} is not ready yet.")
    return option


def monster_action_command(
    state: GameState, cmd: MonsterActionCommand, regs: CombatRegistries, rng: Rng
) -> list[AnyEvent]:
    actor = acting(state, cmd.actor_id)
    if cmd.action.startswith(SPELL_PREFIX):
        cast = CastCommand(
            actor_id=cmd.actor_id,
            spell_id=cmd.action.removeprefix(SPELL_PREFIX),
            slot_level=cmd.slot_level,
            target_ids=cmd.target_ids,
            target_zone=cmd.target_zone,
        )
        return cast_command(state, cast, regs, rng)
    catalog = monster_catalog_of(actor.creature, regs)
    option = _ready_option(catalog, actor.creature, cmd.action)
    plan = plan_monster_option(state, actor, catalog, option, cmd, regs)
    economy = spend(state, cmd.actor_id, action=True, reason=option.key)
    paid = spend_resource(actor.creature, option.resource) if option.resource else []
    head = [changed(cmd.actor_id, economy, option.key), *paid]
    return run_monster_option(rng, state, cmd.actor_id, option, plan, regs, head)
