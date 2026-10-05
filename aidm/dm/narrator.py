"""The narrator: resolved mechanics -> streamed prose (SPEC 6.1 step 3, 6.4, 6.8, 11).

`narrate` makes ONE streamed QUALITY call with the NARRATE context pack (no NPC private data,
no ids) plus the resolved tool results as authoritative facts, and returns a `NarrationStream`
of sentence chunks carrying the scene tone. Style: 2 to 6 sentences, second person plural or
character names, no mechanics numbers unless the player asked for them (`allow_numbers`).
Without a model (no key, outage, timeout, empty answer) the stream falls back to the
deterministic template narration built from the same events, so every resolution narrates.

`narrate_round_segment` describes consecutive monster turns with ONE call (SPEC 6.1).

Tone follows state: an active (or starting) fight is COMBAT, a social exchange (attitude,
secret, shop or introduction events, or `social=True`) is SOCIAL, anything else EXPLORATION.

The narration is recorded into memory by applying `record_narration(state, text)` (a
`NarrationRecorded` event) through the session reducer.

Public API: `NARRATION_STYLE`, `NUMBERS_ALLOWED`, `SEGMENT_STYLE`, `NarrationInput`,
`tone_for(state, events=(), *, social=False)`, `narration_messages(...)`,
`narrate(state, source, llm, *, actor_id, player_text, tone, allow_numbers, guard,
budget_tokens) -> NarrationStream`, `narrate_round_segment(state, events, llm, *, guard,
budget_tokens) -> NarrationStream`, `record_narration(state, text) -> NarrationRecorded | None`.
"""

from collections.abc import Sequence
from typing import Any

from aidm.dm.adjudicator import AdjudicationResult
from aidm.dm.context import DEFAULT_BUDGET_TOKENS, build_context, to_messages
from aidm.dm.context_text import ContextPurpose
from aidm.dm.guard_types import ProseCheck, no_guard
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_types import LlmRole
from aidm.dm.narration_stream import NarrationStream, NarrationTone
from aidm.dm.narration_templates import template_narration
from aidm.models.encounter import EncounterStatus
from aidm.models.encounter_events import EncounterEnded, EncounterStarted
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.models.world_events import (
    AttitudeChanged,
    NarrationRecorded,
    NpcIntroduced,
    SecretRevealed,
    ShopOpened,
)

NARRATION_MAX_TOKENS = 700
NARRATION_STYLE = (
    "Write 2 to 6 sentences of prose only, no lists, headings or name lists. Address the party"
    " in the second person plural or name the characters. State no mechanics numbers: no dice"
    " totals, DCs, damage amounts, hit points or XP. Describe exactly the resolved outcomes"
    " below; a failed attempt is told as a failure in the fiction."
)
NUMBERS_ALLOWED = "The player asked about the numbers: you may state them plainly."
SEGMENT_STYLE = (
    "Describe the consecutive enemy turns below as ONE flowing passage of 2 to 6 sentences,"
    " in order, fast and vivid. State no mechanics numbers. Fallen creatures stay fallen."
)
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


def _unpack(source: NarrationInput) -> tuple[list[AnyEvent], list[str], str | None]:
    if not isinstance(source, AdjudicationResult):
        return list(source), [], None
    facts = [r.result.summary for r in source.executed if r.result.summary]
    if source.pending is not None:
        facts.append(f"Awaiting the player's confirmation: {source.pending.prompt}")
    return list(source.events), facts, source.notice


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
    guard: ProseCheck = no_guard,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
) -> NarrationStream:
    events, facts, notice = _unpack(source)
    style = f"{NARRATION_STYLE} {NUMBERS_ALLOWED}" if allow_numbers else NARRATION_STYLE
    messages = narration_messages(
        state,
        events,
        facts,
        style,
        actor_id=actor_id,
        player_text=player_text,
        budget_tokens=budget_tokens,
    )
    return NarrationStream(
        tone or tone_for(state, events),
        lambda: llm.stream_text(
            messages, LlmRole.QUALITY, max_tokens=NARRATION_MAX_TOKENS, player_text=player_text
        ),
        template_narration(events, state, notice),
        guard,
    )


def narrate_round_segment(
    state: GameState,
    events: Sequence[AnyEvent],
    llm: LlmClient,
    *,
    guard: ProseCheck = no_guard,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
) -> NarrationStream:
    messages = narration_messages(state, events, [], SEGMENT_STYLE, budget_tokens=budget_tokens)
    return NarrationStream(
        NarrationTone.COMBAT,
        lambda: llm.stream_text(messages, LlmRole.QUALITY, max_tokens=NARRATION_MAX_TOKENS),
        template_narration(events, state),
        guard,
    )


def record_narration(state: GameState, text: str) -> NarrationRecorded | None:
    clean = text.strip()
    if not clean:
        return None
    return NarrationRecorded(text=clean, scene_turn=state.world.scene_turn + 1)
