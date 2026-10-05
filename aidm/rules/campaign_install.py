"""Install a campaign plan into a game state: the events that make it exist (SPEC 9, M5.3). Pure.

The plan becomes world registry entries (closed world: the cast, the bosses and the act-1 quests
exist only once these events are applied), the campaign graph (travel neighbours and derived
locks, `aidm.session.campaign_apply`) and the first move to act 1's arrival.

Bosses are registered as world NPCs at their gateway (`boss_npc_id(region)`), so the social
rules apply to them: a boss with an ally path starts unfriendly (`BOSS_ALLY_PATH_BASE`) and can
be turned by deeds; a boss without one starts hostile (DECISIONS M5.3).

Public API: `install_campaign(state, plan, seed) -> list[AnyEvent]` (`ValueError` when a campaign
is already installed or an id clashes), `boss_npc_id(region) -> str`, `plan_npc(npc) -> WorldNpc`,
`act_quest_events(plan, act) -> list[AnyEvent]` (the quests of an act, offered).
"""

from aidm.models.campaign import CampaignPlan, NpcPlan, RegionPlan, RevealKind, SecretPlan
from aidm.models.campaign_events import CampaignInstalled
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.models.world import NpcSecret, Quest, QuestState, WorldNpc
from aidm.models.world_events import NpcIntroduced, PartyMoved, QuestUpdated
from aidm.rules.social import band_floor
from aidm.rules.world_graph import build_campaign_graph

BOSS_ROLE = "boss"
BOSS_ALLY_PATH_BASE = -15
BOSS_HOSTILE_BASE = -60


def boss_npc_id(region: RegionPlan) -> str:
    return f"boss-{region.id}"


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


def act_quest_events(plan: CampaignPlan, act: int) -> list[AnyEvent]:
    return [
        QuestUpdated(
            quest=Quest(
                id=q.id,
                title=q.title,
                state=QuestState.OFFERED,
                giver_npc_id=q.giver_npc_id,
                against_npc_id=q.against_npc_id,
            )
        )
        for q in plan.quests
        if q.act == act
    ]


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
    events += act_quest_events(plan, 1)
    arrival = plan.acts[0].region.arrival.id
    world = state.world
    events.append(
        PartyMoved(from_node=world.current_node, to_node=arrival, scene_index=world.scene_index + 1)
    )
    return events
