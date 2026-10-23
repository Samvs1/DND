"""Quests come from people (M23.4, GOAL "Lifecycle"). Pure: returns events.

Nothing is bulk-offered: install and an act change only start the main quest (the quest-progress
backfill) and place the act's quest items.
- Leads (`lead_events`): every side quest of the party's act that nobody asked yet, whose giver
  lives (alive) at ANOTHER place of that region, gets one journal lead "Someone at <place> may
  need help." (no title, no objective). The first settle in a region is its arrival, so leads
  come on first arrival; a `QuestUpdated` of the quest removes its lead (reducer).
- The ask (`ask_events`): on an arrival (a `PartyMoved` in the batch) at a place where a side
  quest's giver is present, alive and not hostile, and that quest is unknown or still offered
  ("Not now" earlier, or an old save's bulk offer), the giver asks: `QuestUpdated(offered)` for an
  unknown quest (kind, objective and steps from `quest_plan`), then `QuestAsked`. One ask per
  arrival (the first quest in plan order); none while an encounter offer waits, a fight runs or
  the finale card is open (M23.9).
- The answer (`answer_events`): Accept -> `QuestUpdated(active)` (a stored quest without steps,
  an old save's, gets its derived steps and objective in that same event); Not now ->
  `QuestAskDeclined` (stays offered, asked again on the next arrival); Not now for a favour
  (M23.5) lets it go (failed + `withdrawn`, no deed: a favour is never asked again).
  `QuestOfferRefused` when that quest is not being asked.

Public API: `QuestOfferRefused`, `LEAD_TEXT`, `LEAD_AGAIN` (a second asker in one place),
`lead_events(state)`, `ask_events(state, batch)`, `answer_events(state, quest_id, accept)`.
"""

from collections.abc import Sequence

from aidm.models.campaign import CampaignPlan, QuestPlan, RegionPlan
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent
from aidm.models.quest_events import QuestAskDeclined, QuestAsked, QuestLeadAdded
from aidm.models.quests import QuestKind
from aidm.models.state import GameState
from aidm.models.world import Quest, QuestAsk, QuestLead, QuestState
from aidm.models.world_events import PartyMoved, QuestUpdated
from aidm.rules.favours import withdrawn
from aidm.rules.finale import finale_open
from aidm.rules.progression import region_of
from aidm.rules.quest_plan import quest_steps, side_world_quest
from aidm.rules.quest_steps import npc_meetable
from aidm.rules.scene import node_display_name

LEAD_TEXT = "Someone at {place} may need help."
LEAD_AGAIN = "Someone else at {place} may need help too."


class QuestOfferRefused(Exception):
    """No such quest is being asked right now."""


def _act_quests(state: GameState) -> tuple[CampaignPlan, RegionPlan, list[QuestPlan]] | None:
    campaign = state.campaign
    here = region_of(state, state.world.current_node)
    if campaign is None or here is None:
        return None
    plan = campaign.plan
    act = next(a for a in plan.acts if a.region.id == here.id)
    return plan, here, [q for q in plan.quests if q.act == act.index]


def lead_events(state: GameState) -> list[AnyEvent]:
    found = _act_quests(state)
    if found is None:
        return []
    _, region, quests = found
    world = state.world
    led = {lead.quest_id for lead in world.leads}
    said = {lead.text for lead in world.leads}
    events: list[AnyEvent] = []
    for quest in quests:
        giver = world.npcs.get(quest.giver_npc_id)
        if quest.id in world.quests or quest.id in led or giver is None or giver.dead:
            continue
        home = giver.node_id
        lives = region_of(state, home)
        if home is None or home == world.current_node or lives is None or lives.id != region.id:
            continue
        place = node_display_name(state, home)
        text = LEAD_TEXT.format(place=place)
        if text in said:  # M29.5b G14: two askers in one place are two different leads
            text = LEAD_AGAIN.format(place=place)
        said.add(text)
        events.append(QuestLeadAdded(lead=QuestLead(quest_id=quest.id, text=text)))
    return events


def _busy(state: GameState) -> bool:
    enc = state.encounter
    fighting = enc is not None and enc.status is EncounterStatus.ACTIVE
    offer = state.campaign is not None and state.campaign.offer is not None
    finale = finale_open(state) is not None  # M23.9: the finale card asks first
    return fighting or offer or finale or state.world.quest_ask is not None


def ask_events(state: GameState, batch: Sequence[AnyEvent]) -> list[AnyEvent]:
    found = _act_quests(state)
    node = state.world.current_node
    arrived = any(isinstance(e, PartyMoved) and e.to_node == node for e in batch)
    if found is None or node is None or not arrived or _busy(state):
        return []
    plan, _, quests = found
    for quest in quests:
        known = state.world.quests.get(quest.id)
        if known is not None and known.state is not QuestState.OFFERED:
            continue
        if not npc_meetable(state, quest.giver_npc_id):
            continue
        events: list[AnyEvent] = []
        if known is None:
            events.append(QuestUpdated(quest=side_world_quest(plan, quest)))
        ask = QuestAsk(quest_id=quest.id, npc_id=quest.giver_npc_id, node_id=node)
        return [*events, QuestAsked(ask=ask)]
    return []


def _accepted(state: GameState, quest: Quest) -> Quest:
    update: dict[str, object] = {"state": QuestState.ACTIVE, "active_since": state.event_count}
    campaign = state.campaign
    plan = campaign.plan if campaign is not None else None
    planned = next((q for q in plan.quests if q.id == quest.id), None) if plan else None
    if plan is not None and planned is not None and not quest.steps:
        update["steps"] = quest_steps(plan, planned)
        update["objective"] = quest.objective or planned.objective
    return quest.model_copy(update=update)


def answer_events(state: GameState, quest_id: str, accept: bool) -> list[AnyEvent]:
    ask = state.world.quest_ask
    quest = state.world.quests.get(quest_id)
    if ask is None or ask.quest_id != quest_id or quest is None:
        raise QuestOfferRefused(quest_id)
    if not accept and quest.kind is QuestKind.FAVOUR:
        return [QuestUpdated(quest=withdrawn(quest))]  # no re-ask for a favour: it is let go
    if not accept:
        return [QuestAskDeclined(quest_id=quest_id)]
    return [QuestUpdated(quest=_accepted(state, quest))]
