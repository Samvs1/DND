"""The attack situation (shared by resolution and preview) and the exact hit-chance preview.

`attack_situation` gathers EVERY input of an attack roll from state, so the roll
(`aidm.rules.attacks`) and the hotbar preview can never disagree:
- advantage sources (combined with `combine_adv`): the attacker's and target's conditions
  (`attacks_against_melee/ranged`, hidden, helped, dodging, prone...), feature attack
  advantage (Pack Tactics, M3.8), high ground (BG3), and long range (one disadvantage source);
- target AC: the creature's AC + condition AC bonuses (Shield of Faith), at least the condition
  AC floor (Barkskin), + cover for a ranged attack from another zone (SRD 5.1 Cover);
- crit threshold from features (Improved Critical), auto-crit for a melee hit on a paralyzed or
  unconscious target (the attacker is in the same zone), condition bonus dice (Bless; a "-"
  die such as Bane's is subtracted);
- range: melee needs the same zone; ranged reaches the profile's range band.

Public API:
- `AttackSituation(adv, target_ac, bonus_dice, crit_on, auto_crit, range_check, ally_adjacent,
  lucky, adv_why)`: `lucky` = the attacker rerolls a natural 1 (halfling Lucky, a feature hook);
  `adv_why` names the advantage or disadvantage sources (M26.2: conditions, features, high
  ground, long range; `rules.d20.adv_reasons`).
- `attack_situation(state, attacker_id, target_id, profile, feats) -> AttackSituation`
  (both creatures must be combatants of the state's encounter; KeyError otherwise).
- `natural_chances(adv) -> dict[int, Fraction]`: the chance of each natural d20 result.
- `dice_distribution(dice) -> dict[int, Fraction]`: exact totals of plain dice terms.
- `hit_chance(state, attacker_id, target_id, profile, feats) -> HitChance`: exact math over the
  d20 and the bonus dice: a natural 1 misses, a natural >= the crit threshold hits and crits,
  otherwise total >= AC hits; Lucky rerolls a natural 1 once; out of range -> probability 0.
- `hit_chances(state, attacker_id, target_id, regs, spells=None) -> list[HitChance]`: every
  attack option of the attacker against the target (the hotbar tooltip); with the spell registry
  also each attack-roll spell it can cast now (`spell:<index>`, `rules.spell_chances`, M20.4).
  The character sheet keeps `AttackLine.hit_chance` None because a sheet has no target
  (docs/DECISIONS.md M3.3).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from aidm.data.character_data import CharacterRegistries
from aidm.data.feature_defs import FeatureDef
from aidm.data.registry import Registry
from aidm.data.spell_defs import SpellDef
from aidm.models.combat import AttackProfile, HitChance
from aidm.models.dice import AdvState
from aidm.models.encounter import Encounter
from aidm.models.state import GameState
from aidm.models.zones import RangeCheck
from aidm.rules.attack_profiles import attack_options
from aidm.rules.conditions import (
    attack_adv_names,
    condition_ac_bonus,
    condition_ac_floor,
    condition_bonus_dice,
    is_incapacitated,
    melee_hit_auto_crits,
)
from aidm.rules.d20 import adv_reasons, combine_adv
from aidm.rules.dice import parse_dice
from aidm.rules.features import (
    attack_advantage_sources,
    crit_threshold,
    feature_names,
    rerolls_natural_ones,
)
from aidm.rules.spell_chances import spell_attack_options
from aidm.rules.zones import (
    MELEE_BAND,
    cover_ac_bonus,
    high_ground_adv_counts,
    range_band,
    zone_range_check,
)

D20 = 20
HIGH_GROUND = "high ground"
LONG_RANGE = "long range"


@dataclass(frozen=True)
class AttackSituation:
    adv: AdvState
    target_ac: int
    bonus_dice: tuple[str, ...]
    crit_on: int
    auto_crit: bool
    range_check: RangeCheck
    ally_adjacent: bool
    lucky: bool = False
    adv_why: tuple[str, ...] = ()


def _ally_adjacent(state: GameState, enc: Encounter, attacker_id: str, target_id: str) -> bool:
    side, zone = enc.combatant(attacker_id).side, enc.combatant(target_id).zone_id
    for cid, combatant in enc.combatants.items():
        creature = state.creatures.get(cid)
        if cid in (attacker_id, target_id) or creature is None or combatant.side is not side:
            continue
        up = not creature.dead and creature.hp > 0 and combatant.withdrawn is None
        if up and combatant.zone_id == zone and not is_incapacitated(creature):
            return True
    return False


def attack_situation(
    state: GameState,
    attacker_id: str,
    target_id: str,
    profile: AttackProfile,
    feats: Registry[FeatureDef],
) -> AttackSituation:
    enc = state.encounter
    if enc is None:
        raise KeyError("no encounter")
    attacker, target = state.creatures[attacker_id], state.creatures[target_id]
    a_zone, t_zone = enc.combatant(attacker_id).zone_id, enc.combatant(target_id).zone_id
    zmap, ranged = enc.zone_map, profile.ranged
    band = range_band(profile.range_normal, profile.range_long) if ranged else MELEE_BAND
    check = zone_range_check(zmap, a_zone, t_zone, band)
    for_adv, for_dis = attack_adv_names(attacker, target, melee=not ranged)
    ally = _ally_adjacent(state, enc, attacker_id, target_id)
    feat_adv = feature_names(feats, attack_advantage_sources(attacker, feats, ally_adjacent=ally))
    hg_adv, hg_dis = high_ground_adv_counts(zmap, a_zone, t_zone, ranged=ranged)
    long_dis = 1 if check.long_range else 0
    ac = max(target.ac + condition_ac_bonus(target), condition_ac_floor(target))
    ac += cover_ac_bonus(zmap, a_zone, t_zone, ranged=ranged)
    adv = combine_adv(
        len(for_adv) + min(1, len(feat_adv)) + hg_adv, len(for_dis) + hg_dis + long_dis
    )
    for_adv += feat_adv + [HIGH_GROUND] * hg_adv
    for_dis += [HIGH_GROUND] * hg_dis + [LONG_RANGE] * long_dis
    return AttackSituation(
        adv=adv,
        target_ac=ac,
        bonus_dice=condition_bonus_dice(attacker),
        crit_on=crit_threshold(attacker, feats),
        auto_crit=not ranged and melee_hit_auto_crits(target),
        range_check=check,
        ally_adjacent=ally,
        lucky=rerolls_natural_ones(attacker, feats, "attack"),
        adv_why=adv_reasons(adv, for_adv, for_dis),
    )


def natural_chances(adv: AdvState) -> dict[int, Fraction]:
    chances: dict[int, Fraction] = {}
    for n in range(1, D20 + 1):
        if adv is AdvState.ADVANTAGE:
            chances[n] = Fraction(n * n - (n - 1) * (n - 1), D20 * D20)
        elif adv is AdvState.DISADVANTAGE:
            high, low = D20 + 1 - n, D20 - n
            chances[n] = Fraction(high * high - low * low, D20 * D20)
        else:
            chances[n] = Fraction(1, D20)
    return chances


def dice_distribution(dice: str) -> dict[int, Fraction]:
    if dice.startswith("-"):
        return {-value: p for value, p in dice_distribution(dice[1:]).items()}
    expr = parse_dice(dice)
    dist: dict[int, Fraction] = {expr.modifier: Fraction(1)}
    for term in expr.terms:
        if term.keep_highest is not None or term.keep_lowest is not None:
            raise ValueError(f"keep dice are not supported in a bonus: {dice!r}")
        for _ in range(term.count):
            step: dict[int, Fraction] = {}
            for total, p in dist.items():
                for face in range(1, term.sides + 1):
                    step[total + face] = step.get(total + face, Fraction(0)) + p / term.sides
            dist = step
    return dist


def _bonus_distribution(dice: Sequence[str]) -> dict[int, Fraction]:
    dist: dict[int, Fraction] = {0: Fraction(1)}
    for expr in dice:
        step: dict[int, Fraction] = {}
        for total, p in dist.items():
            for value, q in dice_distribution(expr).items():
                step[total + value] = step.get(total + value, Fraction(0)) + p * q
        dist = step
    return dist


def _chances(profile: AttackProfile, sit: AttackSituation) -> tuple[Fraction, Fraction]:
    bonus = _bonus_distribution(sit.bonus_dice)
    hit, crit = Fraction(0), Fraction(0)
    for natural, p in natural_chances(sit.adv).items():
        if natural == 1:
            continue
        if natural >= sit.crit_on:
            hit += p
            crit += p
            continue
        hits = sum(
            (q for b, q in bonus.items() if natural + profile.attack_bonus + b >= sit.target_ac),
            Fraction(0),
        )
        hit += p * hits
        if sit.auto_crit:
            crit += p * hits
    if sit.lucky:
        reroll = natural_chances(sit.adv)[1]
        return hit * (1 + reroll), crit * (1 + reroll)
    return hit, crit


def hit_chance(
    state: GameState,
    attacker_id: str,
    target_id: str,
    profile: AttackProfile,
    feats: Registry[FeatureDef],
) -> HitChance:
    sit = attack_situation(state, attacker_id, target_id, profile, feats)
    hit, crit = _chances(profile, sit) if sit.range_check.in_range else (Fraction(0), Fraction(0))
    return HitChance(
        option=profile.key,
        probability=float(hit),
        crit_chance=float(crit),
        adv=sit.adv,
        target_ac=sit.target_ac,
        attack_bonus=profile.attack_bonus,
        bonus_dice=sit.bonus_dice,
        in_range=sit.range_check.in_range,
        long_range=sit.range_check.long_range,
    )


def hit_chances(
    state: GameState,
    attacker_id: str,
    target_id: str,
    regs: CharacterRegistries,
    spells: Registry[SpellDef] | None = None,
) -> list[HitChance]:
    attacker = state.creatures[attacker_id]
    options = attack_options(attacker, regs)
    if spells is not None:  # M20.4: attack spells too, so "Out of range" means nothing reaches
        options += spell_attack_options(attacker, regs, spells)
    return [hit_chance(state, attacker_id, target_id, option, regs.features) for option in options]
