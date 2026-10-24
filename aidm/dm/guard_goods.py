"""Goods-truth checks of the prose guard (M29.5c, docs/playtests/M29_round1.md G1 G3 G9 G31).

Gold, gear and hand-overs change only through engine events (the shop, `give`, gear uses). Each
check reads ONE sentence against the scene's `TurnTruth` (`aidm.dm.guard_turn`); vocabulary is
data (data/bg3/guard_lexicon.json):
- `unpaid_coin` (G1): a payment ("pays the ten gold", "counts out a gold piece", "passes over
  ... coin") when these events changed no gold; promises ("will you pay") and quoted speech
  are not claims (M32.1b X11: the words outside the quote marks still are). M31.2b (round 4
  typed 45: "Rook slaps the coins onto the table" while no gold moved): a `coin_placing_verbs`
  verb with its coins as object ("sets two gold pieces", "drops a coin": up to three
  `coin_fillers` words between, then a `placed_coin_nouns` noun that ends the phrase or is
  followed by a `placed_coin_followers` word, so "drops the gold chain" is no payment).
- `claimed_items` (G3): a thing the player used as the hero's own that the hero does not carry
  ("Brienne raises the potion", "Rook's silk rope", "Elowen's javelin"), unless the sentence tells
  it as absent ("no such potion", "finds nothing").
- `unmade_handover` (G31): a present NPC told taking or holding a carried thing ("Ranna folds her
  fingers around the stiff scroll") when no keepsake or item changed hands; M29.9c T11: also a
  thing a quest asks for that nobody holds ("Beska takes your sun-ember").
- `unlit_light` (G9): a torch, lantern or candle told catching flame when no light was lit.

Public API: `unpaid_coin`, `claimed_items`, `unmade_handover`, `unlit_light`.
"""

import re

from aidm.dm.guard_light import singular_light
from aidm.dm.guard_scene import GuardScene, words_of
from aidm.dm.guard_text import QUOTE_MARKS, Token, find_phrases, is_negated, tokenize
from aidm.dm.guard_types import Violation, ViolationKind

_MIN_NAME_WORD = 4


def _index_at(tokens: list[Token], start: int) -> int | None:
    return next((i for i, t in enumerate(tokens) if t.start == start), None)


def _first_unnegated(
    sentence: str, tokens: list[Token], phrases: frozenset[str], scene: GuardScene, span: int = 3
) -> re.Match[str] | None:
    for m in find_phrases(sentence, phrases):
        index = _index_at(tokens, m.start())
        if index is not None and not is_negated(tokens, index, scene.lexicon.negations, span):
            return m
    return None


_QUOTED = re.compile(rf"[{QUOTE_MARKS}][^{QUOTE_MARKS}]*(?:[{QUOTE_MARKS}]|$)")


def _unquoted(sentence: str) -> str:
    """The sentence with its quoted words blanked (same length): only the telling is a claim."""
    return _QUOTED.sub(lambda m: " " * len(m.group(0)), sentence)


def _alternatives(words: frozenset[str]) -> str:
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


def _placed_coin(sentence: str, scene: GuardScene) -> re.Match[str] | None:
    """ "slaps the coins onto the table": coins put down or handed over, told as done."""
    lex = scene.lexicon
    if not lex.coin_placing_verbs or not lex.placed_coin_nouns:
        return None
    verbs, nouns = _alternatives(lex.coin_placing_verbs), _alternatives(lex.placed_coin_nouns)
    fillers, follow = _alternatives(lex.coin_fillers), _alternatives(lex.placed_coin_followers)
    pattern = (
        rf"\b(?:{verbs})\s+(?:(?:{fillers}|\d+)\s+){{0,3}}(?:{nouns})"
        rf"(?![\w'-])(?!\s+(?!(?:{follow})\b)[a-z])"
    )
    tokens = tokenize(sentence)
    for m in re.finditer(pattern, sentence, re.IGNORECASE):
        index = _index_at(tokens, m.start())
        if index is None or not is_negated(tokens, index, lex.negations, span=3):
            return m
    return None


def unpaid_coin(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    """M32.1b X11: a sentence with speech in it ("'Fifteen silver, as agreed,' she says, and
    pays the full sum") is judged by its telling outside the quote marks."""
    truth, lex = scene.turn, scene.lexicon
    if not truth.checked or truth.paid or not find_phrases(sentence, lex.coin_nouns):
        return []
    told = _unquoted(sentence)
    if find_phrases(told, lex.payment_refusals):
        return []
    if find_phrases(told, lex.promise_words):  # "will you pay": a pay word is only a promise
        placed = _placed_coin(told, scene)  # but coins put down before any "if" are told done
        hedged = placed is None or find_phrases(told[: placed.start()], lex.promise_words)
        verb = None if hedged else placed
    else:
        verb = _first_unnegated(told, tokenize(told), lex.payment_verbs, scene)
        verb = verb or _placed_coin(told, scene)
    if verb is None:
        return []
    detail = "no gold changed hands: the engine made no sale or payment this turn"
    return [Violation(ViolationKind.UNPAID, verb.group(0), detail)]


def claimed_items(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    truth, lex = scene.turn, scene.lexicon
    if not truth.claimed or find_phrases(sentence, lex.absent_phrases):
        return []
    for claim in truth.claimed:
        pattern = rf"(?<![A-Za-z]){re.escape(claim.term)}(?:s|es)?(?![A-Za-z])"
        for m in re.finditer(pattern, sentence, re.IGNORECASE):
            index = _index_at(tokens, m.start())
            if index is not None and not is_negated(tokens, index, lex.negations, span=3):
                detail = f"{claim.hero} carries no {claim.phrase}: tell the hand finding none"
                return [Violation(ViolationKind.CLAIMED_ITEM, m.group(0), detail)]
    return []


def _npc_words(scene: GuardScene) -> frozenset[str]:
    lex = scene.lexicon
    words = {w for name in scene.present_npcs for w in words_of(name)}
    return frozenset(
        w for w in words if len(w) >= _MIN_NAME_WORD and w not in lex.titles | lex.sentence_starters
    )


def _carried_noun(tokens: list[Token], scene: GuardScene) -> bool:
    """A carried thing, or one a quest asks for (M29.9c T11: "takes your sun-ember")."""
    nouns = scene.item_nouns.keys() | scene.quest_nouns.keys()
    return any(t.lower in nouns or t.lower.rstrip("s") in nouns for t in tokens)


def unmade_handover(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    truth, lex = scene.turn, scene.lexicon
    if not truth.checked or truth.handed or find_phrases(sentence, lex.promise_words):
        return []
    claim = _first_unnegated(sentence, tokens, lex.handover_claims, scene, span=2)
    if claim is None or not find_phrases(sentence, _npc_words(scene)):
        return []
    if not _carried_noun(tokens, scene):
        return []
    detail = "nothing changed hands: no engine event gave the thing to anyone"
    return [Violation(ViolationKind.UNMADE_HANDOVER, claim.group(0), detail)]


def unlit_light(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    truth, lex = scene.turn, scene.lexicon
    nouns = find_phrases(sentence, lex.light_nouns)
    if not truth.checked or truth.lit or not nouns:
        return []
    claim = _first_unnegated(sentence, tokens, lex.light_claims, scene, span=2)
    if claim is None:
        return []
    burning = any(singular_light(m.group(0)) in truth.burning for m in nouns)
    if burning and claim.group(0).casefold() in lex.light_on_claims:
        return []  # M29.7b: a light already burning is told burning, honestly
    detail = "no light was lit: no engine event kindled it"
    return [Violation(ViolationKind.UNLIT_LIGHT, claim.group(0), detail)]
