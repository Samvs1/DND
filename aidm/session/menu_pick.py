"""The menu interpreter's shared table half (M36.6, SPEC 6.2, docs/next/M36_ACTION_MENU.md).

Used by `session.menu_turn` (a line out of a fight) and `session.menu_fight_turn` (a hero's
fight line) when `TableConfig.interpreter` is "menu":
- `line_menu`: the acting hero's menu now (shop data, the waiting card, the line's NOT OFFERED
  things);
- `pick`: the chooser's pick; a failure is the fallback notice and consumes nothing; every pick
  is logged (`menu_choice`, and the `LineRead` record, `record_read`);
- `play_steps`: the line's groups in order through `run`; a refused act or `stop` cuts the rest,
  which is told (`tell_cut`), never dropped silently;
- `tell_rest`: what an act that ends the line cut off (`Plan.rest`) is told;
- `tell_cut`: the plain `STOPPED` notice, and the cut part (in its own words, `cut_words`) logged
  as an `ActionImpossible` with the reason, unless a refusal already logged one.

Public API: `MenuQueueEntry`, `RECENT`, `STOPPED`, `NOT_DONE`, `waiting_card`, `line_menu`,
`recent_events`, `pick`, `record_read`, `play_steps`, `tell_rest`, `tell_cut`, `cut_words`.
"""

from collections.abc import Awaitable, Callable, Sequence

from aidm.dm.chooser import ChooserFailure, choose
from aidm.models.action_menu import ActionMenu, MenuChoice, MenuStep
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
from aidm.rules.acts import OtherIntent
from aidm.rules.menu_card import WaitingCard, with_card
from aidm.rules.menu_steps import Group, Plan
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
    _log_only(
        core,
        LineRead(
            creature_id=actor_id, text=text[:MAX_IMPOSSIBLE_TEXT], steps=steps, other=choice.other
        ),
    )


def _log_only(core: TableCore, event: AnyEvent) -> None:
    """Apply a record that no telling is handed (it leaves the segment again)."""
    core.apply(event)
    if core.segment and core.segment[-1] is event:
        core.segment.pop()


async def play_steps(
    core: TableCore,
    entry: QueueEntry,
    menu: ActionMenu,
    groups: Sequence[Group],
    run: Callable[[Group], Awaitable[None]],
    stop: Callable[[], str | None],
) -> bool:
    for index, group in enumerate(groups):
        before, logged = core.refusals, len(core.log)
        await run(group)
        refused = core.refusals > before
        if refused:
            _log_refusal(core, entry, logged)
        if index == len(groups) - 1:
            return True
        if refused:
            tell_cut(core, entry, NOT_DONE)  # the refusal is logged already
            return False
        why = stop()
        if why is not None:
            tell_cut(core, entry, why, _group_words(menu, groups[index + 1 :]))
            return False
    return True


def _log_refusal(core: TableCore, entry: QueueEntry, since: int) -> None:
    """M43.2 (B1): the refusal's reason as an `ActionImpossible`, unless one is logged."""
    if any(isinstance(e.event, ActionImpossible) for e in core.log[since:]):
        return
    _impossible(core, entry, entry.text, core.last_refusal or NOT_DONE)


def _impossible(core: TableCore, entry: QueueEntry, text: str, reason: str) -> None:
    _log_only(
        core,
        ActionImpossible(
            creature_id=entry.creature_id,
            text=text[:MAX_IMPOSSIBLE_TEXT],
            reason=reason[:MAX_IMPOSSIBLE_REASON],
        ),
    )


def cut_words(menu: ActionMenu, steps: Sequence[MenuStep], other: str = "") -> str:
    """The part of a line a cut leaves out, in its own words: its steps' labels on the menu the
    line was read on, then its `other` words."""
    labels = {e.id: e.label.split(" (", 1)[0] for e in menu.entries}
    words = [labels.get(s.entry, s.entry) for s in steps]
    return "; ".join(w for w in dict.fromkeys([*words, other.strip()]) if w)


def _group_words(menu: ActionMenu, groups: Sequence[Group]) -> str:
    steps = [step for step, _ in groups if step is not None]
    other = [
        a.text for step, acts in groups if step is None for a in acts if isinstance(a, OtherIntent)
    ]
    return cut_words(menu, steps, " ".join(other))


def tell_rest(
    core: TableCore, entry: QueueEntry, menu: ActionMenu, plan: Plan, refused: bool
) -> None:
    """M41.3: what an act that ends the line cut off is told (after a refused end: not done)."""
    if plan.rest is None:
        return
    if refused:
        tell_cut(core, entry, NOT_DONE)
    else:
        tell_cut(core, entry, plan.why, cut_words(menu, plan.rest.steps, plan.rest.other_text))


def tell_cut(core: TableCore, entry: QueueEntry, why: str, cut: str | None = None) -> None:
    """The player is told the rest is not played; the cut part (`cut`, its own words) is logged
    with the plain reason, so the storyteller never reads the whole line as not done. None: a
    refusal of this line is logged already."""
    core.notice(entry.player_id, NoticeKind.INFO, STOPPED.format(why=why))
    if cut is not None:
        _impossible(core, entry, cut, why)
