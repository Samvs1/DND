"""Rolling DM memory read by the context builder (SPEC 6.4 section 5, 6.6).

M4.3 adds the shape with defaults; M4.7 (summariser, fact ledger retrieval) fills
`summaries`. Narration turns are appended by `NarrationRecorded` (`aidm.models.world_events`)
and trimmed by the reducer to the last `MAX_NARRATION_LOG` entries.

Public API: `MAX_NARRATION_LOG`, `SceneSummary(scene_index, node_id, text)`,
`Memory(summaries, narration)`.
"""

from pydantic import BaseModel, ConfigDict, Field

MAX_NARRATION_LOG = 12


class SceneSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scene_index: int = Field(default=0, ge=0)
    node_id: str | None = None
    text: str = Field(min_length=1)


class Memory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summaries: list[SceneSummary] = Field(default_factory=list[SceneSummary])
    narration: list[str] = Field(default_factory=list[str])
