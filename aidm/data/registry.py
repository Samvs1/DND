"""Immutable keyed registry of SRD entries."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol


class UnknownEntryError(KeyError):
    """Raised by `Registry.get` for an index that is not registered."""

    def __init__(self, index: str) -> None:
        super().__init__(index)
        self.index = index

    def __str__(self) -> str:
        return f"unknown entry: {self.index!r}"


class Indexed(Protocol):
    @property
    def index(self) -> str: ...


class Registry[T: Indexed]:
    """Read-only lookup of entries by `.index`, preserving source order."""

    __slots__ = ("_items", "_order")

    def __init__(self, entries: Iterable[T]) -> None:
        items: dict[str, T] = {}
        for entry in entries:
            if entry.index in items:
                raise ValueError(f"duplicate index: {entry.index!r}")
            items[entry.index] = entry
        self._items = items
        self._order = tuple(items.values())

    def get(self, index: str) -> T:
        try:
            return self._items[index]
        except KeyError:
            raise UnknownEntryError(index) from None

    def find(self, index: str) -> T | None:
        return self._items.get(index)

    def all(self) -> tuple[T, ...]:
        return self._order

    def filter(self, pred: Callable[[T], bool]) -> tuple[T, ...]:
        return tuple(e for e in self._order if pred(e))

    def __contains__(self, index: object) -> bool:
        return index in self._items

    def __len__(self) -> int:
        return len(self._order)
