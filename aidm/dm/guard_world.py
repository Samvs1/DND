"""World checks of the prose guard (SPEC 6.5; v1 classes in docs/V1_LESSONS.md).

Each check reads ONE sentence against the frozen `GuardScene`:
- `dead_acting`: a dead creature's name followed (within a few words) by an action verb, in a
  sentence with no death word ("corpse", "lifeless", "slain"...). Names a living creature shares
  (one of two goblins died) are not checked.
- `destroyed_items`: an item the party carries (or a visible item), by a noun of its name or a
  synonym ("vial" for a potion), within five words of a destruction word ("shatters", "broken",
  "shards") that is not negated ("not broken"); "unbroken" never matches (word boundaries).
  A noun owned by someone else ("the goblin's blade") is skipped; items the events removed are
  not protected.
- `unlisted_features`: interactive feature nouns (lever, trapdoor, pressure plate, chest...)
  and hidden ones (a door/passage/seam with "secret", "hidden", "concealed"... or a reveal verb)
  that are neither listed features of this place nor words of its established description.
- `opened_locks` (M27.5): a feature still locked here (its name word, "lock" or "lid") within a
  few words of an opening claim ("swings open", "unlocks", "gives way") that is not negated, not
  an intent ("to open") and not in a sentence that says it held ("holds", "in vain"). Only a
  `FeatureUnlocked` event opens a lock, and it clears the lock before the narration.

Public API: `dead_acting`, `destroyed_items`, `unlisted_features`, `opened_locks`.
"""

import re

from aidm.dm.guard_scene import GuardScene
from aidm.dm.guard_text import Token, base_word, find_phrases, is_negated, singular_forms
from aidm.dm.guard_types import Violation, ViolationKind

_ACTION_REACH = 50
_ITEM_REACH = 5
_LOCK_REACH = 6


def _token_at(tokens: list[Token], start: int) -> int | None:
    return next((i for i, t in enumerate(tokens) if t.start == start), None)


def dead_acting(sentence: str, scene: GuardScene) -> list[Violation]:
    lex = scene.lexicon
    if not scene.dead or find_phrases(sentence, lex.death_words):
        return []
    out: list[Violation] = []
    for name in sorted(scene.dead):
        pattern = rf"(?<![A-Za-z]){re.escape(name)}(?:'s)?(?![A-Za-z])"
        for m in re.finditer(pattern, sentence, re.IGNORECASE):
            if find_phrases(sentence[m.end() : m.end() + _ACTION_REACH], lex.action_verbs):
                detail = f"{name} is dead and cannot act"
                out.append(Violation(ViolationKind.DEAD_ACTING, name, detail))
                break
    return out


def _foreign_owner(tokens: list[Token], index: int, scene: GuardScene) -> bool:
    if index == 0:
        return False
    prev = tokens[index - 1]
    if prev.lower == "its":
        return True
    owner = base_word(prev.text)
    return owner != prev.text and owner not in scene.party


def destroyed_items(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    lex = scene.lexicon
    hits = [
        index
        for m in find_phrases(sentence, lex.destroy_words)
        if (index := _token_at(tokens, m.start())) is not None
        and not is_negated(tokens, index, lex.negations)
    ]
    for i, token in enumerate(tokens):
        noun = next((f for f in singular_forms(token.lower) if f in scene.item_nouns), None)
        if noun is None or _foreign_owner(tokens, i, scene):
            continue
        if any(abs(i - h) <= _ITEM_REACH for h in hits):
            detail = f"{scene.item_nouns[noun]} is intact; no event destroyed it"
            return [Violation(ViolationKind.ITEM_DESTROYED, token.text, detail)]
    return []


def _covered(phrase: str, scene: GuardScene) -> bool:
    words = phrase.casefold().split()
    return any(f in scene.feature_words for f in singular_forms(words[-1]))


def _body_part(tokens: list[Token], index: int | None, scene: GuardScene) -> bool:
    if not index:
        return False
    prev = tokens[index - 1]
    return prev.lower in scene.lexicon.body_possessives or base_word(prev.text) != prev.text


def _hidden_claim(sentence: str, tokens: list[Token], index: int, scene: GuardScene) -> bool:
    lex = scene.lexicon
    near = tokens[max(0, index - 3) : index]
    if any(t.lower in lex.hidden_qualifiers for t in near):
        return True
    reveal = find_phrases(sentence, lex.reveal_verbs)
    return any(r.start() < tokens[index].start for r in reveal)


def unlisted_features(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    lex = scene.lexicon
    out: list[Violation] = []
    found = [(m, True) for m in find_phrases(sentence, lex.feature_nouns_always)]
    found += [(m, False) for m in find_phrases(sentence, lex.feature_nouns_hidden)]
    for m, always in sorted(found, key=lambda pair: pair[0].start()):
        index = _token_at(tokens, m.start())
        if index is None or _covered(m.group(0), scene):
            continue
        if is_negated(tokens, index, lex.negations, span=4) or _body_part(tokens, index, scene):
            continue
        if always or _hidden_claim(sentence, tokens, index, scene):
            detail = f"no {m.group(0).lower()} is listed here"
            out.append(Violation(ViolationKind.UNLISTED_FEATURE, m.group(0), detail))
    return out


def _claims(sentence: str, tokens: list[Token], scene: GuardScene) -> list[int]:
    lex = scene.lexicon
    found: list[int] = []
    for m in find_phrases(sentence, lex.open_claims):
        index = _token_at(tokens, m.start())
        if index is None or is_negated(tokens, index, lex.negations):
            continue
        if index > 0 and tokens[index - 1].lower == "to":  # "tries to open": an intent
            continue
        found.append(index)
    return found


def opened_locks(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    if not scene.locked or find_phrases(sentence, scene.lexicon.lock_failures):
        return []
    claims = _claims(sentence, tokens, scene)
    for i, token in enumerate(tokens):
        forms = singular_forms(token.lower)
        name = next((scene.locked[f] for f in forms if f in scene.locked), None)
        if name is not None and any(abs(i - c) <= _LOCK_REACH for c in claims):
            detail = f"the {name} is still locked; nothing opened it"
            return [Violation(ViolationKind.LOCK_OPENED, token.text, detail)]
    return []
