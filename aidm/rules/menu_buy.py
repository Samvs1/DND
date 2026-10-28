"""Typed buys at an open shop (M44.3, round 9 BB2, BB3; SPEC 6.2). Pure.

A buy is one payment, and a buy is answered by the shop's own rules (`rules.shop.buy_events`:
"No sale: 150 gp needed, 31 gp carried"). The item is recognised by the engine's whole-word name
match (`story_names.mentions`: the buy entry's item id or its catalogue name), never a word list.
- `one_payment(state, menu, steps, text)`: a `pay` step at the open shop's keeper is that buy's
  price when the line has a buy step (dropped: r9-quests 618 paid 50 twice for one potion), and
  is the buy of the one stocked item the line names when it has none (r9-typed 91 "pays the
  peddler 5 gold for one Healer's Kit" handed 5 gold over for no kit).
- `named_buy(menu, text)`: the buy step of the one buy entry the text names, its count the
  number said right before the name ("10 Camp Rations"; the number+unit shape of
  `menu_unoffered.GOLD_SUM`), else 1. M44.3b: a ware the hero cannot pay for is an ordinary
  buy entry (`menu_trade`), so the model picks it and the shop's rules refuse it (r9-typed
  1006, 1546); an `other` part naming a ware is never turned into a buy here (a stunt at a
  ware, "I slip the scroll into my sleeve", is possible and stays the storyteller's).
- `absorbed(menu, steps, text)`: the `other` part names only what a buy step already buys.
- `carried_buy(menu, rest, text)`: the rest of a line carried past an agreed shop opening
  (M41.3): its `other` part naming one ware of the shop now open is that buy (r9-typed 279,
  938, 1351 opened the shop and lost the buy).

Public API: `one_payment`, `named_buy`, `absorbed`, `carried_buy`.
"""

import re
from collections.abc import Sequence

from aidm.models.action_menu import (
    MAX_STEPS,
    ActionKind,
    ActionMenu,
    MenuChoice,
    MenuEntry,
    MenuStep,
)
from aidm.models.state import GameState
from aidm.rules.item_effects import gear_name
from aidm.rules.menu_view import slug
from aidm.rules.story_names import mentions, text_slug


def _keys(entry: MenuEntry) -> tuple[str, ...]:
    item = entry.item or ""
    return tuple(k for k in dict.fromkeys((item, slug(gear_name(item)))) if k)


def _count(line: str, key: str) -> int:
    said = re.search(rf"-(\d+)-{re.escape(key)}(?:s|es)?-", line)
    return max(1, int(said.group(1))) if said is not None else 1


def named_buy(menu: ActionMenu, text: str) -> MenuStep | None:
    line = text_slug(text)
    hits: list[tuple[MenuEntry, str]] = []
    for entry in menu.entries:
        key = next((k for k in _keys(entry) if mentions(line, k)), None)
        if entry.kind is ActionKind.BUY and key is not None:
            hits.append((entry, key))
    if len(hits) != 1:
        return None
    entry, key = hits[0]
    return MenuStep(entry=entry.id, qty=_count(line, key))


def _kinds(menu: ActionMenu) -> dict[str, ActionKind]:
    return {e.id: e.kind for e in menu.entries}


def one_payment(
    state: GameState, menu: ActionMenu, steps: Sequence[MenuStep], text: str
) -> tuple[MenuStep, ...]:
    keeper = state.world.shop_npc_id
    kinds = _kinds(menu)

    def at_keeper(step: MenuStep) -> bool:
        return kinds.get(step.entry) is ActionKind.PAY and step.targets == (keeper,)

    if keeper is None or not any(at_keeper(s) for s in steps):
        return tuple(steps)
    bought = any(kinds.get(s.entry) is ActionKind.BUY for s in steps)
    out: list[MenuStep] = []
    for step in steps:
        if not at_keeper(step):
            out.append(step)
        elif not bought:
            buy = named_buy(menu, text)
            out.append(step if buy is None else buy)
            bought = buy is not None
    return tuple(out)


def absorbed(menu: ActionMenu, steps: Sequence[MenuStep], text: str) -> bool:
    named = named_buy(menu, text)
    return named is not None and named.entry in {s.entry for s in steps}


def carried_buy(menu: ActionMenu, rest: MenuChoice, text: str) -> MenuChoice:
    if not rest.other or len(rest.steps) >= MAX_STEPS:
        return rest
    buy = named_buy(menu, rest.other_text or text)
    if buy is None:
        return rest
    if buy.entry in {s.entry for s in rest.steps}:
        return MenuChoice(steps=rest.steps, colour=rest.colour)
    return MenuChoice(steps=(*rest.steps, buy), colour=rest.colour)
