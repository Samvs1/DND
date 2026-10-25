"""THE attack path: one attack roll and its damage, for PC weapons, throws, spell attacks and
(M3.8) monster actions. Economy and target validation are the caller's job (`rules.commands`).

SRD 5.1 "Making an Attack" with the BG3 additions of `aidm.rules.hit_chance.attack_situation`:
the d20 (advantage combined from every source) + the attack bonus + condition bonus dice
(Bless) against the situational AC. A natural 1 always misses (halfling Lucky rerolls it once);
a natural roll at or above the crit threshold always hits and crits; a melee hit on a paralyzed
or unconscious target crits. A crit doubles every damage die (not modifiers), including riders
whose `doubles_on_crit` is set. Making the roll ends the attacker's attack-consumed conditions
(hidden, helped) and the target's consumed-by-an-attack-against-it ones (guided, M35.3).

Public API:
- `AttackRoll(events, hit, crit, situation)`; `roll_attack(rng, state, attacker_id, target_id,
  profile, feats) -> AttackRoll`: the roll only (`AttackRolled` + consumed conditions).
- `roll_damage_dice(dice, rng, *, crit=False, reroll_below=0) -> Roll`: Great Weapon Fighting
  rerolls each kept die below `reroll_below` once (the first die stays visible, not kept).
- `deal_damage(rng, state, attacker_id, target_id, packets, *, crit, feats) -> list[AnyEvent]`:
  the damage choke point (`rules.damage.resolve_damage`) plus its consequences: the target's
  concentration check, the charms its side's harm ends (`rules.harm_ends`) and the attacker's
  kill temp HP (a feature hook) when a hostile drops to 0. `state` must already include the
  events emitted before this hit.
- `AttackResult(events, hit, crit, riders_used)`; `resolve_attack(rng, state, attacker_id,
  target_id, profile, feats) -> AttackResult`: roll + weapon damage + the profile's typed
  `extra_damage` parts (a monster bite's fire; doubled on a crit) + feature riders (Sneak
  Attack once per turn, Colossus Slayer...) + condition riders the attacker applied to the
  target (Hunter's Mark; doubled on a crit) + flat fighting-style bonuses already in the profile.
  `riders_used` names the once-per-turn riders spent (the command records them in the economy).
  Every damage roll is a `DiceRolled` of kind DAMAGE with the target and a display label
  (the feature or condition name, never its id; M26.2).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from aidm.data.feature_defs import FeatureDef
from aidm.data.registry import Registry
from aidm.models.combat import AttackProfile
from aidm.models.combat_events import AttackRolled
from aidm.models.damage import DamagePacket
from aidm.models.dice import DieRoll, Roll, RollKind
from aidm.models.events import AnyEvent, ConditionRemoved, DamageTaken, DiceRolled, TempHpSet
from aidm.models.state import GameState
from aidm.rules.concentration import concentration_after_damage
from aidm.rules.conditions import (
    attack_consumed_conditions,
    condition_def,
    condition_riders,
    roll_bonus_dice,
)
from aidm.rules.d20 import roll_d20
from aidm.rules.damage import resolve_damage
from aidm.rules.dice import Rng, roll
from aidm.rules.difficulty import scale_damage
from aidm.rules.features import (
    damage_reroll_below,
    damage_riders,
    feature_names,
    kill_temp_hp,
)
from aidm.rules.harm_ends import harm_ended_events
from aidm.rules.hit_chance import AttackSituation, attack_situation
from aidm.rules.projection import project_state


@dataclass(frozen=True)
class AttackRoll:
    events: list[AnyEvent]
    hit: bool
    crit: bool
    situation: AttackSituation


@dataclass(frozen=True)
class AttackResult:
    events: list[AnyEvent]
    hit: bool
    crit: bool
    riders_used: tuple[str, ...] = ()


def roll_attack(
    rng: Rng,
    state: GameState,
    attacker_id: str,
    target_id: str,
    profile: AttackProfile,
    feats: Registry[FeatureDef],
) -> AttackRoll:
    sit = attack_situation(state, attacker_id, target_id, profile, feats)
    d20 = roll_d20(rng, sit.adv, profile.attack_bonus, crit_on=sit.crit_on)
    if d20.is_fumble and sit.lucky:
        d20 = roll_d20(rng, sit.adv, profile.attack_bonus, crit_on=sit.crit_on)
    bonus = tuple(roll_bonus_dice(dice, rng) for dice in sit.bonus_dice)
    total = d20.total + sum(b.total for b in bonus)
    hit = not d20.is_fumble and (d20.is_crit or total >= sit.target_ac)
    crit = hit and (d20.is_crit or sit.auto_crit)
    events: list[AnyEvent] = [
        AttackRolled(
            attacker_id=attacker_id,
            target_id=target_id,
            attack=profile.name,
            roll=d20,
            bonus_rolls=bonus,
            target_ac=sit.target_ac,
            hit=hit,
            crit=crit,
            adv_why=sit.adv_why,
        )
    ]
    for bearer_id, against in ((attacker_id, False), (target_id, True)):
        for c in attack_consumed_conditions(state.creatures[bearer_id], against=against):
            events.append(
                ConditionRemoved(
                    creature_id=bearer_id, name=c.name, source_id=c.source_id, exact_source=True
                )
            )
    return AttackRoll(events=events, hit=hit, crit=crit, situation=sit)


def roll_damage_dice(dice: str, rng: Rng, *, crit: bool = False, reroll_below: int = 0) -> Roll:
    base = roll(dice, rng, crit=crit)
    if reroll_below <= 1:
        return base
    rolled: list[DieRoll] = []
    for die in base.dice:
        if die.kept and die.value < reroll_below:
            rolled.append(die.model_copy(update={"kept": False}))
            rolled.append(DieRoll(sides=die.sides, value=rng.randint(1, die.sides)))
        else:
            rolled.append(die)
    total = sum(d.value for d in rolled if d.kept) + base.modifier
    return base.model_copy(update={"dice": tuple(rolled), "total": total})


def _kill_bonus(
    before: GameState,
    after: GameState,
    attacker_id: str,
    target_id: str,
    feats: Registry[FeatureDef],
) -> list[AnyEvent]:
    enc = before.encounter
    attacker, target = after.creatures.get(attacker_id), before.creatures[target_id]
    if attacker is None or enc is None or target.hp == 0 or after.creatures[target_id].hp > 0:
        return []
    sides = {cid: c.side for cid, c in enc.combatants.items()}
    if sides.get(attacker_id) is None or sides.get(attacker_id) == sides.get(target_id):
        return []
    amount = kill_temp_hp(attacker, feats)
    if amount <= attacker.temp_hp:
        return []
    return [TempHpSet(creature_id=attacker_id, temp_hp=amount)]


def deal_damage(
    rng: Rng,
    state: GameState,
    attacker_id: str,
    target_id: str,
    packets: Sequence[DamagePacket],
    *,
    crit: bool,
    feats: Registry[FeatureDef],
) -> list[AnyEvent]:
    target = state.creatures[target_id]
    packets = scale_damage(state, attacker_id, packets)
    events = resolve_damage(target, packets, crit=crit, source_id=attacker_id)
    if not events:
        return []
    after = project_state(state, events)
    taken = events[0]
    if isinstance(taken, DamageTaken):
        events.extend(concentration_after_damage(rng, after, taken))
        events.extend(harm_ended_events(after, taken))
    events.extend(_kill_bonus(state, after, attacker_id, target_id, feats))
    return events


def _damage_roll(rolled: Roll, attacker_id: str, target_id: str, label: str) -> DiceRolled:
    return DiceRolled(
        roll=rolled, roller_id=attacker_id, label=label, kind=RollKind.DAMAGE, target_id=target_id
    )


def _weapon_packets(
    rng: Rng,
    state: GameState,
    attacker_id: str,
    target_id: str,
    profile: AttackProfile,
    rolled: AttackRoll,
    feats: Registry[FeatureDef],
) -> tuple[list[AnyEvent], list[DamagePacket], tuple[str, ...]]:
    attacker, target = state.creatures[attacker_id], state.creatures[target_id]
    enc = state.encounter
    used = enc.combatant(attacker_id).economy.once_per_turn_used if enc else ()
    sit = rolled.situation
    ctx = profile.context.model_copy(
        update={
            "adv": sit.adv,
            "ally_adjacent": sit.ally_adjacent,
            "target_wounded": target.hp < target.max_hp,
            "crit": rolled.crit,
            "used_once_per_turn": used,
        }
    )
    reroll = damage_reroll_below(attacker, feats, ctx)
    main = roll_damage_dice(profile.damage, rng, crit=rolled.crit, reroll_below=reroll)
    events: list[AnyEvent] = [_damage_roll(main, attacker_id, target_id, f"{profile.name} damage")]
    packets = [DamagePacket(amount=main.total, damage_type=profile.damage_type)]
    for part in profile.extra_damage:
        extra = roll(part.dice, rng, crit=rolled.crit)
        label = f"{profile.name} {part.damage_type.value} damage"
        events.append(_damage_roll(extra, attacker_id, target_id, label))
        packets.append(DamagePacket(amount=extra.total, damage_type=part.damage_type))
    spent: list[str] = []
    for rider in damage_riders(attacker, feats, ctx):
        amount = rider.flat
        if rider.dice:
            extra = roll(rider.dice, rng, crit=rolled.crit and rider.doubles_on_crit)
            label = feature_names(feats, [rider.feature])[0]
            events.append(_damage_roll(extra, attacker_id, target_id, label))
            amount += extra.total
        packets.append(
            DamagePacket(amount=amount, damage_type=rider.damage_type or profile.damage_type)
        )
        if rider.once_per_turn:
            spent.append(rider.feature)
    for name, dice, kind in condition_riders(attacker_id, target):
        extra = roll(dice, rng, crit=rolled.crit)
        label = condition_def(name).name
        events.append(_damage_roll(extra, attacker_id, target_id, label))
        packets.append(DamagePacket(amount=extra.total, damage_type=kind or profile.damage_type))
    return events, packets, tuple(spent)


def resolve_attack(
    rng: Rng,
    state: GameState,
    attacker_id: str,
    target_id: str,
    profile: AttackProfile,
    feats: Registry[FeatureDef],
) -> AttackResult:
    rolled = roll_attack(rng, state, attacker_id, target_id, profile, feats)
    events = list(rolled.events)
    if not rolled.hit:
        return AttackResult(events=events, hit=False, crit=False)
    dice_events, packets, spent = _weapon_packets(
        rng, state, attacker_id, target_id, profile, rolled, feats
    )
    events.extend(dice_events)
    after = project_state(state, events)
    events.extend(
        deal_damage(rng, after, attacker_id, target_id, packets, crit=rolled.crit, feats=feats)
    )
    return AttackResult(events=events, hit=True, crit=rolled.crit, riders_used=spent)
