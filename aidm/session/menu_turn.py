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
M40.1: while a confirm card waits for this player, the menu carries it (`menu_pick.line_menu`):
`card:yes` / `card:no` play the card's own buttons (`held.confirm_hostile`, `cancel_hostile`);
any other pick is a new action, which answers the card No (`_drop_card`, the manual's rule).
M41.3 (round 7 Z6): what an act that ends the line cut off (`rules.menu_steps.plan_line`) is
never dropped: after a travel, rest or shop the party agreed to, it is played once the job is
done, on the menu of where the party is (`_later`: a fight that started, a walk that stopped
short or a step that no longer fits is told); after any other ending act it is told
(`menu_pick.tell_cut`).
Z7: a shared step done by another hero (`MenuStep.by`) is announced first (`DOES`).

Public API: `FIGHT_STARTED`, `DOES`, `menu_line`.
"""

from dataclasses import dataclass
from typing import TypeIs

from aidm.models.action_menu import ActionMenu, MenuChoice, MenuStep
from aidm.models.protocol_client import (
    AnswerOffer,
    CancelHostile,
    ConfirmHostile,
    CopyScroll,
    ShopBuy,
    ShopSell,
)
from aidm.models.protocol_server import NoticeKind
from aidm.models.protocol_views import QueueEntry
from aidm.models.state import Creature
from aidm.rules.acts import (
    Intent,
    InventoryIntent,
    RestIntent,
    ShopIntent,
    TravelIntent,
    WhatNowIntent,
)
from aidm.rules.menu_card import picks_card
from aidm.rules.menu_steps import Act, Group, Plan, plan_line, refit, step_actor, step_acts
from aidm.rules.scene import node_display_name
from aidm.session import held, party_actions, scene_votes, what_now
from aidm.session.asides import Aside, told_with
from aidm.session.declared import declare
from aidm.session.intent_turn import run_intent
from aidm.session.menu_pick import (
    NOT_DONE,
    MenuQueueEntry,
    line_menu,
    pick,
    play_steps,
    tell_cut,
)
from aidm.session.table_core import Job, Player, TableCore

FIGHT_STARTED = "the fight has started"
CANNOT = "That cannot be done outside a fight."
DOES = "{hero} does this: {what}."
SHORT = "the party did not reach {place}"


def _intent(act: Act) -> TypeIs[Intent]:
    return isinstance(act, Intent.__value__)


def _private(act: Act) -> bool:
    return isinstance(act, InventoryIntent | WhatNowIntent)


@dataclass
class _Line:
    """One typed line being played: who typed it, the hero, the words, the menu it was read on."""

    core: TableCore
    player: Player
    actor: Creature
    entry: QueueEntry
    menu: ActionMenu
    carried: bool = False  # M41.3: the rest waits for an agreed travel or rest


async def menu_line(core: TableCore, player: Player, actor: Creature, entry: QueueEntry) -> None:
    menu = line_menu(core, actor.id)
    if isinstance(entry, MenuQueueEntry):  # a button's pick (M36.11): no model call
        choice = entry.choice
    else:
        choice = await pick(core, player, actor.id, entry.text, menu)
    if choice is None:
        return
    _drop_card(core, player, choice)
    line = _Line(core, player, actor, entry, menu)
    plan = plan_line(core.state, menu, choice, core.regs.combat, entry.text)
    if not all(_private(act) for _, acts in plan.groups for act in acts):
        declare(core, entry)
    with told_with(Aside(choice.colour)):  # M36.10a: the manner is told with the first telling
        await _play(line, plan)


async def _play(line: _Line, plan: Plan) -> None:
    core = line.core
    refused = core.refusals

    async def run(group: Group) -> None:
        nonlocal refused
        refused = core.refusals
        step, planned = group
        acts = planned  # M36.10a: each step planned again on the state the steps before it left
        if step is not None:
            _announce(line, step)
            acts = step_acts(core.state, line.menu, step, core.regs.combat, line.entry.text)
        for act in acts:
            before = core.refusals
            await _run(line, act, plan.rest)
            if core.refusals > before:
                return

    done = await play_steps(core, line.player, plan.groups, run, lambda: _fight_started(core))
    if done and plan.rest is not None and not line.carried:
        tell_cut(core, line.player, NOT_DONE if core.refusals > refused else plan.why)


def _announce(line: _Line, step: MenuStep) -> None:
    """M41.3 (Z7): a step another hero does for this line says who acts."""
    hero_id = step_actor(line.menu, step)
    hero = line.core.state.creatures.get(hero_id)
    entry = next((e for e in line.menu.entries if e.id == step.entry), None)
    if hero_id != line.actor.id and hero is not None and entry is not None:
        line.core.notice(None, NoticeKind.INFO, DOES.format(hero=hero.name, what=entry.label))


def _later(line: _Line, rest: MenuChoice, goal: str | None) -> Job:
    """M41.3: the rest of the line, once the agreed travel, rest or shop is done."""
    core = line.core

    async def job() -> None:
        if core.combat_active():
            tell_cut(core, line.player, FIGHT_STARTED)
            return
        if goal is not None and core.state.world.current_node != goal:
            tell_cut(core, line.player, SHORT.format(place=node_display_name(core.state, goal)))
            return
        hero = core.state.creatures.get(line.actor.id, line.actor)
        menu = line_menu(core, hero.id)
        fitted, why = refit(menu, line.menu, rest)
        if fitted is not None:
            later = _Line(core, line.player, hero, line.entry, menu)
            await _play(
                later, plan_line(core.state, menu, fitted, core.regs.combat, line.entry.text)
            )
        if why:
            tell_cut(core, line.player, why)

    return job


def _drop_card(core: TableCore, player: Player, choice: MenuChoice) -> None:
    """A new action answers this player's waiting card No (M15.1), unless it answers the card."""
    pending = core.pending
    if pending is not None and pending.player_id == player.id and not picks_card(choice):
        core.pending = None


def _fight_started(core: TableCore) -> str | None:
    return FIGHT_STARTED if core.combat_active() else None


async def _run(line: _Line, act: Act, rest: MenuChoice | None) -> None:
    core, player, entry = line.core, line.player, line.entry
    hero = core.state.creatures.get(line.actor.id, line.actor)
    if isinstance(act, TravelIntent | RestIntent | ShopIntent) and rest is not None:  # M41.3
        goal = (act.goal or act.node_id) if isinstance(act, TravelIntent) else None
        then = _later(line, rest, goal)
        line.carried = scene_votes.propose_intent(core, player, entry, act, then)
    elif isinstance(act, WhatNowIntent):
        what_now.answer(core, player)
    elif isinstance(act, AnswerOffer):
        await party_actions.answer(core, player, act)
    elif isinstance(act, ShopBuy):
        await party_actions.buy(core, player, act)
    elif isinstance(act, ShopSell):
        await party_actions.sell(core, player, act)
    elif isinstance(act, CopyScroll):
        await party_actions.copy_scroll(core, player, act)
    elif isinstance(act, ConfirmHostile):  # M40.1: the waiting card's own Yes
        await held.confirm_hostile(core, player)
    elif isinstance(act, CancelHostile):
        await held.cancel_hostile(core, player)
    elif _intent(act):
        await run_intent(core, player, hero, entry, act)
    else:  # a fight act on an explore menu: the menu never makes one, said plainly if it did
        core.notice(player.id, NoticeKind.REFUSED, CANNOT)
