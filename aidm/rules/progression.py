"""Campaign progression: where the party is in the plan and when a region is resolved (SPEC 9).

Pure. A region is resolved when its boss is defeated (the boss's creature died, however the
fight started) or, for a boss with an ally path, when the boss's attitude reaches ALLY (only
deeds can get there, `aidm.rules.social`). Resolution unlocks the next act's arrival (derived
locks) and places that act's quest items (its side quests are asked by their givers, M23.4);
resolving the last region completes the campaign.

Public API:
- `region_of(state, node_id) -> RegionPlan | None`; `node_plan(state, node_id) -> NodePlan | None`.
- `boss_npc(state, region) -> WorldNpc | None`; `boss_defeated(state, region) -> bool`
  (a dead creature with the boss's name and stat block, or one that surrendered, M29.9a).
- `region_resolution_events(state) -> list[AnyEvent]`: `RegionResolved` (+ the next act's
  quest items) for every unresolved region whose boss is defeated or allied; empty otherwise. The
  session calls it after a fight ends and after attitude changes. M29.9a T15: no deed or quest
  step closes the master's waiting offer; it waits, shown as a sure parley, for the player's
  answer (`offer_answer.answer_offer` closes a settled master's offer peacefully, M29.5b G29).
- `offer_closed(offer, choice, *, success, detail) -> OfferResolved`: the answer to an offer,
  with its foes and its master (M33.2); `peaceful_close(offer)`: a parley answer, no fight.
- `settled_offer(state) -> EncounterOffer | None`: the pending offer of a boss whose region is
  already resolved (such an offer is answered without a fight).
- `campaign_complete(state) -> bool`: the story is over: the final region is resolved and, when
  the plan has a finale, its ending was chosen (M23.9; an epilogue written before M23.9 also
  counts, so such a save stays finished).
"""

from aidm.models.campaign import NodePlan, RegionPlan
from aidm.models.campaign_events import OfferResolved, RegionResolved
from aidm.models.campaign_state import EncounterOffer, OfferChoice, RegionResolution
from aidm.models.dm_tiers import AttitudeBand
from aidm.models.events import AnyEvent
from aidm.models.state import Creature, GameState
from aidm.models.world import WorldNpc
from aidm.rules.campaign_install import act_quest_events
from aidm.rules.conditions import condition_def
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
        (c.dead or _yielded(c)) and c.name == boss.name and c.monster_index == boss.monster_id
        for c in state.creatures.values()
    )


def _yielded(creature: Creature) -> bool:
    """M29.9a: a master who surrendered to the party counts as beaten (DECISIONS M29.9a)."""
    return any(condition_def(c.name).counts_as_defeated for c in creature.conditions)


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


def offer_closed(
    offer: EncounterOffer, choice: OfferChoice, *, success: bool | None = None, detail: str = ""
) -> OfferResolved:
    """The answer to `offer`, naming who it was to: its monsters and its master (M33.2)."""
    return OfferResolved(
        offer_id=offer.id,
        choice=choice,
        success=success,
        detail=detail,
        foes=offer.monster_ids,
        boss_npc_id=offer.boss_npc_id,
    )


def peaceful_close(offer: EncounterOffer) -> OfferResolved:
    return offer_closed(offer, OfferChoice.PARLEY, success=True, detail="no fight")


def settled_offer(state: GameState) -> EncounterOffer | None:
    campaign = state.campaign
    offer = campaign.offer if campaign is not None else None
    if campaign is None or offer is None or offer.boss_npc_id is None:
        return None
    return offer if offer.region_id in campaign.resolved else None


def campaign_complete(state: GameState) -> bool:
    campaign = state.campaign
    if campaign is None or not campaign.complete:
        return False
    chosen = campaign.finale_choice is not None or campaign.epilogue is not None
    return campaign.plan.finale is None or chosen
