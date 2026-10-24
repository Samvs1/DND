"""Per-creature fight checks of the prose guard (M29.7b, docs/playtests/M29_round2.md R19).

M29.5c's G6 check covered only fights where no blow was resolved. Round 2 told foe charges and
claw hits beside a hero's lone miss, shafts finding their mark in heroes nobody shot, a kill
credited to the wrong hero and a bolt "skipping off" a foe it hit. Each check reads ONE sentence
against the turn's `FightLedger` (`aidm.dm.fight_ledger`); vocabulary is data
(data/bg3/guard_lexicon.json):
- `phantom_blows`: a creature told attacking (the subject of a `strike_claims` phrase, or "X's
  bolt/claws/spell" beside a blow, hit, miss or kill phrase) that made no blow in these events;
- `phantom_hits`: a creature told hit (right after a `hit_claims` phrase: "clubs Elowen", "find
  their mark in Elowen", or "Rook takes a graze") that lost no hit points in these events;
- `false_misses`: a `miss_claims` phrase ("skips off", "goes wide") for an attacker whose every
  attack of these events hit;
- `wrong_killers`: a kill phrase tied to "X's bolt" when someone else dealt the killing damage;
- M29.9c (round 3 T4): attempts and near misses count as blows (`attempt_claims`: "springs at
  Tamsin", "jaws snapping shut a hand's breadth from her wrist");
  a spell's harm (`harm_claims`: "scorching its hide") on a creature that lost no hit points (a
  saved Sacred Flame) is a phantom hit; `phantom_falls`: a `fall_claims` phrase ("slumping into the
  cinders", "sends it crashing") about a creature none of whose possible meanings fell: one that
  fled (FLED_TOLD_DEAD) or one still standing (UNHURT_DECLARED_DOWN).
Mentions are names, their distinctive words, the monster kind and generic foe words ("the
creature"); "it"/"its" means the last foe named (kept across sentences in `PronounContext`). A
subject is a mention that opens a clause; "he"/"she" block the guess (nothing is flagged).
Negated, hedged ("ready to"), passive ("is struck by") and past ("had struck") phrases are not
claims about this turn.

Public API: `fight_truth(sentence, tokens, scene, context) -> list[Violation]`.
"""

import re
from dataclasses import dataclass

from aidm.dm.fight_ledger import FightLedger
from aidm.dm.guard_pronoun import PronounContext
from aidm.dm.guard_scene import GuardScene
from aidm.dm.guard_text import Token, find_phrases, is_negated, plain
from aidm.dm.guard_types import Violation, ViolationKind

_BOUNDARY = re.compile(
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
_KILL_REACH = 40
_AFTER_REACH = 45


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
    cut = max((m.end() for m in _BOUNDARY.finditer(text, 0, start)), default=0)
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


def _mentions(text: str, ledger: FightLedger, scene: GuardScene, ctx: PronounContext):
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


def _claims(
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


def _attacker(text: str, mentions: list[Mention], start: int) -> Mention | None:
    """The subject (or "X's bolt") the phrase at `start` belongs to: in its own clause, or
    across "and"/"then" only when the verb follows right after ("and swings")."""
    before = [n for n in mentions if n.end <= start and (n.subject or n.weapon)]
    if not before:
        return None
    who = before[-1]
    cut = max((m.end() for m in _BOUNDARY.finditer(text, who.end, start)), default=None)
    if cut is not None and len(re.findall(r"[a-z']+", text[cut:start].casefold())) > 1:
        return None
    return who


def _names(scene: GuardScene, ids: frozenset[str]) -> str:
    return ", ".join(sorted({scene.turn.fight.names.get(i, i) for i in ids}))


def _blow(kind: ViolationKind, span: str, detail: str) -> list[Violation]:
    return [Violation(kind, span, detail)]


def _armed(text: str, tokens, mentions: list[Mention], scene: GuardScene) -> list[Mention]:
    """ "X's bolt" told as attacking: a blow, hit or miss phrase right after it, or a kill phrase
    right before it ("folds around Brienne's bolt")."""
    lex = scene.lexicon
    told = lex.strike_claims | lex.hit_claims | lex.miss_claims | lex.attempt_claims
    after = list(_claims(text, tokens, told, scene))
    kills = list(_claims(text, tokens, lex.kill_claims | lex.blow_claims, scene))
    out: list[Mention] = []
    for n in mentions:
        if not n.weapon or not n.ids:
            continue
        follows = any(0 <= m.start() - n.end <= _AFTER_REACH for m in after)
        preceded = any(not text[m.end() : n.start].strip() for m in kills if m.end() <= n.start)
        if follows or preceded:
            out.append(n)
    return out


def _phantom_blows(text: str, tokens, mentions, scene: GuardScene) -> list[Violation]:
    ledger, lex = scene.turn.fight, scene.lexicon
    told: list[tuple[str, Mention]] = []
    phrases = lex.strike_claims | lex.hit_claims | lex.attempt_claims
    for m in _claims(text, tokens, phrases, scene):
        who = _attacker(text, mentions, m.start())
        if who is not None and who.ids:
            told.append((m.group(0), who))
    told += [(text[n.start : n.end], n) for n in _armed(text, tokens, mentions, scene)]
    for span, who in told:
        if not who.ids & ledger.acted:
            detail = (
                f"{_names(scene, who.ids)} made no attack in these events: tell no blow by them"
            )
            return _blow(ViolationKind.PHANTOM_BLOW, span, detail)
    return []


def _target(text: str, end: int, mentions: list[Mention]) -> Mention | None:
    for n in mentions:
        gap = text[end : n.start]
        if n.start >= end and re.fullmatch(rf"\s*(?:in\s+|on\s+)?{_DETERMINERS}", gap, re.I):
            return n
    return None


def _grazed(text: str, mentions: list[Mention], scene: GuardScene) -> list[tuple[str, Mention]]:
    nouns = "|".join(sorted(scene.lexicon.graze_nouns))
    out: list[tuple[str, Mention]] = []
    for n in mentions:
        m = re.match(rf"\s+takes\s+an?\s+(?:[a-z-]+\s+){{0,2}}?({nouns})\b", text[n.end :], re.I)
        if m is not None and n.subject:
            out.append((m.group(1), n))
    return out


def _phantom_hits(text: str, tokens, mentions, scene: GuardScene) -> list[Violation]:
    ledger = scene.turn.fight
    hits = [
        (m.group(0), _target(text, m.end(), mentions))
        for m in _claims(text, tokens, scene.lexicon.hit_claims | scene.lexicon.harm_claims, scene)
    ]
    for span, who in [*hits, *_grazed(text, mentions, scene)]:
        if who is not None and who.ids and not who.ids & ledger.struck:
            detail = f"{_names(scene, who.ids)} lost no hit points in these events: no blow landed"
            return _blow(ViolationKind.PHANTOM_HIT, span, detail)
    return []


def _false_misses(text: str, tokens, mentions, scene: GuardScene) -> list[Violation]:
    ledger = scene.turn.fight
    for m in _claims(text, tokens, scene.lexicon.miss_claims, scene):
        who = _attacker(text, mentions, m.start())
        if who is None or not who.ids or who.ids & ledger.missed_by:
            continue
        if who.ids & ledger.hit_by:
            detail = f"{_names(scene, who.ids)} hit in these events: tell the hit, not a miss"
            return _blow(ViolationKind.FALSE_MISS, m.group(0), detail)
    return []


def _wrong_killers(text: str, mentions: list[Mention], scene: GuardScene) -> list[Violation]:
    ledger, lex = scene.turn.fight, scene.lexicon
    if not ledger.killers:
        return []
    for m in find_phrases(text, lex.kill_claims | lex.blow_claims):
        armed = [n for n in mentions if n.weapon and n.ids]
        near = [
            n for n in armed if min(abs(n.start - m.end()), abs(m.start() - n.end)) <= _KILL_REACH
        ]
        if not near:
            continue
        who = min(near, key=lambda n: min(abs(n.start - m.end()), abs(m.start() - n.end)))
        if who.ids & ledger.acted and not who.ids & ledger.killers:
            killers = _names(scene, ledger.killers)
            detail = f"the killing blow was {killers}'s, not {_names(scene, who.ids)}'s"
            return _blow(ViolationKind.WRONG_KILLER, text[who.start : who.end], detail)
    return []


def _faller(text: str, mentions: list[Mention], start: int, end: int) -> Mention | None:
    """Who a fall phrase is about: a creature inside it ("sends it crashing"), else the clause's
    subject (never "X's bolt": the weapon does not fall)."""
    inside = [n for n in mentions if start <= n.start < end and n.ids]
    if inside:
        return inside[0]
    before = [n for n in mentions if n.end <= start and n.subject and not n.weapon]
    if not before:
        return None
    who = before[-1]
    cut = max((m.end() for m in _BOUNDARY.finditer(text, who.end, start)), default=None)
    if cut is not None and len(re.findall(r"[a-z']+", text[cut:start].casefold())) > 1:
        return None
    return who


def _phantom_falls(text: str, tokens, mentions, scene: GuardScene) -> list[Violation]:
    ledger = scene.turn.fight
    for m in _claims(text, tokens, scene.lexicon.fall_claims, scene, past=False):
        who = _faller(text, mentions, m.start(), m.end())
        if who is None or not who.ids or who.ids & ledger.downed:
            continue
        if not who.ids <= ledger.fled | ledger.standing:
            continue  # it may mean one that is already down
        names = _names(scene, who.ids)
        if who.ids & ledger.fled:
            detail = f"{names} fled the fight alive: never tell them killed or fallen"
            return _blow(ViolationKind.FLED_TOLD_DEAD, m.group(0), detail)
        detail = f"{names} still stands: no engine event dropped them"
        return _blow(ViolationKind.UNHURT_DECLARED_DOWN, m.group(0), detail)
    return []


def fight_truth(
    sentence: str, tokens: list[Token], scene: GuardScene, context: PronounContext
) -> list[Violation]:
    truth = scene.turn
    ledger = truth.fight
    if not truth.checked or not ledger.active:
        return []
    if not (truth.in_fight or ledger.acted or ledger.struck):
        return []
    text = plain(sentence)
    mentions = _mentions(text, ledger, scene, context)
    if find_phrases(text, scene.lexicon.attack_hedges):
        return []
    return [
        *_phantom_blows(text, tokens, mentions, scene),
        *_phantom_hits(text, tokens, mentions, scene),
        *_false_misses(text, tokens, mentions, scene),
        *_wrong_killers(text, mentions, scene),
        *_phantom_falls(text, tokens, mentions, scene),
    ]
