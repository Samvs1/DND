"""Deeds: what the party DOES for or against an NPC, recorded by engine events (SPEC 9 Social).

Deeds are uncapped and the only way past the ally bar (`aidm.rules.social`). Sources:
- quests: completing a quest is a moderate deed for its giver and a moderate deed against the
  NPC it works against; failing it is a minor deed against the giver; a favour (M23.5) done is
  a minor deed for the NPC who asked, and a favour let go or left behind is no deed at all;
- combat help: winning a fight where non-hostile NPCs stand by is a minor deed for each of them
  (the party fought for them);
- gifts: giving an NPC an item the PC carries is a minor deed, a major one for a campaign plot
  item (a quest's reward item).
Points per tier are data (`dm_tiers.json` `deed_points`).

Public API: `QUEST_DEED_TIER`, `FAVOUR_DEED_TIER`, `GiftRefused`,
`quest_deed_events(state, quest, tiers)`, `combat_help_deed_events(state, status, tiers)`,
`gift_events(state, pc_id, npc_id, item, tiers)` (each `-> list[AnyEvent]`).
"""

from aidm.data.dm_tiers import DmTiers
from aidm.models.dm_tiers import XpTier
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent, InventoryChanged
from aidm.models.quests import QuestKind
from aidm.models.state import GameState
from aidm.models.world import Quest, QuestState, WorldNpc
from aidm.rules.dm_tiers import deed_points
from aidm.rules.secrets import item_key
from aidm.rules.social import deed_attitude_events, npc_is_hostile

QUEST_DEED_TIER = XpTier.MODERATE
QUEST_FAILED_TIER = XpTier.MINOR
FAVOUR_DEED_TIER = XpTier.MINOR
COMBAT_HELP_TIER = XpTier.MINOR
GIFT_TIER = XpTier.MINOR
PLOT_GIFT_TIER = XpTier.MAJOR


class GiftRefused(ValueError):
    """The gift cannot be given (no such item carried, NPC absent or hostile)."""


def _deed(state: GameState, npc_id: str | None, points: int, reason: str) -> list[AnyEvent]:
    npc = state.world.npcs.get(npc_id or "")
    return deed_attitude_events(npc, points, reason) if npc is not None else []


def quest_deed_events(state: GameState, quest: Quest, tiers: DmTiers) -> list[AnyEvent]:
    """The deeds of `quest` reaching its (new) state; call before the QuestUpdated is applied."""
    old = state.world.quests.get(quest.id)
    if old is not None and old.state is quest.state:
        return []
    if quest.kind is QuestKind.FAVOUR:  # M23.5: goodwill only, and letting one go costs nothing
        done = quest.state is QuestState.COMPLETED
        points = deed_points(tiers, FAVOUR_DEED_TIER)
        return _deed(state, quest.giver_npc_id, points, f"did favour {quest.id}") if done else []
    if quest.state is QuestState.COMPLETED:
        points = deed_points(tiers, QUEST_DEED_TIER)
        events = _deed(state, quest.giver_npc_id, points, f"completed quest {quest.id}")
        events += _deed(state, quest.against_npc_id, -points, f"quest {quest.id} worked against")
        return events
    if quest.state is QuestState.FAILED:
        points = deed_points(tiers, QUEST_FAILED_TIER)
        return _deed(state, quest.giver_npc_id, -points, f"failed quest {quest.id}")
    return []


def _fought(state: GameState) -> set[str]:
    enc = state.encounter
    if enc is None:
        return set()
    return {c.name for cid, c in state.creatures.items() if cid in enc.combatants}


def combat_help_deed_events(
    state: GameState, status: EncounterStatus, tiers: DmTiers
) -> list[AnyEvent]:
    if status is not EncounterStatus.VICTORY:
        return []
    fought = _fought(state)
    points = deed_points(tiers, COMBAT_HELP_TIER)
    events: list[AnyEvent] = []
    for npc in sorted(state.world.npcs.values(), key=lambda n: n.id):
        bystander = npc.node_id == state.world.current_node and npc.name not in fought
        if bystander and not npc_is_hostile(npc):
            events.extend(deed_attitude_events(npc, points, "the party fought for them"))
    return events


def _plot_items(state: GameState) -> set[str]:
    campaign = state.campaign
    if campaign is None:
        return set()
    return {item_key(q.reward_item) for q in campaign.plan.quests if q.reward_item}


def _receiver(state: GameState, npc_id: str) -> WorldNpc:
    npc = state.world.npcs.get(npc_id)
    if npc is None or npc.node_id != state.world.current_node:
        raise GiftRefused("that person is not here")
    if npc_is_hostile(npc):
        raise GiftRefused(f"{npc.name} refuses anything from the party")
    return npc


def gift_events(
    state: GameState, pc_id: str, npc_id: str, item: str, tiers: DmTiers
) -> list[AnyEvent]:
    npc = _receiver(state, npc_id)
    pc = state.creatures.get(pc_id)
    data = pc.pc if pc is not None and not pc.dead else None
    entry = next((e for e in data.inventory if e.item == item), None) if data else None
    if entry is None:
        raise GiftRefused(f"{pc_id!r} does not carry {item!r}")
    tier = PLOT_GIFT_TIER if item_key(item) in _plot_items(state) else GIFT_TIER
    take = InventoryChanged(creature_id=pc_id, item=item, delta=-1, qty=entry.qty - 1)
    deed = deed_attitude_events(npc, deed_points(tiers, tier), f"gift: {item}")
    return [take, *deed]
