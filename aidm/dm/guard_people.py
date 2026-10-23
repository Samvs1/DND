"""People facts the prose guard freezes once per narration (M29.7b, `aidm.dm.guard_party`).

`people_facts(state, present_npcs, present_roles, lex)` returns the `GuardScene` fields:
- `party_counts`: the numbers the party may be counted as (living heroes, all heroes);
- `hurt`: hero term -> name for every living hero below full hit points;
- `races_here`: race words of the heroes (race, subrace and their parts), of the people present
  and of the creatures here (`present_roles`);
- `present_words`: distinctive word of a present NPC's name -> the name ("wren" -> "Wren
  Averntide");
- `known_ids`: every hyphenated engine id of the manifest (creatures, NPCs, places, features,
  items, quests), lowercase.

Public API: `PeopleFacts`, `people_facts(state, present_npcs, present_roles, lex) -> PeopleFacts`.
"""

import re
from collections.abc import Iterable
from typing import TypedDict

from aidm.data.guard_lexicon import GuardLexicon
from aidm.dm.guard_turn import hero_terms
from aidm.models.state import GameState

_MIN_WORD = 4


class PeopleFacts(TypedDict):
    party_counts: frozenset[int]
    hurt: dict[str, str]
    races_here: frozenset[str]
    present_words: dict[str, str]
    known_ids: frozenset[str]


def _races(state: GameState, present_roles: Iterable[str]) -> frozenset[str]:
    words: set[str] = set(present_roles)
    for creature in state.creatures.values():
        if creature.pc is None:
            continue
        for race in (creature.pc.race, creature.pc.subrace):
            if race:
                low = race.casefold()
                words |= {low, *low.split("-")}
    return frozenset(words)


def _present_words(present_npcs: Iterable[str], lex: GuardLexicon) -> dict[str, str]:
    skip = lex.titles | lex.sentence_starters
    out: dict[str, str] = {}
    for name in sorted(present_npcs):
        for word in re.findall(r"[A-Za-z]+", name):
            if len(word) >= _MIN_WORD and word.casefold() not in skip:
                out.setdefault(word, name)
    return out


def _known_ids(state: GameState) -> frozenset[str]:
    world = state.world
    ids: set[str] = set(state.creatures) | set(world.npcs) | set(world.node_names)
    ids |= set(world.features) | set(world.items) | set(world.quests)
    return frozenset(i.casefold() for i in ids if "-" in i)


def people_facts(
    state: GameState, present_npcs: Iterable[str], present_roles: Iterable[str], lex: GuardLexicon
) -> PeopleFacts:
    heroes = [c for c in state.creatures.values() if c.pc is not None]
    living = [c for c in heroes if not c.dead]
    hurt = [c.name for c in living if c.hp < c.max_hp]
    return PeopleFacts(
        party_counts=frozenset({len(living), len(heroes)} - {0}),
        hurt=hero_terms(hurt, lex),
        races_here=_races(state, present_roles),
        present_words=_present_words(present_npcs, lex),
        known_ids=_known_ids(state),
    )
