"""Party defeat (M11.1, DECISIONS M11.1): the defeat record, its event and the retry markers.

Public API:
- `DefeatSource`: where the defeat text came from ("model", "template" or "mixed").
- `DefeatState(text, source, place)`: `GameState.defeat`; while it is set the table is DEFEATED
  (a reload of a defeated save stays defeated).
- `PartyDefeated(text, source, place)`: the party was wiped (`aidm.rules.party_wipe`); `text` is
  the guarded defeat epilogue. Part of `aidm.models.events.AnyEvent` (`DefeatEvents`), applied by
  THE reducer. A retry truncates the log BEFORE this event, so it simply disappears.
- `CheckpointKind`, `Checkpoint(seq, label, kind, created)`: a retry marker; the state at the
  marker is the replay of the first `seq` events of the campaign (absolute `event_count`).
- `CheckpointFile(checkpoints, retries)`: `saves/<campaign_id>/checkpoints.json`; `retries`
  counts the retries taken, so each retry reseeds the dice differently.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

type DefeatSource = Literal["model", "template", "mixed"]
type CheckpointKind = Literal["arrival", "fight"]

MAX_CHECKPOINTS = 10


class DefeatState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1)
    source: DefeatSource = "template"
    place: str = ""


class PartyDefeated(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["party_defeated"] = "party_defeated"
    text: str = Field(min_length=1)
    source: DefeatSource = "template"
    place: str = ""


DefeatEvents = PartyDefeated


class Checkpoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int = Field(ge=0)
    label: str = Field(min_length=1)
    kind: CheckpointKind
    created: str = ""


class CheckpointFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checkpoints: list[Checkpoint] = Field(default_factory=list[Checkpoint])
    retries: int = Field(default=0, ge=0)
