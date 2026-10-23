"""Typed handing-over between heroes (M29.7a R7 / R8: "Brienne hands the Herbal Poultice to Elowen
and tells her to keep it" spent the poultice on Elowen; "gives the spare crowbar to Elowen" and
passing coin were prose only). A deterministic precheck like `aidm.dm.give_intent`.

`hand_intent(state, actor_id, clean)` reads the precheck's normalised sentence (the hero's own
name with a third-person verb reads the same; a trailing clause after "and" or a comma is cut):
- "<give|hand|pass|toss|slip|lend|offer> [over] <thing> [over] to <hero>",
  "<verb> <hero> <thing>";
- `thing` is "<n> gold" / "<n> gp" / "<n> coins" (gold), else "[n] <item>": a keepsake the
  actor carries, else an inventory item (`aidm.dm.gear_words.fits` on its names). A thing the
  actor does not carry is still an intent (`thing` ""), so the rules say so plainly;
- the receiver is another hero named by full or first name.
None when a drink / use word is said ("give Rook my potion to drink", "pour it into her mouth":
`aidm.dm.heal_intent` heals), when an abstract gift is meant (`ABSTRACT_GIFTS`: "give Elowen
my thanks", "a hug", "a nod"), or when no hero is named. The rules decide
(`aidm.rules.hero_handing.hand_events`).

Public API: `HeroHandIntent(actor_id, to_id, thing, qty, gold)`, `ABSTRACT_GIFTS`,
`hand_intent(state, actor_id, clean) -> HeroHandIntent | None`.
"""

import re
from dataclasses import dataclass

from aidm.dm.gear_words import fits, words
from aidm.dm.sentence import own_reading, split_clause
from aidm.models.state import Creature, CreatureKind, GameState
from aidm.rules.item_effects import gear_name

_THING = r"(?:my |the |a |an |this |that |our |some |his |her |their )?(?P<{}>[a-z0-9 ,'-]+?)"
_VERBS = r"(?:give|hand|pass|toss|slip|lend|offer)"
_HAND = re.compile(
    rf"{_VERBS}(?: over)? {_THING.format('item')}(?: over| across)? to (?P<who>[a-z' -]+?)|"
    rf"{_VERBS} (?P<who2>[a-z' -]+?) {_THING.format('item2')}"
)
_GOLD = re.compile(r"(?P<n>\d+) (?:gold(?: pieces| coins)?|gp|coins?)")
_COUNT = re.compile(r"(?P<n>\d+|two|three|four|five|six|seven|eight|nine|ten) (?P<rest>.+)")
_NUMBERS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
_NUMBERS |= {"nine": 9, "ten": 10}
_USE_WORDS = frozenset(
    {"drink", "drinks", "quaff", "sip", "swallow", "use", "uses", "apply", "applies", "feed"}
    | {"feeds", "pour", "pours", "administer", "rub", "bind", "binds", "heal", "heals", "tend"}
    | {"lips", "mouth", "wound", "wounds"}
)
ABSTRACT_GIFTS = frozenset(
    {"thanks", "thank", "regards", "word", "words", "blessing", "greeting", "greetings", "hug"}
    | {"nod", "smile", "look", "wink", "hand", "advice", "attention", "time", "name", "answer"}
    | {"apology", "apologies", "respect", "respects", "condolence", "condolences", "warning"}
    | {"signal", "sign", "moment", "chance", "break", "push", "shove", "slap", "kiss"}
)


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
    if words(phrase) & ABSTRACT_GIFTS:
        return None
    gold = _GOLD.fullmatch(phrase)
    if gold is not None:
        return HeroHandIntent(actor.id, to_id, None, gold=int(gold["n"]))
    qty, count = 1, _COUNT.fullmatch(phrase)
    if count is not None:
        n = count["n"]
        qty, phrase = (int(n) if n.isdigit() else _NUMBERS[n]), count["rest"]
    return HeroHandIntent(actor.id, to_id, _carried(actor, phrase), qty=max(1, qty))


def _reading(state: GameState, actor: Creature, reading: str) -> HeroHandIntent | None:
    match = _HAND.fullmatch(reading)
    if match is None:
        return None
    who, item = (match["who"], match["item"]) if match["who"] else (match["who2"], match["item2"])
    to_id = _hero(state, actor.id, who)
    return _what(actor, to_id, item) if to_id is not None else None


def hand_intent(state: GameState, actor_id: str, clean: str) -> HeroHandIntent | None:
    actor = state.creatures.get(actor_id)
    if actor is None or actor.pc is None:
        return None
    if set(re.findall(r"[a-z]+", clean)) & _USE_WORDS:
        return None
    own = own_reading(actor.name, clean)
    cut = split_clause(own)
    readings = [own, *(c for c in (cut[0] if cut else None, own.split(",")[0]) if c)]
    for reading in dict.fromkeys(readings):
        found = _reading(state, actor, reading)
        if found is not None:
            return found
    return None
