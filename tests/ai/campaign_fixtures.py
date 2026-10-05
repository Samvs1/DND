"""Fixtures for the campaign generator tests: a valid model draft built from the sample plan."""

from typing import Any

from aidm.dm.campaign_sample import load_sample_campaign
from aidm.models.campaign import CampaignPlan, NodePlan, RegionPlan


def _node(node: NodePlan) -> dict[str, Any]:
    return {
        "name": node.name,
        "flavour": node.flavour,
        "terrain_tags": list(node.terrain_tags),
        "encounter_themes": list(node.encounter_themes),
    }


def _region(region: RegionPlan) -> dict[str, Any]:
    boss: dict[str, Any] = {"monster_id": region.boss.monster_id, "name": region.boss.name}
    if region.boss.ally_path:
        boss["ally_path"] = region.boss.ally_path
    return {
        "name": region.name,
        "flavour": region.flavour,
        "terrain_tags": list(region.terrain_tags),
        "arrival": _node(region.arrival),
        "spokes": [_node(s) for s in region.spokes],
        "gateway": _node(region.gateway),
        "boss": boss,
    }


def draft_from_plan(plan: CampaignPlan | None = None) -> dict[str, Any]:
    """The draft a well-behaved model would submit for `plan` (default: the sample)."""
    plan = plan or load_sample_campaign()
    nodes = {n.id: n.name for n in plan.all_nodes()}
    npcs = {n.id: n.name for n in plan.npcs}
    quests = {q.id: q.title for q in plan.quests}
    draft_npcs = []
    for npc in plan.npcs:
        secrets = []
        for s in npc.secrets:
            cond = s.reveal
            entry: dict[str, Any] = {"text": s.text, "reveal_kind": cond.kind.value}
            if cond.band is not None:
                entry["band"] = cond.band.value
            if cond.quest_id is not None:
                entry["quest_title"] = quests[cond.quest_id]
            if cond.item is not None:
                entry["item"] = cond.item
            secrets.append(entry)
        draft_npcs.append(
            {
                "name": npc.name,
                "role": npc.role,
                "archetype_id": npc.archetype_id,
                "demeanor": npc.demeanor,
                "motive": npc.motive,
                "home_place": nodes[npc.home_node],
                "voice_tag": npc.voice_tag,
                "secrets": secrets,
            }
        )
    draft: dict[str, Any] = {
        "title": plan.title,
        "premise": plan.premise,
        "tone": plan.tone,
        "theme": plan.theme,
        "acts": [
            {"title": a.title, "goal": a.goal, "region": _region(a.region)} for a in plan.acts
        ],
        "npcs": draft_npcs,
        "quests": [
            {
                "title": q.title,
                "giver": npcs[q.giver_npc_id],
                "objective": q.objective,
                "reward_tier": q.reward_tier,
                "act": q.act,
                "reward_item": q.reward_item,
            }
            for q in plan.quests
        ],
    }
    if plan.rival is not None:
        draft["rival_name"] = npcs[plan.rival.npc_id]
        draft["rival_hook"] = plan.rival.hook
    return draft


def with_bad_theme(draft: dict[str, Any], monster: str = "tarrasque") -> dict[str, Any]:
    """A copy whose first act-1 spoke fights an unknown/out-of-tier monster."""
    acts = [dict(a) for a in draft["acts"]]
    region = dict(acts[0]["region"])
    spokes = [dict(s) for s in region["spokes"]]
    spokes[0]["encounter_themes"] = [monster]
    region["spokes"] = spokes
    acts[0] = {**acts[0], "region": region}
    return {**draft, "acts": acts}
