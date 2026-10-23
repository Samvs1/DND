"""Light, place and pick-up truth of the prose guard (M29.7b, M29_round2.md R2 R12 R17).

Owner rule: light versus stealth is never hidden, so the prose tells the engine's light state.
Each check reads ONE sentence against the scene's `TurnTruth` (`aidm.dm.guard_turn`, built from
`aidm.dm.turn_world`); vocabulary is data (data/bg3/guard_lexicon.json):
- `light_state` (R17): a light told going out or staying dark (`light_out_claims`: "stays dark",
  "the flame will not come", "pinches the wick") while that light burns and no event put it
  out; a light told already burning (`light_on_claims`) when no such light burns.
- `short_travel` (R2): the travel stopped one place short of the destination the player named;
  the destination named without a distance word (`travel_hedges`: "toward", "ahead", "beyond")
  tells the party there.
- `unmade_pickup` (R12): a thing told picked up ("picks up", "lifts the chime from the dust")
  when no event put anything into a hero's hands.

Public API: `light_state`, `short_travel`, `unmade_pickup`, `singular_light(noun)`.
"""

import re

from aidm.dm.guard_scene import GuardScene
from aidm.dm.guard_text import Token, find_phrases, is_negated, plain
from aidm.dm.guard_types import Violation, ViolationKind

_FLAME_WORDS = ("wick", "flame", "flames")
_HEAD_WORD = 6
_LIFT_REACH = 5  # words between "lifts" and "from the" ("lifts the unfinished chime from")


def _unnegated(sentence: str, tokens: list[Token], phrases: frozenset[str], scene: GuardScene):
    for m in find_phrases(sentence, phrases):
        index = next((i for i, t in enumerate(tokens) if t.start >= m.start()), len(tokens))
        if not is_negated(tokens, index, scene.lexicon.negations, span=2):
            return m
    return None


def singular_light(noun: str) -> str:
    low = noun.casefold()
    return low[:-2] if low.endswith("hes") else low.removesuffix("s")


def light_state(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    truth, lex = scene.turn, scene.lexicon
    if not truth.checked:
        return []
    nouns = {singular_light(m.group(0)) for m in find_phrases(sentence, lex.light_nouns)}
    out = _unnegated(sentence, tokens, lex.light_out_claims, scene)
    if out is not None and not truth.ended:
        flame = find_phrases(sentence, frozenset(_FLAME_WORDS))
        lit = [n for n in sorted(nouns) if n in truth.burning]
        lit = lit or ([] if nouns or not flame else sorted(truth.burning))
        if lit:
            who = truth.burning[lit[0]]
            detail = f"{who}'s {lit[0]} is lit and burning: it did not go out and can be seen"
            return [Violation(ViolationKind.LIGHT_STATE, out.group(0), detail)]
    on = _unnegated(sentence, tokens, lex.light_on_claims, scene)
    if on is not None and nouns and not nouns & set(truth.burning):
        detail = f"no {sorted(nouns)[0]} burns: none was lit"
        return [Violation(ViolationKind.LIGHT_STATE, on.group(0), detail)]
    return []


def _place_pattern(name: str) -> str:
    bare = plain(name).casefold().strip().removeprefix("the ").strip()
    words = bare.split()
    forms = [re.escape(bare)]
    if len(words) > 1 and len(words[-1]) >= _HEAD_WORD:
        forms.append(re.escape(words[-1]))
    return rf"(?<![a-z])(?:{'|'.join(forms)})(?![a-z])"


def short_travel(sentence: str, scene: GuardScene) -> list[Violation]:
    dest = scene.turn.short_of
    if not dest or find_phrases(sentence, scene.lexicon.travel_hedges):
        return []
    m = re.search(_place_pattern(dest), plain(sentence).casefold())
    if m is None:
        return []
    detail = f"the party stopped one place short of {dest}: it is not there, nothing of it is seen"
    return [Violation(ViolationKind.SHORT_TRAVEL, m.group(0), detail)]


def _lifted_from(sentence: str, scene: GuardScene) -> re.Match[str] | None:
    ordered = sorted(scene.lexicon.pickup_words, key=len, reverse=True)
    verbs = "|".join(re.escape(v) for v in ordered)
    pattern = rf"\b(?:{verbs})\b(?:\s+[\w'-]+){{1,{_LIFT_REACH}}}?\s+from\s+the\b"
    return re.search(pattern, plain(sentence), re.IGNORECASE)


def unmade_pickup(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    truth, lex = scene.turn, scene.lexicon
    if not truth.checked or truth.picked or find_phrases(sentence, lex.promise_words):
        return []
    claim = _unnegated(sentence, tokens, lex.pickup_claims, scene) or _lifted_from(sentence, scene)
    if claim is None:
        return []
    nouns = set(scene.item_nouns) | lex.gear_nouns
    if not any(t.lower in nouns or t.lower.rstrip("s") in nouns for t in tokens):
        return []
    detail = "nothing was picked up: no engine event put anything into a hero's hands"
    return [Violation(ViolationKind.UNMADE_PICKUP, claim.group(0), detail)]
