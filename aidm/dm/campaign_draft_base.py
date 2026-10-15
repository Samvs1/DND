"""The shared base of the campaign drafts: repair over reject and name resolution (M5.3, M16.1).

Every draft model trims over-long strings at a word boundary and cuts over-long lists to the
field's own `max_length` before validation (`fit_limits`); min lengths, required fields and
enums still reject. Names resolve leniently (`resolve_name`): the exact name first, then the one
name that holds the written words (a quest against "Skarn" finds "Skarn the Hollow").

Public API:
- `Draft`: the base model of every draft part (repairs over-long text and lists).
- `trim_words(text, limit) -> str`; `fit_limits(data, limits) -> dict` (the repair step).
- `name_key(name) -> str` (the lookup key of a display name);
  `resolve_name(index, name, rivals=()) -> str | None` (lenient lookup in a key -> id index).
- `slug_id(name, taken) -> str`: a plan id for a display name, unique among `taken`.
"""

from __future__ import annotations

import functools
import re
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, model_validator

TRIM_TAIL = " \t\n,;:-"
_LAST_SPACE = re.compile(r"\s\S*$")


def trim_words(text: str, limit: int) -> str:
    """`text` cut to at most `limit` characters at the last word boundary (hard cut if none)."""
    if len(text) <= limit:
        return text
    space = _LAST_SPACE.search(text[: limit + 1])
    head = text[: space.start()] if space is not None and space.start() > 0 else text[:limit]
    return head.rstrip(TRIM_TAIL) or text[:limit]


def fit_limits(data: Mapping[str, Any], limits: Mapping[str, int]) -> dict[str, Any]:
    """A copy of `data` whose strings and lists named in `limits` fit their maximum length."""
    out = dict(data)
    for name, limit in limits.items():
        value = out.get(name)
        if isinstance(value, str):
            out[name] = trim_words(value, limit)
        elif isinstance(value, list) and len(value) > limit:
            out[name] = value[:limit]
    return out


@functools.cache
def _max_lengths(model: type[BaseModel]) -> dict[str, int]:
    out: dict[str, int] = {}
    for name, info in model.model_fields.items():
        for meta in info.metadata:
            limit = getattr(meta, "max_length", None)
            if isinstance(limit, int):
                out[name] = limit
    return out


class Draft(BaseModel):
    """Base of every draft model: over-long text and lists are repaired, not rejected."""

    @model_validator(mode="before")
    @classmethod
    def _fit(cls, data: Any) -> Any:
        if isinstance(data, Mapping):
            return fit_limits(data, _max_lengths(cls))
        return data


def slug_id(name: str, taken: Iterable[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "x"
    used = set(taken)
    candidate, n = base, 2
    while candidate in used:
        candidate, n = f"{base}-{n}", n + 1
    return candidate


def name_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _contains(key: str, written: str) -> bool:
    """True when the name `key` holds every word of `written` in order, as whole words."""
    return bool(written) and f" {written} " in f" {key} "


def _short(written: str) -> str:
    return written.removeprefix("the ") if written != "the" else written


def resolve_name(index: Mapping[str, str], name: str, rivals: Iterable[str] = ()) -> str | None:
    """The exact name, else the one name (of `index` or `rivals`) holding the written words."""
    key = name_key(name)
    if key in index:
        return index[key]
    written = _short(key)
    hits = {v for k, v in index.items() if _contains(k, written)}
    if len(hits) != 1 or any(_contains(r, written) for r in rivals):
        return None
    return hits.pop()
