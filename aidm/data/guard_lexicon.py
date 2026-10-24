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
    # M29.5c (the honest storyteller): what the engine did not resolve is not told as done
    attack_claims: frozenset[str] = frozenset()
    attack_hedges: frozenset[str] = frozenset()
    weapon_nouns: frozenset[str] = frozenset()
    attack_words: dict[str, tuple[str, ...]] = {}
    wound_claims: frozenset[str] = frozenset()
    payment_verbs: frozenset[str] = frozenset()
    coin_nouns: frozenset[str] = frozenset()
    payment_refusals: frozenset[str] = frozenset()
    gear_nouns: frozenset[str] = frozenset()
    gear_modifier_stops: frozenset[str] = frozenset()
    absent_phrases: frozenset[str] = frozenset()
    handover_claims: frozenset[str] = frozenset()
    light_nouns: frozenset[str] = frozenset()
    light_claims: frozenset[str] = frozenset()
    instruction_phrases: frozenset[str] = frozenset()
    instruction_caps: tuple[str, ...] = ()  # all-caps imperative words ("Do NOT")
    epilogue_death_claims: frozenset[str] = frozenset()
    alive_claims: frozenset[str] = frozenset()
    use_verbs: frozenset[str] = frozenset()
    purchase_words: frozenset[str] = frozenset()
    handover_words: frozenset[str] = frozenset()
    kindle_words: frozenset[str] = frozenset()
    # M29.7b (honest storyteller, round 2): blows per creature, light state, place, people
    strike_claims: frozenset[str] = frozenset()
    hit_claims: frozenset[str] = frozenset()
    graze_nouns: frozenset[str] = frozenset()
    blow_exclusions: frozenset[str] = frozenset()
    miss_claims: frozenset[str] = frozenset()
    attack_nouns: frozenset[str] = frozenset()
    kill_claims: frozenset[str] = frozenset()
    past_markers: frozenset[str] = frozenset()
    passive_markers: frozenset[str] = frozenset()
    light_out_claims: frozenset[str] = frozenset()
    light_on_claims: frozenset[str] = frozenset()
    travel_hedges: frozenset[str] = frozenset()
    pickup_claims: frozenset[str] = frozenset()
    pickup_words: frozenset[str] = frozenset()
    absence_claims: frozenset[str] = frozenset()
    whole_claims: frozenset[str] = frozenset()
    group_phrases: frozenset[str] = frozenset()
    race_words: frozenset[str] = frozenset()
    # M29.9c (round 3 T4 T10 T11 T21): attempts, saved spells, falls, refusals, outcomes, joins
    foe_words: tuple[str, ...] = ()
    attempt_claims: frozenset[str] = frozenset()
    harm_claims: frozenset[str] = frozenset()
    fall_claims: frozenset[str] = frozenset()
    down_conditions: frozenset[str] = frozenset()
    refusal_claims: frozenset[str] = frozenset()
    quest_done_claims: frozenset[str] = frozenset()
    quest_failed_claims: frozenset[str] = frozenset()
    quest_undone_claims: frozenset[str] = frozenset()
    join_claims: frozenset[str] = frozenset()

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
