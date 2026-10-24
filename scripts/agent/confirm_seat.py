"""Which seat a confirmation card waits for (M32.1a X4, round 5: "Elowen ... offering him peace"
showed Elowen the parley card, then `answer confirm` without `--as` went to the host's seat, the
table said nothing was waiting for that seat, and the offer was later answered as a fight).

`confirm_seat(session)`: the name of the hero whose player the table asks to confirm or cancel
(the card the table re-sends to that seat on connect), else None. `answer confirm` and `answer
cancel` without `--as` answer for that hero.

Public API: `confirm_seat(session) -> str | None`.
"""

import contextlib

from scripts.agent.link import open_link
from scripts.agent.session import Session

WAIT_S = 1.0


async def confirm_seat(session: Session) -> str | None:
    for player in session.players:
        link = await open_link(session, player)
        try:
            seat = link.conn.player_id
            with contextlib.suppress(TimeoutError):
                await link.conn.wait_for(
                    lambda m, seat=seat: (
                        m["type"] == "pending_confirmation" and m.get("player_id") == seat
                    ),
                    WAIT_S,
                )
                return str(player["name"])
        finally:
            await link.close()
    return None
