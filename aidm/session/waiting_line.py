"""A typed line that waits for its hero's turn in the fight it started (M32.1a X3, round 5:
"Rook attacks the bandit with his shortbow" at a waiting encounter offer only started the fight,
and the attack was lost while the story told it).

`session.offer_strike` keeps the line on the player's seat (`Player.waiting_line`). When that
hero's turn opens (`combat_flow._prompt`, after the turns before it were told), `play` hands the
same words back to the table as the player's own typed action (`SubmitAction` through the
inbox), so the engine plays it exactly as if typed then: the attack rolls or the cast is cast,
or the rules say why not. The fight's end drops every line still waiting (`drop_all`): a hero
who never got a turn says so in the story of the fight, nothing is played afterwards.

Public API: `keep(player, text)`, `play(core, owner)`, `drop_all(core)`.
"""

from aidm.models.protocol_client import SubmitAction
from aidm.session.table_core import ClientIn, Player, TableCore


def keep(player: Player, text: str) -> None:
    player.waiting_line = text


def play(core: TableCore, owner: Player) -> None:
    text, owner.waiting_line = owner.waiting_line, None
    if text and owner.conns:
        core.inbox.put_nowait(ClientIn(min(owner.conns), SubmitAction(text=text)))


def drop_all(core: TableCore) -> None:
    for player in core.players.values():
        player.waiting_line = None
