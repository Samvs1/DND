"""What now? at the table (M23.8, GOAL_QUESTS "What players see").

`answer(core, player)` serves the phone's What now? button (`what_now`) and a typed "what now"
(`explore.submit_action` asks `precheck.asks_what_now` before anything else). It is NOT a turn:
no queue slot, no vote, no model call, no event, no state change, so it works in a fight and
while another action resolves. The lines come from `rules.quest_hints.what_now`; a line that
would carry private text (`public_feed.leaks`: a motive, an unrevealed secret, a hidden feature)
is dropped as defence in depth. The asker always gets `WhatNowAnswer`; the screens get it too
unless that player asked within the last 5 s (`TableCore.what_now_limit`: the screen is not
spammed).

Public API: `answer(core, player, msg=None)`.
"""

from aidm.models.protocol_client import AskWhatNow
from aidm.models.protocol_server import ErrorCode, WhatNowAnswer
from aidm.models.protocol_views import TablePhase
from aidm.rules.quest_hints import NOTHING, what_now
from aidm.session.public_feed import leaks, private_texts
from aidm.session.table_core import Player, TableCore


def answer(core: TableCore, player: Player, msg: AskWhatNow | None = None) -> None:
    if core.phase is not TablePhase.PLAY:
        ended = core.phase is TablePhase.ENDED
        text = "This tale has ended." if ended else "The adventure has not started yet."
        core.error(player.id, ErrorCode.WRONG_PHASE, text)
        return
    private = private_texts(core.state)
    lines = tuple(line for line in what_now(core.state) if not leaks(line, private))
    reply = WhatNowAnswer(lines=lines or (NOTHING,), asked_by=player.name.strip() or "A player")
    core.send(player.id, reply)
    if core.what_now_limit.allow(player.id, core.config.clock.time()):
        for conn_id in sorted(core.spectators):
            core.send_conn(conn_id, reply)
    core.diag("what_now", player=player.id, lines=len(reply.lines))
