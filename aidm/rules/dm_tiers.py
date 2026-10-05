"""Tier -> number lookups for the DM tools (SPEC 2.1, 6.3). Tables are data (`DmTiers`, an arg).

Public API:
- `party_levels(state) -> list[int]`: levels of the living player characters.
- `party_level(state) -> int`: their average, rounded down (1 with no living PC).
- `severity_damage_dice(tiers, severity, level) -> str`: creative-effect damage dice.
- `severity_save_dc(tiers, severity) -> int`; `severity_rounds(tiers, severity, requested) ->
  int`: the requested duration, at least 1, at most the severity's maximum.
- `xp_award(tiers, tier, level) -> int`: XP per PC for a `grant_xp` tier.
- `item_value_cap(tiers, region_tier) -> int`: the most one `grant_item` may be worth (gp).
- `deed_points(tiers, tier) -> int`: attitude points for a deed of that tier.
"""

from aidm.data.dm_tiers import DmTiers, TierRow
from aidm.models.dm_tiers import Severity, XpTier
from aidm.models.state import GameState


def party_levels(state: GameState) -> list[int]:
    return [c.pc.level for c in state.creatures.values() if c.pc is not None and not c.dead]


def party_level(state: GameState) -> int:
    levels = party_levels(state)
    return sum(levels) // len(levels) if levels else 1


def _row(rows: tuple[TierRow, ...], level: int) -> TierRow:
    return next(r for r in rows if r.max_level >= level)


def severity_damage_dice(tiers: DmTiers, severity: Severity, level: int) -> str:
    return str(_row(tiers.severity_dice, level).value(severity.value))


def severity_save_dc(tiers: DmTiers, severity: Severity) -> int:
    return tiers.severity_save_dc[severity.value]


def severity_rounds(tiers: DmTiers, severity: Severity, requested: int) -> int:
    return max(1, min(requested, tiers.severity_max_rounds[severity.value]))


def xp_award(tiers: DmTiers, tier: XpTier, level: int) -> int:
    return int(_row(tiers.xp_by_level, level).value(tier.value))


def item_value_cap(tiers: DmTiers, region_tier: int) -> int:
    return tiers.item_value_cap_gp[str(max(1, min(3, region_tier)))]


def deed_points(tiers: DmTiers, tier: XpTier) -> int:
    return tiers.deed_points[tier.value]
