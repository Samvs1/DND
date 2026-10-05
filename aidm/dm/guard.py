"""THE prose guard (SPEC 2.2 closed world, 6.1 step 4, 6.5): every prose output passes here.

`check_prose(text, state, *, events, scene)` checks each sentence against the entity registry
and the current scene (`aidm.dm.guard_scene`):
- unknown person-like names, near misses of party names (`aidm.dm.guard_names.unknown_names`);
- wrong class or name for a party member (`wrong_identity`);
- absent NPCs acting or named in an empty scene, invented crowds, present people erased
  (`absent_people`, `crowds`, `erased_people`);
- dead creatures acting, intact items described as destroyed, unlisted doors, passages, levers,
  chests and traps (`aidm.dm.guard_world`);
- any NPC's UNREVEALED secret stated in prose (`aidm.dm.guard_secrets`, M4.7): a reveal is a
  `reveal_secret` tool call validated by the engine, never prose.
Vocabulary is data (data/bg3/guard_lexicon.json); matching uses word boundaries and negation
windows, so "unbroken" and "no hidden door" are not flagged.

`guarded_narration` runs the flow for any model prose (narration, NPC speech `aidm.dm.npc_voice`):
guard every sentence, ONE regeneration with a correction and the offending names scrubbed
from the context, then the safe template (`aidm.dm.guard_flow.GuardedSentences`).

Public API: `SCRUB_TOKEN`, `check_prose`, `prose_checker(state, events=()) -> ProseCheck`,
`scrub_messages(messages, terms)`, `retry_messages(messages, report, shown)`,
`guarded_narration(llm, messages, check, fallback_lines, *, role, max_tokens, player_text,
max_sentences) -> GuardedSentences`.
"""

import re
from collections.abc import Sequence

from aidm.dm.guard_flow import MAX_SENTENCES, GuardedSentences
from aidm.dm.guard_names import absent_people, crowds, erased_people, unknown_names, wrong_identity
from aidm.dm.guard_scene import GuardScene, guard_scene
from aidm.dm.guard_secrets import leaked_secrets
from aidm.dm.guard_text import tokenize
from aidm.dm.guard_types import GuardReport, ProseCheck, Violation
from aidm.dm.guard_world import dead_acting, destroyed_items, unlisted_features
from aidm.dm.llm_backend import Message
from aidm.dm.llm_client import LlmClient, TextStream
from aidm.dm.llm_types import LlmRole
from aidm.dm.sentence_chunker import split_sentences
from aidm.models.events import AnyEvent
from aidm.models.state import GameState

SCRUB_TOKEN = "[unlisted]"
CONTINUE_NOTE = "Continue the narration right after the text above; do not repeat it."


def _sentence_violations(sentence: str, scene: GuardScene) -> list[Violation]:
    tokens = tokenize(sentence)
    return [
        *unknown_names(tokens, scene),
        *wrong_identity(sentence, scene),
        *absent_people(sentence, tokens, scene),
        *crowds(sentence, tokens, scene),
        *erased_people(sentence, scene),
        *dead_acting(sentence, scene),
        *destroyed_items(sentence, tokens, scene),
        *unlisted_features(sentence, tokens, scene),
        *leaked_secrets(sentence, scene.secrets),
    ]


def check_prose(
    text: str,
    state: GameState,
    *,
    events: Sequence[AnyEvent] = (),
    scene: GuardScene | None = None,
) -> GuardReport:
    frozen = scene if scene is not None else guard_scene(state, events)
    found: list[Violation] = []
    for sentence in split_sentences(text):
        found.extend(v for v in _sentence_violations(sentence, frozen) if v not in found)
    return GuardReport(tuple(found))


def prose_checker(state: GameState, events: Sequence[AnyEvent] = ()) -> ProseCheck:
    scene = guard_scene(state, events)
    return lambda text: check_prose(text, state, scene=scene)


def scrub_messages(messages: Sequence[Message], terms: Sequence[str]) -> list[Message]:
    if not terms:
        return [dict(m) for m in messages]
    ordered = sorted(terms, key=len, reverse=True)
    pattern = re.compile(
        "|".join(rf"(?<![A-Za-z]){re.escape(t)}(?![A-Za-z])" for t in ordered), re.IGNORECASE
    )
    out: list[Message] = []
    for message in messages:
        copy = dict(message)
        content = copy.get("content")
        if message.get("role") != "system" and isinstance(content, str):
            copy["content"] = pattern.sub(SCRUB_TOKEN, content)
        out.append(copy)
    return out


def retry_messages(messages: Sequence[Message], report: GuardReport, shown: str) -> list[Message]:
    out = scrub_messages(messages, report.scrub_terms)
    note = report.correction()
    if shown:
        out.append({"role": "assistant", "content": shown})
        note = f"{note} {CONTINUE_NOTE}"
    out.append({"role": "user", "content": note})
    return out


def guarded_narration(
    llm: LlmClient,
    messages: Sequence[Message],
    check: ProseCheck,
    fallback_lines: Sequence[str],
    *,
    role: LlmRole = LlmRole.QUALITY,
    max_tokens: int = 700,
    player_text: str | None = None,
    max_sentences: int = MAX_SENTENCES,
) -> GuardedSentences:
    base = list(messages)

    def attempt(report: GuardReport | None, shown: str) -> TextStream:
        sent = base if report is None else retry_messages(base, report, shown)
        return llm.stream_text(sent, role, max_tokens=max_tokens, player_text=player_text)

    return GuardedSentences(attempt, check, fallback_lines, max_sentences=max_sentences)
