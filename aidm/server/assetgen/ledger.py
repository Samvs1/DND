"""Spend ledger (logs/asset_spend.json) and the budget guard (Addendum B.4).

Every API call is booked BEFORE it is made, at its worst-case estimate (`reserve`), and updated
AFTER with the actual cost from the response usage (`settle`) or marked failed (`fail`). The
ledger is cumulative across runs: the committed total is the sum of every entry's actual cost, or
its worst-case estimate while no actual cost is known (reserved, failed, or no usage reported).
So a retry is a new booked entry and counts toward the cap, and a failed call is assumed charged.
`reserve` refuses (`BudgetRefused`, nothing written) a call whose worst case would push the
committed total above the cap. Every write is atomic (temp file, then os.replace).

Public API: `Ledger`, `LedgerEntry`, `BudgetGuard`, `BudgetRefused`, `load_ledger`, `save_ledger`.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CAP_EPSILON = 1e-9

type EntryStatus = Literal["reserved", "settled", "failed"]


class LedgerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_id: str
    keys: list[str]
    model: str
    endpoint: str
    size: str
    quality: str
    attempt: int = Field(ge=1)
    status: EntryStatus = "reserved"
    estimate_eur: float = Field(ge=0)
    actual_eur: float | None = None
    usage_reported: bool = False
    at: str = ""

    def committed(self) -> float:
        return self.actual_eur if self.actual_eur is not None else self.estimate_eur


class Ledger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str = "EUR"
    entries: list[LedgerEntry] = Field(default_factory=list)

    def committed_eur(self) -> float:
        return round(sum(e.committed() for e in self.entries), 6)


class BudgetRefused(Exception):
    """A call was refused because its worst case would push the spend above the cap."""

    def __init__(self, keys: list[str], estimate_eur: float, committed_eur: float, cap_eur: float):
        self.keys = keys
        self.estimate_eur = estimate_eur
        self.committed_eur = committed_eur
        self.cap_eur = cap_eur
        super().__init__(
            f"budget cap reached: {committed_eur:.4f} EUR spent + {estimate_eur:.4f} EUR worst "
            f"case > cap {cap_eur:.2f} EUR"
        )


def load_ledger(path: Path) -> Ledger:
    if not path.is_file():
        return Ledger()
    return Ledger.model_validate_json(path.read_text(encoding="utf-8"))


def save_ledger(path: Path, ledger: Ledger) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(ledger.model_dump_json(indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)


class BudgetGuard:
    def __init__(self, path: Path, cap_eur: float, clock: Callable[[], str] = lambda: "") -> None:
        self.path = path
        self.cap_eur = cap_eur
        self.clock = clock

    def committed_eur(self) -> float:
        return load_ledger(self.path).committed_eur()

    def reserve(
        self,
        *,
        keys: list[str],
        model: str,
        endpoint: str,
        size: str,
        quality: str,
        attempt: int,
        estimate_eur: float,
    ) -> str:
        """Book a call at its worst case and return its id; `BudgetRefused` past the cap."""
        ledger = load_ledger(self.path)
        committed = ledger.committed_eur()
        if committed + estimate_eur > self.cap_eur + CAP_EPSILON:
            raise BudgetRefused(keys, estimate_eur, committed, self.cap_eur)
        call_id = f"c{len(ledger.entries) + 1:05d}"
        ledger.entries.append(
            LedgerEntry(
                call_id=call_id,
                keys=list(keys),
                model=model,
                endpoint=endpoint,
                size=size,
                quality=quality,
                attempt=attempt,
                estimate_eur=estimate_eur,
                at=self.clock(),
            )
        )
        save_ledger(self.path, ledger)
        return call_id

    def _update(self, call_id: str, status: EntryStatus, actual: float | None, reported: bool):
        ledger = load_ledger(self.path)
        for entry in ledger.entries:
            if entry.call_id == call_id:
                entry.status = status
                entry.actual_eur = actual
                entry.usage_reported = reported
                break
        else:
            raise KeyError(call_id)
        save_ledger(self.path, ledger)

    def settle(self, call_id: str, actual_eur: float | None) -> None:
        """Book the actual cost; with no reported usage the worst case stays committed."""
        self._update(call_id, "settled", actual_eur, actual_eur is not None)

    def fail(self, call_id: str) -> None:
        """Mark a call failed; its worst case stays committed (it may have been charged)."""
        self._update(call_id, "failed", None, False)
