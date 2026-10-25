"""A typed line that waits for its hero's turn in the fight it started (M32.1a X3, round 5:
"Rook attacks the bandit with his shortbow" at a waiting encounter offer only started the fight,
and the attack was lost while the story told it).

`session.offer_strike` keeps the line on the player's seat (`Player.waiting_line`, a
`HeldLine`). When that hero's turn opens (`combat_flow._prompt`, after the turns before it were
told), `play` hands the same words back to the table as the player's own typed action
(`SubmitAction` through the inbox), so the engine plays it exactly as if typed then: the attack
rolls or the cast is cast, or the rules say why not. M36.6 (menu interpreter): the line keeps the
chosen menu step as a job (`HeldLine.strike`, `menu_fight_turn.held_strike`), scheduled instead of
the words, so the step is aimed at the spawned foes (`rules.menu_steps.resume_strike`).

M33.1 (ultrareview 7: a player away as the turn opened lost the line with no word): the line
is kept until it is submitted, once, and only in its hero's own open turn:
- the player has no open connection as the turn opens (the reconnect grace): the line comes due
  in that turn (`HeldLine.due`), and `on_return` plays it when the player comes back while that
  same turn is still open;
- the turn passes without it (the careful auto-turn of an away or downed hero, `lapse`), or the
  fight ends first (`drop_all`): the table is told plainly that it will not be played
  (`LAPSED`), and it is never played afterwards.

Public API: `LAPSED`, `keep(player, text, strike=None)`, `play(core, owner)`,
`on_return(core, player)`, `lapse(core, creature_id)`, `drop_all(core)`.
"""

from aidm.models.protocol_client import SubmitAction
from aidm.models.protocol_server import NoticeKind
from aidm.session.table_core import ClientIn, Job, Player, TableCore
from aidm.session.table_records import HeldLine

LAPSED = "What was typed for {name} at the offer will not be played: {why}."
_TURN_PASSED = "the turn passed first"
_FIGHT_OVER = "the fight ended first"


def keep(player: Player, text: str, strike: Job | None = None) -> None:
    player.waiting_line = HeldLine(text, strike=strike)


def _submit(core: TableCore, owner: Player, line: HeldLine) -> None:
    owner.waiting_line = None
    if line.strike is not None:  # M36.6: the menu step chosen at the offer
        core.schedule(line.strike)
        return
    core.inbox.put_nowait(ClientIn(min(owner.conns), SubmitAction(text=line.text)))


def play(core: TableCore, owner: Player) -> None:
    """The owner's hero's turn just opened: submit the line, or hold it due in this turn."""
    line = owner.waiting_line
    if line is None:
        return
    if owner.conns:
        _submit(core, owner, line)
    else:
        line.due = core.turn_key


def on_return(core: TableCore, player: Player) -> None:
    """A returning player whose line came due in the turn still open gets it played now."""
    line, enc = player.waiting_line, core.state.encounter
    if line is None or line.due is None or enc is None or not player.conns:
        return
    if line.due == core.turn_key and enc.active_id() == player.creature_id:
        _submit(core, player, line)


def _tell(core: TableCore, player: Player, why: str) -> None:
    player.waiting_line = None
    hero = core.state.creatures.get(player.creature_id or "")
    name = hero.name if hero is not None else player.name
    core.notice(None, NoticeKind.INFO, LAPSED.format(name=name, why=why))


def lapse(core: TableCore, creature_id: str) -> None:
    """The hero's turn is played without the line (away or downed): it lapses, said plainly."""
    owner = core.owner_of(creature_id)
    if owner is not None and owner.waiting_line is not None:
        _tell(core, owner, _TURN_PASSED)


def drop_all(core: TableCore) -> None:
    for player in core.players.values():
        if player.waiting_line is not None:
            _tell(core, player, _FIGHT_OVER)
