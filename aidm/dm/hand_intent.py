"""Typed handing-over between heroes (M29.7a R7 / R8: "Brienne hands the Herbal Poultice to Elowen
and tells her to keep it" spent the poultice on Elowen; "gives the spare crowbar to Elowen" and
passing coin were prose only). A deterministic precheck like `aidm.dm.give_intent`.

The `hand` phrase row (data/bg3/intent_phrases.json) reads the sentence (the hero's own name
with a third-person verb reads the same; then its first act and its part before a comma):
- "<give|hand|pass|toss|slip|lend|offer> [over] <thing> [over] to <hero>",
  "<verb> <hero> <thing>";
- `thing` is "<n> gold" / "<n> gp" / "<n> coins" (gold, the `gold_amount` pattern), else
  "[n] <item>": a keepsake the actor carries, else an inventory item
  (`aidm.dm.gear_words.fits` on its names). A thing the actor does not carry is still an
  intent (`thing` ""), so the rules say so plainly;
- the receiver is another hero named by full or first name.
None when a drink / use word is said (the row's `hand_use_words` veto: "give Rook my potion to
drink", "pour it into her mouth" are healing, `aidm.dm.heal_intent`), when an abstract gift is
meant (the lexicon's `abstract_gifts`: "give Elowen my thanks", "a hug", "a nod"), or when no
hero is named. The rules decide (`aidm.rules.hero_handing.hand_events`).

Public API: `HeroHandIntent(actor_id, to_id, thing, qty, gold)`, `RESOLVERS` (`hand`).
"""

import re
from dataclasses import dataclass

from aidm.data.intent_phrases import intent_phrases
from aidm.dm.gear_words import fits, words
from aidm.dm.intent_match import Found, Resolver
from aidm.models.state import Creature, CreatureKind, GameState
from aidm.rules.item_effects import gear_name

_NUMBERS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
_NUMBERS |= {"nine": 9, "ten": 10}


@dataclass(frozen=True)
class HeroHandIntent:
    actor_id: str
    to_id: str
    thing: str | None  # an inventory key or keepsake id; "" when the actor carries no such thing
    qty: int = 1
    gold: int = 0


def _hero(state: GameState, actor_id: str, who: str) -> str | None:
    said = who.strip().removeprefix("the ")
    for c in sorted(state.creatures.values(), key=lambda c: c.id):
        if c.kind is not CreatureKind.PC or c.id == actor_id:
            continue
        name = c.name.lower()
        if said in (name, name.split()[0]):
            return c.id
    return None


def _carried(actor: Creature, phrase: str) -> str:
    assert actor.pc is not None
    said = words(phrase)
    for wanted in dict.fromkeys((said, frozenset(w.removesuffix("e") for w in said))):  # torches
        keepsake = next((k.id for k in actor.pc.keepsakes if fits(wanted, k.name)), None)
        if keepsake is not None:
            return keepsake
        for entry in actor.pc.inventory:
            if fits(wanted, gear_name(entry.item)) or fits(wanted, entry.item.replace("-", " ")):
                return entry.item
    return ""


def _what(actor: Creature, to_id: str, phrase: str) -> HeroHandIntent | None:
    phrase = phrase.strip()
    table = intent_phrases()
    if words(phrase) & table.lexicon["abstract_gifts"]:
        return None
    gold = re.fullmatch(table.patterns["gold_amount"], phrase)
    if gold is not None:
        return HeroHandIntent(actor.id, to_id, None, gold=int(gold["n"]))
    qty, count = 1, re.fullmatch(table.patterns["counted"], phrase)
    if count is not None:
        n = count["n"]
        qty, phrase = (int(n) if n.isdigit() else _NUMBERS[n]), count["rest"]
    return HeroHandIntent(actor.id, to_id, _carried(actor, phrase), qty=max(1, qty))


def hand(found: Found) -> HeroHandIntent | None:
    actor = found.state.creatures.get(found.actor_id)
    if actor is None or actor.pc is None:
        return None
    to_id = _hero(found.state, actor.id, found.group("who") or "")
    return _what(actor, to_id, found.group("item") or "") if to_id is not None else None


RESOLVERS: dict[str, Resolver] = {"hand": hand}
