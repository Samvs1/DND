"""Who and where a typed fight line names (M31.1a V1): the combatants and zones of the active
fight that the words say, in the order they are first said.

- a combatant is named by a word of its name (a hero by the first name), plural "s"/"es"
  and the possessive allowed ("the zombies", M32.1a "the zombie's chest"); the speaker only
  by a self word ("me", "myself");
- a zone by every word of its name or of its id ("the Dry Hummock", "hummock").
Small words ("the", "of", "at" ...) never name anything; neither do the words of a span the
caller already read (a spell's own name: "fire bolt" names no Fire Beetle).

Public API: `tokens(text)`, `name_span(tokens, name)`, `Named(creatures, zones)`,
`named_in_fight(state, actor_id, words)`.
"""

import re
from dataclasses import dataclass

from aidm.models.encounter import Encounter, EncounterStatus
from aidm.models.state import CreatureKind, GameState

_SMALL = frozenset(
    {"the", "a", "an", "of", "my", "his", "her", "their", "our", "at", "on", "to", "in", "into"}
    | {"with", "and", "its", "it", "that", "this", "old", "young", "over", "down", "up"}
)
_SELF = frozenset({"me", "myself", "herself", "himself", "themself", "self"})


def tokens(text: str) -> list[str]:
    flat = text.lower().replace("’", "'").replace("-", " ")
    return re.findall(r"[a-z0-9']+", flat)


def name_span(words: list[str], name: str) -> tuple[int, int] | None:
    """Where the words of `name` stand together in `words` (the first place), else None."""
    want = tokens(name)
    size = len(want)
    if not size:
        return None
    for start in range(len(words) - size + 1):
        if words[start : start + size] == want:
            return start, start + size
    return None


@dataclass(frozen=True)
class Named:
    creatures: tuple[str, ...]
    zones: tuple[str, ...]


def _says(words: list[str], name_word: str) -> int | None:
    for i, w in enumerate(words):
        if w.removesuffix("'s").rstrip("'") in (name_word, f"{name_word}s", f"{name_word}es"):
            return i
    return None


def _creature_at(
    state: GameState, enc: Encounter, actor_id: str, words: list[str]
) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for cid, combatant in enc.combatants.items():
        creature = state.creatures.get(cid)
        if creature is None or creature.dead or combatant.withdrawn is not None:
            continue
        if cid == actor_id:
            at = next((i for i, w in enumerate(words) if w in _SELF), None)
        else:
            names = tokens(creature.name)
            names = names[:1] if creature.kind is CreatureKind.PC else names
            hits = [_says(words, n) for n in names if n not in _SMALL and len(n) > 2]
            at = min((h for h in hits if h is not None), default=None)
        if at is not None:
            found.append((at, cid))
    return found


def _zone_at(enc: Encounter, words: list[str]) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for zone in enc.zone_map.zones:
        for label in (zone.name, zone.id.replace("_", " ")):
            want = [w for w in tokens(label) if w not in _SMALL]
            hits = [_says(words, w) for w in want]
            if want and all(h is not None for h in hits):
                found.append((min(h for h in hits if h is not None), zone.id))
                break
    return found


def named_in_fight(state: GameState, actor_id: str, words: list[str]) -> Named:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        return Named((), ())
    creatures = sorted(_creature_at(state, enc, actor_id, words))
    zones = sorted(_zone_at(enc, words))
    return Named(tuple(c for _, c in creatures), tuple(z for _, z in zones))
