"""The menu interpreter's shared table half (M36.6, SPEC 6.2, docs/next/M36_ACTION_MENU.md).

Used when `TableConfig.interpreter` is "menu" by `session.menu_turn` (a line out of a fight) and
`session.menu_fight_turn` (a hero's fight line):
- `line_menu(core, actor_id)`: the acting hero's menu right now (`rules.action_menu.build_menu`,
  with the table's shop data, so buy and sell are offered while a shop is open here);
- `pick(core, player, actor_id, text, menu)`: the chooser (`dm.chooser.choose`, with the tail of
  the table's log as `recent` for the pronoun anchors). A `ChooserFailure` shows its in-fiction
  notice (`adjudicator.FALLBACK_NOTICE`) to that player only, is logged (`chooser_failed`) and
  returns None: nothing is declared, applied or spent, so the turn is not consumed. Every pick is
  logged too (`menu_choice`: entry ids, and M36.9 the `colour` the model set apart, clipped: the
  words that only say how the hero acts; they go to nothing with mechanics, the narrator already
  has the player's whole line);
- `play_steps(core, player, acts, run, stop)`: the acts in order through `run` (the existing
  runners, which ask the rules again on the live state). A refused act (a REFUSED notice or an
  error sent while it ran, `TableCore.refusals`) stops every act after it, and so does `stop`
  (a fight started, the hero's turn ended); either way the player is told plainly that the rest
  of the line is not played (`STOPPED`), never a silent drop.

Public API: `RECENT`, `STOPPED`, `NOT_DONE`, `line_menu`, `recent_events`, `pick`, `play_steps`.
"""

from collections.abc import Awaitable, Callable, Sequence

from aidm.dm.chooser import ChooserFailure, choose
from aidm.models.action_menu import ActionMenu, MenuChoice
from aidm.models.events import AnyEvent
from aidm.models.protocol_server import NoticeKind
from aidm.rules.action_menu import build_menu
from aidm.rules.menu_steps import Act
from aidm.rules.menu_trade import TradeData
from aidm.session.table_core import Player, TableCore

RECENT = 60
STOPPED = "The rest of what you typed is not played: {why}."
NOT_DONE = "that step did not happen"
COLOUR_CHARS = 120


def line_menu(core: TableCore, actor_id: str) -> ActionMenu:
    trade = TradeData(core.regs.catalogue, core.regs.shops)
    return build_menu(core.state, actor_id, core.regs.combat, trade)


def recent_events(core: TableCore) -> list[AnyEvent]:
    return [logged.event for logged in core.log[-RECENT:]]


async def pick(
    core: TableCore, player: Player, actor_id: str, text: str, menu: ActionMenu
) -> MenuChoice | None:
    choice = await choose(core.state, actor_id, text, menu, core.llm, recent=recent_events(core))
    if isinstance(choice, ChooserFailure):
        core.notice(player.id, NoticeKind.FALLBACK, choice.notice)
        core.diag("chooser_failed", creature_id=actor_id, reason=choice.reason)
        return None
    steps = [step.entry for step in choice.steps]
    core.diag(
        "menu_choice",
        creature_id=actor_id,
        steps=steps,
        other=choice.other,
        colour=choice.colour[:COLOUR_CHARS],
    )
    return choice


async def play_steps(
    core: TableCore,
    player: Player,
    acts: Sequence[Act],
    run: Callable[[Act], Awaitable[None]],
    stop: Callable[[], str | None],
) -> None:
    for index, act in enumerate(acts):
        before = core.refusals
        await run(act)
        if index == len(acts) - 1:
            return
        why = NOT_DONE if core.refusals > before else stop()
        if why is not None:
            core.notice(player.id, NoticeKind.INFO, STOPPED.format(why=why))
            return
