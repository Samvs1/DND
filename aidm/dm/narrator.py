"""The narrator: resolved mechanics -> streamed prose (SPEC 6.1 step 3, 6.4, 6.8, 11).

`narrate` makes ONE streamed QUALITY call with the NARRATE context pack (no NPC private data,
no ids) plus the resolved tool results as authoritative facts, and returns a `NarrationStream`
of sentence chunks carrying the scene tone. How much it says follows the engine's weight of the
beat (`narration_weight`, M19.1: 1-2, 2-3 or 3-5 sentences, the stream bounded to match), never
reusing what was already narrated; second person plural or character names, no mechanics
numbers unless the player asked for them (`allow_numbers`). When nothing changed, or a fight has
only just begun, the facts say so, so the model cannot tell an outcome the engine did not produce.
A refused gear use (`use_item` tool error, M27.5; a creative effect's `GEAR_REFUSED`, M27.6) is
a fact told as an attempt (`TRIED`), never as a result. M29.5c (the honest storyteller): the
facts also carry `aidm.dm.turn_facts` (the weapons used, who still stands, who is unhurt, a
claimed thing the hero does not carry, a payment or hand-over no event made) and the events'
model-only notes (`event_text.event_notes`), and the guard knows the actor and the player's words.
Every sentence passes THE guard (`aidm.dm.guard`, default `prose_checker(state, events)`)
before it is yielded: one regeneration with a correction and scrubbed names, then the template.
Without a model (no key, outage, timeout, empty answer) the stream falls back to the
deterministic template narration built from the same events, so every resolution narrates.

`narrate_round_segment` describes consecutive monster turns with ONE call (SPEC 6.1).

Tone follows state: an active (or starting) fight is COMBAT, a social exchange (attitude,
secret, shop or introduction events, or `social=True`) is SOCIAL, anything else EXPLORATION.

The narration is recorded into memory by applying `record_narration(state, text)` (a
`NarrationRecorded` event) through the session reducer.

`voice_next` names the NPC whose voice answers right after (M20.7): the style tells the model
not to speak for them (`VOICE_NEXT`), the guard flags spoken words or their reply
(`aidm.dm.guard_claims.spoken_for`), and the template drops its stock `QUIET_LINE` (the reply
follows, so a narration with nothing to tell stays silent). M32.1a X7: a turn with no events
whose tool call the engine refused carries the refusal as its notice (`dm.refusal_text`), so
its template fallback says why instead of the stock filler line. M32.1b X15: the telling of the
chosen finale passes no `closing` filler ("the scene waits on your next move").

Public API: `NUMBERS_ALLOWED`, `VOICE_NEXT`, `TRIED`, `NarrationInput`,
`unpack_source(source) -> (events, facts, notice)` (what the narrator is told),
`tone_for(state, events=(), *, social=False)`, `narration_messages(...)`,
`narrate(state, source, llm, *, actor_id, player_text, tone, allow_numbers, guard,
budget_tokens, voice_next) -> NarrationStream`, `narrate_round_segment(state, events, llm, *, guard,
budget_tokens) -> NarrationStream`, `record_narration(state, text) -> NarrationRecorded | None`.
"""

from collections.abc import Sequence
from typing import Any

from aidm.dm.adjudicator import AdjudicationResult
from aidm.dm.context import DEFAULT_BUDGET_TOKENS, build_context, to_messages
from aidm.dm.context_text import ContextPurpose
from aidm.dm.creative_gear import GEAR_REFUSED
from aidm.dm.event_text import event_notes
from aidm.dm.guard import guarded_narration, prose_checker
from aidm.dm.guard_types import ProseCheck
from aidm.dm.llm_client import LlmClient
from aidm.dm.narration_stream import NarrationStream
from aidm.dm.narration_templates import CLOSING_LINE, QUIET_LINE, template_narration
from aidm.dm.narration_weight import (
    NarrationWeight,
    max_tokens_for,
    segment_style_for,
    style_for,
    truth_notes,
    weight_for,
)
from aidm.dm.refusal_text import refusal_line
from aidm.dm.turn_facts import turn_facts
from aidm.models.campaign_events import FinaleChosen
from aidm.models.encounter import EncounterStatus
from aidm.models.encounter_events import EncounterEnded, EncounterStarted
from aidm.models.events import AnyEvent
from aidm.models.narration import NarrationTone
from aidm.models.state import GameState
from aidm.models.world_events import (
    AttitudeChanged,
    NarrationRecorded,
    NpcIntroduced,
    SecretRevealed,
    ShopOpened,
)

NUMBERS_ALLOWED = "The player asked about the numbers: you may state them plainly."
VOICE_NEXT = (
    "{name} answers right after you, in their own voice: do not write {name}'s words, reply,"
    " silence or decision, and never say they keep quiet; tell only the action and what the"
    " engine resolved, and stop with their answer still to come."
)
TRIED = "Tried, and nothing changed: {why} Tell it only as an attempt, never as done."
_SOCIAL_EVENTS = (AttitudeChanged, SecretRevealed, ShopOpened, NpcIntroduced)

type NarrationInput = AdjudicationResult | Sequence[AnyEvent]


def _fight_active(state: GameState, events: Sequence[AnyEvent]) -> bool:
    for event in reversed(events):
        if isinstance(event, EncounterEnded):
            return False
        if isinstance(event, EncounterStarted):
            return True
    enc = state.encounter
    return enc is not None and enc.status is EncounterStatus.ACTIVE


def tone_for(
    state: GameState, events: Sequence[AnyEvent] = (), *, social: bool = False
) -> NarrationTone:
    if _fight_active(state, events):
        return NarrationTone.COMBAT
    if social or any(isinstance(e, _SOCIAL_EVENTS) for e in events):
        return NarrationTone.SOCIAL
    return NarrationTone.EXPLORATION


def unpack_source(source: NarrationInput) -> tuple[list[AnyEvent], list[str], str | None]:
    if not isinstance(source, AdjudicationResult):
        return list(source), [], None
    facts = [r.result.summary for r in source.executed if r.result.summary]
    facts += [
        TRIED.format(why=r.result.error)
        for r in source.calls
        if r.result.error and (r.call.name == "use_item" or r.result.error.startswith(GEAR_REFUSED))
    ]
    if source.pending is not None:
        facts.append(f"Awaiting the player's confirmation: {source.pending.prompt}")
        facts.append("Nothing has happened yet: do not tell the act as done.")
    return list(source.events), facts, source.notice


def _refused(state: GameState, source: NarrationInput) -> str | None:
    """M32.1a X7: a turn with no events whose tool call the engine refused says why."""
    if not isinstance(source, AdjudicationResult) or source.events:
        return None
    return refusal_line(state, (r.result.error for r in source.calls if r.result.error))


def narration_messages(
    state: GameState,
    events: Sequence[AnyEvent],
    facts: Sequence[str],
    style: str,
    *,
    actor_id: str | None = None,
    player_text: str | None = None,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
) -> list[dict[str, Any]]:
    pack = build_context(
        state,
        ContextPurpose.NARRATE,
        actor_id,
        player_text,
        events=events,
        budget_tokens=budget_tokens,
    )
    lines = "\n".join(f"- {f}" for f in facts) if facts else "- (see the engine events)"
    extra = f"## RESOLVED TOOL RESULTS (authoritative)\n{lines}\n\n## STYLE\n{style}"
    return [*to_messages(pack), {"role": "user", "content": extra}]


def narrate(
    state: GameState,
    source: NarrationInput,
    llm: LlmClient,
    *,
    actor_id: str | None = None,
    player_text: str | None = None,
    tone: NarrationTone | None = None,
    allow_numbers: bool = False,
    guard: ProseCheck | None = None,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    voice_next: str | None = None,
) -> NarrationStream:
    events, facts, notice = unpack_source(source)
    notice = notice or _refused(state, source)
    weight = (
        NarrationWeight.MINOR
        if isinstance(source, AdjudicationResult) and source.pending
        else weight_for(events)
    )
    style = style_for(weight)
    style = f"{style} {NUMBERS_ALLOWED}" if allow_numbers else style
    style = f"{style} {VOICE_NEXT.format(name=voice_next)}" if voice_next else style
    told = turn_facts(state, events, actor_id=actor_id, player_text=player_text)
    messages = narration_messages(
        state,
        events,
        [*facts, *truth_notes(events), *told, *event_notes(state, events)],
        style,
        actor_id=actor_id,
        player_text=player_text,
        budget_tokens=budget_tokens,
    )
    fallback = template_narration(events, state, notice)
    if voice_next:  # the NPC's own reply follows: no stock filler line before it
        fallback = [line for line in fallback if line != QUIET_LINE]
    sentences = guarded_narration(
        llm,
        messages,
        guard
        if guard is not None
        else prose_checker(
            state, events, voice_next=voice_next, actor_id=actor_id, player_text=player_text
        ),
        fallback,
        max_tokens=max_tokens_for(weight),
        player_text=player_text,
        closing=() if _ending(events) else (CLOSING_LINE,),
    )
    return NarrationStream(tone or tone_for(state, events), sentences)


def _ending(events: Sequence[AnyEvent]) -> bool:
    """M32.1b X15: the finale's telling is an ending: it never closes on the filler line."""
    return any(isinstance(e, FinaleChosen) for e in events)


def narrate_round_segment(
    state: GameState,
    events: Sequence[AnyEvent],
    llm: LlmClient,
    *,
    guard: ProseCheck | None = None,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
) -> NarrationStream:
    died = any(e.type in ("creature_died", "encounter_ended") for e in events)
    weight = NarrationWeight.MAJOR if died else NarrationWeight.NORMAL
    style = segment_style_for(weight)
    facts = [*turn_facts(state, events), *event_notes(state, events)]
    messages = narration_messages(state, events, facts, style, budget_tokens=budget_tokens)
    sentences = guarded_narration(
        llm,
        messages,
        guard if guard is not None else prose_checker(state, events),
        template_narration(events, state),
        max_tokens=max_tokens_for(weight),
    )
    return NarrationStream(NarrationTone.COMBAT, sentences)


def record_narration(state: GameState, text: str) -> NarrationRecorded | None:
    clean = text.strip()
    if not clean:
        return None
    return NarrationRecorded(text=clean, scene_turn=state.world.scene_turn + 1)
