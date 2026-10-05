"""Value types of the prose guard (SPEC 6.5); the checks themselves live in `aidm.dm.guard`.

Public API:
- `ViolationKind`: UNKNOWN_NAME, DEAD_ACTING, ITEM_DESTROYED, WRONG_IDENTITY, UNLISTED_FEATURE,
  ABSENT_NPC.
- `Violation(kind, span, detail)`: `span` is the offending text as written (a name, a phrase).
- `GuardReport(violations)`: `ok`, `offending` (distinct spans, the terms to scrub from a retry
  context), `correction()` (the instruction for the one regeneration).
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
    def offending(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(v.span for v in self.violations))

    def correction(self) -> str:
        details = "; ".join(dict.fromkeys(v.detail for v in self.violations))
        return (
            "ENGINE GUARD: your narration contradicted the scene manifest or the engine events"
            f" ({details}). Rewrite it naming only listed entities, describing only listed"
            " features and items, and keeping the dead dead."
        )


type ProseCheck = Callable[[str], GuardReport]


def no_guard(text: str) -> GuardReport:
    return GuardReport()
