"""Paying an NPC (M29.9a T17, owner rule: a physically possible action happens). Pure.

`pay_events(state, pc_id, npc_id, gold)` serves the typed "pay Rutter 4 gold" / "hand Rutter a
gold piece" (`aidm.dm.pay_intent`). The hero's coins leave by `GoldChanged` and one
`HandedOver(to_id=<the NPC>, gold=n)` records the payment (the reducer adds it to
`WorldNpc.paid`, which a favour's `pay` step reads, `rules.quest_steps`). Silver and copper are
rounded up to whole gold pieces before this, as the shop rounds a price (`gold_for`). A payment
is no deed by itself (DECISIONS M29.9a: gold could farm goodwill); a `pay` step it meets pays
the favour's goodwill.
Only the impossible is refused, each with a plain reason: a hero who is dead or down, an NPC who
is dead or not here, no amount, and more gold than the hero has.

Public API: `PayRefused(detail)`, `gold_for(amount, coin) -> int`, `pay_events(...)`.
"""

import math

from aidm.models.events import AnyEvent, GoldChanged
from aidm.models.item_events import HandedOver
from aidm.models.state import GameState

COIN_GP = {"gold": 1.0, "silver": 0.1, "copper": 0.01}


class PayRefused(ValueError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def gold_for(amount: int, coin: str) -> int:
    """`amount` coins of `coin` in whole gold pieces, rounded up (at least 1)."""
    return max(1, math.ceil(amount * COIN_GP.get(coin, 1.0) - 1e-9))


def pay_events(state: GameState, pc_id: str, npc_id: str, gold: int) -> list[AnyEvent]:
    payer = state.creatures.get(pc_id)
    if payer is None or payer.pc is None or payer.dead or payer.hp <= 0:
        raise PayRefused("Your hero cannot pay anyone right now.")
    npc = state.world.npcs.get(npc_id)
    if npc is None:
        raise PayRefused("There is nobody like that here.")
    if npc.dead:
        raise PayRefused(f"{npc.name} can take nothing any more.")
    if npc.node_id is None or npc.node_id != state.world.current_node:
        raise PayRefused(f"{npc.name} is not here.")
    if gold < 1:
        raise PayRefused("Say how much gold to pay.")
    have = payer.pc.gold
    if gold > have:
        raise PayRefused(f"{payer.name} has only {have} gold.")
    return [
        GoldChanged(creature_id=pc_id, delta=-gold, gold=have - gold),
        HandedOver(creature_id=pc_id, to_id=npc_id, gold=gold),
    ]
