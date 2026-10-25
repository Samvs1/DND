"""Running totals for a batch built from ONE snapshot (M35.1, round-6 Y1). Pure.

A number-moving event carries its change AND the new value (`GoldChanged.delta`/`.gold`,
`XpGained.amount`/`.xp`, `InventoryChanged.delta`/`.qty`, `CampSuppliesChanged.delta`/
`.camp_supplies`), and the reducer sets the new value. A producer that joins several
payouts read from the same state (two quests finishing in one pass, a region milestone and a
spoke milestone) would write each new value from the snapshot, so the last one silently
overwrote the others (Y1: each hero lost a whole quest's gold and XP). `chain_totals` rewrites
the new values in order so each builds on the ones before it; the changes are kept as they
are. A level-up flag (`LevelUpReady`) is re-derived from the running XP by
`rules.leveling.gain_xp` (one rule), so a flag is neither doubled nor missed.

Every rules function that joins more than one producer's events calls this on its result
(`quest_progress`, `quest_rewards.resolution_reward_events`, `milestones.milestone_events`,
`loot.end_encounter_with_loot`); the sims and the property tests check every log
(`scripts/sim/ledger.py`).

Public API: `chain_totals(state, events) -> list[AnyEvent]`.
"""

from collections.abc import Sequence

from aidm.models.events import (
    AnyEvent,
    CampSuppliesChanged,
    GoldChanged,
    InventoryChanged,
    LongRestTaken,
    XpGained,
)
from aidm.models.state import GameState
from aidm.models.world_events import LevelUpReady
from aidm.rules.item_grants import carried_qty
from aidm.rules.leveling import gain_xp


class _Running:
    def __init__(self, state: GameState) -> None:
        self.state = state
        self.gold: dict[str, int] = {}
        self.xp: dict[str, int] = {}
        self.qty: dict[tuple[str, str], int] = {}
        self.supplies = state.camp_supplies

    def gold_event(self, event: GoldChanged) -> AnyEvent:
        creature = self.state.creatures.get(event.creature_id)
        if creature is None or creature.pc is None:
            return event
        total = self.gold.get(event.creature_id, creature.pc.gold) + event.delta
        self.gold[event.creature_id] = total
        return GoldChanged.model_validate({**event.model_dump(), "gold": total})

    def xp_events(self, event: XpGained) -> list[AnyEvent]:
        creature = self.state.creatures.get(event.creature_id)
        if creature is None or creature.pc is None:
            return [event]
        before = self.xp.get(event.creature_id, creature.pc.xp)
        self.xp[event.creature_id] = before + event.amount
        return gain_xp(creature, event.amount, already=before - creature.pc.xp)

    def item_event(self, event: InventoryChanged) -> AnyEvent:
        creature = self.state.creatures.get(event.creature_id)
        if creature is None or creature.pc is None:
            return event
        key = (event.creature_id, event.item)
        total = self.qty.get(key, carried_qty(creature, event.item)) + event.delta
        self.qty[key] = total
        return InventoryChanged.model_validate({**event.model_dump(), "qty": total})

    def supplies_event(self, event: CampSuppliesChanged) -> AnyEvent:
        self.supplies += event.delta
        return CampSuppliesChanged.model_validate(
            {**event.model_dump(), "camp_supplies": self.supplies}
        )


def chain_totals(state: GameState, events: Sequence[AnyEvent]) -> list[AnyEvent]:
    running = _Running(state)
    out: list[AnyEvent] = []
    for event in events:
        match event:
            case GoldChanged():
                out.append(running.gold_event(event))
            case XpGained():
                out.extend(running.xp_events(event))
            case LevelUpReady():
                pass  # re-derived right after its XpGained from the running XP
            case InventoryChanged():
                out.append(running.item_event(event))
            case CampSuppliesChanged():
                out.append(running.supplies_event(event))
            case LongRestTaken(camp_supplies=supplies):
                running.supplies = supplies
                out.append(event)
            case _:
                out.append(event)
    return out
