"""How a typed line reads a blow (M33.1, ultrareview 3: "I bow to the bandit captain", "I warm my
hands by the fire, watching the bandits", "I keep my bow slung and greet the gnoll" and "I won't
attack the bandit" answered a waiting offer as a fight and were then played as a shot).

ONE reading for the strike rows (`offer_strike`, `weapon_strike`, and the creative weapon rule),
by word position, from the lexicon of data/bg3/intent_phrases.json:
- `marked(text)`: the line's words with a clause mark at every , ; : . ! ? so no reading runs
  across a clause; a reading also stops at a joining word (`clause_joins`: "and", "then").
- `negated(words, i)`: a `negation_words` word stands at most three words before word i in its
  clause ("I won't attack", "I do not wish to attack"; "No mercy, I attack" is not negated).
- `as_weapon(words, i)`: a weapon word is a weapon only in a weapon reading: after a
  `weapon_determiners` word (an article, a possessive, a count: "my bow", "an arrow", "two
  arrows", "Rook's bow") at most two words before it ("my trusty bow"), or right after a
  `weapon_leads` word ("with", "from"); never negated. So "I bow to the captain" and "bows low"
  are courtesies, never a bow.
- `as_act(words, i)`: a strike word is the line's act, never a noun: after a determiner it
  counts only when an aim word (`strike_aims`: "at", "on") follows ("a swing at the bandit"),
  so "by the fire, watching" is a fire; never negated.

Public API: `MARK`, `marked`, `negated`, `as_weapon`, `as_act`, `strikes`, `weapon_words`.
"""

import re

from aidm.data.intent_phrases import intent_phrases
from aidm.dm.fight_names import tokens

MARK = ","
_NEGATION_REACH = 3
_DETERMINER_REACH = 2


def marked(text: str) -> list[str]:
    words: list[str] = []
    for clause in re.split(r"[,;:.!?]+", text):
        if words:
            words.append(MARK)
        words += tokens(clause)
    return words


def _before(words: list[str], i: int, reach: int) -> list[str]:
    """The words of word i's clause before it, at most `reach`, nearest last."""
    stops = intent_phrases().lexicon["clause_joins"] | {MARK}
    out: list[str] = []
    for word in reversed(words[max(0, i - reach) : i]):
        if word in stops:
            break
        out.insert(0, word)
    return out


def negated(words: list[str], i: int) -> bool:
    return bool(
        set(_before(words, i, _NEGATION_REACH)) & intent_phrases().lexicon["negation_words"]
    )


def _determined(words: list[str], i: int) -> bool:
    determiners = intent_phrases().lexicon["weapon_determiners"]
    return any(w in determiners or w.endswith("'s") for w in _before(words, i, _DETERMINER_REACH))


def as_weapon(words: list[str], i: int) -> bool:
    lexicon = intent_phrases().lexicon
    led = i > 0 and words[i - 1] in lexicon["weapon_leads"]
    return (led or _determined(words, i)) and not negated(words, i)


def as_act(words: list[str], i: int) -> bool:
    aimed = i + 1 < len(words) and words[i + 1] in intent_phrases().lexicon["strike_aims"]
    return (aimed or not _determined(words, i)) and not negated(words, i)


def _plain(word: str) -> str:
    return word.removesuffix("'s").rstrip("'")


def strikes(words: list[str]) -> bool:
    verbs = intent_phrases().lexicon["strike_verbs"]
    return any(_plain(w) in verbs and as_act(words, i) for i, w in enumerate(words))


def weapon_words(words: list[str]) -> set[str]:
    """The plain words read as weapons ("my bow" -> "bow"; "I bow to" -> nothing)."""
    return {_plain(w) for i, w in enumerate(words) if w != MARK and as_weapon(words, i)}
