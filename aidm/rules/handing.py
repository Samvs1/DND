"""Handing things to an NPC: the ONE give path (M23.3, GOAL "Items"). Pure: returns events.

`give_events(state, pc_id, npc_id, thing, tiers)` serves the `give` client command and the typed
"give X to Y" pre-check alike. The receiver must be a known NPC, alive, here and not hostile
(M32.1a X7: a hostile one still takes the keepsake a quest's deliver step brings to them, and a
master who yielded, alive with the region settled, takes what is given); then `thing` is
- a keepsake the hero carries (its id): `KeepsakeGiven` moves it to `WorldNpc.keepsakes` (how a
  `deliver` step completes). No deed by itself (DECISIONS M23.3: keepsakes can be made freely,
  so a keepsake deed could be farmed; finishing the quest pays);
- else an inventory item (its key): the existing `social_deeds.gift_events` (a minor deed, a
  major one for a plot reward item).
Refusals are typed with a player-safe `detail`.

Public API: `GiveRefusal`, `GiveRefused(reason, detail)`, `give_events(...) -> list[AnyEvent]`,
`delivers_to(state, quest_id, npc_id) -> bool`.
"""

from enum import StrEnum

from aidm.data.dm_tiers import DmTiers
from aidm.models.events import AnyEvent
from aidm.models.quest_events import KeepsakeGiven
from aidm.models.quests import StepKind
from aidm.models.state import GameState
from aidm.rules.plan_ids import boss_id_of
from aidm.rules.quest_plan import main_quests
from aidm.rules.social import npc_is_hostile
from aidm.rules.social_deeds import GiftRefused, gift_events


class GiveRefusal(StrEnum):
    NOT_A_HERO = "give_not_a_hero"
    NOT_HERE = "give_not_here"
    HOSTILE = "give_hostile"
    NOT_CARRIED = "give_not_carried"


class GiveRefused(ValueError):
    def __init__(self, reason: GiveRefusal, detail: str) -> None:
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason
        self.detail = detail


def _owed(state: GameState, pc_id: str, npc_id: str, thing: str) -> bool:
    """The keepsake `thing` belongs to a quest whose deliver step brings it to this NPC."""
    pc = state.creatures.get(pc_id)
    held = pc.pc.keepsakes if pc is not None and pc.pc is not None else []
    return delivers_to(state, next((k.quest_id for k in held if k.id == thing), None), npc_id)


def delivers_to(state: GameState, quest_id: str | None, npc_id: str) -> bool:
    """A quest (side, favour or main route) whose deliver step names this NPC."""
    if quest_id is None:
        return False
    quest = state.world.quests.get(quest_id)
    steps = list(quest.steps) if quest is not None else []
    if state.campaign is not None:
        mains = main_quests(state.campaign.plan)
        steps += [s for m in mains if m.id == quest_id for r in m.routes for s in r.steps]
    return any(s.kind is StepKind.DELIVER and s.npc == npc_id for s in steps)


def _yielded(state: GameState, npc_id: str) -> bool:
    """A region master still alive after the region was settled (beaten or won over)."""
    resolved = state.campaign.resolved if state.campaign is not None else {}
    return any(boss_id_of(region) == npc_id for region in resolved)


def _check_receiver(state: GameState, npc_id: str, takes_anyway: bool = False) -> None:
    npc = state.world.npcs.get(npc_id)
    if npc is None:
        raise GiveRefused(GiveRefusal.NOT_HERE, "There is nobody like that here.")
    if npc.dead:
        raise GiveRefused(GiveRefusal.NOT_HERE, f"{npc.name} can take nothing any more.")
    if npc.node_id is None or npc.node_id != state.world.current_node:
        raise GiveRefused(GiveRefusal.NOT_HERE, f"{npc.name} is not here.")
    if npc_is_hostile(npc) and not (takes_anyway or _yielded(state, npc_id)):
        raise GiveRefused(GiveRefusal.HOSTILE, f"{npc.name} will take nothing from you.")


def give_events(
    state: GameState, pc_id: str, npc_id: str, thing: str, tiers: DmTiers
) -> list[AnyEvent]:
    pc = state.creatures.get(pc_id)
    if pc is None or pc.pc is None or pc.dead:
        raise GiveRefused(GiveRefusal.NOT_A_HERO, "Your hero cannot hand anything over.")
    _check_receiver(state, npc_id, _owed(state, pc_id, npc_id, thing))
    if any(k.id == thing for k in pc.pc.keepsakes):
        return [KeepsakeGiven(creature_id=pc_id, keepsake_id=thing, npc_id=npc_id)]
    try:
        return gift_events(state, pc_id, npc_id, thing, tiers)
    except GiftRefused:
        raise GiveRefused(GiveRefusal.NOT_CARRIED, "You do not carry that.") from None
