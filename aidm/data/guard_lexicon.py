"""Prose-guard vocabulary: data/bg3/guard_lexicon.json (SPEC 6.5; data over code).

Every list is lowercase; entries with a space are phrases. The guard (`aidm.dm.guard`) reads
them through `guard_lexicon()`; nothing here holds logic.

Public API: `GuardLexicon`, `load_guard_lexicon(path=None)`, `guard_lexicon()` (cached).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator

DEFAULT_GUARD_LEXICON = Path(__file__).resolve().parents[2] / "data" / "bg3" / "guard_lexicon.json"


class GuardLexicon(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = ""
    sentence_starters: frozenset[str]
    allowed_capitalised: frozenset[str]
    titles: frozenset[str]
    person_verbs: frozenset[str]
    action_verbs: frozenset[str]
    death_words: frozenset[str]
    recall_words: frozenset[str]
    destroy_words: frozenset[str]
    negations: frozenset[str]
    item_stop_words: frozenset[str]
    item_synonyms: dict[str, tuple[str, ...]]
    feature_nouns_always: frozenset[str]
    feature_nouns_hidden: frozenset[str]
    hidden_qualifiers: frozenset[str]
    reveal_verbs: frozenset[str]
    body_possessives: frozenset[str]
    crowd_nouns: frozenset[str]
    erase_phrases: frozenset[str]
    class_words: frozenset[str]
    secret_stop_words: frozenset[str] = frozenset()
    death_claims: frozenset[str] = frozenset()
    defeat_claims: frozenset[str] = frozenset()
    rise_claims: frozenset[str] = frozenset()
    blow_claims: frozenset[str] = frozenset()
    death_hedges: frozenset[str] = frozenset()
    pronoun_death_claims: frozenset[str] = frozenset()
    death_soft_claims: frozenset[str] = frozenset()
    death_soft_cues: frozenset[str] = frozenset()
    arrival_phrases: frozenset[str] = frozenset()
    stranger_nouns: frozenset[str] = frozenset()
    entrance_verbs: frozenset[str] = frozenset()
    give_verbs: frozenset[str] = frozenset()
    gain_phrases: frozenset[str] = frozenset()
    reward_nouns: frozenset[str] = frozenset()
    promise_words: frozenset[str] = frozenset()
    speech_verbs: frozenset[str] = frozenset()
    open_claims: frozenset[str] = frozenset()  # M27.5: a lock opened in prose
    lock_failures: frozenset[str] = frozenset()  # M27.5: ...unless the sentence says it held

    @model_validator(mode="after")
    def _check(self) -> GuardLexicon:
        for name, value in self:
            if isinstance(value, frozenset) and any(
                str(w) != str(w).lower() or not str(w).strip() for w in value
            ):
                raise ValueError(f"{name}: lexicon entries must be lowercase and non-empty")
        return self


def load_guard_lexicon(path: Path | None = None) -> GuardLexicon:
    target = path if path is not None else DEFAULT_GUARD_LEXICON
    return GuardLexicon.model_validate(json.loads(target.read_text(encoding="utf-8")))


@functools.cache
def guard_lexicon() -> GuardLexicon:
    return load_guard_lexicon()
