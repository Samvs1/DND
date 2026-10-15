"""What the prose guard knows about the scene, computed once per narration (SPEC 6.5).

`guard_scene(state, events)` freezes the facts every check needs: the known name words (the entity
registry, `aidm.dm.entities`), who is present, who is dead, which absent NPCs exist, the party's
names and classes, the nouns of items the party may not see destroyed, and the words of the features
and description of the current place, and the keys of every unrevealed NPC secret
(`aidm.dm.guard_secrets`), the names of the living (`aidm.dm.guard_alive`) and whether the events
granted a reward (`aidm.dm.guard_rewards`). Recent `events` (already applied to `state`) mark items
that really were lost (`InventoryChanged` with a negative delta, a removed world item is no longer
in the scene), so describing those as gone is allowed.

Public API: `GuardScene`, `guard_scene(state, events=()) -> GuardScene`, `words_of(text)`.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from aidm.data.guard_lexicon import GuardLexicon, guard_lexicon
from aidm.dm.entities import display_name, entity_registry
from aidm.dm.guard_alive import downed_terms, living_terms, standing_terms
from aidm.dm.guard_rewards import rewarded
from aidm.dm.guard_secrets import SecretKey, secret_keys
from aidm.dm.guard_text import plain
from aidm.models import events as ev
from aidm.models.encounter import EncounterStatus
from aidm.models.state import GameState
from aidm.rules.scene import SceneView, current_scene, node_display_name

_WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)*")


def words_of(text: str) -> set[str]:
    """Lowercase words; an apostrophe name counts whole and by its parts ("el'skalfidar", "el",
    "skalfidar"), whatever apostrophe it was written with."""
    out: set[str] = set()
    for word in _WORD.findall(plain(text)):
        low = word.casefold()
        out.add(low)
        out.update(part for part in low.split("'") if part)
    return out


def _plain_keys(terms: dict[str, str]) -> dict[str, str]:
    return {plain(term): name for term, name in terms.items()}


@dataclass(frozen=True)
class GuardScene:
    lexicon: GuardLexicon
    known_words: frozenset[str]
    party: dict[str, str]
    party_classes: frozenset[str]
    present_npcs: frozenset[str]
    absent_npcs: dict[str, str]
    absent_roles: frozenset[str]
    present_roles: frozenset[str]
    dead: frozenset[str]
    others_present: int
    item_nouns: dict[str, str]
    feature_words: frozenset[str]
    secrets: tuple[SecretKey, ...] = ()
    living_terms: dict[str, str] = field(default_factory=dict[str, str])
    standing_terms: dict[str, str] = field(default_factory=dict[str, str])
    downed_terms: dict[str, str] = field(default_factory=dict[str, str])
    offer_pending: bool = False
    voice_next: str = ""
    rewarded: bool = False
    other_places: dict[str, str] = field(default_factory=dict[str, str])


def _lost_items(events: Sequence[ev.AnyEvent]) -> set[str]:
    return {
        display_name(e.item) for e in events if isinstance(e, ev.InventoryChanged) and e.delta < 0
    }


def _item_nouns(names: Iterable[str], lex: GuardLexicon) -> dict[str, str]:
    nouns: dict[str, str] = {}
    for name in sorted(names):
        for word in sorted(words_of(name)):
            if len(word) < 3 or word in lex.item_stop_words:
                continue
            nouns.setdefault(word, name)
            for synonym in lex.item_synonyms.get(word, ()):
                nouns.setdefault(synonym, name)
    return nouns


def _carried(state: GameState) -> set[str]:
    names: set[str] = set()
    for creature in state.creatures.values():
        if creature.pc is not None:
            names.update(display_name(i.item) for i in creature.pc.inventory)
            names.update(k.name for k in creature.pc.keepsakes)
    for npc in state.world.npcs.values():  # M23.3: things handed over still exist
        names.update(k.name for k in npc.keepsakes)
    return names


def _feature_words(state: GameState, scene: SceneView) -> frozenset[str]:
    words = words_of(scene.description) | words_of(scene.node_name)
    for fid in scene.feature_ids:
        feature = state.world.features[fid]
        words |= words_of(f"{feature.name} {feature.kind.value} {feature.description}")
    for exit_id in scene.exits:
        words |= words_of(node_display_name(state, exit_id))
    return frozenset(words)


def _role_words(state: GameState, ids: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for npc_id in ids:
        npc = state.world.npcs[npc_id]
        out |= words_of(f"{npc.role} {npc.archetype_id}")
    return {w for w in out if len(w) >= 4}


def _all_role_words(state: GameState) -> set[str]:
    return set().union(*(words_of(n.role) for n in state.world.npcs.values()))


def _absent_terms(absent: set[str], here: set[str], lex: GuardLexicon) -> dict[str, str]:
    """Each absent NPC by full name and by every distinctive word of it ("Voss")."""
    taken = set().union(*(words_of(n) for n in here)) if here else set[str]()
    terms: dict[str, str] = {}
    for name in sorted(absent):
        terms[name] = name
        for word in re.findall(r"[A-Za-z]+", name):
            low = word.casefold()
            skip = low in lex.titles or low in lex.sentence_starters or low in taken
            if len(word) >= 3 and not skip:
                terms.setdefault(word, name)
    return terms


def guard_scene(state: GameState, events: Sequence[ev.AnyEvent] = ()) -> GuardScene:
    lex = guard_lexicon()
    reg = entity_registry(state)
    scene = current_scene(state)
    present_ids = set(scene.npc_ids)
    living = {plain(c.name) for c in state.creatures.values() if not c.dead}
    present_npcs = {plain(state.world.npcs[i].name) for i in present_ids}
    absent_ids = [i for i, n in state.world.npcs.items() if i not in present_ids and not n.dead]
    absent = {plain(state.world.npcs[i].name) for i in absent_ids} - present_npcs - living
    monsters = {state.creatures[c].name for c in scene.monster_ids}
    present_roles = _role_words(state, present_ids) | words_of(" ".join(monsters))
    known = set().union(*(words_of(n) for n in reg.all_names - reg.hidden_features))
    party = {plain(c.name): c.pc.class_index for c in state.creatures.values() if c.pc is not None}
    slain = {n.name for n in state.world.npcs.values() if n.dead}  # M20.5
    dead = frozenset(plain(n) for n in reg.dead | slain) - living
    carried = (_carried(state) | {state.world.items[i].name for i in scene.item_ids}) - _lost_items(
        events
    )
    return GuardScene(
        lexicon=lex,
        known_words=frozenset(known),
        party=party,
        party_classes=frozenset(party.values()),
        present_npcs=frozenset(present_npcs),
        absent_npcs=_absent_terms(absent, present_npcs | living | set(party), lex),
        absent_roles=frozenset(
            _role_words(state, absent_ids) - present_roles - lex.titles - lex.sentence_starters
        ),
        present_roles=frozenset(present_roles),
        dead=dead,
        others_present=len(present_ids) + len(scene.monster_ids),
        item_nouns=_item_nouns(carried, lex),
        feature_words=_feature_words(state, scene),
        secrets=secret_keys(
            state, frozenset(known | _all_role_words(state)), lex.secret_stop_words
        ),
        living_terms=(terms := _plain_keys(living_terms(state, dead, lex))),
        standing_terms=standing_terms(state, terms),
        downed_terms=_plain_keys(downed_terms(state, dead, lex)),
        offer_pending=_offer_pending(state),
        rewarded=rewarded(events),
        other_places=_other_places(state),
    )


def _offer_pending(state: GameState) -> bool:
    """An encounter offer waits for the party's answer and no fight runs (M20.6)."""
    enc = state.encounter
    fighting = enc is not None and enc.status is EncounterStatus.ACTIVE
    return state.campaign is not None and state.campaign.offer is not None and not fighting


def _other_places(state: GameState) -> dict[str, str]:
    """Lowercase display name -> name of every map node the party is NOT at (QA-10)."""
    here = plain(state.world.node_names.get(state.world.current_node or "", "")).casefold()
    return {
        plain(name).casefold(): name
        for node, name in state.world.node_names.items()
        if node != state.world.current_node and name.casefold() != here and len(name) >= 4
    }
