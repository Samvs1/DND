"""People checks of the prose guard (SPEC 6.5; v1 classes in docs/V1_LESSONS.md).

Each check reads ONE sentence (`tokens` from `aidm.dm.guard_text.tokenize`) against the frozen
`GuardScene` and returns `Violation`s:
- `unknown_names`: capitalised person-like words that are no registered name, lore name, title,
  calendar word, language/people word or class word. Sentence-initial words count only when
  they look like a name (a possessive, or followed by a speech or gesture verb or by another
  capitalised word);
  possessives and plurals reduce to their base ("Mira's", "Goblins"). A near miss of a party
  name ("Aira" for "Aria") is a WRONG_IDENTITY.
- `wrong_identity`: a party member given another class ("Aria the wizard", "the cleric Aria"),
  or "the <class>" when nobody present has that class (party classes, NPC roles/archetypes).
- `absent_people`: a registered NPC who is not here, named in the sentence, or "the <role>" of
  an absent NPC acting in an empty scene; a sentence that recalls them (told, remember, find...)
  is fine.
- `crowds`: crowd nouns ("a throng of onlookers") when fewer than two other people are present.
- `erased_people`: "the hall holds only you" while NPCs or foes are present.

Public API: `unknown_names`, `wrong_identity`, `absent_people`, `crowds`, `erased_people`.
"""

import difflib
import re

from aidm.dm.guard_scene import GuardScene
from aidm.dm.guard_text import (
    Token,
    base_word,
    find_phrases,
    is_negated,
    singular_forms,
)
from aidm.dm.guard_types import Violation, ViolationKind
from aidm.dm.wording import with_article

_NEAR_MISS = 0.75
_LOOKALIKE = 0.7


def _known(word: str, scene: GuardScene) -> bool:
    lex = scene.lexicon
    for form in singular_forms(word):
        if form in scene.known_words or form in lex.allowed_capitalised or form in lex.titles:
            return True
        if form in lex.class_words:
            return True
    return False


def _name_like(tokens: list[Token], i: int, scene: GuardScene) -> bool:
    token = tokens[i]
    if base_word(token.text).casefold() in scene.lexicon.sentence_starters:
        return False
    if base_word(token.text) != token.text:
        return True
    following = tokens[i + 1] if i + 1 < len(tokens) else None
    if following is None:
        return False
    return following.lower in scene.lexicon.person_verbs or (
        following.capitalised and not following.initial
    )


def _misnamed(word: str, scene: GuardScene) -> str | None:
    match = difflib.get_close_matches(word, list(scene.party), n=1, cutoff=_NEAR_MISS)
    return match[0] if match else None


def _resembles_person(word: str, scene: GuardScene) -> bool:
    people = [*scene.present_npcs, *scene.absent_npcs.values()]
    words = [w for name in people for w in re.findall(r"[A-Za-z]{3,}", name)]
    return bool(difflib.get_close_matches(word, words, n=1, cutoff=_LOOKALIKE))


def unknown_names(tokens: list[Token], scene: GuardScene) -> list[Violation]:
    out: list[Violation] = []
    for i, token in enumerate(tokens):
        if not token.capitalised:
            continue
        word = base_word(token.text)
        if _known(word, scene):
            continue
        near = _misnamed(word, scene)
        if near is not None:
            detail = f"{word} is not a party member (did you mean {near}?)"
            out.append(Violation(ViolationKind.WRONG_IDENTITY, word, detail))
        elif not token.initial or _name_like(tokens, i, scene) or _resembles_person(word, scene):
            detail = f"{word} is not in the scene manifest"
            out.append(Violation(ViolationKind.UNKNOWN_NAME, word, detail))
    return out


def _class_pattern(scene: GuardScene) -> str:
    return "|".join(sorted(scene.lexicon.class_words))


def wrong_identity(sentence: str, scene: GuardScene) -> list[Violation]:
    out: list[Violation] = []
    classes = _class_pattern(scene)
    for name, cls in scene.party.items():
        n = re.escape(name)
        pats = (
            rf"\b{n}\b,?\s+(?i:the)\s+(?:[a-z]+\s+)?({classes})\b",
            rf"\b(?i:the)\s+(?:[a-z]+\s+)?({classes}),?\s+{n}\b",
        )
        for pat in pats:
            for m in re.finditer(pat, sentence):
                if m.group(1) != cls:
                    detail = f"{name} is {with_article(cls)}, not {with_article(m.group(1))}"
                    out.append(Violation(ViolationKind.WRONG_IDENTITY, m.group(0), detail))
    allowed = scene.party_classes | scene.present_roles
    for m in re.finditer(rf"\b(?i:the|your|our)\s+(?:[a-z]+\s+)?({classes})\b", sentence):
        if m.group(1) not in allowed:
            detail = f"nobody here is {with_article(m.group(1))}"
            out.append(Violation(ViolationKind.WRONG_IDENTITY, m.group(0), detail))
    return out


def _recalled(tokens: list[Token], scene: GuardScene) -> bool:
    return any(t.lower in scene.lexicon.recall_words for t in tokens)


def _acting(sentence: str, start: int, scene: GuardScene) -> bool:
    tail = sentence[start : start + 60]
    return bool(find_phrases(tail, scene.lexicon.action_verbs))


def absent_people(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    if _recalled(tokens, scene):
        return []
    empty = scene.others_present == 0
    out: list[Violation] = []
    named: set[str] = set()
    for term, name in sorted(scene.absent_npcs.items(), key=lambda kv: -len(kv[0])):
        if name in named:
            continue
        if re.search(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", sentence):
            named.add(name)
            out.append(Violation(ViolationKind.ABSENT_NPC, term, f"{name} is not here"))
    for role in sorted(scene.absent_roles):
        for m in re.finditer(rf"\bthe\s+{re.escape(role)}\b", sentence, re.IGNORECASE):
            if empty and _acting(sentence, m.end(), scene):
                detail = f"no {role} is here"
                out.append(Violation(ViolationKind.ABSENT_NPC, m.group(0), detail))
    return out


def crowds(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    if scene.others_present >= 2:
        return []
    out: list[Violation] = []
    starts = {t.start: i for i, t in enumerate(tokens)}
    for m in find_phrases(sentence, scene.lexicon.crowd_nouns):
        index = starts.get(m.start())
        if index is not None and is_negated(tokens, index, scene.lexicon.negations):
            continue
        detail = "no crowd is present in the scene"
        out.append(Violation(ViolationKind.INVENTED_CROWD, m.group(0), detail))
    return out


def erased_people(sentence: str, scene: GuardScene) -> list[Violation]:
    if scene.others_present == 0:
        return []
    return [
        Violation(ViolationKind.ERASED_PRESENT, m.group(0), "people listed here are present")
        for m in find_phrases(sentence, scene.lexicon.erase_phrases)
    ]
