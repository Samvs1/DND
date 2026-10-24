"""The typed lines that need the whole table: travel, rest and a shop open a ready vote (split
out of `session.explore` in M32.1a; SPEC 6.1).

`propose_intent(core, player, entry, intent)` opens the vote with its job
(`party_actions.travel_job`, `rest_job`, `shop_job`) and tells the table who proposed it.
M32.1a X6 (round 5: "back to Hollowgate Cross, then on to the Barrow" stopped at the first
place): a `TravelIntent` with a `goal` further on is walked road by road (`_route_job`); the walk
stops where something needs the party (a fight, an encounter offer, a crossing that asks first,
a road that is shut) and says plainly where it stopped, why, and that the goal lies further on.
M33.1 (ultrareview 4: the next road withdrew a giver's Accept / Not now card): it also stops
at every other state that holds the party (`rules.quest_offers` "busy"): a quest asked here,
an open finale card.

Public API: `propose_intent`, `STOPPED`.
"""

from aidm.dm.precheck import RestIntent, RestKind, ShopIntent, TravelIntent
from aidm.models.protocol_server import NoticeKind
from aidm.models.protocol_views import QueueEntry, VoteKind
from aidm.rules.finale import finale_open
from aidm.rules.scene import node_display_name
from aidm.rules.world_graph import travel_route
from aidm.session import party_actions, votes
from aidm.session.table_core import Job, Player, TableCore

STOPPED = "The party stops at {here}: {why}. {goal} lies further on: travel on when ready."
_WHY_OFFER = "something waits here for your answer"
_WHY_SHUT = "the road on is shut"
_WHY_ASKS = "the next crossing asks you first"
_WHY_QUEST = "{name} asks for your help here"
_WHY_FINALE = "the last choice waits here for your answer"


type VoteIntent = TravelIntent | RestIntent | ShopIntent


def propose_intent(core: TableCore, player: Player, entry: QueueEntry, intent: VoteIntent) -> None:
    if isinstance(intent, TravelIntent):
        goal = intent.goal or intent.node_id
        detail = f"travel to {node_display_name(core.state, goal)}"
        if intent.goal is not None:
            detail += f" (by {node_display_name(core.state, intent.node_id)})"
        _propose(core, player, VoteKind.TRAVEL, detail, _route_job(core, entry.creature_id, intent))
    elif isinstance(intent, RestIntent):
        short = intent.kind is RestKind.SHORT
        kind = VoteKind.SHORT_REST if short else VoteKind.LONG_REST
        detail = "take a short rest" if short else "make camp for a long rest"
        _propose(core, player, kind, detail, party_actions.rest_job(core, intent.kind))
    else:
        npc = core.state.world.npcs[intent.npc_id]
        job = party_actions.shop_job(core, entry.creature_id, intent.npc_id)
        _propose(core, player, VoteKind.SHOP, f"trade with {npc.name}", job)


def _propose(core: TableCore, player: Player, kind: VoteKind, detail: str, job: Job) -> None:
    if votes.open_vote(core, kind, detail, player, job):
        core.notice(None, NoticeKind.INFO, f"{player.name} proposes to {detail}.")


def _stop_reason(core: TableCore, hop: str, last: bool) -> str | None:
    """Why the walk cannot go on after this road (None: it goes on; "": nothing to add)."""
    if core.pending is not None:  # a crossing asks first: its card says why
        return "" if last else _WHY_ASKS
    if core.combat_active():
        return ""  # the fight speaks for itself
    if core.state.world.current_node != hop:
        return _WHY_SHUT
    offer = core.state.campaign.offer if core.state.campaign is not None else None
    if offer is not None and offer.node_id == hop:
        return _WHY_OFFER
    ask = core.state.world.quest_ask
    if ask is not None:
        npc = core.state.world.npcs.get(ask.npc_id)
        return _WHY_QUEST.format(name=npc.name if npc is not None else "Someone")
    return _WHY_FINALE if finale_open(core.state) is not None else None


def _route_job(core: TableCore, actor_id: str, intent: TravelIntent) -> Job:
    async def job() -> None:
        goal, hop = intent.goal, intent.node_id
        while True:
            left = travel_route(core.state.world, core.state.world.current_node, goal or hop)
            await party_actions.travel_job(core, actor_id, hop)()
            why = _stop_reason(core, hop, last=left is None or len(left) <= 1)
            here = core.state.world.current_node
            if goal is None or here == goal:
                return
            route = travel_route(core.state.world, here, goal) if why is None else None
            if why is None and route:
                hop = route[0]
                continue
            if why != "":
                where, there = (
                    node_display_name(core.state, here),
                    node_display_name(core.state, goal),
                )
                text = STOPPED.format(here=where, why=why or _WHY_SHUT, goal=there)
                core.notice(None, NoticeKind.INFO, text)
            return

    return job
