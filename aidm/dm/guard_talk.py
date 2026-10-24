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
  foes are (`GuardScene.stale_foes`, `aidm.dm.guard_present`).

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


def stale_foe(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    if not scene.stale_foes:
        return []
    terms = scene.stale_foes.keys() | {f"{t}s" for t in scene.stale_foes}
    claim = _unnegated(sentence, tokens, frozenset(terms), scene)
    if claim is None:
        return []
    low = claim.group(0).casefold()
    name = scene.stale_foes.get(low) or scene.stale_foes.get(low[:-1], claim.group(0))
    detail = f"no {name} is here now: tell only the foes of this scene"
    return [Violation(ViolationKind.STALE_FOE, claim.group(0), detail)]
