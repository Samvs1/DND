"""Small schema pieces shared by the class, race and background overlays (data/bg3).

- `ItemQty(item, qty)`: an SRD equipment index and a count.
- `PickList(choose, options)`: "choose N of these indexes" (skills, tools, languages, abilities).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ItemQty(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    item: str = Field(min_length=1)
    qty: int = Field(default=1, ge=1)


class PickList(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    choose: int = Field(ge=1)
    options: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_options(self) -> PickList:
        if len(set(self.options)) != len(self.options):
            raise ValueError("duplicate options in a pick list")
        if self.choose > len(self.options):
            raise ValueError("cannot choose more options than are offered")
        return self
