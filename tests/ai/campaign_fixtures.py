"""Fixtures for the campaign generator tests: a valid model draft built from the sample plan."""

from typing import Any

from aidm.dm.campaign_sample import load_sample_campaign
from aidm.models.campaign import CampaignPlan, NodePlan, RegionPlan, SecretPlan
from aidm.models.quests import QuestStep, RouteKind, RoutePlan
from aidm.rules.plan_ids import boss_npc_id


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


def _step(step: QuestStep, nodes: dict[str, str], npcs: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": step.kind.value, "text": step.text}
    if step.nodes:
        out["places"] = [nodes[n] for n in step.nodes]
    if step.npc is not None:
        out["npc"] = npcs[step.npc]
    if step.band is not None:
        out["band"] = step.band.value
    if step.count != 1:
        out["count"] = step.count
    if step.hidden:
        out["hidden"] = True
    return out | {k: v for k, v in {"item": step.item, "tag": step.tag}.items() if v is not None}


def _route(route: RoutePlan, nodes: dict[str, str], npcs: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "title": route.title,
        "steps": [_step(s, nodes, npcs) for s in route.steps],
    }
    if route.hint_npc_id is not None:
        out["hint_npc"] = npcs[route.hint_npc_id]
    if route.effect is not None:
        out["effect"] = route.effect
    return out


def _quest_parts(plan: CampaignPlan, draft: dict[str, Any]) -> None:
    """Add the sample's steps, routes and finale to `draft` (by names, as the model writes)."""
    nodes = {n.id: n.name for n in plan.all_nodes()}
    npcs = {n.id: n.name for n in plan.npcs}
    npcs |= {boss_npc_id(a.region): a.region.boss.name for a in plan.acts}
    for quest, entry in zip(plan.quests, draft["quests"], strict=True):
        entry["steps"] = [_step(s, nodes, npcs) for s in quest.steps]
    for act, entry in zip(plan.acts, draft["acts"], strict=True):
        for route in act.main.routes if act.main is not None else ():
            key = "peace" if route.kind is RouteKind.PEACE else "cunning"
            entry[key] = _route(route, nodes, npcs)
    if plan.finale is not None:
        endings = [{"title": o.title, "text": o.text} for o in plan.finale.options]
        draft["finale"] = {"question": plan.finale.question, "endings": endings}


def _secret(secret: SecretPlan, titles: dict[str, str]) -> dict[str, Any]:
    cond = secret.reveal
    entry: dict[str, Any] = {"text": secret.text, "reveal_kind": cond.kind.value}
    if cond.band is not None:
        entry["band"] = cond.band.value
    if cond.quest_id is not None:
        entry["quest_title"] = titles[cond.quest_id]
    if cond.item is not None:
        entry["item"] = cond.item
    if cond.fact_tag is not None:
        entry["fact_tag"] = cond.fact_tag
    return entry


def draft_from_plan(plan: CampaignPlan | None = None, *, quests: bool = True) -> dict[str, Any]:
    """The draft a well-behaved model would submit for `plan` (default: the sample); with
    `quests=False` the pre-M23 shape (no steps, routes or finale)."""
    plan = plan or load_sample_campaign()
    nodes = {n.id: n.name for n in plan.all_nodes()}
    npcs = {n.id: n.name for n in plan.npcs}
    titles = {q.id: q.title for q in plan.quests}
    draft_npcs = []
    for npc in plan.npcs:
        secrets = [_secret(s, titles) for s in npc.secrets]
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
    if quests:
        _quest_parts(plan, draft)
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
