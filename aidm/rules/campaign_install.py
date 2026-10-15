"""Install a campaign plan into a game state: the events that make it exist (SPEC 9, M5.3). Pure.

The plan becomes world registry entries (closed world: the cast and the bosses exist only once
these events are applied; side quests are never bulk-offered, their givers ask on arrival,
`aidm.rules.quest_offers`, M23.4), the campaign graph (travel neighbours and derived
locks, `aidm.session.campaign_apply`), the party's starting camp supplies
(`rules.rests.STARTING_CAMP_SUPPLIES`: one long rest, BG3-like; RULES_DECISIONS M9.2) and the
first move to act 1's arrival.

Bosses are registered as world NPCs at their gateway (`plan_ids.boss_npc_id(region)`), so the social
rules apply to them: a boss with an ally path starts unfriendly (`BOSS_ALLY_PATH_BASE`) and can
be turned by deeds; a boss without one starts hostile (DECISIONS M5.3).

Public API: `install_campaign(state, plan, seed) -> list[AnyEvent]` (`ValueError` when a campaign
is already installed or an id clashes), `plan_npc(npc) -> WorldNpc`,
`act_quest_events(state, plan, act) -> list[AnyEvent]` (the act's quest items placed in the
world, `aidm.rules.quest_items`, M23.3; since M23.4 no side quest is offered here).
"""

from aidm.models.campaign import CampaignPlan, NpcPlan, RegionPlan, RevealKind, SecretPlan
from aidm.models.campaign_events import CampaignInstalled
from aidm.models.events import AnyEvent, CampSuppliesChanged
from aidm.models.state import GameState
from aidm.models.world import NpcSecret, WorldNpc
from aidm.models.world_events import NpcIntroduced, PartyMoved
from aidm.rules.plan_ids import boss_npc_id
from aidm.rules.quest_items import quest_item_events
from aidm.rules.rests import STARTING_CAMP_SUPPLIES
from aidm.rules.social import band_floor
from aidm.rules.world_graph import build_campaign_graph

BOSS_ROLE = "boss"
BOSS_ALLY_PATH_BASE = -15
BOSS_HOSTILE_BASE = -60


def _secret(secret: SecretPlan) -> NpcSecret:
    cond = secret.reveal
    floor = band_floor(cond.band) if cond.kind is RevealKind.ATTITUDE and cond.band else None
    return NpcSecret(id=secret.id, text=secret.text, min_score=floor, reveal=cond)


def plan_npc(npc: NpcPlan) -> WorldNpc:
    return WorldNpc(
        id=npc.id,
        name=npc.name,
        role=npc.role,
        archetype_id=npc.archetype_id,
        demeanor=npc.demeanor,
        voice_tag=npc.voice_tag,
        node_id=npc.home_node,
        motive=npc.motive,
        secrets=[_secret(s) for s in npc.secrets],
    )


def _boss(region: RegionPlan) -> WorldNpc:
    boss = region.boss
    allied = boss.ally_path is not None
    return WorldNpc(
        id=boss_npc_id(region),
        name=boss.name,
        role=BOSS_ROLE,
        archetype_id=boss.monster_id,
        demeanor="guarded" if allied else "hostile",
        node_id=region.gateway.id,
        base=BOSS_ALLY_PATH_BASE if allied else BOSS_HOSTILE_BASE,
        hostile=not allied,
        motive=f"Could be turned: {boss.ally_path}" if allied else "",
    )


def act_quest_events(state: GameState, plan: CampaignPlan, act: int) -> list[AnyEvent]:
    return list[AnyEvent](quest_item_events(state, plan, act))


def install_campaign(state: GameState, plan: CampaignPlan, seed: int) -> list[AnyEvent]:
    if state.campaign is not None:
        raise ValueError("a campaign is already installed")
    npcs = [plan_npc(n) for n in plan.npcs] + [_boss(r) for r in plan.all_regions()]
    clashes = sorted({n.id for n in npcs} & set(state.world.npcs))
    if clashes or len({n.id for n in npcs}) != len(npcs):
        raise ValueError(f"campaign npc ids clash: {clashes or 'boss id'}")
    events: list[AnyEvent] = [
        CampaignInstalled(plan=plan, graph=build_campaign_graph(plan, seed), seed=seed)
    ]
    events += [NpcIntroduced(npc=npc) for npc in npcs]
    events += act_quest_events(state, plan, 1)
    supplies = state.camp_supplies + STARTING_CAMP_SUPPLIES
    events.append(CampSuppliesChanged(delta=STARTING_CAMP_SUPPLIES, camp_supplies=supplies))
    arrival = plan.acts[0].region.arrival.id
    world = state.world
    events.append(
        PartyMoved(from_node=world.current_node, to_node=arrival, scene_index=world.scene_index + 1)
    )
    return events
