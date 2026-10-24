"""Promises, errands and stale foes in prose (M32.1b, docs/playtests/M31_round5.md X10 X11 X14).

Round 5: a favour's asker promised "fifteen silver" though favours pay only goodwill (quests
391, 395), a peddler set "a run of silverleaf to the manse gate" for "a copper or two" that was
never a quest (quests 42-44), and a parley with the ghast at the Leech-Beds was told as the
earlier bandit captain (full 1256). Each check reads ONE sentence; narration and an NPC's own
speech alike (`GuardScene.talk`, `aidm.dm.guard_turn.TalkTruth`); vocabulary is data
(data/bg3/guard_lexicon.json):
- `promised_coin`: a `coin_promises` phrase ("I will pay", "a copper or two", "fair coin")
  with a coin noun, unless coin may be promised this turn (a shop at work, or a quest other
  than a favour asked or held by a giver standing here); negated phrases are no promise;
- `unasked_errand`: an `errand_offers` phrase ("a small errand", "a run of") when no quest
  event happened and no open quest's giver stands here: errands exist only through the favour
  tool (`offer_favour`);
- `stale_foe`: a foe kind of the encounter catalogue named while it is not in play and other
  foes are (`GuardScene.stale_foes`, `aidm.dm.guard_present`); a one-word kind counts only as
  a creature noun (M33.2 finding 6, `creature_determiners`, `creature_noun_breaks`).

Public API: `promised_coin`, `unasked_errand`, `stale_foe`.
"""

import re

from aidm.dm.guard_scene import GuardScene
from aidm.dm.guard_text import Token, find_phrases, is_negated
from aidm.dm.guard_types import Violation, ViolationKind


def _unnegated(
    sentence: str, tokens: list[Token], phrases: frozenset[str], scene: GuardScene
) -> re.Match[str] | None:
    for m in find_phrases(sentence, phrases):
        index = next((i for i, t in enumerate(tokens) if t.start >= m.start()), len(tokens))
        if not is_negated(tokens, index, scene.lexicon.negations, span=2):
            return m
    return None


def promised_coin(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    talk, lex = scene.talk, scene.lexicon
    if not talk.checked or talk.coin_ok or not find_phrases(sentence, lex.coin_nouns):
        return []
    claim = _unnegated(sentence, tokens, lex.coin_promises, scene)
    if claim is None:
        return []
    detail = (
        "nobody promises coin here: a favour pays only goodwill and rewards are the engine's;"
        " ask the party to come back and tell them instead"
    )
    return [Violation(ViolationKind.COIN_PROMISED, claim.group(0), detail)]


def unasked_errand(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    talk = scene.talk
    if not talk.checked or talk.errand_ok:
        return []
    claim = _unnegated(sentence, tokens, scene.lexicon.errand_offers, scene)
    if claim is None:
        return []
    detail = "no errand or task was asked: tell none (only an asked favour or quest is one)"
    return [Violation(ViolationKind.UNASKED_ERRAND, claim.group(0), detail)]


def _creature_noun(sentence: str, tokens: list[Token], m: re.Match[str], scene: GuardScene) -> bool:
    """M33.2 finding 6: a one-word kind names a creature only as a noun with a determiner (an
    article, count, ordinal or possessive up to two words before: "the scouts", "two hulking
    zombies", "Vex's bandits") or as the sentence's first word ("Zombies lurch"); never before
    "of" or a hyphen ("a skeleton of a boat", "zombie-like"), and never as a verb ("Rook scouts
    the treeline")."""
    if len(m.group(0).split()) > 1:
        return True
    lex = scene.lexicon
    index = next((i for i, t in enumerate(tokens) if t.start >= m.start()), len(tokens))
    after = tokens[index + 1].lower if index + 1 < len(tokens) else ""
    if sentence[m.end() : m.end() + 1] == "-" or after in lex.creature_noun_breaks:
        return False
    if index == 0 or (index < len(tokens) and tokens[index].initial):
        return True
    marks = lex.creature_determiners | lex.count_words.keys() | lex.ordinal_words.keys()
    before = tokens[max(0, index - 2) : index]
    return any(t.lower in marks or t.lower.endswith("'s") for t in before)


def stale_foe(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    if not scene.stale_foes:
        return []
    terms = frozenset(scene.stale_foes.keys() | {f"{t}s" for t in scene.stale_foes})
    negations = scene.lexicon.negations
    for m in find_phrases(sentence, terms):
        index = next((i for i, t in enumerate(tokens) if t.start >= m.start()), len(tokens))
        if is_negated(tokens, index, negations, span=2):
            continue
        if not _creature_noun(sentence, tokens, m, scene):
            continue
        low = m.group(0).casefold()
        name = scene.stale_foes.get(low) or scene.stale_foes.get(low[:-1], m.group(0))
        detail = f"no {name} is here now: tell only the foes of this scene"
        return [Violation(ViolationKind.STALE_FOE, m.group(0), detail)]
    return []
