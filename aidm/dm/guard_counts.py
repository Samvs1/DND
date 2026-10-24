"""Foe-count check of the prose guard (M31.1c, docs/playtests/M31_round4.md V17).

Round 4 told "each robed cultist", "the second cultist" and "robed cultists" while the fight
held ONE cultist (full 66, 68, 228). `foe_counts` reads ONE sentence against the fight's
`FightLedger.kinds` (each foe kind's head noun -> how many the fight holds, dead or alive, with
the present NPCs of that word): a plural of the head ("cultists", "wolves") claims two, a count
word before it ("two", "both", "second", "other", "each": lexicon `count_words`) claims its
number; a claim above what the fight holds is flagged, unless negated ("no other cultist").

M32.1b X14 (round 5 full 1223: "three shapes" behind a one-foe offer): `figure_counts` counts
unnamed figures (`figure_words`: "shapes", "figures") after a count word, and "the three
behind him" (three besides him), against the foes of an offer (`GuardScene.foes_here`: its
monsters and master; off during a fight, where "two charred shapes" are debris).

Public API: `plurals(head) -> frozenset[str]`, `foe_counts(text, scene) -> list[Violation]`,
`figure_counts(text, scene) -> list[Violation]`.
"""

import re

from aidm.dm.guard_scene import GuardScene
from aidm.dm.guard_text import is_negated, tokenize
from aidm.dm.guard_types import Violation, ViolationKind

_GAP = r"(?:[a-z-]+\s+)?"  # one adjective at most: "each robed cultist", not "third catches the"


def plurals(head: str) -> frozenset[str]:
    forms = {f"{head}s", f"{head}es"}
    if head.endswith("y"):
        forms.add(f"{head[:-1]}ies")
    if head.endswith("f"):
        forms.add(f"{head[:-1]}ves")
    if head.endswith("fe"):
        forms.add(f"{head[:-2]}ves")
    if head.endswith("man"):
        forms.add(f"{head[:-3]}men")
    return frozenset(forms)


def _negated(text: str, start: int, scene: GuardScene) -> bool:
    tokens = tokenize(text)
    index = next((i for i, t in enumerate(tokens) if t.start >= start), len(tokens))
    return is_negated(tokens, index, scene.lexicon.negations, span=2)


def _claimed(text: str, head: str, scene: GuardScene) -> tuple[str, int] | None:
    """The biggest count the sentence claims for `head`, with the words that claim it."""
    counts = scene.lexicon.count_words
    many = "|".join(re.escape(p) for p in sorted(plurals(head), key=len, reverse=True))
    words = "|".join(re.escape(w) for w in sorted(counts, key=len, reverse=True))
    best: tuple[str, int] | None = None
    if words:
        pattern = rf"\b({words})\s+{_GAP}(?:{many}|{re.escape(head)})\b"
        for m in re.finditer(pattern, text, re.I):
            n = counts[m.group(1).casefold()]
            if not _negated(text, m.start(), scene) and (best is None or n > best[1]):
                best = (m.group(0), n)
    for m in re.finditer(rf"\b(?:{many})\b", text, re.I):
        if best is None and not _negated(text, m.start(), scene):
            best = (m.group(0), 2)
    return best


def _figures(text: str, scene: GuardScene) -> tuple[str, int] | None:
    """M32.1b X14: the biggest count of unnamed figures ("three shapes", "the three behind
    him": that many besides the one before them)."""
    lex = scene.lexicon
    counts = lex.count_words
    if not counts or not lex.figure_words:
        return None
    words = "|".join(re.escape(w) for w in sorted(counts, key=len, reverse=True))
    nouns = "|".join(re.escape(w) for w in sorted(lex.figure_words, key=len, reverse=True))
    best: tuple[str, int] | None = None
    patterns = (
        (rf"\b({words})\s+{_GAP}(?:{nouns})\b", 0),
        (rf"\bthe\s+({words})\s+(?:behind|beside|with|around)\s+(?:him|her|it|them)\b", 1),
    )
    for pattern, extra in patterns:
        for m in re.finditer(pattern, text, re.I):
            n = counts[m.group(1).casefold()] + extra
            if not _negated(text, m.start(), scene) and (best is None or n > best[1]):
                best = (m.group(0), n)
    return best


def figure_counts(text: str, scene: GuardScene) -> list[Violation]:
    """More unnamed figures than an offer's foes."""
    held = scene.foes_here
    if held <= 0:
        return []
    claim = _figures(text, scene)
    if claim is None or claim[1] <= held:
        return []
    detail = f"only {held} foe{'s' if held > 1 else ''} here: tell no other shapes or figures"
    return [Violation(ViolationKind.FOE_COUNT, claim[0], detail)]


def foe_counts(text: str, scene: GuardScene) -> list[Violation]:
    for head, held in sorted(scene.turn.fight.kinds.items()):
        claim = _claimed(text, head, scene)
        if claim is not None and claim[1] > held:
            detail = f"the fight holds {held} {head}: no other {head} is here"
            return [Violation(ViolationKind.FOE_COUNT, claim[0], detail)]
    return []
