"""Websocket protocol: the `ClientMsg` and `ServerMsg` discriminated unions (SPEC 10).

The single source of truth for the wire format; `scripts/gen_protocol.py` writes
`aidm/web/protocol.json` and `docs/PROTOCOL.md` from it (the gate fails when they are stale).
Message classes live in `protocol_client.py` and `protocol_server.py`, view payloads in
`protocol_views.py`.

Public API: `AnyClientMsg`, `AnyServerMsg`, `ClientMsg`, `ServerMsg` (annotated with the `type`
discriminator), `CLIENT_MESSAGES`, `SERVER_MESSAGES` (every message class, in declaration
order), `client_adapter`, `server_adapter` (`TypeAdapter`s for parsing and JSON schema).
"""

from typing import Annotated, get_args

from pydantic import BaseModel, Field, TypeAdapter

from aidm.models import protocol_client as c
from aidm.models import protocol_server as s

type AnyClientMsg = (
    c.Hello
    | c.CreateCharacter
    | c.RollAbilities
    | c.SubmitAction
    | c.CombatCommandMsg
    | c.Suggestion
    | c.ConfirmHostile
    | c.CancelHostile
    | c.Vote
    | c.AnswerOffer
    | c.AnswerQuestOffer
    | c.ChooseFinale
    | c.LevelUp
    | c.ShopBuy
    | c.ShopSell
    | c.Give
    | c.Equip
    | c.Unequip
    | c.Drop
    | c.UseItem
    | c.RequestSheet
    | c.RequestHitChances
    | c.Chat
    | c.HostStart
    | c.HostPause
    | c.HostResume
    | c.HostKick
    | c.HostDifficulty
    | c.HostTtsToggle
    | c.HostTurnTimer
    | c.HostSave
    | c.HostLoad
    | c.HostNew
    | c.HostEnd
    | c.HostForceVote
    | c.ExportCharacter
    | c.ImportCharacter
    | c.Ping
    | c.Presented
    | c.DefeatRetry
    | c.DefeatLoad
    | c.DefeatNew
    | c.Typing
    | c.AudioSettingsMsg
    | c.ScribeRevive
    | c.ScribeSkip
    | c.HelpUp
    | c.AskWhatNow
)

type AnyServerMsg = (
    s.Welcome
    | s.Snapshot
    | s.EventMsg
    | s.LobbyRoster
    | s.AbilityRolls
    | s.CreationResult
    | s.QueueState
    | s.Resolving
    | s.PlayerActionMsg
    | s.DiceRoll
    | s.NarrationChunkMsg
    | s.NarrationDone
    | s.VoteOpen
    | s.VoteUpdate
    | s.VoteClosed
    | s.PendingConfirmationMsg
    | s.EncounterOfferMsg
    | s.CombatState
    | s.HitChances
    | s.TurnPrompt
    | s.ShopStock
    | s.LevelUpAvailable
    | s.Notice
    | s.ErrorMsg
    | s.HostStats
    | s.ChatRelay
    | s.SuggestionRelay
    | s.Pong
    | s.EpilogueMsg
    | s.StoryHistory
    | s.CharacterExport
    | s.SheetMsg
    | s.FloorState
    | s.AudioSettingsState
    | s.ScribeLineMsg
    | s.ScribeSkipMsg
    | s.WhatNowAnswer
)

ClientMsg = Annotated[AnyClientMsg, Field(discriminator="type")]
ServerMsg = Annotated[AnyServerMsg, Field(discriminator="type")]

CLIENT_MESSAGES: tuple[type[BaseModel], ...] = get_args(AnyClientMsg.__value__)
SERVER_MESSAGES: tuple[type[BaseModel], ...] = get_args(AnyServerMsg.__value__)

client_adapter: TypeAdapter[AnyClientMsg] = TypeAdapter(ClientMsg)
server_adapter: TypeAdapter[AnyServerMsg] = TypeAdapter(ServerMsg)
