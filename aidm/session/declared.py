"""A player's typed action, told to the whole table as it starts to play out (M22.1, owner request).

`declare(core, entry)` applies ONE `ActionDeclared` with the player's seat name, their hero and
the words as typed (`declared_text`: control and direction-override characters dropped, every
whitespace run folded to one space, capped at the length the Dungeon Master reads). The public
feed broadcasts it as `player_action` and keeps it in the story history, so the shared screen
shows who did what before the telling, also after a reload or a restart. Empty words declare
nothing. The event is bookkeeping: it never joins a combat segment's telling, and the player's
words reach the model only through the wrapped player block, never as an event line.

Callers: the exploration resolver (every typed action except the private inventory listing), a
creative action in a fight (after the earlier segment is told) and a typed move.

Public API: `declared_text`, `declare`.
"""

import re

from aidm.dm.context import MAX_PLAYER_CHARS
from aidm.models.protocol_views import QueueEntry
from aidm.models.world_events import ActionDeclared
from aidm.session.table_core import TableCore

_HIDDEN = re.compile(r"[\x00-\x08\x0e-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069]")
_SPACE = re.compile(r"\s+")


def declared_text(text: str) -> str:
    """The words as the table reads them: one line, no hidden characters, capped."""
    return _SPACE.sub(" ", _HIDDEN.sub("", text)).strip()[:MAX_PLAYER_CHARS]


def declare(core: TableCore, entry: QueueEntry) -> None:
    player = core.players.get(entry.player_id)
    text = declared_text(entry.text)
    if player is None or not text:
        return
    name = player.name.strip() or "A player"
    event = ActionDeclared(creature_id=entry.creature_id, player_name=name, text=text)
    core.apply(event)
    core.segment = [e for e in core.segment if e is not event]
