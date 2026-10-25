"""Paying out a reward (loot, a quest, a milestone) as events: ONE path for every source.

A `Payout` is plain numbers and item ids decided by the engine tables. `payout_events` shares it
among the living player characters: every PC gets `xp_each` (with the level-up flag of
`rules.leveling.gain_xp`), gold is split evenly (the remainder goes to the first PCs by id), items
go round-robin, camp supplies join the party pool. A log-only `RewardGranted` comes first so
narration and the epilogue can say what was earned.

Public API:
- `Payout(xp_each, gold_total, items, supplies)`: frozen; `is_empty`.
- `reward_party(state) -> list[Creature]`: living player characters sorted by id.
- `gold_shares(total, count) -> list[int]`: the even split (sums to `total`).
- `payout_events(state, payout, source, kind, catalogue) -> list[AnyEvent]`: `[]` without a
  living PC or an empty payout. The new values are read from `state`: a caller that joins
  several payouts from one state runs `rules.running_totals.chain_totals` over the result.
"""

from dataclasses import dataclass
from typing import Literal

from aidm.data.item_catalogue import CatalogueItem
from aidm.data.registry import Registry
from aidm.models.events import AnyEvent, GoldChanged
from aidm.models.state import Creature, GameState
from aidm.models.world_events import RewardGranted
from aidm.rules.item_grants import gain_item_events
from aidm.rules.leveling import gain_xp


@dataclass(frozen=True)
class Payout:
    xp_each: int = 0
    gold_total: int = 0
    items: tuple[str, ...] = ()
    supplies: int = 0

    @property
    def is_empty(self) -> bool:
        return not (self.xp_each or self.gold_total or self.items or self.supplies)


def reward_party(state: GameState) -> list[Creature]:
    pcs = [c for c in state.creatures.values() if c.pc is not None and not c.dead]
    return sorted(pcs, key=lambda c: c.id)


def gold_shares(total: int, count: int) -> list[int]:
    if count <= 0:
        return []
    base, extra = divmod(total, count)
    return [base + (1 if i < extra else 0) for i in range(count)]


def payout_events(
    state: GameState,
    payout: Payout,
    source: str,
    kind: Literal["loot", "quest", "milestone"],
    catalogue: Registry[CatalogueItem],
) -> list[AnyEvent]:
    party = reward_party(state)
    if not party or payout.is_empty:
        return []
    gold_each = payout.gold_total // len(party)
    events: list[AnyEvent] = [
        RewardGranted(
            source=source,
            kind=kind,
            xp_each=payout.xp_each,
            gold_each=gold_each,
            items=payout.items,
        )
    ]
    if payout.xp_each:
        for pc in party:
            events.extend(gain_xp(pc, payout.xp_each))
    for pc, share in zip(party, gold_shares(payout.gold_total, len(party)), strict=True):
        if share and pc.pc is not None:
            events.append(GoldChanged(creature_id=pc.id, delta=share, gold=pc.pc.gold + share))
    grants = [(party[i % len(party)].id, item, 1) for i, item in enumerate(payout.items)]
    events.extend(gain_item_events(state, grants, catalogue, extra_supplies=payout.supplies))
    return events
