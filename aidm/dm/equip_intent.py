"""Typed equip, unequip and drop (SPEC 6.2 pre-checks; moved out of `aidm.dm.precheck` in M29.7a).

`item_command(state, actor_id, clean)` reads the precheck's normalised sentence and returns an
`ItemIntent` when it plainly equips, unequips or drops an item the actor carries (or wears):
- equip: equip, wield, wear, don, put on, pull on, strap on, slip on, ready, draw, heft, take up,
  switch to, swap to; "swap/switch/trade my <old> for <new>" equips the new one;
- unequip: unequip, unwield, sheathe, stow, put away, take off, doff, remove, unstrap, unhook,
  unbuckle, unsling;
- drop: drop, discard, throw away.
M29.7a R9 ("Elowen unhooks her mace and wields the new warhammer instead", "I put on the studded
leather armor in place of my leather armor" equipped nothing): the hero's own name with a
third-person verb reads the same (`aidm.dm.sentence.own_reading`); a trailing "instead",
"in place of ..." or "instead of ..." is dropped; the two acts of "<unequip X> and <equip Y>"
read as the equip (it takes Y in hand, the rules free the slot); an item named with a spare word
("the new warhammer") is the carried item whose name words are all in the phrase, the others
only spare words (`_SPARE`: new, old, spare ...; an exact name first). Anything else is None.
The rules decide (`aidm.rules.equipment`).

Public API: `ItemAction` (EQUIP/UNEQUIP/DROP), `ItemIntent(actor_id, action, item)` (`item` the
inventory index), `item_command(state, actor_id, clean) -> ItemIntent | None`.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from aidm.dm.entities import display_name
from aidm.dm.sentence import own_reading, plain_verb, split_clause
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


_THE = r"(?:my |the |a |an |his |her |their |our )?"
_EQUIP = re.compile(
    r"(?:equip|wield|don|put on|pull on|strap on|slip on|wear|ready|draw|heft|take up|"
    rf"switch to|swap to) {_THE}(?P<item>[a-z ,'-]+)|"
    rf"(?:swap|switch|trade|exchange) {_THE}[a-z ,'-]+? (?:for|with) {_THE}(?P<item2>[a-z ,'-]+)"
)
_UNEQUIP = re.compile(
    r"(?:unequip|unwield|sheathe|stow|put away|take off|doff|remove|unstrap|unhook|unbuckle|"
    rf"unsling) {_THE}(?P<item>[a-z ,'-]+)"
)
_DROP = re.compile(rf"(?:drop|discard|throw away) {_THE}(?P<item>[a-z ,'-]+)")
_SPARE = frozenset({"new", "old", "spare", "other", "own", "trusty", "second", "extra", "fine"})
_SPARE |= {"good", "bought", "shiny", "borrowed", "heavy", "light", "trusted", "plain"}
_TAIL = re.compile(r" (?:instead(?: of .*)?|in place of .*|in its place|for now)$")


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
    loose = next(
        (i for i, have in names if any(h and h <= wanted and wanted - h <= _SPARE for h in have)),
        None,
    )
    found = exact or loose
    return ItemIntent(actor.id, action, found) if found is not None else None


def _one(actor: Creature, text: str) -> ItemIntent | None:
    text = _TAIL.sub("", text).strip()
    for action, pattern in (
        (ItemAction.EQUIP, _EQUIP),
        (ItemAction.UNEQUIP, _UNEQUIP),
        (ItemAction.DROP, _DROP),
    ):
        match = pattern.fullmatch(text)
        if match:
            return _item(actor, action, match["item"] or match.groupdict().get("item2") or "")
    return None


def _plain(text: str) -> str:
    verb, _, rest = text.partition(" ")
    return f"{plain_verb(verb)} {rest}".strip()


def item_command(state: GameState, actor_id: str, clean: str) -> ItemIntent | None:
    actor = state.creatures.get(actor_id)
    if actor is None:
        return None
    own = own_reading(actor.name, clean)
    cut = split_clause(own)
    if cut is not None:
        first, second = _one(actor, cut[0]), _one(actor, _plain(cut[1]))
        if first is not None and second is not None:
            return second if second.action is ItemAction.EQUIP else first
    return _one(actor, own)
