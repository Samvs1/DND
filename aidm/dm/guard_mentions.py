"""Who a fight sentence names, and which claim phrases it makes (M29.7b, split out in M31.1c).

The shared reading machinery of the per-creature fight checks (`aidm.dm.guard_blows`,
`aidm.dm.guard_results`): mentions are names, their distinctive words, the monster kind and
generic foe words ("the creature"); "it"/"its" means the last foe named (kept across sentences in
`PronounContext`). A subject is a mention that opens a clause; "he"/"she" block the guess.
Negated, hedged ("ready to"), passive ("is struck by") and past ("had struck") phrases are not
claims about this turn.

Public API: `Mention`, `BOUNDARY`, `AFTER_REACH`, `read_mentions(text, ledger, scene, ctx)`,
`claims(text, tokens, phrases, scene, *, past)`, `attacker(text, mentions, start)`,
`target(text, end, mentions)`, `names_of(scene, ids)`, `blow(kind, span, detail)`.
"""

import re
from dataclasses import dataclass

from aidm.dm.fight_ledger import FightLedger
from aidm.dm.guard_pronoun import PronounContext
from aidm.dm.guard_scene import GuardScene
from aidm.dm.guard_text import Token, find_phrases, is_negated
from aidm.dm.guard_types import Violation, ViolationKind

BOUNDARY = re.compile(
    r"[,;:—–]|\b(?:and|then|but|while|as|before|when|until|yet|so|who|which)\b", re.I
)
_PREPOSITIONS = frozenset(
    {"at", "into", "through", "on", "across", "toward", "towards", "past", "over", "under"}
    | {"with", "of", "from", "to", "by", "in", "onto", "around", "against", "beside", "behind"}
)
_DETERMINERS = (
    r"(?:(?:the|a|an|its|his|her|their|second|first|other|nearest|last|next|lead|"
    r"surviving|remaining|wounded)\s+){0,2}"
)
_UNKNOWN = frozenset({"he", "she", "his", "her", "him", "they", "their", "them"})
_IT = frozenset({"it", "its"})
_NOUN_REACH = 2
AFTER_REACH = 45


@dataclass(frozen=True)
class Mention:
    start: int
    end: int
    ids: frozenset[str]  # empty: "he"/"she", someone the guard cannot tell
    subject: bool
    weapon: bool  # "X's bolt": X is told attacking


def _subject_at(text: str, start: int, starts: list[int]) -> bool:
    """A mention opens its clause: at most three words before it, no preposition, no other
    creature named in between ("Bandit attacks Brienne": Brienne is no subject)."""
    cut = max((m.end() for m in BOUNDARY.finditer(text, 0, start)), default=0)
    words = re.findall(r"[a-z']+", text[cut:start].casefold())
    crowded = any(cut <= s < start for s in starts)
    return len(words) <= 3 and not set(words) & _PREPOSITIONS and not crowded


def _weapon_after(text: str, end: int, scene: GuardScene) -> bool:
    lex = scene.lexicon
    nouns = lex.attack_nouns | lex.weapon_nouns
    words = re.findall(r"[a-z-]+", text[end : end + 40].casefold())[: _NOUN_REACH + 1]
    joined = [" ".join(words[i : i + 2]) for i in range(len(words))]
    return any(w in nouns for w in words) or any(j in nouns for j in joined)


type _Raw = tuple[int, int, frozenset[str], bool]  # start, end, ids, possessive


def _named(text: str, ledger: FightLedger) -> list[_Raw]:
    taken: list[tuple[int, int]] = []
    found: list[_Raw] = []
    for term, ids in ledger.terms:
        pattern = rf"(?<![A-Za-z]){re.escape(term)}('s|s)?(?![A-Za-z])"
        for m in re.finditer(pattern, text, re.I):
            if any(a < m.end() and m.start() < b for a, b in taken):
                continue
            taken.append((m.start(), m.end()))
            found.append((m.start(), m.end(), ids, m.group(1) == "'s"))
    return sorted(found)


def _pronouns(text: str, named: list[_Raw], ledger: FightLedger, ctx: PronounContext):
    out: list[_Raw] = []
    for m in re.finditer(r"\b[A-Za-z]+\b", text):
        low = m.group(0).casefold()
        if low in _UNKNOWN:
            out.append((m.start(), m.end(), frozenset(), False))
        elif low in _IT:
            before = [n for n in named if n[1] <= m.start() and n[2] <= ledger.foes]
            ids = before[-1][2] if before else ctx.last_foe
            if ids:
                out.append((m.start(), m.end(), ids, low == "its"))
    return out


def read_mentions(text: str, ledger: FightLedger, scene: GuardScene, ctx: PronounContext):
    named = _named(text, ledger)
    raw = sorted([*named, *_pronouns(text, named, ledger, ctx)])
    starts = [r[0] for r in raw]
    out: list[Mention] = []
    for start, end, ids, possessive in raw:
        weapon = possessive and _weapon_after(text, end, scene)
        out.append(Mention(start, end, ids, _subject_at(text, start, starts), weapon))
    foes = [n for n in named if n[2] <= ledger.foes]
    if foes:
        ctx.last_foe = foes[-1][2]
    return out


def claims(
    text: str, tokens: list[Token], phrases: frozenset[str], scene: GuardScene, *, past: bool = True
):
    """Claim phrases about this turn; `past` False keeps "before slumping" (a fall phrase)."""
    lex = scene.lexicon
    for m in find_phrases(text, phrases):
        index = next((i for i, t in enumerate(tokens) if t.start >= m.start()), len(tokens))
        before = {t.lower for t in tokens[max(0, index - 2) : index]}
        if is_negated(tokens, index, lex.negations, span=2) or before & lex.passive_markers:
            continue
        if past and {t.lower for t in tokens[max(0, index - 3) : index]} & lex.past_markers:
            continue
        after = re.findall(r"[a-z']+", text[m.end() : m.end() + 24].casefold())[:2]
        if after[:1] == ["by"] or _excluded(after, lex.blow_exclusions):
            continue
        yield m


def _excluded(after: list[str], exclusions: frozenset[str]) -> bool:
    return bool(set(after) & exclusions) or " ".join(after) in exclusions


def attacker(text: str, found: list[Mention], start: int) -> Mention | None:
    """The subject (or "X's bolt") the phrase at `start` belongs to: in its own clause, or
    across "and"/"then" only when the verb follows right after ("and swings")."""
    before = [n for n in found if n.end <= start and (n.subject or n.weapon)]
    if not before:
        return None
    who = before[-1]
    cut = max((m.end() for m in BOUNDARY.finditer(text, who.end, start)), default=None)
    if cut is not None and len(re.findall(r"[a-z']+", text[cut:start].casefold())) > 1:
        return None
    return who


def names_of(scene: GuardScene, ids: frozenset[str]) -> str:
    return ", ".join(sorted({scene.turn.fight.names.get(i, i) for i in ids}))


def blow(kind: ViolationKind, span: str, detail: str) -> list[Violation]:
    return [Violation(kind, span, detail)]


def target(text: str, end: int, found: list[Mention]) -> Mention | None:
    for n in found:
        gap = text[end : n.start]
        if n.start >= end and re.fullmatch(rf"\s*(?:in\s+|on\s+)?{_DETERMINERS}", gap, re.I):
            return n
    return None
