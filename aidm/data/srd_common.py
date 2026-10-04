"""Shared building blocks for the typed SRD entry models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SrdModel(BaseModel):
    """Base for every SRD entry: unknown keys ignored, instances immutable."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)


class ApiRef(SrdModel):
    """A reference to another SRD entry (`index` is the registry key)."""

    index: str
    name: str
    url: str | None = None


class Cost(SrdModel):
    quantity: int
    unit: str
