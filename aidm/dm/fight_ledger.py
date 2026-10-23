"""Who did what to whom in this turn's fight events (M29.7b, docs/playtests/M29_round2.md R19).

Round 2 showed fight prose inventing blows per creature: a foe's charge and claw hit when no foe
acted, shafts that "find their mark" in heroes nobody shot, a kill credited to the wrong hero, a
bolt that "skips off" when the engine said hit. `fight_ledger(state, events)` freezes, from the
events already applied to `state`:
- `acted`: creature ids that made a blow (an attack, a spell, a monster action, damage dealt);
- `struck`: ids that lost hit points; `hit_by` / `missed_by`: attackers with a hit (or damage
  dealt) / with a missed attack; `downed`: ids that fell to 0 HP or died; `killers`: the sources of
  the damage that dropped them;
- `terms`: every word the prose may use for a creature in this fight (names, their distinctive
  words, the monster kind; generic foe words such as "creature" mean every foe), longest first;
- `foes`: the ids of the non-hero creatures in the fight.
`FightLedger()` (empty `terms`) switches the per-creature checks off.

Public API: `FightLedger`, `fight_ledger(state, events) -> FightLedger`,
`fight_lines(state, ledger, events) -> list[str]`.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from aidm.data.guard_lexicon import GuardLexicon, guard_lexicon
from aidm.dm.guard_text import plain
from aidm.dm.wording import attack_label
from aidm.models import events as ev
from aidm.models.combat_events import AttackRolled, MonsterActionUsed, SpellCast
from aidm.models.state import Creature, GameState

GENERIC_FOE_WORDS = ("creature", "beast", "brute", "monster", "thing", "figure")
_MIN_WORD = 4


@dataclass(frozen=True)
class FightLedger:
    acted: frozenset[str] = frozenset()
    struck: frozenset[str] = frozenset()
    hit_by: frozenset[str] = frozenset()
    missed_by: frozenset[str] = frozenset()
    downed: frozenset[str] = frozenset()
    killers: frozenset[str] = frozenset()
    killed_by: tuple[tuple[str, str], ...] = ()  # (fallen id, source id of the killing damage)
    terms: tuple[tuple[str, frozenset[str]], ...] = ()
    foes: frozenset[str] = frozenset()
    names: dict[str, str] = field(default_factory=dict[str, str])

    @property
    def active(self) -> bool:
        return bool(self.terms)


def _fighters(state: GameState, events: Sequence[ev.AnyEvent]) -> list[Creature]:
    ids = {c.id for c in state.creatures.values() if c.pc is not None}
    if state.encounter is not None:
        ids |= {c.creature_id for c in state.encounter.combatants.values()}
    for e in events:
        for key in ("creature_id", "attacker_id", "target_id", "caster_id", "source_id"):
            value = getattr(e, key, None)
            if isinstance(value, str):
                ids.add(value)
    return [state.creatures[i] for i in sorted(ids) if i in state.creatures]


def _words(creature: Creature, lex: GuardLexicon) -> set[str]:
    name = plain(creature.name).casefold()
    words = {name}
    skip = lex.titles | lex.sentence_starters
    words |= {w for w in re.findall(r"[a-z]+", name) if len(w) >= _MIN_WORD and w not in skip}
    if creature.pc is None and creature.monster_index:
        kind = creature.monster_index.replace("-", " ")
        words |= {kind} | {w for w in kind.split() if len(w) >= _MIN_WORD and w not in skip}
    return words


def _terms(fighters: list[Creature], lex: GuardLexicon) -> tuple[tuple[str, frozenset[str]], ...]:
    found: dict[str, set[str]] = {}
    for creature in fighters:
        for word in _words(creature, lex):
            found.setdefault(word, set()).add(creature.id)
    foes = {c.id for c in fighters if c.pc is None}
    if foes:
        for word in GENERIC_FOE_WORDS:
            found.setdefault(word, set()).update(foes)
    ordered = sorted(found.items(), key=lambda p: (-len(p[0]), p[0]))
    return tuple((term, frozenset(ids)) for term, ids in ordered)


def _blows(events: Sequence[ev.AnyEvent]) -> tuple[set[str], set[str], set[str]]:
    acted: set[str] = set()
    hit: set[str] = set()
    missed: set[str] = set()
    for e in events:
        if isinstance(e, AttackRolled):
            acted.add(e.attacker_id)
            (hit if e.hit else missed).add(e.attacker_id)
        elif isinstance(e, SpellCast):
            acted.add(e.caster_id)
        elif isinstance(e, MonsterActionUsed):
            acted.add(e.creature_id)
        elif isinstance(e, ev.DamageTaken) and e.source_id is not None and e.hp_lost > 0:
            acted.add(e.source_id)
            hit.add(e.source_id)
    return acted, hit, missed


def _falls(events: Sequence[ev.AnyEvent]) -> tuple[set[str], set[str], dict[str, str]]:
    struck: set[str] = set()
    downed: set[str] = set()
    killers: dict[str, str] = {}
    source: dict[str, str] = {}
    for e in events:
        if isinstance(e, ev.DamageTaken) and e.hp_lost > 0:
            struck.add(e.creature_id)
            if e.source_id is not None:
                source[e.creature_id] = e.source_id
        elif isinstance(e, ev.HpChanged) and e.delta < 0:
            struck.add(e.creature_id)
            if e.new_hp == 0:
                downed.add(e.creature_id)
                if e.creature_id in source:
                    killers[e.creature_id] = source[e.creature_id]
        elif isinstance(e, ev.CreatureDied):
            downed.add(e.creature_id)
    return struck, downed, killers


def fight_ledger(state: GameState, events: Sequence[ev.AnyEvent]) -> FightLedger:
    lex = guard_lexicon()
    fighters = _fighters(state, events)
    if not any(c.pc is None for c in fighters):
        return FightLedger()
    acted, hit, missed = _blows(events)
    struck, downed, killers = _falls(events)
    return FightLedger(
        acted=frozenset(acted),
        struck=frozenset(struck),
        hit_by=frozenset(hit),
        missed_by=frozenset(missed),
        downed=frozenset(downed),
        killers=frozenset(killers.values()),
        killed_by=tuple(sorted(killers.items())),
        terms=_terms(fighters, lex),
        foes=frozenset(c.id for c in fighters if c.pc is None),
        names={c.id: c.name for c in fighters},
    )


def _name(state: GameState, cid: str) -> str:
    creature = state.creatures.get(cid)
    return creature.name if creature is not None else cid


def fight_lines(state: GameState, ledger: FightLedger, events: Sequence[ev.AnyEvent]) -> list[str]:
    """One short line per blow, for the narrator's facts: who, with what, at whom, the outcome."""
    out: list[str] = []
    for e in events:
        if isinstance(e, AttackRolled):
            outcome = "hit" if e.hit else "missed"
            line = f"{_name(state, e.attacker_id)}: {attack_label(e.attack)} at"
            out.append(f"{line} {_name(state, e.target_id)}, {outcome}")
        elif isinstance(e, SpellCast):
            targets = ", ".join(_name(state, t) for t in e.target_ids) or "an area"
            out.append(f"{_name(state, e.caster_id)}: {e.spell_id.replace('-', ' ')} at {targets}")
    killers = dict(ledger.killed_by)
    for cid in sorted(ledger.downed):
        by = killers.get(cid)
        tail = f" (the killing blow was {_name(state, by)}'s)" if by is not None else ""
        out.append(f"{_name(state, cid)} fell{tail}")
    return out
