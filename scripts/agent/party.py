"""The `Heroes:` block of every view (M29.7e H14): one sheet request per seated hero.

Public API: `heroes_block`.
"""

from scripts.agent.hero_view import hero_lines, supplies_line
from scripts.agent.link import Link, Msg, open_link
from scripts.agent.session import Session


async def heroes_block(session: Session, state: Msg) -> list[str]:
    """Camp supplies plus every hero's slots, spells (out of a fight) and resources."""
    lines = [supplies_line(state), "Heroes:"]
    for player in session.players:
        link: Link = await open_link(session, player)
        try:
            sheet = await link.sheet()
        finally:
            await link.close()
        if sheet:
            lines += hero_lines(sheet, bool(state.get("combat")))
    return lines
