"""Goods-truth checks of the prose guard (M29.5c, docs/playtests/M29_round1.md G1 G3 G9 G31).

Gold, gear and hand-overs change only through engine events (the shop, `give`, gear uses). Each
check reads ONE sentence against the scene's `TurnTruth` (`aidm.dm.guard_turn`); vocabulary is
data (data/bg3/guard_lexicon.json):
- `unpaid_coin` (G1): a payment ("pays the ten gold", "counts out a gold piece", "passes over
  ... coin") when these events changed no gold; promises ("will you pay") and quoted speech
  are not claims.
- `claimed_items` (G3): a thing the player used as the hero's own that the hero does not carry
  ("Brienne raises the potion", "Rook's silk rope", "Elowen's javelin"), unless the sentence tells
  it as absent ("no such potion", "finds nothing").
- `unmade_handover` (G31): a present NPC told taking or holding a carried thing ("Ranna folds her
  fingers around the stiff scroll") when no keepsake or item changed hands.
- `unlit_light` (G9): a torch, lantern or candle told catching flame when no light was lit.

Public API: `unpaid_coin`, `claimed_items`, `unmade_handover`, `unlit_light`.
"""

import re

from aidm.dm.guard_scene import GuardScene, words_of
from aidm.dm.guard_text import QUOTE_MARKS, Token, find_phrases, is_negated
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


def unpaid_coin(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    truth, lex = scene.turn, scene.lexicon
    if not truth.checked or truth.paid or any(q in sentence for q in QUOTE_MARKS):
        return []
    if not find_phrases(sentence, lex.coin_nouns) or find_phrases(
        sentence, lex.promise_words | lex.payment_refusals
    ):
        return []
    verb = _first_unnegated(sentence, tokens, lex.payment_verbs, scene)
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
    return any(
        t.lower in scene.item_nouns or t.lower.rstrip("s") in scene.item_nouns for t in tokens
    )


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
    if not truth.checked or truth.lit or not find_phrases(sentence, lex.light_nouns):
        return []
    claim = _first_unnegated(sentence, tokens, lex.light_claims, scene, span=2)
    if claim is None:
        return []
    detail = "no light was lit: no engine event kindled it"
    return [Violation(ViolationKind.UNLIT_LIGHT, claim.group(0), detail)]
