"""Rolling DM memory read by the context builder (SPEC 6.4 section 5, 6.6).

Narration turns are appended by `NarrationRecorded` (`aidm.models.world_events`) and trimmed by
the reducer to the last `MAX_NARRATION_LOG` entries. Scene summaries are appended by
`SceneSummarised` (M4.7, written by `aidm.dm.memory`). The reducer also counts the narrated
turns since the last summary (`turns_since_summary`) and remembers where that run of turns
began (`since_scene`, `since_node`), so the summariser knows what to cover even after the
party moved on.

Public API: `MAX_NARRATION_LOG`, `SummarySource` (model / template), `SceneSummary(scene_index,
node_id, text, title, entity_ids, turns, source)`, `Memory(summaries, narration,
turns_since_summary, since_scene, since_node)`.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

MAX_NARRATION_LOG = 12


class SummarySource(StrEnum):
    MODEL = "model"
    TEMPLATE = "template"


class SceneSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scene_index: int = Field(default=0, ge=0)
    node_id: str | None = None
    text: str = Field(min_length=1)
    title: str = ""
    entity_ids: tuple[str, ...] = ()
    turns: int = Field(default=0, ge=0)
    source: SummarySource = SummarySource.MODEL


class Memory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summaries: list[SceneSummary] = Field(default_factory=list[SceneSummary])
    narration: list[str] = Field(default_factory=list[str])
    turns_since_summary: int = Field(default=0, ge=0)
    since_scene: int = Field(default=0, ge=0)
    since_node: str | None = None
