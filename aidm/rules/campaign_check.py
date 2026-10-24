"""Plan checks against the data registries (M5.1): what `aidm.models.campaign` cannot know.

Pure (the registries are cached read-only data). Returns `Problem`s so the campaign generator can
feed them back to the LLM on its retry (M5.3).

Checks (codes): `unknown_archetype` (NPC archetype is not an SRD monster/NPC stat block),
`unknown_monster` (encounter theme or boss is not an encounter-ready catalogue monster),
`theme_tier` (an encounter theme is not of the region tier), `boss_tier` (boss CR does not fit the
region tier), `boss_area` (M29.6b: the boss's area blast, a breath weapon, would rate above the
boss cap against heroes of the tier's planned level, `aidm.rules.encounter_danger`; M31.1f: an area
damage spell its kit can cast, fireball and kin, counts the same way),
`unknown_terrain` (a terrain tag is not a zone-template terrain).

Public API: `check_plan_refs(plan) -> list[Problem]` (empty when valid),
`master_too_dangerous(monster_id, tier) -> bool` (the `boss_area` test).
These checks run when a plan is made (the generator and the built-in sample), never when a save
loads, so a plan saved before a check grew still plays.
"""

from __future__ import annotations

from aidm.data.encounter_monsters import encounter_monsters, tier_for_cr
from aidm.data.encounter_tables import encounter_tables
from aidm.data.spell_defs import spell_defs
from aidm.data.srd import srd
from aidm.data.zone_templates import zone_templates
from aidm.models.campaign import CampaignPlan, NodePlan, RegionPlan
from aidm.models.encounter import Difficulty
from aidm.models.problem import Problem
from aidm.rules.encounter_danger import too_dangerous


def _terrain(owner: str, tags: tuple[str, ...]) -> list[Problem]:
    known = zone_templates()
    return [
        Problem(
            code="unknown_terrain", message=f"{owner}: unknown terrain tag {tag!r}", subject=owner
        )
        for tag in tags
        if tag not in known
    ]


def _themes(region: RegionPlan, node: NodePlan) -> list[Problem]:
    out: list[Problem] = []
    for monster_id in node.encounter_themes:
        entry = encounter_monsters().find(monster_id)
        if entry is None:
            msg = f"{node.id}: {monster_id!r} is not an encounter-ready monster"
            out.append(Problem(code="unknown_monster", message=msg, subject=node.id))
        elif entry.tier != region.tier:
            msg = (
                f"{node.id}: {monster_id!r} is tier {entry.tier}, the region is tier {region.tier}"
            )
            out.append(Problem(code="theme_tier", message=msg, subject=node.id))
    return out


def _boss(region: RegionPlan) -> list[Problem]:
    boss = region.boss
    entry = encounter_monsters().find(boss.monster_id)
    if entry is None:
        msg = f"{region.id}: boss {boss.monster_id!r} is not an encounter-ready monster"
        return [Problem(code="unknown_monster", message=msg, subject=region.id)]
    if tier_for_cr(entry.cr) != region.tier:
        msg = (
            f"{region.id}: boss {boss.monster_id!r} (CR {entry.cr}) does not fit tier {region.tier}"
        )
        return [Problem(code="boss_tier", message=msg, subject=region.id)]
    if master_too_dangerous(boss.monster_id, region.tier):
        msg = (
            f"{region.id}: boss {boss.monster_id!r} has an area attack or spell too strong for the "
            f"heroes of tier {region.tier}; choose another boss"
        )
        return [Problem(code="boss_area", message=msg, subject=region.id)]
    return []


def master_too_dangerous(monster_id: str, tier: int) -> bool:
    tables = encounter_tables()
    hp = tables.area_reference_hp.get(tier)
    monster = srd().monsters.find(monster_id)
    if hp is None or monster is None:
        return False
    return too_dangerous(monster, hp, Difficulty(tables.boss_rating_cap), tables, spell_defs())


def _region(region: RegionPlan) -> list[Problem]:
    out = _terrain(region.id, region.terrain_tags) + _boss(region)
    for node in region.nodes():
        out += _terrain(node.id, node.terrain_tags) + _themes(region, node)
    return out


def check_plan_refs(plan: CampaignPlan) -> list[Problem]:
    problems: list[Problem] = []
    for region in plan.all_regions():
        problems += _region(region)
    monsters = srd().monsters
    for npc in plan.npcs:
        if npc.archetype_id not in monsters:
            msg = f"npc {npc.id!r}: unknown archetype {npc.archetype_id!r}"
            problems.append(Problem(code="unknown_archetype", message=msg, subject=npc.id))
    return problems
