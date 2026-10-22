"""Action commands: attack, throw, hide, help and dodge (SPEC 6.1, 7.2).

- Attack: one attack with an option of `rules.attack_profiles.attack_options` through THE
  attack path (`rules.attacks.resolve_attack`). The first attack spends the action and leaves
  `attacks_per_action - 1` further attacks (Extra Attack) in `attacks_left`; the off-hand
  attack is a bonus action (BG3: no prior Attack action needed). Melee needs the same zone,
  ranged the weapon's range band; a charmed attacker cannot attack its charmer.
- Throw (BG3 action): a thrown weapon or any carried object (improvised 1d4) at a target in
  throw range. M27.7: the object leaves the pack, hit or miss, as in the item interpreter (and
  leaves the hand when the last one was worn); a weapon with the SRD thrown property lands at
  this place (`ItemPlaced`, picked up after the fight), anything else is gone like an
  improvised throw (docs/RULES_DECISIONS.md M27.7).
- Hide (action, or Cunning Action): Stealth against the highest passive Perception of the
  standing opponents; success applies "hidden" (ends when the creature attacks).
- Help (action): an ally in the same zone gets "helped" (advantage on its next attack or check,
  until the helper's next turn). BG3: helping a downed ally (0 HP) brings it back to 1 HP.
- Dodge (action): "dodging" until the start of the creature's next turn.
- End a condition (M27.6, action): a condition with an `end_check` in data (burning: DC 10 DEX)
  on the actor or a creature in its zone; the actor's ability check (with its conditions,
  `CheckResolved`), a success removes every instance.

Public API: `attack_command`, `throw_command`, `hide_command`, `help_command`,
`dodge_command`; each `(state, command, regs[, rng]) -> list[AnyEvent]` or `CommandRefused`;
`end_condition_command(state, cmd, rng)`.
`check_attack_target(state, actor, target_id, profile, regs)`: the target checks of an attack
(a living combatant, not the attacker's charmer, in the profile's range band); monster actions
(M3.8) use it too. The free attack that starts a fight lives in `rules.opening_strike` (M20.5).
"""

from aidm.data.combat_data import CombatRegistries
from aidm.models.abilities import Ability, Skill
from aidm.models.combat import AttackEconomy, AttackProfile
from aidm.models.commands import (
    AttackCommand,
    DodgeCommand,
    EndConditionCommand,
    HelpCommand,
    HideCommand,
    RefusalCode,
    ThrowCommand,
)
from aidm.models.encounter import TurnEconomy
from aidm.models.events import AnyEvent, CheckResolved, InventoryChanged
from aidm.models.state import Creature, GameState
from aidm.rules.attack_profiles import find_option, throw_profile
from aidm.rules.attacks import resolve_attack
from aidm.rules.checks import passive_score
from aidm.rules.command_checks import (
    Actor,
    CommandRefused,
    acting,
    changed,
    combat_target,
    opponents,
    spend,
    spend_action_or_feature,
)
from aidm.rules.condition_timing import apply_condition, new_condition, remove_condition
from aidm.rules.conditions import (
    ability_check_with_conditions,
    can_attack_target,
    can_take_actions,
    condition_def,
    skill_check_with_conditions,
)
from aidm.rules.damage import resolve_healing
from aidm.rules.dice import Rng
from aidm.rules.equipment import drop_events, release_events, unequip_events
from aidm.rules.features import attacks_per_action
from aidm.rules.hit_chance import attack_situation
from aidm.rules.item_grants import carried_qty

HIDDEN = "hidden"
HELPED = "helped"
DODGING = "dodging"


def check_attack_target(
    state: GameState, actor: Actor, target_id: str, profile: AttackProfile, regs: CombatRegistries
) -> None:
    target = combat_target(state, actor, target_id)
    if not can_attack_target(actor.creature, target):
        raise CommandRefused(
            RefusalCode.INVALID_TARGET, f"You cannot bring yourself to attack {target.name}."
        )
    sit = attack_situation(state, actor.creature.id, target_id, profile, regs.chars.features)
    if not sit.range_check.in_range:
        raise CommandRefused(RefusalCode.OUT_OF_RANGE, f"{target.name} is out of range.")


def _attack_economy(
    state: GameState, actor: Actor, profile: AttackProfile, regs: CombatRegistries
) -> TurnEconomy:
    cid, economy = actor.creature.id, actor.combatant.economy
    if profile.economy is AttackEconomy.BONUS_ACTION:
        return spend(state, cid, bonus_action=True, reason=profile.name)
    if profile.economy is AttackEconomy.ATTACK and economy.attacks_left > 0:
        if not can_take_actions(actor.creature):
            raise CommandRefused(RefusalCode.CANNOT_ACT, "You cannot act right now.")
        return economy.model_copy(update={"attacks_left": economy.attacks_left - 1})
    spent = spend(state, cid, action=True, reason=profile.name)
    if profile.economy is AttackEconomy.ACTION:
        return spent
    extra = attacks_per_action(actor.creature, regs.chars.features) - 1
    return spent.model_copy(update={"attacks_left": extra})


def _attack_with(
    state: GameState,
    actor: Actor,
    target_id: str,
    profile: AttackProfile,
    regs: CombatRegistries,
    rng: Rng,
) -> list[AnyEvent]:
    check_attack_target(state, actor, target_id, profile, regs)
    economy = _attack_economy(state, actor, profile, regs)
    feats = regs.chars.features
    result = resolve_attack(rng, state, actor.creature.id, target_id, profile, feats)
    if result.riders_used:
        used = (*economy.once_per_turn_used, *result.riders_used)
        economy = economy.model_copy(update={"once_per_turn_used": used})
    return [changed(actor.creature.id, economy, profile.name), *result.events]


def attack_command(
    state: GameState, cmd: AttackCommand, regs: CombatRegistries, rng: Rng
) -> list[AnyEvent]:
    actor = acting(state, cmd.actor_id)
    profile = find_option(actor.creature, regs.chars, cmd.option)
    if profile is None:
        raise CommandRefused(RefusalCode.UNKNOWN_OPTION, "You have no such attack.")
    return _attack_with(state, actor, cmd.target_id, profile, regs, rng)


def _owns(state: GameState, actor: Actor, item: str) -> bool:
    pc = actor.creature.pc
    if pc is None:
        return False
    slots = pc.equipped.model_dump().values()
    return item in slots or any(row.item == item and row.qty > 0 for row in pc.inventory)


def throw_command(
    state: GameState, cmd: ThrowCommand, regs: CombatRegistries, rng: Rng
) -> list[AnyEvent]:
    actor = acting(state, cmd.actor_id)
    if cmd.item is not None and not _owns(state, actor, cmd.item):
        raise CommandRefused(RefusalCode.ITEM_NOT_OWNED, "You are not carrying that.")
    weapon = regs.chars.equipment.find(cmd.item) if cmd.item else None
    profile = throw_profile(actor.creature, weapon, regs.chars)
    events = _attack_with(state, actor, cmd.target_id, profile, regs, rng)
    if cmd.item is None:
        return events
    return [*events, *_leaves_pack(state, actor.creature, cmd.item, regs)]


def _leaves_pack(
    state: GameState, creature: Creature, item: str, regs: CombatRegistries
) -> list[AnyEvent]:
    weapon = regs.chars.equipment.find(item)
    carried = carried_qty(creature, item)
    if carried < 1:  # only in a slot (an old save): it leaves the hand
        return unequip_events(creature, item, regs.chars)
    if weapon is not None and any(p.index == "thrown" for p in weapon.properties):
        return drop_events(state, creature, item, regs.chars)  # it lands here
    left = InventoryChanged(creature_id=creature.id, item=item, delta=-1, qty=carried - 1)
    return [*release_events(creature, item, regs.chars), left]


def hide_command(
    state: GameState, cmd: HideCommand, regs: CombatRegistries, rng: Rng
) -> list[AnyEvent]:
    actor = acting(state, cmd.actor_id)
    if any(c.name == HIDDEN for c in actor.creature.conditions):
        raise CommandRefused(RefusalCode.ALREADY_HIDDEN, "You are already hidden.")
    feats = regs.chars.features
    economy = spend_action_or_feature(state, actor, feats, "hide", bonus_action=cmd.bonus_action)
    watchers = opponents(state, actor)
    dc = max((passive_score(w, Skill.PERCEPTION) for w in watchers), default=0)
    result = skill_check_with_conditions(rng, actor.creature, Skill.STEALTH, dc)
    events: list[AnyEvent] = [
        changed(cmd.actor_id, economy, "hide"),
        CheckResolved(creature_id=cmd.actor_id, result=result, reason="hide"),
    ]
    if result.success:
        events.extend(
            apply_condition(actor.creature, new_condition(HIDDEN, source_id=cmd.actor_id))
        )
    return events


def help_command(state: GameState, cmd: HelpCommand, regs: CombatRegistries) -> list[AnyEvent]:
    actor = acting(state, cmd.actor_id)
    target = combat_target(state, actor, cmd.target_id)
    other = actor.enc.combatant(target.id)
    if other.side is not actor.combatant.side:
        raise CommandRefused(RefusalCode.INVALID_TARGET, f"{target.name} is not your ally.")
    if other.zone_id != actor.combatant.zone_id:
        raise CommandRefused(RefusalCode.OUT_OF_RANGE, f"{target.name} is not close enough.")
    economy = spend(state, cmd.actor_id, action=True, reason="help")
    if target.hp == 0:
        return [changed(cmd.actor_id, economy, "help"), *resolve_healing(target, 1)]
    helped = new_condition(HELPED, source_id=cmd.actor_id, tick_creature_id=cmd.actor_id)
    return [changed(cmd.actor_id, economy, "help"), *apply_condition(target, helped)]


def dodge_command(state: GameState, cmd: DodgeCommand, regs: CombatRegistries) -> list[AnyEvent]:
    actor = acting(state, cmd.actor_id)
    economy = spend(state, cmd.actor_id, action=True, reason="dodge")
    dodging = new_condition(DODGING, source_id=cmd.actor_id)
    return [changed(cmd.actor_id, economy, "dodge"), *apply_condition(actor.creature, dodging)]


def end_condition_command(state: GameState, cmd: EndConditionCommand, rng: Rng) -> list[AnyEvent]:
    actor = acting(state, cmd.actor_id)
    target_id = cmd.target_id or cmd.actor_id
    target = combat_target(state, actor, target_id, allow_self=True)
    held = any(c.name == cmd.condition for c in target.conditions)
    check = condition_def(cmd.condition).end_check if held else None
    if check is None:
        raise CommandRefused(RefusalCode.INVALID_TARGET, f"{target.name} has nothing to end.")
    if actor.enc.combatant(target_id).zone_id != actor.combatant.zone_id:
        raise CommandRefused(RefusalCode.OUT_OF_RANGE, f"{target.name} is not close enough.")
    economy = spend(state, cmd.actor_id, action=True, reason=check.label)
    result = ability_check_with_conditions(rng, actor.creature, Ability(check.ability), check.dc)
    events: list[AnyEvent] = [
        changed(cmd.actor_id, economy, check.label),
        CheckResolved(creature_id=cmd.actor_id, result=result, reason=check.label),
    ]
    if result.success:
        events.extend(remove_condition(target, cmd.condition))
    return events
