"""Rolling DM memory read by the context builder (SPEC 6.4 section 5, 6.6).

Narration turns are appended by `NarrationRecorded` (`aidm.models.world_events`) and trimmed by
the reducer to the last `MAX_NARRATION_LOG` entries. Scene summaries are appended by
`SceneSummarised` (M4.7, written by `aidm.dm.memory`). The reducer also counts the narrated
turns since the last summary (`turns_since_summary`) and remembers where that run of turns
began (`since_scene`, `since_node`), so the summariser knows what to cover even after the
party moved on.

Public API: `MAX_NARRATION_LOG`, `MAX_UNTOLD`, `SummarySource` (model / template),
`SceneSummary(scene_index, node_id, text, title, entity_ids, turns, source)`, `Memory(summaries,
narration, turns_since_summary, since_scene, since_node, narration_made, untold)`.
M40.4: `SceneSummary.made` and `narration_made` are stamped by the reducer
(`aidm.models.story.StoryStamp`); `narration_made` lines up with `narration` from the end (a
save from before M40.4, or a test that set `narration` alone, has fewer stamps: the older lines
are unstamped).
M43.3 (contract rule D1): `untold` holds the refusals (`ActionImpossible`) logged since the last
`NarrationRecorded`, at most `MAX_UNTOLD`; the reducer appends and clears them, and the context
builder tells them to the next storyteller, whichever events that telling is handed.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.impossible import ActionImpossible
from aidm.models.story import StoryStamp

MAX_NARRATION_LOG = 12
MAX_UNTOLD = 4


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
    made: StoryStamp | None = None  # M40.4: stamped by the reducer


class Memory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summaries: list[SceneSummary] = Field(default_factory=list[SceneSummary])
    narration: list[str] = Field(default_factory=list[str])
    narration_made: list[StoryStamp] = Field(default_factory=list[StoryStamp])  # M40.4
    turns_since_summary: int = Field(default=0, ge=0)
    since_scene: int = Field(default=0, ge=0)
    since_node: str | None = None
    untold: list[ActionImpossible] = Field(default_factory=list[ActionImpossible])  # M43.3
