"""Value types of the prose guard (SPEC 6.5); the checks themselves live in `aidm.dm.guard`.

Public API:
- `ViolationKind`: UNKNOWN_NAME, DEAD_ACTING, ITEM_DESTROYED, WRONG_IDENTITY, UNLISTED_FEATURE,
  ABSENT_NPC, INVENTED_CROWD, ERASED_PRESENT, SECRET_LEAK (M4.7), LIVING_DECLARED_DEAD and
  UNEARNED_REWARD (M4.8), UNHURT_DECLARED_DOWN (M19.1); M29.5c: UNRESOLVED_BLOW, WRONG_WEAPON,
  UNHURT_WOUNDED, UNPAID, CLAIMED_ITEM, UNMADE_HANDOVER, UNLIT_LIGHT, PLACEHOLDER,
  INSTRUCTION_LEAK; M29.7b: PHANTOM_BLOW, PHANTOM_HIT, FALSE_MISS, WRONG_KILLER, LIGHT_STATE,
  SHORT_TRAVEL, UNMADE_PICKUP, WRONG_COUNT, HURT_TOLD_WHOLE, IDENTIFIER; M29.9c: FLED_TOLD_DEAD,
  REFUSED_HANDOVER, UNMADE_OUTCOME, DENIED_OUTCOME, JOINED_PARTY; M30.1 IMPOSSIBLE_DONE;
  M30.2b UNCAST_SPELL; M31.1c: FOE_COUNT, IMMUNE_HARMED, HIT_TOLD_MISSED, MISS_HARM_UNTOLD,
  FOUND_TAKEN, WRONG_RECIPIENT, QUEST_ACCEPTED, ALLY_DEFEATED; M32.1b: EPILOGUE_PLACE,
  FLED_ALIVE, HELPLESS_ACTING, WRONG_ORDER, COIN_PROMISED, UNASKED_ERRAND, STALE_FOE;
  `SCRUBBED_KINDS` (names removed from a retry).
- `Violation(kind, span, detail)`: `span` is the offending text as written (a name, a phrase).
- `GuardReport(violations)`: `ok`, `scrub_terms` (distinct offending names, removed from the
  retry context), `correction()` (the instruction for the one regeneration; it never repeats
  a scrubbed name).
- `ProseCheck`: `Callable[[str], GuardReport]`, the hook the narrator and NPC voice call on every
  sentence; `no_guard` is the identity check (never flags anything).
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class ViolationKind(StrEnum):
    UNKNOWN_NAME = "unknown_name"
    DEAD_ACTING = "dead_acting"
    ITEM_DESTROYED = "item_destroyed"
    WRONG_IDENTITY = "wrong_identity"
    UNLISTED_FEATURE = "unlisted_feature"
    ABSENT_NPC = "absent_npc"
    INVENTED_CROWD = "invented_crowd"
    ERASED_PRESENT = "erased_present"
    SECRET_LEAK = "secret_leak"
    LIVING_DECLARED_DEAD = "living_declared_dead"
    UNHURT_DECLARED_DOWN = "unhurt_declared_down"
    UNEARNED_REWARD = "unearned_reward"
    FALSE_TRAVEL = "false_travel"
    INVENTED_STRANGER = "invented_stranger"
    DOWNED_RISING = "downed_rising"
    OFFER_BLOW = "offer_blow"
    SPOKE_FOR_NPC = "spoke_for_npc"
    LOCK_OPENED = "lock_opened"
    UNRESOLVED_BLOW = "unresolved_blow"  # M29.5c: the honest storyteller
    WRONG_WEAPON = "wrong_weapon"
    UNHURT_WOUNDED = "unhurt_wounded"
    UNPAID = "unpaid"
    CLAIMED_ITEM = "claimed_item"
    UNMADE_HANDOVER = "unmade_handover"
    UNLIT_LIGHT = "unlit_light"
    PLACEHOLDER = "placeholder"
    INSTRUCTION_LEAK = "instruction_leak"
    PHANTOM_BLOW = "phantom_blow"  # M29.7b: per creature, place, light, people
    PHANTOM_HIT = "phantom_hit"
    FALSE_MISS = "false_miss"
    WRONG_KILLER = "wrong_killer"
    LIGHT_STATE = "light_state"
    SHORT_TRAVEL = "short_travel"
    UNMADE_PICKUP = "unmade_pickup"
    WRONG_COUNT = "wrong_count"
    HURT_TOLD_WHOLE = "hurt_told_whole"
    IDENTIFIER = "identifier"
    FLED_TOLD_DEAD = "fled_told_dead"  # M29.9c: round 3 T4 T10 T11 T21
    REFUSED_HANDOVER = "refused_handover"
    UNMADE_OUTCOME = "unmade_outcome"
    DENIED_OUTCOME = "denied_outcome"
    JOINED_PARTY = "joined_party"
    IMPOSSIBLE_DONE = "impossible_done"  # M30.1: an impossible action told as working
    UNCAST_SPELL = "uncast_spell"  # M30.2b: a spell told cast that the engine never cast
    FOE_COUNT = "foe_count"  # M31.1c: round 4 V17-V20
    IMMUNE_HARMED = "immune_harmed"
    HIT_TOLD_MISSED = "hit_told_missed"
    MISS_HARM_UNTOLD = "miss_harm_untold"
    FOUND_TAKEN = "found_taken"
    WRONG_RECIPIENT = "wrong_recipient"
    QUEST_ACCEPTED = "quest_accepted"
    ALLY_DEFEATED = "ally_defeated"
    EPILOGUE_PLACE = "epilogue_place"  # M32.1b: round 5 X10-X16
    FLED_ALIVE = "fled_alive"
    HELPLESS_ACTING = "helpless_acting"
    WRONG_ORDER = "wrong_order"
    COIN_PROMISED = "coin_promised"
    UNASKED_ERRAND = "unasked_errand"
    STALE_FOE = "stale_foe"


SCRUBBED_KINDS = frozenset({ViolationKind.UNKNOWN_NAME, ViolationKind.ABSENT_NPC})


@dataclass(frozen=True)
class Violation:
    kind: ViolationKind
    span: str
    detail: str


@dataclass(frozen=True)
class GuardReport:
    violations: tuple[Violation, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.violations

    @property
    def scrub_terms(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(v.span for v in self.violations if v.kind in SCRUBBED_KINDS))

    def correction(self) -> str:
        details = "; ".join(
            dict.fromkeys(
                "a person who is not in this scene was named"
                if v.kind in SCRUBBED_KINDS
                else v.detail
                for v in self.violations
            )
        )
        return (
            "ENGINE GUARD: your narration contradicted the scene manifest or the engine events"
            f" ({details}). Rewrite it naming only listed entities, describing only listed"
            " features and items, and keeping the dead dead."
        )


type ProseCheck = Callable[[str], GuardReport]


def no_guard(text: str) -> GuardReport:
    return GuardReport()
