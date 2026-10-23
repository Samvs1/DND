"""Favours: small tasks a present NPC asks in play (M23.5, GOAL "Kinds of quest"). Pure.

A favour is the only quest the AI may register (`offer_favour`); plan quests come from the plan.
It is asked through the SAME card as a side quest (`QuestAsked`), has exactly one typed step and
pays only goodwill with the NPC who asked (`social_deeds.quest_deed_events`, a minor deed; never
XP, gold or items, `quest_rewards`). Rules (`favour_events`, each refusal a `FavourRefused`):
- not during a fight, nor while an encounter offer or another quest card waits for the players;
- the asker is a known NPC standing here, alive, not hostile and not a region boss, and has no
  other favour open or done (each NPC asks one favour);
- at most ONE favour is open (offered or active) at a time;
- the step is one of `FAVOUR_KINDS` (no `free`: the engine closes favours; no `obtain`: nothing
  is placed for a favour); its places and NPCs are known and lie in the party's CURRENT region
  (closed world); `deliver` names a flavour keepsake a hero carries; `clear` is never the
  arrival; the step is not met already (a favour asks for something still to do). M29.9a T17:
  `pay` names the NPC to pay (the asker too) and the price; its `gold` is stored as the total
  that NPC must have been paid (what they had before plus the price), so old coins never count.
The id is `favour-<n>`; title and objective (the step text) are the model's words, shown as
written. Not now withdraws a favour (failed + `withdrawn`, no deed, `rules.quest_offers`); an
offered favour whose card is gone (the party moved on) lapses the same way
(`favour_lapse_events`); a favour is left behind with its region (`rules.quest_leaving`).

Public API: `FAVOUR_KINDS`, `FavourRefused`, `open_favour(state) -> Quest | None`,
`favour_events(state, npc_id, title, step) -> list[AnyEvent]`, `withdrawn(quest) -> Quest`,
`favour_lapse_events(state) -> list[AnyEvent]`.
"""

from aidm.models.campaign import RegionPlan
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent
from aidm.models.quest_events import QuestAsked
from aidm.models.quests import QuestKind, QuestStep, StepKind
from aidm.models.state import GameState
from aidm.models.world import MAX_QUEST_LOG, ClosedReason, Quest, QuestAsk, QuestState, WorldNpc
from aidm.models.world_events import QuestUpdated
from aidm.rules.finale import finale_open
from aidm.rules.plan_ids import boss_npc_id
from aidm.rules.progression import region_of
from aidm.rules.quest_steps import step_met
from aidm.rules.secrets import item_key
from aidm.rules.social import npc_is_hostile

FAVOUR_KINDS = frozenset(
    {
        StepKind.VISIT,
        StepKind.CLEAR,
        StepKind.DEFEAT,
        StepKind.DELIVER,
        StepKind.MEET,
        StepKind.WIN_OVER,
        StepKind.LEARN,
        StepKind.PAY,
    }
)
OPEN = (QuestState.OFFERED, QuestState.ACTIVE)
LET_GO_LINE = "Let go."


class FavourRefused(Exception):
    """The favour cannot be registered; `message` says why in words the model can act on."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def open_favour(state: GameState) -> Quest | None:
    quests = sorted(state.world.quests.values(), key=lambda q: q.id)
    return next((q for q in quests if q.kind is QuestKind.FAVOUR and q.state in OPEN), None)


def _check_moment(state: GameState) -> None:
    enc = state.encounter
    if enc is not None and enc.status is EncounterStatus.ACTIVE:
        raise FavourRefused("no favours during a fight")
    campaign = state.campaign
    asking = state.world.quest_ask is not None or finale_open(state) is not None
    if asking or (campaign is not None and campaign.offer is not None):
        raise FavourRefused("another question is waiting for the players; ask later")
    current = open_favour(state)
    if current is not None:
        raise FavourRefused(f"the favour {current.title!r} is still open; one favour at a time")


def _is_boss(state: GameState, npc_id: str) -> bool:
    campaign = state.campaign
    regions = campaign.plan.all_regions() if campaign is not None else ()
    return any(boss_npc_id(r) == npc_id for r in regions)


def _asker(state: GameState, npc_id: str) -> WorldNpc:
    npc = state.world.npcs.get(npc_id)
    if npc is None or npc.dead:
        raise FavourRefused(f"unknown or dead npc {npc_id!r}; only a present NPC can ask")
    if npc.node_id is None or npc.node_id != state.world.current_node:
        raise FavourRefused(f"{npc.name} is not here; only a present NPC can ask a favour")
    if npc_is_hostile(npc) or _is_boss(state, npc.id):
        raise FavourRefused(f"{npc.name} asks no favours of the party")
    asked = [
        q
        for q in state.world.quests.values()
        if q.kind is QuestKind.FAVOUR
        and q.giver_npc_id == npc.id
        and (q.state is QuestState.COMPLETED or q.state in OPEN)
    ]
    if asked:
        raise FavourRefused(f"{npc.name} already asked the party a favour")
    return npc


def _region(state: GameState) -> RegionPlan | None:
    return region_of(state, state.world.current_node)


def _check_place(state: GameState, node: str, kind: StepKind) -> None:
    region = _region(state)
    if region is not None:
        if all(n.id != node for n in region.nodes()):
            raise FavourRefused(f"{node!r} is not a place of this region; use a known place id")
        if kind is StepKind.CLEAR and node == region.arrival.id:
            raise FavourRefused("there is nothing to clear at the arrival; name another place")
        return
    world = state.world
    if node not in world.node_names and node not in world.neighbours:
        raise FavourRefused(f"unknown place {node!r}; use a known place id")


def _check_npc(state: GameState, npc_id: str, asker: WorldNpc, kind: StepKind) -> None:
    npc = state.world.npcs.get(npc_id)
    if npc is None or npc.dead:
        raise FavourRefused(f"unknown or dead npc {npc_id!r}; name a known, living NPC")
    if npc.id == asker.id and kind is not StepKind.PAY:
        raise FavourRefused("the favour must concern someone other than the asker")
    region = _region(state)
    home = region_of(state, npc.node_id)
    if region is not None and (home is None or home.id != region.id):
        raise FavourRefused(f"{npc.name} is not in this region")


def _carried_flavour(state: GameState, item: str) -> bool:
    wanted = item_key(item)
    return any(
        k.quest_id is None and item_key(k.name) == wanted
        for c in state.creatures.values()
        if c.pc is not None and not c.dead
        for k in c.pc.keepsakes
    )


def _check_step(state: GameState, step: QuestStep, asker: WorldNpc, owner: str) -> None:
    if step.kind not in FAVOUR_KINDS:
        raise FavourRefused(
            f"a favour cannot be a {step.kind.value!r} step; use visit, clear, defeat, deliver,"
            " meet, win_over, learn or pay"
        )
    for node in step.nodes:
        _check_place(state, node, step.kind)
    if step.npc is not None:
        _check_npc(state, step.npc, asker, step.kind)
    if step.kind is StepKind.DELIVER and not _carried_flavour(state, step.item or ""):
        raise FavourRefused("a favour delivers a keepsake a hero carries now (not a quest item)")
    if step_met(state, step, owner):
        raise FavourRefused("that is already done; a favour asks for something still to do")


def _favour_id(state: GameState) -> str:
    n = 1 + sum(1 for q in state.world.quests.values() if q.kind is QuestKind.FAVOUR)
    while f"favour-{n}" in state.world.quests:
        n += 1
    return f"favour-{n}"


def favour_events(state: GameState, npc_id: str, title: str, step: QuestStep) -> list[AnyEvent]:
    _check_moment(state)
    asker = _asker(state, npc_id)
    quest_id = _favour_id(state)
    _check_step(state, step, asker, quest_id)
    payee = state.world.npcs.get(step.npc or "")
    if step.kind is StepKind.PAY and payee is not None:  # the price on top of earlier coins
        step = step.model_copy(update={"gold": step.gold + payee.paid})
    node = asker.node_id
    assert node is not None  # `_asker`: they stand at the party's place
    quest = Quest(
        id=quest_id,
        title=title.strip(),
        state=QuestState.OFFERED,
        giver_npc_id=asker.id,
        kind=QuestKind.FAVOUR,
        objective=step.text,
        steps=(step,),
    )
    ask = QuestAsk(quest_id=quest_id, npc_id=asker.id, node_id=node)
    return [QuestUpdated(quest=quest), QuestAsked(ask=ask)]


def withdrawn(quest: Quest) -> Quest:
    log = (*quest.log, LET_GO_LINE)[-MAX_QUEST_LOG:]
    update = {"state": QuestState.FAILED, "closed_reason": ClosedReason.WITHDRAWN, "log": log}
    return quest.model_copy(update=update)


def favour_lapse_events(state: GameState) -> list[AnyEvent]:
    """An offered favour whose card is gone (the party moved on) is let go: no re-ask exists."""
    ask = state.world.quest_ask
    return [
        QuestUpdated(quest=withdrawn(q))
        for q in sorted(state.world.quests.values(), key=lambda q: q.id)
        if q.kind is QuestKind.FAVOUR
        and q.state is QuestState.OFFERED
        and (ask is None or ask.quest_id != q.id)
    ]
