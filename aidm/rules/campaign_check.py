"""Plan checks against the data registries (M5.1): what `aidm.models.campaign` cannot know.

Pure (the registries are cached read-only data). Returns `Problem`s so the campaign generator can
feed them back to the LLM on its retry (M5.3).

Checks (codes): `unknown_archetype` (NPC archetype is not an SRD monster/NPC stat block),
`unknown_monster` (encounter theme or boss is not an encounter-ready catalogue monster),
`theme_tier` (an encounter theme is not of the region tier), `boss_tier` (boss CR does not fit the
region tier), `unknown_terrain` (a terrain tag is not a zone-template terrain).

Public API: `check_plan_refs(plan) -> list[Problem]` (empty when valid).
"""

from __future__ import annotations

from aidm.data.encounter_monsters import encounter_monsters, tier_for_cr
from aidm.data.srd import srd
from aidm.data.zone_templates import zone_templates
from aidm.models.campaign import CampaignPlan, NodePlan, RegionPlan
from aidm.models.problem import Problem


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
    return []


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
