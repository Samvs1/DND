"""The defeat flow (M11.1, DECISIONS M11.1): party wipe -> DEFEATED -> retry, load or new.

- `after_job(core)` runs after EVERY table job (`Table._worker_loop`): when the phase is PLAY, no
  fight is active and `rules.party_wipe.party_wiped` holds (a lost fight just ended, or surface or
  trap damage downed the last hero outside a fight), the table enters the defeat: the queue,
  vote, pending confirmation and turn timer are cleared, the defeat epilogue is told
  (`dm.defeat.begin_defeat`: guarded, template fallback; it never fails the defeat), then
  `PartyDefeated` is applied and the phase becomes DEFEATED. Then the arrival checkpoint a move
  asked for is written (`checkpoints.flush_arrival`).
- `locked(core, player, msg)`: while DEFEATED every gameplay message is refused with
  `wrong_phase` (refusal "defeated"); allowed are the read-only requests (sheet, export, chat),
  the defeat choices, the safe host controls (save, load, new, end, kick, TTS toggle) and the
  audio remote (M11.2); `typing` is refused. Ping and
  hello are handled before any seat check.
- `defeat_message(core, player, msg)`: `defeat_retry` / `defeat_load` / `defeat_new`, only in
  phase DEFEATED and only from the host or the sole connected player (`not_host` otherwise).
- `retry(core, player)`: back to `core.retry_checkpoint()`: the live log is cut at the marker
  (the discarded tail is saved as `events.<n>.defeat`), the state is rebuilt by replaying the
  kept log, every connection keeps its seat (`host_switch.switch` re-sends welcome, roster,
  snapshot and story history), the dice are reseeded with the retry counter and a short notice
  says the party tries again. Nothing new is narrated; a fight checkpoint resumes the fight.

Determinism: dice are never part of the replay (events carry resolved values), so reseeding the
live RNG with `"<seed>:<seq>:retry<n>"` keeps `replay(initial, log) == state` while the retried
fight can end differently.

Public API: `ALLOWED`, `after_job`, `enter_defeat`, `locked`, `may_choose`, `defeat_message`,
`retry`.
"""

import logging
import random
from functools import partial

from aidm.dm.defeat import begin_defeat, defeat_event, defeat_facts, template_defeat
from aidm.models import protocol_client as c
from aidm.models.defeat import CheckpointFile, PartyDefeated
from aidm.models.events import LoggedEvent
from aidm.models.protocol import AnyClientMsg
from aidm.models.protocol_server import ErrorCode, NoticeKind
from aidm.models.protocol_views import TablePhase
from aidm.rules.party_wipe import party_wiped
from aidm.session import checkpoints, combat_flow, floor, host_switch, votes
from aidm.session.persistence import LoadedCampaign, replay_log
from aidm.session.table_core import Job, Player, TableCore
from aidm.session.telling import tell

_LOG = logging.getLogger(__name__)
ALLOWED: tuple[type, ...] = (
    c.RequestSheet,
    c.ExportCharacter,
    c.Chat,
    c.ScribeSkip,
    *c.DEFEAT_MESSAGES,
    c.HostSave,
    c.HostLoad,
    c.HostNew,
    c.HostEnd,
    c.HostKick,
    c.HostTtsToggle,
    c.AudioSettingsMsg,
)
LOCKED = "The party has fallen. The host can try again, load a save or begin a new adventure."
NO_CHECKPOINT = "There is no checkpoint to return to. Load a save or begin a new adventure."
RETRY_FAILED = "The retry could not be saved; nothing was changed."


def locked(core: TableCore, player: Player, msg: AnyClientMsg) -> bool:
    if core.phase is not TablePhase.DEFEATED or isinstance(msg, ALLOWED):
        return False
    core.error(player.id, ErrorCode.WRONG_PHASE, LOCKED, "defeated")
    return True


async def after_job(core: TableCore) -> None:
    calm = core.phase is TablePhase.PLAY and not core.combat_active()
    if calm and core.state.defeat is None and party_wiped(core.state):
        await enter_defeat(core)
    checkpoints.flush_arrival(core)


def _clear(core: TableCore) -> None:
    for entry in core.queue:
        core.notice(entry.player_id, NoticeKind.INFO, "Your plan is lost with the fallen party.")
    core.queue.clear()
    floor.clear_typing(core)
    core.broadcast_queue()
    if core.vote is not None:
        votes.close_vote(core, passed=False, reason="the party has fallen")
    core.pending = None
    combat_flow.end_player_turn(core)
    core.in_combat = False
    core.segment = []


async def _defeat_event(core: TableCore) -> PartyDefeated:
    facts = defeat_facts(core.state)
    try:
        stream = begin_defeat(core.state, core.llm)
        await tell(core, stream)
        return defeat_event(stream, facts)
    except Exception:
        _LOG.exception("defeat epilogue failed; the template is used")
        text = " ".join(template_defeat(facts))
        return PartyDefeated(text=text, source="template", place=facts.place)


async def enter_defeat(core: TableCore) -> None:
    _clear(core)
    core.apply(await _defeat_event(core))
    core.phase = TablePhase.DEFEATED


def may_choose(core: TableCore, player: Player) -> bool:
    connected = [p for p in core.players.values() if p.connected]
    return player.is_host or connected == [player]


def defeat_message(core: TableCore, player: Player, msg: AnyClientMsg) -> None:
    if core.phase is not TablePhase.DEFEATED:
        core.error(player.id, ErrorCode.WRONG_PHASE, "The party has not fallen.", "not_defeated")
        return
    if not may_choose(core, player):
        text = "Only the host chooses how the tale goes on."
        core.error(player.id, ErrorCode.NOT_HOST, text, "defeat_host_only")
        return
    match msg:
        case c.DefeatRetry():
            core.schedule(partial(retry, core, player))
        case c.DefeatLoad(campaign_id=campaign_id):
            core.schedule(
                partial(_if_defeated, core, partial(host_switch.load, core, player, campaign_id))
            )
        case c.DefeatNew():
            core.schedule(
                partial(_if_defeated, core, partial(host_switch.new_campaign, core, player))
            )
        case _:
            core.error(player.id, ErrorCode.INVALID, "That is not a defeat choice.")


async def _if_defeated(core: TableCore, step: Job) -> None:
    """A choice runs only while the table is still DEFEATED (a double click does nothing)."""
    if core.phase is TablePhase.DEFEATED:
        await step()


def _cut_saved_log(
    core: TableCore, keep: list[LoggedEvent], tail: list[LoggedEvent], n: int
) -> bool:
    store = core.config.store
    if store is None:
        return True
    try:
        store.truncate_log(core.save_id or core.state.campaign_id, keep, tail, n)
    except OSError:
        _LOG.exception("cutting the saved log for a retry failed")
        return False
    return True


async def retry(core: TableCore, player: Player) -> None:
    if core.phase is not TablePhase.DEFEATED:
        return
    point = core.retry_checkpoint()
    if point is None:
        core.error(player.id, ErrorCode.REFUSED, NO_CHECKPOINT, "no_checkpoint")
        return
    core.autosave()
    keep = [e for e in core.log if e.seq < point.seq]
    tail = [e for e in core.log if e.seq >= point.seq]
    attempt = core.checkpoints.retries + 1
    if not _cut_saved_log(core, keep, tail, attempt):
        core.error(player.id, ErrorCode.REFUSED, RETRY_FAILED, "retry_failed")
        return
    marks = [m for m in core.checkpoints.checkpoints if m.seq <= point.seq]
    state = replay_log(core.initial, keep)
    cid = core.save_id or core.state.campaign_id
    loaded = LoadedCampaign(
        cid,
        core.initial,
        state,
        keep,
        core.table_meta(),
        checkpoints=CheckpointFile(checkpoints=marks, retries=attempt),
    )
    host_token = next((p.token for p in core.players.values() if p.is_host), None)
    host_switch.switch(core, loaded, host_token, keep_kicked=True)
    core.rng = random.Random(f"{state.seed}:{state.event_count}:retry{attempt}")
    checkpoints.save(core)
    text = f"Fate turns back its page, and the party tries again: {point.label}."
    core.notice(None, NoticeKind.INFO, text)
