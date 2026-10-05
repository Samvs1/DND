"""Seats, characters and the campaign start (SPEC 8, 9, 10 lobby phase).

`hello` seats a new player (the first one is the host) or, with a known token, reconnects the
seat: the connection gets `welcome` + a full `snapshot`, and whatever waits for that player is
re-sent (their turn prompt, a pending hostile confirmation). `closed` drops a connection; a
player with no connection left is away: they leave the open vote, and their hero's current
turn is auto-played. `create` builds a hero through `rules.creation` (rolled scores must be
the ones this table rolled for that player); `start_campaign` (host) generates the campaign
with its own timeout (`TableConfig.campaign_timeout_s`, 150 s by default: the quality model
needs ~25-45 s per call), installs it and narrates the opening through `telling.conclude`.

Public API: `hello`, `closed`, `roll`, `create`, `start_campaign`, `party_text`.
"""

from aidm.dm.campaign_gen import CampaignSource, generate_campaign
from aidm.models.creation import AbilityMethod, CreationError, CreationErrorCode
from aidm.models.events import CreatureAdded, CreatureRemoved
from aidm.models.protocol_client import CreateCharacter, Hello
from aidm.models.protocol_server import (
    AbilityRolls,
    CreationResult,
    ErrorCode,
    ErrorMsg,
    NoticeKind,
    PendingConfirmationMsg,
    TurnPrompt,
    Welcome,
)
from aidm.models.protocol_views import TablePhase
from aidm.models.state import GameState
from aidm.rules.ability_gen import roll_ability_scores
from aidm.rules.campaign_install import install_campaign
from aidm.rules.creation import build_character, validate_creation
from aidm.rules.sheet import build_sheet
from aidm.session import combat_flow, votes
from aidm.session.stats import send_host_stats
from aidm.session.table_core import Player, TableCore
from aidm.session.telling import conclude
from aidm.session.views import event_message

GENERATING = "The Dungeon Master is writing your campaign. This can take up to two minutes."
MAX_CATCH_UP = 500
FELL_BACK = "The tale-weaver faltered, so a ready-made tale begins instead."


def hello(core: TableCore, conn_id: str, msg: Hello) -> None:
    if msg.token is not None and msg.token in core.kicked:
        text = "The host removed you from this table."
        core.send_conn(conn_id, ErrorMsg(code=ErrorCode.REFUSED, text=text))
        return
    player = next((p for p in core.players.values() if msg.token and p.token == msg.token), None)
    if player is None:
        player = core.new_player(msg.name)
    player.conns.add(conn_id)
    core.conn_player[conn_id] = player.id
    welcome = Welcome(player_id=player.id, token=player.token, is_host=player.is_host)
    core.send_conn(conn_id, welcome)
    core.send_conn(conn_id, core.snapshot())
    if msg.last_seq is not None:
        _catch_up(core, conn_id, msg.last_seq)
    core.broadcast_roster()
    send_host_stats(core)
    _resend_waiting(core, conn_id, player)
    if core.resume_combat and player.creature_id is not None:
        core.resume_combat = False
        core.schedule(lambda: combat_flow.advance(core))


def _catch_up(core: TableCore, conn_id: str, last_seq: int) -> None:
    """Re-send the event lines the client missed (seq >= its `last_seq`), oldest first."""
    missed = [entry for entry in core.log if entry.seq >= last_seq][-MAX_CATCH_UP:]
    for entry in missed:
        core.send_conn(conn_id, event_message(core.state, entry.seq, entry.event))


def _resend_waiting(core: TableCore, conn_id: str, player: Player) -> None:
    enc = core.state.encounter
    active = enc.active_id() if enc is not None and core.turn_key is not None else None
    if active is not None and active == player.creature_id:
        seconds = core.config.turn_seconds
        core.send_conn(
            conn_id, TurnPrompt(creature_id=active, player_id=player.id, seconds=seconds)
        )
    pending = core.pending
    if pending is not None and pending.player_id == player.id:
        msg = PendingConfirmationMsg(player_id=player.id, prompt=pending.prompt)
        core.send_conn(conn_id, msg)


def closed(core: TableCore, conn_id: str) -> None:
    core.outboxes.pop(conn_id, None)
    player = core.player_for(conn_id)
    core.conn_player.pop(conn_id, None)
    if player is None:
        return
    player.conns.discard(conn_id)
    if player.connected:
        return
    core.broadcast_roster()
    votes.drop_voter(core, player.id)
    release_turn(core, player.creature_id)


def release_turn(core: TableCore, creature_id: str | None) -> None:
    """A hero whose player left plays its current turn by the safe default."""
    enc = core.state.encounter
    key = core.turn_key
    if key is not None and enc is not None and enc.active_id() == creature_id:
        core.schedule(lambda: combat_flow.turn_timeout(core, key))


def roll(core: TableCore, player: Player) -> None:
    rolls = roll_ability_scores(core.creation_rng)
    core.issued_rolls[player.id] = rolls
    core.send(player.id, AbilityRolls(rolls=tuple(rolls)))


def _can_create(core: TableCore, player: Player) -> bool:
    if core.phase in (TablePhase.GENERATING, TablePhase.ENDED) or core.combat_active():
        core.error(player.id, ErrorCode.WRONG_PHASE, "Heroes can join between scenes.")
        return False
    if core.phase is TablePhase.PLAY and core.living_pc(player) is not None:
        core.error(player.id, ErrorCode.REFUSED, "You already have a hero in this tale.")
        return False
    return True


async def create(core: TableCore, player: Player, msg: CreateCharacter) -> None:
    if not _can_create(core, player):
        return
    choices, chars = msg.choices, core.regs.combat.chars
    errors = validate_creation(choices, chars)
    rolled = core.issued_rolls.get(player.id)
    if choices.ability_method is AbilityMethod.ROLL_4D6 and list(choices.rolls) != rolled:
        detail = "roll your ability scores at this table first"
        errors.append(
            CreationError(code=CreationErrorCode.ROLLS_INVALID, field="rolls", detail=detail)
        )
    if errors:
        core.send(player.id, CreationResult(ok=False, errors=tuple(errors)))
        return
    cid = f"pc-{player.id}"
    if cid in core.state.creatures:
        core.apply(CreatureRemoved(creature_id=cid))
    core.apply(CreatureAdded(creature=build_character(choices, chars, cid)))
    player.creature_id = cid
    sheet = build_sheet(core.state.creatures[cid], chars)
    core.send(player.id, CreationResult(ok=True, sheet=sheet))
    core.broadcast_roster()


def party_text(state: GameState) -> str:
    heroes = sorted((c for c in state.creatures.values() if c.pc is not None), key=lambda c: c.id)
    parts = [
        f"{c.name}, level {c.pc.level} {c.pc.race} {c.pc.class_index}"
        for c in heroes
        if c.pc is not None
    ]
    return f"{len(parts)} adventurers: " + "; ".join(parts)


async def start_campaign(core: TableCore, host: Player, theme: str | None) -> None:
    if core.phase is not TablePhase.LOBBY:
        core.error(host.id, ErrorCode.WRONG_PHASE, "The campaign has already begun.")
        return
    if not any(c.pc is not None for c in core.state.creatures.values()):
        core.error(host.id, ErrorCode.NO_CHARACTER, "Create at least one hero first.")
        return
    core.phase = TablePhase.GENERATING
    core.notice(None, NoticeKind.PROGRESS, GENERATING)
    core.broadcast_snapshot()
    try:
        result = await generate_campaign(
            theme,
            party_text(core.state),
            core.llm,
            seed=core.state.seed,
            timeout_s=core.config.campaign_timeout_s,
        )
    except BaseException:
        core.phase = TablePhase.LOBBY
        raise
    if result.source is CampaignSource.FALLBACK and core.llm.available:
        core.notice(None, NoticeKind.FALLBACK, FELL_BACK)
    events = core.apply_all(install_campaign(core.state, result.plan, core.state.seed))
    core.phase = TablePhase.PLAY
    await conclude(core, None, events)
