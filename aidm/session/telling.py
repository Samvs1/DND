"""Narration out of the table actor, and the after-mechanics order every resolution follows.

`conclude` is the shared tail of an exploration resolution (M4.7 + M5.4/M5.6/M5.7 order):
1. follow-ups of the applied mechanics: after a `PartyMoved`, `dm.arrival.on_arrival` (describe
   once, then the world's encounter offer); then, after EVERY batch, `quest_flow.settle_after`
   (region resolution + milestone rewards, the spoke milestones of the batch, then quest steps,
   routes and main quests, M23.2);
2. narrate (streamed sentence by sentence as `narration_chunk`, each carrying its audio url when
   the host's TTS toggle is on and the synthesis made it in time (`narration_pipe`); then
   `narration_done`);
3. NPC voice when `voice_target` names a present NPC (second stream, shown as `Name: "..."`;
   the narration before it is told not to speak for that NPC, M20.7);
4. ONE `record_narration` of narration + speech, then `summarise` when due (never mid-fight);
5. a new encounter offer goes out as `encounter_offer`; the epilogue runs once it is ready.
Fights that start are handled by the caller (`combat_flow.after_resolution`).

Every told narration is also kept in `core.public` (the story history for reconnects).

Every `tell` also writes one `narration` diagnostics line (source, retry, guard flags; M20.1).

Public API: `tell`, `tell_text`, `remember`, `follow_ups`, `conclude`, `maybe_epilogue`,
`MAX_DIAG_FLAGS`.
"""

from collections.abc import Sequence
from dataclasses import replace

from aidm.dm.adjudicator import AdjudicationResult
from aidm.dm.arrival import on_arrival
from aidm.dm.epilogue import begin_epilogue, epilogue_event, epilogue_ready
from aidm.dm.memory import should_summarise, summarise
from aidm.dm.narration_stream import NarrationChunk, NarrationStream
from aidm.dm.narrator import narrate, record_narration
from aidm.dm.npc_voice import npc_voice, voice_target
from aidm.models.campaign_events import EncounterOffered
from aidm.models.events import AnyEvent
from aidm.models.narration import NarrationTone
from aidm.models.protocol_server import (
    EncounterOfferMsg,
    EpilogueMsg,
    NarrationDone,
)
from aidm.models.protocol_views import TablePhase
from aidm.models.world_events import PartyMoved
from aidm.session import asides, scribe_voice
from aidm.session.narration_pipe import NarrationPipe
from aidm.session.quest_flow import settle_after
from aidm.session.table_core import TableCore
from aidm.session.views import public_offer

MAX_DIAG_FLAGS = 8


async def tell(core: TableCore, stream: NarrationStream) -> str:
    """Stream the sentences as `narration_chunk`s (the pipe adds audio), then `narration_done`."""
    nid = core.next_id("n")
    tone: NarrationTone | None = None
    pipe = NarrationPipe(core, nid)
    try:
        async for chunk in stream:
            tone = tone or chunk.tone
            pipe.add(chunk)
        await pipe.finish()
    except BaseException:
        pipe.abort()
        raise
    core.broadcast(NarrationDone(id=nid))
    core.public.add_narration(nid, stream.feed_text, tone, core.state.event_count)
    _diag_narration(core, stream)
    return stream.text


def _diag_narration(core: TableCore, stream: NarrationStream) -> None:
    """M20.1: where a narration came from and what the guard flagged (model words only, never
    the player's), so a playtest's fallbacks can be explained from the logs."""
    flags = [f"{v.kind.value}:{v.span}" for r in stream.reports for v in r.violations]
    failure = stream.failure.reason.value if stream.failure is not None else None
    core.diag(
        "narration",
        source=stream.source.value,
        retried=stream.retried,
        flags=flags[:MAX_DIAG_FLAGS],
        failure=failure,
    )


async def tell_text(
    core: TableCore, text: str, tone: NarrationTone = NarrationTone.EXPLORATION
) -> str:
    nid = core.next_id("n")
    pipe = NarrationPipe(core, nid)
    try:
        pipe.add(NarrationChunk(0, text, tone, line=True))
        await pipe.finish()
    except BaseException:
        pipe.abort()
        raise
    core.broadcast(NarrationDone(id=nid))
    core.public.add_narration(nid, text, tone, core.state.event_count)
    return text


async def remember(
    core: TableCore,
    text: str,
    events: Sequence[AnyEvent] = (),
    *,
    player_text: str | None = None,
) -> None:
    recorded = record_narration(core.state, text)
    if recorded is not None:
        core.apply(recorded)
    if not core.combat_active() and should_summarise(core.state, events):
        outcome = await summarise(core.state, core.llm, events=events, player_text=player_text)
        core.apply_all(list(outcome.events))


async def follow_ups(core: TableCore, events: Sequence[AnyEvent]) -> list[AnyEvent]:
    out: list[AnyEvent] = []
    moved = [e for e in events if isinstance(e, PartyMoved)]
    if moved:
        out += await on_arrival(
            core.state,
            core.llm,
            core.regs,
            retreat_node=moved[-1].from_node,
            apply=core.apply,
        )
    out += settle_after(core.state, core.regs, [*events, *out], core.apply_all)
    return out


async def conclude(
    core: TableCore,
    result: AdjudicationResult | None,
    events: Sequence[AnyEvent],
    *,
    actor_id: str | None = None,
    player_text: str | None = None,
) -> list[AnyEvent]:
    """Narrate applied mechanics (see the module docstring); returns every event of the turn.
    M33.1: scene-setting words of the turn's line (`asides.take`) are told with it."""
    lead = asides.take()
    if lead is not None:
        player_text = f"{lead}, then {player_text}" if player_text else lead
    every = [*events, *await follow_ups(core, events)]
    source = replace(result, events=tuple(every)) if result is not None else every
    target = voice_target(core.state, result, player_text) if player_text else None
    stream = narrate(
        core.state,
        source,
        core.llm,
        actor_id=actor_id,
        player_text=player_text,
        voice_next=core.state.world.npcs[target].name if target is not None else None,
    )
    text = await tell(core, stream)
    if target is not None:
        voice = npc_voice(
            core.state,
            target,
            core.llm,
            actor_id=actor_id,
            player_text=player_text,
            result=result,
            events=every,
        )
        text = f"{text} {await tell(core, voice)}"
    await remember(core, text, every, player_text=player_text)
    offer = public_offer(core.state)
    if offer is not None and any(isinstance(e, EncounterOffered) for e in every):
        core.broadcast(EncounterOfferMsg(offer=offer))
    await maybe_epilogue(core)
    return every


async def maybe_epilogue(core: TableCore) -> None:
    if not epilogue_ready(core.state):
        return
    scribe_voice.campaign_won(core)
    stream = begin_epilogue(core.state, core.llm)
    if stream is None:
        return
    text = await tell(core, stream)
    core.apply(epilogue_event(stream))
    core.broadcast(EpilogueMsg(text=text))
    core.phase = TablePhase.ENDED
