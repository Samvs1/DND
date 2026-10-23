"""Leak checks of the prose guard (M29.5c, docs/playtests/M29_round1.md G22 G36).

Players hear stories, never the machinery behind them:
- `placeholders` (G22): a bracketed or braced token in prose ("[unlisted] [unlisted]": the model
  copied the scrub token of a retry) is flagged.
- `instructions` (G36): text meant for the storyteller ("Do NOT choose for them", "Tell this
  ending as it happens now", "describe no new deed") is flagged: a phrase of
  `instruction_phrases`, or an all-caps imperative word of `instruction_caps` ("NOT").
- `instruction_free(text)` drops every sentence holding such text: THE filter for engine lines
  shown to players (`aidm.session.public_feed`), so a line built from a prompt never carries
  its instruction.

Public API: `PLACEHOLDER`, `placeholders(sentence)`, `instructions(sentence, lex)`,
`instruction_free(text) -> str`.
"""

import re

from aidm.data.guard_lexicon import GuardLexicon, guard_lexicon
from aidm.dm.guard_text import find_phrases, plain
from aidm.dm.guard_types import Violation, ViolationKind
from aidm.dm.sentence_chunker import split_sentences

PLACEHOLDER = re.compile(r"\[[A-Za-z _-]{2,30}\]|\{[A-Za-z_ ]{2,30}\}")
_LEAK_DETAIL = "instructions to the storyteller are never told to the players"


def placeholders(sentence: str) -> list[Violation]:
    m = PLACEHOLDER.search(sentence)
    if m is None:
        return []
    detail = "a placeholder token is not prose: name only listed people and things, or none"
    return [Violation(ViolationKind.PLACEHOLDER, m.group(0), detail)]


def _instruction(sentence: str, lex: GuardLexicon) -> str | None:
    hit = find_phrases(sentence, lex.instruction_phrases)
    if hit:
        return hit[0].group(0)
    caps = re.search(rf"\b(?:{'|'.join(map(re.escape, lex.instruction_caps))})\b", sentence)
    if caps is not None and lex.instruction_caps and len(sentence.split()) > 2:
        return caps.group(0)
    return None


def instructions(sentence: str, lex: GuardLexicon) -> list[Violation]:
    hit = _instruction(sentence, lex)
    return [] if hit is None else [Violation(ViolationKind.INSTRUCTION_LEAK, hit, _LEAK_DETAIL)]


def instruction_free(text: str) -> str:
    """`text` without the sentences that hold storyteller instructions (or placeholders)."""
    lex = guard_lexicon()
    sentences = split_sentences(plain(text))
    kept = [s for s in sentences if _instruction(s, lex) is None and not PLACEHOLDER.search(s)]
    return text if len(kept) == len(sentences) else " ".join(kept)
