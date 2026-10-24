"""The master's boost (M31.1d): the one interpreter of the master template. Pure.

Round 4 met an 11-HP hobgoblin, a 22-HP ghoul and a wight at 26 of its 45 SRD hit points: the
M29.6 small-party hit point scale (`boss_hp_scale_floor`) compared a lone master with the boss cap
x `boss_budget_scale` (M29.6b), which is below one CR 3 monster for four level-3 heroes, so full
parties got scaled masters too. Now:
- a solo or duo (at most `tables.small_party_max` heroes) keeps that scale (owner rule): hit
  points x boss cap / the master's adjusted XP, never below `boss_hp_scale_floor`;
- a party of `template.party_min` heroes or more gets the template (`aidm.data.master_template`):
  hit points towards the hit dice maximum, a master's turn (lite legendary points) and a trait;
  M31.1g (owner 2026-10-24, "Tune HP to the cap", replacing the M31.1d SRD floor): those hit
  points x `template.full_party_hp_share[region tier]` (1.0 when the tier is not listed), never
  below the small-party scale above computed for the same party (the M29.6 scale every party
  met in round 4: a master never spawns weaker than round 4's);
- every master is never weaker than the region's own spoke fights: when its rated XP alone is
  below `offer_spokes.spoke_strength`, its hit points (and rated XP) rise by that ratio, at most
  `template.floor_hp_scale_max`.
The offer rates the master at its SRD XP x `rating_factor` (hit point scale x the share of round
damage its master's turn adds), so the danger word follows the real strength.

Public API:
- `MasterBoost(hp_scale, legendary_points, traits, rating_factor, legendary_recharge)`;
  `extra_attacks`: its master's turns a round on average.
- `boss_cap_xp(levels, data, tier) -> int`: the most adjusted XP a master's fight may have.
- `hit_dice_ratio(monster, share) -> float`: hit points at `share` of the way from the average to
  the hit dice maximum, over the average.
- `small_party_scale(levels, data, monster, tier) -> float`: the M29.6 hit point scale (boss cap
  over the master's adjusted XP, never below `boss_hp_scale_floor`; 1.0 when it fits).
- `master_boost(state, data, monster_id, region) -> MasterBoost`.
- `boss_hp_scale(state, data, monster_id, region=None) -> float`: the master spawn's hit point
  scale (M29.6, M31.1d).
"""

from dataclasses import dataclass, replace

from aidm.data.srd_monsters import SrdMonster
from aidm.models.campaign import RegionPlan
from aidm.models.encounter import MAX_SPAWN_HP_SCALE, Difficulty
from aidm.models.state import GameState
from aidm.rules.dice import DiceError, dice_max
from aidm.rules.dm_tiers import party_levels
from aidm.rules.encounter_budget import adjusted_xp, rating_cap_xp
from aidm.rules.encounter_threat import attack_damage, round_damage
from aidm.rules.monster_catalog import monster_catalog
from aidm.rules.offer_label import heroes_ac
from aidm.rules.offer_spokes import OfferData, spoke_strength, xp_of


@dataclass(frozen=True)
class MasterBoost:
    hp_scale: float = 1.0
    legendary_points: int = 0
    traits: tuple[str, ...] = ()
    rating_factor: float = 1.0
    legendary_recharge: int = 1

    @property
    def extra_attacks(self) -> float:
        """Its master's turns a round on average (a spent pool refills on a d6 of at least
        `legendary_recharge` at the start of its turn)."""
        return self.legendary_points * (7 - self.legendary_recharge) / 6


def boss_cap_xp(levels: list[int], data: OfferData, tier: int) -> int:
    """The most adjusted XP a master's fight may have (M29.6b: x `boss_budget_scale[tier]`)."""
    cap = rating_cap_xp(levels, Difficulty(data.tables.boss_rating_cap), data.tables)
    return int(cap * data.tables.boss_budget_scale.get(tier, 1.0))


def hit_dice_ratio(monster: SrdMonster, share: float) -> float:
    if share <= 0 or monster.hit_points <= 0:
        return 1.0
    try:
        top = dice_max(monster.hit_points_roll.replace(" ", ""))
    except DiceError:
        return 1.0
    average = monster.hit_points
    return (average + share * max(0, top - average)) / average


def small_party_scale(levels: list[int], data: OfferData, monster: str, tier: int) -> float:
    floor = data.tables.boss_hp_scale_floor
    if floor is None:
        return 1.0
    cap = boss_cap_xp(levels, data, tier)
    alone = adjusted_xp([xp_of(data, monster)], len(levels), data.tables)
    return 1.0 if alone <= cap else max(floor, cap / alone)


def _damage_factor(state: GameState, data: OfferData, monster: SrdMonster, extra: float) -> float:
    if extra <= 0:
        return 1.0
    catalog = monster_catalog(monster, data.overlay, data.spells if data.spells else ())
    ac = heroes_ac(state)
    base = round_damage(catalog, data.spells, ac)
    return (base + extra * attack_damage(catalog, ac)) / base if base > 0 else 1.0


def _base(
    state: GameState, data: OfferData, monster_id: str, tier: int
) -> tuple[float, int, tuple[str, ...]]:
    levels = party_levels(state)
    template = data.master
    if len(levels) <= data.tables.small_party_max:
        return small_party_scale(levels, data, monster_id, tier), 0, ()
    if len(levels) < template.party_min:
        return 1.0, 0, ()
    share = template.full_party_hp_share.get(tier, 1.0)
    hp = hit_dice_ratio(data.monsters.get(monster_id), template.hit_dice_share) * share
    hp = max(hp, small_party_scale(levels, data, monster_id, tier))
    traits = (template.trait,) if template.trait else ()
    return hp, template.legendary_points, traits


def master_boost(
    state: GameState, data: OfferData, monster_id: str, region: RegionPlan | None
) -> MasterBoost:
    levels = party_levels(state)
    if not levels:
        return MasterBoost()
    tier = region.tier if region is not None else state.world.region_tier
    hp, points, traits = _base(state, data, monster_id, tier)
    monster = data.monsters.get(monster_id)
    turn = MasterBoost(legendary_points=points, legendary_recharge=data.master.legendary_recharge)
    factor = hp * _damage_factor(state, data, monster, turn.extra_attacks)
    strength = spoke_strength(state, data, region) if region is not None else 0
    alone = adjusted_xp([round(monster.xp * factor)], len(levels), data.tables)
    if 0 < alone < strength:
        lift = min(data.master.floor_hp_scale_max, strength / alone)
        hp, factor = hp * lift, factor * lift
    capped = min(MAX_SPAWN_HP_SCALE, hp)
    return replace(turn, hp_scale=capped, traits=traits, rating_factor=factor * capped / hp)


def boss_hp_scale(
    state: GameState, data: OfferData, monster_id: str, region: RegionPlan | None = None
) -> float:
    return master_boost(state, data, monster_id, region).hp_scale
