"""Table actor state and its outbound plumbing (SPEC 5 Concurrency, 10). See `table.py`.

`TableCore` holds everything one table owns: the `GameState` (mutated ONLY through `apply`,
which runs THE reducer, appends a `LoggedEvent` with a monotonic `seq` and broadcasts the
public event line plus any dice), the seats (`Player`), the subscriber queues of the open
connections, the exploration queue, the open vote, a pending hostile act, the combat segment
awaiting narration and the turn timer. Handlers in `lobby`, `explore`, `votes`,
`combat_flow`, `party_actions` and `host` take a `TableCore` and never import `table.py`.

Public API: `Player`, `TableConfig`, `TtsHook`, `no_tts`, `Job`, `ClientIn`, `Closed`,
`TimerFired`, `Inbound`, `PendingHostile`, `OpenVote`, `TableCore`.
"""

import asyncio
import logging
import random
import secrets
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from aidm.dm.campaign_gen import CAMPAIGN_TIMEOUT_S
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_types import ToolCall
from aidm.dm.tool_context import ToolRegistries, tool_registries
from aidm.models.dice import Roll
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent, LoggedEvent
from aidm.models.narration import NarrationTone
from aidm.models.protocol import AnyClientMsg, AnyServerMsg
from aidm.models.protocol_server import (
    DiceRoll,
    ErrorCode,
    ErrorMsg,
    LevelUpAvailable,
    LobbyRoster,
    Notice,
    NoticeKind,
    QueueState,
    Snapshot,
)
from aidm.models.protocol_views import PlayerInfo, QueueEntry, TablePhase, VoteKind, VoteView
from aidm.models.state import Creature, GameState
from aidm.models.world_events import LevelUpReady
from aidm.session.persistence import CampaignStore, SeatRecord, TableMeta, new_game_state
from aidm.session.reducer import apply as reduce
from aidm.session.table_clock import Clock, LoopClock, TimerHandle
from aidm.session.views import dice_view, event_message, public_state

type TtsHook = Callable[[str, NarrationTone], Awaitable[str | None]]
type Job = Callable[[], Awaitable[None]]
_LOG = logging.getLogger(__name__)


async def no_tts(text: str, tone: NarrationTone) -> str | None:
    """The M6 TTS hook: no audio (M8 plugs the Fish Audio adapter in here)."""
    return None


@dataclass(frozen=True)
class TableConfig:
    clock: Clock = field(default_factory=LoopClock)
    vote_seconds: float = 30.0
    turn_seconds: float | None = 90.0
    campaign_timeout_s: float = CAMPAIGN_TIMEOUT_S
    tts: TtsHook = no_tts
    regs: ToolRegistries | None = None
    store: CampaignStore | None = None
    new_state: Callable[[], GameState] = new_game_state
    tts_enabled: bool = False


@dataclass
class Player:
    id: str
    name: str
    token: str
    is_host: bool = False
    creature_id: str | None = None
    conns: set[str] = field(default_factory=set[str])

    @property
    def connected(self) -> bool:
        return bool(self.conns)

    def info(self) -> PlayerInfo:
        return PlayerInfo(
            id=self.id,
            name=self.name,
            is_host=self.is_host,
            connected=self.connected,
            creature_id=self.creature_id,
        )


@dataclass(frozen=True)
class ClientIn:
    conn_id: str
    msg: AnyClientMsg


@dataclass(frozen=True)
class Closed:
    conn_id: str


@dataclass(frozen=True)
class TimerFired:
    kind: str
    key: str


type Inbound = ClientIn | Closed | TimerFired


@dataclass(frozen=True)
class PendingHostile:
    player_id: str
    actor_id: str
    call: ToolCall
    prompt: str


@dataclass
class OpenVote:
    id: str
    kind: VoteKind
    detail: str
    proposer_id: str
    voters: list[str]
    on_pass: Job
    ready: set[str] = field(default_factory=set[str])
    declined: set[str] = field(default_factory=set[str])
    seconds: float = 0.0
    timer: TimerHandle | None = None

    def view(self) -> VoteView:
        return VoteView(
            vote_id=self.id,
            kind=self.kind,
            detail=self.detail,
            proposer_id=self.proposer_id,
            voters=tuple(self.voters),
            ready=tuple(sorted(self.ready)),
            declined=tuple(sorted(self.declined)),
            seconds=self.seconds,
        )


class TableCore:
    def __init__(self, state: GameState, llm: LlmClient, config: TableConfig | None = None) -> None:
        self.state = state
        self.initial = state.model_copy(deep=True)
        self.llm = llm
        self.config = config if config is not None else TableConfig()
        self.regs = self.config.regs if self.config.regs is not None else tool_registries()
        self.rng = random.Random(state.seed)
        self.creation_rng = random.Random(f"{state.seed}:creation")
        self.log: list[LoggedEvent] = []
        self.players: dict[str, Player] = {}
        self.outboxes: dict[str, asyncio.Queue[AnyServerMsg]] = {}
        self.conn_player: dict[str, str] = {}
        self.phase = TablePhase.PLAY if state.world.current_node else TablePhase.LOBBY
        self.paused = False
        self.queue: deque[QueueEntry] = deque()
        self.resolving: QueueEntry | None = None
        self.resolver_scheduled = False
        self.vote: OpenVote | None = None
        self.pending: PendingHostile | None = None
        self.in_combat = False
        self.segment: list[AnyEvent] = []
        self.turn_key: str | None = None
        self.turn_timer: TimerHandle | None = None
        self.issued_rolls: dict[str, list[Roll]] = {}
        self.inbox: asyncio.Queue[Inbound] = asyncio.Queue()
        self.jobs: asyncio.Queue[Job] = asyncio.Queue()
        self.next_counter = 1
        self.tts_enabled = self.config.tts_enabled
        self.resume_combat = False
        self.kicked: set[str] = set()
        self.unsaved: list[LoggedEvent] = []
        self.save_warned = False

    # --- ids, seats, lookups -------------------------------------------------------------

    def next_id(self, prefix: str) -> str:
        self.next_counter += 1
        return f"{prefix}{self.next_counter - 1}"

    def new_player(self, name: str) -> Player:
        player = Player(
            id=self.next_id("p"),
            name=name.strip() or "Adventurer",
            token=secrets.token_urlsafe(16),
            is_host=not self.players,
        )
        self.players[player.id] = player
        return player

    def player_for(self, conn_id: str) -> Player | None:
        pid = self.conn_player.get(conn_id)
        return self.players.get(pid) if pid is not None else None

    def owner_of(self, creature_id: str | None) -> Player | None:
        if creature_id is None:
            return None
        return next((p for p in self.players.values() if p.creature_id == creature_id), None)

    def living_pc(self, player: Player) -> Creature | None:
        creature = self.state.creatures.get(player.creature_id or "")
        if creature is None or creature.pc is None or creature.dead:
            return None
        return creature

    def combat_active(self) -> bool:
        enc = self.state.encounter
        return enc is not None and enc.status is EncounterStatus.ACTIVE

    # --- the ONE mutation path -----------------------------------------------------------

    def apply(self, event: AnyEvent) -> None:
        seq = self.state.event_count
        reduce(self.state, event)
        self.record(event, seq)

    def apply_all(self, events: list[AnyEvent]) -> list[AnyEvent]:
        for event in events:
            self.apply(event)
        return events

    def record(self, event: AnyEvent, seq: int) -> None:
        """Log and broadcast an event the reducer already applied (the combat runner's hook)."""
        logged = LoggedEvent(seq=seq, event=event)
        self.log.append(logged)
        self.unsaved.append(logged)
        if self.in_combat:
            self.segment.append(event)
        self.broadcast(event_message(self.state, seq, event))
        dice = dice_view(event)
        if dice is not None:
            self.broadcast(DiceRoll(seq=seq, dice=dice))
        if isinstance(event, LevelUpReady):
            owner = self.owner_of(event.creature_id)
            if owner is not None:
                msg = LevelUpAvailable(creature_id=event.creature_id, level=event.level)
                self.send(owner.id, msg)

    # --- persistence (M6.3) --------------------------------------------------------------

    def table_meta(self) -> TableMeta:
        seats = [
            SeatRecord(
                id=p.id, name=p.name, token=p.token, is_host=p.is_host, creature_id=p.creature_id
            )
            for p in self.players.values()
        ]
        return TableMeta(seats=seats, next_id=self.next_counter, tts_enabled=self.tts_enabled)

    def autosave(self, *, force: bool = False) -> bool:
        """Append the unsaved events (fsync) and rewrite snapshot + table metadata.

        Called after every job and seat change. A failing disk never stops the game: the events
        stay buffered for the next try and the host gets one notice. Returns True when written
        (`force` also saves a table that has no events yet)."""
        store = self.config.store
        cid = self.state.campaign_id
        if store is None or (not force and not self.log and not store.exists(cid)):
            return False
        try:
            store.save(
                cid,
                initial=self.initial,
                events=self.unsaved,
                state=self.state,
                meta=self.table_meta(),
            )
        except OSError:
            _LOG.exception("autosave failed")
            if not self.save_warned:
                self.save_warned = True
                for host in (p for p in self.players.values() if p.is_host):
                    self.notice(host.id, NoticeKind.HOST, "Saving failed; the game continues.")
            return False
        self.unsaved.clear()
        self.save_warned = False
        return True

    # --- outbound ------------------------------------------------------------------------

    def send_conn(self, conn_id: str, msg: AnyServerMsg) -> None:
        box = self.outboxes.get(conn_id)
        if box is not None:
            box.put_nowait(msg)

    def send(self, player_id: str, msg: AnyServerMsg) -> None:
        player = self.players.get(player_id)
        for conn_id in sorted(player.conns) if player is not None else ():
            self.send_conn(conn_id, msg)

    def broadcast(self, msg: AnyServerMsg) -> None:
        for conn_id in sorted(self.conn_player):
            self.send_conn(conn_id, msg)

    def notice(self, player_id: str | None, kind: NoticeKind, text: str) -> None:
        msg = Notice(kind=kind, text=text)
        if player_id is None:
            self.broadcast(msg)
        else:
            self.send(player_id, msg)

    def error(self, player_id: str, code: ErrorCode, text: str) -> None:
        self.send(player_id, ErrorMsg(code=code, text=text))

    def snapshot(self) -> Snapshot:
        view = public_state(
            self.state,
            phase=self.phase,
            paused=self.paused,
            players=[p.info() for p in self.players.values()],
            queue=list(self.queue),
            resolving=self.resolving,
            vote=self.vote.view() if self.vote is not None else None,
            tts_enabled=self.tts_enabled,
        )
        return Snapshot(seq=self.state.event_count, state=view)

    def broadcast_snapshot(self) -> None:
        if self.conn_player:
            self.broadcast(self.snapshot())

    def broadcast_roster(self) -> None:
        self.broadcast(LobbyRoster(players=tuple(p.info() for p in self.players.values())))

    def broadcast_queue(self) -> None:
        self.broadcast(QueueState(entries=tuple(self.queue), resolving=self.resolving))

    # --- jobs and timers -----------------------------------------------------------------

    def schedule(self, job: Job) -> None:
        self.jobs.put_nowait(job)

    def start_timer(self, kind: str, key: str, seconds: float) -> TimerHandle:
        def fire() -> None:
            self.inbox.put_nowait(TimerFired(kind, key))

        return self.config.clock.call_later(seconds, fire)
