"""Fight-truth checks of the prose guard (M29.5c, docs/playtests/M29_round1.md G6 G7 G21 G32 G35).

Each check reads ONE sentence against the frozen `GuardScene` and its `TurnTruth`
(`aidm.dm.guard_turn`); vocabulary is data (data/bg3/guard_lexicon.json):
- `unresolved_blows` (G6, G32): while a fight runs and these events resolved no blow (no attack,
  damage, spell or monster action), an attack claim ("springs at Rook", "lunges", "drops it") that
  is neither negated nor hedged ("ready to", "about to") is flagged: nothing was rolled.
- `wrong_weapon` (G7): an attacker of these events named with a weapon it did not attack with
  ("Brienne's sword" for her light crossbow; "with his mace"); spell attacks are not judged.
- `unhurt_wounded` (G32): a hero at full HP whom no event touched, told with a wound in the same
  clause ("where the rat-bites mark them", "reopens Brienne's rat-bites").
- `pronoun_down` (G21): "he/she/it ... lies still" when every creature the pronoun can mean (named
  before it in the sentence, else in the last sentence that named anyone) is still standing.
- `dead_alive` (G35): a dead creature or NPC told as living on ("Regent Varek kept his word").

Public API: `DOWN_PRONOUNS`, `unresolved_blows`, `wrong_weapon`, `unhurt_wounded`,
`pronoun_down`, `dead_alive`.
"""

import re

from aidm.dm.guard_pronoun import PronounContext
from aidm.dm.guard_scene import GuardScene
from aidm.dm.guard_text import Token, find_phrases, is_negated, plain
from aidm.dm.guard_types import Violation, ViolationKind

DOWN_PRONOUNS = frozenset({"he", "she", "it"})
_REACH = 90
_ALIVE_REACH = 40
_NOT_BODY = r"(?![a-z-])(?!\s+(?:arm|hand|side|shoulder))"  # "her sword arm" is a body part
_CLAUSE = re.compile(r"\b(?:while|whilst|as|when|but|though|until|before|after)\b|[;:,]", re.I)


def _index_at(tokens: list[Token], start: int) -> int | None:
    return next((i for i, t in enumerate(tokens) if t.start == start), None)


def _unnegated(sentence: str, tokens: list[Token], phrases: frozenset[str], scene: GuardScene):
    lex = scene.lexicon
    for m in find_phrases(sentence, phrases):
        index = _index_at(tokens, m.start())
        if index is not None and not is_negated(tokens, index, lex.negations, span=2):
            return m
    return None


def unresolved_blows(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    truth = scene.turn
    if not truth.checked or not truth.in_fight or truth.blows:
        return []
    lex = scene.lexicon
    if find_phrases(sentence, lex.attack_hedges):
        return []
    hit = _unnegated(sentence, tokens, lex.attack_claims | lex.blow_claims, scene)
    if hit is None:
        return []
    detail = "no attack was rolled yet: nobody struck, bit, hit or hurt anyone"
    return [Violation(ViolationKind.UNRESOLVED_BLOW, hit.group(0), detail)]


def _nouns(scene: GuardScene) -> str:
    return "|".join(re.escape(n) for n in sorted(scene.lexicon.weapon_nouns, key=len, reverse=True))


def wrong_weapon(sentence: str, scene: GuardScene) -> list[Violation]:
    if not scene.turn.weapons:
        return []
    low = plain(sentence).casefold()
    nouns = _nouns(scene)
    for term, used in sorted(scene.turn.weapons.items()):
        name = re.escape(term)
        owned = rf"(?<![a-z]){name}'s(?:\s+[a-z-]+){{0,2}}?\s+({nouns}){_NOT_BODY}"
        held = (
            rf"(?<![a-z]){name}(?![a-z'])[^.;:]{{0,60}}?\bwith\s+(?:his|her|their|its|a|an|the|one)"
            rf"\s+(?:[a-z-]+\s+){{0,2}}?({nouns}){_NOT_BODY}"
        )
        for pattern in (owned, held):
            m = re.search(pattern, low)
            if m is not None and m.group(1) not in used:
                detail = f"{term} attacked with other gear: name only the resolved attack's weapon"
                return [Violation(ViolationKind.WRONG_WEAPON, m.group(1), detail)]
    return []


def _clause(sentence: str, start: int) -> str:
    found = _CLAUSE.search(sentence, start)
    end = found.start() if found is not None else len(sentence)
    return sentence[start : min(end, start + _REACH)]


def _others(scene: GuardScene, name: str) -> list[str]:
    names = {*scene.party, *scene.living_terms}
    return [n for n in names if n.casefold() not in name.casefold() and len(n) >= 3]


def unhurt_wounded(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    truth = scene.turn
    lex = scene.lexicon
    if not truth.checked or not truth.unhurt or not find_phrases(sentence, lex.wound_claims):
        return []
    text = plain(sentence)
    for term, name in sorted(truth.unhurt.items(), key=lambda p: -len(p[0])):
        for m in re.finditer(rf"(?<![A-Za-z]){re.escape(term)}(?:'s)?(?![A-Za-z])", text, re.I):
            after = _clause(text, m.end())
            wound = find_phrases(after, lex.wound_claims)
            if not wound or find_phrases(after[: wound[0].start()], _others(scene, name)):
                continue
            index = _index_at(tokens, m.end() + wound[0].start())
            if index is None or not is_negated(tokens, index, lex.negations, span=2):
                detail = f"{name} is unhurt: no engine event wounded them"
                return [Violation(ViolationKind.UNHURT_WOUNDED, wound[0].group(0), detail)]
    return []


def _mentions(sentence: str, scene: GuardScene) -> list[tuple[int, str, bool]]:
    terms = [(t, n, True) for t, n in scene.standing_terms.items()]
    terms += [(t, n, False) for t, n in scene.living_terms.items() if t not in scene.standing_terms]
    terms += [(n, n, False) for n in scene.dead]
    found: list[tuple[int, str, bool]] = []
    for term, name, up in terms:
        pattern = rf"(?<![A-Za-z]){re.escape(term)}(?:'s|s)?(?![A-Za-z])"
        found += [(m.start(), name, up) for m in re.finditer(pattern, sentence, re.I)]
    return sorted(found)


def pronoun_down(
    sentence: str, tokens: list[Token], scene: GuardScene, context: PronounContext
) -> list[Violation]:
    lex = scene.lexicon
    mentions = _mentions(sentence, scene)
    found: list[Violation] = []
    if find_phrases(sentence, lex.defeat_claims):
        for token in tokens:
            if token.lower not in DOWN_PRONOUNS or found:
                continue
            before = {name: up for start, name, up in mentions if start < token.start}
            candidates = before or context.standing
            if not candidates or not all(candidates.values()):
                continue
            claim = find_phrases(_clause(sentence, token.end), lex.defeat_claims)
            hedged = find_phrases(sentence, lex.death_hedges | lex.attack_hedges)
            if claim and not hedged:
                names = ", ".join(sorted(candidates))
                detail = f"'{token.text}' means {names}, still standing; no engine event beat them"
                found.append(Violation(ViolationKind.UNHURT_DECLARED_DOWN, token.text, detail))
    if mentions:
        context.standing = {name: up for _, name, up in mentions}
    return found


def dead_alive(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    lex = scene.lexicon
    if not scene.dead or not find_phrases(sentence, lex.alive_claims):
        return []
    for name in sorted(scene.dead, key=len, reverse=True):
        for m in re.finditer(rf"(?<![A-Za-z]){re.escape(name)}(?![A-Za-z])", sentence, re.I):
            window = sentence[m.end() : m.end() + _ALIVE_REACH]
            claim = find_phrases(window, lex.alive_claims)
            index = _index_at(tokens, m.end() + claim[0].start()) if claim else None
            if index is not None and not is_negated(tokens, index, lex.negations, span=2):
                detail = f"{name} is dead: never tell them living on or acting"
                return [Violation(ViolationKind.DEAD_ACTING, name, detail)]
    return []
