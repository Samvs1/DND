"""Handing things to an NPC: the ONE give path (M23.3, GOAL "Items"). Pure: returns events.

`give_events(state, pc_id, npc_id, thing, tiers)` serves the `give` client command and the typed
"give X to Y" pre-check alike. The receiver must be a known NPC, alive, here and not hostile;
then `thing` is
- a keepsake the hero carries (its id): `KeepsakeGiven` moves it to `WorldNpc.keepsakes` (how a
  `deliver` step completes). No deed by itself (DECISIONS M23.3: keepsakes can be made freely,
  so a keepsake deed could be farmed; finishing the quest pays);
- else an inventory item (its key): the existing `social_deeds.gift_events` (a minor deed, a
  major one for a plot reward item).
Refusals are typed with a player-safe `detail`.

Public API: `GiveRefusal`, `GiveRefused(reason, detail)`, `give_events(...) -> list[AnyEvent]`.
"""

from enum import StrEnum

from aidm.data.dm_tiers import DmTiers
from aidm.models.events import AnyEvent
from aidm.models.quest_events import KeepsakeGiven
from aidm.models.state import GameState
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


def _check_receiver(state: GameState, npc_id: str) -> None:
    npc = state.world.npcs.get(npc_id)
    if npc is None:
        raise GiveRefused(GiveRefusal.NOT_HERE, "There is nobody like that here.")
    if npc.dead:
        raise GiveRefused(GiveRefusal.NOT_HERE, f"{npc.name} can take nothing any more.")
    if npc.node_id is None or npc.node_id != state.world.current_node:
        raise GiveRefused(GiveRefusal.NOT_HERE, f"{npc.name} is not here.")
    if npc_is_hostile(npc):
        raise GiveRefused(GiveRefusal.HOSTILE, f"{npc.name} will take nothing from you.")


def give_events(
    state: GameState, pc_id: str, npc_id: str, thing: str, tiers: DmTiers
) -> list[AnyEvent]:
    pc = state.creatures.get(pc_id)
    if pc is None or pc.pc is None or pc.dead:
        raise GiveRefused(GiveRefusal.NOT_A_HERO, "Your hero cannot hand anything over.")
    _check_receiver(state, npc_id)
    if any(k.id == thing for k in pc.pc.keepsakes):
        return [KeepsakeGiven(creature_id=pc_id, keepsake_id=thing, npc_id=npc_id)]
    try:
        return gift_events(state, pc_id, npc_id, thing, tiers)
    except GiftRefused:
        raise GiveRefused(GiveRefusal.NOT_CARRIED, "You do not carry that.") from None
