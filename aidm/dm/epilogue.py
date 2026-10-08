"""The epilogue of a finished campaign (SPEC 9: "reflects what actually happened, not invention").

When `campaign_complete(state)` and no epilogue exists, `begin_epilogue` makes ONE streamed QUALITY
call whose only input is the facts of `aidm.dm.epilogue_facts` (the fact ledger, how each region
was resolved, quest outcomes, fallen heroes, NPC attitudes). Every sentence passes THE guard
(`aidm.dm.guard`) before it is yielded: invented names, dead creatures acting (a defeated boss is
never alive again), living people declared dead and unearned rewards are flagged, then ONE retry
with the offending names scrubbed, then the deterministic template that lists what really
happened (`template_epilogue`). The epilogue is a story ABOUT the past, so the scene-local
"absent NPC" check is switched off (everyone who exists may be mentioned); the closed-world name
check is not.

Public API:
- `EPILOGUE_STYLE`, `epilogue_ready(state) -> bool`, `epilogue_messages(facts) -> list[Message]`.
- `epilogue_checker(state) -> ProseCheck`; `facts_checker(state, lines) -> ProseCheck` (the same
  relaxed guard for any prose about listed facts; the defeat epilogue uses it too).
- `begin_epilogue(state, llm) -> NarrationStream | None`: None until the campaign is complete (or
  when the epilogue is already written); the stream's sentences are the epilogue.
- `epilogue_event(stream) -> EpilogueWritten`: the event to apply once the stream is collected.
- `async write_epilogue(state, llm) -> EpilogueResult | None`: the whole thing, collected.
"""

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass

from aidm.dm.epilogue_facts import EpilogueFacts, epilogue_facts, template_epilogue
from aidm.dm.guard import check_prose, guarded_narration
from aidm.dm.guard_flow import NarrationSource
from aidm.dm.guard_scene import guard_scene, words_of
from aidm.dm.guard_types import GuardReport, ProseCheck
from aidm.dm.llm_backend import Message
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_types import LlmRole
from aidm.dm.narration_stream import NarrationStream
from aidm.models.campaign_events import EpilogueWritten
from aidm.models.narration import NarrationTone
from aidm.models.state import GameState
from aidm.rules.progression import campaign_complete

EPILOGUE_MAX_TOKENS = 900
EPILOGUE_MAX_SENTENCES = 14
EPILOGUE_STYLE = (
    "You write the epilogue of a finished fantasy campaign. Use ONLY the facts listed by the"
    " user: tell what happened to the places, the heroes who fell or lived on, the quests, the"
    " people the party befriended or wronged. Invent no names, no events, no rewards and no"
    " places that are not listed. A defeated enemy stays defeated: never describe it acting."
    " A hero who survived is alive. 5 to 10 sentences of prose, past tense, no lists, no"
    " mechanics numbers."
)


@dataclass(frozen=True)
class EpilogueResult:
    text: str
    source: NarrationSource
    retried: bool
    reports: tuple[GuardReport, ...]
    event: EpilogueWritten


def epilogue_ready(state: GameState) -> bool:
    campaign = state.campaign
    return campaign_complete(state) and campaign is not None and campaign.epilogue is None


def epilogue_messages(facts: EpilogueFacts) -> list[Message]:
    listed = "\n".join(f"- {line}" for line in facts.lines())
    user = f"FACTS (the only things that happened):\n{listed}\n\nWrite the epilogue now."
    return [{"role": "system", "content": EPILOGUE_STYLE}, {"role": "user", "content": user}]


def epilogue_checker(state: GameState, facts: EpilogueFacts | None = None) -> ProseCheck:
    """THE guard with the scene-local checks relaxed: every word of the facts is known."""
    return facts_checker(state, (facts or epilogue_facts(state)).lines())


def facts_checker(state: GameState, lines: Sequence[str]) -> ProseCheck:
    """THE guard for prose ABOUT listed facts (epilogue, defeat): no absent-NPC check, the
    facts' words are known; the closed-world name check stays on."""
    listed = words_of(" ".join(lines))
    base = guard_scene(state)
    scene = dataclasses.replace(
        base,
        absent_npcs={},
        absent_roles=frozenset[str](),
        known_words=base.known_words | listed,
        feature_words=base.feature_words | listed,
    )
    return lambda text: check_prose(text, state, scene=scene)


def begin_epilogue(state: GameState, llm: LlmClient) -> NarrationStream | None:
    if not epilogue_ready(state):
        return None
    facts = epilogue_facts(state)
    sentences = guarded_narration(
        llm,
        epilogue_messages(facts),
        epilogue_checker(state, facts),
        template_epilogue(facts),
        role=LlmRole.QUALITY,
        max_tokens=EPILOGUE_MAX_TOKENS,
        max_sentences=EPILOGUE_MAX_SENTENCES,
    )
    return NarrationStream(NarrationTone.EXPLORATION, sentences)


def epilogue_event(stream: NarrationStream) -> EpilogueWritten:
    return EpilogueWritten(text=stream.text, source=stream.source.value)


async def write_epilogue(state: GameState, llm: LlmClient) -> EpilogueResult | None:
    stream = begin_epilogue(state, llm)
    if stream is None:
        return None
    await stream.collect()
    return EpilogueResult(
        text=stream.text,
        source=stream.source,
        retried=stream.retried,
        reports=tuple(stream.reports),
        event=epilogue_event(stream),
    )
