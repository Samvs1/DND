"""Level-up through the protocol: `request_sheet` -> `sheet.level_up` options -> `level_up`.

`build_choices(options)` makes one legal pick set from the server's own `LevelUpOptions`
(first N of every group, the first subclass, an ASI when due), so it works for any class.
M29.2: `smart=True` (the campaign bots) takes the spells of `scripts.sim.spells.PREFERRED` first
and raises the class's main ability at an ASI.

Public API: `build_choices`, `level_up_bot`.
"""

from scripts.sim.bot import Bot
from scripts.sim.client import Msg
from scripts.sim.spells import prefer


def _picks(group: Msg | None, smart: bool = False) -> list[str]:
    if not group:
        return []
    ids = [o["id"] for o in group["options"]]
    return (prefer(ids) if smart else ids)[: group["choose"]]


def build_choices(options: Msg, smart: bool = False, main: str = "con") -> Msg:
    choices: Msg = {}
    if options.get("subclass"):
        choices["subclass"] = options["subclass"]["id"]
    if options.get("asi"):
        choices["asi"] = {main if smart else "con": 2}
    choices["class_choices"] = {g["id"]: _picks(g) for g in options.get("class_choices", [])}
    choices["feature_choices"] = {g["id"]: _picks(g) for g in options.get("feature_choices", [])}
    choices["cantrips"] = _picks(options.get("cantrips"))
    choices["spells"] = _picks(options.get("spells"), smart)
    if options.get("prepared"):
        choices["prepared"] = _picks(options["prepared"], smart)
    return choices


async def level_up_bot(bot: Bot, timeout: float = 20.0, main: str = "con") -> str:
    """Level the bot's hero up once; returns "ok" or the refusal text."""
    timeout *= bot.patience
    conn = bot.conn
    mark = conn.mark()
    await conn.send({"type": "request_sheet"})
    sheet = await conn.wait_for(lambda m: m["type"] == "sheet", timeout, mark)
    options = sheet.get("level_up")
    if not options:
        return "no level-up options offered"
    mark = conn.mark()
    picks = build_choices(options, bot.plan.smart, main)
    await conn.send({"type": "level_up", "choices": picks})
    got = await conn.wait_for(lambda m: m["type"] in ("error", "notice"), timeout, mark)
    return "ok" if got["type"] == "notice" else f"refused: {got['text']}"
