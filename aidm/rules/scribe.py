"""The Scribe's revive, pure (M13.1, house rule, GOAL_SCRIBE.md). Data: data/bg3/scribe.json.

A fallen hero (a PC with `dead`) is rewritten into the story for gold, outside combat only. The
price is `base_gp + per_level_gp x level` of the fallen hero; with payment "fallen_first" (owner
choice M20.4) the fallen hero's own purse pays first and the requesting player's own hero pays
the rest from its `gold`; that hero must be standing (alive, above 0 HP). A PC at 0 HP who is
still alive is not fallen (`scribe_not_fallen`). The table-wide blocks come first: a defeated
table (the defeat flow's lock), a paused table, an active fight, nobody fallen.

The revive is `GoldChanged` (the fallen hero's purse, then the payer, each when above 0), one
`ConditionRemoved` per cleared condition name (all but `keep_conditions`), then
`CharacterRewritten` with the restored HP ("half" = ceil(max HP / 2), "one" = 1, "full" = max
HP). THE reducer applies them.

Public API:
- `ScribeRefusal` (the refusal codes, stable strings for the UI and the Scribe's lines),
  `ScribeRefused(reason, detail)`: nothing is spent on a refusal.
- `revive_price(level, table) -> int`, `restored_hp(max_hp, table) -> int`,
  `purse_share(target, cost, table) -> int` (what the fallen hero's purse pays).
- `fallen_heroes(state) -> list[Creature]` (dead PCs, by id).
- `table_block(state, *, paused) -> ScribeRefusal | None`.
- `scribe_view(state, table, *, paused) -> ScribeView` (the public `scribe` state).
- `revive_events(state, payer_id, target_id, table, *, paused=False) -> list[AnyEvent]`.
"""

import math
from enum import StrEnum

from aidm.data.scribe_defs import ScribeTable
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent, ConditionRemoved, GoldChanged
from aidm.models.scribe import CharacterRewritten, FallenHero, ScribeView
from aidm.models.state import Creature, GameState


class ScribeRefusal(StrEnum):
    DEFEATED = "scribe_defeated"
    PAUSED = "scribe_paused"
    IN_COMBAT = "scribe_in_combat"
    NONE_FALLEN = "scribe_none_fallen"
    PAYER_DOWN = "scribe_payer_down"
    UNKNOWN_TARGET = "scribe_unknown_target"
    NOT_FALLEN = "scribe_not_fallen"
    NO_FUNDS = "scribe_no_funds"


class ScribeRefused(ValueError):
    """The Scribe will not (or cannot) rewrite anyone; nothing was spent."""

    def __init__(self, reason: ScribeRefusal, detail: str = "") -> None:
        super().__init__(f"{reason.value}: {detail}" if detail else reason.value)
        self.reason = reason
        self.detail = detail


def revive_price(level: int, table: ScribeTable) -> int:
    return table.base_gp + table.per_level_gp * level


def restored_hp(max_hp: int, table: ScribeTable) -> int:
    match table.restore:
        case "half":
            return max(1, math.ceil(max_hp / 2))
        case "one":
            return 1
        case "full":
            return max_hp


def _level(creature: Creature) -> int:
    return creature.pc.level if creature.pc is not None else 1


def fallen_heroes(state: GameState) -> list[Creature]:
    dead = (c for c in state.creatures.values() if c.pc is not None and c.dead)
    return sorted(dead, key=lambda c: c.id)


def table_block(state: GameState, *, paused: bool) -> ScribeRefusal | None:
    enc = state.encounter
    if state.defeat is not None:
        return ScribeRefusal.DEFEATED
    if paused:
        return ScribeRefusal.PAUSED
    if enc is not None and enc.status is EncounterStatus.ACTIVE:
        return ScribeRefusal.IN_COMBAT
    if not fallen_heroes(state):
        return ScribeRefusal.NONE_FALLEN
    return None


def purse_share(target: Creature, cost: int, table: ScribeTable) -> int:
    """What the fallen hero's own purse pays of `cost` (M20.4, payment "fallen_first")."""
    if table.payment != "fallen_first" or target.pc is None:
        return 0
    return min(target.pc.gold, cost)


def _fallen(c: Creature, table: ScribeTable) -> FallenHero:
    price = revive_price(_level(c), table)
    purse = purse_share(c, price, table)
    return FallenHero(
        creature_id=c.id,
        name=c.name,
        level=_level(c),
        price_gp=price,
        purse_gp=purse,
        due_gp=price - purse,
    )


def scribe_view(state: GameState, table: ScribeTable, *, paused: bool) -> ScribeView:
    block = table_block(state, paused=paused)
    fallen = tuple(_fallen(c, table) for c in fallen_heroes(state))
    return ScribeView(
        available=block is None, reason=block.value if block is not None else None, fallen=fallen
    )


def _payer(state: GameState, payer_id: str) -> Creature:
    payer = state.creatures.get(payer_id)
    if payer is None or payer.pc is None or payer.dead or payer.hp <= 0:
        raise ScribeRefused(ScribeRefusal.PAYER_DOWN, "the one who pays must be standing")
    return payer


def _target(state: GameState, target_id: str) -> Creature:
    target = state.creatures.get(target_id)
    if target is None or target.pc is None:
        raise ScribeRefused(ScribeRefusal.UNKNOWN_TARGET, target_id)
    if not target.dead:
        raise ScribeRefused(ScribeRefusal.NOT_FALLEN, target.name)
    return target


def _cleared(target: Creature, table: ScribeTable) -> list[AnyEvent]:
    names = dict.fromkeys(c.name for c in target.conditions if c.name not in table.keep_conditions)
    return [ConditionRemoved(creature_id=target.id, name=name) for name in names]


def revive_events(
    state: GameState,
    payer_id: str,
    target_id: str,
    table: ScribeTable,
    *,
    paused: bool = False,
) -> list[AnyEvent]:
    block = table_block(state, paused=paused)
    if block is not None:
        raise ScribeRefused(block)
    payer = _payer(state, payer_id)
    target = _target(state, target_id)
    cost = revive_price(_level(target), table)
    purse = purse_share(target, cost, table)
    due = cost - purse
    gold = payer.pc.gold if payer.pc is not None else 0
    if gold < due:
        detail = f"{cost} gp needed, {purse} gp in {target.name}'s purse, {gold} gp carried"
        raise ScribeRefused(ScribeRefusal.NO_FUNDS, detail)
    events: list[AnyEvent] = []
    if purse > 0 and target.pc is not None:
        own = target.pc.gold
        events.append(GoldChanged(creature_id=target.id, delta=-purse, gold=own - purse))
    if due > 0:
        events.append(GoldChanged(creature_id=payer.id, delta=-due, gold=gold - due))
    events.extend(_cleared(target, table))
    hp = restored_hp(target.max_hp, table)
    events.append(CharacterRewritten(target_id=target.id, payer_id=payer.id, cost_gp=cost, hp=hp))
    return events
