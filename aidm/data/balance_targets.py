"""Typed loader for `data/balance_targets.json` (M29.1). Data only: tuning never touches code.

M31.1d: a target may name the `metric` it bounds (default: its own id), so a second target can
bound the same metric for a narrower group of styles or parties (the master floor).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

TARGETS_PATH = Path(__file__).resolve().parents[2] / "data" / "balance_targets.json"


class Target(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    text: str
    min: float | None = None
    max: float | None = None
    styles: tuple[str, ...] | None = None
    parties: tuple[str, ...] | None = None
    metric: str | None = None

    @property
    def metric_id(self) -> str:
        return self.metric or self.id

    def applies(self, style: str, party: str) -> bool:
        return (self.styles is None or style in self.styles) and (
            self.parties is None or party in self.parties
        )

    def holds(self, value: float) -> bool:
        return (self.min is None or value >= self.min) and (self.max is None or value <= self.max)


class BalanceTargets(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int
    note: str = ""
    targets: tuple[Target, ...]


def load_balance_targets(path: Path = TARGETS_PATH) -> BalanceTargets:
    return BalanceTargets.model_validate(json.loads(path.read_text(encoding="utf-8")))
