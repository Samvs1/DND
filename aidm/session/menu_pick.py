"""The menu interpreter's shared table half (M36.6, SPEC 6.2, docs/next/M36_ACTION_MENU.md).

Used when `TableConfig.interpreter` is "menu" by `session.menu_turn` (a line out of a fight) and
`session.menu_fight_turn` (a hero's fight line):
- `line_menu(core, actor_id, text="")`: the acting hero's menu right now
  (`rules.action_menu.build_menu`, with the table's shop data, so buy and sell are offered while
  a shop is open here); M40.1: with the confirm card waiting for this hero's player
  (`waiting_card`, the table's `PendingHostile`) as `card:yes` / `card:no`
  (`rules.menu_card.with_card`); M43.2: with the line's NOT OFFERED things
  (`rules.menu_unoffered.with_unoffered`), so a step at one is refused with the reason;
- `pick(core, player, actor_id, text, menu)`: the chooser (`dm.chooser.choose`, with the tail of
  the table's log as `recent` for the pronoun anchors). A `ChooserFailure` shows its in-fiction
  notice (`adjudicator.FALLBACK_NOTICE`) to that player only, is logged (`chooser_failed`) and
  returns None: nothing is declared, applied or spent, so the turn is not consumed. Every pick is
  logged too (`menu_choice`: entry ids, and M36.9 the `colour` the model set apart, clipped: the
  words that only say how the hero acts; they go to nothing with mechanics, the narrator already
  has the player's whole line);
- `play_steps(core, player, entry, acts, run, stop)`: the acts in order through `run` (the
  existing runners, which ask the rules again on the live state). A refused act (a REFUSED notice
  or an error sent while it ran, `TableCore.refusals`) stops every act after it, and so does
  `stop` (a fight started, the hero's turn ended); either way the player is told plainly that
  the rest of the line is not played (`STOPPED`), never a silent drop. M41.3: it answers whether
  every act ran (the caller then tells what an act that ends the line cut off, `tell_cut`).
  M43.2 (the contract's B1): a refusal that logged no `ActionImpossible` logs one with the
  refusal's words (`TableCore.last_refusal`), so every refused typed line leaves its reason in
  the save (log-only here: the player has the notice, the screen shows the event).
- `tell_cut(core, player, entry, why)`: the plain `STOPPED` notice with that reason; M43.2 (B4):
  logged as an `ActionImpossible` for the part not played.

Public API: `MenuQueueEntry`, `RECENT`, `STOPPED`, `NOT_DONE`, `waiting_card`, `line_menu`,
`recent_events`,
`pick` (M43.1: it logs a `LineRead`), `record_read`, `play_steps`, `tell_cut`.
"""

from collections.abc import Awaitable, Callable, Sequence

from aidm.dm.chooser import ChooserFailure, choose
from aidm.models.action_menu import ActionMenu, MenuChoice
from aidm.models.events import AnyEvent
from aidm.models.impossible import (
    MAX_IMPOSSIBLE_REASON,
    MAX_IMPOSSIBLE_TEXT,
    MAX_READ_STEP,
    MAX_READ_STEPS,
    ActionImpossible,
    LineRead,
)
from aidm.models.protocol_server import NoticeKind
from aidm.models.protocol_views import QueueEntry
from aidm.rules.action_menu import build_menu
from aidm.rules.menu_card import WaitingCard, with_card
from aidm.rules.menu_trade import TradeData
from aidm.rules.menu_unoffered import with_unoffered
from aidm.session.table_core import Player, TableCore

RECENT = 60
STOPPED = "The rest of what you typed is not played: {why}."
NOT_DONE = "that step did not happen"
COLOUR_CHARS = 120


class MenuQueueEntry(QueueEntry):
    """A queued button pick (M36.11): the pick rides with the entry, the wire shows the base."""

    choice: MenuChoice


def waiting_card(core: TableCore, actor_id: str) -> WaitingCard | None:
    """The confirm card held for this hero's player, if one waits (M40.1)."""
    pending = core.pending
    owner = core.owner_of(actor_id)
    if pending is None or owner is None or pending.player_id != owner.id:
        return None
    return WaitingCard(actor_id, pending.prompt) if pending.actor_id == actor_id else None


def line_menu(core: TableCore, actor_id: str, text: str = "") -> ActionMenu:
    trade = TradeData(core.regs.catalogue, core.regs.shops)
    menu = build_menu(core.state, actor_id, core.regs.combat, trade)
    menu = with_card(menu, waiting_card(core, actor_id))
    return with_unoffered(core.state, menu, text) if text else menu


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
    record_read(core, actor_id, text, choice)
    return choice


def record_read(core: TableCore, actor_id: str, text: str, choice: MenuChoice) -> None:
    """M43.1: log how the typed line was read (log-only; never part of a telling)."""
    steps = tuple(
        (f"{s.entry}>{','.join(s.targets)}" if s.targets else s.entry)[:MAX_READ_STEP]
        for s in choice.steps[:MAX_READ_STEPS]
    )
    event = LineRead(
        creature_id=actor_id, text=text[:MAX_IMPOSSIBLE_TEXT], steps=steps, other=choice.other
    )
    core.apply(event)
    core.segment = [e for e in core.segment if e is not event]


async def play_steps[T](
    core: TableCore,
    player: Player,
    entry: QueueEntry,
    acts: Sequence[T],
    run: Callable[[T], Awaitable[None]],
    stop: Callable[[], str | None],
) -> bool:
    for index, act in enumerate(acts):
        before, logged = core.refusals, len(core.log)
        await run(act)
        if core.refusals > before:
            _log_refusal(core, entry, logged)
        if index == len(acts) - 1:
            return True
        why = NOT_DONE if core.refusals > before else stop()
        if why is not None:
            tell_cut(core, player, entry, why)
            return False
    return True


def _log_refusal(core: TableCore, entry: QueueEntry, since: int) -> None:
    """M43.2 (B1): the refusal's reason as an `ActionImpossible`, unless one is logged."""
    if any(isinstance(e.event, ActionImpossible) for e in core.log[since:]):
        return
    _impossible(core, entry, core.last_refusal or NOT_DONE)


def _impossible(core: TableCore, entry: QueueEntry, reason: str) -> None:
    event = ActionImpossible(
        creature_id=entry.creature_id,
        text=entry.text[:MAX_IMPOSSIBLE_TEXT],
        reason=reason[:MAX_IMPOSSIBLE_REASON],
    )
    core.apply(event)
    core.segment = [e for e in core.segment if e is not event]


def tell_cut(core: TableCore, player: Player, entry: QueueEntry, why: str) -> None:
    core.notice(player.id, NoticeKind.INFO, STOPPED.format(why=why))
    _impossible(core, entry, STOPPED.format(why=why))
