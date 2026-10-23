"""Every region has a trader (M29.5b G34: a generated campaign had no shop in any of its 15 places,
so gold was useless). Repair over reject, like the quest repairs (`aidm.dm.campaign_draft`).

A region has a trader when one of the cast living in it has a shopkeeper role (the role words
the table uses to find a shop, `aidm.dm.precheck.SHOP_ROLES`). A region without one gets a
peddler at its arrival (the safe place), with a repair note; the model's own cast is never
changed.

Public API: `PEDDLER_ROLE`, `region_has_trader(plan, region) -> bool`,
`with_traders(plan, notes) -> CampaignPlan`.
"""

import re

from aidm.dm.campaign_draft_base import slug_id
from aidm.dm.campaign_steps import repair_note
from aidm.dm.precheck import SHOP_ROLES
from aidm.models.campaign import CampaignPlan, NpcPlan, RegionPlan
from aidm.models.problem import Problem

PEDDLER_ROLE = "travelling peddler and trader"
PEDDLER_ARCHETYPE = "commoner"
MAX_NAME = 40


def _role_words(role: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z]+", role.lower()))


def region_has_trader(plan: CampaignPlan, region: RegionPlan) -> bool:
    homes = {n.id for n in region.nodes()}
    return any(
        npc.home_node in homes and any(r in _role_words(npc.role) for r in SHOP_ROLES)
        for npc in plan.npcs
    )


def _peddler(region: RegionPlan, taken: set[str]) -> NpcPlan:
    name = f"{region.arrival.name} Peddler"
    name = name if len(name) <= MAX_NAME else "Wandering Peddler"
    npc_id = slug_id(name, taken)
    taken.add(npc_id)
    return NpcPlan(
        id=npc_id,
        name=name,
        role=PEDDLER_ROLE,
        archetype_id=PEDDLER_ARCHETYPE,
        demeanor="Brisk, practical and glad of custom.",
        motive="Wants fair coin and a safe road home.",
        home_node=region.arrival.id,
    )


def with_traders(plan: CampaignPlan, notes: list[Problem]) -> CampaignPlan:
    taken = {n.id for n in plan.npcs} | {n.id for n in plan.all_nodes()}
    added: list[NpcPlan] = []
    for region in plan.all_regions():
        if region_has_trader(plan, region):
            continue
        peddler = _peddler(region, taken)
        added.append(peddler)
        notes.append(repair_note(region.id, f"no trader lived here: {peddler.name} was added"))
    if not added:
        return plan
    return CampaignPlan.model_validate(
        plan.model_copy(update={"npcs": (*plan.npcs, *added)}).model_dump()
    )
