"""Thrown gear (M27.6): the `damage` effect of data/bg3/item_uses.json through THE attack path.

SRD 5.1 Adventuring Gear (Acid, Alchemist's Fire, Holy Water): "make a ranged attack against a
creature ..., treating the [item] as an improvised weapon". SRD 5.1 "Improvised Weapons": no
proficiency bonus, a thrown one has a normal range of 20 feet and a long range of 60 feet. So the
profile is the improvised throw of `rules.attack_profiles` (STR modifier, no proficiency, 20/60)
with the item's own damage (dice and type from data, no ability modifier: the gear's damage is
the liquid's, not the throw's). `rules.attacks.resolve_attack` rolls it: darkness, cover,
conditions, crits and the one damage path (resistances, immunities, temp HP) all apply.

`DamageUse.ability_mod` adds the thrower's STR modifier to the damage (the SRD improvised throw
of an item without a listed use, `item_uses.improvised_use`: 1d4 + STR bludgeoning). A flat
`dice` ("1") is a flat amount (a lit torch: SRD 5.1 Torch, 1 fire damage).

Order on a hit:
1. the item's own damage (the attack path above);
2. the effect's `condition` (alchemist's fire: burning; `apply_condition`, immunities apply);
3. `_on_hit_extras`: the substance weakness (`rules.weaknesses`, the item's `substances`).
Data adds effects, it never forbids the throw (owner, 2026-10-22): a target whose creature type
is not in `creature_types` (holy water: undead, fiend) is still attacked; the attack roll is made
and the flask is spent, but a hit deals none of the item's damage nor its condition (SRD 5.1 Holy
Water: only a fiend or undead takes the 2d6 radiant); the substance weakness still applies.
Refused (a str, nothing spent) only when impossible: no fight, no creature of this fight named,
a target the thrower may not attack, or out of range.

Public API: `throw_profile_for(creature, name, effect) -> AttackProfile`,
`effect_applies(target, effect) -> bool`, `thrown_item_events(rng, state, actor_id, target_id,
name, effect, feats, substances=()) -> list[AnyEvent] | str` (`state` already includes the
use's spent action; a str is the refusal message).
"""

from collections.abc import Sequence

from aidm.data.feature_defs import FeatureDef
from aidm.data.item_uses import DamageUse
from aidm.data.registry import Registry
from aidm.models.abilities import Ability
from aidm.models.combat import AttackEconomy, AttackProfile
from aidm.models.damage import DamageType
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent
from aidm.models.features import AttackContext
from aidm.models.state import Creature, GameState
from aidm.rules.abilities import ability_modifier
from aidm.rules.attack_profiles import IMPROVISED_RANGE, THROW_KEY, weapon_die, with_mod
from aidm.rules.attacks import AttackResult, resolve_attack, roll_attack
from aidm.rules.command_checks import changed
from aidm.rules.condition_timing import apply_condition, new_condition
from aidm.rules.conditions import can_attack_target
from aidm.rules.dice import Rng
from aidm.rules.hit_chance import attack_situation
from aidm.rules.monster_stats import creature_type_of
from aidm.rules.projection import project_state
from aidm.rules.weaknesses import substance_weakness_events


def throw_profile_for(creature: Creature, name: str, effect: DamageUse) -> AttackProfile:
    normal, long = IMPROVISED_RANGE
    mod = ability_modifier(creature.abilities[Ability.STR])
    return AttackProfile(
        key=THROW_KEY,
        name=f"Throw {name}",
        attack_bonus=mod,
        damage=with_mod(effect.dice, mod) if effect.ability_mod else effect.dice,
        damage_type=DamageType(effect.damage_type),
        ranged=True,
        range_normal=normal,
        range_long=long,
        context=AttackContext(ranged=True, weapon_die=weapon_die(effect.dice)),
        economy=AttackEconomy.ACTION,
    )


def _target_problem(
    state: GameState, actor_id: str, target_id: str | None, effect: DamageUse, name: str
) -> Creature | str:
    enc = state.encounter
    target = state.creatures.get(target_id or "")
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        return f"The {name} is thrown in a fight, and there is none now."
    there = enc.combatants.get(target.id) if target is not None else None
    if target is None or there is None or target.dead or there.withdrawn is not None:
        return f"Name a creature in this fight to throw the {name} at."
    if target.id == actor_id or not can_attack_target(state.creatures[actor_id], target):
        return f"{state.creatures[actor_id].name} cannot throw the {name} at {target.name}."
    return target


def effect_applies(target: Creature, effect: DamageUse) -> bool:
    """The item's own damage and condition reach this creature (`creature_types`, empty: any)."""
    return not effect.creature_types or creature_type_of(target) in effect.creature_types


def _riders(state: GameState, actor_id: str, result: AttackResult, label: str) -> list[AnyEvent]:
    enc = state.encounter
    if not result.riders_used or enc is None:
        return []
    economy = enc.combatant(actor_id).economy
    used = (*economy.once_per_turn_used, *result.riders_used)
    return [changed(actor_id, economy.model_copy(update={"once_per_turn_used": used}), label)]


def _on_hit_extras(
    rng: Rng,
    state: GameState,
    hit: tuple[str, str],
    substances: Sequence[str],
    feats: Registry[FeatureDef],
) -> list[AnyEvent]:
    """Further consequences of a hit: the substance weakness (`rules.weaknesses`)."""
    actor_id, target_id = hit
    return substance_weakness_events(rng, state, actor_id, target_id, substances, feats)


def thrown_item_events(
    rng: Rng,
    state: GameState,
    actor_id: str,
    target_id: str | None,
    name: str,
    effect: DamageUse,
    feats: Registry[FeatureDef],
    substances: Sequence[str] = (),
) -> list[AnyEvent] | str:
    target = _target_problem(state, actor_id, target_id, effect, name)
    if isinstance(target, str):
        return target
    actor = state.creatures[actor_id]
    profile = throw_profile_for(actor, name, effect)
    situation = attack_situation(state, actor_id, target.id, profile, feats)
    if not situation.range_check.in_range:
        return f"{target.name} is too far for the {name}: your zone or a touching one."
    applies = effect_applies(target, effect)
    if applies:
        result = resolve_attack(rng, state, actor_id, target.id, profile, feats)
    else:  # the throw happens; the item's own damage does not reach this creature
        rolled = roll_attack(rng, state, actor_id, target.id, profile, feats)
        result = AttackResult(events=rolled.events, hit=rolled.hit, crit=rolled.crit)
    events = [*_riders(state, actor_id, result, profile.name), *result.events]
    if not result.hit:
        return events
    after = project_state(state, events)
    if effect.condition is not None and applies and not after.creatures[target.id].dead:
        mark = new_condition(effect.condition, source_id=actor_id)
        events.extend(apply_condition(after.creatures[target.id], mark))
    hit = (actor_id, target.id)
    events.extend(_on_hit_extras(rng, project_state(state, events), hit, substances, feats))
    return events
