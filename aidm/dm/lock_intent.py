"""Picking or forcing the lock of a way that cannot be opened by hand (M29.7c R24).

A locked exit (the gateway while the region still hides places, the next region's arrival while
its master is not dealt with) is a progress gate, not a lock: no pick or crowbar opens it. In
round 2 (full 123-125) "I try to pick the lock on the Foundling Vault door" still got a Sleight
of Hand check, 18 passed, and the prose said the lock refused. Such a try gets no check: the
precheck answers with the world reason that says what opens the way
(`aidm.rules.gateway_lock.locked_reason`), like walking into it does.

Read: a lock verb (pick, unlock, force, jimmy, pry, breach; or open, break, bash, kick, smash
with a lock word: lock, door, gate, seal; "pick up" is no lock verb) and every name word of
one locked exit.

Public API: `barred_lock_reason(state, locked_exits, text) -> str | None` (`text` normalised).
"""

import re
from collections.abc import Iterable

from aidm.models.state import GameState
from aidm.rules.gateway_lock import locked_reason
from aidm.rules.scene import node_display_name

STRONG_VERBS = frozenset(
    {"pick", "picks", "picking", "unlock", "unlocks", "unlocking", "force", "forces", "forcing"}
    | {"jimmy", "jimmies", "pry", "prise", "prize", "breach", "breaches"}
)
WEAK_VERBS = frozenset(
    {"open", "opens", "break", "breaks", "bash", "bashes", "kick", "kicks", "smash", "smashes"}
)
LOCK_WORDS = frozenset({"lock", "locks", "door", "doors", "gate", "gates", "seal", "seals"})
_DROP = frozenset({"the", "of", "a", "an"})


def _words(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9']+", text.lower().replace("-", " ")))


def _tries_lock(words: frozenset[str]) -> bool:
    return bool(words & STRONG_VERBS) or bool(words & WEAK_VERBS and words & LOCK_WORDS)


_PICK_UP = re.compile(r"\bpick(?:s|ing)? (?:\S+ ){0,3}up\b")


def barred_lock_reason(state: GameState, locked_exits: Iterable[str], text: str) -> str | None:
    words = _words(_PICK_UP.sub(" ", text.lower()))
    if not _tries_lock(words):
        return None
    for node in locked_exits:
        name = _words(node_display_name(state, node)) - _DROP
        if name and name <= words:
            return locked_reason(state, node)
    return None
