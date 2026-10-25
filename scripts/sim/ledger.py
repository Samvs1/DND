"""The running-value ledger check (M35.1, round-6 Y1): every absolute agrees with its delta.

Events that move a number carry both the change and the new value (`GoldChanged.delta` and
`.gold`, `XpGained.amount` and `.xp`, `InventoryChanged.delta` and `.qty`,
`CampSuppliesChanged.delta` and `.camp_supplies`); the reducer sets the new value. A producer
that builds two of them for the same number from ONE snapshot writes a stale value and the
second silently overwrites the first (Y1: two quest payouts in one pass, the second wiped the
first). This replays a log and reports every event whose value is not the running value plus
its change. Test-side only: the sims (`checks.replay_problems`) and the property tests call it;
live play never asserts it.

Public API: `ledger_problems(initial, events, limit=10) -> list[str]` (`initial` is not
modified; at most `limit` problems, ASCII).
"""

from collections.abc import Iterable

from aidm.models.events import (
    AnyEvent,
    CampSuppliesChanged,
    GoldChanged,
    InventoryChanged,
    XpGained,
)
from aidm.models.state import GameState
from aidm.session.reducer import apply


def _pc_value(state: GameState, creature_id: str, field: str, item: str = "") -> int | None:
    creature = state.creatures.get(creature_id)
    pc = creature.pc if creature is not None else None
    if pc is None:
        return None
    if field == "gold":
        return pc.gold
    if field == "xp":
        return pc.xp
    return sum(row.qty for row in pc.inventory if row.item == item)


def _expected(state: GameState, event: AnyEvent) -> tuple[str, int | None, int] | None:
    """(label, the running value plus the change, the value the event writes)."""
    match event:
        case GoldChanged(creature_id=cid, delta=delta, gold=gold):
            before = _pc_value(state, cid, "gold")
            return f"gold_changed {cid}", None if before is None else before + delta, gold
        case XpGained(creature_id=cid, amount=amount, xp=xp):
            before = _pc_value(state, cid, "xp")
            return f"xp_gained {cid}", None if before is None else before + amount, xp
        case InventoryChanged(creature_id=cid, item=item, delta=delta, qty=qty):
            before = _pc_value(state, cid, "item", item)
            return (
                f"inventory_changed {cid} {item}",
                None if before is None else before + delta,
                qty,
            )
        case CampSuppliesChanged(delta=delta, camp_supplies=supplies):
            return "camp_supplies_changed", state.camp_supplies + delta, supplies
        case _:
            return None


def ledger_problems(initial: GameState, events: Iterable[AnyEvent], limit: int = 10) -> list[str]:
    state = initial.model_copy(deep=True)
    problems: list[str] = []
    for index, event in enumerate(events):
        check = _expected(state, event)
        if check is not None:
            label, want, wrote = check
            if want is not None and want != wrote:
                problems.append(f"event {index} {label}: wrote {wrote}, running value {want}")
                if len(problems) >= limit:
                    break
        apply(state, event)
    return [p.encode("ascii", "replace").decode("ascii") for p in problems]
