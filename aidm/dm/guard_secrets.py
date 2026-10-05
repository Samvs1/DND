"""Secret-leak check of the prose guard (SPEC 6.3 `reveal_secret`, 6.4 item 7, 6.5).

A secret becomes known only through the engine (`reveal_secret` -> `SecretRevealed`). Any prose,
narration or NPC speech, that states an UNREVEALED secret of any NPC is flagged, whoever speaks.
Matching is deterministic: the whole secret text as a phrase, or enough of its distinctive
keywords in one sentence. Keywords are the secret's words of >= `MIN_KEYWORD_LEN` letters that
are not stop words (data/bg3/guard_lexicon.json `secret_stop_words`) and not name or role words
of the world (saying "Mira" or "innkeeper" is not a leak), reduced to a `STEM_LEN` prefix so
"poisoned" matches "poison". One or two keywords must all appear; more need `LEAK_RATIO` of them
(at least 2).

Public API: `SecretKey(npc_id, secret_id, phrase, stems)`, `secret_keys(state, excluded,
stop_words) -> tuple[SecretKey, ...]`, `leaked_secrets(sentence, keys) -> list[Violation]`.
"""

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass

from aidm.dm.guard_types import Violation, ViolationKind
from aidm.models.state import GameState

MIN_KEYWORD_LEN = 4
STEM_LEN = 5
LEAK_RATIO = 0.5
MIN_PHRASE_CHARS = 8
LEAK_DETAIL = "an unrevealed secret was stated; only the engine reveals secrets"
_WORD = re.compile(r"[A-Za-z]+")


@dataclass(frozen=True)
class SecretKey:
    npc_id: str
    secret_id: str
    phrase: str
    stems: frozenset[str]


def _words(text: str) -> list[str]:
    return [w.casefold() for w in _WORD.findall(text.replace("’", "'"))]


def _stems(words: Iterable[str], excluded: frozenset[str], stop: frozenset[str]) -> set[str]:
    return {
        w[:STEM_LEN]
        for w in words
        if len(w) >= MIN_KEYWORD_LEN and w not in stop and w not in excluded
    }


def secret_keys(
    state: GameState, excluded: frozenset[str], stop_words: frozenset[str]
) -> tuple[SecretKey, ...]:
    keys: list[SecretKey] = []
    for npc_id in sorted(state.world.npcs):
        for secret in state.world.npcs[npc_id].secrets:
            if secret.revealed:
                continue
            words = _words(secret.text)
            stems = frozenset(_stems(words, excluded, stop_words))
            keys.append(SecretKey(npc_id, secret.id, " ".join(words), stems))
    return tuple(keys)


def _needed(count: int) -> int:
    return count if count <= 2 else max(2, math.ceil(count * LEAK_RATIO))


def _leaks(key: SecretKey, phrase: str, stems: set[str]) -> bool:
    if len(key.phrase) >= MIN_PHRASE_CHARS and f" {key.phrase} " in f" {phrase} ":
        return True
    return bool(key.stems) and len(key.stems & stems) >= _needed(len(key.stems))


def leaked_secrets(sentence: str, keys: tuple[SecretKey, ...]) -> list[Violation]:
    if not keys:
        return []
    words = _words(sentence)
    phrase = " ".join(words)
    stems = {w[:STEM_LEN] for w in words if len(w) >= MIN_KEYWORD_LEN}
    return [
        Violation(ViolationKind.SECRET_LEAK, f"secret {k.npc_id}/{k.secret_id}", LEAK_DETAIL)
        for k in keys
        if _leaks(k, phrase, stems)
    ]
