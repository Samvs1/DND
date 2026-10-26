"""When a story record was made (M40.4): pydantic only.

A story record is model-written text the state keeps and later prompts, the journal and the
epilogue show again: a ledger fact (`world.Fact`), a scene summary (`memory.SceneSummary`), a
narrated turn (`memory.Memory.narration`) and a place description (`world.World.descriptions`).
The reducer stamps each one when its event is applied (`StoryStamp(seq, scene)`: the event's
seq and the scene index then), so a replay stamps the same values and an old save gets its
stamps on load (the log is replayed from `initial.json`). A record without a stamp (made before
M40.4 in a snapshot-only save) counts as made before every logged change.
`aidm.rules.story_records` decides from the stamp whether a record is shown dated or left out.

Public API: `StoryStamp(seq, scene)`.
"""

from pydantic import BaseModel, ConfigDict, Field


class StoryStamp(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int = Field(ge=0)
    scene: int = Field(default=0, ge=0)
