"""Campaign progression: where the party is in the plan and when a region is resolved (SPEC 9).

Pure. A region is resolved when its boss is defeated (the boss's creature died, however the
fight started) or, for a boss with an ally path, when the boss's attitude reaches ALLY (only
deeds can get there, `aidm.rules.social`). Resolution unlocks the next act's arrival (derived
locks) and places that act's quest items (its side quests are asked by their givers, M23.4);
resolving the last region completes the campaign.

Public API:
- `region_of(state, node_id) -> RegionPlan | None`; `node_plan(state, node_id) -> NodePlan | None`.
- `boss_npc(state, region) -> WorldNpc | None`; `boss_defeated(state, region) -> bool`
  (a dead creature with the boss's name and stat block).
- `region_resolution_events(state) -> list[AnyEvent]`: `RegionResolved` (+ the next act's
  quest items) for every unresolved region whose boss is defeated or allied; empty otherwise. The
  session calls it after a fight ends and after attitude changes.
- `campaign_complete(state) -> bool`.
"""

from aidm.models.campaign import NodePlan, RegionPlan
from aidm.models.campaign_events import RegionResolved
from aidm.models.campaign_state import RegionResolution
from aidm.models.dm_tiers import AttitudeBand
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.models.world import WorldNpc
from aidm.rules.campaign_install import act_quest_events
from aidm.rules.plan_ids import boss_npc_id
from aidm.rules.social import attitude_band, attitude_score


def region_of(state: GameState, node_id: str | None) -> RegionPlan | None:
    campaign = state.campaign
    if campaign is None or node_id is None:
        return None
    for region in campaign.plan.all_regions():
        if any(n.id == node_id for n in region.nodes()):
            return region
    return None


def node_plan(state: GameState, node_id: str | None) -> NodePlan | None:
    region = region_of(state, node_id)
    if region is None:
        return None
    return next(n for n in region.nodes() if n.id == node_id)


def boss_npc(state: GameState, region: RegionPlan) -> WorldNpc | None:
    return state.world.npcs.get(boss_npc_id(region))


def boss_defeated(state: GameState, region: RegionPlan) -> bool:
    boss = region.boss
    return any(
        c.dead and c.name == boss.name and c.monster_index == boss.monster_id
        for c in state.creatures.values()
    )


def _allied(state: GameState, region: RegionPlan) -> bool:
    npc = boss_npc(state, region)
    if region.boss.ally_path is None or npc is None or npc.hostile:
        return False
    return attitude_band(attitude_score(npc)) is AttitudeBand.ALLY


def region_resolution_events(state: GameState) -> list[AnyEvent]:
    campaign = state.campaign
    if campaign is None:
        return []
    events: list[AnyEvent] = []
    resolved = set(campaign.resolved)
    acts = campaign.plan.acts
    for act in acts:
        region = act.region
        if region.id in resolved:
            continue
        if boss_defeated(state, region):
            how = RegionResolution.DEFEAT
        elif _allied(state, region):
            how = RegionResolution.ALLIANCE
        else:
            continue
        resolved.add(region.id)
        final = len(resolved) == len(acts)
        events.append(RegionResolved(region_id=region.id, how=how, final=final))
        if act.index < len(acts):
            events.extend(act_quest_events(state, campaign.plan, act.index + 1))
    return events


def campaign_complete(state: GameState) -> bool:
    return state.campaign is not None and state.campaign.complete
