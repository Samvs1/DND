"""Server -> client websocket messages (SPEC 10, 11, 12). Joined into `ServerMsg` by `protocol.py`.

Rules for every payload: public views only (`aidm.models.protocol_views`), no NPC motives or
unrevealed secrets, no hidden features, and never raw exception text (`Notice`/`ErrorMsg` carry
player-safe text). `seq` is the event-log position: a `Snapshot` reflects every event with
`seq < snapshot.seq`; `EventMsg`s carry only PUBLIC events (`aidm.session.public_feed`), so their
seqs have gaps where a private event (campaign setup, an unmet NPC, a hidden feature) was applied.
`StoryHistory` follows the snapshot on every hello so a reload restores the story feed.

Public API: `NoticeKind`, `ErrorCode`, `Welcome`, `Snapshot`, `EventMsg`, `LobbyRoster`,
`AbilityRolls`, `CreationResult`, `QueueState`, `Resolving`, `DiceRoll`, `NarrationChunkMsg`,
`NarrationDone`, `VoteOpen`, `VoteUpdate`, `VoteClosed`, `PendingConfirmationMsg`,
`EncounterOfferMsg`, `CombatState`, `HitChances`, `TurnPrompt`, `ShopStock`,
`LevelUpAvailable`, `Notice`, `ErrorMsg`, `HostStats`, `ChatRelay`, `SuggestionRelay`, `Pong`,
`EpilogueMsg`, `StoryHistory`, `CharacterExport`, `SheetMsg`; M11.2 `FloorState` (holder,
queue, typing; broadcast on every queue or typing change) and `AudioSettingsState` (the
screen's audio, broadcast on every change; also in `PublicState.audio`).
`ErrorMsg.refusal` carries the typed reason of a refused combat command or gear change (a
`RefusalCode` or `EquipRefusal` value) so a client shows its own friendly wording.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.combat import HitChance
from aidm.models.creation import CreationError
from aidm.models.dice import Roll
from aidm.models.leveling import LevelUpOptions
from aidm.models.narration import NarrationTone
from aidm.models.protocol_views import (
    AudioSettings,
    DiceView,
    FloorView,
    PlayerInfo,
    PublicCombat,
    PublicOffer,
    PublicState,
    QueueEntry,
    RollEntry,
    StockLine,
    StoryEntry,
    VoteKind,
)
from aidm.models.sheet import CharacterSheet


class _Server(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class NoticeKind(StrEnum):
    INFO = "info"
    PROGRESS = "progress"
    FALLBACK = "fallback"
    REFUSED = "refused"
    HOST = "host"


class ErrorCode(StrEnum):
    NOT_JOINED = "not_joined"
    NOT_HOST = "not_host"
    WRONG_PHASE = "wrong_phase"
    NO_CHARACTER = "no_character"
    NOT_YOUR_TURN = "not_your_turn"
    ALREADY_QUEUED = "already_queued"
    REFUSED = "refused"
    INVALID = "invalid"
    UNKNOWN_TARGET = "unknown_target"
    NO_VOTE = "no_vote"
    PAUSED = "paused"


class Welcome(_Server):
    type: Literal["welcome"] = "welcome"
    player_id: str
    token: str
    is_host: bool = False


class Snapshot(_Server):
    type: Literal["snapshot"] = "snapshot"
    seq: int = Field(ge=0)
    state: PublicState


class EventMsg(_Server):
    type: Literal["event"] = "event"
    seq: int = Field(ge=0)
    kind: str
    line: str = ""


class LobbyRoster(_Server):
    type: Literal["lobby_roster"] = "lobby_roster"
    players: tuple[PlayerInfo, ...] = ()


class AbilityRolls(_Server):
    type: Literal["ability_rolls"] = "ability_rolls"
    rolls: tuple[Roll, ...] = ()


class CreationResult(_Server):
    type: Literal["creation_result"] = "creation_result"
    ok: bool
    errors: tuple[CreationError, ...] = ()
    sheet: CharacterSheet | None = None


class QueueState(_Server):
    type: Literal["queue_state"] = "queue_state"
    entries: tuple[QueueEntry, ...] = ()
    resolving: QueueEntry | None = None


class Resolving(_Server):
    type: Literal["resolving"] = "resolving"
    entry: QueueEntry


class DiceRoll(_Server):
    type: Literal["dice_roll"] = "dice_roll"
    seq: int = Field(ge=0)
    dice: DiceView


class NarrationChunkMsg(_Server):
    type: Literal["narration_chunk"] = "narration_chunk"
    id: str
    index: int = Field(ge=0)
    text: str
    audio_url: str | None = None
    tone: NarrationTone = NarrationTone.EXPLORATION


class NarrationDone(_Server):
    type: Literal["narration_done"] = "narration_done"
    id: str


class VoteOpen(_Server):
    type: Literal["vote_open"] = "vote_open"
    vote_id: str
    kind: VoteKind
    detail: str = ""
    proposer_id: str
    voters: tuple[str, ...] = ()
    seconds: float = Field(ge=0)


class VoteUpdate(_Server):
    type: Literal["vote_update"] = "vote_update"
    vote_id: str
    ready: tuple[str, ...] = ()
    declined: tuple[str, ...] = ()


class VoteClosed(_Server):
    type: Literal["vote_closed"] = "vote_closed"
    vote_id: str
    passed: bool
    reason: str = ""


class PendingConfirmationMsg(_Server):
    type: Literal["pending_confirmation"] = "pending_confirmation"
    player_id: str
    prompt: str


class EncounterOfferMsg(_Server):
    type: Literal["encounter_offer"] = "encounter_offer"
    offer: PublicOffer


class CombatState(_Server):
    type: Literal["combat_state"] = "combat_state"
    combat: PublicCombat | None = None


class HitChances(_Server):
    type: Literal["hit_chances"] = "hit_chances"
    attacker_id: str
    target_id: str
    chances: tuple[HitChance, ...] = ()


class TurnPrompt(_Server):
    type: Literal["turn_prompt"] = "turn_prompt"
    creature_id: str
    player_id: str | None = None
    seconds: float | None = None


class ShopStock(_Server):
    type: Literal["shop_stock"] = "shop_stock"
    npc_id: str
    npc_name: str = ""
    stock: tuple[StockLine, ...] = ()


class LevelUpAvailable(_Server):
    type: Literal["level_up_available"] = "level_up_available"
    creature_id: str
    level: int = Field(ge=2, le=20)


class Notice(_Server):
    type: Literal["notice"] = "notice"
    kind: NoticeKind = NoticeKind.INFO
    text: str


class ErrorMsg(_Server):
    type: Literal["error"] = "error"
    code: ErrorCode
    text: str
    refusal: str | None = None


class HostStats(_Server):
    type: Literal["host_stats"] = "host_stats"
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    calls: int = Field(default=0, ge=0)


class ChatRelay(_Server):
    type: Literal["chat"] = "chat"
    player_id: str
    name: str
    text: str


class SuggestionRelay(_Server):
    type: Literal["suggestion"] = "suggestion"
    player_id: str
    name: str
    text: str


class Pong(_Server):
    type: Literal["pong"] = "pong"


class EpilogueMsg(_Server):
    type: Literal["epilogue"] = "epilogue"
    text: str


class StoryHistory(_Server):
    """The recent story (narration and public event lines, oldest first), sent after a snapshot,
    plus the recent dice rolls (oldest first)."""

    type: Literal["story_history"] = "story_history"
    entries: tuple[StoryEntry, ...] = ()
    dice: tuple[RollEntry, ...] = ()


class CharacterExport(_Server):
    """The player's hero as a character JSON document (`rules.character_io` format)."""

    type: Literal["character_export"] = "character_export"
    creature_id: str
    name: str
    text: str


class SheetMsg(_Server):
    """The asker's own derived sheet (`request_sheet`), plus what the next level asks when the
    hero can level up now (`level_up`)."""

    type: Literal["sheet"] = "sheet"
    creature_id: str
    sheet: CharacterSheet
    level_up: LevelUpOptions | None = None


class FloorState(_Server):
    type: Literal["floor_state"] = "floor_state"
    floor: FloorView


class AudioSettingsState(_Server):
    type: Literal["audio_settings"] = "audio_settings"
    settings: AudioSettings
