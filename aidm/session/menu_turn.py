"""One typed line out of a fight, read by the menu chooser (M36.6, SPEC 6.2).

`menu_line(core, player, actor, entry)`: the hero's menu (`menu_pick.line_menu`: the explore
scope, or the offer scope while an encounter offer waits here), the chooser's pick
(`menu_pick.pick`; a failure is the fallback notice and nothing else), the acts
(`rules.menu_steps.to_groups`; M36.10a: each step planned again on the live state the steps
before it left), then each act through the runner the buttons already
use, which asks the rules again on the live state:
- the intents (`intent_turn.run_intent`): give, hand, pay, take, lift, loot, equip, unequip,
  drop, talk (`AskIntent` with the words), look, search, inventory, travel, rest, shop, the quest
  card, help up, healing, casts, features, an offer strike (`offer_strike.offer_strike_turn`,
  which keeps the chosen step for the hero's turn) and `OtherIntent`: the storyteller
  (`held.adjudicated`) with the off-menu words;
- the client handlers: the offer card's answer (`party_actions.answer`), the shop's buy and sell
  and scroll copying (`party_actions.buy`, `sell`, `copy_scroll`), "what now" (`what_now.answer`).
The words are declared once (not for a private listing: the pack, "what now"). A refused act
stops the acts after it, and a fight that starts stops them too (`menu_pick.play_steps`).
The narrator still gets the player's own words for colour (the entry's text), as today; M36.10a:
the chooser's `colour` (the words that only say how the hero acts: "steps forward") is told with
the first narration of the line (`asides.told_with`), (M33.1).

Public API: `FIGHT_STARTED`, `menu_line`.
"""

from typing import TypeIs

from aidm.models.protocol_client import AnswerOffer, CopyScroll, ShopBuy, ShopSell
from aidm.models.protocol_server import NoticeKind
from aidm.models.protocol_views import QueueEntry
from aidm.models.state import Creature
from aidm.rules.acts import Intent, InventoryIntent, WhatNowIntent
from aidm.rules.menu_steps import Act, Group, step_acts, to_groups
from aidm.session import party_actions, what_now
from aidm.session.asides import Aside, told_with
from aidm.session.declared import declare
from aidm.session.intent_turn import run_intent
from aidm.session.menu_pick import MenuQueueEntry, line_menu, pick, play_steps
from aidm.session.table_core import Player, TableCore

FIGHT_STARTED = "the fight has started"
CANNOT = "That cannot be done outside a fight."


def _intent(act: Act) -> TypeIs[Intent]:
    return isinstance(act, Intent.__value__)


def _private(act: Act) -> bool:
    return isinstance(act, InventoryIntent | WhatNowIntent)


async def menu_line(core: TableCore, player: Player, actor: Creature, entry: QueueEntry) -> None:
    menu = line_menu(core, actor.id)
    if isinstance(entry, MenuQueueEntry):  # a button's pick (M36.11): no model call
        choice = entry.choice
    else:
        choice = await pick(core, player, actor.id, entry.text, menu)
    if choice is None:
        return
    groups = to_groups(core.state, menu, choice, core.regs.combat, entry.text)
    if not all(_private(act) for _, acts in groups for act in acts):
        declare(core, entry)

    async def run(group: Group) -> None:
        step, planned = group
        acts = planned  # M36.10a: each step planned again on the state the steps before it left
        if step is not None:
            acts = step_acts(core.state, menu, step, core.regs.combat, entry.text)
        for act in acts:
            before = core.refusals
            await _run(core, player, actor, entry, act)
            if core.refusals > before:
                return

    with told_with(Aside(choice.colour)):  # M36.10a: the manner is told with the first telling
        await play_steps(core, player, groups, run, lambda: _fight_started(core))


def _fight_started(core: TableCore) -> str | None:
    return FIGHT_STARTED if core.combat_active() else None


async def _run(
    core: TableCore, player: Player, actor: Creature, entry: QueueEntry, act: Act
) -> None:
    hero = core.state.creatures.get(actor.id, actor)
    if isinstance(act, WhatNowIntent):
        what_now.answer(core, player)
    elif isinstance(act, AnswerOffer):
        await party_actions.answer(core, player, act)
    elif isinstance(act, ShopBuy):
        await party_actions.buy(core, player, act)
    elif isinstance(act, ShopSell):
        await party_actions.sell(core, player, act)
    elif isinstance(act, CopyScroll):
        await party_actions.copy_scroll(core, player, act)
    elif _intent(act):
        await run_intent(core, player, hero, entry, act)
    else:  # a fight act on an explore menu: the menu never makes one, said plainly if it did
        core.notice(player.id, NoticeKind.REFUSED, CANNOT)
