"""Typed healing out of a fight (M29.5b G2 / G17 / G33: "I drink my potion", "I pour my potion
into Rook", "Elowen casts cure wounds on Tamsin" were told by the storyteller as heals the engine
never made). A deterministic precheck, like `aidm.dm.give_intent`; the rules decide.

`heal_intent(state, actor_id, clean)` reads the precheck's normalised sentence:
- a spell: the sentence says cast / casts / casting and names a healing spell (a spell whose data
  has a `heal` effect, matched by the words of its id); the actor is the caster (a player plays
  only their own hero), the targets are the heroes the sentence names other than the actor (the
  last one named for a one-target spell; every hero for a many-target spell when none is named),
  else the actor;
- a healing consumable (data/bg3/consumables.json with `heal`): a drink verb ("drink", "quaff",
  "use", "apply" ...) heals the actor or the hero the sentence names; a giving verb ("pour",
  "feed", "bind" ...) needs a named hero (M29.7a R7: "hand" / "give" with no drink word is a
  hand-over, `aidm.dm.hand_intent`, read before this). The draught is the actor's, else the named
  hero's own ("pours his potion between Rook's lips"). The best word match wins ("my potion").
Anything else is None and goes on as before (the adjudicator).

Public API: `HealIntent(actor_id, target_ids, item, owner_id, spell)`,
`heal_intent(state, actor_id, clean) -> HealIntent | None`.
"""

import re
from dataclasses import dataclass

from aidm.data.combat_data import combat_registries
from aidm.data.spell_defs import HealEffect
from aidm.models.state import Creature, CreatureKind, GameState

_CAST = frozenset({"cast", "casts", "casting"})
_SELF_VERBS = frozenset(
    {"drink", "drinks", "quaff", "quaffs", "sip", "sips", "swallow", "swallows", "gulp", "use"}
    | {"uses", "apply", "applies", "down", "downs"}
)
_GIVE_VERBS = frozenset(
    {"pour", "pours", "feed", "feeds", "tip", "tips", "bind", "binds"}
    | {"press", "presses", "administer", "administers", "rub", "rubs"}
)
_SMALL = frozenset({"of", "the", "a", "an", "my", "his", "her"})


@dataclass(frozen=True)
class HealIntent:
    actor_id: str
    target_ids: tuple[str, ...]
    item: str | None = None
    owner_id: str | None = None  # who carries the item
    spell: str | None = None


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower().replace("-", " "))


def _named_heroes(state: GameState, actor_id: str, text: str) -> list[str]:
    """The heroes (not the actor; the dead too, so the rules can refuse) the sentence names, in
    the order they appear last."""
    found: list[tuple[int, str]] = []
    for c in state.creatures.values():
        if c.kind is not CreatureKind.PC or c.id == actor_id:
            continue
        first = _words(c.name)[:1]
        hits = (
            [m.start() for m in re.finditer(rf"\b{re.escape(first[0])}\b", text)] if first else []
        )
        if hits:
            found.append((hits[-1], c.id))
    return [cid for _, cid in sorted(found)]


def _spell(words: set[str]) -> str | None:
    heals = [
        s.index
        for s in combat_registries().spells.all()
        if any(isinstance(e, HealEffect) for e in s.effects) and set(_words(s.index)) <= words
    ]
    return max(heals, key=lambda i: len(_words(i)), default=None)


def _spell_intent(state: GameState, actor_id: str, clean: str, words: set[str]) -> HealIntent:
    spell = _spell(words)
    named = _named_heroes(state, actor_id, clean)
    one = spell is not None and combat_registries().spells.get(spell).targeting.kind == "creature"
    if not named:
        party = [c.id for c in state.creatures.values() if c.kind is CreatureKind.PC and not c.dead]
        targets = (actor_id,) if one else tuple(party)
    else:
        targets = (named[-1],) if one else tuple(named)
    return HealIntent(actor_id, targets, spell=spell)


def _heal_items(hero: Creature, words: set[str]) -> tuple[int, str] | None:
    if hero.pc is None:
        return None
    regs = combat_registries().consumables
    scored: list[tuple[int, str]] = []
    for row in hero.pc.inventory:
        item = regs.find(row.item)
        if item is None or not item.heal or row.qty < 1:
            continue
        name = set(_words(item.name)) - _SMALL
        if name & words:
            scored.append((len(name & words), row.item))
    return max(scored, default=None)


def _item_intent(
    state: GameState, actor: Creature, clean: str, words: set[str]
) -> HealIntent | None:
    named = _named_heroes(state, actor.id, clean)
    if not words & _SELF_VERBS and not (words & _GIVE_VERBS and named):
        return None
    target = state.creatures[named[-1]] if named else actor
    for owner in (actor, target):
        best = _heal_items(owner, words)
        if best is not None:
            return HealIntent(actor.id, (target.id,), item=best[1], owner_id=owner.id)
    return None


def heal_intent(state: GameState, actor_id: str, clean: str) -> HealIntent | None:
    actor = state.creatures.get(actor_id)
    if actor is None or actor.pc is None:
        return None
    words = set(_words(clean))
    if words & _CAST:
        intent = _spell_intent(state, actor_id, clean, words)
        return intent if intent.spell is not None else None
    return _item_intent(state, actor, clean, words)
