"""The offer registries and the spoke foe pick (SPEC 9, M29.6; split from `rules.encounter_offer`
in M31.1d so the master template can measure the region's spoke fights). Pure.

A spoke's list is rated at most `tables.spoke_rating_cap[region tier]` (tier 1: easy) times
`spoke_budget_scale[tier]` and fields at most `spoke_max_monsters_per_pc` monsters per PC; a theme
list too costly for the party gets terrain-matched stand-ins within the budget when
`tables.spoke_stand_ins` is on (M29.6), else (or when none fits) its cheapest monster. M29.6b: a
monster whose area blast alone rates above the cap is never picked (unless nothing else exists).

Public API:
- `OfferData(monsters, tables, terrains, tiers, encounter, overlay, spells, master)`: the
  registries (`master`: the M31.1d master template; the default is switched off).
- `hero_hp(state) -> float`: the living heroes' average hit point maximum (M29.6b).
- `safe_monsters(state, data, monsters, cap) -> list[str]`: the monsters whose blast fits `cap`.
- `spoke_monsters(state, data, region, node, rng) -> list[str]`: a spoke's foes.
- `spoke_strength(state, data, region) -> int`: M31.1d, the adjusted XP of the strongest foe
  group any spoke of the region may field for this party (its budget cap, or its cheapest theme
  monster when nothing fits); 0 for a region without spoke themes.
"""

import random
from dataclasses import dataclass, field

from aidm.data.dm_tiers import DmTiers
from aidm.data.encounter_monsters import EncounterMonster
from aidm.data.encounter_tables import EncounterTables
from aidm.data.master_template import MasterTemplate
from aidm.data.monster_overlay import MonsterOverlay
from aidm.data.registry import Registry
from aidm.data.spell_defs import SpellDef
from aidm.data.srd_monsters import SrdMonster
from aidm.data.zone_templates import TerrainTemplate
from aidm.models.campaign import NodePlan, RegionPlan
from aidm.models.encounter import Difficulty
from aidm.models.state import GameState
from aidm.rules.dice import Rng
from aidm.rules.dm_tiers import party_levels
from aidm.rules.encounter_budget import adjusted_xp, pick_monsters, rating_cap_xp
from aidm.rules.encounter_danger import too_dangerous


@dataclass(frozen=True)
class OfferData:
    monsters: Registry[SrdMonster]
    tables: EncounterTables
    terrains: Registry[TerrainTemplate]
    tiers: DmTiers
    encounter: Registry[EncounterMonster]
    overlay: MonsterOverlay = field(default_factory=MonsterOverlay)
    spells: Registry[SpellDef] | None = None
    master: MasterTemplate = field(default_factory=MasterTemplate)


def xp_of(data: OfferData, monster: str) -> int:
    return data.monsters.get(monster).xp


def hero_hp(state: GameState) -> float:
    """The living heroes' average hit point maximum (0 with none)."""
    pcs = [c.max_hp for c in state.creatures.values() if c.pc is not None and not c.dead]
    return sum(pcs) / len(pcs) if pcs else 0.0


def safe_monsters(
    state: GameState, data: OfferData, monsters: list[str], cap: Difficulty
) -> list[str]:
    """M29.6b: the monsters whose area blast alone does not rate above `cap`."""
    hp = hero_hp(state)
    return [m for m in monsters if not too_dangerous(data.monsters.get(m), hp, cap, data.tables)]


def _spoke_tables(data: OfferData, tier: int, size: int) -> EncounterTables:
    per_pc = data.tables.spoke_max_monsters_per_pc.get(tier)
    if per_pc is None:
        return data.tables
    return data.tables.model_copy(
        update={"max_monsters": min(data.tables.max_monsters, per_pc * size)}
    )


def _spoke_budget(state: GameState, data: OfferData, tier: int) -> tuple[int, Difficulty]:
    levels = party_levels(state)
    rating = Difficulty(data.tables.spoke_rating_cap.get(tier, Difficulty.MEDIUM.value))
    scale = data.tables.spoke_budget_scale.get(tier, 1.0)
    return int(rating_cap_xp(levels, rating, data.tables) * scale), rating


def spoke_monsters(
    state: GameState, data: OfferData, region: RegionPlan, node: NodePlan, rng: Rng
) -> list[str]:
    size = len(party_levels(state))
    cap, rating = _spoke_budget(state, data, region.tier)
    themes = safe_monsters(state, data, list(node.encounter_themes), rating)
    xps = {m: xp_of(data, m) for m in themes}
    tables = _spoke_tables(data, region.tier, size)
    picked = pick_monsters(rng, cap, xps, size, tables)
    if not picked and data.tables.spoke_stand_ins:
        picked = _stand_ins(rng, (state, data), node.encounter_themes, (cap, size, rating), tables)
    every = xps or {m: xp_of(data, m) for m in node.encounter_themes}
    return picked or [min(sorted(every), key=lambda m: every[m])]


def _stand_ins(
    rng: Rng,
    where: tuple[GameState, OfferData],
    themes: tuple[str, ...],
    budget: tuple[int, int, Difficulty],
    tables: EncounterTables,
) -> list[str]:
    """M29.6: no theme monster fits the party's budget (a small or low-level party) -> the
    encounter-ready monsters sharing a terrain with the themes, at the highest XP one of them
    fits alone, picked within the budget (M29.6b: and whose area blast is within the spoke cap).
    [] when none fits (the cheapest theme monster stays)."""
    state, data = where
    cap, size, rating = budget
    tags = {t for m in themes if (e := data.encounter.find(m)) is not None for t in e.tags}
    near = [e.index for e in data.encounter.all() if tags & set(e.tags)]
    fits = {
        m: xp_of(data, m)
        for m in safe_monsters(state, data, near, rating)
        if adjusted_xp([xp_of(data, m)], size, tables) <= cap
    }
    if not fits:
        return []
    top = max(fits.values())
    return pick_monsters(rng, cap, {m: x for m, x in fits.items() if x == top}, size, tables)


def _node_strength(state: GameState, data: OfferData, tier: int, node: NodePlan) -> int:
    size = len(party_levels(state))
    cap, rating = _spoke_budget(state, data, tier)
    tables = _spoke_tables(data, tier, size)
    themes = safe_monsters(state, data, list(node.encounter_themes), rating)
    if any(adjusted_xp([xp_of(data, m)], size, tables) <= cap for m in themes):
        return cap
    budget = (cap, size, rating)
    probe = random.Random(0)
    if data.tables.spoke_stand_ins and _stand_ins(
        probe, (state, data), node.encounter_themes, budget, tables
    ):
        return cap
    every = themes or list(node.encounter_themes)
    return min(adjusted_xp([xp_of(data, m)], size, tables) for m in every)


def spoke_strength(state: GameState, data: OfferData, region: RegionPlan) -> int:
    if not party_levels(state):
        return 0
    found = [
        _node_strength(state, data, region.tier, node)
        for node in region.spokes
        if node.encounter_themes
    ]
    return max(found, default=0)
