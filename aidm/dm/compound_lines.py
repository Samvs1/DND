"""The acts of a compound typed line (M32.1a X6, round 5: "I sheathe my sword and sling my shield"
did only the shield, "I charge the zombie and cleave it with my longsword" only the move, "I pick
up the salt and hand it to Gran Tevin" only the pick-up).

`clause_parts(state, actor_id, text)` cuts the hero's own reading of the line
(`dm.sentence.own_reading`) into at most three acts at the clause cuts of `split_clause`
(", then", " and" ...). A later part counts as an act only when it starts with a verb the
table knows (a verb of any phrase row, or of the lexicon's `act_verbs`, `talk_words`,
`strike_verbs`, `lead_in_verbs`), never another hero's name: "search the plots and ditches"
and "cast fire bolt at the goblin and the orc" are one act, and the hero never acts for a
friend. A later part's first verb reads plain ("gives" -> "give"), and an "it" right after
that verb stands for the earlier part's object when that part starts with a verb ("pick up the
salt and hand it to Gran Tevin" -> "hand the salt to gran tevin"; "attack the thug before it
moves" keeps its "it").
`is_lead_in(part)`: a part that only sets the scene (a first word of `lead_in_verbs`: "step
forward", "kneel", "hold out the ring") is never ruled on by itself; the callers tell it with
the turn's other words (M33.1). A movement that may deserve a check (climb, jump, leap, vault,
dash, charge, rush, scramble, slip) is in `act_verbs`, never a lead-in.

The callers (`session.intent_turn`, `session.fight_text`) route every part through the one
router and run each in order; this module decides nothing about intents.

Public API: `clause_parts(state, actor_id, text) -> list[str]` (empty: one act),
`is_lead_in(part) -> bool`.
"""

import re
from functools import cache

from aidm.data.intent_phrases import intent_phrases
from aidm.dm.sentence import normalise, own_reading, plain_verb, split_clause
from aidm.models.state import CreatureKind, GameState

_MAX_PARTS = 3
_PARTICLES = frozenset(
    {"up", "out", "down", "over", "forth", "back", "off", "away", "aside", "forward", "forwards"}
    | {"ahead", "closer", "around", "in", "near"}
)
_PREPOSITIONS = frozenset(
    {"on", "in", "at", "from", "to", "with", "into", "onto", "off", "under", "by", "near"}
    | {"beside", "toward", "towards", "across", "through", "for", "before", "as", "and"}
)
_IT = re.compile(r"^(?:(?:up|out|over|back|down) )?it\b")
_LEXICONS = ("act_verbs", "talk_words", "strike_verbs", "lead_in_verbs")


def _first(text: str) -> str:
    return text.split(" ", 1)[0] if text else ""


@cache
def _verbs() -> frozenset[str]:
    """Every verb the table knows: the first word of each row's verbs, and the verb lexicons."""
    table = intent_phrases()
    words: set[str] = set()
    for name in _LEXICONS:
        words |= table.lexicon[name]
    for row in table.rows:
        for verb in (*row.verbs, *(v for p in row.patterns for v in p.verbs)):
            head = re.match(r"[a-z]+", verb)
            if head is not None:
                words.add(head.group())
    return frozenset(words)


def _is_verb(word: str) -> bool:
    clean = word.strip(",.:;!?")
    return clean in _verbs() or plain_verb(clean) in _verbs()


def _starts_act(state: GameState, actor_id: str, part: str) -> bool:
    first = _first(part)
    friends = {
        c.name.lower().split()[0]
        for c in state.creatures.values()
        if c.kind is CreatureKind.PC and c.id != actor_id and c.name
    }
    return _is_verb(first) and first not in friends


def _plain(part: str) -> str:
    verb, _, rest = part.partition(" ")
    return f"{plain_verb(verb.strip(',.:;!?'))} {rest}".strip()


def _object(part: str) -> str:
    """What the act is done to: the words after its verb (and a particle), up to a
    preposition ("pick up the salt on the ground" -> "the salt")."""
    words = part.split()[1:]
    if words and words[0] in _PARTICLES:
        words = words[1:]
    cut = next((i for i, w in enumerate(words) if w in _PREPOSITIONS), len(words))
    words = words[:cut]
    while words and words[-1] in _PARTICLES:  # "hand the shard over" -> "the shard"
        words = words[:-1]
    return " ".join(words)


def _with_antecedent(part: str, before: str) -> str:
    thing = _object(before) if _is_verb(_first(before)) else ""
    if not thing:
        return part
    head, _, rest = part.partition(" ")
    return f"{head} {_IT.sub(lambda m: m.group().removesuffix('it') + thing, rest)}".strip()


def clause_parts(state: GameState, actor_id: str, text: str) -> list[str]:
    actor = state.creatures.get(actor_id)
    rest = own_reading(actor.name if actor is not None else "", normalise(text))
    parts: list[str] = []
    while len(parts) < _MAX_PARTS - 1:
        cut = split_clause(rest)
        if cut is None or not _starts_act(state, actor_id, cut[1]):
            break
        parts.append(cut[0])
        rest = _with_antecedent(_plain(cut[1]), cut[0])
    return [*parts, rest] if parts else []


def is_lead_in(part: str) -> bool:
    return _first(part) in intent_phrases().lexicon["lead_in_verbs"]
