"""Level-up through the protocol: `request_sheet` -> `sheet.level_up` options -> `level_up`.

`build_choices(options)` makes one legal pick set from the server's own `LevelUpOptions`
(first N of every group, the first subclass, an ASI when due), so it works for any class.

Public API: `build_choices`, `level_up_bot`, `grant_xp_to_level_two`.
"""

from aidm.rules.leveling import gain_xp
from scripts.sim.bot import Bot
from scripts.sim.client import Msg
from scripts.sim.server import SimServer


def _picks(group: Msg | None) -> list[str]:
    if not group:
        return []
    return [o["id"] for o in group["options"][: group["choose"]]]


def build_choices(options: Msg) -> Msg:
    choices: Msg = {}
    if options.get("subclass"):
        choices["subclass"] = options["subclass"]["id"]
    if options.get("asi"):
        choices["asi"] = {"con": 2}
    choices["class_choices"] = {g["id"]: _picks(g) for g in options.get("class_choices", [])}
    choices["feature_choices"] = {g["id"]: _picks(g) for g in options.get("feature_choices", [])}
    choices["cantrips"] = _picks(options.get("cantrips"))
    choices["spells"] = _picks(options.get("spells"))
    if options.get("prepared"):
        choices["prepared"] = _picks(options["prepared"])
    return choices


async def level_up_bot(bot: Bot, timeout: float = 20.0) -> str:
    """Level the bot's hero up once; returns "ok" or the refusal text."""
    conn = bot.conn
    mark = conn.mark()
    await conn.send({"type": "request_sheet"})
    sheet = await conn.wait_for(lambda m: m["type"] == "sheet", timeout, mark)
    options = sheet.get("level_up")
    if not options:
        return "no level-up options offered"
    mark = conn.mark()
    await conn.send({"type": "level_up", "choices": build_choices(options)})
    got = await conn.wait_for(lambda m: m["type"] in ("error", "notice"), timeout, mark)
    return "ok" if got["type"] == "notice" else f"refused: {got['text']}"


async def grant_xp_to_level_two(srv: SimServer, hero_ids: list[str]) -> None:
    """Natural play may fall short of 300 XP: top the heroes up with the engine's own `gain_xp`
    events, applied through a table job (so the log, the broadcast and `level_up_available`
    behave exactly as for earned XP)."""
    core = srv.table

    async def job() -> None:
        for hero_id in hero_ids:
            hero = core.state.creatures.get(hero_id)
            if hero is not None and hero.pc is not None and hero.pc.xp < 300:
                core.apply_all(gain_xp(hero, 300 - hero.pc.xp))

    core.schedule(job)
    await core.settle()
