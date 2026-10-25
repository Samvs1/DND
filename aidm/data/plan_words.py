"""Word sets the campaign-plan repairs read: data/bg3/plan_words.json (M36.1, moved out of the
typed-intent lexicon; data over code).

Shape: `come_back_words`: the lowercase words that say a quest giver wants the party to come back
or bring something back (`aidm.rules.plan_tasks.come_back`).

Public API: `PlanWords`, `load_plan_words(path=None)`, `plan_words()` (default, cached).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator

DEFAULT_PLAN_WORDS = Path(__file__).resolve().parents[2] / "data" / "bg3" / "plan_words.json"


class PlanWords(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = ""
    come_back_words: frozenset[str]

    @field_validator("come_back_words")
    @classmethod
    def _lowercase_words(cls, words: frozenset[str]) -> frozenset[str]:
        if not words or any(not w or w != w.lower() or " " in w for w in words):
            raise ValueError("come_back_words must be non-empty lowercase single words")
        return words


def load_plan_words(path: Path | None = None) -> PlanWords:
    raw = json.loads((path or DEFAULT_PLAN_WORDS).read_text(encoding="utf-8"))
    return PlanWords.model_validate(raw)


@functools.cache
def plan_words() -> PlanWords:
    return load_plan_words()
