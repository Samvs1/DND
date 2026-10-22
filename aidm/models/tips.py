"""The tooltip model (M28.1): a title and one to four short lines, served by GET /api/tips."""

from pydantic import BaseModel, ConfigDict, Field


class Tip(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1)
    lines: tuple[str, ...] = Field(min_length=1, max_length=4)

    @property
    def text(self) -> str:
        """The plain one-paragraph form, e.g. for tests and logs."""
        return f"{self.title}. " + " ".join(self.lines)
