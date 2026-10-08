"""The editable image price table (data/asset_costs.json) and cost estimates (Addendum B.4).

A call costs text input tokens + reference image tokens + image output tokens, each at the model's
USD per 1M token rate, converted with `usd_to_eur`. The WORST case uses the prompt length divided
by `chars_per_text_token`, `tokens_per_reference_image` per reference, the listed output tokens
for the quality and size, the most expensive price row when the model is unknown (or not chosen
yet, as in a dry run) and the `safety_margin`. The ACTUAL cost uses the usage the response
reported; None when the response reported none (the guard then keeps the worst case).

Public API: `PriceTable`, `ModelPrice`, `load_price_table`, `DEFAULT_PRICE_TABLE`.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from aidm.server.assetgen.provider import ImageUsage

DEFAULT_PRICE_TABLE = Path(__file__).resolve().parents[3] / "data" / "asset_costs.json"
PER_MTOK = 1_000_000


class ModelPrice(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text_input: float = Field(ge=0)
    image_input: float = Field(ge=0)
    image_output: float = Field(ge=0)


class PriceTable(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    usd_to_eur: float = Field(gt=0)
    safety_margin: float = Field(ge=1)
    chars_per_text_token: int = Field(ge=1)
    tokens_per_reference_image: int = Field(ge=0)
    default_quality: str
    sheet_cells: int = Field(ge=1, le=16)
    sheet_size: str
    request_sizes: dict[str, str]
    retired_models: tuple[str, ...]
    models: dict[str, ModelPrice] = Field(min_length=1)
    output_tokens: dict[str, dict[str, int]]

    def price_for(self, model: str | None) -> ModelPrice:
        """The model's row; the most expensive row for an unknown or unchosen model."""
        if model is not None and model in self.models:
            return self.models[model]
        return max(self.models.values(), key=lambda p: (p.image_output, p.image_input))

    def size_for(self, kind: str) -> str:
        return self.request_sizes.get(kind, self.sheet_size)

    def _out_tokens(self, quality: str, size: str) -> int:
        by_size = self.output_tokens.get(quality) or max(
            self.output_tokens.values(), key=lambda t: max(t.values())
        )
        return by_size.get(size, max(by_size.values()))

    def _usd(self, price: ModelPrice, text: int, image_in: int, image_out: int) -> float:
        return (
            text * price.text_input + image_in * price.image_input + image_out * price.image_output
        ) / PER_MTOK

    def worst_case_eur(
        self, *, model: str | None, prompt: str, size: str, quality: str, references: int
    ) -> float:
        """The most a call can cost in EUR (rounded up to 1/10000)."""
        text = len(prompt) // self.chars_per_text_token + 1
        image_in = references * self.tokens_per_reference_image
        usd = self._usd(self.price_for(model), text, image_in, self._out_tokens(quality, size))
        return _round_up(usd * self.safety_margin * self.usd_to_eur)

    def actual_eur(self, model: str, usage: ImageUsage) -> float | None:
        """The call's cost in EUR from the reported usage; None when nothing was reported."""
        if not usage.reported:
            return None
        usd = self._usd(
            self.price_for(model),
            usage.text_input_tokens,
            usage.image_input_tokens,
            usage.output_tokens,
        )
        return _round_up(usd * self.usd_to_eur)


def _round_up(value: float) -> float:
    scaled = value * 10_000
    whole = int(scaled)
    return (whole + (1 if scaled - whole > 1e-9 else 0)) / 10_000


@functools.cache
def load_price_table(path: Path = DEFAULT_PRICE_TABLE) -> PriceTable:
    return PriceTable.model_validate(json.loads(path.read_text(encoding="utf-8")))
