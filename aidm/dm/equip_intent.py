"""Typed equip, unequip and drop (SPEC 6.2 pre-checks; moved out of `aidm.dm.precheck` in M29.7a).

The `item_*` phrase rows (data/bg3/intent_phrases.json) read the sentence and the resolver
returns an `ItemIntent` when it plainly equips, unequips or drops an item the actor carries (or
wears); the first verb row that matches decides:
- equip: equip, wield, wear, don, put on, pull on, strap on, slip on, ready, draw, heft, take up,
  switch to, swap to; "swap/switch/trade my <old> for <new>" equips the new one;
- unequip: unequip, unwield, sheathe, stow, put away, take off, doff, remove, unstrap, unhook,
  unbuckle, unsling;
- drop: drop, discard, throw away.
M29.7a R9 ("Elowen unhooks her mace and wields the new warhammer instead", "I put on the studded
leather armor in place of my leather armor" equipped nothing): the hero's own name with a
third-person verb reads the same (`aidm.dm.sentence.own_reading`); a trailing "instead",
"in place of ..." or "instead of ..." is dropped (the `item_tail` reading); the two acts of
"<unequip X> and <equip Y>" read as the equip (`item_pair`, ranked first: it takes Y in hand,
the rules free the slot); an item named with a spare word ("the new warhammer") is the carried
item whose name words are all in the phrase, the others only spare words (the lexicon's
`spare_item_words`: new, old, spare ...; an exact name first). Anything else is None. The rules
decide (`aidm.rules.equipment`).

Public API: `ItemAction` (EQUIP/UNEQUIP/DROP), `ItemIntent(actor_id, action, item)` (`item` the
inventory index), `RESOLVERS` (`item`, `item_pair`).
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from aidm.data.intent_phrases import intent_phrases
from aidm.dm.entities import display_name
from aidm.dm.intent_match import Found, Resolver, route
from aidm.dm.sentence import plain_verb
from aidm.models.state import Creature, GameState


class ItemAction(StrEnum):
    EQUIP = "equip"
    UNEQUIP = "unequip"
    DROP = "drop"


@dataclass(frozen=True)
class ItemIntent:
    actor_id: str
    action: ItemAction
    item: str


def _words(name: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9']+", name.lower().replace("-", " "))) - {"the"}


def _equipped(pc: Creature) -> list[str]:
    assert pc.pc is not None
    eq = pc.pc.equipped
    return [s for s in (eq.main_hand, eq.off_hand, eq.ranged, eq.armor, eq.shield) if s]


def _item(actor: Creature, action: ItemAction, name: str) -> ItemIntent | None:
    if actor.pc is None:
        return None
    pool = (
        _equipped(actor) if action is ItemAction.UNEQUIP else [i.item for i in actor.pc.inventory]
    )
    wanted = _words(name)
    names = [(index, (_words(index), _words(display_name(index)))) for index in pool]
    exact = next((i for i, have in names if wanted in have), None)
    spare = intent_phrases().lexicon["spare_item_words"]
    loose = next(
        (i for i, have in names if any(h and h <= wanted and wanted - h <= spare for h in have)),
        None,
    )
    found = exact or loose
    return ItemIntent(actor.id, action, found) if found is not None else None


def item(found: Found) -> ItemIntent | None:
    actor = found.state.creatures.get(found.actor_id)
    if actor is None:
        return None
    return _item(actor, ItemAction(str(found.params["action"])), found.group("item") or "")


def _one(state: GameState, actor_id: str, text: str) -> ItemIntent | None:
    found = route(state, actor_id, text, {"item": item}, families=("item",), base="as_is")
    return found if isinstance(found, ItemIntent) else None


def _plain(text: str) -> str:
    verb, _, rest = text.partition(" ")
    return f"{plain_verb(verb)} {rest}".strip()


def item_pair(found: Found) -> ItemIntent | None:
    """Both acts of "<unequip X> and <equip Y>" are item commands: the equip, else the first."""
    if found.rest is None:
        return None
    first = _one(found.state, found.actor_id, found.text)
    second = _one(found.state, found.actor_id, _plain(found.rest))
    if first is None or second is None:
        return None
    return second if second.action is ItemAction.EQUIP else first


RESOLVERS: dict[str, Resolver] = {"item": item, "item_pair": item_pair}
