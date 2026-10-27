"""A hero's typed fight line, read by the menu chooser (M36.6, SPEC 6.1, 6.2).

`menu_combat_line(core, player, pc, text)`:
- off the hero's turn: no model call. Only an exact free entry of the menu (the pack, "what
  now", putting out the light; `dm.chooser.exact_choice` on those entries alone) plays; any other
  line is answered "It is not your turn." and nothing is consumed;
- on the hero's turn (a scheduled job): the fight menu, the chooser's pick (`menu_pick.pick`; a
  failure is the fallback notice, nothing spent, the turn still open), the acts
  (`rules.menu_steps.plan_line`, planned on the state each step leaves), then `play_fight_acts`.
  M41.3 (round 7 Z6): what an act that ends the line cut off (end turn, flee) is told
  (`menu_pick.tell_rest`), never dropped silently.

`play_fight_acts(core, player, entry, menu, groups, turn=True)`: the segment so far is told and
the words declared once (not for a private listing), then each act through the existing runner,
which asks the rules again on the live state: a move list, a draw, a surrender demand, a refusal and
`OtherIntent` (the creative action, `fight_text._creative`, with the off-menu words) through
`fight_text.play_act`; every other hotbar command through `combat_flow.player_command`; the pack
listing, "what now" (`what_now.answer`) and a put-out (`gear_actions.fight_use`). A refused act
stops the acts after it, and so does the end of the hero's turn or of the fight
(`menu_pick.play_steps`).

Stunt cost (DECISIONS M36.6): a stunt (`other`) is an improvised action and takes the hero's
action (SRD "Improvising an Action"); a flourish that only colours a step is no stunt (the
chooser's rules say so). A stunt first and an attack after it: the attack meets the rules' plain
"no action left"; an attack first and a stunt after it: the stunt meets `ACTION_SPENT`.

`held_strike(core, player, actor_id, step, text)`: the job a strike chosen at a waiting offer
waits as (`waiting_line.keep`, M32.1a X3 / M33.1 lapse rules unchanged): on the hero's turn the
step is aimed at the spawned foes (`rules.menu_steps.resume_strike`) and played as above.

Public API: `TURN_OVER`, `menu_combat_line`, `play_fight_acts`, `held_strike`.
"""

from collections.abc import Sequence

from aidm.dm.chooser import exact_choice
from aidm.dm.scene_text import inventory_text
from aidm.models.action_menu import ActionKind, ActionMenu, MenuChoice, MenuStep
from aidm.models.protocol_server import ErrorCode, NoticeKind
from aidm.models.protocol_views import QueueEntry
from aidm.models.state import Creature
from aidm.rules.acts import InventoryIntent, OtherIntent, RefusedIntent, UseIntent, WhatNowIntent
from aidm.rules.acts_fight import DrawAttack, SurrenderIntent
from aidm.rules.menu_steps import Act, Group, plan_line, resume_strike, to_groups
from aidm.rules.menu_steps_fight import COMMAND_TYPES
from aidm.session import combat_flow, gear_actions, what_now
from aidm.session.declared import declare
from aidm.session.fight_text import NOT_YOUR_TURN, my_turn, play_act
from aidm.session.menu_pick import (
    MenuQueueEntry,
    line_menu,
    pick,
    play_steps,
    tell_rest,
)
from aidm.session.table_core import Job, Player, TableCore

TURN_OVER = "your turn is over"
CANNOT = "That cannot be done in a fight."
_FREE = frozenset({ActionKind.INVENTORY, ActionKind.WHAT_NOW, ActionKind.PUT_OUT})


def _free_menu(menu: ActionMenu) -> ActionMenu:
    entries = tuple(e for e in menu.entries if e.kind in _FREE)
    return ActionMenu(scope=menu.scope, actor_id=menu.actor_id, entries=entries)


def menu_combat_line(
    core: TableCore, player: Player, pc: Creature, text: str, picked: MenuChoice | None = None
) -> None:
    """`picked`: a button's menu pick (M36.11, `session.menu_act`), played with no model call."""
    entry = QueueEntry(player_id=player.id, creature_id=pc.id, text=text)
    if picked is not None:
        entry = MenuQueueEntry(player_id=player.id, creature_id=pc.id, text=text, choice=picked)
    if my_turn(core, pc.id):
        core.schedule(lambda: _turn(core, player, entry))
        return
    free = _free_menu(line_menu(core, pc.id))
    if picked is None:
        choice = exact_choice(free, text)
    else:
        known = {e.id for e in free.entries}
        choice = picked if all(s.entry in known for s in picked.steps) else None
    if choice is None:
        core.error(player.id, ErrorCode.NOT_YOUR_TURN, NOT_YOUR_TURN)
        return
    groups = to_groups(core.state, free, choice, core.regs.combat, text)

    async def off_turn() -> None:
        await play_fight_acts(core, player, entry, free, groups, turn=False)

    core.schedule(off_turn)


async def _turn(core: TableCore, player: Player, entry: QueueEntry) -> None:
    if not my_turn(core, entry.creature_id):  # the turn passed while the job waited
        core.error(player.id, ErrorCode.NOT_YOUR_TURN, NOT_YOUR_TURN)
        return
    menu = line_menu(core, entry.creature_id, entry.text)
    if isinstance(entry, MenuQueueEntry):
        choice = entry.choice
    else:
        choice = await pick(core, player, entry.creature_id, entry.text, menu)
    if choice is None:
        return
    plan = plan_line(core.state, menu, choice, core.regs.combat, entry.text)
    before = core.refusals
    if await play_fight_acts(core, player, entry, menu, plan.groups):  # M41.3: the cut part told
        tell_rest(core, entry, menu, plan, core.refusals > before)


def _private(act: Act) -> bool:
    return isinstance(act, InventoryIntent | WhatNowIntent)


async def play_fight_acts(
    core: TableCore,
    player: Player,
    entry: QueueEntry,
    menu: ActionMenu,
    groups: Sequence[Group],
    *,
    turn: bool = True,
) -> bool:
    single: list[Group] = [(step, [act]) for step, made in groups for act in made]
    if not all(_private(act) for _, made in groups for act in made):
        if turn:
            await combat_flow.tell_segment(core)
        declare(core, entry)

    async def run(group: Group) -> None:
        for act in group[1]:
            await _fight_act(core, player, entry, act)

    def stop() -> str | None:
        return TURN_OVER if turn and not my_turn(core, entry.creature_id) else None

    return await play_steps(core, entry, menu, single, run, stop)


async def _fight_act(core: TableCore, player: Player, entry: QueueEntry, act: Act) -> None:
    if isinstance(act, list | DrawAttack | SurrenderIntent | RefusedIntent):
        await play_act(core, player, entry, act, say=False)
    elif isinstance(act, OtherIntent):  # the creative action: it takes the action
        await play_act(core, player, entry.model_copy(update={"text": act.text}), None, say=False)
    elif isinstance(act, COMMAND_TYPES):
        await combat_flow.player_command(core, player, act)
    elif isinstance(act, InventoryIntent):
        hero = core.state.creatures.get(act.actor_id)
        if hero is not None:
            core.notice(player.id, NoticeKind.INFO, inventory_text(hero))
    elif isinstance(act, WhatNowIntent):
        what_now.answer(core, player)
    elif isinstance(act, UseIntent):
        await gear_actions.fight_use(core, player, entry, act, say=False)
    else:  # an explore act on a fight menu: the menu never makes one, said plainly if it did
        core.notice(player.id, NoticeKind.REFUSED, CANNOT)


def held_strike(core: TableCore, player: Player, actor_id: str, step: MenuStep, text: str) -> Job:
    async def job() -> None:
        entry = QueueEntry(player_id=player.id, creature_id=actor_id, text=text)
        if not my_turn(core, actor_id):
            core.error(player.id, ErrorCode.NOT_YOUR_TURN, NOT_YOUR_TURN)
            return
        acts = resume_strike(core.state, actor_id, step, core.regs.combat)
        await play_fight_acts(core, player, entry, line_menu(core, actor_id), [(step, acts)])

    return job
