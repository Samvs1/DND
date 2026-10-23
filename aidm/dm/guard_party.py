"""People and party checks of the prose guard (M29.7b, docs/playtests/M29_round2.md R13 R21 R28).

Each check reads ONE sentence against the frozen `GuardScene`; vocabulary is data
(data/bg3/guard_lexicon.json):
- `wrong_count` (R28): "the five of you" / "all five of you" counting more heroes than the
  party has ("you" are the heroes; a smaller count may be a group of them; a lone hero's "the two
  of you" with a foe is left alone, docs/DECISIONS.md M29.7b).
- `hurt_told_whole` (R28): a hurt hero (below full hit points) told whole or unhurt, by name
  ("Brienne, Elowen, Rook and Tamsin move unhurt") or with the whole party ("all four of you
  whole", `group_phrases`) in the same clause.
- `wrong_race` (R28): "the dwarf" when no hero, present person or creature here is one.
- `told_absent` (R13): a present NPC told absent ("Wren is nowhere in sight", `absence_claims`).
- `identifiers` (R21): an identifier-shaped token in prose: any snake_case word
  ("offer_favour"), or a kebab-case id of the manifest ("wren-averntide", "cultist-1").

Public API: `COUNT_WORDS`, `wrong_count`, `hurt_told_whole`, `wrong_race`, `told_absent`,
`identifiers`.
"""

import re

from aidm.dm.guard_scene import GuardScene
from aidm.dm.guard_text import Token, find_phrases, is_negated, plain
from aidm.dm.guard_types import Violation, ViolationKind

COUNT_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
_COUNT = re.compile(rf"\b(?:the|all)\s+({'|'.join(COUNT_WORDS)})\s+of\s+(?:you|us)\b", re.I)
_CLAUSE_END = re.compile(r"[;.!?]|\bbut\b|\bwhile\b|\bthough\b", re.I)
_SNAKE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_KEBAB = re.compile(r"\b[a-z][a-z0-9]*(?:-[a-z0-9]+)+\b")
_ABSENT_REACH = 30
_WHOLE_REACH = 50
_MIN_PARTY = 2


def wrong_count(sentence: str, scene: GuardScene) -> list[Violation]:
    size = max(scene.party_counts, default=0)
    if size < _MIN_PARTY:
        return []
    for m in _COUNT.finditer(plain(sentence)):
        told = COUNT_WORDS[m.group(1).casefold()]
        if told > size:
            detail = f"the party is {size} heroes, not {told}: count only the heroes"
            return [Violation(ViolationKind.WRONG_COUNT, m.group(0), detail)]
    return []


def _clause_before(text: str, end: int) -> str:
    cut = max((m.end() for m in _CLAUSE_END.finditer(text, 0, end)), default=0)
    return text[max(cut, end - _WHOLE_REACH) : end]


def hurt_told_whole(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    if not scene.hurt:
        return []
    lex = scene.lexicon
    text = plain(sentence)
    for claim in find_phrases(text, lex.whole_claims):
        index = next((i for i, t in enumerate(tokens) if t.start >= claim.start()), len(tokens))
        if is_negated(tokens, index, lex.negations, span=2):
            continue
        before = _clause_before(text, claim.start())
        named = [
            name
            for term, name in scene.hurt.items()
            if re.search(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", before, re.I)
        ]
        group = _COUNT.search(before) or find_phrases(before, lex.group_phrases)
        hurt = named or (sorted(set(scene.hurt.values())) if group else [])
        if hurt:
            detail = f"{', '.join(sorted(set(hurt)))} is still hurt: never tell them whole"
            return [Violation(ViolationKind.HURT_TOLD_WHOLE, claim.group(0), detail)]
    return []


def wrong_race(sentence: str, scene: GuardScene) -> list[Violation]:
    races = "|".join(re.escape(r) for r in sorted(scene.lexicon.race_words, key=len, reverse=True))
    if not races:
        return []
    for m in re.finditer(rf"\b(?i:the|your|our)\s+({races})\b(?!-)", sentence):
        race = m.group(1).casefold()
        if race not in scene.races_here:
            detail = f"nobody here is a {race}"
            return [Violation(ViolationKind.WRONG_IDENTITY, m.group(0), detail)]
    return []


def told_absent(sentence: str, scene: GuardScene) -> list[Violation]:
    text = plain(sentence)
    for claim in find_phrases(text, scene.lexicon.absence_claims):
        window = text[max(0, claim.start() - _ABSENT_REACH) : claim.end() + _ABSENT_REACH]
        for word in sorted(scene.present_words):
            if re.search(rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])", window, re.I):
                detail = f"{scene.present_words[word]} is here: never tell them absent"
                return [Violation(ViolationKind.ERASED_PRESENT, claim.group(0), detail)]
    return []


def identifiers(sentence: str, scene: GuardScene) -> list[Violation]:
    text = plain(sentence)
    found = _SNAKE.search(text)
    if found is None:
        found = next((m for m in _KEBAB.finditer(text) if m.group(0) in scene.known_ids), None)
    if found is None:
        return []
    detail = "an engine id is not prose: name people, places and things by their names"
    return [Violation(ViolationKind.IDENTIFIER, found.group(0), detail)]
