"""Short and long rests for the party (SPEC 7.2, BG3 behaviour; see docs/RULES_DECISIONS.md).

The party is every living PC in the state. Rests are refused with a typed `RestRefused` error
(the tool layer turns it into an in-fiction refusal); otherwise they return events only.

Public API:
- `MAX_SHORT_RESTS` (2 between long rests), `CAMP_SUPPLY_PER_MEMBER` (10: a party of four pays
  40, the BG3 cost of a full long rest), `STARTING_CAMP_SUPPLIES` (40: the pool a campaign
  install gives the party, one long rest for four, M9.2), `SHORT_REST_HEAL_DIVISOR` (2: a
  short rest heals half of max HP, BG3; no hit dice).
- `RestRefusal`: NO_PARTY / NO_SHORT_RESTS_LEFT / NOT_ENOUGH_SUPPLIES.
- `RestRefused(reason, detail, short_by=0)`: ValueError subclass carrying the `reason` (and,
  for missing supplies, how many are missing).
- `rest_refused_text(refused) -> str`: the player line naming the actual reason (M29.5b G34).
- `living_party(state) -> list[Creature]`; `short_rests_left(state) -> int`;
  `long_rest_cost(state) -> int` (= living members x CAMP_SUPPLY_PER_MEMBER).
- `adjust_camp_supplies(state, delta) -> list[AnyEvent]`: `[CampSuppliesChanged]` (loot, shops);
  ValueError if the pool would go below 0; nothing for delta 0.
- `short_rest(state, feats=None) -> list[AnyEvent]`: `ShortRestTaken`, then per living member
  healing of max_hp // 2 (through `resolve_healing`, so a 0-HP member wakes), its SHORT_REST
  resources and, with the feature registry, an automatic Arcane Recovery
  (`feature_build.auto_slot_recovery`: the highest spent slots that fit; docs/DECISIONS.md M7.5b).
- `long_rest(state) -> list[AnyEvent]`: pays the supplies (`LongRestTaken`, which also resets the
  short-rest counter), then per living member: HP to max (death-save state reset), temporary HP
  cleared, every resource restored, ROUNDS and UNTIL_LONG_REST conditions ended, concentration
  ended. The dead are not revived and do not count toward the cost. Gear boons that last until
  the long rest end (`BoonEnded`, M27.3, `aidm.rules.boons.long_rest_boon_events`), and so
  does every carried light (`LightEnded`, M27.12, `long_rest_light_events`).
"""

from enum import StrEnum

from aidm.data.feature_defs import FeatureDef
from aidm.data.registry import Registry
from aidm.models.events import (
    AnyEvent,
    CampSuppliesChanged,
    LongRestTaken,
    ShortRestTaken,
    TempHpSet,
)
from aidm.models.state import Creature, CreatureKind, GameState, RechargeKind
from aidm.rules.boons import long_rest_boon_events, long_rest_light_events
from aidm.rules.concentration import end_concentration
from aidm.rules.condition_timing import long_rest_condition_events
from aidm.rules.damage import resolve_healing
from aidm.rules.feature_build import auto_slot_recovery
from aidm.rules.resources import restore_resources

MAX_SHORT_RESTS = 2
CAMP_SUPPLY_PER_MEMBER = 10
STARTING_CAMP_SUPPLIES = 4 * CAMP_SUPPLY_PER_MEMBER
SHORT_REST_HEAL_DIVISOR = 2


class RestRefusal(StrEnum):
    NO_PARTY = "no_party"
    NO_SHORT_RESTS_LEFT = "no_short_rests_left"
    NOT_ENOUGH_SUPPLIES = "not_enough_supplies"


class RestRefused(ValueError):
    """A rest the rules do not allow right now; `reason` says why."""

    def __init__(self, reason: RestRefusal, detail: str, short_by: int = 0) -> None:
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason
        self.detail = detail
        self.short_by = short_by


def rest_refused_text(refused: RestRefused) -> str:
    if refused.reason is RestRefusal.NOT_ENOUGH_SUPPLIES:
        return (
            f"The party cannot make camp: {refused.short_by} camp supplies short "
            f"({refused.detail}). Buy supplies from a trader or find them as loot."
        )
    if refused.reason is RestRefusal.NO_SHORT_RESTS_LEFT:
        return f"No short rest is left: {refused.detail}. A long rest (make camp) resets them."
    return "No living hero is able to rest."


def living_party(state: GameState) -> list[Creature]:
    return [c for c in state.creatures.values() if c.kind is CreatureKind.PC and not c.dead]


def short_rests_left(state: GameState) -> int:
    return max(0, MAX_SHORT_RESTS - state.short_rests_used)


def long_rest_cost(state: GameState) -> int:
    return len(living_party(state)) * CAMP_SUPPLY_PER_MEMBER


def adjust_camp_supplies(state: GameState, delta: int) -> list[AnyEvent]:
    total = state.camp_supplies + delta
    if total < 0:
        raise ValueError(f"camp supplies would drop to {total}")
    if delta == 0:
        return []
    return [CampSuppliesChanged(delta=delta, camp_supplies=total)]


def _party_or_refuse(state: GameState) -> list[Creature]:
    party = living_party(state)
    if not party:
        raise RestRefused(RestRefusal.NO_PARTY, "no living party member")
    return party


def short_rest(state: GameState, feats: Registry[FeatureDef] | None = None) -> list[AnyEvent]:
    party = _party_or_refuse(state)
    if short_rests_left(state) == 0:
        raise RestRefused(
            RestRefusal.NO_SHORT_RESTS_LEFT, f"{MAX_SHORT_RESTS} short rests already taken"
        )
    events: list[AnyEvent] = [ShortRestTaken(short_rests_used=state.short_rests_used + 1)]
    for member in party:
        events.extend(resolve_healing(member, member.max_hp // SHORT_REST_HEAL_DIVISOR))
        events.extend(restore_resources(member, {RechargeKind.SHORT_REST}))
        if feats is not None:
            events.extend(auto_slot_recovery(member, feats))
    return events


def _long_rest_member(state: GameState, member: Creature) -> list[AnyEvent]:
    events = resolve_healing(member, member.max_hp - member.hp)
    if member.temp_hp:
        events.append(TempHpSet(creature_id=member.id, temp_hp=0))
    events.extend(restore_resources(member, set(RechargeKind)))
    events.extend(long_rest_condition_events(member))
    events.extend(end_concentration(state, member.id, "long rest"))
    return events


def long_rest(state: GameState) -> list[AnyEvent]:
    party = _party_or_refuse(state)
    cost = long_rest_cost(state)
    if state.camp_supplies < cost:
        raise RestRefused(
            RestRefusal.NOT_ENOUGH_SUPPLIES,
            f"the long rest needs {cost}, the party has {state.camp_supplies}",
            short_by=cost - state.camp_supplies,
        )
    events: list[AnyEvent] = [
        LongRestTaken(supplies_spent=cost, camp_supplies=state.camp_supplies - cost)
    ]
    for member in party:
        events.extend(_long_rest_member(state, member))
    return [*events, *long_rest_boon_events(state), *long_rest_light_events(state)]
