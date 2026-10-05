"""A validation finding reported by a checker instead of an exception (SPEC 9, M5.1/M5.2).

`Problem(code, message, subject)`: `code` is a stable machine tag (e.g. `unreachable_node`),
`message` is a human sentence (fed back to the campaign generator for its retry), `subject` is
the id the finding is about ("" when it concerns the whole thing).
"""

from pydantic import BaseModel, ConfigDict


class Problem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    message: str
    subject: str = ""
