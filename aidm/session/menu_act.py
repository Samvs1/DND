"""A button's pick of one menu entry (M36.11, SPEC 6.2, docs/next/M36_ACTION_MENU.md).

`menu_act(core, player, msg)`: the four buttons that used to send text (map travel, shop visit,
an item's gear use, put out the light) send `MenuAct(entry, targets, qty)` instead, the shape of
a `MenuStep`. The acting hero's menu is built on the live state (`menu_pick.line_menu`) and the
pick is checked against it: an unknown entry, a target the entry does not offer, too many
targets or too big a count is a plain REFUSED notice to that player, nothing declared, nothing
spent. A valid pick plays through the same path as a chooser pick, with NO model call:
- in a fight (`menu_fight_turn.menu_combat_line`): on the hero's turn, or off turn only the free
  entries (the pack, "what now", putting out the light), else "It is not your turn.";
- out of a fight: queued like a typed line (`menu_pick.MenuQueueEntry`) and played by
  `menu_turn.menu_line`, with the same turn and ALREADY_QUEUED rules.
The declared words (the action log) are the entry's label without its bracket, plus the target's.

Public API: `NOT_ON_MENU`, `menu_act`.
"""

import re

from aidm.models.action_menu import ActionMenu, MenuChoice, MenuEntry, MenuStep
from aidm.models.protocol_client import MenuAct
from aidm.models.protocol_server import ErrorCode, NoticeKind
from aidm.session import explore, menu_fight_turn
from aidm.session.fight_text import my_turn
from aidm.session.menu_pick import MenuQueueEntry, line_menu
from aidm.session.table_core import Player, TableCore

NOT_ON_MENU = "That is not something you can do right now."
_BRACKET = re.compile(r"\s*\([^)]*\)")


def _fits(entry: MenuEntry, msg: MenuAct) -> bool:
    return (
        set(msg.targets) <= set(entry.target_ids)
        and len(msg.targets) <= entry.max_targets
        and msg.qty <= entry.qty_max
    )


def _words(menu: ActionMenu, entry: MenuEntry, msg: MenuAct) -> str:
    labels = {t.id: t.label.split(",", 1)[0] for t in menu.targets}
    named = [labels.get(t, t) for t in msg.targets]
    return " ".join([_BRACKET.sub("", entry.label).strip(), *named])


def menu_act(core: TableCore, player: Player, msg: MenuAct) -> None:
    pc = explore.acting_hero(core, player, None)
    if pc is None:
        return
    menu = line_menu(core, pc.id)
    if core.combat_active() and not my_turn(core, pc.id):  # only the free entries play now
        picked = MenuChoice(steps=(MenuStep(entry=msg.entry, targets=msg.targets, qty=msg.qty),))
        known = next((e for e in menu.entries if e.id == msg.entry), None)
        said = _words(menu, known, msg) if known is not None else msg.entry
        menu_fight_turn.menu_combat_line(core, player, pc, said, picked)
        return
    entry = next((e for e in menu.entries if e.id == msg.entry), None)
    if entry is None or not _fits(entry, msg):
        core.notice(player.id, NoticeKind.REFUSED, NOT_ON_MENU)
        return
    choice = MenuChoice(steps=(MenuStep(entry=entry.id, targets=msg.targets, qty=msg.qty),))
    text = _words(menu, entry, msg)
    if core.combat_active():
        menu_fight_turn.menu_combat_line(core, player, pc, text, choice)
        return
    if any(e.player_id == player.id for e in core.queue):
        core.error(player.id, ErrorCode.ALREADY_QUEUED, "Your next action is already waiting.")
        return
    core.queue.append(
        MenuQueueEntry(player_id=player.id, creature_id=pc.id, text=text, choice=choice)
    )
    core.broadcast_queue()
    explore.kick_resolver(core)
