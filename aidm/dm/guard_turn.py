"""What this turn's engine events resolved, frozen for the prose guard (M29.5c, honest storyteller).

The narrator may tell only what the engine did (M29 round 1: a purchase no shop performed, a
potion the hero never had "shattering", a foe "lying still" at 8 of 32 HP, a crossbow told as a
mace). `turn_truth(state, events, actor_id=..., player_text=...)` freezes, from the events
already applied to `state`:
- `in_fight` / `blows`: a fight runs (or started) and whether any blow was resolved (an attack,
  damage, a spell or a monster action);
- `weapons`: attacker term -> the words of what it attacked with (the attack's name, the
  lexicon's `item_synonyms` and `attack_words`: a light crossbow shoots bolts), weapon attacks only;
- `paid` (a gold change or a trade), `handed` (a keepsake given, an item lost, traded or placed),
  `lit` (a light lit);
- `claimed`: the things the player's own words used as the hero's that the hero does not carry
  (`claimed_things`: "I drink my potion of giant strength" with no potion -> "potion"; "pulls
  fifty feet of silk rope" with only hempen rope -> "silk rope");
- `unhurt`: hero term -> name for every hero at full HP whom no event touched;
- M29.7b: `fight` (`aidm.dm.fight_ledger`: who acted, was struck, missed, fell, killed), `burning`
  (light noun -> bearer, `aidm.dm.turn_world`), `ended` (a light went out), `short_of` (the travel
  destination not reached this turn), `picked` (a thing came into a hero's hands).
`TurnTruth()` (`checked` False) switches these checks off, for prose about the past (epilogue).

Public API: `TurnTruth`, `Claim`, `claimed_things(state, actor_id, text)`, `hero_terms(names)`,
`turn_truth(state, events, *, actor_id, player_text) -> TurnTruth`.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from aidm.data.guard_lexicon import GuardLexicon, guard_lexicon
from aidm.dm.entities import display_name
from aidm.dm.fight_ledger import FightLedger, fight_ledger
from aidm.dm.guard_text import find_phrases, plain
from aidm.dm.turn_world import burning, picked_up, short_of
from aidm.models import events as ev
from aidm.models import world_events as we
from aidm.models.combat_events import AttackRolled, MonsterActionUsed, SpellCast
from aidm.models.encounter import EncounterStatus
from aidm.models.encounter_events import EncounterStarted
from aidm.models.item_events import HandedOver, ItemUsed, LightEnded, LightLit
from aidm.models.quest_events import KeepsakeGiven
from aidm.models.state import Creature, GameState

_WORD = re.compile(r"[a-z]+(?:-[a-z]+)*")
_MIN_TERM = 4
_VERB_REACH = 5  # words between a use verb and the thing ("pulls fifty feet of silk rope")
_MAX_MODIFIERS = 2


@dataclass(frozen=True)
class Claim:
    hero: str  # the hero's name
    phrase: str  # the thing as the player wrote it ("potion of giant strength")
    term: str  # what the guard looks for in prose ("potion", or "silk rope")


@dataclass(frozen=True)
class TurnTruth:
    checked: bool = False
    in_fight: bool = False
    blows: bool = True
    weapons: dict[str, frozenset[str]] = field(default_factory=dict[str, frozenset[str]])
    paid: bool = True
    handed: bool = True
    lit: bool = True
    claimed: tuple[Claim, ...] = ()
    unhurt: dict[str, str] = field(default_factory=dict[str, str])
    fight: FightLedger = field(default_factory=FightLedger)
    burning: dict[str, str] = field(default_factory=dict[str, str])
    ended: bool = True
    short_of: str = ""
    picked: bool = True


def hero_terms(names: Iterable[str], lex: GuardLexicon | None = None) -> dict[str, str]:
    """Each name and every distinctive word of it (>= 4 letters, no title) -> the name."""
    words = lex or guard_lexicon()
    terms: dict[str, str] = {}
    for name in sorted(names):
        terms[plain(name).casefold()] = name
        for word in re.findall(r"[A-Za-z]+", plain(name)):
            low = word.casefold()
            if len(low) >= _MIN_TERM and low not in words.titles | words.sentence_starters:
                terms.setdefault(low, name)
    return terms


def _carried_names(creature: Creature) -> list[str]:
    if creature.pc is None:
        return []
    names = [display_name(i.item) for i in creature.pc.inventory]
    return names + [k.name for k in creature.pc.keepsakes]


def _name_words(name: str, lex: GuardLexicon) -> set[str]:
    words = set(_WORD.findall(plain(name).casefold().replace(",", " ")))
    for word in list(words):
        words.update(lex.item_synonyms.get(word, ()))
        words.add(word.removesuffix("s"))
    return words


def _modifiers(before: list[str], lex: GuardLexicon) -> list[str]:
    """The words right before the noun, back to the first stop word ("of silk" -> silk)."""
    out: list[str] = []
    for word in reversed(before[-_MAX_MODIFIERS:]):
        if word in lex.gear_modifier_stops or word in lex.use_verbs:
            break
        out.insert(0, word)
    return out


def _framed_as_own(before: list[str], lex: GuardLexicon) -> bool:
    """The player used the thing as the hero's: "my potion", or a use verb right before."""
    if before and before[-1] in {"my", "his", "her", "their", "our"}:
        return True
    window = " ".join(before[-_VERB_REACH - 1 :])
    return bool(find_phrases(window, lex.use_verbs))


def _claim(hero: Creature, text: str, start: int, noun: str, lex: GuardLexicon) -> Claim | None:
    before = _WORD.findall(text[:start])
    if not _framed_as_own(before, lex):
        return None
    mods = _modifiers(before, lex)
    tail = re.match(r"\s+of\s+((?:[a-z-]+\s*){1,3})", text[start + len(noun) :])
    phrase = " ".join([*mods, noun, *(["of", tail.group(1).strip()] if tail else [])])
    owned = [_name_words(n, lex) for n in _carried_names(hero)]
    with_noun = [w for w in owned if noun in w or noun.removesuffix("s") in w]
    if not with_noun:
        return Claim(hero.name, phrase, noun)
    if mods and not any(set(mods) <= w for w in with_noun):
        return Claim(hero.name, phrase, " ".join([*mods, noun]))
    return None


def claimed_things(state: GameState, actor_id: str | None, text: str | None) -> list[Claim]:
    """Things the player's words use as the hero's own that the hero does not carry."""
    hero = state.creatures.get(actor_id or "")
    if hero is None or hero.pc is None or not text:
        return []
    lex = guard_lexicon()
    low = plain(text).casefold()
    found: list[Claim] = []
    for m in find_phrases(low, lex.gear_nouns):
        claim = _claim(hero, low, m.start(), m.group(0).casefold(), lex)
        if claim is not None and claim.term not in {c.term for c in found}:
            found.append(claim)
    return found


_BLOWS = (AttackRolled, ev.DamageTaken, SpellCast, MonsterActionUsed)
_HANDED = (KeepsakeGiven, we.ItemsTraded, we.ItemPlaced, HandedOver)


def _weapons(state: GameState, events: Sequence[ev.AnyEvent], lex: GuardLexicon) -> dict:
    out: dict[str, frozenset[str]] = {}
    weaponish = lex.weapon_nouns | frozenset(lex.attack_words)
    for e in events:
        attacker = state.creatures.get(e.attacker_id) if isinstance(e, AttackRolled) else None
        if attacker is None or not isinstance(e, AttackRolled):
            continue
        words = _name_words(e.attack, lex)
        if not words & weaponish:
            continue  # a spell attack: the guard does not judge a caster's focus
        for word in list(words):
            words.update(lex.attack_words.get(word, ()))
        for term in hero_terms([attacker.name], lex):
            out[term] = out.get(term, frozenset()) | frozenset(words)
    return out


def _unspent(
    claims: list[Claim], events: Sequence[ev.AnyEvent], lex: GuardLexicon
) -> tuple[Claim, ...]:
    """Claims minus the things these events used up (M29.7b: the last potion was drunk)."""
    spent: set[str] = set()
    for e in events:
        if isinstance(e, ItemUsed) or (isinstance(e, ev.InventoryChanged) and e.delta < 0):
            spent |= _name_words(display_name(e.item), lex)
    return tuple(c for c in claims if not set(c.term.split()) <= spent)


def _touched(events: Sequence[ev.AnyEvent]) -> set[str]:
    return {e.creature_id for e in events if isinstance(e, ev.HpChanged | ev.DamageTaken)}


def _fighting(state: GameState, events: Sequence[ev.AnyEvent]) -> bool:
    enc = state.encounter
    active = enc is not None and enc.status is EncounterStatus.ACTIVE
    return active or any(isinstance(e, EncounterStarted) for e in events)


def turn_truth(
    state: GameState,
    events: Sequence[ev.AnyEvent],
    *,
    actor_id: str | None = None,
    player_text: str | None = None,
) -> TurnTruth:
    lex = guard_lexicon()
    touched = _touched(events)
    unhurt = [
        c.name
        for c in state.creatures.values()
        if c.pc is not None and not c.dead and c.hp >= c.max_hp and c.id not in touched
    ]
    return TurnTruth(
        checked=True,
        in_fight=_fighting(state, events),
        blows=any(isinstance(e, _BLOWS) for e in events),
        weapons=_weapons(state, events, lex),
        paid=any(isinstance(e, ev.GoldChanged | we.ItemsTraded) for e in events),
        handed=any(
            isinstance(e, _HANDED) or (isinstance(e, ev.InventoryChanged) and e.delta < 0)
            for e in events
        ),
        lit=any(isinstance(e, LightLit) for e in events),
        claimed=_unspent(claimed_things(state, actor_id, player_text), events, lex),
        unhurt=hero_terms(unhurt, lex),
        fight=fight_ledger(state, events),
        burning=burning(state),
        ended=any(isinstance(e, LightEnded) for e in events),
        short_of=short_of(state, events, player_text),
        picked=picked_up(events),
    )
